"""Pruning tests for the source cache carried between release runs."""

from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest

import source_cache


class SourceCachePruneTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='minefed-source-cache-test-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.write('inventory/build-recipes.json', {'entries': [
            {'modId': 'alpha', 'mode': 'source'}, {'modId': 'beta', 'mode': 'source'},
            {'modId': 'gamma', 'mode': 'source'}, {'modId': 'binary', 'mode': 'binary'}]})
        self.enterContext(redirect_stdout(io.StringIO()))

    def write(self, relative, value):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value), encoding='utf-8')
        return path

    def entry(self, key, identity, jar=True):
        directory = self.root / 'build/source-cache' / key
        if jar:
            directory.mkdir(parents=True, exist_ok=True)
            (directory / (identity + '.jar')).write_bytes(b'jar')
        self.write(f'build/source-cache/{key}/result.json', {'modId': identity, 'cacheKey': key})
        return directory

    def receipt(self, identity, key, hit):
        self.write(f'build/modpack-work/run/sources/{identity}/result.json',
                   {'modId': identity, 'cacheKey': key, 'cacheHit': hit})

    def remaining(self):
        return sorted(path.name for path in (self.root / 'build/source-cache').iterdir())

    def test_new_build_replaces_older_entry_and_keeps_unreached_sources(self):
        old, new, other, older_other = 'a' * 64, 'b' * 64, 'c' * 64, 'd' * 64
        for key, identity in ((old, 'alpha'), (new, 'alpha'), (other, 'beta'), (older_other, 'beta')):
            self.entry(key, identity)
        self.receipt('alpha', new, False)
        self.assertTrue(source_cache.prune(self.root))
        self.assertEqual(self.remaining(), [new, other, older_other])

    def test_all_hits_without_stale_entries_do_not_request_a_save(self):
        key = 'a' * 64
        self.entry(key, 'alpha')
        self.receipt('alpha', key, True)
        self.assertFalse(source_cache.prune(self.root))
        self.assertEqual(self.remaining(), [key])

    def test_hit_still_drops_superseded_entry(self):
        current, stale = 'a' * 64, 'b' * 64
        self.entry(current, 'alpha')
        self.entry(stale, 'alpha')
        self.receipt('alpha', current, True)
        self.assertTrue(source_cache.prune(self.root))
        self.assertEqual(self.remaining(), [current])

    def test_incomplete_mismatched_and_retired_entries_are_removed(self):
        partial = self.root / 'build/source-cache' / ('a' * 64)
        partial.mkdir(parents=True)
        (partial / 'alpha.jar').write_bytes(b'partial')
        mismatched = self.entry('b' * 64, 'beta')
        self.write(f'build/source-cache/{mismatched.name}/result.json', {'modId': 'beta', 'cacheKey': 'c' * 64})
        self.entry('d' * 64, 'retired')
        self.entry('e' * 64, 'binary')
        broken = self.root / 'build/source-cache' / ('f' * 64)
        broken.mkdir()
        (broken / 'result.json').write_text('{broken', encoding='utf-8')
        kept = self.entry('0' * 64, 'gamma')
        self.assertTrue(source_cache.prune(self.root))
        self.assertEqual(self.remaining(), [kept.name])

    def test_only_cache_key_directories_are_touched(self):
        other = self.root / 'build/source-cache/notes'
        other.mkdir(parents=True)
        (other / 'result.json').write_text('{}', encoding='utf-8')
        (self.root / 'build/source-cache/readme.txt').write_text('keep', encoding='utf-8')
        self.assertFalse(source_cache.prune(self.root))
        self.assertEqual(self.remaining(), ['notes', 'readme.txt'])

    def test_missing_cache_reports_new_builds(self):
        self.receipt('alpha', 'a' * 64, False)
        self.assertTrue(source_cache.prune(self.root))
        self.assertFalse((self.root / 'build/source-cache').exists())

    def test_github_output_records_the_decision(self):
        output = self.root / 'github-output'
        output.write_text('earlier=value\n', encoding='utf-8')
        original = source_cache.ROOT
        source_cache.ROOT = self.root
        self.addCleanup(setattr, source_cache, 'ROOT', original)
        self.receipt('alpha', 'a' * 64, False)
        self.assertEqual(source_cache.main(['prune', '--github-output', str(output)]), 0)
        self.assertEqual(output.read_text(encoding='utf-8'), 'earlier=value\nchanged=true\n')


if __name__ == '__main__':
    unittest.main()
