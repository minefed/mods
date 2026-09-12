"""Offline checks for server-only plugin selection, bytes and legal notices."""
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import mods
import release_plugins as plugins


class ServerPluginTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='minefed-plugin-test-')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.work = self.root / 'build/work'
        self.work.mkdir(parents=True)
        self.path = self.root / 'artifacts/local/TCPShield-2.8.1.jar'
        self.path.parent.mkdir(parents=True)
        self.contents = {'plugin.yml': 'name: TCPShield\nversion: 2.8.1\nmain: example.Plugin\n',
                         'bungee.yml': 'name: TCPShield\nversion: 2.8.1\nmain: example.Bungee\n',
                         'velocity-plugin.json': json.dumps({'id': 'tcpshield', 'version': '2.8.1', 'main': 'example.Velocity'}),
                         'LICENSE': 'Retained JAR author copyright\n', 'payload.class': b'fixture'}
        self.entry = {'fileName': self.path.name, 'modId': None, 'version': None, 'environment': None,
                      'included': False, 'exclusionReason': 'Non-Fabric plugin', 'management': 'binary', 'source': None,
                      'artifact': {'path': self.path.relative_to(self.root).as_posix(), 'redistribution': 'allowed',
                                   'url': 'https://github.com/TCPShield/RealIP/releases/download/2.8.1/TCPShield-2.8.1.jar'},
                      'license': 'MIT', 'licenseUrl': 'https://github.com/TCPShield/RealIP/blob/2.8.1/LICENSE',
                      'notes': ['Server plugin fixture'], 'authors': ['TCPShield']}
        self.notice = self.root / 'inventory/notices/tcpshield/LICENSE'
        self.notice.parent.mkdir(parents=True)
        self.notice.write_bytes(b'MIT License\nCopyright (c) 2020 TCPShield\n')
        self.policy = {'serverPlugins': [{'fileName': self.path.name, 'reason': 'Reviewed server plugin',
                       'evidenceUrls': [self.entry['licenseUrl']],
                       'noticePaths': [self.notice.relative_to(self.root).as_posix()]}]}
        self.write_jar()

    def write_manifest(self):
        target = self.root / 'inventory/mods.lock.json'
        target.write_text(json.dumps({'schemaVersion': 1, 'minecraftVersion': '1.20.4', 'loader': 'fabric',
                                      'entries': [self.entry]}), encoding='utf-8')

    def write_jar(self):
        with zipfile.ZipFile(self.path, 'w') as archive:
            for name, content in self.contents.items():
                archive.writestr(name, content)
        self.entry['sha256'], self.entry['size'] = mods.file_digest(self.path)
        self.write_manifest()

    def prepare(self):
        return plugins.prepare(self.root, self.policy, self.work)

    def test_exact_bytes_descriptors_and_author_notices_are_preserved(self):
        before = self.path.read_bytes()
        selected, notices = self.prepare()
        self.assertEqual(1, len(selected))
        record, path, entry = selected[0]
        self.assertEqual(before, path.read_bytes())
        self.assertEqual(self.entry, entry)
        self.assertEqual(('plugins/TCPShield-2.8.1.jar', '2.8.1', True, False),
                         (record['path'], record['version'], record['server'], record['client']))
        self.assertEqual((self.entry['sha256'], len(before)), (record['sha256'], record['size']))
        self.assertNotIn('modId', record)
        self.assertEqual(['TCPShield'], record['authors'])
        self.assertEqual(self.notice.read_bytes(), notices[record['noticePaths'][0]])
        self.assertIn(b'Retained JAR author copyright\n', notices.values())

    def test_no_plugins_does_not_require_a_baseline(self):
        self.assertEqual(([], {}), plugins.prepare(self.root / 'absent', {}, self.work))

    def test_absent_local_plugin_is_downloaded_only_to_staging(self):
        contents = self.path.read_bytes()
        self.path.unlink()
        response = io.BytesIO(contents)
        response.url = self.entry['artifact']['url']
        with patch.object(mods, 'download', return_value=response) as download:
            selected, _ = self.prepare()
        download.assert_called_once_with(self.entry['artifact']['url'])
        self.assertFalse(self.path.exists())
        self.assertEqual(contents, selected[0][1].read_bytes())
        self.assertTrue(selected[0][1].is_relative_to(self.work))

    def test_existing_corrupt_plugin_is_not_replaced_or_downloaded(self):
        self.path.write_bytes(b'local modifications')
        with patch.object(mods, 'download') as download:
            with self.assertRaisesRegex(mods.ModError, 'SHA-256 mismatch'):
                self.prepare()
        download.assert_not_called()
        self.assertEqual(b'local modifications', self.path.read_bytes())

    def test_corrupt_and_oversized_downloads_are_rejected(self):
        self.path.unlink()
        for content in (b'corrupt', b'x' * (self.entry['size'] + 1)):
            with self.subTest(size=len(content)):
                with tempfile.TemporaryDirectory(dir=self.work) as attempt:
                    response = io.BytesIO(content)
                    response.url = self.entry['artifact']['url']
                    with patch.object(mods, 'download', return_value=response):
                        with self.assertRaisesRegex(mods.ModError, 'SHA-256 mismatch|exceeds recorded'):
                            plugins.prepare(self.root, self.policy, Path(attempt))

    def test_nonplugin_and_fabric_jars_are_rejected_even_with_valid_hash(self):
        for contents in ({'payload.bin': 'not a plugin'},
                         {'fabric.mod.json': '{}', **self.contents}):
            with self.subTest(contents=list(contents)):
                self.contents = contents
                self.write_jar()
                with self.assertRaises(mods.ModError):
                    self.prepare()

    def test_included_baseline_local_only_and_unreviewed_urls_are_rejected(self):
        original = copy.deepcopy(self.entry)
        for mutate in (lambda e: e.update(included=True),
                       lambda e: e.update(modId='pretend-mod'),
                       lambda e: e['artifact'].update(redistribution='local-only'),
                       lambda e: e['artifact'].update(url='http://example.com/plugin.jar')):
            self.entry = copy.deepcopy(original)
            mutate(self.entry)
            self.write_manifest()
            with self.assertRaises(mods.ModError):
                self.prepare()

    def test_unsafe_duplicate_and_non_notice_paths_are_rejected(self):
        original = copy.deepcopy(self.policy)
        mutations = (lambda p: p['serverPlugins'][0].update(fileName='../plugin.jar'),
                     lambda p: p['serverPlugins'][0].update(noticePaths=['../LICENSE']),
                     lambda p: p['serverPlugins'][0].update(noticePaths=['inventory/mods.lock.json']),
                     lambda p: p['serverPlugins'][0].update(noticePaths=[]),
                     lambda p: p['serverPlugins'].append(copy.deepcopy(p['serverPlugins'][0])))
        for mutate in mutations:
            self.policy = copy.deepcopy(original)
            mutate(self.policy)
            with self.assertRaises(mods.ModError):
                self.prepare()

    def test_zip_traversal_link_and_duplicate_names_are_rejected(self):
        for invalid in ('../outside.class', 'META-INF/../../escape.class'):
            self.contents[invalid] = b'unsafe'
            self.write_jar()
            with self.assertRaises(mods.ModError):
                self.prepare()
            del self.contents[invalid]
        with zipfile.ZipFile(self.path, 'w') as archive:
            for name, content in self.contents.items():
                archive.writestr(name, content)
            linked = zipfile.ZipInfo('linked.class')
            linked.external_attr = 0o120777 << 16
            archive.writestr(linked, 'payload.class')
        self.entry['sha256'], self.entry['size'] = mods.file_digest(self.path)
        self.write_manifest()
        with self.assertRaisesRegex(mods.ModError, 'linked'):
            self.prepare()
        self.contents['PLUGIN.YML'] = self.contents['plugin.yml']
        self.write_jar()
        with self.assertRaisesRegex(mods.ModError, 'Duplicate'):
            self.prepare()

    def test_descriptor_version_conflict_and_binary_notice_are_rejected(self):
        self.contents['bungee.yml'] = 'name: TCPShield\nversion: 3.0\nmain: example.Bungee\n'
        self.write_jar()
        with self.assertRaisesRegex(mods.ModError, 'Conflicting'):
            self.prepare()
        self.notice.write_bytes(b'not\x00text')
        with self.assertRaisesRegex(mods.ModError, 'text'):
            self.prepare()


if __name__ == '__main__':
    unittest.main()
