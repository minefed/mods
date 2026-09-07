#!/usr/bin/env python3
"""Create reviewed public release assets from a verified private build ZIP."""
from __future__ import annotations

import argparse
import copy
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tempfile
from urllib.parse import urlparse
import zipfile

import build_modpack as builder
import mods

ROOT = Path(__file__).resolve().parents[1]
MRPACK_HOSTS = {'cdn.modrinth.com', 'github.com', 'raw.githubusercontent.com', 'gitlab.com'}

# A standalone stdlib installer is shipped with both profiles. It does not install
# Minecraft or accept its EULA, and never replaces an existing modified file.
INSTALLER = r'''#!/usr/bin/env python3
"""Restore and verify the exact reviewed mod files; Python 3.10+, no packages."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PureWindowsPath
import re
import tempfile
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

def target(root, value):
    parts = value.split('/') if isinstance(value, str) else []
    if not parts or parts[0] != 'mods' or len(parts) != 2:
        raise ValueError('Expected mods/<filename>: ' + str(value))
    if PureWindowsPath(value).drive or any(p in ('', '.', '..') or re.search(r'[<>:"|?*\\\x00-\x1f]', p) or p.endswith((' ', '.')) for p in parts):
        raise ValueError('Unsafe mod path: ' + value)
    path = root
    for part in parts:
        if re.fullmatch(r'(?i)(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?', part):
            raise ValueError('Reserved filename: ' + value)
        path = path / part
        if path.is_symlink() or getattr(path, 'is_junction', lambda: False)():
            raise ValueError('Linked paths are forbidden: ' + value)
    if not path.resolve().is_relative_to(root):
        raise ValueError('Path leaves installation directory')
    return path

def url_check(value):
    parsed = urlparse(value)
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or re.search(r'\s|[\x00-\x1f]', value):
        raise ValueError('Expected a reviewed HTTPS download URL')

class HTTPSOnly(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        url_check(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)

def check(path, item):
    digest, size = hashlib.sha256(), 0
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
            size += len(block)
    if digest.hexdigest() != item['sha256'] or size != item['size']:
        raise ValueError('Modified or corrupt file left unchanged: ' + str(path))

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, default=Path(__file__).resolve().parent)
    args = parser.parse_args()
    root = args.directory.resolve()
    manifest = json.loads((Path(__file__).resolve().parent / 'download-manifest.json').read_text(encoding='utf-8'))
    items = manifest['files']
    if not items:
        raise ValueError('Installation manifest contains no required mods')
    seen, pending = set(), []
    for item in items:
        path = target(root, item['path'])
        if item['path'].casefold() in seen:
            raise ValueError('Duplicate installation path')
        seen.add(item['path'].casefold())
        if not re.fullmatch('[0-9a-f]{64}', str(item.get('sha256'))) or type(item.get('size')) is not int or item['size'] <= 0:
            raise ValueError('Invalid recorded hash or size')
        if item.get('downloadUrl'):
            url_check(item['downloadUrl'])
        if path.exists():
            check(path, item)
        else:
            pending.append((path, item))
    missing = []
    opener = build_opener(HTTPSOnly())
    for path, item in pending:
        if not item.get('downloadUrl'):
            missing.append(item['path'] + ': ' + item.get('reason', 'Restore this exact file from the archive or author'))
            continue
        target(root, item['path'])
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=path.parent, suffix='.part', delete=False) as stream:
                temporary = Path(stream.name)
                with opener.open(Request(item['downloadUrl'], headers={'User-Agent': 'Minefed-Modpack-Installer/1'}), timeout=60) as response:
                    url_check(response.url)
                    size = 0
                    while block := response.read(1024 * 1024):
                        size += len(block)
                        if size > item['size']:
                            raise ValueError('Download exceeds recorded size: ' + item['path'])
                        stream.write(block)
            check(temporary, item)
            target(root, item['path'])
            os.link(temporary, path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
    if missing:
        raise ValueError('Installation incomplete. Required files must be restored manually:\n' + '\n'.join(missing))
    for item in items:
        check(target(root, item['path']), item)
    print('All required mod files verified. Minecraft/Fabric startup has not been validated.')

if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, KeyError) as error:
        raise SystemExit(str(error))
'''


def json_bytes(value) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf-8')


def https_url(value: str, *, mrpack: bool = False) -> None:
    if not isinstance(value, str):
        raise mods.ModError('A reviewed HTTPS URL is required')
    parsed = urlparse(value)
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or re.search(r'\s|[\x00-\x1f]', value):
        raise mods.ModError(f'Invalid reviewed HTTPS URL: {value!r}')
    if mrpack and parsed.hostname.lower() not in MRPACK_HOSTS:
        raise mods.ModError(f'Modrinth does not support this download host: {parsed.hostname}; review a supported URL or use manual installation')


def zip_members(root: Path, archive: zipfile.ZipFile) -> dict:
    result = {}
    folded = set()
    for info in archive.infolist():
        name = info.filename.rstrip('/') if info.is_dir() else info.filename
        mods.safe_path(root, name)
        if name.casefold() in folded or (info.external_attr >> 16) & 0o170000 == 0o120000:
            raise mods.ModError(f'Duplicate or linked ZIP member: {name}')
        folded.add(name.casefold())
        result[info.filename] = info
    return result


def zip_json(archive, members, name):
    if name not in members or members[name].file_size > 8 * mods.CHUNK_SIZE:
        raise mods.ModError(f'Missing or oversized ZIP metadata: {name}')
    return json.loads(archive.read(members[name]).decode('utf-8-sig'))


def copy_member(archive, info, target: Path, expected: dict) -> None:
    if info.file_size != expected['size']:
        raise mods.ModError(f'ZIP size differs from manifest: {info.filename}')
    target.parent.mkdir(parents=True, exist_ok=True)
    with archive.open(info) as source, target.open('xb') as output:
        shutil.copyfileobj(source, output, mods.CHUNK_SIZE)
    mods.check_bytes(target, expected)


def checked_jar(root: Path, path: Path, entry: dict) -> dict:
    staged = copy.deepcopy(entry)
    staged['artifact']['path'] = path.relative_to(root).as_posix()
    mods.check_artifact(root, staged)
    metadata = builder.fabric_metadata(path)
    builder.check_runtime_metadata(metadata)
    return metadata


def input_build(root: Path, result_json: str, work: Path):
    summary = builder.read_json(mods.safe_path(root, result_json))
    path = mods.safe_path(root, summary['path'])
    mods.check_bytes(path, {**summary, 'fileName': path.name})
    with zipfile.ZipFile(path) as archive:
        members = zip_members(root, archive)
        if archive.testzip() is not None:
            raise mods.ModError('Input build ZIP failed CRC validation')
        manifest = zip_json(archive, members, 'inventory/mods.lock.json')
        recipes = zip_json(archive, members, 'inventory/build-recipes.json')
        provenance = zip_json(archive, members, 'BUILD-PROVENANCE.json')
        build = manifest.get('build', {})
        if not summary.get('sourceCompilation') or not build.get('sourceCompilation') or summary.get('run') != build.get('run'):
            raise mods.ModError('Input must be a completed source build with a matching run ID')
        if manifest.get('minecraftVersion') != '1.20.4' or manifest.get('loader') != 'fabric':
            raise mods.ModError('Release requires Minecraft 1.20.4 / Fabric')
        entries = manifest['entries']
        identities = {e['modId'] for e in entries if e['included']}
        recipe_map = {e['modId']: e for e in recipes['entries']}
        provenance_map = {e['modId']: e for e in provenance}
        if len(entries) != len(identities) or len(recipe_map) != len(recipes['entries']) or set(recipe_map) != identities or len(provenance_map) != len(provenance) or set(provenance_map) != identities:
            raise mods.ModError('Input build inventory/recipe/provenance coverage differs')
        for field, value in [('artifactCount', len(entries)), ('sourceCount', sum(e['mode'] == 'source' for e in recipe_map.values())), ('binaryCount', sum(e['mode'] == 'binary' for e in recipe_map.values()))]:
            if summary.get(field) != value:
                raise mods.ModError(f'Input build {field} differs from its recipe coverage')
        paths, names = {}, set()
        for entry in entries:
            name = entry['fileName']
            mods.safe_path(root, name)
            if '/' in name or not name.endswith('.jar') or name.casefold() in names:
                raise mods.ModError('Unsafe or duplicate input JAR filename')
            names.add(name.casefold())
            identity = entry['modId']
            if recipe_map[identity]['mode'] == 'source':
                receipt = provenance_map[identity]
                if not entry['artifact'].get('builtFromSource') or receipt.get('run') != summary['run'] or receipt.get('sha256') != entry['sha256']:
                    raise mods.ModError(f'Input source provenance differs: {identity}')
            archive_name = 'mods/' + name
            if archive_name not in members:
                raise mods.ModError(f'Input ZIP JAR missing: {name}')
            target = work / 'input' / name
            copy_member(archive, members[archive_name], target, entry)
            checked_jar(root, target, entry)
            paths[identity] = target
        if {n for n in members if n.startswith('mods/') and not members[n].is_dir()} != {'mods/' + e['fileName'] for e in entries}:
            raise mods.ModError('Unrecorded mod file in input ZIP')
        notices = {}
        for name, info in members.items():
            if name.startswith('licenses/') and not info.is_dir():
                if info.file_size > 20 * mods.CHUNK_SIZE:
                    raise mods.ModError('Oversized legal notice')
                notices[name] = archive.read(info)
    return summary, manifest, recipe_map, provenance_map, paths, notices


def load_policy(root: Path, value: str, identities: set) -> dict:
    policy = builder.read_json(mods.safe_path(root, value))
    if policy.get('schemaVersion') != 1 or policy.get('minecraftVersion') != '1.20.4' or policy.get('timezone', 'Asia/Seoul') != 'Asia/Seoul':
        raise mods.ModError('Unsupported release policy schema/target/timezone')
    loader = policy.get('fabricLoaderVersion')
    if not isinstance(loader, str) or not re.fullmatch(r'\d+\.\d+\.\d+', loader) or not builder.version_satisfies(loader, '>=0.18.0'):
        raise mods.ModError('Release policy requires an exact Fabric Loader version >= 0.18.0')
    entries = policy.get('entries', [])
    if {e.get('modId') for e in entries} != identities or len(entries) != len(identities):
        raise mods.ModError('Release policy must cover every input mod exactly once')
    for entry in entries:
        if entry.get('distribution') not in ('embed', 'download', 'manual') or entry.get('artifact') not in ('built', 'baseline'):
            raise mods.ModError(f'Invalid distribution/artifact selection: {entry.get("modId")}')
        if not entry.get('reason') or not isinstance(entry.get('evidenceUrls'), list) or not entry['evidenceUrls']:
            raise mods.ModError('Each release decision requires a reason and evidence URLs')
        for url in entry['evidenceUrls']:
            https_url(url)
        if any(type(entry.get(side)) is not bool for side in ('server', 'client')):
            raise mods.ModError('Release side selections must be explicit booleans')
        if entry['distribution'] == 'download':
            https_url(entry.get('downloadUrl'), mrpack=entry['client'])
    for side in ('server', 'client'):
        if not any(e[side] for e in entries):
            raise mods.ModError(f'Release {side} profile has zero mods')
    return policy


def baseline_artifact(root: Path, entry: dict, decision: dict, work: Path) -> Path:
    path = mods.safe_path(root, entry['artifact']['path'])
    if path.exists():
        checked_jar(root, path, entry)
        return path
    url = decision.get('downloadUrl') or entry['artifact'].get('url')
    https_url(url)
    target = work / 'baseline' / entry['fileName']
    target.parent.mkdir(parents=True, exist_ok=True)
    with mods.download(url) as response, target.open('xb') as output:
        https_url(response.url)
        size = 0
        while block := response.read(mods.CHUNK_SIZE):
            size += len(block)
            if size > entry['size']:
                raise mods.ModError('Baseline download exceeds recorded byte size')
            output.write(block)
    checked_jar(root, target, entry)
    return target


def select_files(root, manifest, provenance, paths, policy, work):
    original = {e['modId']: e for e in mods.load_manifest(root)['entries'] if e['included']}
    built = {e['modId']: e for e in manifest['entries']}
    if set(original) != set(built):
        raise mods.ModError('Input build must cover every included baseline mod exactly once')
    selected = []
    for decision in policy['entries']:
        identity = decision['modId']
        if identity not in original:
            raise mods.ModError(f'Release mod missing from baseline: {identity}')
        entry = copy.deepcopy(original[identity] if decision['artifact'] == 'baseline' else built[identity])
        path = baseline_artifact(root, entry, decision, work) if decision['artifact'] == 'baseline' else paths[identity]
        metadata = checked_jar(root, path, entry)
        for side in ('client', 'server'):
            if decision[side] and metadata.get('environment', '*') not in ('*', side):
                raise mods.ModError(f'Release side conflicts with Fabric metadata: {identity} / {side}')
        if decision['distribution'] == 'embed':
            if entry['artifact']['redistribution'] not in ('allowed', 'modpack-only'):
                raise mods.ModError(f'Public embedding blocked by local-only artifact: {identity}')
            if decision['artifact'] == 'built' and provenance[identity].get('source', {}).get('workingTreeStatus'):
                raise mods.ModError(f'Public source link cannot represent a dirty build: {identity}')
        hashes = {name: hashlib.new(name) for name in ('sha1', 'sha512')}
        with path.open('rb') as stream:
            while block := stream.read(mods.CHUNK_SIZE):
                for digest in hashes.values():
                    digest.update(block)
        record = {'modId': identity, 'path': 'mods/' + entry['fileName'], 'version': entry['version'],
                  'sha256': entry['sha256'], 'size': entry['size'], 'hashes': {k: h.hexdigest() for k, h in hashes.items()},
                  **copy.deepcopy(decision), 'license': entry.get('license'), 'licenseUrl': entry.get('licenseUrl'),
                  'inputBuild': {'version': built[identity]['version'], 'sha256': built[identity]['sha256']},
                  'replacesBuiltArtifact': entry['sha256'] != built[identity]['sha256'],
                  'source': entry.get('source')}
        if record.get('source'):
            source = record['source']
            repository_url = source['url'].removesuffix('.git')
            record['sourceCommitUrl'] = repository_url + '/tree/' + source['commit']
            if decision['artifact'] == 'built' and entry['artifact'].get('builtFromSource'):
                record['sourceArchiveUrl'] = repository_url + '/archive/' + source['commit'] + '.zip'
                record['sourceHistoryUrl'] = repository_url + '/commits/' + source['commit']
                record['sourceCommitDate'] = mods.git(mods.safe_path(root, source['path']),
                                                      'show', '-s', '--format=%cI', source['commit'])
        selected.append((record, path, entry))
    for side in ('client', 'server'):
        filenames = [r['path'].casefold() for r, _, _ in selected if r[side]]
        if len(filenames) != len(set(filenames)):
            raise mods.ModError(f'Colliding filenames in {side} profile')
    return selected


def resource_pack(root: Path, lock_path: str, destination: Path) -> dict:
    lock = builder.read_json(mods.safe_path(root, lock_path))
    if lock.get('schemaVersion') != 1 or lock.get('minecraftVersion') != '1.20.4' or len(lock.get('entries', [])) != 1:
        raise mods.ModError('Expected one reviewed Minecraft 1.20.4 resource pack')
    entry = lock['entries'][0]
    mods.validate_source(root, {**entry, 'path': entry['sourcePath']}, 'resource pack')
    source = mods.safe_path(root, entry['sourcePath'])
    directory = mods.safe_path(source, entry['sourceDir'])
    if mods.git(source, 'rev-parse', 'HEAD') != entry['commit'] or mods.git(source, 'status', '--porcelain', '--untracked-files=normal'):
        raise mods.ModError('Resource pack source must be clean and at its reviewed commit')
    license_record = entry.get('license', {})
    if license_record.get('redistribution') not in ('owner-authorized', 'allowed', 'modpack-only'):
        raise mods.ModError('Resource pack lacks a recorded public redistribution permission')
    tracked = subprocess.run(['git', '-C', str(source), 'ls-files', '-z', '--', entry['sourceDir']], check=True, capture_output=True).stdout.decode('utf-8').split('\0')
    files = []
    for relative in filter(None, tracked):
        path = mods.safe_path(source, relative)
        name = path.relative_to(directory).as_posix()
        if name not in ('pack.mcmeta', 'pack.png') and not name.startswith('assets/'):
            raise mods.ModError(f'Non-game file in resource pack sourceDir: {name}')
        if not path.is_file():
            raise mods.ModError(f'Missing tracked resource: {relative}')
        files.append((name, path))
    if not any(name.startswith('assets/') for name, _ in files) or 'pack.mcmeta' not in {n for n, _ in files}:
        raise mods.ModError('Resource pack needs tracked pack.mcmeta and assets')
    metadata = builder.read_json(directory / 'pack.mcmeta')
    if metadata.get('pack', {}).get('pack_format') != 22 or entry.get('packFormat') != 22:
        raise mods.ModError('Minecraft 1.20.4 resource pack requires pack_format 22')
    with zipfile.ZipFile(destination, 'x', compression=zipfile.ZIP_DEFLATED) as archive:
        for name, path in sorted(files):
            archive.write(path, name)
        archive.writestr('MINEFED-COPYRIGHT.txt', '\n'.join(license_record.get('noticeText', [])) + '\n')
        archive.writestr('MINEFED-RESOURCE-PROVENANCE.json', json_bytes(entry))
    if mods.git(source, 'rev-parse', 'HEAD') != entry['commit'] or mods.git(source, 'status', '--porcelain', '--untracked-files=normal'):
        raise mods.ModError('Resource pack source changed while packaging')
    return {'id': entry['id'], 'commit': entry['commit'], 'packFormat': 22, 'gameFileCount': len(files), 'runtimeValidated': False}


def source_notices(records, version: str) -> str:
    lines = ['# License, source and modification notices', '',
             'These files retain their individual author licenses. No additional rights are granted.',
             'Minecraft startup and mod interaction have not been validated.', '',
             'Build instructions for this release: https://github.com/minefed/mods/tree/' + version + '/docs/BUILDING.md',
             'Exact build recipes for this release: https://github.com/minefed/mods/tree/' + version + '/inventory/build-recipes.json', '']
    for record in records:
        lines += [f"## {record['modId']} {record['version']}", '', f"License: {record.get('license')}",
                  f"License evidence: {record.get('licenseUrl')}", f"Distribution: {record['distribution']} / {record['artifact']}",
                  f"Decision: {record['reason']}", *record['evidenceUrls']]
        if record.get('sourceCommitUrl'):
            if record['artifact'] == 'built':
                lines += ['Managed source and build instructions: ' + record['sourceCommitUrl'],
                          'Minefed build/compatibility changes are recorded in this repository history at that exact commit.']
                if record.get('sourceArchiveUrl'):
                    lines += ['Corresponding source archive: ' + record['sourceArchiveUrl'],
                              'Commit date: ' + record['sourceCommitDate'],
                              'Modification history: ' + record['sourceHistoryUrl'],
                              'Minefed modifications include the build and compatibility changes in this history; upstream copyright notices remain in the source and JAR.']
            else:
                lines += ['Managed source reference (not asserted to produce this published binary): ' + record['sourceCommitUrl'],
                          'The original download and author license evidence identify the selected published artifact.']
        if record['replacesBuiltArtifact']:
            lines += [f"Explicit policy replacement: built {record['inputBuild']['version']} ({record['inputBuild']['sha256']})",
                      f"is replaced by the original published {record['version']} ({record['sha256']})."]
        lines.append('')
    return '\n'.join(lines)


def write_profile(root, destination, side, selected, notices, version, loader, resource):
    chosen = [(r, p, e) for r, p, e in selected if r[side]]
    records = [r for r, _, _ in chosen]
    prefix = 'overrides/' if side == 'client' else ''
    with zipfile.ZipFile(destination, 'x', compression=zipfile.ZIP_DEFLATED) as archive:
        for record, path, entry in chosen:
            if record['distribution'] == 'embed':
                # Recheck bytes immediately before writing, then validate outputs below.
                mods.check_bytes(path, entry)
                archive.write(path, prefix + record['path'])
        archive.writestr(prefix + 'download-manifest.json', json_bytes({'schemaVersion': 1, 'version': version, 'side': side, 'files': records}))
        archive.writestr(prefix + 'install-mods.py', INSTALLER)
        source_text = source_notices(records, version)
        archive.writestr(prefix + 'LICENSES.md', source_text)
        archive.writestr(prefix + 'SOURCES.md', source_text)
        archive.writestr(prefix + 'MINEFED-RELEASE.json', json_bytes({'version': version, 'side': side, 'minecraft': '1.20.4',
                          'fabricLoader': loader, 'runtimeValidated': False, 'files': records}))
        for name, content in notices.items():
            archive.writestr(prefix + name, content)
        manual = [r for r in records if r['distribution'] == 'manual']
        instructions = [f'Minefed {version} ({side})', '', 'Target: Minecraft 1.20.4, Java 17, Fabric Loader ' + loader,
                        'Run: python install-mods.py',
                        'The installer restores official downloads and verifies every required mod. Existing modified files are preserved.',
                        'A successful ZIP build does not verify Minecraft startup. Configure your own server; no EULA is accepted by this tool.', '']
        if manual:
            instructions += ['INSTALLATION IS INCOMPLETE UNTIL THESE REQUIRED FILES ARE INSTALLED:',
                             *[r['path'] + ': ' + r['reason'] + ' ' + ' '.join(r['evidenceUrls']) for r in manual], '']
        if side == 'client':
            instructions += ['Import this .mrpack in a Modrinth-compatible launcher.',
                             'Enable the included Minefed resource pack in Minecraft resource-pack settings.',
                             'Run install-mods.py from the imported instance to verify all required files.']
            archive.write(resource, f'overrides/resourcepacks/minefed-{version}.zip')
            downloads = [{'path': r['path'], 'hashes': r['hashes'], 'env': {'client': 'required', 'server': 'unsupported'},
                          'downloads': [r['downloadUrl']], 'fileSize': r['size']}
                         for r in records if r['distribution'] == 'download']
            archive.writestr('modrinth.index.json', json_bytes({'formatVersion': 1, 'game': 'minecraft', 'versionId': version,
                              'name': 'Minefed', 'files': downloads,
                              'dependencies': {'minecraft': '1.20.4', 'fabric-loader': loader}}))
        archive.writestr(prefix + 'INSTALL.txt', '\n'.join(instructions) + '\n')
    with zipfile.ZipFile(destination) as archive:
        zip_members(root, archive)
        if archive.testzip() is not None:
            raise mods.ModError(f'{side} output failed ZIP CRC validation')
        for record in records:
            if record['distribution'] == 'embed':
                digest = hashlib.sha256()
                with archive.open(prefix + record['path']) as stream:
                    while block := stream.read(mods.CHUNK_SIZE):
                        digest.update(block)
                if digest.hexdigest() != record['sha256']:
                    raise mods.ModError(f'Embedded output bytes changed: {record["modId"]}')
    return {'modCount': len(records), 'embeddedCount': sum(r['distribution'] == 'embed' for r in records),
            'downloadCount': sum(r['distribution'] == 'download' for r in records), 'manualCount': len(manual),
            'excludedModIds': [r['modId'] for r, _, _ in selected if not r[side]]}


def release(root: Path, result_json: str, version: str, policy_path: str = 'inventory/release-policy.json',
            output: str | None = None, resource_lock: str = 'inventory/resourcepacks.lock.json') -> Path:
    if not re.fullmatch(r'[0-9]{14}', version):
        raise mods.ModError('Release version must be yyyyMMddHHmmss in Asia/Seoul')
    try:
        timestamp = datetime.strptime(version, '%Y%m%d%H%M%S').replace(tzinfo=timezone(timedelta(hours=9)))
    except ValueError as exc:
        raise mods.ModError('Invalid release version date/time') from exc
    destination = mods.output_path(root, output or f'build/releases/{version}')
    if destination.exists():
        raise mods.ModError(f'Release output exists; left unchanged: {destination}')
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.release-work-', dir=destination.parent) as temporary:
        work = Path(temporary)
        summary, manifest, recipes, provenance, paths, notices = input_build(root, result_json, work)
        policy = load_policy(root, policy_path, set(paths))
        selected = select_files(root, manifest, provenance, paths, policy, work)
        publication = work / 'publication'
        publication.mkdir()
        resource = publication / 'resourcepack.zip'
        resource_info = resource_pack(root, resource_lock, resource)
        with zipfile.ZipFile(resource) as archive:
            zip_members(root, archive)
            if archive.testzip() is not None:
                raise mods.ModError('Resource pack failed CRC validation')
        profiles = {}
        for side, name in [('server', 'server.zip'), ('client', 'client.mrpack')]:
            profiles[side] = write_profile(root, publication / name, side, selected, notices, version,
                                          policy['fabricLoaderVersion'], resource)
        assets = []
        for kind, name, media in [('server', 'server.zip', 'application/zip'), ('client', 'client.mrpack', 'application/x-modrinth-modpack+zip'), ('resourcepack', 'resourcepack.zip', 'application/zip')]:
            digest, size = mods.file_digest(publication / name)
            assets.append({'kind': kind, 'name': name, 'path': (destination / name).relative_to(root).as_posix(), 'sha256': digest, 'size': size, 'mediaType': media})
        result = {'schemaVersion': 1, 'version': version, 'createdAt': timestamp.isoformat(), 'timezone': 'Asia/Seoul',
                  'inputBuild': summary, 'sourceInputZip': summary['path'], 'runtimeValidated': False,
                  'policySha256': mods.file_digest(mods.safe_path(root, policy_path))[0], 'assets': assets,
                  'profiles': profiles, 'resourcePack': resource_info, 'files': [r for r, _, _ in selected]}
        (publication / 'release-assets.json').write_bytes(json_bytes(result))
        # Publish the complete directory in one rename. Failed preparation exposes
        # none of the three assets. Cooperating publishers share a short OS lock.
        with builder._file_lock(destination.parent / '.release-publication.lock', 'Waiting for another release publication'):
            if destination.exists():
                raise mods.ModError(f'Release output exists; left unchanged: {destination}')
            os.rename(publication, destination)
    return destination / 'release-assets.json'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--result-json', default='build/distributions/latest.json')
    parser.add_argument('--version', required=True)
    parser.add_argument('--policy', default='inventory/release-policy.json')
    parser.add_argument('--resource-lock', default='inventory/resourcepacks.lock.json')
    parser.add_argument('--output')
    args = parser.parse_args(argv)
    try:
        print(release(ROOT, args.result_json, args.version, args.policy, args.output, args.resource_lock))
        return 0
    except (mods.ModError, OSError, ValueError, KeyError, zipfile.BadZipFile, subprocess.CalledProcessError) as exc:
        print(f'Release packaging failed: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
