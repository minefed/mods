"""Dependency-free export validator regressions, including exact multipart coverage."""
import importlib.util
import itertools
import json
from pathlib import Path
import random
import struct
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location('export_verify', Path(__file__).parents[1] / 'verify.py')
VERIFY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VERIFY)


class MultipartVerifierTest(unittest.TestCase):
    def metadata(self, domain, conditions):
        states = [dict(zip(domain, values)) for values in itertools.product(*domain.values())]

        def matches(condition, state):
            for key, value in condition.items():
                if key == 'OR':
                    if not any(matches(child, state) for child in value):
                        return False
                elif key == 'AND':
                    if not all(matches(child, state) for child in value):
                        return False
                else:
                    if type(value) is bool:
                        value = str(value).lower()
                    if state[key] not in value.split('|'):
                        return False
            return True

        block = {'states': len(states), 'components': len(conditions), 'propertyValues': domain,
                 'matchedStateCounts': [sum(matches(c, s) for s in states) for c in conditions],
                 'emptyStates': sum(not any(matches(c, s) for c in conditions) for s in states)}
        blockstate = {'multipart': [{'when': c, 'apply': {'model': 'test:block/part'}} for c in conditions]}
        return block, blockstate

    def test_nested_conditions_match_all_cartesian_states(self):
        domain = {'east': ['none', 'low', 'tall'], 'north': ['none', 'low', 'tall'],
                  'up': ['false', 'true'], 'waterlogged': ['false', 'true']}
        conditions = [{'OR': [{'east': 'low|tall'}, {'AND': [{'north': 'none'}, {'up': True}]}]},
                      {'north': 'tall', 'waterlogged': False}]
        block, data = self.metadata(domain, conditions)
        self.assertEqual(len(VERIFY.multipart_variants(block, data)), 2)

    def test_random_truth_tables_and_shuffled_property_order(self):
        randomizer = random.Random(5086)
        domain = {'a': ['0', '1', '2'], 'b': ['false', 'true'], 'c': ['low', 'tall']}
        states = [dict(zip(domain, values)) for values in itertools.product(*domain.values())]
        for trial in range(100):
            order = list(domain.items())
            randomizer.shuffle(order)
            conditions = [{'OR': [state for state in states if randomizer.choice([True, False])]}]
            block, data = self.metadata(dict(order), conditions)
            VERIFY.multipart_variants(block, data)

    def test_missing_when_is_always_true_and_no_match_can_be_empty(self):
        block, data = self.metadata({'a': ['0', '1']}, [{}])
        del data['multipart'][0]['when']
        VERIFY.multipart_variants(block, data)
        block, data = self.metadata({'a': ['0', '1']}, [{'OR': []}])
        self.assertEqual(block['emptyStates'], 2)
        VERIFY.multipart_variants(block, data)

    def test_diagonal_wall_domain_26244_states(self):
        domain = {direction: ['none', 'low', 'tall'] for direction in
                  ['east', 'north', 'northeast', 'northwest', 'south', 'southeast', 'southwest', 'west']}
        domain.update(up=['false', 'true'], waterlogged=['false', 'true'])
        block, data = self.metadata(domain, [{'northwest': 'low|tall'}, {'up': True}])
        self.assertEqual(block['states'], 26244)
        self.assertEqual(block['matchedStateCounts'], [17496, 13122])
        VERIFY.multipart_variants(block, data)

    def test_rejects_incorrect_counts_and_unknown_properties(self):
        for field, value in [('states', 3), ('components', 2), ('emptyStates', 0), ('matchedStateCounts', [2])]:
            block, data = self.metadata({'a': ['0', '1']}, [{'a': '1'}])
            block[field] = value
            with self.assertRaises(ValueError):
                VERIFY.multipart_variants(block, data)
        for condition in [{'missing': '1'}, {'a': 'missing'}, {'AND': {}}, []]:
            block, data = self.metadata({'a': ['0', '1']}, [{'a': '1'}])
            data['multipart'][0]['when'] = condition
            with self.assertRaises(ValueError):
                VERIFY.multipart_variants(block, data)

    def test_full_export_accepts_only_explicit_empty_model(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            def write(relative, data):
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(data), encoding='utf-8')

            block, state = self.metadata({'a': ['0', '1']}, [{}])
            block.update(block='test:block', exported=True, failures=[], format='multipart')
            write('pack.mcmeta', {'pack': {'pack_format': 22}})
            write('export-report.json', {'schemaVersion': 1, 'minecraft': '1.20.4', 'complete': True,
                                         'distribution': 'local-only', 'blocks': [block],
                                         'exportedBlocks': 1, 'exportedStates': 2})
            write('assets/test/blockstates/block.json', state)
            write('assets/test/models/block/part.json', {'bluemap_quads': [], 'minefed_export_empty': True})
            self.assertEqual(VERIFY.verify(root)['exportedStates'], 2)
            write('assets/test/models/block/part.json', {'bluemap_quads': []})
            with self.assertRaises(ValueError):
                VERIFY.verify(root)

    def test_existing_variant_export_still_loads(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for folder in ['assets/test/blockstates', 'assets/test/models/block']:
                (root / folder).mkdir(parents=True)
            (root / 'pack.mcmeta').write_text(json.dumps({'pack': {'pack_format': 22}}))
            (root / 'export-report.json').write_text(json.dumps({
                'schemaVersion': 1, 'minecraft': '1.20.4', 'complete': True, 'distribution': 'local-only',
                'blocks': [{'block': 'test:block', 'exported': True, 'failures': [], 'states': 1}],
                'exportedBlocks': 1, 'exportedStates': 1}))
            (root / 'assets/test/blockstates/block.json').write_text(json.dumps({'variants': {'': {'model': 'test:block/part'}}}))
            (root / 'assets/test/models/block/part.json').write_text(json.dumps({'bluemap_quads': [], 'minefed_export_empty': True}))
            self.assertEqual(VERIFY.verify(root)['exportedBlocks'], 1)


class TextureAnimationTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / 'texture.png'

    def texture(self, width, height, animation=None):
        self.path.write_bytes(b'\x89PNG\r\n\x1a\n' + struct.pack('>I', 13) + b'IHDR' + struct.pack('>II', width, height))
        metadata = self.path.with_name(self.path.name + '.mcmeta')
        if animation is None:
            metadata.unlink(missing_ok=True)
        else:
            metadata.write_text(json.dumps({'animation': animation}), encoding='utf-8')

    def test_square_static_and_vertical_animated_textures(self):
        self.texture(16, 16)
        self.assertIsNone(VERIFY.texture_animation(self.path))
        self.texture(16, 48)
        self.assertIsNone(VERIFY.texture_animation(self.path))
        self.texture(16, 48, {'frames': [{'index': 2, 'time': 5}, {'index': 0, 'time': 1},
                                       {'index': 2, 'time': 3}], 'interpolate': True})
        self.assertEqual(VERIFY.texture_animation(self.path), 3)
        self.texture(16, 48, {'frames': [2, 0, 2], 'frametime': 4})
        self.assertEqual(VERIFY.texture_animation(self.path), 3)

    def test_invalid_frame_index_time_and_layout_are_rejected(self):
        for animation in [
                {'frames': [3]}, {'frames': [-1]}, {'frames': [True]}, {'frames': []},
                {'frames': [{'index': 0, 'time': 0}]}, {'frames': [{'index': 0, 'time': -1}]},
                {'frames': [0], 'frametime': True}, {'frames': [0], 'interpolate': 1},
                {'frames': [0], 'width': 8}]:
            self.texture(16, 48, animation)
            with self.assertRaises(ValueError):
                VERIFY.texture_animation(self.path)
        for width, height in [(16, 48), (48, 16), (16, 30)]:
            self.texture(width, height)
            self.assertIsNone(VERIFY.texture_animation(self.path))
        self.texture(48, 16, {'frames': [0]})
        with self.assertRaises(ValueError):
            VERIFY.texture_animation(self.path)

    def test_animation_manifest_requires_metadata_and_correct_strip_count(self):
        root = Path(self.directory.name)

        def write(relative, data):
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(data), encoding='utf-8')

        self.path = root / 'assets/test/textures/animated.png'
        self.path.parent.mkdir(parents=True)
        self.texture(16, 48, {'frames': [2, 0, 2], 'frametime': 4})
        report = {'schemaVersion': 1, 'minecraft': '1.20.4', 'complete': True, 'distribution': 'local-only',
                  'blocks': [{'block': 'test:block', 'exported': True, 'failures': [], 'states': 1}],
                  'exportedBlocks': 1, 'exportedStates': 1, 'textures': {'original:image': 'test:animated'},
                  'animatedTextures': {'original:image': {'frames': 3}}}
        write('pack.mcmeta', {'pack': {'pack_format': 22}})
        write('export-report.json', report)
        write('assets/test/blockstates/block.json', {'variants': {'': {'model': 'test:block/part'}}})
        write('assets/test/models/block/part.json', {'bluemap_quads': [], 'minefed_export_empty': True})
        self.assertEqual(VERIFY.verify(root)['animatedTextures'], 1)
        report['animatedTextures']['original:image']['frames'] = 2
        write('export-report.json', report)
        with self.assertRaisesRegex(ValueError, 'frame count'):
            VERIFY.verify(root)
        report['animatedTextures']['original:image']['frames'] = 3
        write('export-report.json', report)
        self.texture(16, 48)
        with self.assertRaisesRegex(ValueError, 'frame count'):
            VERIFY.verify(root)


if __name__ == '__main__':
    unittest.main()
