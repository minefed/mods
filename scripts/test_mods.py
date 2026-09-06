"""Safety and integrity checks for baseline preparation; no network or server use."""

import copy
import io
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import mods


class InventoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="minefed-mods-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()

    def entry(self, name="one.jar", mod_id="one", included=True, policy="allowed"):
        path = self.root / ".cache" / "server-mods" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(path, "w") as jar:
            if mod_id is not None:
                jar.writestr("fabric.mod.json", json.dumps({"id": mod_id, "version": "1.0", "environment": "*"}))
            else:
                jar.writestr("plugin.yml", "name: TCPShield\nversion: 2.8.1\n")
            jar.writestr("LICENSE", "A retained author license notice\n")
        digest, size = mods.file_digest(path)
        return {"fileName": name, "sha256": digest, "size": size, "modId": mod_id,
                "version": "1.0" if mod_id else None, "environment": "*" if mod_id else None,
                "management": "binary", "source": None,
                "artifact": {"path": path.relative_to(self.root).as_posix(), "redistribution": policy,
                             "url": "https://example.com/one.jar"},
                "included": included, "exclusionReason": None if included else "Inventory only",
                "license": "MIT", "licenseUrl": "https://example.com/LICENSE", "notes": "Test fixture"}

    def manifest(self, *entries):
        value = {"schemaVersion": 1, "minecraftVersion": "1.20.4", "loader": "fabric", "entries": list(entries)}
        path = self.root / "inventory" / "mods.lock.json"
        path.parent.mkdir(exist_ok=True)
        path.write_text(json.dumps(value), encoding="utf-8")
        return mods.load_manifest(self.root)

    def test_verify_covers_excluded_artifacts_and_detects_mutation(self):
        active, excluded = self.entry(), self.entry("plugin.jar", None, included=False)
        manifest = self.manifest(active, excluded)
        self.assertEqual(mods.verify(self.root, manifest), 2)
        artifact = self.root / excluded["artifact"]["path"]
        artifact.write_bytes(b"changed")
        with self.assertRaisesRegex(mods.ModError, "SHA-256 mismatch"):
            mods.verify(self.root, manifest)
        self.assertEqual(artifact.read_bytes(), b"changed")

    def test_fabric_metadata_must_match_even_when_hash_is_correct(self):
        entry = self.entry()
        entry["version"] = "2.0"
        with self.assertRaisesRegex(mods.ModError, "id/version/environment mismatch"):
            mods.verify(self.root, self.manifest(entry))

    def test_manifest_requires_hash_and_rejects_duplicate_filenames(self):
        entry = self.entry()
        missing = copy.deepcopy(entry)
        del missing["sha256"]
        with self.assertRaisesRegex(mods.ModError, "SHA-256"):
            self.manifest(missing)
        with self.assertRaisesRegex(mods.ModError, "Duplicate filename"):
            self.manifest(entry, entry)

    def test_stage_rejects_duplicate_ids_and_does_not_create_output(self):
        manifest = self.manifest(self.entry(), self.entry("duplicate.jar", "one"))
        with self.assertRaisesRegex(mods.ModError, "Duplicate included modId"):
            mods.stage(self.root, manifest)
        self.assertFalse((self.root / "build").exists())

    def test_stage_is_curated_idempotent_and_preserves_modified_output(self):
        active, excluded = self.entry(), self.entry("old.jar", included=False)
        manifest = self.manifest(active, excluded)
        self.assertEqual(mods.stage(self.root, manifest), 1)
        destination = self.root / "build" / "staged-mods"
        self.assertEqual([path.name for path in destination.iterdir()], ["one.jar"])
        self.assertEqual(mods.stage(self.root, manifest), 1)
        (destination / "one.jar").write_bytes(b"local output edit")
        with self.assertRaisesRegex(mods.ModError, "SHA-256 mismatch"):
            mods.stage(self.root, manifest)
        self.assertEqual((destination / "one.jar").read_bytes(), b"local output edit")

    def test_stage_refuses_unexpected_files(self):
        manifest = self.manifest(self.entry())
        destination = self.root / "build" / "staged-mods"
        destination.mkdir(parents=True)
        (destination / "unrelated.txt").write_text("keep")
        with self.assertRaisesRegex(mods.ModError, "Unexpected stage content"):
            mods.stage(self.root, manifest)
        self.assertEqual((destination / "unrelated.txt").read_text(), "keep")

    def test_paths_cannot_escape_or_target_non_build_outputs(self):
        manifest = self.manifest(self.entry())
        for value in ("../outside", "build/../../outside", "C:/outside", "build\\..\\outside", "vendor/jars", "build", "build/CON"):
            with self.subTest(value=value), self.assertRaises(mods.ModError):
                mods.stage(self.root, manifest, value)
        manifest["entries"][0]["artifact"]["path"] = "../one.jar"
        with self.assertRaises(mods.ModError):
            mods.verify(self.root, manifest)

    def test_symlinked_output_parent_is_rejected(self):
        actual = self.root / "actual"
        actual.mkdir()
        try:
            (self.root / "build").symlink_to(actual, target_is_directory=True)
        except OSError:
            self.skipTest("Creating symlinks is unavailable on this host")
        with self.assertRaisesRegex(mods.ModError, "Linked paths"):
            mods.stage(self.root, self.manifest(self.entry()))
        self.assertEqual(list(actual.iterdir()), [])

    def test_pack_requires_private_for_local_only_and_keeps_lock_and_notices(self):
        entry = self.entry(policy="local-only")
        manifest = self.manifest(entry, self.entry("excluded.jar", included=False))
        with self.assertRaisesRegex(mods.ModError, "--private"):
            mods.pack(self.root, manifest)
        self.assertFalse((self.root / "build").exists())
        self.assertEqual(mods.pack(self.root, manifest, private=True), 1)
        target = self.root / "build" / "minefed-baseline.zip"
        with zipfile.ZipFile(target) as archive:
            self.assertIn("licenses/jars/one.jar/LICENSE", archive.namelist())
            self.assertEqual(archive.read("mods/one.jar"), (self.root / entry["artifact"]["path"]).read_bytes())
            self.assertNotIn("mods/excluded.jar", archive.namelist())
            self.assertEqual(json.loads(archive.read("inventory/mods.lock.json")), manifest)
            self.assertTrue(json.loads(archive.read("PACK-INFO.json"))["private"])
        original_hash = mods.file_digest(target)
        with self.assertRaisesRegex(mods.ModError, "already exists"):
            mods.pack(self.root, manifest, private=True)
        self.assertEqual(mods.file_digest(target), original_hash)

    def test_modpack_only_permission_can_be_used_by_pack(self):
        manifest = self.manifest(self.entry(policy="modpack-only"))
        self.assertEqual(mods.pack(self.root, manifest), 1)

    def test_pack_exports_legal_notices_without_copying_similarly_named_assets(self):
        entry = self.entry()
        artifact = self.root / entry["artifact"]["path"]
        legal = ("LICENSE_mcwdoors", "LICENSE.md_oritech",
                 "LICENSE_extension 'base' property 'archivesName'", "COPYING.LESSER",
                 "META-INF/NOTICE.txt", "org/example/publicsuffix/NOTICE")
        payloads = ("assets/yuushya/models/button_sign/notice.json",
                    "assets/yuushya/textures/button_sign/notice.png",
                    "data/example/notice.txt", "assets/example/LICENSE",
                    "NOTICE.json", "NOTICE.png", "NOTICE.svg", "NOTICE.class",
                    "org/example/NoticeManager.class")
        with zipfile.ZipFile(artifact, "a") as jar:
            for name in legal:
                jar.writestr(name, "Legal author notice")
            for name in payloads:
                jar.writestr(name, "Mod payload")
        entry["sha256"], entry["size"] = mods.file_digest(artifact)
        mods.pack(self.root, self.manifest(entry))
        with zipfile.ZipFile(self.root / "build" / "minefed-baseline.zip") as archive:
            exported = set(archive.namelist())
            for name in legal:
                self.assertIn(f"licenses/jars/one.jar/{name}", exported)
            for name in payloads:
                self.assertNotIn(f"licenses/jars/one.jar/{name}", exported)
            # The original mod is retained byte for byte; only extra notice
            # exports are filtered, so no game resources are removed from it.
            self.assertEqual(archive.read("mods/one.jar"), artifact.read_bytes())

    def test_hydrate_installs_verified_bytes_and_never_overwrites(self):
        entry = self.entry()
        manifest = self.manifest(entry)
        artifact = self.root / entry["artifact"]["path"]
        content = artifact.read_bytes()
        artifact.unlink()
        with patch.object(mods, "download", return_value=io.BytesIO(content)) as fetch:
            self.assertEqual(mods.hydrate(self.root, manifest), 1)
            fetch.assert_called_once()
        self.assertEqual(artifact.read_bytes(), content)
        with patch.object(mods, "download") as fetch:
            self.assertEqual(mods.hydrate(self.root, manifest), 0)
            fetch.assert_not_called()
        artifact.write_bytes(b"local edit")
        with patch.object(mods, "download") as fetch, self.assertRaisesRegex(mods.ModError, "SHA-256 mismatch"):
            mods.hydrate(self.root, manifest)
        fetch.assert_not_called()
        self.assertEqual(artifact.read_bytes(), b"local edit")

    def test_hydrate_rejects_corruption_and_removes_only_its_temporary_file(self):
        entry = self.entry()
        manifest = self.manifest(entry)
        artifact = self.root / entry["artifact"]["path"]
        artifact.unlink()
        for content in (b"corrupted", b"x" * (entry["size"] + 1)):
            with patch.object(mods, "download", return_value=io.BytesIO(content)), self.assertRaises(mods.ModError):
                mods.hydrate(self.root, manifest)
            self.assertFalse(artifact.exists())
            self.assertEqual(list(artifact.parent.glob("*.part")), [])

    def test_hydrate_restores_known_urls_then_reports_manual_missing_files(self):
        known, manual = self.entry(), self.entry("custom.jar", "custom")
        manifest = self.manifest(known, manual)
        manifest["entries"][1]["artifact"]["url"] = None
        known_path = self.root / known["artifact"]["path"]
        manual_path = self.root / manual["artifact"]["path"]
        content = known_path.read_bytes()
        known_path.unlink()
        manual_path.unlink()
        with patch.object(mods, "download", return_value=io.BytesIO(content)) as fetch:
            with self.assertRaisesRegex(mods.ModError, "Restored 1.*manual-only") as error:
                mods.hydrate(self.root, manifest)
            fetch.assert_called_once()
        self.assertIn("custom.jar", str(error.exception))
        self.assertEqual(known_path.read_bytes(), content)
        self.assertFalse(manual_path.exists())

    def test_hydrate_requires_reviewed_url_and_allowed_artifact_directory(self):
        entry = self.entry()
        manifest = self.manifest(entry)
        (self.root / entry["artifact"]["path"]).unlink()
        for url in (None, "http://example.com/file.jar", "file:///tmp/file.jar"):
            manifest["entries"][0]["artifact"]["url"] = url
            with self.subTest(url=url), self.assertRaises(mods.ModError):
                mods.hydrate(self.root, manifest)
        manifest["entries"][0]["artifact"]["url"] = "https://example.com/file.jar"
        manifest["entries"][0]["artifact"]["path"] = "scripts/one.jar"
        with self.assertRaisesRegex(mods.ModError, "artifact directories"):
            mods.hydrate(self.root, manifest)

    def test_atomic_publication_refuses_a_file_created_concurrently(self):
        temporary, destination = self.root / "temp", self.root / "dest"
        temporary.write_bytes(b"new")
        destination.write_bytes(b"existing")
        with self.assertRaisesRegex(mods.ModError, "already exists"):
            mods.publish_new(temporary, destination)
        self.assertEqual(destination.read_bytes(), b"existing")

    @unittest.skipUnless(shutil.which("git"), "Git is needed for source verification")
    def test_source_verification_checks_gitlink_url_head_and_local_changes(self):
        def run(folder, *args):
            return subprocess.run(["git", "-C", str(folder), *args], check=True, capture_output=True, text=True).stdout.strip()

        run(self.root, "init")
        source = self.root / "source"
        source.mkdir()
        run(source, "init")
        run(source, "config", "user.email", "test@example.invalid")
        run(source, "config", "user.name", "Test")
        (source / "code.txt").write_text("baseline")
        run(source, "add", "code.txt")
        run(source, "commit", "-m", "chore(test): seed source")
        commit = run(source, "rev-parse", "HEAD")
        (self.root / ".gitmodules").write_text('[submodule "source"]\n\tpath = source\n\turl = https://github.com/minefed/source.git\n')
        run(self.root, "update-index", "--add", "--cacheinfo", f"160000,{commit},source")
        entry = self.entry()
        entry["management"] = "submodule"
        entry["source"] = {"path": "source", "url": "https://github.com/minefed/source.git", "upstream": "https://example.com/source",
                           "ref": "refs/heads/main", "commit": commit}
        manifest = self.manifest(entry)
        self.assertEqual(mods.verify(self.root, manifest, sources=True), 1)
        extra_manifest = copy.deepcopy(manifest)
        extra_manifest["entries"][0]["management"] = "binary"
        extra_manifest["entries"][0]["source"] = None
        extra_manifest["sourceRepositories"] = [entry["source"]]
        self.assertEqual(mods.verify(self.root, extra_manifest, sources=True), 1)
        with self.assertRaisesRegex(mods.ModError, "Unrecorded"):
            mods.check_sources(self.root, [])
        entry["source"]["commit"] = "0" * 40
        with self.assertRaisesRegex(mods.ModError, "gitlink differs"):
            mods.check_sources(self.root, [entry])
        entry["source"]["commit"] = commit
        (source / "code.txt").write_text("local work")
        with self.assertRaisesRegex(mods.ModError, "local changes"):
            mods.check_sources(self.root, [entry])
        (source / "code.txt").write_text("baseline")
        entry["source"]["url"] = "https://example.com/wrong"
        with self.assertRaisesRegex(mods.ModError, "URL/path differs"):
            mods.check_sources(self.root, [entry])


if __name__ == "__main__":
    unittest.main()
