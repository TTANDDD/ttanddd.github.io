"""Check daily deduplication and preservation of verified citation data offline."""

from contextlib import redirect_stdout
from datetime import datetime, timezone
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError


SPEC = importlib.util.spec_from_file_location(
    "scholar", Path(__file__).resolve().parents[1] / "scripts/update_scholar.py")
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
                     "papers": [{"id": "public", "title": "Public paper"}]}
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
                    "citations": 55, "h_index": 3, "i10_index": 1, "papers": {}}
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
