import json
import tempfile
import unittest
from pathlib import Path

from valvi.sources import ConfigError, load_sources, parse_sources, summary


def source(**overrides):
    row = {
        "sourceId": "SOURCE-01",
        "siteId": "SITE-01",
        "folder": r"\\example.invalid\authorized-folder",
        "enabled": True,
        "pollSeconds": 30,
    }
    row.update(overrides)
    return row


def document(*rows):
    return {"readOnly": True, "sources": list(rows)}


class SourceConfigTests(unittest.TestCase):
    def test_multiple_sources(self):
        sources = parse_sources(document(
            source(), source(sourceId="SOURCE-02",
                             folder=r"C:\Example\Folder", enabled=False)
        ))
        self.assertEqual(summary(sources)["enabled"], 1)
        self.assertFalse(summary(sources)["network_checked"])

    def test_write_mode_rejected(self):
        with self.assertRaises(ConfigError):
            parse_sources({"readOnly": False, "sources": []})

    def test_duplicate_ids(self):
        with self.assertRaises(ConfigError):
            parse_sources(document(source(), source(sourceId="source-01",
                                                   folder=r"C:\Different")))

    def test_duplicate_folders(self):
        with self.assertRaises(ConfigError):
            parse_sources(document(source(), source(sourceId="SOURCE-02",
                       folder=r"\\EXAMPLE.INVALID\AUTHORIZED-FOLDER")))

    def test_bad_folders(self):
        for folder in (r"relative\path", r"\\example.invalid", r"C:\A\..\B",
                       r"C:\Wild*", "", r"\\?\C:\A"):
            with self.subTest(folder=folder), self.assertRaises(ConfigError):
                parse_sources(document(source(folder=folder)))

    def test_invalid_types(self):
        for changes in ({"enabled": "true"}, {"pollSeconds": True},
                        {"pollSeconds": 1}, {"pollSeconds": 3601},
                        {"sourceId": "../bad"}, {"extra": "unknown"}):
            with self.subTest(changes=changes), self.assertRaises(ConfigError):
                parse_sources(document(source(**changes)))

    def test_empty_sources(self):
        self.assertEqual(summary(parse_sources(document()))["sources"], 0)

    def test_private_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sources.json"
            path.write_text(json.dumps(document(source())), encoding="utf-8-sig")
            result = summary(load_sources(path))
            self.assertNotIn("example.invalid", json.dumps(result))
            path.write_text("{broken", encoding="utf-8")
            with self.assertRaises(ConfigError):
                load_sources(path)


if __name__ == "__main__":
    unittest.main()
