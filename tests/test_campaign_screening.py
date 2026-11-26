"""Check the contract between a campaign aggregate, its signed positions and a search step."""
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "EVALUATE"))
from campaign_screening import FILM, REGISTER, SITE, apply_position_screen, search_trajectory


class CampaignScreeningTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root / REGISTER).parent.mkdir()
        films = [
            ["A", "recast", "F1", "Validation", "KEEP", "paired"],
            ["A", "failed", "F2", "Exploration", "DISCARD", "one position"],
            ["A", "missing aggregate", "F3", "Exploration", "DISCARD", "no pair"],
        ]
        sites = [["P1", 1, "reps.csv", "recast | rep 1", "sample 5", 10., .2],
                 ["P3", 3, "reps.csv", "recast | rep 3", "sample 7", 30., .6]]
        reviews = [films[0] + row for row in sites]
        reviews.extend(film + [None] * len(SITE) for film in films[1:])
        self.review = pd.DataFrame(reviews, columns=FILM + SITE)
        self.review.to_csv(self.root / REGISTER, index=False)
        self.fits = pd.DataFrame({
            "name": ["recast | rep 1", "recast | rep 2", "recast | rep 3"],
            "Trial": ["sample 5", "sample 6", "sample 7"],
            "Good Fit": [True, True, True],
            "Elastic Modulus": [10., 1000., 30.], "Pore Fraction": [.2, .99, .6],
            "Thickness": [100., 300., np.nan]})
        self.fits.to_csv(self.root / "reps.csv", index=False)
        self.aggregate = pd.DataFrame({
            "campaign": "A", "condition": ["recast", "failed", "missing aggregate", "new"],
            "Elastic Modulus Mean": [99., 50., np.nan, 50.], "Pore Fraction Mean": .8,
            "Elastic Modulus SD": 33., "Pore Fraction SD": .1, "Thickness Mean": 72.,
            "Thickness SD": 10., "Humidity Mean": 39., "Humidity SD": 2., "CV PreDiscard Mean": .14})

    def test_joint_measurements_and_each_exclusion(self):
        films, log = apply_position_screen(self.aggregate, self.root)
        self.assertEqual(log.screening_outcome.tolist(), [
            "Retained", "Failed position review", "Missing or invalid aggregate objective pair", "No reviewed film"])
        self.assertEqual(films.condition.tolist(), ["recast"])
        film = films.iloc[0]
        self.assertEqual(film.screened_position_count, 2)
        self.assertEqual(film["Elastic Modulus Mean"], 20.)
        self.assertAlmostEqual(film["Pore Fraction Mean"], .4)
        self.assertAlmostEqual(film["Elastic Modulus SD"], np.sqrt(200))
        self.assertEqual(film["Thickness N"], 1)
        self.assertEqual(film["Thickness Mean"], 100.)
        self.assertTrue(np.isnan(film["Thickness SD"]))
        self.assertEqual(film["Humidity SD"], 2.)
        self.assertEqual(film["CV PreDiscard Mean"], .14)

    def test_duplicate_and_changed_fits_require_review(self):
        pd.concat([self.review, self.review.iloc[[0]]]).to_csv(self.root / REGISTER, index=False)
        with self.assertRaisesRegex(ValueError, "distinct"):
            apply_position_screen(self.aggregate, self.root)
        self.review.to_csv(self.root / REGISTER, index=False)
        self.fits.loc[0, "Pore Fraction"] += .02
        self.fits.to_csv(self.root / "reps.csv", index=False)
        with self.assertRaisesRegex(ValueError, "changed since"):
            apply_position_screen(self.aggregate, self.root)

    def test_only_explicit_true_flags_count_toward_the_two_position_minimum(self):
        for flag in ["False", None, "unknown", "1"]:
            with self.subTest(flag=flag):
                self.fits["Good Fit"] = ["True", "True", flag]
                self.fits.to_csv(self.root / "reps.csv", index=False)
                films, log = apply_position_screen(self.aggregate, self.root)
                self.assertTrue(films.empty)
                self.assertEqual(log.iloc[0].good_fit_position_count, 1)
                self.assertEqual(log.iloc[0].screening_outcome,
                                 "Fewer than two positions with archived Good Fit")

    def test_failed_reviewed_position_does_not_contribute_to_either_mean(self):
        site = self.review.iloc[0].copy()
        site[SITE] = ["P2", 2, "reps.csv", "recast | rep 2", "sample 6", 1000., .99]
        pd.concat([self.review, site.to_frame().T]).to_csv(self.root / REGISTER, index=False)
        self.fits.loc[1, "Good Fit"] = False
        self.fits.to_csv(self.root / "reps.csv", index=False)
        films, log = apply_position_screen(self.aggregate, self.root)
        self.assertEqual(log.iloc[0].reviewed_position_count, 3)
        self.assertEqual(films.iloc[0].good_fit_position_count, 2)
        self.assertEqual(films.iloc[0]["Elastic Modulus Mean"], 20.)
        self.assertAlmostEqual(films.iloc[0]["Pore Fraction Mean"], .4)

    def test_trajectory_numbers_only_screened_search_films(self):
        films = pd.DataFrame({"campaign": "A", "condition": ["single", "explore", "repeat", "dual"],
                              "sample_time": [1, 2, 3, 4], "iteration": [1, 2, 3, 4],
                              "screening_phase": ["Single", "Exploration", "Validation", "Dual objective"]})
        t = search_trajectory(films)
        self.assertEqual(t.condition.tolist(), ["explore", "dual"])
        self.assertEqual(t.iteration.tolist(), [1, 2])
        self.assertEqual(films.iteration.tolist(), [1, 2, 3, 4])
