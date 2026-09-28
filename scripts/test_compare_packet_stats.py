import tempfile
import unittest
from pathlib import Path

import compare_packet_stats


def dump(rows, wire):
    return ('# reason=command windowSeconds=10.000\n'
            'direction\ttype\tchannel\tcount\tuncompressedBytes\tcountPerSecond\tbytesPerSecond\n'
            + ''.join('\t'.join(map(str, r)) + '\n' for r in rows)
            + '\ndirection\tplayer\twireBytes\twireBytesPerSecond\n'
            + ''.join('\t'.join(map(str, r)) + '\n' for r in wire))


class ComparePacketStatsTest(unittest.TestCase):
    def test_orders_by_byte_rate_change_and_totals(self):
        with tempfile.TemporaryDirectory() as tmp:
            before, after = Path(tmp, 'a.tsv'), Path(tmp, 'b.tsv')
            before.write_text(dump([('out', 'BlockEntityUpdate', '', 200, 100000, '20.00', '10000.00'),
                                    ('out', 'CustomPayload', 'mtr:packet', 10, 5000, '1.00', '500.00'),
                                    ('in', 'KeepAlive', '', 1, 10, '0.10', '1.00')],
                                   [('out', 'alice', 60000, '6000.00')]), encoding='utf-8')
            after.write_text(dump([('out', 'CustomPayload', 'mtr:packet', 10, 4000, '1.00', '400.00'),
                                   ('in', 'KeepAlive', '', 1, 10, '0.10', '1.00')],
                                  [('out', 'alice', 20000, '2000.00')]), encoding='utf-8')
            lines = compare_packet_stats.compare(before, after, 10)
        self.assertTrue(lines[1].startswith('out\tBlockEntityUpdate\t\t20.00\t0.00\t10000\t0\t-10000'))
        self.assertIn('mtr:packet', lines[2])
        self.assertIn('total out: uncompressed 10500 -> 400 B/s, socket 6000 -> 2000 B/s', lines)
        self.assertIn('total in: uncompressed 1 -> 1 B/s, socket 0 -> 0 B/s', lines)

    def test_ignores_comments_and_malformed_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp, 'a.tsv')
            path.write_text(dump([('out', 'X', '', 1, 2, '0.10', '0.20'), ('bad',)], []), encoding='utf-8')
            packets, wire = compare_packet_stats.load(path)
        self.assertEqual(packets, {('out', 'X', ''): (0.1, 0.2)})
        self.assertEqual(wire, {})


if __name__ == '__main__':
    unittest.main()
