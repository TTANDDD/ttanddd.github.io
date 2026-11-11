"""Check daily deduplication and preservation of verified citation data offline."""

from contextlib import redirect_stdout
from datetime import datetime, timezone
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError


SPEC = importlib.util.spec_from_file_location(
    "scholar", Path(__file__).resolve().parents[1] / "scripts/update_scholar.py")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
SCHOLAR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SCHOLAR)
FLAGS = ["--skip-if-current", "--defer-if-blocked"]
PROFILE = "https://scholar.google.com/citations?user=fixture"
HTML = b'''<div id="gsc_prf_in">Test Researcher</div>
<table id="gsc_rsb_st"><tr><td>Citations</td><td>56</td></tr>
<tr><td>h-index</td><td>3</td></tr><tr><td>i10-index</td><td>1</td></tr></table>
<table><tbody id="gsc_a_b"><tr><td><a class="gsc_a_at"
href="/citations?citation_for_view=fixture:paper">Public paper</a></td>
<td><a class="gsc_a_ac" href="/scholar?cites=123">6</a></td></tr></tbody></table>'''


class Clock(datetime):
    value = datetime(2026, 11, 11, 1, 0, tzinfo=timezone.utc)

    @classmethod
    def now(cls, tz=None):
        return cls.value.astimezone(tz)


class RefreshTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.folder = Path(self.temporary.name)
        self.path = self.folder / "scholar.json"
        self.output = self.folder / "output"
        self.summary = self.folder / "summary"
        self.log = io.StringIO()
        self.site = {"person": {"name": "Test Researcher", "scholar": PROFILE},
                     "fields": [], "papers": [{"id": "public", "title": "Public paper", "status": "published"}]}
        (self.folder / "site.json").write_text(json.dumps(self.site), encoding="utf-8")
        Clock.value = datetime(2026, 11, 11, 1, 0, tzinfo=timezone.utc)
        self.seed("2026-11-10T01:00:00Z")
        for context in [patch.object(SCHOLAR, "DATA", self.folder),
                        patch.object(SCHOLAR, "datetime", Clock),
                        patch.dict("os.environ", {"GITHUB_OUTPUT": str(self.output),
                            "GITHUB_STEP_SUMMARY": str(self.summary), "GITHUB_ACTIONS": "true"}),
                        redirect_stdout(self.log)]:
            context.__enter__()
            self.addCleanup(context.__exit__, None, None, None)
        self.network = patch.object(SCHOLAR, "urlopen").start()
        self.addCleanup(patch.stopall)
        response = MagicMock()
        response.geturl.return_value = "https://scholar.google.com/citations"
        response.read.return_value = HTML
        self.network.return_value.__enter__.return_value = response

    def seed(self, stamp, **changes):
        snapshot = {"profile": PROFILE, "checked_at": stamp,
                    "citations": 55, "h_index": 3, "i10_index": 1, "papers": {},
                    "publication_scan": {"version": 1, "checked_at": stamp}}
        snapshot.update(changes)
        self.path.write_text(json.dumps(snapshot, indent=2) + "\n", encoding="utf-8")
        self.before = self.path.read_bytes()

    def refuse(self, code=403):
        self.network.side_effect = HTTPError(SCHOLAR.URL, code, "refused", None, None)

    def test_current_snapshot_never_contacts_scholar_or_rewrites_data(self):
        self.seed("2026-11-11T00:30:00Z")
        SCHOLAR.main(FLAGS)
        self.network.assert_not_called()
        self.assertEqual(self.before, self.path.read_bytes())
        self.assertEqual("status=current\n", self.output.read_text())

    def test_utc_midnight_does_not_repeat_same_beijing_day(self):
        self.seed("2026-11-10T23:55:00Z")
        SCHOLAR.main(FLAGS)
        self.network.assert_not_called()

    def test_counts_only_snapshot_does_not_skip_new_publication_scan(self):
        self.seed("2026-11-11T00:30:00Z", publication_scan={})
        SCHOLAR.main(FLAGS)
        self.network.assert_called_once()
        scan = json.loads(self.path.read_text())["publication_scan"]
        self.assertEqual(1, scan["observed_count"])
        self.assertEqual("complete", scan["status"])

    def test_publication_inventory_follows_scholar_pagination(self):
        first = HTML + b'<button id="gsc_bpf_more"></button>'
        second = HTML.replace(b'fixture:paper', b'fixture:second') + b'<button id="gsc_bpf_more" disabled></button>'
        responses = []
        for content in (first, second):
            response = MagicMock()
            response.__enter__.return_value.geturl.return_value = SCHOLAR.URL
            response.__enter__.return_value.read.return_value = content
            responses.append(response)
        self.network.side_effect = responses
        with patch.object(SCHOLAR.time, "sleep"):
            root = SCHOLAR.read_profile("fixture")
        self.assertEqual(2, len(SCHOLAR.inventory(root, self.site)))
        self.assertIn("cstart=100", self.network.call_args_list[1].args[0].full_url)

    def test_duplicate_versions_keep_one_real_count_without_summing(self):
        html = HTML.decode().replace('</tbody>', '''<tr><td><a class="gsc_a_at"
          href="/citations?citation_for_view=fixture:journal">Public paper</a></td>
          <td><a class="gsc_a_ac" href="/scholar?cites=456">4</a></td></tr></tbody>''')
        result = SCHOLAR.extract(html, self.site, {}, "2026-11-11T01:00:00Z")
        self.assertEqual(6, result["papers"]["public"]["count"])
        self.assertEqual("123", result["papers"]["public"]["cluster"])

    def test_verified_discovery_is_saved_with_its_citations(self):
        title = "A new public medical imaging paper"
        html = HTML.decode().replace('</tbody>', f'''<tr><td><a class="gsc_a_at"
          href="/citations?citation_for_view=fixture:new">{title}</a></td>
          <td><a class="gsc_a_ac" href="/scholar?cites=789">1</a></td></tr></tbody>''')
        self.network.return_value.__enter__.return_value.read.return_value = html.encode()
        metadata = {"title": title, "authors": ["Test Researcher"], "year": 2026,
                    "status": "published", "venue": "Example Medical Journal", "citation": "12, 34",
                    "doi": "10.1234/medical", "url": "https://doi.org/10.1234/medical", "source": "Crossref"}
        with patch("publication_watch.public_record", return_value=(metadata, 0)):
            SCHOLAR.main(FLAGS)
        site = json.loads((self.folder / "site.json").read_text(encoding="utf-8"))
        snapshot = json.loads(self.path.read_text())
        self.assertEqual(2, len(site["papers"]))
        added = snapshot["publication_scan"]["added"]
        self.assertEqual(1, len(added))
        self.assertEqual(1, snapshot["papers"][added[0]]["count"])

    def test_unverified_discovery_does_not_leak_into_public_files(self):
        secret_title = "A manuscript without a public article"
        html = HTML.decode().replace('</tbody>', f'''<tr><td><a class="gsc_a_at"
          href="/citations?citation_for_view=fixture:unreleased">{secret_title}</a></td>
          <td><a class="gsc_a_ac"></a></td></tr></tbody>''')
        self.network.return_value.__enter__.return_value.read.return_value = html.encode()
        with patch("publication_watch.public_record", return_value=(None, 0)):
            SCHOLAR.main(FLAGS)
        for path in (self.path, self.folder / "site.json", self.summary):
            self.assertNotIn(secret_title, path.read_text(encoding="utf-8"))
        self.assertNotIn(secret_title, self.log.getvalue())
        self.assertEqual(1, json.loads(self.path.read_text())["publication_scan"]["unverified_count"])

    def test_beijing_midnight_allows_new_verified_update(self):
        self.seed("2026-11-10T15:59:00Z")
        Clock.value = datetime(2026, 11, 10, 16, 1, tzinfo=timezone.utc)
        SCHOLAR.main(FLAGS)
        self.network.assert_called_once()
        fresh = json.loads(self.path.read_text())
        self.assertEqual(56, fresh["citations"])
        self.assertEqual(6, fresh["papers"]["public"]["count"])
        self.assertEqual("2026-11-10T16:01:00Z", fresh["checked_at"])
        self.assertEqual("status=refreshed\n", self.output.read_text())

    def test_refused_cloud_request_preserves_every_byte_and_warns(self):
        for code in (403, 429):
            with self.subTest(code=code):
                self.refuse(code)
                SCHOLAR.main(FLAGS)
                self.assertEqual(self.before, self.path.read_bytes())
                self.assertIn(f"HTTP {code}", self.summary.read_text())
        self.assertIn("status=deferred", self.output.read_text())
        self.assertIn("::warning", self.log.getvalue())
        self.assertNotIn("status=refreshed", self.output.read_text())

    def test_local_refusal_still_fails_for_scheduler_retry(self):
        self.refuse()
        with self.assertRaises(HTTPError):
            SCHOLAR.main([])
        self.assertEqual(self.before, self.path.read_bytes())
        self.assertFalse(self.output.exists())

    def test_other_http_errors_are_not_hidden(self):
        self.refuse(500)
        with self.assertRaises(HTTPError):
            SCHOLAR.main(FLAGS)
        self.assertEqual(self.before, self.path.read_bytes())

    def test_bad_profile_response_is_not_hidden(self):
        self.network.return_value.__enter__.return_value.read.return_value = b"<html>Sign in</html>"
        with self.assertRaises(ValueError):
            SCHOLAR.main(FLAGS)
        self.assertEqual(self.before, self.path.read_bytes())
        self.assertFalse(self.output.exists())

    def test_unverified_or_future_snapshot_cannot_be_used_as_fallback(self):
        for changes in ({"profile": "another-author"}, {"citations": None},
                        {"checked_at": "invalid"}, {"checked_at": "2099-01-01T00:00:00Z"}):
            with self.subTest(changes=changes):
                self.seed("2026-11-11T00:30:00Z", **changes)
                self.refuse()
                with self.assertRaises(HTTPError):
                    SCHOLAR.main(FLAGS)
                self.assertEqual(self.before, self.path.read_bytes())


if __name__ == "__main__":
    unittest.main()
