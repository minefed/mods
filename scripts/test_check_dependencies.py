"""Offline fixtures for dependency policy checks; no network or JAR downloads."""
from copy import deepcopy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import URLError
from urllib.parse import parse_qs, urlparse

import check_dependencies as checker
import mods


def version(identity="new", **fields):
    return {"id": identity, "project_id": "P123", "version_number": "2", "version_type": "release",
            "date_published": "2026-09-01T00:00:00Z", "status": "listed", "game_versions": ["1.20.4"],
            "loaders": ["fabric"], "dependencies": [{"dependency_type": "required", "project_id": "Other"}],
            "files": [{"filename": "library.jar", "url": "https://cdn.modrinth.com/library.jar", "primary": True,
                       "hashes": {"sha512": "b" * 128}}], **fields}


def fixtures():
    policy = {"schemaVersion": 1, "minecraftVersion": "1.20.4", "loader": "fabric", "channel": "release",
              "entries": [{"modId": "library", "projectId": "P123"}]}
    manifest = {"schemaVersion": 1, "minecraftVersion": "1.20.4", "loader": "fabric", "entries": [
        {"modId": "library", "version": "1", "fileName": "library.jar", "sha256": "a" * 64,
         "size": 3, "management": "binary", "included": True,
         "artifact": {"path": "artifacts/local/library.jar", "redistribution": "allowed", "sha512": "a" * 128,
                      "publishedRelease": {"provider": "modrinth", "projectId": "P123", "versionId": "old"}}}]}
    return policy, manifest


class ReleaseSelectionTests(unittest.TestCase):
    def latest(self, versions):
        return checker.latest_release(versions, "P123", "1.20.4", "fabric")

    def test_filters_runtime_project_status_and_stability_explicitly(self):
        rejected = [{"game_versions": ["1.21"]}, {"loaders": ["forge"]}, {"version_type": "beta"},
                    {"version_type": "alpha"}, {"project_id": "Wrong"}, {"status": "unlisted"},
                    {"status": "draft"}, {"game_versions": "1.20.4"}, {"loaders": "fabric"}]
        versions = [version(str(index), date_published="2026-09-02T00:00:00Z", **fields)
                    for index, fields in enumerate(rejected)]
        accepted = version("stable")
        accepted.pop("status")  # Older API responses may omit this field.
        self.assertEqual("stable", self.latest(versions + [accepted])["versionId"])

    def test_sorts_actual_instants_with_deterministic_ties_not_version_numbers(self):
        older = version("z", version_number="999", date_published="2026-09-01T09:30:00+09:00")
        newer = version("b", version_number="1", date_published="2026-09-01T01:00:00Z")
        tied = version("a", date_published="2026-09-01T03:00:00+02:00")
        for candidates in ([older, newer, tied], [tied, newer, older]):
            self.assertEqual("b", self.latest(candidates)["versionId"])

    def test_unique_primary_or_single_jar_and_metadata_preserved(self):
        candidate = version()
        extra = {**candidate["files"][0], "filename": "sources.jar", "primary": False}
        candidate["files"].append(extra)
        latest = self.latest([candidate])
        self.assertEqual("library.jar", latest["fileName"])
        self.assertEqual(candidate["dependencies"], latest["dependencies"])
        self.assertEqual(candidate["files"][0]["hashes"], latest["hashes"])
        candidate["files"] = [extra, {"filename": "readme.txt", "primary": True}]
        self.assertEqual("sources.jar", self.latest([candidate])["fileName"])

    def test_ambiguous_missing_or_unverified_latest_jar_fails_without_older_fallback(self):
        base = version()
        invalid = [[], [base["files"][0], deepcopy(base["files"][0])],
                   [{**base["files"][0], "hashes": {}}], [{**base["files"][0], "url": "http://example.com/a.jar"}]]
        for files in invalid:
            with self.subTest(files=files), self.assertRaises(mods.ModError):
                self.latest([version("old", date_published="2025-01-01T00:00:00Z"), version(files=files)])

    def test_invalid_api_shapes_dates_duplicates_and_no_stable_fail(self):
        for candidates in ({}, [None], [], [version(version_type="beta")], [version(date_published="invalid")],
                           [version(date_published="2026-09-01T00:00:00")], [version(), version()]):
            with self.subTest(candidates=candidates), self.assertRaises(mods.ModError):
                self.latest(candidates)


class PolicyAndReportTests(unittest.TestCase):
    def test_invalid_policy_and_baseline_mapping(self):
        mutations = [lambda p, m: p.update(schemaVersion=2), lambda p, m: p.update(channel="beta"),
                     lambda p, m: p.update(loader="forge"), lambda p, m: p.update(entries=[]),
                     lambda p, m: p["entries"].append(dict(p["entries"][0])),
                     lambda p, m: p["entries"].append({"modId": "other", "projectId": "P123"}),
                     lambda p, m: p["entries"][0].update(projectId="../escape"),
                     lambda p, m: m["entries"].append(deepcopy(m["entries"][0])),
                     lambda p, m: m["entries"].clear(), lambda p, m: m.update(minecraftVersion="1.21"),
                     lambda p, m: m["entries"][0]["artifact"].update(publishedRelease=None),
                     lambda p, m: m["entries"][0]["artifact"].update(sha512="bad"),
                     lambda p, m: m["entries"][0]["artifact"]["publishedRelease"].update(projectId="Other")]
        for mutate in mutations:
            policy, manifest = fixtures()
            mutate(policy, manifest)
            with self.subTest(mutate=mutate), self.assertRaises(mods.ModError):
                checker.validate_policy(policy, manifest)

    def test_comparison_and_unknown_id_and_no_in_memory_mutation(self):
        policy, manifest = fixtures()
        original = deepcopy((policy, manifest))
        for candidate, status in [(version(), "update-available"), (version("old"), "artifact-changed"),
                                  (version("old", files=[{**version()["files"][0], "hashes": {"sha512": "A" * 128}}]), "current")]:
            with self.subTest(status=status), patch.object(checker, "fetch_versions", return_value=[candidate]):
                report = checker.check(policy, manifest, ["library", "library"])
                self.assertEqual(status, report["entries"][0]["status"])
                self.assertFalse(report["baselineChanged"])
                self.assertFalse(report["runtimeValidated"])
                self.assertEqual(original, (policy, manifest))
        with patch.object(checker, "fetch_versions") as fetch:
            with self.assertRaisesRegex(mods.ModError, "Unknown"):
                checker.check(policy, manifest, ["typo"])
            fetch.assert_not_called()

    def test_http_query_filters_timeout_and_errors(self):
        with patch.object(checker, "urlopen", return_value=io.BytesIO(json.dumps([version()]).encode())) as request:
            self.assertEqual("new", checker.fetch_versions("P123", "1.20.4", "fabric")[0]["id"])
            args, kwargs = request.call_args
            parsed = urlparse(args[0].full_url)
            self.assertEqual("api.modrinth.com", parsed.hostname)
            self.assertEqual("/v2/project/P123/version", parsed.path)
            query = parse_qs(parsed.query)
            self.assertEqual(["1.20.4"], json.loads(query["game_versions"][0]))
            self.assertEqual(["fabric"], json.loads(query["loaders"][0]))
            self.assertEqual(30, kwargs["timeout"])
        for content in (b"not json", b"{}"):
            with patch.object(checker, "urlopen", return_value=io.BytesIO(content)), self.assertRaises(mods.ModError):
                checker.fetch_versions("P123", "1.20.4", "fabric")
        with patch.object(checker, "urlopen", side_effect=URLError("offline")), self.assertRaises(mods.ModError):
            checker.fetch_versions("P123", "1.20.4", "fabric")

    def test_cli_writes_only_requested_report_and_failures_are_nonzero(self):
        policy, manifest = fixtures()
        with tempfile.TemporaryDirectory(prefix="minefed-update-test-") as directory:
            root = Path(directory)
            (root / "inventory").mkdir()
            lock = root / checker.DEFAULT_MANIFEST
            lock.write_text(json.dumps(manifest), encoding="utf-8")
            policy_path = root / checker.DEFAULT_POLICY
            policy_path.write_text(json.dumps(policy), encoding="utf-8")
            before = {path: path.read_bytes() for path in (lock, policy_path)}
            with patch.object(checker, "ROOT", root), patch.object(checker, "fetch_versions", return_value=[version()]), \
                    patch("sys.stdout", new_callable=io.StringIO), patch("sys.stderr", new_callable=io.StringIO):
                self.assertEqual(0, checker.main([]))
                self.assertFalse((root / "build").exists())
                self.assertEqual(0, checker.main(["--id", "library", "--output", "build/dependencies.json"]))
                output = root / "build/dependencies.json"
                self.assertEqual("update-available", json.loads(output.read_text())["entries"][0]["status"])
                self.assertEqual(1, checker.main(["--output", mods.DEFAULT_MANIFEST]))
                self.assertEqual(1, checker.main(["--id", "unknown"]))
                with patch.object(checker, "fetch_versions", side_effect=mods.ModError("offline")):
                    self.assertEqual(1, checker.main(["--output", "build/failed.json"]))
                    self.assertFalse((root / "build/failed.json").exists())
                with patch.object(checker, "fetch_versions", return_value=[version("old")]):
                    self.assertEqual(1, checker.main([]))
            self.assertEqual(before, {path: path.read_bytes() for path in before})
            self.assertEqual({lock, policy_path, output}, {path for path in root.rglob("*") if path.is_file()})


if __name__ == "__main__":
    unittest.main()
