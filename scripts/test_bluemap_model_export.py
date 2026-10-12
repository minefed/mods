"""Exporter acceptance checks: unsafe partial overrides must never be accepted."""
import importlib.util
import json
from pathlib import Path
import struct
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location('bluemap_export_verify', Path(__file__).resolve().parents[1] /
    'tools/bluemap-model-exporter/verify.py')
verify = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(verify)


class ExportContractTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.report = {'schemaVersion': 1, 'minecraft': '1.20.4', 'distribution': 'local-only',
                       'complete': True, 'exportedBlocks': 1, 'exportedStates': 1,
                       'blocks': [{'block': 'fixture:chair', 'states': 1, 'exported': True, 'failures': []}]}
        self.write('export-report.json', self.report)
        self.write('pack.mcmeta', {'pack': {'pack_format': 22}})
        self.write('assets/fixture/blockstates/chair.json', {'variants': {'': {'model': 'fixture:chair'}}})
        self.model = {'bluemap_quads': [{'positions': [[0, 1, 0], [0, 1, 1], [1, 1, 1], [1, 1, 0]],
                        'uv': [[0, 0], [0, 16], [16, 16], [16, 0]], 'texture': 'fixture:wood',
                        'direction': 'up', 'tintindex': -1, 'color': '#ffffff', 'shade': True}]}
        self.write('assets/fixture/models/chair.json', self.model)
        image = self.root / 'assets/fixture/textures/wood.png'
        image.parent.mkdir(parents=True)
        # The validator deliberately checks PNG envelope/size, not third-party pixel content.
        image.write_bytes(b'\x89PNG\r\n\x1a\n' + struct.pack('>I', 13) + b'IHDR' + struct.pack('>II', 16, 16))

    def write(self, name, data):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data), encoding='utf-8')

    def test_complete_block_and_sprite_references(self):
        result = verify.verify(self.root, require_all=True)
        self.assertEqual((1, 1, 1), (result['exportedStates'], result['models'], result['textures']))

    def test_partial_rejected_block_override_is_rejected(self):
        self.report['blocks'][0]['exported'] = False
        self.write('export-report.json', self.report)
        with self.assertRaisesRegex(ValueError, 'partial override'):
            verify.verify(self.root)

    def test_missing_sprite_is_rejected(self):
        (self.root / 'assets/fixture/textures/wood.png').unlink()
        with self.assertRaises(FileNotFoundError):
            verify.verify(self.root)

    def test_uncounted_state_is_rejected(self):
        self.report['blocks'][0]['states'] = 2
        self.write('export-report.json', self.report)
        with self.assertRaisesRegex(ValueError, 'coverage'):
            verify.verify(self.root)

    def test_contextual_shape_requires_explicit_mode(self):
        self.model['minefed_export_context'] = {'mode': 'isolated', 'queries': ['neighbor:1,0,0']}
        self.write('assets/fixture/models/chair.json', self.model)
        with self.assertRaisesRegex(ValueError, 'Unacknowledged'):
            verify.verify(self.root)
        self.report['contextualMode'] = 'isolated'
        self.write('export-report.json', self.report)
        verify.verify(self.root)

    def test_geometry_does_not_accept_nonfinite_coordinates(self):
        self.model['bluemap_quads'][0]['positions'][0][0] = float('nan')
        self.write('assets/fixture/models/chair.json', self.model)
        with self.assertRaisesRegex(ValueError, 'invalid vertex'):
            verify.verify(self.root)

    def test_resource_path_cannot_leave_export(self):
        self.model['bluemap_quads'][0]['texture'] = 'fixture:../../secret'
        self.write('assets/fixture/models/chair.json', self.model)
        with self.assertRaisesRegex(ValueError, 'Invalid resource'):
            verify.verify(self.root)


if __name__ == '__main__':
    unittest.main()
