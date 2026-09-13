"""Verify and bundle pinned client resource packs without changing upstream ZIPs."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import re
import zipfile

import build_modpack as builder
import mods


def prepare(root: Path, lock_path: str, work: Path, selected) -> tuple[list, dict, dict]:
    lock_file = mods.safe_path(root, lock_path)
    snapshot = {'path': lock_path, 'sha256': mods.file_digest(lock_file)[0]}
    lock = builder.read_json(lock_file)
    if lock.get('schemaVersion') != 1 or lock.get('minecraftVersion') != '1.20.4':
        raise mods.ModError('Client resource packs require the Minecraft 1.20.4 resource lock')
    entries = lock.get('clientPacks', [])
    if not isinstance(entries, list):
        raise mods.ModError('clientPacks must be an array')
    builtin = lock.get('clientDefaults', {}).get('builtInResourcePacks', [])
    if not isinstance(builtin, list) or len(builtin) != len(set(builtin)):
        raise mods.ModError('Client built-in resource packs must be a unique list')
    clients = {record['modId']: path for record, path, _ in selected if record['client']}
    for identity in builtin:
        if not isinstance(identity, str) or not re.fullmatch(r'[a-z][a-z0-9_-]*:[a-z0-9_-]+', identity):
            raise mods.ModError('Invalid built-in resource pack ID')
        namespace, name = identity.split(':')
        if namespace not in clients:
            raise mods.ModError('Built-in resource pack requires a selected client mod: ' + identity)
        with zipfile.ZipFile(clients[namespace]) as archive:
            if f'resourcepacks/{name}/pack.mcmeta' not in archive.namelist():
                raise mods.ModError('Built-in resource pack is absent from the selected JAR: ' + identity)
    prepared, notices, names, ids = [], {}, set(), set()
    for entry in entries:
        name = entry.get('fileName')
        mods.safe_path(root, name)
        if '/' in name or not name.endswith('.zip') or name.casefold().startswith('minefed-'):
            raise mods.ModError('Client resource pack needs a distinct plain ZIP filename')
        identity = entry.get('id')
        if not isinstance(identity, str) or not re.fullmatch(r'[a-z][a-z0-9_-]+', identity):
            raise mods.ModError('Invalid client resource pack ID')
        if name.casefold() in names or identity in ids:
            raise mods.ModError('Duplicate client resource pack')
        names.add(name.casefold())
        ids.add(identity)
        if not entry.get('version') or '1.20.4' not in entry.get('gameVersions', []):
            raise mods.ModError('Client resource pack must have reviewed 1.20.4 compatibility')
        if (type(entry.get('enabledByDefault')) is not bool or
                type(entry.get('allowIncompatibleFormat', False)) is not bool):
            raise mods.ModError('Client resource pack defaults must be explicit booleans')
        for algorithm, length in [('sha256', 64), ('sha512', 128)]:
            if not re.fullmatch(r'[0-9a-f]{' + str(length) + '}', str(entry.get(algorithm, ''))):
                raise mods.ModError('Client resource pack requires ' + algorithm)
        if type(entry.get('size')) is not int or entry['size'] <= 0:
            raise mods.ModError('Client resource pack requires a positive byte size')
        legal = entry.get('license', {})
        if (legal.get('redistribution') not in ('allowed', 'modpack-only') or not legal.get('id')
                or not legal.get('noticeText') or not entry.get('authors')):
            raise mods.ModError('Client resource pack requires reviewed redistribution permission and attribution')
        evidence = entry.get('evidenceUrls')
        if not isinstance(evidence, list) or not evidence:
            raise mods.ModError('Client resource pack requires official evidence URLs')
        artifact = entry['artifact']
        for url in [artifact.get('url'), legal.get('url'), *evidence]:
            mods.validate_url(url)
        path = mods.safe_path(root, artifact.get('path'))
        if path.name != name or not any(path.is_relative_to(root / folder) for folder in mods.ARTIFACT_DIRS):
            raise mods.ModError('Client resource pack path must use an artifact directory and its pinned filename')
        if not path.exists():
            path = work / 'client-resourcepacks' / name
            path.parent.mkdir(parents=True, exist_ok=True)
            with mods.download(artifact['url']) as response, path.open('xb') as output:
                mods.validate_url(response.url)
                size = 0
                while block := response.read(mods.CHUNK_SIZE):
                    size += len(block)
                    if size > entry['size']:
                        raise mods.ModError('Client resource pack download exceeds pinned size')
                    output.write(block)
        mods.check_bytes(path, entry)
        with path.open('rb') as stream:
            digest = hashlib.sha512()
            for block in iter(lambda: stream.read(mods.CHUNK_SIZE), b''):
                digest.update(block)
            if digest.hexdigest() != entry['sha512']:
                raise mods.ModError('Client resource pack SHA-512 mismatch')
        with zipfile.ZipFile(path) as archive:
            seen = set()
            for info in archive.infolist():
                member = info.filename.rstrip('/') if info.is_dir() else info.filename
                mods.safe_path(root, member)
                if member.casefold() in seen or (info.external_attr >> 16) & 0o170000 == 0o120000:
                    raise mods.ModError('Duplicate or linked client resource pack ZIP member')
                seen.add(member.casefold())
            if not any(name.startswith('assets/') for name in seen):
                raise mods.ModError('Client resource pack has no assets')
            if 'pack.mcmeta' not in archive.namelist() or archive.getinfo('pack.mcmeta').file_size > mods.CHUNK_SIZE:
                raise mods.ModError('Client resource pack is missing valid root pack.mcmeta')
            metadata = json.loads(archive.read('pack.mcmeta').decode('utf-8-sig'))
            pack_format = metadata.get('pack', {}).get('pack_format')
            if type(pack_format) is not int or pack_format != entry.get('packFormat'):
                raise mods.ModError('Client resource pack format differs from its reviewed metadata')
            if pack_format != 22 and not entry.get('allowIncompatibleFormat'):
                raise mods.ModError('Non-1.20.4 resource pack format needs explicit compatibility review')
            if archive.testzip() is not None:
                raise mods.ModError('Client resource pack ZIP CRC validation failed')
            for info in archive.infolist():
                if not info.is_dir() and mods.is_notice(info.filename):
                    if info.file_size > 20 * mods.CHUNK_SIZE:
                        raise mods.ModError('Oversized client resource pack notice')
                    notices[f'licenses/client-resourcepacks/{identity}/upstream/{info.filename}'] = archive.read(info)
        for notice in legal.get('documents', []):
            source = mods.safe_path(root, notice['path'])
            if source.stat().st_size > 20 * mods.CHUNK_SIZE or mods.file_digest(source)[0] != notice['sha256']:
                raise mods.ModError('Reviewed client resource pack notice changed')
            notices[f'licenses/client-resourcepacks/{identity}/reviewed/{source.name}'] = source.read_bytes()
        record = {**copy.deepcopy(entry), 'path': 'resourcepacks/' + name,
                  'downloadUrl': artifact['url'], 'archiveIncluded': True}
        notices[f'licenses/client-resourcepacks/{identity}/provenance.json'] = (
            json.dumps(record, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
        prepared.append((record, path, entry))
    if mods.file_digest(lock_file)[0] != snapshot['sha256']:
        raise mods.ModError('Resource pack manifest changed during preparation')
    snapshot['builtInResourcePacks'] = builtin
    return prepared, notices, snapshot


def options(records: list[dict], version: str, builtin: list[str]) -> str:
    """Defaults for a newly imported instance; upstream archives stay byte-identical."""
    enabled = [record for record in records if record['enabledByDefault']]
    packs = ['vanilla', 'fabric', *builtin, *['file/' + r['fileName'] for r in enabled],
             f'file/minefed-{version}.zip']
    incompatible = ['file/' + r['fileName'] for r in enabled if r.get('allowIncompatibleFormat')]
    return ('resourcePacks:' + json.dumps(packs, ensure_ascii=False, separators=(',', ':')) + '\n'
            + 'incompatibleResourcePacks:' + json.dumps(incompatible, ensure_ascii=False, separators=(',', ':')) + '\n')
