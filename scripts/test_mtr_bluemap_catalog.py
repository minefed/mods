"""Registration coverage and reproducible metadata extraction; no game/network."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

import mods
import mtr_bluemap_catalog as catalog


class VehicleCatalogTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='minefed-mtr-catalog-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.pack = self.root / 'resource_pack'
        self.definition = {'modelResource': 'mtr:test/body.bbmodel', 'textureResource': 'mtr:test/body.png',
                           'modelPropertiesResource': 'mtr:test/properties.json',
                           'positionDefinitionsResource': 'mtr:test/positions.json'}
        self.vehicle = {'id': 'test_cab_1', 'name': 'Test cab', 'length': 25, 'width': 2,
                        'models': [self.definition]}
        self.write(catalog.REGISTRATIONS[0], {'custom_signs': {}})
        self.write(catalog.REGISTRATIONS[1], {'vehicles': [self.vehicle]})
        for identifier in self.definition.values():
            self.write(catalog.ResourceReader.asset(identifier), {})

    def write(self, path, value):
        destination = self.pack / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(value), encoding='utf-8')

    def test_exact_ids_dimensions_and_zip_directory_match_without_copying_assets(self):
        second = {**self.vehicle, 'id': 'test_cab_2', 'name': 'Reverse cab'}
        self.write(catalog.REGISTRATIONS[1], {'vehicles': [self.vehicle, second]})
        expected = catalog.build_catalog(self.pack, require_vehicles=True)
        archive_path = self.root / 'pack.zip'
        with zipfile.ZipFile(archive_path, 'w') as archive:
            for path in sorted(self.pack.rglob('*')):
                if path.is_file():
                    archive.write(path, path.relative_to(self.pack).as_posix())
        self.assertEqual(expected, catalog.build_catalog(archive_path, require_vehicles=True))
        self.assertEqual({'test_cab_1', 'test_cab_2'}, set(expected['vehicles']))
        self.assertEqual({'name': 'Test cab', 'length': 25, 'width': 2}, expected['vehicles']['test_cab_1'])
        self.assertEqual('live-mtr-route', expected['source']['colors'])
        self.assertEqual(6, len(expected['source']['resourceSha256']))

    def test_no_silent_coverage_loss_from_missing_or_invalid_resources(self):
        for field, identifier in self.definition.items():
            path = self.pack / catalog.ResourceReader.asset(identifier)
            content = path.read_bytes()
            path.unlink()
            with self.subTest(field=field), self.assertRaisesRegex(mods.ModError, 'Missing or unreadable'):
                catalog.build_catalog(self.pack)
            path.write_bytes(content)
        path = self.pack / catalog.ResourceReader.asset(self.definition['modelPropertiesResource'])
        path.write_text('{invalid')
        with self.assertRaisesRegex(mods.ModError, 'Invalid MTR resource JSON'):
            catalog.build_catalog(self.pack)

    def test_registration_branch_matches_mtr_and_legacy_trains_require_migration(self):
        self.write(catalog.REGISTRATIONS[0], {'custom_signs': {}, 'vehicles': [{**self.vehicle, 'id': 'ignored'}]})
        self.assertEqual(['test_cab_1'], list(catalog.build_catalog(self.pack)['vehicles']))
        self.write(catalog.REGISTRATIONS[0], {'custom_trains': {'legacy_train': {}}})
        with self.assertRaisesRegex(mods.ModError, 'Legacy custom_trains require migration'):
            catalog.build_catalog(self.pack)

    def test_duplicate_empty_invalid_dimensions_and_unsafe_reference_fail(self):
        cases = [({'vehicles': [self.vehicle, self.vehicle]}, 'duplicate'),
                 ({'vehicles': []}, 'no supported'),
                 ({'vehicles': [{**self.vehicle, 'length': 0}]}, 'Invalid length'),
                 ({'vehicles': [{**self.vehicle, 'width': float('nan')}]}, 'Invalid width'),
                 ({'vehicles': [{**self.vehicle, 'models': []}]}, 'Missing MTR vehicle body')]
        unsafe = copy.deepcopy(self.vehicle)
        unsafe['models'][0]['modelResource'] = 'mtr:../../outside.json'
        cases.append(({'vehicles': [unsafe]}, 'Unsafe'))
        for document, message in cases:
            self.write(catalog.REGISTRATIONS[1], document)
            with self.subTest(message=message), self.assertRaisesRegex(mods.ModError, message):
                catalog.build_catalog(self.pack, require_vehicles=True)

    def test_current_pack_all_six_active_vehicle_parts_are_covered(self):
        pack = Path(__file__).resolve().parents[1] / 'resourcepack/resource_pack'
        if not pack.exists():
            self.skipTest('Resource pack submodule is not initialized')
        result = catalog.build_catalog(pack, require_vehicles=True)
        expected = {f'minefed_mxr_{family}_{part}' for family in ('a1000', 'mistilteinn')
                    for part in ('cab_1', 'cab_2', 'trailer')}
        self.assertTrue(expected.issubset(result['vehicles']))
        registered = json.loads((pack / catalog.REGISTRATIONS[1]).read_text(encoding='utf-8'))['vehicles']
        self.assertEqual({vehicle['id'] for vehicle in registered}, set(result['vehicles']))


if __name__ == '__main__':
    unittest.main()
