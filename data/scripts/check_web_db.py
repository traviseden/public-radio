"""Check the portable snapshot independently, including lookup plans."""

import csv
import sqlite3
from pathlib import Path

root = Path(__file__).resolve().parents[1]
c = sqlite3.connect(f"{(root / 'web.sqlite').as_uri()}?mode=ro", uri=True)
assert c.execute("pragma integrity_check").fetchone()[0] == "ok"
assert not c.execute("pragma foreign_key_check").fetchall()
roster = {
    "s-" + r["SID"]
    for r in csv.DictReader((root / "station_index.csv").open())
    if r["Type"] in ("Radio", "Both")
}
assert {i for (i,) in c.execute("select id from station")} == roster
assert not c.execute(
    "select id from target where residents<0 or (residents is not null and geometry is null)"
).fetchall()
assert not c.execute("""select t.id from target t left join profile p on p.target_id=t.id
    group by t.id having count(p.metric_id) != case when t.residents is null then 0 else (select count(*) from metric) end""").fetchall()
assert not c.execute("""select p.target_id from profile p where estimate<0 or moe90<0
    or (missing_groups>0 and moe90 is not null)""").fetchall()
assert not c.execute("""select o.id from target o join station s on s.owner=o.id join target t on t.id=s.id
    where o.kind='owner' group by o.id having o.residents<max(t.residents) or o.residents>sum(t.residents)""").fetchall()
assert (
    c.execute("select count(*) from footprint_bounds").fetchone()
    == c.execute("select count(geometry) from target").fetchone()
)
for query, index in [
    (
        "select id from target where kind='station' and name like 'WAM%' order by name collate nocase",
        "target_directory",
    ),
    ("select id from station where state='Virginia'", "station_state"),
    ("select id from station where owner='o-example'", "station_owner"),
    ("select id from station where facility='65399'", "station_facility"),
    (
        "select id from station where application='test' and site='01'",
        "station_application",
    ),
    (
        "select estimate from profile where target_id='s-135' and metric_id='population'",
        "PRIMARY KEY",
    ),
    (
        "select spatial_id from footprint_bounds where west<=-77 and east>=-77 and south<=39 and north>=39",
        "VIRTUAL TABLE INDEX",
    ),
]:
    plan = " ".join(r[-1] for r in c.execute("explain query plan " + query))
    assert index in plan, (query, plan)
print(
    "Verified roster completeness, profile integrity, owner bounds and indexed lookup plans."
)
