"""Reject source JARs that silently lose runtime resource families before packaging.

This is a packaging check, not a substitute for Minecraft's dynamic model loaders.
The report covers every selected source and binary JAR. The immutable operating
baseline provides independent evidence that a namespace used a resource family.
"""
from __future__ import annotations

import argparse
from collections import Counter
import io
import json
from pathlib import Path
import re
import sys
import zipfile

import build_modpack as builder
import mods

ROOT = Path(__file__).resolve().parents[1]
BASELINE = 'inventory/resource-baseline.json'
RESOURCE = re.compile(r'^(assets/[^/]+/(?:blockstates|models|textures)|data/[^/]+/(?:recipes|loot_tables))/.+')


def summarize(path: Path) -> dict:
    families = Counter()
    invalid = []
    class_count = 0
    with zipfile.ZipFile(path) as archive:
        for info in archive.infolist():
            if info.is_dir():
                continue
            name = info.filename
            class_count += name.endswith('.class')
            match = RESOURCE.fullmatch(name)
            if match:
                family = match[1]
                if family.endswith('/textures'):
                    if name.endswith('.png'):
                        families[family] += 1
                elif name.endswith('.json'):
                    families[family] += 1
                    try:
                        json.loads(archive.read(info).decode('utf-8-sig'))
                    except (ValueError, UnicodeDecodeError) as exc:
                        invalid.append({'path': name, 'error': str(exc)})
            # Resource-only outer mods may legitimately put all code in nested JARs.
            if name.startswith('META-INF/jars/') and name.endswith('.jar'):
                with zipfile.ZipFile(io.BytesIO(archive.read(info))) as nested:
                    class_count += sum(n.endswith('.class') for n in nested.namelist())
    return {'families': dict(sorted(families.items())), 'classCount': class_count,
            'invalidJson': invalid}


def lost_families(current: dict, baseline: dict) -> list[str]:
    """Do not demand equal counts: updates may intentionally replace some assets."""
    missing = [family for family, count in baseline['families'].items()
               if count and not current['families'].get(family)]
    if baseline['classCount'] and not current['classCount']:
        missing.append('runtime classes')
    return sorted(missing)


def load_baselines(root: Path) -> dict:
    """Keep the historical evidence usable in CI without redistributing old JARs."""
    document = json.loads((root / BASELINE).read_text(encoding='utf-8'))
    if (not isinstance(document, dict) or document.get('schemaVersion') != 1 or
            not isinstance(document.get('entries'), list)):
        raise mods.ModError('Invalid resource baseline manifest')
    records = {}
    for row in document['entries']:
        if not isinstance(row, dict):
            raise mods.ModError('Resource baseline entry must be an object')
        identity = row.get('modId')
        families = row.get('families')
        if (not isinstance(identity, str) or not identity or identity in records or
                not re.fullmatch(r'[a-f0-9]{64}', str(row.get('sha256', ''))) or
                type(row.get('classCount')) is not int or row['classCount'] < 0 or
                not isinstance(families, dict) or
                any(not isinstance(key, str) or type(value) is not int or value <= 0
                    for key, value in families.items())):
            raise mods.ModError('Invalid or duplicate resource baseline entry: ' + str(identity))
        records[identity] = row
    return records


def baseline_summary(root: Path, entry: dict, records: dict) -> dict:
    baseline = records.get(entry['modId'])
    if baseline is None or baseline['sha256'] != entry['sha256']:
        raise mods.ModError('Missing hash-matched resource baseline: ' + entry['modId'])
    path = mods.safe_path(root, entry['artifact']['path'])
    if path.exists():
        mods.check_artifact(root, entry)
        actual = summarize(path)
        if any(actual[key] != baseline[key] for key in ('families', 'classCount')):
            raise mods.ModError('Resource baseline does not match the original JAR: ' + entry['modId'])
    return baseline


def audit(root: Path, run: str) -> dict:
    manifest, plan = builder.load_plan(root)
    work = builder.check_run(root, run, manifest, plan)
    entries, _ = builder.collect_entries(root, run, manifest, plan)
    original = mods.load_manifest(root)
    baselines = {e['modId']: e for e in original['entries'] if e['included']}
    baseline_records = load_baselines(root)
    source_ids = {r['modId'] for r in plan['entries'] if r['mode'] == 'source'}
    report = {'schemaVersion': 1, 'run': run, 'minecraftVersion': '1.20.4',
              'loader': 'fabric', 'runtimeValidated': False, 'entries': [], 'errors': [],
              'baselineManifestSha256': mods.file_digest(root / BASELINE)[0],
              'scope': 'JAR JSON syntax, resource-family and runtime-class preservation; '
                       'dynamic resources, individual block states and visuals require runtime validation.'}
    for entry in entries:
        path = mods.safe_path(root, entry['artifact']['path'])
        current = summarize(path)
        row = {'modId': entry['modId'], 'version': entry['version'],
               'sha256': entry['sha256'], 'artifactPath': entry['artifact']['path'], **current}
        baseline_entry = baselines.get(entry['modId'])
        if entry['modId'] in source_ids and baseline_entry and baseline_entry.get('capturedServerBaseline', True):
            # The snapshot is independently captured from the hash-pinned original.
            # CI restores only required binary inputs, not every historical source JAR.
            baseline = baseline_summary(root, baseline_entry, baseline_records)
            row['baselineSha256'] = baseline_entry['sha256']
            row['lostFamilies'] = lost_families(current, baseline)
            report['errors'].extend(f"{entry['modId']}: lost {family}" for family in row['lostFamilies'])
        report['errors'].extend(f"{entry['modId']}: invalid JSON {item['path']}" for item in current['invalidJson'])
        report['entries'].append(row)
    report['artifactCount'] = len(report['entries'])
    builder.write_json(work / 'resource-audit.json', report)
    if report['errors']:
        raise mods.ModError('Runtime resource audit failed:\n' + '\n'.join(report['errors']))
    print(f"Verified runtime resource packaging for {len(entries)} JARs. Report: {work / 'resource-audit.json'}")
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', required=True)
    args = parser.parse_args(argv)
    try:
        audit(ROOT, args.run)
    except (mods.ModError, OSError, ValueError, zipfile.BadZipFile) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
