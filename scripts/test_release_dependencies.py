"""Offline dependency fixtures; opt in to Java/official-download integration separately."""
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
import zipfile

import mods
import release_dependencies as dependencies


def fixture_predicates(pairs):
    """Only explicit fixture predicates; never a production SemVer replacement."""
    accepted = {
        '*': lambda version: True,
        '=1': lambda version: version == '1',
        '=2': lambda version: version == '2',
    }
    return {(version, predicate): accepted[predicate](version) for version, predicate in pairs}


def record(identity, version='1', environment='*', **fields):
    return {'origin': identity + '.jar', 'metadata': {'id': identity, 'version': version, 'schemaVersion': 1, **fields},
            'profiles': {'server': True, 'client': True},
            'activeEnvironments': ['server', 'client'] if environment == '*' else [environment], 'topLevel': True}


class DependencyTests(unittest.TestCase):
    def test_missing_and_breaks_are_reported_for_selected_profiles(self):
        result = dependencies.analyze([record('one', depends={'absent': '*'}, breaks={'two': '=1'}), record('two')],
                                      '0.18.0', fixture_predicates)
        for side in ('server', 'client'):
            report = result['environments'][side]
            self.assertEqual('absent', report['missingOrIncompatibleDependencies'][0]['to'])
            self.assertEqual('two', report['unavoidableBreaks'][0]['to'])
        self.assertFalse(result['runtimeValidated'])

    def test_disabled_environment_softens_only_present_legacy_dependency(self):
        required = record('common', depends={'client_dependency': '*'})
        client = record('client_dependency', environment='client')
        result = dependencies.analyze([required, client], '0.18.0', fixture_predicates)
        self.assertEqual([], result['environments']['server']['missingOrIncompatibleDependencies'])
        self.assertEqual(1, len(result['environments']['server']['environmentDisabledDependenciesSoftened']))
        self.assertEqual([], result['environments']['client']['environmentDisabledDependenciesSoftened'])
        client['profiles']['server'] = False
        result = dependencies.analyze([required, client], '0.18.0', fixture_predicates)
        self.assertEqual(1, len(result['environments']['server']['missingOrIncompatibleDependencies']))

    def test_candidate_intersection_and_top_level_version_cannot_be_masked(self):
        first = record('library', '1')
        second = record('library', '2')
        first['topLevel'] = second['topLevel'] = False
        required = [record('a', depends={'library': '=1'}), record('b', depends={'library': '=2'})]
        result = dependencies.analyze([*required, first, second], '0.18.0', fixture_predicates)
        self.assertEqual('library', result['environments']['server']['candidateVersionIntersectionEmpty'][0]['modId'])
        first['topLevel'] = True
        result = dependencies.analyze([record('a', depends={'library': '=2'}), first, second], '0.18.0', fixture_predicates)
        self.assertEqual(['1'], result['environments']['server']['missingOrIncompatibleDependencies'][0]['availableVersions'])

    def test_nested_jar_and_provides_are_actual_metadata_and_missing_jar_fails(self):
        with tempfile.TemporaryDirectory(prefix='minefed-dependency-test-') as directory:
            root = Path(directory)
            (root / '.cache').mkdir()
            nested = io.BytesIO()
            with zipfile.ZipFile(nested, 'w') as jar:
                jar.writestr('fabric.mod.json', json.dumps({'schemaVersion': 1, 'id': 'implementation', 'version': '1', 'provides': ['api']}))
            outer = io.BytesIO()
            with zipfile.ZipFile(outer, 'w') as jar:
                jar.writestr('fabric.mod.json', json.dumps({'schemaVersion': 1, 'id': 'parent', 'version': '1',
                    'depends': {'api': '=1'}, 'jars': [{'file': 'META-INF/jars/api.jar'}]}))
                jar.writestr('META-INF/jars/api.jar', nested.getvalue())
            with zipfile.ZipFile(outer) as jar:
                records = dependencies.scan_metadata(root, jar, 'actual.jar', {'client': True, 'server': True})
            self.assertEqual(2, len(records))
            self.assertIn('!/META-INF/jars/api.jar', records[1]['origin'])
            result = dependencies.analyze(records, '0.18.0', fixture_predicates)
            self.assertEqual([], result['environments']['server']['missingOrIncompatibleDependencies'])
            missing = io.BytesIO()
            with zipfile.ZipFile(missing, 'w') as jar:
                jar.writestr('fabric.mod.json', json.dumps({'id': 'parent', 'version': '1', 'jars': [{'file': 'missing.jar'}]}))
            with zipfile.ZipFile(missing) as jar:
                with self.assertRaisesRegex(mods.ModError, 'Missing'):
                    dependencies.scan_metadata(root, jar, 'actual.jar', {'client': True, 'server': True})


class FabricPredicateIntegration(unittest.TestCase):
    @unittest.skipUnless(os.environ.get('MINEFED_RELEASE_INTEGRATION') == '1', 'Set MINEFED_RELEASE_INTEGRATION=1 for JDK17/official Fabric integration')
    def test_real_fabric_predicates_prerelease_or_and_non_numeric_versions(self):
        root = Path(__file__).resolve().parents[1]
        pairs = {('1.20.4', '>=1.20.3-'), ('4.0.5', '>=4.0.0-beta.14 <4.1'),
                 ('4.1.0', '>=4.0.0-beta.14 <4.1'), ('7.3.0+f2cdc4a', '>=7.3.0'), ('custom-build', '*')}
        answers = dependencies.evaluate_predicates(root, pairs)
        self.assertTrue(answers[('1.20.4', '>=1.20.3-')])
        self.assertTrue(answers[('4.0.5', '>=4.0.0-beta.14 <4.1')])
        self.assertFalse(answers[('4.1.0', '>=4.0.0-beta.14 <4.1')])
        self.assertTrue(answers[('7.3.0+f2cdc4a', '>=7.3.0')])
        self.assertTrue(answers[('custom-build', '*')])


if __name__ == '__main__':
    unittest.main()
