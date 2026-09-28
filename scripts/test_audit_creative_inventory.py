import tempfile
from pathlib import Path
import unittest
from audit_creative_inventory import summarize


class CreativeAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.log = ''
        for name in ('cold', 'reload'):
            self.log += f'{name}\tcreative_stacks\t49\n{name}\tmodels_not_prewarmed\ttrue\n{name}_sweep_complete\t49\n'
            self.write(f'{name}-creative-items.txt', '\n'.join(f'example:item_{i}' for i in range(49)))
            self.write(f'{name}-sweep-progress.tsv', '0\t0\t48\n1\t48\t49\n')
        self.write('creative-probe.tsv', self.log + 'complete\ttrue\n')

    def write(self, path, text):
        (self.root / path).write_text(text, encoding='utf-8')

    def test_first_frame_only_is_distinct_from_persistent_purple(self):
        self.write('cold-render-candidates.tsv', '0\t1\t0\texample:item_0\t100\n0\t1\t1\texample:item_1\t50\n0\t3\t1\texample:item_1\t50\n')
        for frame in (1, 3):
            (self.root / f'cold-page-0-frame-{frame}.png').touch()
        result = summarize(self.root)
        self.assertTrue(result['requiresVisualReview'])
        self.assertEqual(result['passes']['cold']['firstFrameOnly'], [{'index': 0, 'item': 'example:item_0'}])

    def test_completion_marker_does_not_hide_missing_page(self):
        self.write('reload-sweep-progress.tsv', '0\t0\t48\n')
        with self.assertRaisesRegex(ValueError, 'not every stack'):
            summarize(self.root)

    def test_title_or_single_pass_is_not_complete_validation(self):
        self.write('creative-probe.tsv', self.log.split('reload\t')[0] + 'complete\ttrue\n')
        with self.assertRaisesRegex(ValueError, 'reload: missing'):
            summarize(self.root)

    def test_item_exception_is_not_hidden_by_completion(self):
        self.write('cold-render-errors.tsv', '0\texample:item_0\tjava.lang.RuntimeException\n')
        with self.assertRaisesRegex(ValueError, 'rendering raised'):
            summarize(self.root)

    def test_unreviewable_candidates_are_rejected(self):
        self.write('cold-render-candidates.tsv', '0\t1\t0\texample:item_0\t100\n')
        with self.assertRaisesRegex(ValueError, 'screenshot missing'):
            summarize(self.root)


if __name__ == '__main__':
    unittest.main()
