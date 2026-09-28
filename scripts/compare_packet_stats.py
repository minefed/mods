"""Compare two packet-stats TSV dumps from tools/packet-stats (rates per second)."""
import argparse
import csv
from pathlib import Path


def load(path: Path) -> tuple[dict, dict]:
    """Return ({(direction, type, channel): (count/s, bytes/s)}, {(direction, player): bytes/s})."""
    packets, wire = {}, {}
    section = None
    for row in csv.reader(path.read_text(encoding='utf-8').splitlines(), delimiter='\t'):
        if not row or row[0].startswith('#'):
            continue
        if row[:3] == ['direction', 'type', 'channel']:
            section = 'packets'
        elif row[:2] == ['direction', 'player']:
            section = 'wire'
        elif section == 'packets' and len(row) == 7:
            packets[tuple(row[:3])] = (float(row[5]), float(row[6]))
        elif section == 'wire' and len(row) == 4:
            wire[tuple(row[:2])] = float(row[3])
    return packets, wire


def compare(before: Path, after: Path, limit: int) -> list[str]:
    old_packets, old_wire = load(before)
    new_packets, new_wire = load(after)
    lines = ['direction\ttype\tchannel\tcount/s before\tafter\tbytes/s before\tafter\tbytes/s delta']
    keys = sorted(old_packets.keys() | new_packets.keys(),
                  key=lambda k: -abs(new_packets.get(k, (0, 0))[1] - old_packets.get(k, (0, 0))[1]))
    for key in keys[:limit]:
        (oc, ob), (nc, nb) = old_packets.get(key, (0, 0)), new_packets.get(key, (0, 0))
        lines.append('\t'.join([*key, f'{oc:.2f}', f'{nc:.2f}', f'{ob:.0f}', f'{nb:.0f}', f'{nb - ob:+.0f}']))
    for direction in ('out', 'in'):
        old_total = sum(v[1] for k, v in old_packets.items() if k[0] == direction)
        new_total = sum(v[1] for k, v in new_packets.items() if k[0] == direction)
        old_socket = sum(v for k, v in old_wire.items() if k[0] == direction)
        new_socket = sum(v for k, v in new_wire.items() if k[0] == direction)
        lines.append(f'total {direction}: uncompressed {old_total:.0f} -> {new_total:.0f} B/s, '
                     f'socket {old_socket:.0f} -> {new_socket:.0f} B/s')
    return lines


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('before', type=Path)
    parser.add_argument('after', type=Path)
    parser.add_argument('--limit', type=int, default=40, help='rows with the largest byte-rate change')
    args = parser.parse_args()
    print('\n'.join(compare(args.before, args.after, args.limit)))


if __name__ == '__main__':
    main()
