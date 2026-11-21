"""Produce a compact, indexed build-time SQLite snapshot, atomically."""

import hashlib
import os
import sqlite3
import tempfile
from datetime import date
from pathlib import Path

import numpy as np
import shapely
from reach_metrics import METRICS, acs_values
from reach_overlay import overlays
from reach_roster import load_roster, owner_id
from reach_sources import CACHE, ROOT, fetch

SCHEMA = """
PRAGMA foreign_keys=ON;
CREATE TABLE target(id TEXT PRIMARY KEY,kind TEXT NOT NULL,name TEXT NOT NULL,
  residents INTEGER,unassigned_residents INTEGER,geometry TEXT) WITHOUT ROWID;
CREATE INDEX target_directory ON target(kind,name COLLATE NOCASE,id);
CREATE TABLE station(id TEXT PRIMARY KEY REFERENCES target, state TEXT, city TEXT, affiliation TEXT,
  licensee TEXT, facility TEXT, application TEXT, site TEXT, owner TEXT REFERENCES target,
  evidence TEXT, operator_source TEXT, lat REAL, lon REAL, reason TEXT) WITHOUT ROWID;
CREATE INDEX station_state ON station(state,id);
CREATE INDEX station_owner ON station(owner,id) WHERE owner IS NOT NULL;
CREATE INDEX station_facility ON station(facility) WHERE facility IS NOT NULL;
CREATE INDEX station_application ON station(application,site) WHERE application IS NOT NULL;
CREATE INDEX station_affiliation ON station(affiliation,id);
CREATE INDEX station_licensee ON station(licensee COLLATE NOCASE,id);
CREATE TABLE footprint_key(spatial_id INTEGER PRIMARY KEY,target_id TEXT NOT NULL UNIQUE REFERENCES target);
CREATE VIRTUAL TABLE footprint_bounds USING rtree(spatial_id,west,east,south,north);
CREATE TABLE metric(id TEXT PRIMARY KEY, label TEXT, universe TEXT, source TEXT, ordinal INTEGER) WITHOUT ROWID;
CREATE TABLE profile(target_id TEXT REFERENCES target, metric_id TEXT REFERENCES metric, estimate REAL,
  moe90 REAL, missing_groups INTEGER NOT NULL, PRIMARY KEY(target_id,metric_id)) WITHOUT ROWID;
CREATE TABLE build(key TEXT PRIMARY KEY,value TEXT) WITHOUT ROWID;
"""


def profiles(db, weights):
    gids = sorted({g for records in weights.values() for g, *_ in records})
    indices = {g: i for i, g in enumerate(gids)}
    acs = acs_values(CACHE, gids)
    for ident, records in weights.items():
        ix = [indices[r[0]] for r in records]
        supports = np.asarray([r[1:] for r in records], dtype=float)
        for i, (key, _, _, _, _, support) in enumerate(METRICS):
            w = supports[:, int(support == "households")]
            estimates, margins = acs[ix, i, :].T
            # An unknown weight with positive/unknown source estimate cannot
            # be counted as zero. Keep the subtotal and mark incomplete.
            unknown = (~np.isfinite(w) & (estimates != 0)) | (
                (w > 0) & ~np.isfinite(estimates)
            )
            use = (w > 0) & np.isfinite(estimates)
            estimate = float(np.sum(w[use] * estimates[use]))
            moe = None
            if (
                not unknown.any()
                and not ((~np.isfinite(w)) & (margins != 0)).any()
                and np.isfinite(margins[use]).all()
            ):
                moe = float(np.sqrt(np.sum(np.square(w[use] * margins[use]))))
            db.execute(
                "INSERT INTO profile VALUES(?,?,?,?,?)",
                (ident, key, estimate, moe, int(unknown.sum())),
            )


def build():
    stations, geometries, owners = load_roster()
    fetch()
    print(
        f"{len(stations)} roster entries; {len(geometries)} station and owner footprints",
        flush=True,
    )
    pop, weights, missing = overlays(geometries)
    with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
        path = Path(tmp) / "web.sqlite"
        db = sqlite3.connect(path)
        db.executescript(SCHEMA)
        for ident, kind, name in [(s["id"], "station", s["name"]) for s in stations] + [
            (owner_id(n), "owner", n) for n in owners
        ]:
            geom = geometries.get(ident)
            display = shapely.to_geojson(geom) if geom is not None else None
            db.execute(
                "INSERT INTO target VALUES(?,?,?,?,?,?)",
                (ident, kind, name, pop.get(ident), missing.get(ident), display),
            )
            if geom is not None:
                key = db.execute(
                    "INSERT INTO footprint_key(target_id) VALUES(?)", (ident,)
                ).lastrowid
                west, south, east, north = geom.bounds
                db.execute(
                    "INSERT INTO footprint_bounds VALUES(?,?,?,?,?)",
                    (key, west, east, south, north),
                )
        for entry in stations:
            db.execute(
                """INSERT INTO station VALUES(:id,:state,:city,:affiliation,:licensee,:facility,
                          :application,:site,:owner,:evidence,:operator_source,:lat,:lon,:reason)""",
                entry,
            )
        db.executemany(
            "INSERT INTO metric VALUES(?,?,?,?,?)",
            [
                (key, label, universe, table, i)
                for i, (key, label, universe, table, *_) in enumerate(METRICS)
            ],
        )
        profiles(db, weights)
        manifest = (CACHE / "manifest.json").read_text()
        info = {
            "built": str(date.today()),
            "census": "2020 Census, April 1",
            "acs": "2020–2024 ACS 5-year detailed tables",
            "source_manifest": manifest,
            "roster_sha256": hashlib.sha256(
                (ROOT / "station_index.csv").read_bytes()
            ).hexdigest(),
            "fcc_contours_file": "FM_service_contour_current.txt",
        }
        for key, source in [
            ("fcc_database", ROOT / "public_radio_facility_data.sqlite"),
            ("fcc_contours", ROOT / "tables/FM_service_contour_current.txt"),
            ("owner_evidence", ROOT / "documented_owners.csv"),
            ("reviewed_facilities", ROOT / "reviewed_facilities.csv"),
        ]:
            if source.exists():
                digest = hashlib.sha256()
                with source.open("rb") as f:
                    for chunk in iter(lambda: f.read(1 << 20), b""):
                        digest.update(chunk)
                info[key + "_sha256"] = digest.hexdigest()
        db.executemany("INSERT INTO build VALUES(?,?)", info.items())
        db.execute("ANALYZE")
        violations = db.execute("PRAGMA foreign_key_check").fetchall()
        if violations or db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("Invalid web database")
        db.commit()
        db.close()
        os.replace(path, ROOT / "web.sqlite")
    print(
        f"Created web.sqlite ({(ROOT / 'web.sqlite').stat().st_size:,} bytes)",
        flush=True,
    )


if __name__ == "__main__":
    build()
