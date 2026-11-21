import sqlite3
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import shapely

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import build_web_db as builder
import reach_overlay as overlay


class OverlayTest(unittest.TestCase):
    def test_overlapping_owners_and_different_household_weights(self):
        # The two census polygons are broader than the footprints. Assignment
        # must use actual point positions and the correct population universe.
        groups = [shapely.box(0, 0, 2, 2), shapely.box(2, 0, 4, 2)]
        a, b = shapely.box(0, 0, 1.5, 2), shapely.box(1, 0, 3, 2)
        inputs = (
            np.array([0.25, 1.25, 2.75, 3.75]),
            np.ones(4),
            np.array([10, 60, 15, 15]),
            np.array([8, 12, 3, 9]),
        )
        layer = (
            {"crs": "EPSG:4269"},
            None,
            shapely.to_wkb(groups),
            [np.array(["west", "east"])],
        )
        with (
            patch.object(overlay, "STATES", {"11": "DC"}),
            patch.object(overlay.pyogrio.raw, "read", return_value=layer),
            patch.object(overlay, "block_support", return_value=inputs),
        ):
            totals, weights, missing = overlay.overlays(
                {"a": a, "b": b, "owner": a.union(b)}
            )
        self.assertEqual(dict(totals), {"a": 70, "b": 75, "owner": 85})
        self.assertFalse(any(missing.values()))
        w = {g: (p, h) for g, p, h in weights["b"]}
        np.testing.assert_allclose(w["west"], [60 / 70, 12 / 20])
        np.testing.assert_allclose(w["east"], [0.5, 0.25])

    def test_missing_support_is_not_zero_and_margins_are_weighted(self):
        db = sqlite3.connect(":memory:")
        self.addCleanup(db.close)
        db.execute("create table profile(target,metric,estimate,moe,missing)")
        # One group contributes entirely and one by half. Household support
        # in the second group is unavailable; don't publish a complete total.
        weights = {"test": [("a", 1, 1), ("b", 0.5, None)]}
        values = np.array([[[50, 3], [25, 2]], [[20, 8], [10, 5]]])
        metrics = [
            ("pop", "", "", "", [1], "people"),
            ("hh", "", "", "", [1], "households"),
        ]
        with (
            patch.object(builder, "METRICS", metrics),
            patch.object(builder, "acs_values", return_value=values),
        ):
            builder.profiles(db, weights)
        self.assertEqual(
            db.execute(
                "select estimate,moe,missing from profile where metric='pop'"
            ).fetchone(),
            (60, 5, 0),
        )
        self.assertEqual(
            db.execute(
                "select estimate,moe,missing from profile where metric='hh'"
            ).fetchone(),
            (25, None, 1),
        )
