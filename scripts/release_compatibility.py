"""Package the committed, resource-only compatibility mod without third-party textures."""
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile

import mods

SOURCE = 'compatibility/resource-fixes'
FILES = {
    'fabric.mod.json', 'LICENSE', 'NOTICE.md',
    'assets/mythicmetals_decorations/models/block/hydrargym_chest.json',
    'assets/mythicmetals_decorations/models/item/hydrargym_chest.json',
    'data/diagonalfences/tags/blocks/non_diagonal_fences.json',
}


def prepare(root: Path, policy: dict, work: Path):
    enabled = policy.get('resourceCompatibilityMod', False)
    if not isinstance(enabled, bool):
        raise mods.ModError('resourceCompatibilityMod must be boolean')
    if not enabled:
        return []
    source = mods.safe_path(root, SOURCE)
    actual = {p.relative_to(source).as_posix() for p in source.rglob('*') if p.is_file()}
    if actual != FILES:
        raise mods.ModError('Compatibility mod must contain exactly the reviewed JSON and notices')
    if mods.git(root, 'status', '--porcelain', '--untracked-files=normal', '--', SOURCE):
        raise mods.ModError('Compatibility input must match its committed source')
    commit = mods.git(root, 'rev-parse', 'HEAD')
    contents = {}
    for name in sorted(FILES):
        tracked = subprocess.run(['git', '-C', str(root), 'show', f'{commit}:{SOURCE}/{name}'],
                                 capture_output=True, check=False)
        if tracked.returncode:
            raise mods.ModError('Compatibility input must match its committed source: ' + name)
        # Read Git bytes, so Windows CRLF checkout conversion cannot alter the JAR.
        data = tracked.stdout
        if name.endswith('.json'):
            json.loads(data)
        contents[name] = data
    metadata = json.loads(contents['fabric.mod.json'])
    if (metadata.get('id') != 'minefed_resource_fixes' or metadata.get('environment') != '*'
            or any(k in metadata for k in ('entrypoints', 'mixins', 'jars'))):
        raise mods.ModError('Compatibility mod must be resource-only and available on both sides')
    filename = f"minefed-resource-fixes-{metadata['version']}.jar"
    path = work / filename
    with zipfile.ZipFile(path, 'x', compression=zipfile.ZIP_DEFLATED) as jar:
        for name, data in contents.items():
            info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            jar.writestr(info, data)
    digest, size = mods.file_digest(path)
    source_url = f'https://github.com/minefed/mods/tree/{commit}/{SOURCE}'
    record = {
        'modId': metadata['id'], 'version': metadata['version'], 'path': 'mods/' + filename,
        'sha256': digest, 'size': size,
        'hashes': {h: hashlib.new(h, path.read_bytes()).hexdigest() for h in ('sha1', 'sha512')},
        'artifact': 'compatibility', 'distribution': 'embed', 'archiveIncluded': True,
        'artifactRedistribution': 'allowed', 'client': True, 'server': True,
        'license': 'MIT', 'licenseUrl': source_url + '/LICENSE',
        'reason': 'Resource-only Minefed overrides for the original Diagonal Fences and Mythic Metals Decorations JARs. Includes JSON and author notices, no third-party textures or executable classes.',
        'evidenceUrls': [source_url, source_url + '/NOTICE.md'],
        'authors': metadata['authors'], 'replacesBuiltArtifact': False,
        'sourceCommitUrl': source_url,
        'source': {'path': SOURCE, 'url': 'https://github.com/minefed/mods', 'commit': commit},
        'sourceFiles': {n: hashlib.sha256(data).hexdigest() for n, data in contents.items()},
    }
    return [(record, path, {'fileName': filename, 'sha256': digest, 'size': size})]
