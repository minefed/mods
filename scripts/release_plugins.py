"""Prepare reviewed server plugins separately from the Fabric mod build graph."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import re
from urllib.parse import urlparse
import zipfile

import mods


NOTICE_LIMIT = 20 * mods.CHUNK_SIZE
DESCRIPTORS = ('plugin.yml', 'bungee.yml', 'velocity-plugin.json')


def https_url(value) -> None:
    if not isinstance(value, str):
        raise mods.ModError('Server plugin requires a reviewed HTTPS URL')
    parsed = urlparse(value)
    if (parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password
            or re.search(r'\s|[\x00-\x1f]', value)):
        raise mods.ModError('Server plugin requires a reviewed HTTPS URL')


def text_notice(content: bytes, name: str) -> bytes:
    if not content or len(content) > NOTICE_LIMIT:
        raise mods.ModError('Empty or oversized server plugin notice: ' + name)
    try:
        decoded = content.decode('utf-8-sig')
    except UnicodeError as exc:
        raise mods.ModError('Server plugin notice must be UTF-8 text: ' + name) from exc
    if not decoded.strip() or '\x00' in decoded:
        raise mods.ModError('Server plugin notice must be nonempty text: ' + name)
    return content


def inspect_plugin(root: Path, path: Path, entry: dict) -> tuple[str | None, dict]:
    """Verify the exact JAR and inspect supported plugin descriptors, without Fabric."""
    staged = copy.deepcopy(entry)
    staged['artifact']['path'] = path.relative_to(root).as_posix()
    mods.check_artifact(root, staged)
    notices, versions, members = {}, set(), {}
    try:
        with zipfile.ZipFile(path) as archive:
            for info in archive.infolist():
                name = info.filename.rstrip('/') if info.is_dir() else info.filename
                mods.safe_path(root, name)
                key = name.casefold()
                if key in members or (info.external_attr >> 16) & 0o170000 == 0o120000:
                    raise mods.ModError('Duplicate or linked server plugin ZIP member: ' + name)
                members[key] = info
            if 'fabric.mod.json' in members:
                raise mods.ModError('Server plugin must not contain Fabric metadata: ' + entry['fileName'])
            descriptors = [members[name] for name in DESCRIPTORS if name in members]
            if not descriptors:
                raise mods.ModError('JAR has no supported server plugin descriptor: ' + entry['fileName'])
            for info in descriptors:
                if info.is_dir() or info.file_size > mods.CHUNK_SIZE:
                    raise mods.ModError('Invalid server plugin descriptor: ' + info.filename)
                content = archive.read(info).decode('utf-8-sig')
                if info.filename.casefold() == 'velocity-plugin.json':
                    metadata = json.loads(content)
                    if not isinstance(metadata, dict) or not all(
                            isinstance(metadata.get(field), str) and metadata[field].strip()
                            for field in ('id', 'version', 'main')):
                        raise mods.ModError('Invalid Velocity plugin descriptor')
                    versions.add(metadata['version'])
                else:
                    # Only inspect simple top-level scalar identity fields; do not execute YAML.
                    fields = {}
                    for field in ('name', 'version', 'main'):
                        match = re.search(r'^' + field + r':\s*([^\r\n]+)', content, re.MULTILINE)
                        if not match or not match.group(1).strip():
                            raise mods.ModError('Invalid server plugin descriptor: ' + info.filename)
                        fields[field] = match.group(1).strip().strip('\"\'')
                    versions.add(fields['version'])
            if len(versions) != 1:
                raise mods.ModError('Conflicting server plugin descriptor versions')
            version = versions.pop()
            if entry.get('version') is not None and entry['version'] != version:
                raise mods.ModError('Server plugin descriptor version differs from inventory')
            if archive.testzip() is not None:
                raise mods.ModError('Server plugin ZIP CRC validation failed')
            for info in members.values():
                if info.is_dir() or not mods.is_notice(info.filename):
                    continue
                if info.file_size > NOTICE_LIMIT:
                    raise mods.ModError('Oversized server plugin notice: ' + info.filename)
                target = 'licenses/server-plugins/' + entry['fileName'] + '/jar/' + info.filename
                notices[target] = text_notice(archive.read(info), info.filename)
            return version, notices
    except (OSError, ValueError, UnicodeError, zipfile.BadZipFile) as exc:
        raise mods.ModError('Cannot inspect server plugin: ' + entry['fileName'] + ': ' + str(exc)) from exc


def artifact(root: Path, entry: dict, work: Path) -> Path:
    local = mods.safe_path(root, entry['artifact']['path'])
    if local.exists():
        return local
    relative = (work / 'server-plugins' / entry['fileName']).relative_to(root).as_posix()
    target = mods.safe_path(root, relative)
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        with mods.download(entry['artifact']['url']) as response, target.open('xb') as output:
            https_url(response.url)
            size = 0
            while block := response.read(mods.CHUNK_SIZE):
                size += len(block)
                if size > entry['size']:
                    raise mods.ModError('Server plugin download exceeds recorded byte size')
                output.write(block)
    except FileExistsError as exc:
        raise mods.ModError('Server plugin staging file already exists; left unchanged') from exc
    return target


def prepare(root: Path, policy: dict, work: Path) -> tuple[list, dict]:
    """Return verified (record, path, entry) plugins and preserved legal notices."""
    root = root.resolve()
    decisions = policy.get('serverPlugins', [])
    if not isinstance(decisions, list):
        raise mods.ModError('serverPlugins must be an array')
    if not decisions:
        return [], {}
    baseline = mods.load_manifest(root)['entries']
    selected, notices, names = [], {}, set()
    for decision in decisions:
        if not isinstance(decision, dict):
            raise mods.ModError('Server plugin decisions must be objects')
        name = decision.get('fileName')
        mods.safe_path(root, name)
        if '/' in name or not name.lower().endswith('.jar'):
            raise mods.ModError('Expected a plain server plugin JAR filename')
        if name.casefold() in names:
            raise mods.ModError('Duplicate server plugin selection: ' + name)
        names.add(name.casefold())
        matches = [entry for entry in baseline if entry['fileName'] == name]
        if len(matches) != 1 or matches[0]['included'] or matches[0].get('modId') is not None:
            raise mods.ModError('Server plugin must match one excluded non-Fabric inventory entry: ' + name)
        entry = copy.deepcopy(matches[0])
        if entry['artifact']['redistribution'] not in ('allowed', 'modpack-only'):
            raise mods.ModError('Public server plugin embedding blocked by local-only artifact: ' + name)
        https_url(entry['artifact'].get('url'))
        https_url(entry.get('licenseUrl'))
        if not isinstance(entry.get('license'), str) or not entry['license'].strip():
            raise mods.ModError('Server plugin requires a recorded license')
        if not isinstance(decision.get('reason'), str) or not decision['reason'].strip():
            raise mods.ModError('Server plugin decision requires a reason')
        evidence = decision.get('evidenceUrls')
        if not isinstance(evidence, list) or not evidence:
            raise mods.ModError('Server plugin decision requires evidence URLs')
        for url in evidence:
            https_url(url)
        notice_paths = decision.get('noticePaths')
        if not isinstance(notice_paths, list) or not notice_paths:
            raise mods.ModError('Server plugin requires reviewed noticePaths')
        reviewed = {}
        for relative in notice_paths:
            notice = mods.safe_path(root, relative)
            if not mods.is_notice(relative):
                raise mods.ModError('Server plugin notice path must identify a legal notice: ' + relative)
            if not notice.is_file() or notice.stat().st_size > NOTICE_LIMIT:
                raise mods.ModError('Missing or oversized server plugin notice: ' + relative)
            target = 'licenses/server-plugins/' + name + '/reviewed/' + relative
            if target.casefold() in {key.casefold() for key in reviewed}:
                raise mods.ModError('Duplicate server plugin notice path: ' + relative)
            reviewed[target] = text_notice(notice.read_bytes(), relative)
        path = artifact(root, entry, work.resolve())
        version, jar_notices = inspect_plugin(root, path, entry)
        record = {'id': name, 'path': 'plugins/' + name, 'version': version,
                  'sha256': entry['sha256'], 'size': entry['size'],
                  'license': entry['license'], 'licenseUrl': entry['licenseUrl'],
                  'artifactUrl': entry['artifact']['url'], 'artifact': 'baseline',
                  'distribution': 'embed', 'server': True, 'client': False,
                  'reason': decision['reason'], 'evidenceUrls': copy.deepcopy(evidence),
                  'noticePaths': list(reviewed)}
        for field in ('notes', 'authors', 'source'):
            if field in entry:
                record[field] = copy.deepcopy(entry[field])
        notices.update(jar_notices)
        notices.update(reviewed)
        selected.append((record, path, entry))
    return selected, notices
