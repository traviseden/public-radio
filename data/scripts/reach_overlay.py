"""Batch geometry work; no spatial extension is required to open the web database."""

from collections import defaultdict
from zipfile import ZipFile

import numpy as np
import pandas as pd
import pyogrio.raw
import shapely as sh
from pyproj import Transformer
from reach_sources import CACHE, STATES


def block_support(abbr):
    # 2020 P.L. geographic header: block summary level 750, population, housing,
    # internal point. Segment 02 ends with H1 total/occupied/vacant. Join by
    # LOGRECNO, not file ordering; never use all housing units for households.
    with ZipFile(CACHE / f"{abbr.lower()}2020.pl.zip") as z:
        with z.open(f"{abbr.lower()}geo2020.pl") as file:
            geo = pd.read_csv(
                file,
                sep="|",
                header=None,
                encoding="latin1",
                quoting=3,
                usecols=[2, 7, 90, 91, 92, 93],
                low_memory=False,
            )
        geo = geo.loc[geo[2] == 750].set_index(7, verify_integrity=True)
        with z.open(f"{abbr.lower()}000022020.pl") as file:
            occupancy = pd.read_csv(
                file, sep="|", header=None, usecols=[4, 149, 150, 151]
            ).set_index(4, verify_integrity=True)
    occ = occupancy.loc[geo.index]
    if not np.array_equal(geo[91], occ[149]) or not np.array_equal(
        occ[149], occ[150] + occ[151]
    ):
        raise ValueError(f"{abbr}: H1 housing count mismatch")
    return (
        geo[93].to_numpy(),
        geo[92].to_numpy(),
        geo[90].to_numpy(dtype=np.int64),
        occ[150].to_numpy(dtype=np.int64),
    )


def overlays(geometries):
    # Block point coordinates and 2024 TIGER BGs are NAD83 lon/lat.
    transform = Transformer.from_crs(4326, 4269, always_xy=True)
    ids = list(geometries)
    targets = sh.transform(
        np.array(list(geometries.values()), dtype=object),
        transform.transform,
        interleaved=False,
    )
    tree = sh.STRtree(targets)
    pop20 = defaultdict(int)
    missing = defaultdict(int)
    weights = defaultdict(list)
    for fp, abbr in STATES.items():
        meta, _, wkb, fields = pyogrio.raw.read(
            CACHE / f"tl_2024_{fp}_bg.zip", columns=["GEOID"]
        )
        if meta["crs"] != "EPSG:4269":
            raise ValueError(f"Unexpected BG CRS: {meta['crs']}")
        geoms = sh.from_wkb(wkb)
        bg_idx, tgt_idx = tree.query(geoms, predicate="intersects")
        if not len(bg_idx):
            continue
        needed = np.unique(bg_idx)
        shapes, codes = geoms[needed], fields[0][needed]
        # State-sized work only; compress to BGs intersecting a selected target.
        bgids = np.searchsorted(needed, bg_idx)
        x, y, pop, hh = block_support(abbr)
        keep = (pop > 0) | (hh > 0)
        pts = sh.points(x[keep], y[keep])
        pop, hh = pop[keep], hh[keep]
        # Assign old internal points spatially, not by truncating GEOID20.
        pi, bi = sh.STRtree(shapes).query(pts, predicate="covered_by")
        assignment = np.full(len(pts), -1)
        if len(pi):
            # A shared boundary gets one deterministic assignment.
            ordered = np.lexsort((codes[bi], pi))
            unique, first = np.unique(pi[ordered], return_index=True)
            assignment[unique] = bi[ordered[first]]
        mapped = assignment >= 0

        n_groups = len(shapes)

        def counts(groups, values, size=n_groups):
            return np.bincount(groups, weights=values, minlength=size)

        totals = [counts(assignment[mapped], a[mapped]) for a in (pop, hh)]
        points_tree = sh.STRtree(pts)
        for ti in np.unique(tgt_idx):
            target, ident = targets[ti], ids[ti]
            covered = points_tree.query(target, predicate="covers")
            pop20[ident] += int(pop[covered].sum())
            assigned = covered[assignment[covered] >= 0]
            missing[ident] += int(pop[covered[assignment[covered] < 0]].sum())
            selected = [counts(assignment[assigned], a[assigned]) for a in (pop, hh)]
            bs = bgids[tgt_idx == ti]
            full = sh.covers(target, shapes[bs])
            # Exclude boundary-only intersections. The dimensional predicate
            # checks the interiors, without treating angular area as metres.
            partial = ~full
            positive = full.copy()
            positive[partial] = sh.relate_pattern(
                target, shapes[bs[partial]], "2********"
            )
            for b, entire in zip(bs[positive], full[positive], strict=True):
                ws = [
                    1.0 if entire else s[b] / t[b] if t[b] else None
                    for s, t in zip(selected, totals, strict=True)
                ]
                weights[ident].append((codes[b], *ws))
        print(f"{abbr}: {len(shapes):,} intersecting block groups", flush=True)
    return pop20, weights, missing
