"""Regression checks for identity, source outages and citation coverage."""

from copy import deepcopy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import refresh_publications as registry


PERSON = {"name": "Hailong Qu", "email": "example@example.org"}
BASE = "10.1234/baseline"
NEW = "10.1234/forecast"
OLD = "2026-11-14T00:00:00Z"
NOW = "2026-11-16T00:00:00Z"
SITE = {"person": PERSON, "fields": [], "papers": [
    {"id": "curated", "title": "Prior work", "status": "published",
     "authors": "Hailong Qu, Mei Chen, Alex Lee", "links": [["DOI", "https://doi.org/" + BASE]]}]}


def work(doi, number, authors, institutions=None, count=2):
    institutions = institutions or {}
    return {"doi": "https://doi.org/" + doi, "type": "article", "title": "Classroom CO₂ forecasts",
            "id": f"https://openalex.org/W{number}", "cited_by_count": count, "is_retracted": False,
            "authorships": [{"raw_author_name": name, "author": {"display_name": name},
                             "institutions": [{"display_name": place} for place in institutions.get(name, [])]}
                            for name in authors]}


class RegistryTests(unittest.TestCase):
    def setUp(self):
        self.anchor = work(BASE, 1, ["Qu, Hailong", "Chen, Mei", "Alex Lee"],
                           {"Qu, Hailong": ["Example University"]}, 10)

    def test_namesake_ssrn_and_coauthors_affiliation_do_not_publish(self):
        people = ["Hailong Qu", "Mei Chen"]
        other = work("10.1234/namesake", 2, people, {"Mei Chen": ["Example University"]})
        ssrn = work("10.2139/ssrn.123", 3, people + ["Alex Lee"])
        new = work(NEW, 4, people, {"Hailong Qu": ["Example University"]}, 0)
        metadata = {"doi": NEW, "title": new["title"], "authors": people, "year": 2026,
                    "status": "published", "venue": "Journal", "citation": "16",
                    "url": "https://doi.org/" + NEW, "source": "Crossref"}
        with patch.object(registry, "lookup_dois", return_value=[self.anchor]), \
             patch.object(registry, "related_works", return_value=[other, ssrn, new]), \
             patch.object(registry, "recent_crossref", return_value=[]), \
             patch.object(registry, "datacite_preprints", return_value=[]), \
             patch.object(registry, "official_metadata", return_value=metadata) as verify:
            updated, snap, errors = registry.refresh(SITE, {}, NOW)
            self.assertEqual([NEW], [call.args[0]["doi"] for call in verify.call_args_list])
            self.assertEqual("built-environment", updated["papers"][0]["field"])
            self.assertEqual(2, len(updated["papers"]))
            self.assertEqual(1, snap["publication_scan"]["unconfirmed"])
            self.assertEqual((10, 1, 1), (snap["citations"], snap["h_index"], snap["i10_index"]))
            self.assertEqual(0, snap["papers"][updated["papers"][0]["id"]]["count"])
            same, second, _ = registry.refresh(updated, snap, NOW)
            self.assertEqual(updated, same)
            self.assertEqual([], second["publication_scan"]["added"])
            self.assertFalse(errors)

    def test_failed_lookups_preserve_old_counts_and_date(self):
        last = registry.citation_snapshot(SITE, [self.anchor], {}, OLD)
        with patch.object(registry, "lookup_dois", side_effect=TimeoutError), \
             patch.object(registry, "related_works", return_value=[]), \
             patch.object(registry, "recent_crossref", return_value=[]), \
             patch.object(registry, "datacite_preprints", return_value=[]):
            updated, snapshot, errors = registry.refresh(SITE, last, NOW)
        self.assertEqual(SITE, updated)
        self.assertEqual(OLD, snapshot["checked_at"])
        self.assertEqual(last["papers"], snapshot["papers"])
        self.assertEqual("partial", snapshot["publication_scan"]["status"])
        self.assertTrue(errors)

    def test_missing_known_record_is_distinct_from_a_real_zero(self):
        old = registry.citation_snapshot(SITE, [self.anchor], {}, OLD)
        with self.assertRaises(ValueError):
            registry.citation_snapshot(SITE, [], old, NOW)
        fresh = registry.citation_snapshot(SITE, [{**self.anchor, "cited_by_count": 0}], old, NOW)
        self.assertEqual((0, NOW), (fresh["citations"], fresh["checked_at"]))

    def test_one_work_is_counted_once_and_journal_doi_has_priority(self):
        site = deepcopy(SITE)
        site["papers"][0]["links"].insert(0, ["arXiv", "https://arxiv.org/abs/2601.10000v3"])
        site["papers"].append({**site["papers"][0], "id": "alias"})
        snapshot = registry.citation_snapshot(site, [self.anchor, self.anchor], {}, NOW)
        self.assertEqual(BASE, registry.paper_doi(site["papers"][0]))
        self.assertEqual(10, snapshot["citations"])
        self.assertEqual(1, snapshot["h_index"])

    def test_unindexed_new_record_does_not_create_zero_count(self):
        site = deepcopy(SITE)
        site["papers"].append({"id": "unindexed", "links": [["DOI", "https://doi.org/" + NEW]]})
        snapshot = registry.citation_snapshot(site, [self.anchor], {}, NOW)
        self.assertEqual({"curated"}, set(snapshot["papers"]))

    def test_unrelated_openalex_cluster_is_never_requested(self):
        for i, author in enumerate(self.anchor["authorships"], 1):
            author["author"]["id"] = f"https://openalex.org/A{i}"
        with patch.object(registry, "oa_works", return_value=[]) as fetch:
            registry.related_works([self.anchor], PERSON)
        fetch.assert_called_once_with("author.id:A1")


if __name__ == "__main__":
    unittest.main()
