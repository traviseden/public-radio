"""Pinned, keyless Census inputs. Cache complete downloads; never put Census .dat in FCC tables/."""

import hashlib
import json
import shutil
import time
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "downloads" / "reach"
STATES = dict(
    item.split(":")
    for item in [
        "01:AL",
        "02:AK",
        "04:AZ",
        "05:AR",
        "06:CA",
        "08:CO",
        "09:CT",
        "10:DE",
        "11:DC",
        "12:FL",
        "13:GA",
        "15:HI",
        "16:ID",
        "17:IL",
        "18:IN",
        "19:IA",
        "20:KS",
        "21:KY",
        "22:LA",
        "23:ME",
        "24:MD",
        "25:MA",
        "26:MI",
        "27:MN",
        "28:MS",
        "29:MO",
        "30:MT",
        "31:NE",
        "32:NV",
        "33:NH",
        "34:NJ",
        "35:NM",
        "36:NY",
        "37:NC",
        "38:ND",
        "39:OH",
        "40:OK",
        "41:OR",
        "42:PA",
        "44:RI",
        "45:SC",
        "46:SD",
        "47:TN",
        "48:TX",
        "49:UT",
        "50:VT",
        "51:VA",
        "53:WA",
        "54:WV",
        "55:WI",
        "56:WY",
        "72:PR",
    ]
)
NAMES = [
    "Alabama",
    "Alaska",
    "Arizona",
    "Arkansas",
    "California",
    "Colorado",
    "Connecticut",
    "Delaware",
    "District_of_Columbia",
    "Florida",
    "Georgia",
    "Hawaii",
    "Idaho",
    "Illinois",
    "Indiana",
    "Iowa",
    "Kansas",
    "Kentucky",
    "Louisiana",
    "Maine",
    "Maryland",
    "Massachusetts",
    "Michigan",
    "Minnesota",
    "Mississippi",
    "Missouri",
    "Montana",
    "Nebraska",
    "Nevada",
    "New_Hampshire",
    "New_Jersey",
    "New_Mexico",
    "New_York",
    "North_Carolina",
    "North_Dakota",
    "Ohio",
    "Oklahoma",
    "Oregon",
    "Pennsylvania",
    "Rhode_Island",
    "South_Carolina",
    "South_Dakota",
    "Tennessee",
    "Texas",
    "Utah",
    "Vermont",
    "Virginia",
    "Washington",
    "West_Virginia",
    "Wisconsin",
    "Wyoming",
    "Puerto_Rico",
]
TABLES = ("B01003", "B01001", "B03002", "B15003", "C17002", "B19001", "B25003")
BASE = "https://www2.census.gov"


def sources():
    for (fp, abbr), name in zip(STATES.items(), NAMES, strict=True):
        yield f"{BASE}/programs-surveys/decennial/2020/data/01-Redistricting_File--PL_94-171/{name}/{abbr.lower()}2020.pl.zip"
        yield f"{BASE}/geo/tiger/TIGER2024/BG/tl_2024_{fp}_bg.zip"
    for table in TABLES:
        yield f"{BASE}/programs-surveys/acs/summary_file/2024/table-based-SF/data/5YRData/acsdt5y2024-{table.lower()}.dat"


def download(url):
    path = CACHE / url.rsplit("/", 1)[1]
    if not path.is_file():
        temp = path.with_suffix(path.suffix + ".part")
        for attempt in range(3):
            try:
                with (
                    urllib.request.urlopen(url, timeout=240) as r,
                    temp.open("wb") as f,
                ):
                    if r.status != 200:
                        raise ValueError(f"Unexpected HTTP {r.status} for {url}")
                    shutil.copyfileobj(r, f, 1 << 20)
                    length = r.headers.get("Content-Length")
                if length and temp.stat().st_size != int(length):
                    raise ValueError("Incomplete download")
                if path.suffix == ".zip":
                    with zipfile.ZipFile(temp) as archive:
                        if not archive.namelist():
                            raise ValueError("Empty archive")
                else:
                    with temp.open("rb") as f:
                        if not f.readline().startswith(b"GEO_ID|"):
                            raise ValueError(f"Unexpected table header: {url}")
                temp.replace(path)
                break
            except Exception:
                temp.unlink(missing_ok=True)
                if attempt == 2:
                    raise
                time.sleep(2**attempt)
        print(f"Fetched {path.name}", flush=True)
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return {"url": url, "sha256": digest.hexdigest(), "bytes": path.stat().st_size}


def fetch():
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / "manifest.json"
    previous = (
        {row["url"]: row["sha256"] for row in json.loads(path.read_text())}
        if path.exists()
        else {}
    )
    with ThreadPoolExecutor(max_workers=6) as pool:
        manifest = list(pool.map(download, sources()))
    for row in manifest:
        if row["url"] in previous and previous[row["url"]] != row["sha256"]:
            raise ValueError(f"Source differs from cached manifest: {row['url']}")
    temp = path.with_suffix(".part")
    temp.write_text(json.dumps(manifest, indent=2) + "\n")
    temp.replace(path)


if __name__ == "__main__":
    fetch()
