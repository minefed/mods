"""Fixture integrity and isolation tests; never execute Java or access the network."""

from contextlib import contextmanager
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import build_modpack as builder
import mods
import prepare_model_fixtures as fixtures


def archive(entries):
    data = io.BytesIO()
    with zipfile.ZipFile(data, 'w') as jar:
        for name, content in entries.items():
            jar.writestr(name, content)
    return data.getvalue()


class ModelFixtureTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='minefed-model-fixtures-')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        (self.root / 'scripts').mkdir()
        (self.root / fixtures.SCRIPT).write_text('reviewed generator', encoding='utf-8')
        self.payloads = {
            'minecraft': archive({'version.json': '{"id":"1.20.4"}', 'official.class': b'original'}),
            'mappings': archive({'mappings/mappings.tiny': b'tiny\t2\t0\tofficial\tintermediary\n'}),
            'remapper': b'reviewed executable, never executed by this test',
            'scena': b'reviewed Scena fixture',
        }
        self.manifest = {'schemaVersion': 1, 'minecraftVersion': '1.20.4', 'artifacts': {
            key: {'fileName': key + '.jar', 'url': 'https://example.invalid/' + key + '.jar',
                  'sha256': hashlib.sha256(data).hexdigest(), 'size': len(data),
                  'license': 'test-only synthetic data', 'licenseUrl': 'https://example.invalid/license',
                  'source': 'synthetic test fixture'} for key, data in self.payloads.items()}}
        self.save_manifest()
        self.download = patch.object(mods, 'download', side_effect=lambda url:
                                     io.BytesIO(self.payloads[url.rsplit('/', 1)[1][:-4]])).start()
        self.addCleanup(patch.stopall)
        patch.object(builder, 'java_home', return_value=self.root / 'jdk17').start()
        self.lock_events = []

        @contextmanager
        def gradle_lock(root):
            self.lock_events.append('enter-gradle')
            yield
            self.lock_events.append('leave-gradle')

        patch.object(builder, 'gradle_cache_lock', side_effect=gradle_lock).start()
        self.run = patch.object(subprocess, 'run', side_effect=self.fake_remap).start()

    def save_manifest(self):
        (self.root / fixtures.MANIFEST).write_text(json.dumps(self.manifest), encoding='utf-8')

    def fake_remap(self, command, **kwargs):
        self.assertEqual(self.lock_events[-1], 'enter-gradle')
        self.assertEqual(command[-3:], ['official', 'intermediary', '--threads=2'])
        self.assertNotIn('--ignoreConflicts', command)
        self.assertNotIn('--removeFrames', command)
        output = Path(command[7])
        output.write_bytes(archive({'version.json': '{"id":"1.20.4"}',
                                   **{name: b'remapped ' + name.encode() for name in fixtures.CLASSES}}))
        return subprocess.CompletedProcess(command, 0)

    def test_prepare_then_reuse_with_distinct_empty_worker_homes(self):
        with patch.dict(os.environ, {'GRADLE_USER_HOME': str(self.root / 'empty-worker-0')}):
            first = fixtures.prepare(self.root)
        with patch.dict(os.environ, {'GRADLE_USER_HOME': str(self.root / 'empty-worker-1')}):
            self.assertEqual(first, fixtures.prepare(self.root))
            self.assertEqual(first, fixtures.fingerprint(self.root))
        self.assertEqual(self.download.call_count, 4)
        self.assertEqual(self.run.call_count, 1)
        self.assertEqual(set(first['outputs']), {fixtures.MINECRAFT, fixtures.SCENA})
        self.assertEqual(set(first['minecraftClassSha256']), set(fixtures.CLASSES))
        self.assertFalse((self.root / 'empty-worker-0').exists())
        self.assertEqual(self.lock_events, ['enter-gradle', 'leave-gradle'] * 2)

    def test_download_mode_cannot_execute_java_or_claim_prepared(self):
        fixtures.prepare(self.root, download_only=True)
        self.run.assert_not_called()
        self.assertEqual(self.lock_events, [])
        with self.assertRaisesRegex(mods.ModError, 'missing'):
            fixtures.fingerprint(self.root)

    def test_oversized_download_is_not_published(self):
        self.payloads['minecraft'] += b'corrupt'
        with self.assertRaisesRegex(mods.ModError, 'larger'):
            fixtures.prepare(self.root)
        self.assertEqual(list((fixtures.directory(self.root) / 'downloads').iterdir()), [])
        self.run.assert_not_called()

    def test_same_length_wrong_hash_is_not_published(self):
        self.payloads['minecraft'] = b'x' * len(self.payloads['minecraft'])
        with self.assertRaises(mods.ModError):
            fixtures.prepare(self.root)
        self.assertEqual(list((fixtures.directory(self.root) / 'downloads').iterdir()), [])
        self.run.assert_not_called()

    def test_interrupted_download_removes_partial_file(self):
        class Interrupted(io.BytesIO):
            def read(self, size=-1):
                raise KeyboardInterrupt()
        self.download.side_effect = lambda url: Interrupted()
        with self.assertRaises(KeyboardInterrupt):
            fixtures.prepare(self.root)
        self.assertEqual(list((fixtures.directory(self.root) / 'downloads').iterdir()), [])

    def test_corrupt_existing_download_fails_without_network_or_remap(self):
        fixtures.prepare(self.root, download_only=True)
        cached = fixtures.directory(self.root) / 'downloads/minecraft.jar'
        cached.write_bytes(b'corrupt')
        self.download.reset_mock()
        with self.assertRaises(mods.ModError):
            fixtures.prepare(self.root)
        self.download.assert_not_called()
        self.run.assert_not_called()

    def test_remapper_failure_does_not_publish_output_or_receipt(self):
        self.run.side_effect = lambda command, **kwargs: subprocess.CompletedProcess(command, 7)
        with self.assertRaisesRegex(mods.ModError, 'remapping failed'):
            fixtures.prepare(self.root)
        base = fixtures.directory(self.root)
        self.assertFalse((base / fixtures.MINECRAFT).exists())
        self.assertFalse((base / 'receipt.json').exists())
        self.assertEqual(list(base.glob('prepare-*')), [])

    def test_timeout_preserves_previous_outputs_and_receipt(self):
        fixtures.prepare(self.root)
        base = fixtures.directory(self.root)
        before = {name: (base / name).read_bytes()
                  for name in (fixtures.MINECRAFT, fixtures.SCENA, 'receipt.json')}
        (self.root / fixtures.SCRIPT).write_text('new generator requiring remap', encoding='utf-8')
        self.run.side_effect = subprocess.TimeoutExpired('synthetic remapper', 300)
        with self.assertRaises(subprocess.TimeoutExpired):
            fixtures.prepare(self.root)
        for name, content in before.items():
            self.assertEqual((base / name).read_bytes(), content)
        self.assertEqual(list(base.glob('prepare-*')), [])
        with self.assertRaisesRegex(mods.ModError, 'generator changed'):
            fixtures.fingerprint(self.root)

    def test_bad_remapped_version_or_missing_class_cannot_publish(self):
        def incomplete(command, **kwargs):
            Path(command[7]).write_bytes(archive({'version.json': '{"id":"1.20.5"}'}))
            return subprocess.CompletedProcess(command, 0)
        self.run.side_effect = incomplete
        with self.assertRaisesRegex(mods.ModError, 'not Minecraft'):
            fixtures.prepare(self.root)
        self.assertFalse((fixtures.directory(self.root) / 'receipt.json').exists())

    def test_output_tampering_fails_both_reuse_and_fingerprint(self):
        fixtures.prepare(self.root)
        (fixtures.directory(self.root) / fixtures.MINECRAFT).write_bytes(b'tampered')
        with self.assertRaises(mods.ModError):
            fixtures.fingerprint(self.root)
        with self.assertRaises(mods.ModError):
            fixtures.prepare(self.root)
        self.assertEqual(self.run.call_count, 1)

    def test_forged_scena_receipt_cannot_override_independent_upstream_pin(self):
        fixtures.prepare(self.root)
        base = fixtures.directory(self.root)
        scena = base / fixtures.SCENA
        scena.write_bytes(b'tampered Scena')
        receipt = json.loads((base / 'receipt.json').read_text())
        receipt['outputs'][fixtures.SCENA] = fixtures.describe(scena)
        (base / 'receipt.json').write_text(json.dumps(receipt))
        with self.assertRaises(mods.ModError):
            fixtures.fingerprint(self.root)

    def test_generator_change_requires_reprepare_and_reuses_verified_downloads(self):
        original = fixtures.prepare(self.root)
        (self.root / fixtures.SCRIPT).write_text('new reviewed generator', encoding='utf-8')
        with self.assertRaisesRegex(mods.ModError, 'generator changed'):
            fixtures.fingerprint(self.root)
        replacement = fixtures.prepare(self.root)
        self.assertNotEqual(original['inputs'], replacement['inputs'])
        self.assertEqual(self.download.call_count, 4)
        self.assertEqual(self.run.call_count, 2)

    def test_wrong_mapping_namespace_fails_before_remapper(self):
        self.payloads['mappings'] = archive({'mappings/mappings.tiny': b'tiny\t2\t0\tnamed\tofficial\n'})
        artifact = self.manifest['artifacts']['mappings']
        artifact.update(size=len(self.payloads['mappings']),
                        sha256=hashlib.sha256(self.payloads['mappings']).hexdigest())
        self.save_manifest()
        with self.assertRaisesRegex(mods.ModError, 'official -> intermediary'):
            fixtures.prepare(self.root)
        self.run.assert_not_called()

    def test_manifest_rejects_traversal_duplicate_and_unreviewed_http(self):
        for value in ('../minecraft.jar', 'scena.jar'):
            self.manifest['artifacts']['minecraft']['fileName'] = value
            self.save_manifest()
            with self.assertRaises(mods.ModError):
                fixtures.load_manifest(self.root)
        self.manifest['artifacts']['minecraft']['fileName'] = 'minecraft.jar'
        self.manifest['artifacts']['minecraft']['url'] = 'http://example.invalid/minecraft.jar'
        self.save_manifest()
        with self.assertRaises(mods.ModError):
            fixtures.load_manifest(self.root)

    def test_source_receipt_fingerprint_includes_model_fixture_contents(self):
        prepared = fixtures.prepare(self.root)
        plan = {'entries': [{'mode': 'source', 'java': 17}]}
        recipe = {'sourcePath': 'minefed-client-compat', 'tasks': ['verifyModelVariantMixin']}
        result = builder.tool_fingerprint(self.root, plan, recipe)
        self.assertEqual(result['modelProbeFixtures'], prepared)
        recipe['tasks'] = ['build', 'verifyPtsCompatibility']
        self.assertNotIn('modelProbeFixtures', builder.tool_fingerprint(self.root, plan, recipe))


class ModelFixtureRepositoryTests(unittest.TestCase):
    def test_checked_in_pins_match_java_scena_probe_and_stay_local(self):
        manifest = fixtures.load_manifest(fixtures.ROOT)
        probe = fixtures.ROOT / 'minefed-client-compat/src/probe/java/ScenaModelCacheProbe.java'
        # Source submodules can be absent, or pinned to the pre-model-probe
        # revision while this independent parent tooling change is integrated.
        if probe.is_file():
            self.assertIn(manifest['artifacts']['scena']['sha256'], probe.read_text())
        release = json.loads((fixtures.ROOT / 'inventory/release-inputs.json').read_text(encoding='utf-8'))
        self.assertNotIn(fixtures.DIRECTORY, json.dumps(release))

    def test_parent_prepares_shared_fixtures_and_recipe_passes_explicit_paths(self):
        build = (fixtures.ROOT / 'build.gradle').read_text(encoding='utf-8')
        self.assertIn("commandLine pythonExecutable, 'scripts/prepare_model_fixtures.py', 'prepare'", build)
        self.assertIn('compatibilityFixtures.configure { dependsOn modelFixtures }', build)
        plan = json.loads((fixtures.ROOT / 'inventory/build-recipes.json').read_text(encoding='utf-8'))
        recipe = next(r for r in plan['entries'] if r['modId'] == 'minefed-client-compat')
        tasks = {task for phase in recipe.get('phases', [recipe['tasks']]) for task in phase}
        # Older recipes can intentionally omit model probes. If enabled, every
        # worker must pass the exact shared paths checked by the receipt hook.
        if tasks & fixtures.PROBE_TASKS:
            self.assertIn('-PminecraftJar=../' + fixtures.DIRECTORY + '/' + fixtures.MINECRAFT, recipe['args'])
            self.assertIn('-PscenaJar=../' + fixtures.DIRECTORY + '/' + fixtures.SCENA, recipe['args'])


if __name__ == '__main__':
    unittest.main()
