#!/usr/bin/env python3
"""Keep the verified source cache small enough to carry between CI runs."""

import argparse
import json
from pathlib import Path
import re
import shutil
import sys

import mods

ROOT = Path(__file__).resolve().parents[1]
CACHE = 'build/source-cache'
KEY = re.compile(r'[0-9a-f]{64}')


def read_record(path):
    try:
        value = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def run_receipts(root):
    """Receipts written by source builds of every run in this workspace."""
    receipts = []
    for path in sorted(root.glob('build/modpack-work/*/sources/*/result.json')):
        record = read_record(path)
        if record and isinstance(record.get('modId'), str) and isinstance(record.get('cacheKey'), str):
            receipts.append(record)
    return receipts


def prune(root):
    """Drop entries superseded by this workspace's builds; return whether the cache changed.

    A source built or reused here keeps only that entry. Sources this run never
    reached (for example after a failure) keep their entries for the next run.
    Entries for recipes that no longer exist, and incomplete or unreadable
    entries, are removed. Only 64-hex directories directly in the cache are touched.
    """
    root = Path(root).resolve()
    cache = mods.safe_path(root, CACHE)
    recipes = json.loads((root / 'inventory/build-recipes.json').read_text(encoding='utf-8'))
    sources = {recipe['modId'] for recipe in recipes['entries'] if recipe['mode'] == 'source'}
    receipts = run_receipts(root)
    used = {}
    for receipt in receipts:
        used.setdefault(receipt['modId'], set()).add(receipt['cacheKey'])
    changed = any(receipt.get('cacheHit') is not True for receipt in receipts)
    if not cache.is_dir():
        return changed
    for entry in sorted(cache.iterdir()):
        if not KEY.fullmatch(entry.name) or entry.is_symlink() or not entry.is_dir():
            continue
        record = read_record(entry / 'result.json')
        identity = record.get('modId') if record else None
        keep = (record is not None and record.get('cacheKey') == entry.name and identity in sources
                and entry.name in used.get(identity, {entry.name}))
        if not keep:
            shutil.rmtree(mods.safe_path(root, f'{CACHE}/{entry.name}'))
            print(f'Removed source cache entry {entry.name} ({identity or "unreadable"})', flush=True)
            changed = True
    return changed


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    command = commands.add_parser('prune')
    command.add_argument('--github-output', type=Path,
                         help='Append changed=true|false for a later cache save step')
    args = parser.parse_args(argv)
    try:
        changed = prune(ROOT)
    except (mods.ModError, OSError, ValueError, KeyError) as exc:
        print('ERROR: ' + str(exc), file=sys.stderr)
        return 1
    print('Source cache changed' if changed else 'Source cache unchanged', flush=True)
    if args.github_output:
        with args.github_output.open('a', encoding='utf-8') as output:
            output.write(f'changed={"true" if changed else "false"}\n')
    return 0


if __name__ == '__main__':
    sys.exit(main())
