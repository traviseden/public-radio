"""Fetch a bounded, vintage-matched DC sample for comparing Census products."""

import csv
import hashlib
import io
import json
import os
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zipfile import ZipFile

OUT = Path(__file__).resolve().parent.parent / "downloads" / "census-sample"
API = "https://api.census.gov/data"
TIGER = "https://www2.census.gov/geo/tiger"
PRODUCTS = [
    ("2024/acs/acs5", "B01003", ["B01003_001E", "B01003_001M"], "block group",
     f"{TIGER}/TIGER2024/BG/tl_2024_11_bg.zip"),
    ("2020/dec/dhc", "P1", ["P1_001N"], "block",
     f"{TIGER}/TIGER2020/TABBLOCK20/tl_2020_11_tabblock20.zip"),
]


def fetch(url):
    # Do not print exception URLs: optional data queries contain an API key.
    try:
        with urlopen(Request(url, headers={"User-Agent": "public-radio-census-sample/1"}), timeout=90) as response:
            return response.read()
    except OSError as error:
        raise SystemExit(f"Census download failed ({type(error).__name__}); rerun the target.") from None


def save(name, content, source):
    path = OUT / name
    temp = path.with_suffix(path.suffix + ".part")
    temp.write_bytes(content)
    temp.replace(path)
    return {"file": name, "source": source, "bytes": len(content), "sha256": hashlib.sha256(content).hexdigest()}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    key = os.environ.get("CENSUS_API_KEY")
    manifest = []
    for dataset, table, fields, unit, geometry_url in PRODUCTS:
        metadata_url = f"{API}/{dataset}/groups/{table}.json"
        metadata = fetch(metadata_url)
        if not set(fields) <= json.loads(metadata)["variables"].keys():
            raise ValueError(f"{table}: missing expected variables")
        manifest.append(save(f"{table}-dictionary.json", metadata, metadata_url))
        geometry = fetch(geometry_url)
        with ZipFile(io.BytesIO(geometry)) as archive:
            if archive.testzip() or not any(name.endswith(".shp") for name in archive.namelist()):
                raise ValueError(f"{table}: incomplete TIGER archive")
        manifest.append(save(geometry_url.rsplit("/", 1)[1], geometry, geometry_url))
        if key:
            params = {"get": ",".join(fields), "for": f"{unit}:*", "in": "state:11 county:001 tract:*"}
            source = f"{API}/{dataset}?{urlencode(params)}"
            rows = json.loads(fetch(source + "&" + urlencode({"key": key})))
            header, *records = rows
            geo = ["state", "county", "tract", unit]
            if not records or not set(fields + geo) <= set(header):
                raise ValueError(f"{table}: unexpected data response")
            buf = io.StringIO()
            writer = csv.writer(buf)
            writer.writerow(["GEOID", *fields])
            for row in records:
                record = dict(zip(header, row, strict=True))
                writer.writerow(["".join(record[k] for k in geo), *(record[k] for k in fields)])
            manifest.append(save(f"{table}-dc.csv", buf.getvalue().encode(), source))
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"{len(manifest)} verified source files in {OUT}")
    if not key:
        print("Set CENSUS_API_KEY to also fetch population observations (CSV); dictionaries are metadata only.")


if __name__ == "__main__":
    main()
