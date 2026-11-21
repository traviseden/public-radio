"""Select FCC contours from the project's public-radio roster, never from all licensees."""

import csv
import hashlib
import json
import re
import sqlite3
from collections import defaultdict

import shapely
import yaml
from reach_sources import NAMES, ROOT, STATES
from shapely.geometry import shape


def owner_id(name):
    return "o-" + hashlib.sha256(name.casefold().strip().encode()).hexdigest()[:16]


def load_roster():
    path = ROOT / "public_radio_facility_data.sqlite"
    if not path.is_file():
        raise SystemExit("Missing full FCC database. Run make db first.")
    conn = sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    rows, geometries, owners = [], {}, defaultdict(list)
    documented = {
        r["roster_licensee"]: r
        for r in csv.DictReader((ROOT / "documented_owners.csv").open())
    }
    reviewed = {
        r["sid"]: r for r in csv.DictReader((ROOT / "reviewed_facilities.csv").open())
    }
    state_codes = {
        n.replace("_", " "): s for n, s in zip(NAMES, STATES.values(), strict=True)
    }
    state_codes.update({"Guam": "GU", "Virgin Islands": "VI", "American Samoa": "AS"})
    for source in csv.DictReader((ROOT / "station_index.csv").open()):
        if source["Type"] not in ("Radio", "Both"):
            continue
        name = source["Recipient"].strip()
        ident = "s-" + source["SID"]
        review = reviewed.get(source["SID"], {})
        call = re.sub(r"[- ](?:FM|AM)$", "", name.upper())
        state = {"Massachussetts": "Massachusetts"}.get(
            source["State"], source["State"]
        )
        entry = {
            "id": ident,
            "name": name,
            "state": state,
            "city": source["City"],
            "affiliation": source["Affiliation"].strip(),
            "licensee": source["Licensee"].strip(),
            "facility": None,
            "application": None,
            "site": None,
            "owner": None,
            "evidence": None,
            "operator_source": None,
            "lat": None,
            "lon": None,
            "reason": "No unambiguous active public FM license match in this snapshot",
        }
        rows.append(entry)
        meta_path = (
            ROOT / "stations" / (call + ".yaml")
            if re.fullmatch(r"[A-Z]{3,4}", call)
            else None
        )
        meta = (
            yaml.safe_load(meta_path.read_text())
            if meta_path and meta_path.exists()
            else {}
        )
        owner = (
            meta.get("top_level_owner")
            or (
                meta.get("licensee_name")
                if meta.get("control_of_respondent") == "N"
                else ""
            )
            or ""
        ).strip()
        if owner:
            entry["evidence"] = "Station ownership record"
        elif doc := documented.get(entry["licensee"].upper()):
            owner, entry["evidence"] = doc["owner"], doc["evidence_url"]
        if owner:
            entry["owner"] = owner_id(owner)
            owners[owner].append(ident)
        if not re.fullmatch(r"[A-Z]{3,4}", call) or name.upper().endswith(
            (" AM", "-AM")
        ):
            continue
        candidates = conn.execute(
            """
          SELECT DISTINCT facility_id,license_filing_id,community_served_state FROM facility
          WHERE callsign IN (?, ?, ?) AND facility_status='LICEN' AND active_ind='Y'
            AND (facility_type='EDT' OR facility_id=?) AND service_code IN ('FM','FL')
        """,
            (call, call + "-FM", call + "-LP", review.get("facility_id")),
        ).fetchall()
        # An explicit filing-to-facility link beats name suffixes or a
        # grantee address across a state line. Don't guess between FM and LPFM.
        filing = source["FCCID"].strip()
        linked = [
            f
            for f in candidates
            if filing
            and conn.execute(
                """
          SELECT 1 FROM application_facility af JOIN application a
            ON a.aapp_application_id=af.afac_application_id
          WHERE af.afac_facility_id=? AND a.aapp_file_num=? LIMIT 1
        """,
                (f["facility_id"], filing),
            ).fetchone()
        ]
        candidates = (
            [f for f in candidates if f["facility_id"] == review["facility_id"]]
            if review
            else linked
            or [
                f
                for f in candidates
                if f["community_served_state"] == state_codes.get(state)
            ]
        )
        if len(candidates) != 1:
            continue
        f = candidates[0]
        entry["facility"] = f["facility_id"]
        entry["operator_source"] = review.get("public_operator_evidence")
        contours = conn.execute(
            """
          SELECT DISTINCT c.geometry,c.lms_application_id,c.dts_site_number,c.transmitter_site
          FROM application_facility af JOIN fm_service_contour c
            ON c.lms_application_id=af.afac_application_id
          JOIN license_filing_version l ON l.filing_version_id=c.lms_application_id
          WHERE af.afac_facility_id=? AND af.active_ind='Y' AND c.service IN ('FM','FL')
            AND l.auth_type_code='L' AND l.current_status_code='GRA' AND l.active_ind='Y'
            AND l.license_filing_id=?
        """,
            (entry["facility"], f["license_filing_id"]),
        ).fetchall()
        if len(contours) != 1:
            entry["reason"] = (
                f"{len(contours)} matching primary licensed site records; needs review"
            )
            continue
        c = contours[0]
        geom = shape(json.loads(c["geometry"])) if c["geometry"] else None
        if (
            geom is None
            or geom.is_empty
            or not geom.is_valid
            or geom.bounds[2] - geom.bounds[0] > 180
        ):
            entry["reason"] = "Geometry needs review"
            continue
        lat, lon = (float(x) for x in c["transmitter_site"].split(","))
        entry.update(
            application=c["lms_application_id"],
            site=c["dts_site_number"],
            lat=lat,
            lon=lon,
            reason=None,
        )
        geometries[ident] = geom
    for name, members in owners.items():
        if all(member in geometries for member in members):
            geometries[owner_id(name)] = shapely.union_all(
                [geometries[m] for m in members]
            )
    conn.close()
    return rows, geometries, owners
