#!/usr/bin/env python3
"""Validate complete cold/reload creative sweeps and summarize candidate IDs only."""
import argparse
import json
from pathlib import Path


def summarize(directory):
    directory = Path(directory)
    lines = (directory / 'creative-probe.tsv').read_text(encoding='utf-8').splitlines()
    if 'complete\ttrue' not in lines or any(line.startswith('failed\t') for line in lines):
        raise ValueError('Probe did not finish successfully')
    result = {'schemaVersion': 1, 'passes': {}, 'requiresVisualReview': False}
    for name in ('cold', 'reload'):
        sizes = [int(line.split('\t')[2]) for line in lines if line.startswith(name + '\tcreative_stacks\t')]
        if len(sizes) != 1 or sizes[0] <= 0 or f'{name}_sweep_complete\t{sizes[0]}' not in lines:
            raise ValueError(f'{name}: missing or ambiguous complete sweep')
        if name + '\tmodels_not_prewarmed\ttrue' not in lines:
            raise ValueError(f'{name}: cold model enumeration was not recorded')
        count = sizes[0]
        labels = (directory / f'{name}-creative-items.txt').read_text(encoding='utf-8').splitlines()
        if len(labels) != count:
            raise ValueError(f'{name}: stack label count differs')
        end = pages = 0
        for row in (directory / f'{name}-sweep-progress.tsv').read_text().splitlines():
            page, start, stop = map(int, row.split('\t'))
            if page != pages or start != end or stop != min(start + 48, count) or stop <= start:
                raise ValueError(f'{name}: non-contiguous page coverage')
            end, pages = stop, pages + 1
        if end != count:
            raise ValueError(f'{name}: not every stack was rendered')
        errors = directory / f'{name}-render-errors.tsv'
        if errors.exists() and errors.read_text().strip():
            raise ValueError(f'{name}: item rendering raised an exception')
        candidates = directory / f'{name}-render-candidates.tsv'
        rows, seen, first, third = [], set(), set(), set()
        for row in candidates.read_text(encoding='utf-8').splitlines() if candidates.exists() else []:
            page, frame, index, identity, pixels = row.split('\t')
            page, frame, index, pixels = map(int, (page, frame, index, pixels))
            if (frame not in (1, 3) or not 0 <= index < count or page != index // 48
                    or identity != labels[index] or not 5 < pixels <= 145 * 76
                    or (frame, index) in seen):
                raise ValueError(f'{name}: inconsistent candidate evidence')
            if not (directory / f'{name}-page-{page}-frame-{frame}.png').is_file():
                raise ValueError(f'{name}: candidate screenshot missing')
            seen.add((frame, index))
            (first if frame == 1 else third).add(index)
            rows.append({'page': page, 'frame': frame, 'index': index, 'item': identity, 'pixels': pixels})
        result['passes'][name] = {'stacks': count, 'pages': pages, 'candidates': rows,
                                  'firstFrameOnly': [{'index': i, 'item': labels[i]} for i in sorted(first - third)]}
        result['requiresVisualReview'] |= bool(rows)
    result['limits'] = 'Candidates require screenshot review; this checks GUI item rendering, not every placed-block state or server feature.'
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    try:
        result = summarize(args.directory)
    except (OSError, ValueError) as error:
        parser.exit(1, str(error) + '\n')
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + '\n'
    if args.output:
        args.output.write_text(rendered, encoding='utf-8')
    print(rendered, end='')


if __name__ == '__main__':
    main()
