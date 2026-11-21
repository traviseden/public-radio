"""Additive ACS cells only; each result has a declared universe/support."""

import numpy as np


def metric(key, label, universe, table, cells, support="people"):
    return key, label, universe, table, tuple(cells), support


METRICS = [
    metric("population", "Residents", "All residents", "B01003", [1]),
    metric(
        "children", "Under 18", "All residents", "B01001", [3, 4, 5, 6, 27, 28, 29, 30]
    ),
    metric(
        "working_age",
        "18–64",
        "All residents",
        "B01001",
        [*range(7, 20), *range(31, 44)],
    ),
    metric(
        "seniors",
        "65 and older",
        "All residents",
        "B01001",
        [*range(20, 26), *range(44, 50)],
    ),
    metric("hispanic", "Hispanic or Latino, any race", "All residents", "B03002", [12]),
    *[
        metric(
            "race_" + str(n), label + " (not Hispanic)", "All residents", "B03002", [n]
        )
        for n, label in [
            (3, "White alone"),
            (4, "Black alone"),
            (5, "American Indian or Alaska Native alone"),
            (6, "Asian alone"),
            (7, "Native Hawaiian or Pacific Islander alone"),
            (8, "Other race alone"),
            (9, "Two or more races"),
        ]
    ],
    metric("adults25", "Adults 25 and older", "Residents aged 25+", "B15003", [1]),
    metric(
        "degree",
        "Bachelor’s degree or higher",
        "Residents aged 25+",
        "B15003",
        range(22, 26),
    ),
    metric(
        "poverty_base",
        "Residents with determined poverty status",
        "Poverty universe",
        "C17002",
        [1],
    ),
    metric("poverty", "Below the poverty level", "Poverty universe", "C17002", [2, 3]),
    *[
        metric("income_" + str(i), label, "Households", "B19001", cells, "households")
        for i, (label, cells) in enumerate(
            [
                ("Income below $25,000", range(2, 6)),
                ("$25,000–49,999", range(6, 11)),
                ("$50,000–99,999", range(11, 14)),
                ("$100,000 or more", range(14, 18)),
            ]
        )
    ],
    metric(
        "households", "Occupied households", "Households", "B25003", [1], "households"
    ),
    metric("owned", "Owner occupied", "Households", "B25003", [2], "households"),
    metric("rented", "Renter occupied", "Households", "B25003", [3], "households"),
]


def acs_values(cache, geoids):
    """Read only BG rows for intersecting units. Missing/sentinel cells become NaN."""
    indices = {g: i for i, g in enumerate(geoids)}
    values = np.full((len(geoids), len(METRICS), 2), np.nan)
    for table in dict.fromkeys(m[3] for m in METRICS):
        wanted = [(i, m[4]) for i, m in enumerate(METRICS) if m[3] == table]
        with (cache / f"acsdt5y2024-{table.lower()}.dat").open("rb") as f:
            header = f.readline().decode().strip().split("|")
            cols = [
                (
                    i,
                    [
                        [header.index(f"{table}_{kind}{n:03d}") for n in cells]
                        for kind in "EM"
                    ],
                )
                for i, cells in wanted
            ]
            for line in f:
                if not line.startswith(b"1500000US"):
                    continue
                idx = indices.get(line[9:21].decode())
                if idx is None:
                    continue
                row = line.rstrip().split(b"|")
                for i, (es, ms) in cols:
                    for k, group in enumerate((es, ms)):
                        cells = [row[c] for c in group]
                        if all(c.isdigit() for c in cells):
                            nums = list(map(int, cells))
                            values[idx, i, k] = (
                                sum(nums) if k == 0 else sum(v * v for v in nums) ** 0.5
                            )
    return values
