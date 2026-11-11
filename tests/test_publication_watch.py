"""Verify publication identity, visibility, deduplication and editorial preservation."""

from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import publication_watch as watch
import build


PERSON = {"name": "Hailong Qu", "email": "example@example.org"}
STAMP = "2026-11-11T07:00:00Z"
TITLE = "Learning physical constraints for electrical transmission lines"


def work(**changes):
    value = {"type": "journal-article", "title": [TITLE], "DOI": "10.1234/example",
             "container-title": ["Example Engineering Journal"], "volume": "12", "article-number": "34",
             "author": [{"given": "Hailong", "family": "Qu"}, {"given": "Another", "family": "Author"}],
             "published": {"date-parts": [[2026, 11, 1]]}}
    value.update(changes)
    return value


def record(title=TITLE, work_id="fixture:new"):
    return {"work_id": work_id, "title": title, "venue": "Example Engineering Journal", "year": "2026"}


class PublicationTests(unittest.TestCase):
    def setUp(self):
        self.metadata = watch.crossref_record(work(), TITLE, PERSON)
        self.site = {"person": PERSON, "papers": [], "fields": [], "degrees": ["preserve"]}

    def test_dataset_wrong_author_near_title_and_unpublished_record_are_rejected(self):
        cases = [work(type="dataset"), work(author=[{"given": "Haifeng", "family": "Qu"}]),
                 work(title=[TITLE + " using a different experiment"])]
        unregistered = work()
        unregistered.pop("published")
        cases.append(unregistered)
        for value in cases:
            with self.subTest(value=value):
                self.assertIsNone(watch.crossref_record(value, TITLE, PERSON))

    def test_new_public_article_is_added_with_only_verified_metadata(self):
        with patch.object(watch, "public_record", return_value=(self.metadata, 0)):
            updated, scan = watch.sync_publications([record()], self.site, {}, STAMP)
        paper = updated["papers"][0]
        self.assertEqual("electrical", paper["field"])
        self.assertEqual("first", paper["role"])
        self.assertEqual("published", paper["status"])
        self.assertEqual([["DOI", "https://doi.org/10.1234/example"]], paper["links"])
        self.assertEqual("12, 34", paper["citation"])
        self.assertEqual(1, len(scan["added"]))
        self.assertNotIn("top", paper)
        self.assertNotIn("zh_title", paper)
        self.assertNotIn("note", paper)
        self.assertEqual([], self.site["papers"])
        self.assertEqual(["preserve"], updated["degrees"])
        for locale in ("en", "zh"):
            html = build.paper_entry(paper, locale, "/")
            self.assertEqual(1, html.count(TITLE))
            self.assertNotIn('class="paper-note"', html)
            self.assertNotIn('class="figure-grid"', html)
            self.assertIn("10.1234/example", html)

    def test_nonfirst_author_does_not_gain_a_corresponding_or_cofirst_claim(self):
        metadata = {**self.metadata, "authors": ["Another Author", "Hailong Qu"]}
        with patch.object(watch, "public_record", return_value=(metadata, 0)):
            updated, _ = watch.sync_publications([record()], self.site, {}, STAMP)
        self.assertNotIn("role", updated["papers"][0])

    def test_unverified_candidate_is_absent_from_all_public_output(self):
        candidate = record("Unreleased manuscript title")
        with patch.object(watch, "public_record", return_value=(None, 0)):
            updated, scan = watch.sync_publications([candidate], self.site, {}, STAMP)
        self.assertEqual(1, scan["unverified_count"])
        self.assertEqual([], updated["papers"])
        self.assertNotIn(candidate["title"], json.dumps([updated, scan]))

    def test_source_failure_is_reported_without_publishing_a_guess(self):
        with patch.object(watch, "public_record", return_value=(None, 1)):
            updated, scan = watch.sync_publications([record()], self.site, {}, STAMP)
        self.assertEqual(self.site, updated)
        self.assertEqual("partial", scan["status"])
        self.assertEqual(1, scan["source_errors"])

    def preprint_site(self):
        site = deepcopy(self.site)
        site["papers"] = [{"id": "existing", "title": TITLE, "zh_title": "原有中文标题",
                           "status": "preprint", "year": 2025, "venue": "arXiv", "role": "cofirst",
                           "authors": "Hailong Qu*, Another Author*", "note": {"en": "User-written contribution"},
                           "field": "electrical", "figures": [{"file": "keep-model.webp"}],
                           "links": [["arXiv", "https://arxiv.org/abs/2501.12345"]]}]
        return site

    def test_journal_version_updates_one_entry_and_preserves_manual_content(self):
        site = self.preprint_site()
        with patch.object(watch, "public_record", return_value=(self.metadata, 0)):
            updated, scan = watch.sync_publications([record()], site, {}, STAMP)
        self.assertEqual(1, len(updated["papers"]))
        self.assertEqual([], scan["added"])
        self.assertEqual(["existing"], scan["updated"])
        paper = updated["papers"][0]
        self.assertEqual("published", paper["status"])
        for key in ("id", "title", "zh_title", "authors", "role", "note", "figures", "field"):
            self.assertEqual(site["papers"][0][key], paper[key])
        self.assertEqual(2, len(paper["links"]))

    def test_duplicate_scholar_versions_do_not_create_duplicate_publications(self):
        with patch.object(watch, "public_record", return_value=(self.metadata, 0)):
            updated, scan = watch.sync_publications([record(), record(work_id="fixture:other")], self.site, {}, STAMP)
        self.assertEqual(1, len(updated["papers"]))
        self.assertEqual(1, len(scan["added"]))

    def test_profile_omission_does_not_delete_existing_papers(self):
        site = self.preprint_site()
        updated, scan = watch.sync_publications([], site, {}, STAMP)
        self.assertEqual(site, updated)
        self.assertEqual([], scan["added"])

    def test_arxiv_identity_and_full_authorship_are_required(self):
        html = f'''<meta name="citation_title" content="{TITLE}">
          <meta name="citation_author" content="Hailong Qu">
          <meta name="citation_arxiv_id" content="2501.12345v2">
          <meta name="citation_date" content="2025/01/02">'''
        meta = watch.arxiv_record(html, "2501.12345", TITLE, PERSON)
        self.assertEqual("preprint", meta["status"])
        self.assertIsNone(watch.arxiv_record(html, "2501.99999", TITLE, PERSON))
        self.assertIsNone(watch.arxiv_record(html.replace("Hailong Qu", "Haifeng Qu"), "2501.12345", TITLE, PERSON))


if __name__ == "__main__":
    unittest.main()
