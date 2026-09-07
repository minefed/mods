"""Public packaging policy and exact-byte checks; no Gradle or network."""
import copy
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import mods
import release_pack as release


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        # Packaging tests remain offline/JDK-free. The dependency checker has
        # separate fixture tests and an explicitly enabled real-Java integration.
        checker = patch.object(release.release_dependencies, 'check_selected', return_value={'scope': 'mocked packaging fixture', 'runtimeValidated': False})
        checker.start()
        self.addCleanup(checker.stop)
        self.temporary = tempfile.TemporaryDirectory(prefix='minefed-release-test-')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        (self.root / 'inventory').mkdir()
        self.alpha = self.jar('alpha-original.jar', 'alpha', '1.0')
        self.beta = self.jar('beta.jar', 'beta', '1.0', environment='server')
        self.gamma = self.jar('gamma.jar', 'gamma', '1.0')
        self.baseline = self.manifest([self.alpha, self.beta, self.gamma])
        self.write('inventory/mods.lock.json', self.baseline)
        self.built = self.jar('alpha-built.jar', 'alpha', '2.0')
        self.built['artifact']['builtFromSource'] = True
        self.produced = self.manifest([self.built, self.beta, self.gamma])
        self.produced['build'] = {'run': 'test-run', 'sourceCompilation': True, 'sourceCount': 1, 'binaryCount': 2, 'runtimeValidated': False}
        self.recipes = {'entries': [{'modId': 'alpha', 'mode': 'source'}, {'modId': 'beta', 'mode': 'binary'}, {'modId': 'gamma', 'mode': 'binary'}]}
        self.provenance = [{'modId': 'alpha', 'mode': 'source', 'run': 'test-run', 'sha256': self.built['sha256'],
                            'source': {'workingTreeStatus': ''}}, {'modId': 'beta', 'mode': 'binary'}, {'modId': 'gamma', 'mode': 'binary'}]
        self.policy = {'schemaVersion': 1, 'minecraftVersion': '1.20.4', 'fabricLoaderVersion': '0.18.0', 'timezone': 'Asia/Seoul',
                       'entries': [self.decision('alpha'), self.decision('beta', client=False),
                                   self.decision('gamma', distribution='download', artifact='baseline', downloadUrl='https://cdn.modrinth.com/gamma.jar')]}
        self.write('inventory/release-policy.json', self.policy)
        resource = self.root / 'resourcepack'
        (resource / 'resource_pack/assets/minefed').mkdir(parents=True)
        (resource / 'resource_pack/pack.mcmeta').write_text('{"pack":{"pack_format":22,"description":"fixture"}}')
        (resource / 'resource_pack/assets/minefed/fixture.json').write_text('{"real":"game bytes"}')
        (resource / 'design').mkdir()
        (resource / 'design/private-project.txt').write_text('must never be published')
        for args in [('init', '-q'), ('config', 'user.name', 'Fixture'), ('config', 'user.email', 'fixture@example.invalid'),
                     ('add', '.'), ('commit', '-qm', 'test(resource): add fixture')]:
            self.git(*args)
        self.resource_lock = {'schemaVersion': 1, 'minecraftVersion': '1.20.4', 'entries': [{
            'id': 'minefed', 'sourcePath': 'resourcepack', 'sourceDir': 'resource_pack', 'commit': self.git('rev-parse', 'HEAD'),
            'ref': 'main', 'url': 'https://github.com/minefed/resourcepack', 'packFormat': 22,
            'license': {'redistribution': 'owner-authorized', 'noticeText': ['Fixture author copyright']}}]}
        self.write('inventory/resourcepacks.lock.json', self.resource_lock)
        self.input_zip()

    def git(self, *args):
        return subprocess.run(['git', '-C', str(self.root / 'resourcepack'), *args], check=True,
                              capture_output=True, text=True).stdout.strip()

    def write(self, path, value):
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(release.json_bytes(value))

    def jar(self, filename, identity, version, environment='*'):
        path = self.root / 'artifacts/local' / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(path, 'w') as archive:
            archive.writestr('fabric.mod.json', json.dumps({'schemaVersion': 1, 'id': identity, 'version': version,
                'environment': environment, 'depends': {'minecraft': '~1.20.4', 'java': '>=17'}}))
            archive.writestr('LICENSE', 'Fixture MIT author notice')
            archive.writestr('payload.bin', (identity + version).encode())
        digest, size = mods.file_digest(path)
        return {'modId': identity, 'fileName': filename, 'sha256': digest, 'size': size, 'version': version,
                'environment': environment, 'management': 'binary', 'source': None, 'included': True,
                'artifact': {'path': path.relative_to(self.root).as_posix(), 'redistribution': 'allowed', 'url': 'https://cdn.modrinth.com/' + filename},
                'license': 'MIT', 'licenseUrl': 'https://example.com/LICENSE', 'notes': 'fixture'}

    def manifest(self, entries):
        return {'schemaVersion': 1, 'minecraftVersion': '1.20.4', 'loader': 'fabric', 'entries': copy.deepcopy(entries)}

    def decision(self, identity, **kwargs):
        return {'modId': identity, 'distribution': 'embed', 'artifact': 'built', 'reason': 'Reviewed fixture permission',
                'evidenceUrls': ['https://example.com/LICENSE'], 'client': True, 'server': True, **kwargs}

    def input_zip(self, extra=None):
        path = self.root / 'build/input.zip'
        path.parent.mkdir(exist_ok=True)
        with zipfile.ZipFile(path, 'w') as archive:
            archive.writestr('inventory/mods.lock.json', release.json_bytes(self.produced))
            archive.writestr('inventory/build-recipes.json', release.json_bytes(self.recipes))
            archive.writestr('BUILD-PROVENANCE.json', release.json_bytes(self.provenance))
            archive.writestr('licenses/jars/alpha-built.jar/LICENSE', 'Preserved build author notice')
            for entry in self.produced['entries']:
                archive.write(self.root / entry['artifact']['path'], 'mods/' + entry['fileName'])
            if extra:
                archive.writestr(extra, 'malicious path')
        digest, size = mods.file_digest(path)
        self.write('build/latest.json', {**self.produced['build'], 'path': 'build/input.zip', 'sha256': digest,
                                       'size': size, 'artifactCount': 3, 'private': True})

    def run_release(self, version='20260907123456'):
        return release.release(self.root, 'build/latest.json', version)

    def test_three_assets_preserve_source_bytes_split_sides_and_keep_game_resources(self):
        manifest_path = self.run_release()
        report = json.loads(manifest_path.read_text())
        self.assertEqual({'server', 'client', 'resourcepack'}, {a['kind'] for a in report['assets']})
        self.assertEqual(4, len(list(manifest_path.parent.iterdir())))
        self.assertEqual('+09:00', report['createdAt'][-6:])
        for asset in report['assets']:
            self.assertEqual((asset['sha256'], asset['size']), mods.file_digest(self.root / asset['path']))
        with zipfile.ZipFile(manifest_path.parent / 'server.zip') as server:
            self.assertEqual((self.root / self.built['artifact']['path']).read_bytes(), server.read('mods/alpha-built.jar'))
            self.assertIn('mods/beta.jar', server.namelist())
            self.assertNotIn('mods/gamma.jar', server.namelist())
            self.assertEqual(b'Preserved build author notice', server.read('licenses/jars/alpha-built.jar/LICENSE'))
            self.assertEqual(3, len(json.loads(server.read('download-manifest.json'))['files']))
        with zipfile.ZipFile(manifest_path.parent / 'client.mrpack') as client:
            self.assertNotIn('overrides/mods/beta.jar', client.namelist())
            self.assertEqual((self.root / self.built['artifact']['path']).read_bytes(), client.read('overrides/mods/alpha-built.jar'))
            index = json.loads(client.read('modrinth.index.json'))
            self.assertEqual('20260907123456', index['versionId'])
            self.assertEqual({'sha1', 'sha512'}, set(index['files'][0]['hashes']))
            self.assertEqual(hashlib.sha512((self.root / self.gamma['artifact']['path']).read_bytes()).hexdigest(), index['files'][0]['hashes']['sha512'])
            self.assertIn('overrides/resourcepacks/minefed-20260907123456.zip', client.namelist())
        with zipfile.ZipFile(manifest_path.parent / 'resourcepack.zip') as resources:
            self.assertEqual(b'{"real":"game bytes"}', resources.read('assets/minefed/fixture.json'))
            self.assertFalse(any('design' in n or 'private-project' in n for n in resources.namelist()))
        self.assertFalse(report['runtimeValidated'])

    def test_local_only_embed_is_rejected_without_publishing_assets(self):
        self.produced['entries'][0]['artifact']['redistribution'] = 'local-only'
        self.input_zip()
        with self.assertRaisesRegex(mods.ModError, 'local-only'):
            self.run_release()
        self.assertFalse((self.root / 'build/releases/20260907123456').exists())

    def test_dependency_failure_prevents_all_public_assets(self):
        release.release_dependencies.check_selected.side_effect = mods.ModError('selected dependency missing')
        with self.assertRaisesRegex(mods.ModError, 'dependency missing'):
            self.run_release()
        self.assertFalse((self.root / 'build/releases/20260907123456').exists())

    def test_source_notices_identify_actual_commit_and_release_build_instructions(self):
        record = {**self.decision('alpha'), 'version': '2.0', 'license': 'GPL-3.0', 'licenseUrl': 'https://example.com/LICENSE',
                  'replacesBuiltArtifact': False, 'sourceCommitUrl': 'https://github.com/minefed/alpha/tree/' + '2' * 40,
                  'sourceArchiveUrl': 'https://github.com/minefed/alpha/archive/' + '2' * 40 + '.zip',
                  'sourceHistoryUrl': 'https://github.com/minefed/alpha/commits/' + '2' * 40,
                  'sourceCommitDate': '2026-09-07T13:00:00+09:00'}
        text = release.source_notices([record], '20260907123456')
        self.assertIn(record['sourceArchiveUrl'], text)
        self.assertIn(record['sourceHistoryUrl'], text)
        self.assertIn(record['sourceCommitDate'], text)
        self.assertIn('https://github.com/minefed/mods/tree/20260907123456/docs/BUILDING.md', text)
        self.assertIn('https://github.com/minefed/mods/tree/20260907123456/inventory/build-recipes.json', text)

    def test_explicit_original_download_uses_baseline_bytes_and_discloses_replacement(self):
        self.produced['entries'][0]['artifact']['redistribution'] = 'local-only'
        self.policy['entries'][0] = self.decision('alpha', distribution='download', artifact='baseline', downloadUrl='https://cdn.modrinth.com/alpha.jar')
        self.write('inventory/release-policy.json', self.policy)
        self.input_zip()
        manifest = self.run_release()
        with zipfile.ZipFile(manifest.parent / 'client.mrpack') as client:
            self.assertNotIn('overrides/mods/alpha-built.jar', client.namelist())
            entry = next(e for e in json.loads(client.read('overrides/download-manifest.json'))['files'] if e['modId'] == 'alpha')
            self.assertEqual('1.0', entry['version'])
            self.assertEqual('2.0', entry['inputBuild']['version'])
            self.assertTrue(entry['replacesBuiltArtifact'])
            self.assertEqual(self.alpha['sha256'], entry['sha256'])
            self.assertIn('Explicit policy replacement', client.read('overrides/LICENSES.md').decode())

    def test_zip_traversal_is_rejected_even_with_matching_outer_hash(self):
        self.input_zip('../escaped.txt')
        with self.assertRaisesRegex(mods.ModError, 'Unsafe'):
            self.run_release()
        self.assertFalse((self.root / 'escaped.txt').exists())

    def test_wrong_built_hash_and_unsupported_mrpack_host_are_rejected(self):
        self.produced['entries'][0]['sha256'] = '0' * 64
        self.input_zip()
        with self.assertRaises(mods.ModError):
            self.run_release()
        self.produced['entries'][0]['sha256'] = self.built['sha256']
        self.input_zip()
        self.policy['entries'][2]['downloadUrl'] = 'https://unsupported.example/gamma.jar'
        self.write('inventory/release-policy.json', self.policy)
        with self.assertRaisesRegex(mods.ModError, 'Modrinth does not support'):
            self.run_release()

    def test_late_failure_publishes_none_and_existing_release_is_never_overwritten(self):
        original = release.write_profile
        def fail_client(*args, **kwargs):
            if args[2] == 'client':
                raise mods.ModError('injected client failure')
            return original(*args, **kwargs)
        with patch.object(release, 'write_profile', side_effect=fail_client):
            with self.assertRaisesRegex(mods.ModError, 'injected'):
                self.run_release()
        self.assertFalse((self.root / 'build/releases/20260907123456').exists())
        manifest = self.run_release()
        before = manifest.read_bytes()
        with self.assertRaisesRegex(mods.ModError, 'exists'):
            self.run_release()
        self.assertEqual(before, manifest.read_bytes())

    def test_resource_commit_mismatch_or_dirty_files_are_rejected(self):
        self.resource_lock['entries'][0]['commit'] = '1' * 40
        self.write('inventory/resourcepacks.lock.json', self.resource_lock)
        with self.assertRaisesRegex(mods.ModError, 'reviewed commit'):
            self.run_release()
        self.resource_lock['entries'][0]['commit'] = self.git('rev-parse', 'HEAD')
        self.write('inventory/resourcepacks.lock.json', self.resource_lock)
        (self.root / 'resourcepack/resource_pack/pack.mcmeta').write_text('{}')
        with self.assertRaisesRegex(mods.ModError, 'clean'):
            self.run_release()

    def test_installer_verifies_required_files_rejects_modified_and_missing_manual(self):
        installation = self.root / 'installation'
        installation.mkdir()
        script = installation / 'install-mods.py'
        script.write_text(release.INSTALLER, encoding='utf-8')
        (installation / 'mods').mkdir()
        contents = b'correct reviewed bytes'
        jar = installation / 'mods/required.jar'
        jar.write_bytes(contents)
        record = {'path': 'mods/required.jar', 'sha256': hashlib.sha256(contents).hexdigest(), 'size': len(contents), 'reason': 'Restore from author'}
        self.write('installation/download-manifest.json', {'files': [record]})
        command = [sys.executable, str(script)]
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(0, result.returncode, result.stderr)
        jar.write_bytes(b'user changes')
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertNotEqual(0, result.returncode)
        self.assertEqual(b'user changes', jar.read_bytes())
        jar.unlink()
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertNotEqual(0, result.returncode)
        self.assertIn('incomplete', result.stderr)
        record['path'] = 'mods/../../outside.jar'
        self.write('installation/download-manifest.json', {'files': [record]})
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertNotEqual(0, result.returncode)
        self.assertFalse((self.root / 'outside.jar').exists())

    def test_installer_download_checks_bytes_and_rejects_insecure_redirects(self):
        installation = self.root / 'download-installation'
        installation.mkdir()
        namespace = {'__name__': 'installer_test', '__file__': str(installation / 'install-mods.py')}
        exec(compile(release.INSTALLER, 'install-mods.py', 'exec'), namespace)
        contents = b'reviewed original download'
        record = {'path': 'mods/original.jar', 'sha256': hashlib.sha256(contents).hexdigest(),
                  'size': len(contents), 'downloadUrl': 'https://cdn.modrinth.com/original.jar'}
        self.write('download-installation/download-manifest.json', {'files': [record]})
        class Opener:
            payload = contents
            calls = 0
            def open(self, *_args, **_kwargs):
                self.calls += 1
                response = io.BytesIO(self.payload)
                response.url = record['downloadUrl']
                return response
        opener = Opener()
        namespace['build_opener'] = lambda _handler: opener
        with patch.object(sys, 'argv', ['install-mods.py']), patch('sys.stdout', new_callable=io.StringIO):
            namespace['main']()
            namespace['main']()
        self.assertEqual(1, opener.calls)
        target = installation / record['path']
        self.assertEqual(contents, target.read_bytes())
        target.unlink()
        opener.payload = b'corrupt'
        with patch.object(sys, 'argv', ['install-mods.py']):
            with self.assertRaisesRegex(ValueError, 'corrupt'):
                namespace['main']()
        self.assertFalse(target.exists())
        self.assertEqual([], list(target.parent.glob('*.part')))
        with self.assertRaisesRegex(ValueError, 'HTTPS'):
            namespace['HTTPSOnly']().redirect_request(None, None, 302, '', {}, 'http://example.com/file.jar')
        for invalid in ('mods/a\x01.jar', 'mods/CON.jar', 'mods/a\\b.jar'):
            with self.assertRaises(ValueError):
                namespace['target'](installation, invalid)


if __name__ == '__main__':
    unittest.main()
