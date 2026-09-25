import json
from pathlib import Path
import tempfile
import unittest
import zipfile
import io

import audit_pack_resources as audit


class ResourcePackagingTests(unittest.TestCase):
    def baseline_fixture(self):
        entry = {'modId': 'doors', 'version': '1.0.0', 'environment': '*', 'sha256': 'a' * 64,
                 'artifact': {'path': 'artifacts/local/doors.jar'}}
        row = {'modId': 'doors', 'sha256': entry['sha256'],
               'families': {'assets/doors/models': 3}, 'classCount': 2}
        return entry, row

    def test_ci_uses_hash_bound_evidence_without_historical_jar(self):
        entry, row = self.baseline_fixture()
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'inventory').mkdir()
            (root / audit.BASELINE).write_text(json.dumps({'schemaVersion': 1, 'entries': [row]}))
            baseline = audit.baseline_summary(root, entry, audit.load_baselines(root))
            self.assertEqual(audit.lost_families({'families': {}, 'classCount': 2}, baseline),
                             ['assets/doors/models'])

    def test_missing_or_wrong_hash_evidence_is_not_silently_skipped(self):
        entry, row = self.baseline_fixture()
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(audit.mods.ModError):
                audit.baseline_summary(Path(folder), entry, {})
            row['sha256'] = 'b' * 64
            with self.assertRaises(audit.mods.ModError):
                audit.baseline_summary(Path(folder), entry, {'doors': row})

    def test_duplicate_baseline_evidence_is_rejected(self):
        _, row = self.baseline_fixture()
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'inventory').mkdir()
            (root / audit.BASELINE).write_text(json.dumps({'schemaVersion': 1, 'entries': [row, row]}))
            with self.assertRaises(audit.mods.ModError):
                audit.load_baselines(root)

    def test_local_original_cross_checks_the_snapshot(self):
        entry, row = self.baseline_fixture()
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            path = root / entry['artifact']['path']
            path.parent.mkdir(parents=True)
            with zipfile.ZipFile(path, 'w') as archive:
                archive.writestr('fabric.mod.json', json.dumps({'id': 'doors', 'version': '1.0.0'}))
                archive.writestr('assets/doors/models/door.json', '{}')
            entry['sha256'], entry['size'] = audit.mods.file_digest(path)
            entry['fileName'] = path.name
            row['sha256'] = entry['sha256']
            with self.assertRaisesRegex(audit.mods.ModError, 'does not match the original JAR'):
                audit.baseline_summary(root, entry, {'doors': row})
            row.update(families={'assets/doors/models': 1}, classCount=0)
            self.assertEqual(audit.baseline_summary(root, entry, {'doors': row}), row)

    def summary(self, entries):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'mod.jar'
            with zipfile.ZipFile(path, 'w') as archive:
                for name, value in entries.items():
                    archive.writestr(name, value)
            return audit.summarize(path)

    def test_textures_do_not_hide_missing_generated_models(self):
        baseline = self.summary({'assets/doors/textures/block/door.png': b'png',
                                 'assets/doors/blockstates/door.json': '{}',
                                 'assets/doors/models/block/door.json': '{}'})
        broken = self.summary({'assets/doors/textures/block/door.png': b'png'})
        self.assertEqual(audit.lost_families(broken, baseline),
                         ['assets/doors/blockstates', 'assets/doors/models'])

    def test_namespace_must_not_be_replaced_by_another_mod(self):
        original = self.summary({'assets/a/models/block/a.json': '{}'})
        other = self.summary({'assets/b/models/block/a.json': '{}'})
        self.assertEqual(audit.lost_families(other, original), ['assets/a/models'])

    def test_source_only_jar_cannot_replace_runtime_code(self):
        baseline = self.summary({'example/Main.class': b'class'})
        sources = self.summary({'example/Main.java': b'class Main {}'})
        self.assertEqual(audit.lost_families(sources, baseline), ['runtime classes'])

    def test_nested_runtime_code_is_accepted(self):
        nested = io.BytesIO()
        with zipfile.ZipFile(nested, 'w') as archive:
            archive.writestr('example/Main.class', b'class')
        current = self.summary({'META-INF/jars/core.jar': nested.getvalue()})
        self.assertEqual(current['classCount'], 1)

    def test_partial_intentional_removal_is_not_a_family_loss(self):
        baseline = self.summary({'assets/a/models/one.json': '{}', 'assets/a/models/two.json': '{}'})
        current = self.summary({'assets/a/models/new.json': '{}'})
        self.assertFalse(audit.lost_families(current, baseline))

    def test_malformed_json_is_reported_with_path(self):
        result = self.summary({'assets/a/blockstates/a.json': '{',
                               'assets/a/models/valid.json': '\ufeff{}'})
        self.assertEqual([e['path'] for e in result['invalidJson']], ['assets/a/blockstates/a.json'])

    def test_builtin_pack_does_not_mask_missing_default_assets(self):
        current = self.summary({'resourcepacks/optional/assets/a/models/a.json': '{}'})
        original = self.summary({'assets/a/models/a.json': '{}'})
        self.assertEqual(audit.lost_families(current, original), ['assets/a/models'])

    def test_texture_metadata_is_not_an_image(self):
        current = self.summary({'assets/a/textures/a.png.mcmeta': '{}'})
        original = self.summary({'assets/a/textures/a.png': b'png'})
        self.assertEqual(audit.lost_families(current, original), ['assets/a/textures'])


if __name__ == '__main__':
    unittest.main()
