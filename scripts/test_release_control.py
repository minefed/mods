import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
import zipfile

import mods
import release_control as control


class ReleaseControlTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        policy = self.root / 'inventory/release-policy.json'
        policy.parent.mkdir()
        policy.write_text('{}\n')
        self.plan = {'version': '20260907150000', 'fingerprint': 'a' * 64,
                     'rootCommit': 'b' * 40, 'sources': []}
        self.manifest = {'schemaVersion': 1, 'version': self.plan['version'],
                         'policySha256': mods.file_digest(policy)[0], 'assets': [],
                         'profiles': {'server': {'modCount': 68}, 'client': {'modCount': 66}}}
        for kind, name, media in [('server', 'server.zip', 'application/zip'),
                                  ('client', 'client.mrpack', 'application/x-modrinth-modpack+zip'),
                                  ('resourcepack', 'resourcepack.zip', 'application/zip')]:
            path = self.root / 'build/releases' / self.plan['version'] / name
            path.parent.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(path, 'w') as archive:
                archive.writestr('readme.txt', kind)
            digest, size = mods.file_digest(path)
            self.manifest['assets'].append({'kind': kind, 'name': name, 'mediaType': media,
                                           'path': path.relative_to(self.root).as_posix(), 'sha256': digest, 'size': size})
        self.manifest_path = self.root / 'build/release-assets.json'
        self.plan_path = self.root / 'build/release-plan.json'
        self.patch_path = self.root / 'build/release-inputs.patch'
        self.manifest_path.write_text(json.dumps(self.manifest))
        self.plan_path.write_text(json.dumps(self.plan))
        self.patch_path.write_bytes(b'')

    def test_requires_three_unmodified_version_scoped_assets(self):
        self.assertEqual(3, len(control.validate_assets(self.root, self.manifest, self.plan)))
        self.manifest['assets'][0]['path'] = '../server.zip'
        with self.assertRaises(mods.ModError):
            control.validate_assets(self.root, self.manifest, self.plan)
        self.manifest = json.loads(self.manifest_path.read_text())
        self.manifest['assets'].pop()
        with self.assertRaises(mods.ModError):
            control.validate_assets(self.root, self.manifest, self.plan)
        self.manifest = json.loads(self.manifest_path.read_text())
        artifact = self.root / self.manifest['assets'][0]['path']
        artifact.write_bytes(artifact.read_bytes() + b'tampered')
        with self.assertRaises(mods.ModError):
            control.validate_assets(self.root, self.manifest, self.plan)

    def test_policy_change_blocks_upload(self):
        (self.root / 'inventory/release-policy.json').write_text('{"changed":true}')
        with self.assertRaisesRegex(mods.ModError, 'policy changed'):
            control.validate_assets(self.root, self.manifest, self.plan)

    def test_bundled_release_description_does_not_require_missing_downloads(self):
        self.manifest['archiveMode'] = 'bundled'
        body = control.release_body(self.manifest, self.plan, 'c' * 40)
        self.assertIn('모든 모드 JAR 내장', body)
        self.assertIn('추가 모드 다운로드·수동 복원이 필요 없습니다', body)
        self.assertNotIn('다운로드 참조로 제공', body)

    def test_published_manifest_change_or_missing_snapshot_blocks_upload(self):
        relative = 'inventory/published-artifacts.lock.json'
        lock = self.root / relative
        lock.write_text('{"reviewed":"official binaries"}\n')
        policy = self.root / 'inventory/release-policy.json'
        policy.write_text(json.dumps({'publishedManifest': relative}))
        self.manifest['policySha256'] = mods.file_digest(policy)[0]
        self.manifest['publishedManifest'] = {'path': relative, 'sha256': mods.file_digest(lock)[0]}
        self.assertEqual(3, len(control.validate_assets(self.root, self.manifest, self.plan)))
        snapshot = self.manifest.pop('publishedManifest')
        with self.assertRaisesRegex(mods.ModError, 'manifest reference differs'):
            control.validate_assets(self.root, self.manifest, self.plan)
        self.manifest['publishedManifest'] = {**snapshot, 'path': 'inventory/wrong.json'}
        with self.assertRaisesRegex(mods.ModError, 'manifest reference differs'):
            control.validate_assets(self.root, self.manifest, self.plan)
        self.manifest['publishedManifest'] = snapshot
        lock.write_text('{"changed":true}')
        with self.assertRaisesRegex(mods.ModError, 'manifest changed'):
            control.validate_assets(self.root, self.manifest, self.plan)

    def test_bootstrap_restores_only_exact_hashed_original(self):
        meta = {'schemaVersion': 1, 'id': 'example', 'version': '1.0', 'environment': '*'}
        jar = self.root / 'original.jar'
        with zipfile.ZipFile(jar, 'w') as archive:
            archive.writestr('fabric.mod.json', json.dumps(meta))
        digest, size = mods.file_digest(jar)
        entry = {'modId': 'example', 'fileName': 'original.jar', 'version': '1.0', 'environment': '*',
                 'sha256': digest, 'size': size, 'artifact': {'path': 'vendor/local/original.jar'}}
        pack = self.root / 'client.mrpack'
        with zipfile.ZipFile(pack, 'w') as archive:
            archive.write(jar, 'overrides/mods/original.jar')
            archive.writestr('../../unwanted.txt', 'not extracted')
        control.restore_embedded(self.root, pack, [entry])
        self.assertEqual(jar.read_bytes(), (self.root / entry['artifact']['path']).read_bytes())
        self.assertFalse((self.root / 'unwanted.txt').exists())
        (self.root / entry['artifact']['path']).write_bytes(b'local edits')
        with self.assertRaises(mods.ModError):
            control.restore_embedded(self.root, pack, [entry])
        self.assertEqual(b'local edits', (self.root / entry['artifact']['path']).read_bytes())

    def bootstrap_fixture(self, override=True):
        entry = {'modId': 'ptsdeco', 'fileName': 'historical.jar', 'version': '1.0', 'environment': '*',
                 'sha256': '1' * 64, 'size': 1, 'included': True, 'management': 'binary', 'source': None,
                 'artifact': {'path': 'artifacts/local/historical.jar', 'url': None, 'redistribution': 'allowed'}}
        manifest = {'schemaVersion': 1, 'minecraftVersion': '1.20.4', 'loader': 'fabric', 'entries': [entry]}
        recipes = {'schemaVersion': 1, 'minecraftVersion': '1.20.4', 'loader': 'fabric',
                   'entries': [{'modId': 'ptsdeco', 'mode': 'binary', 'reason': 'Reviewed runtime input'}]}
        (self.root / 'inventory/mods.lock.json').write_text(json.dumps(manifest))
        if override:
            recipes['dependencyManifest'] = 'inventory/dependencies.lock.json'
            recipes['entries'][0]['dependency'] = True
            updated = {**entry, 'fileName': 'official.jar', 'version': '2.0',
                       'artifact': {'path': 'artifacts/local/official.jar', 'redistribution': 'allowed',
                                    'url': 'https://cdn.modrinth.com/official.jar'}}
            (self.root / recipes['dependencyManifest']).write_text(json.dumps({**manifest, 'entries': [updated]}))
        (self.root / 'inventory/build-recipes.json').write_text(json.dumps(recipes))
        policy = {'entries': [{'modId': 'ptsdeco', 'distribution': 'embed', 'artifact': 'built' if override else 'baseline'}]}
        (self.root / 'inventory/release-policy.json').write_text(json.dumps(policy))

    def test_bootstrap_skips_unavailable_baseline_replaced_by_downloadable_dependency(self):
        self.bootstrap_fixture()
        original = (self.root / 'inventory/mods.lock.json').read_bytes()
        with patch.object(control, 'github') as github, patch.object(mods, 'download') as download, \
                contextlib.redirect_stdout(io.StringIO()):
            control.bootstrap(self.root)
        github.assert_not_called()
        download.assert_not_called()  # The build prepare phase hydrates this official JAR.
        self.assertEqual(original, (self.root / 'inventory/mods.lock.json').read_bytes())
        self.assertFalse((self.root / 'artifacts/local/historical.jar').exists())

    def test_bootstrap_keeps_manual_original_requirement_and_rejects_missing_override(self):
        self.bootstrap_fixture(override=False)
        with patch.object(control, 'github', side_effect=HTTPError('fixture', 404, 'not found', {}, None)) as github:
            with self.assertRaisesRegex(mods.ModError, 'first release must be built from the local verified JAR'):
                control.bootstrap(self.root)
        github.assert_called_once()
        self.bootstrap_fixture()
        (self.root / 'inventory/dependencies.lock.json').unlink()
        with patch.object(control, 'github') as github:
            with self.assertRaisesRegex(mods.ModError, 'Cannot read manifest'):
                control.bootstrap(self.root)
        github.assert_not_called()

    def remote_asset(self, asset):
        return {'name': asset['name'], 'state': 'uploaded', 'size': asset['size'], 'digest': 'sha256:' + asset['sha256']}

    def test_remote_digest_is_required(self):
        asset = self.manifest['assets'][0]
        control.verify_remote_asset(self.remote_asset(asset), asset)
        value = self.remote_asset(asset)
        value.pop('digest')
        with self.assertRaises(mods.ModError):
            control.verify_remote_asset(value, asset)

    def run_publication(self, fail_upload=False, existing=False):
        calls = []
        def api(method, path, body=None):
            calls.append((method, path, body))
            if path == 'repos/minefed/mods':
                return {'private': False, 'default_branch': 'main'}
            if '/releases/tags/' in path or '/git/ref/tags/' in path:
                if existing:
                    return {'exists': True}
                raise HTTPError(path, 404, 'not found', {}, None)
            if method == 'POST':
                self.assertTrue(body['draft'])
                return {'id': 1}
            remote = {'assets': [self.remote_asset(a) for a in self.manifest['assets']]}
            if method == 'PATCH':
                remote.update(draft=False, html_url='https://github.com/minefed/mods/releases/tag/' + self.plan['version'])
            return remote
        def upload(identity, asset, path):
            if fail_upload and asset['kind'] == 'client':
                raise mods.ModError('upload failure')
            return self.remote_asset(asset)
        with patch.object(control, 'token', return_value='test-token'), patch.object(control, 'github', side_effect=api), \
                patch.object(control, 'release_commit', return_value='b' * 40), \
                patch.object(control, 'git_with_token') as push, \
                patch.object(mods, 'git', return_value='https://github.com/minefed/mods'), \
                patch.object(control, 'upload_asset', side_effect=upload), contextlib.redirect_stdout(io.StringIO()):
            if fail_upload or existing:
                with self.assertRaises(mods.ModError):
                    control.publish(self.root, self.manifest_path, self.plan_path, self.patch_path)
                self.assertFalse(any(method == 'PATCH' for method, _, _ in calls))
                if existing:
                    push.assert_not_called()
            else:
                control.publish(self.root, self.manifest_path, self.plan_path, self.patch_path)
                self.assertEqual(1, sum(method == 'PATCH' for method, _, _ in calls))
                push.assert_called_once()

    def test_failed_second_upload_leaves_draft(self):
        self.run_publication(fail_upload=True)

    def test_existing_tag_is_not_overwritten(self):
        self.run_publication(existing=True)

    def test_three_verified_assets_are_published_together(self):
        self.run_publication()


if __name__ == '__main__':
    unittest.main()
