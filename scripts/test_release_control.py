import contextlib
import io
import json
from pathlib import Path
import subprocess
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

    def test_resource_pack_lock_change_blocks_upload(self):
        lock = self.root / 'inventory/resourcepacks.lock.json'
        lock.write_text('{"clientPacks":[]}')
        self.manifest['resourcePackManifest'] = {'path': 'inventory/resourcepacks.lock.json',
                                                'sha256': mods.file_digest(lock)[0]}
        self.assertEqual(3, len(control.validate_assets(self.root, self.manifest, self.plan)))
        lock.write_text('{"clientPacks":[{"changed":true}]}')
        with self.assertRaisesRegex(mods.ModError, 'Resource pack manifest changed'):
            control.validate_assets(self.root, self.manifest, self.plan)

    def test_observation_mod_requires_unchanged_input_manifest(self):
        policy = self.root / 'inventory/release-policy.json'
        policy.write_text('{"minecraftMcpMod":true}')
        self.manifest['policySha256'] = mods.file_digest(policy)[0]
        with self.assertRaisesRegex(mods.ModError, 'Minecraft MCP manifest changed'):
            control.validate_assets(self.root, self.manifest, self.plan)
        lock = self.root / 'inventory/minecraft-mcp.lock.json'
        lock.write_text('{"version":"0.3.0+minefed.1"}')
        self.manifest['minecraftMcpManifest'] = {'path': 'inventory/minecraft-mcp.lock.json', 'sha256': mods.file_digest(lock)[0]}
        self.assertEqual(3, len(control.validate_assets(self.root, self.manifest, self.plan)))
        lock.write_text('{"version":"changed"}')
        with self.assertRaisesRegex(mods.ModError, 'Minecraft MCP manifest changed'):
            control.validate_assets(self.root, self.manifest, self.plan)

    def test_bundled_release_description_does_not_require_missing_downloads(self):
        self.manifest['archiveMode'] = 'bundled'
        self.manifest['profiles']['server']['pluginCount'] = 1
        body = control.release_body(self.manifest, self.plan, 'c' * 40)
        self.assertIn('모든 모드 JAR 내장', body)
        self.assertIn('추가 모드 다운로드·수동 복원이 필요 없습니다', body)
        self.assertNotIn('다운로드 참조로 제공', body)
        self.assertIn('서버 플러그인 1개는 plugins/에 포함', body)

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

    def prepare_publication_patch(self, *, unrelated=False):
        """Model the separate clean build and publish checkouts with a real Git patch."""
        def git(*args):
            return subprocess.run(['git', '-C', str(self.root), *args], check=True, capture_output=True).stdout

        old_commit, new_commit = '1' * 40, '2' * 40
        lock = self.root / 'inventory/resourcepacks.lock.json'
        lock.write_text(json.dumps({'entries': [{'sourcePath': 'resourcepack', 'commit': old_commit}]}))
        (self.root / '.gitignore').write_text('build/\n')
        (self.root / 'README.md').write_text('Reviewed root input\n')
        (self.root / 'resourcepack').mkdir()
        git('init', '-q')
        git('config', 'user.name', 'Release test')
        git('config', 'user.email', 'release-test@example.invalid')
        git('config', 'core.autocrlf', 'false')
        git('remote', 'add', 'origin', 'https://github.com/minefed/mods.git')
        git('add', '.gitignore', 'README.md', 'inventory')
        git('update-index', '--add', '--cacheinfo', f'160000,{old_commit},resourcepack')
        git('commit', '-qm', 'test(release): create publisher fixture')
        self.plan['rootCommit'] = git('rev-parse', 'HEAD').decode().strip()
        self.plan['sources'] = [{'path': 'resourcepack', 'kind': 'resourcepack', 'commit': new_commit}]
        lock.write_text(json.dumps({'entries': [{'sourcePath': 'resourcepack', 'commit': new_commit}]}))
        self.manifest['resourcePack'] = {'commit': new_commit}
        self.manifest['resourcePackManifest'] = {
            'path': 'inventory/resourcepacks.lock.json', 'sha256': mods.file_digest(lock)[0]}
        git('add', 'inventory/resourcepacks.lock.json')
        git('update-index', '--cacheinfo', f'160000,{new_commit},resourcepack')
        if unrelated:
            (self.root / 'README.md').write_text('Unreviewed root input\n')
            git('add', 'README.md')
        self.patch_path.write_bytes(git('diff', '--cached', '--binary', '--submodule=short'))
        git('reset', '--hard', 'HEAD')
        self.plan_path.write_text(json.dumps(self.plan))
        self.manifest_path.write_text(json.dumps(self.manifest))
        self.assertNotEqual(mods.file_digest(lock)[0], self.manifest['resourcePackManifest']['sha256'])

    @contextlib.contextmanager
    def isolated_publication(self):
        """Run actual local Git operations, but record and block all remote writes."""
        writes = []
        local_git = control.git_with_token

        def git(root, args, **kwargs):
            if args[0] == 'push':
                writes.append(('push', args))
                return ''
            return local_git(root, args, **kwargs)

        def api(method, path, body=None):
            if method != 'GET':
                writes.append((method, path))
            if path == 'repos/minefed/mods':
                return {'private': False, 'default_branch': 'main'}
            if '/releases/tags/' in path or '/git/ref/tags/' in path:
                raise HTTPError(path, 404, 'not found', {}, None)
            if method == 'POST':
                return {'id': 1}
            result = {'assets': [self.remote_asset(a) for a in self.manifest['assets']]}
            if method == 'PATCH':
                result.update(draft=False, html_url='https://github.com/minefed/mods/releases/tag/' + self.plan['version'])
            return result

        def upload(identity, asset, path):
            writes.append(('upload', asset['name']))
            return self.remote_asset(asset)

        with patch.object(control, 'token', return_value='test-token'), \
                patch.object(control, 'github', side_effect=api), \
                patch.object(control, 'git_with_token', side_effect=git), \
                patch.object(control, 'upload_asset', side_effect=upload), contextlib.redirect_stdout(io.StringIO()):
            yield writes

    def test_publish_validates_resource_manifest_after_applying_reviewed_patch(self):
        self.prepare_publication_patch()
        with self.isolated_publication() as writes:
            control.publish(self.root, self.manifest_path, self.plan_path, self.patch_path)
        self.assertEqual(['push', 'POST', 'upload', 'upload', 'upload', 'PATCH'], [kind for kind, _ in writes])
        lock = self.root / 'inventory/resourcepacks.lock.json'
        self.assertEqual(self.manifest['resourcePackManifest']['sha256'], mods.file_digest(lock)[0])

    def test_publish_rejects_tampered_resource_hash_before_remote_writes(self):
        self.prepare_publication_patch()
        self.manifest['resourcePackManifest']['sha256'] = '0' * 64
        self.manifest_path.write_text(json.dumps(self.manifest))
        with self.isolated_publication() as writes:
            with self.assertRaisesRegex(mods.ModError, 'Resource pack manifest changed'):
                control.publish(self.root, self.manifest_path, self.plan_path, self.patch_path)
        self.assertEqual([], writes)

    def test_publish_rejects_tampered_asset_before_remote_writes(self):
        self.prepare_publication_patch()
        asset = self.root / self.manifest['assets'][0]['path']
        asset.write_bytes(asset.read_bytes() + b'tampered')
        with self.isolated_publication() as writes:
            with self.assertRaisesRegex(mods.ModError, 'Release asset SHA-256/size mismatch'):
                control.publish(self.root, self.manifest_path, self.plan_path, self.patch_path)
        self.assertEqual([], writes)

    def test_publish_rejects_unrelated_patch_before_remote_writes(self):
        self.prepare_publication_patch(unrelated=True)
        with self.isolated_publication() as writes:
            with self.assertRaisesRegex(mods.ModError, 'Release pin patch contains unrelated files'):
                control.publish(self.root, self.manifest_path, self.plan_path, self.patch_path)
        self.assertEqual([], writes)


if __name__ == '__main__':
    unittest.main()
