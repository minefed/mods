"""Actual compatibility resources, deterministic packaging and committed-source checks."""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import zipfile

import mods
import release_compatibility as compat


class CompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='minefed-compatibility-')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        shutil.copytree(Path(__file__).resolve().parents[1] / compat.SOURCE, self.root / compat.SOURCE)
        for args in [('init', '-q'), ('config', 'core.autocrlf', 'false'),
                     ('config', 'user.name', 'Fixture'), ('config', 'user.email', 'fixture@example.invalid'),
                     ('add', compat.SOURCE), ('commit', '-qm', 'test(compat): add fixture')]:
            subprocess.run(['git', '-C', str(self.root), *args], check=True, capture_output=True)

    def prepare(self, name):
        work = self.root / name
        work.mkdir()
        return compat.prepare(self.root, {'resourceCompatibilityMod': True}, work)[0]

    def test_deterministic_jar_preserves_models_optional_tags_and_licenses(self):
        record, path, entry = self.prepare('one')
        other, second, _ = self.prepare('two')
        self.assertEqual(path.read_bytes(), second.read_bytes())
        self.assertEqual(record['sha256'], other['sha256'])
        mods.check_bytes(path, entry)
        with zipfile.ZipFile(path) as jar:
            self.assertEqual(compat.FILES, set(jar.namelist()))
            self.assertFalse(any(n.endswith(('.png', '.class', '.jar')) for n in jar.namelist()))
            metadata = json.loads(jar.read('fabric.mod.json'))
            # Loader 0.18.4 production resource packs follow lexicographical mod
            # order, not dependency order; the override must follow its target.
            self.assertGreater(metadata['id'], 'mythicmetals_decorations')
            self.assertEqual('*', metadata['environment'])
            self.assertTrue({'diagonalfences', 'mythicmetals_decorations'} <= set(metadata['depends']))
            for kind in ('block', 'item'):
                model = json.loads(jar.read(f'assets/mythicmetals_decorations/models/{kind}/hydrargym_chest.json'))
                self.assertEqual('mythicmetals_decorations:block/hydrargym_block', model['textures']['particle'])
            tag = json.loads(jar.read('data/diagonalfences/tags/blocks/non_diagonal_fences.json'))
            self.assertFalse(tag['replace'])
            self.assertEqual(14, len({v['id'] for v in tag['values']}))
            self.assertTrue(all(v['required'] is False for v in tag['values']))
            self.assertIn(b'Copyright (c) 2021', jar.read('LICENSE'))
            self.assertIn(b'No such textures are included', jar.read('NOTICE.md'))

    def test_dirty_source_cannot_claim_committed_provenance(self):
        (self.root / compat.SOURCE / 'NOTICE.md').write_text('changed')
        with self.assertRaisesRegex(mods.ModError, 'committed source'):
            self.prepare('dirty')

    def test_unreviewed_files_are_rejected(self):
        (self.root / compat.SOURCE / 'texture.png').write_bytes(b'not permitted')
        with self.assertRaisesRegex(mods.ModError, 'exactly the reviewed'):
            self.prepare('extra')

    def test_default_policy_does_not_add_a_mod(self):
        self.assertEqual([], compat.prepare(self.root, {}, self.root))


if __name__ == '__main__':
    unittest.main()
