"""Offline integrity tests for mixed source/binary builds; no game or Gradle launch."""

import copy
from contextlib import ExitStack, contextmanager, redirect_stderr, redirect_stdout
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
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


class SourceLockTests(unittest.TestCase):
    def test_process_lock_blocks_same_mod_until_release_but_allows_other_mod(self):
        worker = """
import sys
from pathlib import Path
from build_modpack import source_lock

root = Path(sys.argv[1])
if sys.argv[2] == 'holder':
    with source_lock(root, 'alpha'):
        (root / 'alpha-held').touch()
        sys.stdin.readline()
else:
    with source_lock(root, 'beta'):
        (root / 'beta-entered').touch()
    (root / 'alpha-attempted').touch()
    with source_lock(root, 'alpha'):
        (root / 'alpha-entered').touch()
"""
        with tempfile.TemporaryDirectory(prefix="minefed-lock-test-") as temporary:
            root = Path(temporary).resolve()
            processes = []

            def launch(role):
                process = subprocess.Popen(
                    [sys.executable, "-u", "-c", worker, str(root), role],
                    cwd=Path(__file__).resolve().parent,
                    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    text=True, encoding="utf-8")
                processes.append(process)
                return process

            def await_marker(name, process):
                deadline = time.monotonic() + 15
                while not (root / name).exists():
                    if process.poll() is not None:
                        self.fail(f"Worker exited before {name}: {process.communicate()}")
                    if time.monotonic() >= deadline:
                        self.fail(f"Worker did not reach {name} within 15 seconds")
                    time.sleep(0.02)

            try:
                holder = launch("holder")
                await_marker("alpha-held", holder)
                contender = launch("contender")
                # Beta must enter while another process still owns Alpha.
                await_marker("beta-entered", contender)
                await_marker("alpha-attempted", contender)
                self.assertIsNone(holder.poll())
                # The contender has no work besides entering Alpha and exiting.
                with self.assertRaises(subprocess.TimeoutExpired):
                    contender.wait(timeout=1)
                self.assertFalse((root / "alpha-entered").exists())
                _, holder_errors = holder.communicate(input="release\n", timeout=15)
                _, contender_errors = contender.communicate(timeout=15)
                self.assertEqual(holder.returncode, 0, holder_errors)
                self.assertEqual(contender.returncode, 0, contender_errors)
                self.assertTrue((root / "alpha-entered").is_file())
            finally:
                for process in processes:
                    if process.poll() is None:
                        process.kill()
                    process.communicate(timeout=15)


class GradleCacheLockTests(unittest.TestCase):
    worker = """
import sys
from pathlib import Path
from build_modpack import gradle_cache_lock

root, markers = map(Path, sys.argv[1:3])
role = sys.argv[3]
(markers / (role + '-attempted')).touch()
with gradle_cache_lock(root):
    (markers / (role + '-entered')).touch()
    sys.stdin.readline()
"""

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="minefed-gradle-lock-test-")
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name).resolve()
        self.processes = []
        self.addCleanup(self.stop_workers)

    def stop_workers(self):
        for process in self.processes:
            if process.poll() is None:
                process.kill()
            process.communicate(timeout=15)

    def launch(self, role, gradle_home):
        workspace = self.directory / (role + '-workspace')
        workspace.mkdir()
        environment = dict(os.environ, GRADLE_USER_HOME=str(gradle_home))
        process = subprocess.Popen(
            [sys.executable, "-u", "-c", self.worker, str(workspace), str(self.directory), role],
            cwd=Path(__file__).resolve().parent, env=environment,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8")
        self.processes.append(process)
        return process

    def await_marker(self, name, process):
        deadline = time.monotonic() + 15
        while not (self.directory / name).exists():
            if process.poll() is not None:
                self.fail(f"Worker exited before {name}: {process.communicate()}")
            if time.monotonic() >= deadline:
                self.fail(f"Worker did not reach {name} within 15 seconds")
            time.sleep(0.02)

    def release(self, process):
        _, errors = process.communicate(input="release\n", timeout=15)
        self.assertEqual(process.returncode, 0, errors)

    def test_shared_gradle_home_blocks_other_workspace_until_release(self):
        gradle_home = self.directory / 'shared-gradle-home'
        holder = self.launch('holder', gradle_home)
        self.await_marker('holder-entered', holder)
        contender = self.launch('contender', gradle_home)
        self.await_marker('contender-attempted', contender)
        # Workers use distinct workspaces; the shared Gradle cache is the boundary.
        time.sleep(0.5)
        self.assertIsNone(contender.poll())
        self.assertFalse((self.directory / 'contender-entered').exists())
        self.release(holder)
        self.await_marker('contender-entered', contender)
        self.release(contender)

    def test_separate_gradle_homes_can_enter_before_first_process_releases(self):
        holder = self.launch('holder', self.directory / 'gradle-home-a')
        self.await_marker('holder-entered', holder)
        contender = self.launch('contender', self.directory / 'gradle-home-b')
        self.await_marker('contender-entered', contender)
        self.assertIsNone(holder.poll())
        self.release(contender)
        self.release(holder)


class GradleProcessTests(unittest.TestCase):
    worker = """
import os
from pathlib import Path
import subprocess
import sys
import time
from build_modpack import _file_lock

directory, role = Path(sys.argv[1]), sys.argv[2]
if role == 'wrapper':
    subprocess.Popen([sys.executable, '-u', '-c', sys.argv[3], str(directory), 'descendant'],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
with _file_lock(directory / (role + '.lock'), 'Unexpected test lock contender'):
    (directory / (role + '.ready')).write_text(str(os.getpid()))
    while True:
        time.sleep(0.1)
"""

    def assert_worker_released(self, directory, role):
        # The worker holds this OS lock for its entire lifetime. Reacquiring it
        # is portable evidence that cleanup finished, without guessing user PIDs.
        with (directory / (role + '.lock')).open('r+b') as stream:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)

    def test_cancellation_stops_wrapper_and_descendant_before_cache_unlock(self):
        for exception_type in (KeyboardInterrupt, SystemExit, RuntimeError):
            with self.subTest(exception=exception_type.__name__), \
                    tempfile.TemporaryDirectory(prefix='minefed-cancel-test-') as temporary:
                directory = Path(temporary).resolve()
                command = [sys.executable, '-u', '-c', self.worker, str(directory), 'wrapper', self.worker]
                original_wait = subprocess.Popen.wait
                cancelled = []

                def wait_then_cancel(process, *args, **kwargs):
                    if process.args == command and not cancelled:
                        cancelled.append(process)
                        deadline = time.monotonic() + 15
                        while not all((directory / (role + '.ready')).exists() for role in ('wrapper', 'descendant')):
                            if process.poll() is not None or time.monotonic() >= deadline:
                                raise AssertionError('Cancellation fixture did not start both processes')
                            time.sleep(0.02)
                        raise exception_type('Simulated runner cancellation')
                    return original_wait(process, *args, **kwargs)

                environment = dict(os.environ, GRADLE_USER_HOME=str(directory / 'gradle-home'))
                try:
                    with patch.dict(os.environ, environment), \
                            patch.object(subprocess.Popen, 'wait', new=wait_then_cancel), \
                            (directory / 'worker.log').open('w') as log:
                        with builder.gradle_cache_lock(directory):
                            with self.assertRaisesRegex(exception_type, 'Simulated runner cancellation'):
                                builder.run_gradle_process(command, cwd=Path(__file__).resolve().parent,
                                                           env=environment, stdout=log)
                            # The global lock is still held here. Both real test
                            # processes must already have released their own locks.
                            self.assert_worker_released(directory, 'wrapper')
                            self.assert_worker_released(directory, 'descendant')
                    self.assertIsNotNone(cancelled[0].poll())
                finally:
                    for process in cancelled:
                        if process.poll() is None:
                            builder.stop_process_tree(process)

    def test_normal_process_exit_preserves_status_and_output(self):
        with tempfile.TemporaryDirectory(prefix='minefed-process-test-') as temporary:
            directory = Path(temporary)
            with (directory / 'output.log').open('w') as output:
                result = builder.run_gradle_process(
                    [sys.executable, '-c', "import sys; print('build failed'); sys.exit(7)"],
                    cwd=directory, env=dict(os.environ), stdout=output)
            self.assertEqual(result.returncode, 7)
            self.assertIn('build failed', (directory / 'output.log').read_text())


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
        self.contexts.enter_context(patch.dict(os.environ, {"GRADLE_USER_HOME": str(self.root / "gradle-home")}))
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
                patch.object(builder, "run_gradle_process", side_effect=invoke) as process:
            builder.build_source(self.root, run, "alpha")
        return [call.args[0] for call in process.call_args_list if call.args[0][0] == "fake-gradle"]

    def receipt_path(self, run="test-run"):
        return builder.run_path(self.root, run) / "sources" / "alpha" / "result.json"

    def save_dependency(self, **changes):
        path = self.jar(self.root / "vendor/local/beta-2.0.jar", "beta", version="2.0",
                        marker=b"official dependency release bytes")
        digest, size = mods.file_digest(path)
        entry = copy.deepcopy(self.binary_entry)
        entry.update(fileName=path.name, version="2.0", sha256=digest, size=size)
        entry["artifact"]["path"] = path.relative_to(self.root).as_posix()
        entry.update(changes)
        dependencies = {"schemaVersion": 1, "minecraftVersion": "1.20.4", "loader": "fabric",
                        "entries": [entry]}
        self.plan["dependencyManifest"] = "inventory/dependencies.lock.json"
        next(recipe for recipe in self.plan["entries"] if recipe["modId"] == "beta")["dependency"] = True
        self.save_inputs()
        builder.write_json(self.root / self.plan["dependencyManifest"], dependencies)
        return dependencies

    def test_official_dependency_overlay_is_prepared_and_packaged_without_changing_baseline(self):
        dependencies = self.save_dependency()
        baseline_path = self.root / "inventory/mods.lock.json"
        baseline_bytes = baseline_path.read_bytes()
        original_bytes = (self.root / self.binary_entry["artifact"]["path"]).read_bytes()
        dependency = dependencies["entries"][0]
        expected_bytes = (self.root / dependency["artifact"]["path"]).read_bytes()
        with patch.object(mods, "hydrate", wraps=mods.hydrate) as hydrate:
            self.prepare()
        self.assertEqual(hydrate.call_args.args[1]["entries"], [dependency])
        self.build()
        artifact = builder.assemble(self.root, "test-run")
        with zipfile.ZipFile(artifact) as archive:
            self.assertEqual(archive.read("mods/beta-2.0.jar"), expected_bytes)
            self.assertNotIn("mods/beta.jar", archive.namelist())
            entries = json.loads(archive.read("inventory/mods.lock.json"))["entries"]
            actual = next(entry for entry in entries if entry["modId"] == "beta")
            self.assertEqual(actual, dependency)
            provenance = json.loads(archive.read("BUILD-PROVENANCE.json"))
            binary = next(item for item in provenance if item["modId"] == "beta")
            self.assertEqual((binary["mode"], binary["version"], binary["sha256"]),
                             ("binary", "2.0", dependency["sha256"]))
        self.assertEqual(baseline_path.read_bytes(), baseline_bytes)
        self.assertEqual((self.root / self.binary_entry["artifact"]["path"]).read_bytes(), original_bytes)

    def test_dependency_overlay_preserves_excluded_entries_with_same_mod_id(self):
        excluded = self.baseline("beta-legacy.jar", "beta")
        excluded.update(included=False, exclusionReason="Historical duplicate")
        self.manifest["entries"].append(excluded)
        dependencies = self.save_dependency()
        manifest, _ = builder.load_plan(self.root)
        self.assertEqual(manifest["entries"][-1], excluded)
        self.assertEqual(sum(e["included"] for e in manifest["entries"]), 2)
        self.assertEqual(next(e for e in manifest["entries"] if e["modId"] == "beta" and e["included"]),
                         dependencies["entries"][0])

    def test_dependency_manifest_rejects_wrong_schema_target_and_loader(self):
        for key, value in (("schemaVersion", 2), ("minecraftVersion", "1.21"), ("loader", "forge")):
            with self.subTest(key=key):
                dependencies = self.save_dependency()
                dependencies[key] = value
                builder.write_json(self.root / self.plan["dependencyManifest"], dependencies)
                with self.assertRaises(mods.ModError):
                    builder.load_plan(self.root)

    def test_dependency_manifest_rejects_nonbinary_excluded_source_and_unknown_entries(self):
        for changes in ({"management": "submodule", "source": self.source_entry["source"]},
                        {"source": self.source_entry["source"]},
                        {"included": False, "exclusionReason": "Excluded dependency"},
                        {"modId": "unknown"}, {"modId": "alpha"}):
            with self.subTest(changes=changes):
                self.save_dependency(**changes)
                with self.assertRaisesRegex(mods.ModError, "Dependency must"):
                    builder.load_plan(self.root)

    def test_dependency_manifest_rejects_duplicate_ids(self):
        dependencies = self.save_dependency()
        duplicate = copy.deepcopy(dependencies["entries"][0])
        duplicate["fileName"] = "beta-duplicate.jar"
        duplicate["artifact"]["path"] = "vendor/local/beta-duplicate.jar"
        dependencies["entries"].append(duplicate)
        builder.write_json(self.root / self.plan["dependencyManifest"], dependencies)
        with self.assertRaisesRegex(mods.ModError, "Duplicate dependency modId"):
            builder.load_plan(self.root)

    def test_dependency_manifest_cannot_omit_a_declared_dependency(self):
        self.save_dependency()
        self.recipe.update(mode="binary", dependency=True)
        self.save_inputs()
        with self.assertRaisesRegex(mods.ModError, "missing: alpha"):
            builder.load_plan(self.root)

    def test_dependency_recipes_require_a_manifest_instead_of_using_baseline(self):
        self.save_dependency()
        del self.plan["dependencyManifest"]
        self.save_inputs()
        with self.assertRaisesRegex(mods.ModError, "require dependencyManifest"):
            builder.load_plan(self.root)

    def test_dependency_manifest_cannot_replace_an_unflagged_binary(self):
        self.save_dependency()
        next(recipe for recipe in self.plan["entries"] if recipe["modId"] == "beta")["dependency"] = False
        self.save_inputs()
        with self.assertRaisesRegex(mods.ModError, "extra: beta"):
            builder.load_plan(self.root)

    def test_dependency_flag_must_be_boolean_and_only_used_on_binary_recipes(self):
        binary_recipe = next(recipe for recipe in self.plan["entries"] if recipe["modId"] == "beta")
        for value in ("true", 1, None):
            with self.subTest(value=value):
                binary_recipe["dependency"] = value
                self.save_inputs()
                with self.assertRaisesRegex(mods.ModError, "boolean on a binary recipe"):
                    builder.load_plan(self.root)
        del binary_recipe["dependency"]
        self.recipe["dependency"] = True
        self.save_inputs()
        with self.assertRaisesRegex(mods.ModError, "boolean on a binary recipe"):
            builder.load_plan(self.root)

    def test_dependency_overlay_rejects_collisions_with_remaining_inventory(self):
        for artifact_path in ("vendor/local/alpha-baseline.jar", "artifacts/local/alpha-baseline.jar"):
            with self.subTest(path=artifact_path):
                dependencies = self.save_dependency(fileName="alpha-baseline.jar")
                dependencies["entries"][0]["artifact"]["path"] = artifact_path
                builder.write_json(self.root / self.plan["dependencyManifest"], dependencies)
                with self.assertRaisesRegex(mods.ModError, "collides with inventory"):
                    builder.load_plan(self.root)

    def test_dependency_change_after_prepare_invalidates_run(self):
        dependencies = self.save_dependency()
        self.prepare()
        dependencies["entries"][0]["version"] = "3.0"
        builder.write_json(self.root / self.plan["dependencyManifest"], dependencies)
        with self.assertRaisesRegex(mods.ModError, "changed during this run"):
            self.build()

    def test_plan_without_dependency_manifest_preserves_legacy_inventory(self):
        manifest, plan = builder.load_plan(self.root)
        self.assertEqual(manifest, self.manifest)
        self.assertNotIn("dependencyManifest", plan)

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

    def test_verified_source_cache_reuses_only_identical_inputs(self):
        self.prepare('first')
        self.assertEqual(len(self.build('first')), 1)
        self.prepare('second')
        self.assertEqual(self.build('second'), [])
        receipt = builder.read_json(self.receipt_path('second'))
        self.assertTrue(receipt['cacheHit'])
        self.assertEqual(receipt['compiledRun'], 'first')
        self.assertEqual(receipt['run'], 'second')
        builder.assemble(self.root, 'second')

    def test_source_edit_invalidates_verified_cache(self):
        self.prepare('first')
        self.build('first')
        (self.source / 'new-source.txt').write_text('new input', encoding='utf-8')
        self.prepare('second')
        self.assertEqual(len(self.build('second')), 1)
        self.assertFalse(builder.read_json(self.receipt_path('second'))['cacheHit'])

    def test_root_wrapper_distribution_change_invalidates_source_cache(self):
        self.prepare('first')
        self.build('first')
        properties = self.root / 'gradle' / 'wrapper' / 'gradle-wrapper.properties'
        properties.parent.mkdir(parents=True, exist_ok=True)
        properties.write_text('distributionUrl=https://services.gradle.org/distributions/gradle-8.13-bin.zip', encoding='utf-8')
        self.prepare('second')
        self.assertEqual(len(self.build('second')), 1)

    def change_tool(self, relative='scripts/source-repositories.gradle'):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('Changed tool input\n', encoding='utf-8')

    def test_mods_tool_change_invalidates_verified_source_cache(self):
        self.prepare('first')
        self.build('first')
        self.change_tool('scripts/mods.py')
        self.prepare('second')
        self.assertEqual(len(self.build('second')), 1)

    def test_tool_change_while_waiting_for_gradle_lock_prevents_compilation(self):
        @contextmanager
        def changed_lock(root):
            self.change_tool()
            yield

        self.prepare()
        with patch.object(builder, 'gradle_cache_lock', side_effect=changed_lock):
            with self.assertRaisesRegex(mods.ModError, 'Build tools changed'):
                self.build()
        self.assertFalse((self.source / 'build/libs/alpha-built.jar').exists())
        self.assertFalse(self.receipt_path().exists())

    def test_tool_change_during_build_cannot_publish_receipt_or_cache(self):
        self.prepare()
        with self.assertRaisesRegex(mods.ModError, 'Build tools changed'):
            self.build(mutation=self.change_tool)
        self.assertFalse(self.receipt_path().exists())
        self.assertFalse(list((self.root / 'build/source-cache').glob('*/result.json')))

    def test_tool_change_during_cache_copy_cannot_publish_receipt(self):
        self.prepare('first')
        self.build('first')
        self.prepare('second')
        original_copy = shutil.copyfile

        def changing_copy(source, destination, *args, **kwargs):
            result = original_copy(source, destination, *args, **kwargs)
            self.change_tool()
            return result

        with patch.object(builder.shutil, 'copyfile', side_effect=changing_copy):
            with self.assertRaisesRegex(mods.ModError, 'Build tools changed'):
                self.build('second')
        self.assertFalse(self.receipt_path('second').exists())

    def test_tool_change_after_compilation_prevents_packaging(self):
        self.prepare()
        self.build()
        self.change_tool('scripts/mods.py')
        with self.assertRaisesRegex(mods.ModError, 'Build tools changed'):
            builder.assemble(self.root, 'test-run')
        self.assertFalse((self.root / 'build/distributions').exists())

    def test_rebuild_sources_forces_compilation(self):
        self.prepare('first')
        self.build('first')
        self.prepare('second')
        with patch.dict(builder.os.environ, {'MINEFED_REBUILD_SOURCES': '1'}):
            self.assertEqual(len(self.build('second')), 1)

    def test_source_cache_corruption_is_rejected(self):
        self.prepare('first')
        self.build('first')
        record_path = next((self.root / 'build' / 'source-cache').glob('*/result.json'))
        record = builder.read_json(record_path)
        (self.root / record['artifactPath']).write_bytes(b'corrupted')
        self.prepare('second')
        with self.assertRaisesRegex(mods.ModError, 'SHA-256'):
            self.build('second')

    def test_unexpected_source_version_is_rejected(self):
        self.prepare()
        with self.assertRaisesRegex(mods.ModError, 'Unexpected source version'):
            self.build(outputs=[{'filename': 'alpha-built.jar', 'version': '3.0'}])

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
