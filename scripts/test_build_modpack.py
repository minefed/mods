"""Offline integrity tests for mixed source/binary builds; no game or Gradle launch."""

import copy
from contextlib import ExitStack, redirect_stderr, redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import build_modpack as builder
import mods


class RepositoryRecipeTests(unittest.TestCase):
    def test_recipes_cover_all_68_included_inventory_mods_once(self):
        manifest, plan = builder.load_plan(Path(__file__).resolve().parents[1])
        expected = {entry["modId"] for entry in manifest["entries"] if entry["included"]}
        actual = [recipe["modId"] for recipe in plan["entries"]]
        self.assertEqual(len(expected), 68)
        self.assertEqual(len(actual), 68)
        self.assertEqual(set(actual), expected)
        self.assertEqual({recipe["mode"] for recipe in plan["entries"]}, {"source", "binary"})

    def test_version_ranges_cover_deployed_cross_version_and_exclusion_boundaries(self):
        accepted = ("~1.20.3-", ">=1.20.3- <1.20.5", "1.20.x", ["1.20.2", "1.20.4"], "1.20.4")
        rejected = ("~1.21", ">1.20.4", "<1.20.4", ">=1.20.5", ["1.20.2", "1.21"])
        for predicate in accepted:
            with self.subTest(predicate=predicate):
                self.assertTrue(builder.version_satisfies("1.20.4", predicate))
        for predicate in rejected:
            with self.subTest(predicate=predicate):
                self.assertFalse(builder.version_satisfies("1.20.4", predicate))


class MixedBuildTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="minefed-build-test-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.source = self.root / "alpha-source"
        self.source.mkdir()
        (self.source / ".gitignore").write_text("build/\n.gradle/\n", encoding="utf-8")
        (self.source / "Main.java").write_text("class Main {}\n", encoding="utf-8")
        (self.source / "LICENSE").write_text("Source author license\n", encoding="utf-8")
        # Real Git state makes mutation/receipt tests independent of fake hashes.
        self.real_run = subprocess.run
        self.git("init", "--quiet")
        self.git("add", ".")
        self.git("-c", "user.name=Minefed Test", "-c", "user.email=test@example.invalid",
                 "-c", "commit.gpgsign=false", "commit", "--quiet", "-m",
                 "test(fixture): initialize isolated source fixture")
        source_record = {"path": "alpha-source", "url": "https://example.invalid/alpha.git",
                         "upstream": "https://example.invalid/upstream.git", "ref": "main",
                         "commit": self.git("rev-parse", "HEAD")}
        self.source_entry = self.baseline("alpha-baseline.jar", "alpha", source=source_record)
        self.binary_entry = self.baseline("beta.jar", "beta")
        self.manifest = {"schemaVersion": 1, "minecraftVersion": "1.20.4", "loader": "fabric",
                         "entries": [self.source_entry, self.binary_entry]}
        self.recipe = {"sourcePath": "alpha-source", "modId": "alpha", "mode": "source",
                       "reason": "Fixture source supports Fabric 1.20.4", "java": 17,
                       "tasks": [":remapJar"], "args": [], "artifactGlobs": ["build/libs/*.jar"],
                       "expectedVersion": "2.0", "sourceWorkDir": "."}
        self.plan = {"schemaVersion": 1, "minecraftVersion": "1.20.4", "loader": "fabric",
                     "entries": [self.recipe, {"modId": "beta", "mode": "binary",
                                               "reason": "Reviewed binary dependency"}]}
        self.save_inputs()
        notices = self.root / "inventory" / "notices"
        notices.mkdir()
        (notices / "author.txt").write_text("Retained deployment notice\n", encoding="utf-8")
        self.contexts = ExitStack()
        self.addCleanup(self.contexts.close)
        self.contexts.enter_context(patch.object(builder, "java_home", return_value=self.root / "fake-jdk"))
        self.stdout = io.StringIO()
        self.stderr = io.StringIO()
        self.contexts.enter_context(redirect_stdout(self.stdout))
        self.contexts.enter_context(redirect_stderr(self.stderr))

    def git(self, *arguments):
        return self.real_run(["git", "-C", str(self.source), *arguments], check=True,
                             capture_output=True, text=True, encoding="utf-8").stdout.strip()

    def jar(self, path, identity, version="2.0", marker=b"newly built source bytes",
            minecraft="~1.20.4", java=">=17", environment="*", class_major=61):
        path.parent.mkdir(parents=True, exist_ok=True)
        metadata = {"schemaVersion": 1, "id": identity, "version": version,
                    "environment": environment, "license": "MIT",
                    "depends": {"minecraft": minecraft, "java": java, "fabricloader": ">=0.15.0"}}
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("fabric.mod.json", json.dumps(metadata))
            archive.writestr("LICENSE", "Built artifact author license\n")
            archive.writestr("assets/alpha/marker.bin", marker)
            archive.writestr("example/Main.class", b"\xca\xfe\xba\xbe\x00\x00" + class_major.to_bytes(2, "big"))
        return path

    def baseline(self, filename, identity, source=None):
        path = self.jar(self.root / "artifacts" / "local" / filename, identity,
                        version="1.0", marker=b"original deployment bytes")
        digest, size = mods.file_digest(path)
        return {"fileName": filename, "sha256": digest, "size": size, "modId": identity,
                "version": "1.0", "environment": "*", "included": True, "exclusionReason": None,
                "management": "submodule" if source else "binary", "source": source,
                "artifact": {"path": path.relative_to(self.root).as_posix(),
                             "redistribution": "local-only", "url": None},
                "license": "MIT", "licenseUrl": "https://example.invalid/LICENSE", "notes": "Fixture"}

    def save_inputs(self):
        builder.write_json(self.root / "inventory" / "mods.lock.json", self.manifest)
        builder.write_json(self.root / builder.RECIPES, self.plan)

    def prepare(self, run="test-run"):
        builder.prepare(self.root, run)

    def build(self, run="test-run", *, outputs=None, returncode=0, mutation=None):
        """Mock only the Gradle process; retain real Git, file hashing and packaging."""
        outputs = [{"filename": "alpha-built.jar"}] if outputs is None else outputs

        def invoke(command, *args, **kwargs):
            if command[0] != "fake-gradle":
                return self.real_run(command, *args, **kwargs)
            kwargs["stdout"].write("Fake Gradle completed fixture phase\n")
            if not returncode:
                for output in outputs:
                    options = dict(output)
                    filename = options.pop("filename")
                    self.jar(self.source / "build" / "libs" / filename, "alpha", **options)
            if mutation:
                mutation()
            return subprocess.CompletedProcess(command, returncode)

        with patch.object(builder, "wrapper_command", return_value=["fake-gradle"]), \
                patch.object(builder.subprocess, "run", side_effect=invoke) as process:
            builder.build_source(self.root, run, "alpha")
        return [call.args[0] for call in process.call_args_list if call.args[0][0] == "fake-gradle"]

    def receipt_path(self, run="test-run"):
        return builder.run_path(self.root, run) / "sources" / "alpha" / "result.json"

    def test_plan_rejects_missing_and_duplicate_recipes(self):
        self.plan["entries"].pop()
        self.save_inputs()
        with self.assertRaises(mods.ModError):
            builder.load_plan(self.root)
        self.plan["entries"].append(copy.deepcopy(self.recipe))
        self.save_inputs()
        with self.assertRaises(mods.ModError):
            builder.load_plan(self.root)

    def test_mod_id_cannot_escape_run_output_directory(self):
        self.source_entry["modId"] = "../escape"
        self.recipe["modId"] = "../escape"
        self.save_inputs()
        with self.assertRaises(mods.ModError):
            builder.load_plan(self.root)
        self.assertFalse((self.root / "build").exists())

    def test_binary_mutation_is_rejected_before_prepare_without_overwrite(self):
        artifact = self.root / self.binary_entry["artifact"]["path"]
        artifact.write_bytes(b"locally modified binary")
        with self.assertRaisesRegex(mods.ModError, "SHA-256"):
            self.prepare()
        self.assertEqual(artifact.read_bytes(), b"locally modified binary")
        self.assertFalse(builder.run_path(self.root, "test-run").exists())

    def test_binary_mutation_after_prepare_is_rejected_at_pack(self):
        self.prepare()
        self.build()
        (self.root / self.binary_entry["artifact"]["path"]).write_bytes(b"changed after prepare")
        with self.assertRaisesRegex(mods.ModError, "SHA-256"):
            builder.assemble(self.root, "test-run")

    def test_source_failure_never_falls_back_to_present_baseline(self):
        self.prepare()
        original = self.root / self.source_entry["artifact"]["path"]
        self.assertTrue(original.is_file())
        with self.assertRaisesRegex(mods.ModError, "Source build failed"):
            self.build(returncode=1)
        self.assertFalse(self.receipt_path().exists())
        with self.assertRaisesRegex(mods.ModError, "Missing successful source build"):
            builder.assemble(self.root, "test-run")
        self.assertFalse((self.root / "build" / "distributions").exists())

    def test_old_run_receipt_cannot_be_reused(self):
        self.prepare("old-run")
        self.build("old-run")
        self.prepare("new-run")
        target = self.receipt_path("new-run")
        target.parent.mkdir(parents=True)
        shutil.copyfile(self.receipt_path("old-run"), target)
        with self.assertRaisesRegex(mods.ModError, "Stale source build receipt"):
            builder.assemble(self.root, "new-run")

    def test_receipt_relabeling_cannot_collect_old_run_artifact(self):
        self.prepare("old-run")
        self.build("old-run")
        self.prepare("new-run")
        receipt = builder.read_json(self.receipt_path("old-run"))
        receipt["run"] = "new-run"
        builder.write_json(self.receipt_path("new-run"), receipt)
        with self.assertRaisesRegex(mods.ModError, "outside this run"):
            builder.assemble(self.root, "new-run")

    def test_multiple_runtime_jars_are_rejected(self):
        self.prepare()
        with self.assertRaisesRegex(mods.ModError, "exactly one runtime JAR"):
            self.build(outputs=[{"filename": "alpha-a.jar"}, {"filename": "alpha-b.jar"}])
        self.assertFalse(self.receipt_path().exists())

    def test_generated_and_binary_filename_collision_is_rejected(self):
        self.prepare()
        self.build(outputs=[{"filename": "beta.jar"}])
        with self.assertRaisesRegex(mods.ModError, "filenames collide"):
            builder.assemble(self.root, "test-run")

    def test_source_changes_during_build_cannot_get_success_receipt(self):
        self.prepare()
        with self.assertRaisesRegex(mods.ModError, "Source changed while building"):
            self.build(mutation=lambda: (self.source / "Main.java").write_text("class Changed {}"))
        self.assertFalse(self.receipt_path().exists())

    def test_source_changes_after_build_invalidate_receipt(self):
        self.prepare()
        self.build()
        (self.source / "Main.java").write_text("class LaterEdit {}", encoding="utf-8")
        with self.assertRaisesRegex(mods.ModError, "Source changed after compilation"):
            builder.assemble(self.root, "test-run")

    def test_collected_source_bytes_cannot_change_before_pack(self):
        self.prepare()
        self.build()
        receipt = builder.read_json(self.receipt_path())
        artifact = self.root / receipt["artifactPath"]
        artifact.write_bytes(b"edited collected output")
        with self.assertRaisesRegex(mods.ModError, "SHA-256"):
            builder.assemble(self.root, "test-run")
        self.assertEqual(artifact.read_bytes(), b"edited collected output")

    def test_ordered_generation_and_remapping_phases_use_same_recipe_arguments(self):
        self.recipe["phases"] = [[":common:generate"], [":fabric:remapJar"]]
        self.recipe["args"] = ["--offline"]
        self.save_inputs()
        self.prepare()
        commands = self.build()
        self.assertEqual([command[-1] for command in commands], [":common:generate", ":fabric:remapJar"])
        self.assertTrue(all("--offline" in command and "--no-daemon" in command for command in commands))
        receipt = builder.read_json(self.receipt_path())
        self.assertEqual(receipt["tasks"], self.recipe["phases"])

    def test_changed_plan_invalidates_run(self):
        self.prepare()
        self.recipe["args"] = ["--offline"]
        self.save_inputs()
        with self.assertRaisesRegex(mods.ModError, "changed during this run"):
            self.build()

    def test_successful_mixed_pack_preserves_built_bytes_hashes_metadata_and_notices(self):
        self.prepare()
        self.build()
        artifact = builder.assemble(self.root, "test-run")
        receipt = builder.read_json(self.receipt_path())
        expected_source = (self.root / receipt["artifactPath"]).read_bytes()
        expected_binary = (self.root / self.binary_entry["artifact"]["path"]).read_bytes()
        with zipfile.ZipFile(artifact) as archive:
            self.assertIsNone(archive.testzip())
            self.assertEqual(archive.read("mods/alpha-built.jar"), expected_source)
            self.assertEqual(archive.read("mods/beta.jar"), expected_binary)
            self.assertNotIn("mods/alpha-baseline.jar", archive.namelist())
            lock = json.loads(archive.read("inventory/mods.lock.json"))
            entries = {entry["modId"]: entry for entry in lock["entries"]}
            self.assertEqual(entries["alpha"]["version"], "2.0")
            self.assertEqual(entries["alpha"]["sha256"], hashlib.sha256(expected_source).hexdigest())
            self.assertEqual(entries["alpha"]["size"], len(expected_source))
            self.assertTrue(entries["alpha"]["artifact"]["builtFromSource"])
            self.assertEqual(entries["beta"]["sha256"], self.binary_entry["sha256"])
            self.assertEqual(entries["alpha"]["source"], self.source_entry["source"])
            self.assertEqual(archive.read("licenses/jars/alpha-built.jar/LICENSE"),
                             b"Built artifact author license\n")
            self.assertEqual(archive.read("licenses/sources/alpha-source/LICENSE"),
                             (self.source / "LICENSE").read_bytes())
            self.assertEqual(archive.read("licenses/repository/inventory/notices/author.txt"),
                             (self.root / "inventory" / "notices" / "author.txt").read_bytes())
            provenance = json.loads(archive.read("BUILD-PROVENANCE.json"))
            self.assertEqual({item["mode"] for item in provenance}, {"source", "binary"})
            self.assertEqual(json.loads(archive.read("inventory/build-recipes.json")), self.plan)
            self.assertTrue(json.loads(archive.read("PACK-INFO.json"))["private"])
            self.assertFalse(lock["build"]["runtimeValidated"])
        self.assertEqual(self.git("status", "--porcelain"), "")

    def test_wrapper_accepts_explicit_root_workdir_and_uses_upstream_properties(self):
        upstream = self.source / "gradle" / "wrapper"
        upstream.mkdir(parents=True)
        properties = b"distributionUrl=https\\://services.gradle.org/distributions/gradle-8.5-bin.zip\n"
        (upstream / "gradle-wrapper.properties").write_bytes(properties)
        root_wrapper = self.root / "gradle" / "wrapper"
        root_wrapper.mkdir(parents=True)
        (root_wrapper / "gradle-wrapper.jar").write_bytes(b"test bootstrap")
        work = self.root / "build" / "wrapper-test"
        command = builder.wrapper_command(self.root, self.source, work, self.recipe)
        self.assertEqual(command[-2:], ["--project-dir", str(self.source)])
        self.assertEqual((work / "wrapper" / "gradle-wrapper.properties").read_bytes(), properties)
        self.assertEqual((work / "wrapper" / "gradle-wrapper.jar").read_bytes(), b"test bootstrap")
        self.assertFalse((upstream / "gradle-wrapper.jar").exists())

    def test_minecraft_incompatible_source_output_is_rejected(self):
        self.prepare()
        with self.assertRaises(mods.ModError):
            self.build(outputs=[{"filename": "alpha-wrong-minecraft.jar", "minecraft": "~1.21"}])
            builder.assemble(self.root, "test-run")

    def test_java_incompatible_source_output_is_rejected(self):
        self.prepare()
        with self.assertRaises(mods.ModError):
            self.build(outputs=[{"filename": "alpha-java21.jar", "java": ">=21", "class_major": 65}])
            builder.assemble(self.root, "test-run")


if __name__ == "__main__":
    unittest.main()
