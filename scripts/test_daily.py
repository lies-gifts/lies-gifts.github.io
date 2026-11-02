"""Offline checks for publication integrity, provenance and parsing."""
import argparse
import copy
import json
from pathlib import Path
import tempfile
import unittest
from daily import canonical, deduplicate, parse_source, parse_time, prepare, read, write


def story(key="one"):
    return {"id": key, "event_key": key, "category": "研究", "title": key, "summary": "Summary", "impact": "Usefulness",
            "source_name": "Original", "source_url": "https://example.org/" + key, "published_at": "2026-11-01T12:00:00Z",
            "tags": ["论文"], "verification": "研究预印本", "evidence_note": "Authors' preprint, not independently replicated",
            "editorial_reviewed": True, "selection_reason": "Relevant methods", "provenance": []}


def edition(items):
    return {"schema_version": 2, "date": "2026-11-02", "generated_at": "2026-11-02T08:00:00+08:00",
            "window_start": "2026-11-01T08:00:00+08:00", "window_end": "2026-11-02T08:00:00+08:00",
            "title": "Example", "summary": "Example", "editorial_reviewed": True, "items": items}


class DailyTests(unittest.TestCase):
    def test_canonical_dates_and_arxiv_identity(self):
        self.assertEqual(canonical("https://example.org/a/?utm_source=x#here"), "https://example.org/a")
        self.assertEqual(canonical("https://arxiv.org/pdf/2610.12345v2.pdf"), "https://arxiv.org/abs/2610.12345")
        self.assertIsNone(parse_time("2026-11-01T12:00:00"))
        self.assertIsNotNone(parse_time("Sun, 01 Nov 2026 12:00:00 GMT"))

    def test_rss_atom_and_release_dates(self):
        rows = parse_source({"format":"rss"}, b"<rss><channel><item><title>Paper</title><link>https://example.org/p</link><pubDate>Sun, 01 Nov 2026 12:00:00 GMT</pubDate></item></channel></rss>")
        self.assertEqual(len(rows), 1)
        atom = b'<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>Paper</title><link href="https://example.org/a"/><updated>2026-11-01T12:00:00Z</updated></entry></feed>'
        rows = parse_source({"format":"atom"}, atom)
        self.assertIsNone(rows[0]["published_at"])
        self.assertEqual(rows[0]["updated_at"], "2026-11-01T12:00:00Z")
        releases = [{"html_url":"https://github.com/x/y/releases/tag/v2", "tag_name":"v2", "published_at":"2026-11-01T12:00:00Z", "prerelease":True}]
        item = parse_source({"format":"github_releases", "repo":"x/y"}, json.dumps(releases).encode())[0]
        self.assertEqual(item["event_key"], "release:x/y:v2")
        self.assertTrue(item["prerelease"])

    def test_hf_modification_is_not_release(self):
        item = parse_source({"format":"hf_models"}, b'[{"id":"org/model","lastModified":"2026-11-01T00:00:00Z"}]')[0]
        self.assertIsNone(item["published_at"])
        self.assertEqual(item["updated_at"], "2026-11-01T00:00:00Z")

    def test_duplicate_reporting_and_distinct_releases(self):
        first = story()
        second = copy.deepcopy(first)
        second["source_url"] += "?utm_campaign=news"
        second["provenance"] = [{"name":"Second", "url":"https://example.org/report"}]
        result = deduplicate([first, second, story("two")], [story()])
        self.assertEqual(len(result), 2)
        self.assertTrue(result[0]["already_published"])
        self.assertEqual(len(result[0]["provenance"]), 1)

    def test_lossless_merge_and_guarded_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            old = edition([story()])
            write(root / "data/2026-11-02.json", old)
            original = (root / "data/2026-11-02.json").read_bytes()
            write(root / "data/index.json", {"editions":[{"date":"2026-11-02","title":"Example","count":1}], "sources":[]})
            write(root / "config/sources.json", {"sources":[]})
            incoming = root / "incoming.json"
            write(incoming, edition([story("two")]))
            args = argparse.Namespace(root=root, edition=incoming, out=root/"stage")
            prepare(args)
            merged = read(root / "stage/data/2026-11-02.json")
            self.assertEqual([x["id"] for x in merged["items"]], ["one", "two"])
            self.assertEqual((root / "stage" / merged["previous_revisions"][0]).read_bytes(), original)
            changed = story()
            changed["summary"] = "Replaced without revision intent"
            write(incoming, edition([changed]))
            with self.assertRaisesRegex(AssertionError, "explicit revision"):
                prepare(args)
            unreviewed = story("three")
            unreviewed["editorial_reviewed"] = False
            write(incoming, edition([unreviewed]))
            with self.assertRaisesRegex(AssertionError, "Unreviewed"):
                prepare(args)


if __name__ == "__main__":
    unittest.main()
