"""Offline release planning/materialization tests using real temporary Git repos."""

import base64
from contextlib import ExitStack
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

import release_inputs as ri


def run(root, *args):
    result = subprocess.run(['git', '-c', 'protocol.file.allow=always', '-C', str(root), *args],
                            capture_output=True, text=True, encoding='utf-8', check=True)
    return result.stdout.strip()


def init(path):
    path.mkdir()
    run(path, 'init', '-b', 'main')
    run(path, 'config', 'user.name', 'Release fixture')
    run(path, 'config', 'user.email', 'fixture@example.invalid')
    run(path, 'config', 'core.autocrlf', 'false')


def commit(path, message='test: fixture'):
    run(path, 'add', '--all')
    run(path, 'commit', '-m', message)
    return run(path, 'rev-parse', 'HEAD')


class VersionTests(unittest.TestCase):
    def test_clock_rollback_and_same_second_never_reuse_a_tag(self):
        now = datetime(2026, 9, 7, 10, 0, 0, tzinfo=ri.KST)
        self.assertEqual(ri.next_version(['20260907100000'], now), '20260907100001')
        self.assertEqual(ri.next_version(['20260908100000', 'v1.2'], now), '20260908100001')

    def test_invalid_timestamp_tag_fails_instead_of_ignoring_collision(self):
        with self.assertRaises(ri.InputError):
            ri.next_version(['20261399999999'])

    def test_release_marker_validates_and_rejects_ambiguous_state(self):
        state = {'fingerprint': 'a' * 64}
        marker = '<!-- minefed-state:' + base64.b64encode(json.dumps(state).encode()).decode() + ' -->'
        self.assertEqual(ri.release_state(marker), state)
        self.assertIsNone(ri.release_state('An unrelated release'))
        for invalid in (marker + marker, '<!-- minefed-state:e30= -->'):
            with self.subTest(invalid=invalid), self.assertRaises(ri.InputError):
                ri.release_state(invalid)

    def test_source_or_root_change_changes_fingerprint(self):
        source = {'path': 'mod', 'url': 'https://github.com/minefed/mod', 'ref': 'main', 'kind': 'mod', 'commit': 'b' * 40}
        old = ri.fingerprint('a' * 40, [source])
        self.assertNotEqual(old, ri.fingerprint('c' * 40, [source]))
        self.assertNotEqual(old, ri.fingerprint('a' * 40, [{**source, 'commit': 'd' * 40}]))

    def test_external_urls_and_paths_are_rejected(self):
        for url in ('https://github.com/outsider/mod', 'file:///repo', 'https://github.com/minefed/mod?x=1', 'git@github.com:minefed/mod'):
            with self.subTest(url=url), self.assertRaises(ri.InputError):
                ri.repository_name(url)
        with tempfile.TemporaryDirectory() as temp:
            for path in ('../outside', '/absolute', 'x\\..\\other', ''):
                with self.subTest(path=path), self.assertRaises(ri.InputError):
                    ri.local_path(Path(temp), path)


class GitFixtureTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / 'root'
        init(self.root)
        (self.root / '.gitignore').write_text('build/\n', encoding='utf-8')
        run(self.root, 'remote', 'add', 'origin', 'https://github.com/minefed/mods')
        self.remotes = {}
        self.initial = {}
        for name in ('mod', 'resourcepack'):
            upstream = self.base / ('upstream-' + name)
            init(upstream)
            (upstream / 'LICENSE').write_bytes(b'MIT fixture\n')
            (upstream / 'README.md').write_text('Fixture permission and instructions\n', encoding='utf-8')
            (upstream / 'source.txt').write_text('initial code\n', encoding='utf-8')
            self.initial[name] = commit(upstream)
            run(self.root, 'submodule', 'add', str(upstream), name)
            run(self.root, 'config', '-f', '.gitmodules', 'submodule.' + name + '.url', 'https://github.com/minefed/' + name)
            run(self.root, 'config', '-f', '.gitmodules', 'submodule.' + name + '.branch', 'main')
            self.remotes['https://github.com/minefed/' + name] = upstream
        ri.write_json(self.root / 'inventory/mods.lock.json', {'entries': [
            {'modId': 'fixture', 'included': True, 'fileName': 'original.jar', 'version': '1.0', 'sha256': '1' * 64, 'size': 123,
             'source': {'path': 'mod', 'url': 'https://github.com/minefed/mod', 'ref': 'main', 'commit': self.initial['mod'],
                        'baselineCommit': self.initial['mod'], 'baselineRef': '1.0'}}],
            'sourceRepositories': [{'path': 'resourcepack', 'commit': self.initial['resourcepack']}]})
        ri.write_json(self.root / 'inventory/resourcepacks.lock.json', {'entries': [
            {'id': 'pack', 'sourcePath': 'resourcepack', 'commit': self.initial['resourcepack'],
             'sourceDir': 'game', 'baselineCommit': self.initial['resourcepack']}]})
        ri.write_json(self.root / 'inventory/build-recipes.json', {'entries': [
            {'modId': 'fixture', 'mode': 'source', 'sourcePath': 'mod', 'expectedVersion': '1.0',
             'artifactGlobs': ['build/libs/fixture-1.0-fabric.jar'], 'tasks': ['remapJar'], 'java': 17}]})
        ri.write_json(self.root / ri.INPUTS, {'schemaVersion': 1, 'entries': [
            {'modId': 'fixture', 'sourcePath': 'mod', 'releaseGlobs': ['build/libs/fixture-*-fabric.jar']}],
            'sources': [{'path': name, 'licenseFiles': ri.license_files(self.root / name, sha),
                         'nestedGitlinks': ri.nested_gitlinks(self.root / name, sha)} for name, sha in self.initial.items()]})
        self.root_commit = commit(self.root)
        self.raw_git = ri.git
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(ri, 'git', side_effect=self.local_git))
        self.releases = []
        self.stack.enter_context(patch.object(ri, 'github', side_effect=self.fake_github))
        self.stack.enter_context(patch.dict(os.environ, {'GITHUB_OUTPUT': str(self.base / 'outputs')}))

    def local_git(self, root, *args, binary=False):
        if args[:2] == ('ls-remote', '--tags'):
            return ''
        if args[:2] == ('ls-remote', '--exit-code'):
            upstream = self.remotes[args[2]]
            return run(upstream, 'rev-parse', 'HEAD') + '\t' + args[3]
        if args[:2] == ('fetch', '--no-tags'):
            args = (*args[:2], str(self.remotes[args[2]]), *args[3:])
        return self.raw_git(root, *args, binary=binary)

    def fake_github(self, method, path, body=None):
        if path.endswith('/latest'):
            published = [e for e in self.releases if not e.get('draft') and e.get('published_at')]
            if not published:
                raise HTTPError(path, 404, 'No published release', {}, None)
            return published[0]
        return self.releases

    def advance(self, name='mod', filename='source.txt', text='new code\n'):
        source = self.remotes['https://github.com/minefed/' + name]
        (source / filename).write_text(text, encoding='utf-8')
        return commit(source, 'fix: update fixture')

    def planned(self):
        return ri.plan(self.root, 'build/plan.json')

    def test_plan_uses_last_published_state_and_reserves_draft_timestamp(self):
        first = self.planned()
        marker = '<!-- minefed-state:' + base64.b64encode(json.dumps({'fingerprint': first['fingerprint']}).encode()).decode() + ' -->'
        self.releases = [{'draft': True, 'tag_name': '20990101000000', 'body': ''},
                         {'draft': False, 'tag_name': first['version'], 'published_at': '2026-09-07T00:00:00Z', 'body': marker}]
        second = self.planned()
        self.assertFalse(second['changed'])
        self.assertEqual(second['version'], '20990101000001')
        self.assertIn('changed=false', (self.base / 'outputs').read_text())
        self.advance()
        self.assertTrue(self.planned()['changed'])

    def test_plan_observes_root_changes_and_rejects_dirty_children(self):
        first = self.planned()
        (self.root / 'new-root.txt').write_text('root build settings')
        commit(self.root)
        self.assertNotEqual(first['fingerprint'], self.planned()['fingerprint'])
        (self.root / 'mod/source.txt').write_text('local edit')
        with self.assertRaises(ri.InputError):
            self.planned()

    def test_force_rebuild_keeps_verified_inputs_and_reserves_a_new_version(self):
        first = self.planned()
        marker = '<!-- minefed-state:' + base64.b64encode(json.dumps({'fingerprint': first['fingerprint']}).encode()).decode() + ' -->'
        self.releases = [{'draft': False, 'tag_name': '20990101000000',
                          'published_at': '2026-09-07T00:00:00Z', 'body': marker}]
        self.assertFalse(self.planned()['changed'])
        forced = ri.plan(self.root, 'build/forced.json', force=True)
        self.assertTrue(forced['changed'])
        self.assertTrue(forced['force'])
        self.assertEqual(forced['fingerprint'], first['fingerprint'])
        self.assertEqual(forced['sources'], first['sources'])
        self.assertEqual(forced['rootCommit'], first['rootCommit'])
        self.assertEqual(forced['version'], '20990101000001')
        (self.root / 'mod/source.txt').write_text('local edit')
        with self.assertRaises(ri.InputError):
            ri.plan(self.root, 'build/forced.json', force=True)

    def test_materialize_updates_gitlinks_only_and_preserves_operational_fields(self):
        new_mod = self.advance()
        new_pack = self.advance('resourcepack', text='private source must not be emitted\n')
        value = self.planned()
        old = ri.read_json(self.root, 'inventory/mods.lock.json')
        result = ri.materialize(self.root, 'build/plan.json')
        new = ri.read_json(self.root, 'inventory/mods.lock.json')
        expected = json.loads(json.dumps(old))
        expected['entries'][0]['source']['commit'] = new_mod
        expected['sourceRepositories'][0]['commit'] = new_pack
        self.assertEqual(new, expected)
        self.assertEqual(run(self.root, 'rev-parse', 'HEAD'), self.root_commit)
        self.assertEqual(run(self.root / 'mod', 'rev-parse', 'HEAD'), new_mod)
        self.assertEqual(run(self.root / 'resourcepack', 'rev-parse', 'HEAD'), new_pack)
        self.assertEqual(run(self.root / 'mod', 'branch', '--show-current'), '')
        recipe = ri.read_json(self.root, 'inventory/build-recipes.json')['entries'][0]
        self.assertNotIn('expectedVersion', recipe)
        self.assertEqual(recipe['artifactGlobs'], ['build/libs/fixture-*-fabric.jar'])
        patch_text = Path(result['patch']).read_text()
        self.assertIn('Subproject commit ' + new_pack, patch_text)
        self.assertNotIn('private source must not be emitted', patch_text)
        self.assertNotIn('new code', patch_text)
        # The staged patch can reconstruct the planned inventories and gitlinks.
        run(self.root, 'reset', '--hard', self.root_commit)
        run(self.root, 'apply', '--index', result['patch'])
        self.assertEqual(ri.read_json(self.root, 'inventory/mods.lock.json'), expected)

    def test_unchanged_source_keeps_exact_recipe_version(self):
        self.planned()
        ri.materialize(self.root, 'build/plan.json')
        self.assertEqual(ri.read_json(self.root, 'inventory/build-recipes.json')['entries'][0]['expectedVersion'], '1.0')

    def test_changed_license_fails_before_pin_or_inventory_edits(self):
        self.advance(filename='LICENSE', text='All Rights Reserved\n')
        self.planned()
        with self.assertRaisesRegex(ri.InputError, 'review required'):
            ri.materialize(self.root, 'build/plan.json')
        self.assertEqual(run(self.root / 'mod', 'rev-parse', 'HEAD'), self.initial['mod'])
        self.assertFalse(run(self.root, 'status', '--porcelain'))
        self.assertFalse((self.root / 'build/release-inputs.patch').exists())

    def test_added_and_removed_license_evidence_are_detected(self):
        source = self.remotes['https://github.com/minefed/mod']
        original = ri.license_files(source, self.initial['mod'])
        new = self.advance(filename='NOTICE-new.txt', text='New required attribution\n')
        with self.assertRaises(ri.InputError):
            ri.check_licenses(source, new, original)
        (source / 'NOTICE-new.txt').unlink()
        (source / 'LICENSE').unlink()
        removed = commit(source)
        with self.assertRaises(ri.InputError):
            ri.check_licenses(source, removed, original)

    def test_license_hash_uses_git_blob_not_checkout_line_endings(self):
        expected = ri.license_files(self.root / 'mod', self.initial['mod'])
        (self.root / 'mod/LICENSE').write_bytes(b'MIT fixture\r\n')
        self.assertEqual(expected['LICENSE'], hashlib.sha256(b'MIT fixture\n').hexdigest())
        self.assertEqual(expected, ri.license_files(self.root / 'mod', self.initial['mod']))

    def test_nested_dependency_updates_require_review_before_checkout(self):
        source = self.remotes['https://github.com/minefed/mod']
        run(source, 'update-index', '--add', '--cacheinfo', '160000,' + self.initial['mod'] + ',nested')
        run(source, 'commit', '-m', 'test: add nested dependency')
        nested_commit = run(source, 'rev-parse', 'HEAD')
        self.planned()
        with self.assertRaisesRegex(ri.InputError, 'Nested source changed; review required'):
            ri.materialize(self.root, 'build/plan.json')
        self.assertEqual(run(self.root / 'mod', 'rev-parse', 'HEAD'), self.initial['mod'])
        self.assertFalse(run(self.root, 'status', '--porcelain'))
        original = ri.nested_gitlinks(source, nested_commit)
        self.assertEqual(original, {'nested': self.initial['mod']})
        ri.check_nested_sources(source, nested_commit, original)
        run(source, 'update-index', '--cacheinfo', '160000,' + nested_commit + ',nested')
        run(source, 'commit', '-m', 'test: update nested dependency')
        with self.assertRaises(ri.InputError):
            ri.check_nested_sources(source, run(source, 'rev-parse', 'HEAD'), original)
        run(source, 'update-index', '--force-remove', 'nested')
        run(source, 'commit', '-m', 'test: remove nested dependency')
        with self.assertRaises(ri.InputError):
            ri.check_nested_sources(source, run(source, 'rev-parse', 'HEAD'), original)

    def test_tampered_plan_and_changed_root_are_rejected(self):
        value = self.planned()
        value['sources'][0]['commit'] = 'f' * 40
        ri.write_json(self.root / 'build/plan.json', value)
        with self.assertRaisesRegex(ri.InputError, 'fingerprint'):
            ri.materialize(self.root, 'build/plan.json')
        self.planned()
        (self.root / 'root-change').write_text('new')
        commit(self.root)
        with self.assertRaisesRegex(ri.InputError, 'Root HEAD'):
            ri.materialize(self.root, 'build/plan.json')

    def test_force_rewritten_remote_cannot_replace_planned_commit(self):
        self.planned()
        upstream = self.remotes['https://github.com/minefed/mod']
        run(upstream, 'checkout', '--orphan', 'replacement')
        commit(upstream, 'test: unrelated history')
        run(upstream, 'branch', '-M', 'main')
        with self.assertRaises(ri.InputError):
            ri.materialize(self.root, 'build/plan.json')
        self.assertFalse(run(self.root, 'status', '--porcelain'))


class RepositoryInputsTests(unittest.TestCase):
    def test_reviewed_globs_cover_source_recipes_and_match_current_artifacts(self):
        import fnmatch
        root = Path(__file__).resolve().parents[1]
        recipes = {e['modId']: e for e in ri.read_json(root, 'inventory/build-recipes.json')['entries'] if e['mode'] == 'source'}
        entries = ri.read_json(root, ri.INPUTS)['entries']
        self.assertEqual(set(recipes), {e['modId'] for e in entries})
        self.assertEqual(len(entries), 53)
        for entry in entries:
            recipe = recipes[entry['modId']]
            self.assertEqual(recipe['sourcePath'], entry['sourcePath'])
            for old in recipe['artifactGlobs']:
                # Existing Git-version globs stand for an actual abbreviation.
                representative = old.replace('*', 'abcdef0')
                self.assertTrue(any(fnmatch.fnmatchcase(representative, new) for new in entry['releaseGlobs']), (entry['modId'], old))


if __name__ == '__main__':
    unittest.main()
