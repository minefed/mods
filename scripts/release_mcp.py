"""Build a loopback-only observation derivative of the pinned Minecraft MCP JAR."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import zipfile

import build_modpack as builder
import mods

ROOT = Path(__file__).resolve().parents[1]
LOCK = 'inventory/minecraft-mcp.lock.json'
SOURCE = 'compatibility/minecraft-mcp'
SERVER = 'xyz/langyo/minecraft/mcp/common/McpHttpServer'
SOURCE_FILES = {'LICENSE-MIT', 'LICENSE-APACHE', 'LICENSE-CC0', 'NOTICE.md', 'src/' + SERVER + '.java'}


def pinned_input(root, entry):
    cache = mods.safe_path(root, '.cache/minecraft-mcp-inputs')
    cache.mkdir(parents=True, exist_ok=True)
    name = entry['fileName']
    if Path(name).name != name or not name.endswith('.jar'):
        raise mods.ModError('Invalid Minecraft MCP input filename')
    destination = mods.safe_path(cache, name)
    if destination.exists():
        mods.check_bytes(destination, entry)
        return destination
    local = mods.safe_path(root, 'artifacts/local/' + name)
    if local.is_file():
        mods.check_bytes(local, entry)
        data = local.read_bytes()
    else:
        with mods.download(entry['url']) as response:
            data = response.read(entry['size'] + 1)
    if len(data) != entry['size'] or hashlib.sha256(data).hexdigest() != entry['sha256']:
        raise mods.ModError('Minecraft MCP input hash/size mismatch: ' + name)
    with tempfile.NamedTemporaryFile(dir=cache, suffix='.part', delete=False) as stream:
        temporary = Path(stream.name)
        stream.write(data)
    try:
        try:
            mods.publish_new(temporary, destination)
        except mods.ModError:
            if not destination.exists():
                raise
        mods.check_bytes(destination, entry)
    finally:
        temporary.unlink(missing_ok=True)
    return destination


def build(root, work, *, require_committed=True):
    root, work = Path(root).resolve(), Path(work).resolve()
    lock_path = mods.safe_path(root, LOCK)
    lock = json.loads(lock_path.read_text(encoding='utf-8'))
    if (lock.get('schemaVersion'), lock.get('modId'), lock.get('minecraftVersion'), lock.get('loader'),
            lock.get('client'), lock.get('server')) != (1, 'mcpmod', '1.20.4', 'fabric', True, False):
        raise mods.ModError('Minecraft MCP must remain a reviewed client-only Minecraft 1.20.4 Fabric mod')
    source = mods.safe_path(root, SOURCE)
    if {p.relative_to(source).as_posix() for p in source.rglob('*') if p.is_file()} != SOURCE_FILES:
        raise mods.ModError('Minecraft MCP source files differ from the reviewed set')
    if require_committed and mods.git(root, 'status', '--porcelain', '--untracked-files=normal', '--', SOURCE, LOCK, 'scripts/release_mcp.py'):
        raise mods.ModError('Minecraft MCP inputs must match committed source before packaging')
    commit = mods.git(root, 'rev-parse', 'HEAD')
    # Canonical LF bytes avoid Windows checkout conversion changing the output.
    contents = {n: (source / n).read_bytes().replace(b'\r\n', b'\n') for n in sorted(SOURCE_FILES)}
    upstream = pinned_input(root, lock['upstream'])
    gson = pinned_input(root, lock['compileDependency'])
    work.mkdir(parents=True, exist_ok=True)
    name = lock['fileName']
    output = mods.safe_path(work, name)
    if output.exists():
        raise mods.ModError('Minecraft MCP output exists; left unchanged')
    with tempfile.TemporaryDirectory(prefix='mcp-compile-', dir=work) as temporary:
        temp = Path(temporary)
        java_source = temp / 'McpHttpServer.java'
        java_source.write_bytes(contents['src/' + SERVER + '.java'])
        classes = temp / 'classes'
        classes.mkdir()
        java = builder.java_home(root, 17) / 'bin' / ('javac.exe' if os.name == 'nt' else 'javac')
        result = subprocess.run([str(java), '--release', '17', '-g:none', '-encoding', 'UTF-8', '-classpath',
                                 os.pathsep.join(map(str, (upstream, gson))), '-d', str(classes), str(java_source)],
                                capture_output=True, text=True, encoding='utf-8')
        if result.returncode:
            raise mods.ModError('Minecraft MCP compilation failed: ' + result.stderr)
        with zipfile.ZipFile(upstream) as original:
            if original.testzip() is not None:
                raise mods.ModError('Minecraft MCP upstream CRC failure')
            payload = {n: original.read(n) for n in original.namelist() if not n.endswith('/')
                       and not (n.startswith(SERVER + '$') or n == SERVER + '.class')}
        metadata = json.loads(payload['fabric.mod.json'])
        if (metadata.get('id'), metadata.get('version'), metadata.get('environment')) != ('mcpmod', '0.3.0', 'client'):
            raise mods.ModError('Unexpected upstream Minecraft MCP Fabric metadata')
        metadata.update(version=lock['version'], name='Minecraft Mod MCP (Minefed observation)', license='MIT',
                        depends={'minecraft': '1.20.4', 'java': '>=17', 'fabricloader': '>=0.16.0'})
        payload['fabric.mod.json'] = (json.dumps(metadata, ensure_ascii=False, indent=2) + '\n').encode()
        for path in classes.rglob('*.class'):
            payload[path.relative_to(classes).as_posix()] = path.read_bytes()
        for name, data in contents.items():
            payload['META-INF/minefed/' + name] = data
        payload['META-INF/minefed/upstream.json'] = (json.dumps(lock, ensure_ascii=False, indent=2) + '\n').encode()
        with zipfile.ZipFile(output, 'x', compression=zipfile.ZIP_DEFLATED) as jar:
            for name, data in sorted(payload.items()):
                info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o644 << 16
                jar.writestr(info, data)
    digest, size = mods.file_digest(output)
    source_url = f'https://github.com/minefed/mods/tree/{commit}/{SOURCE}'
    record = {
        'modId': 'mcpmod', 'version': lock['version'], 'path': 'mods/' + output.name,
        'sha256': digest, 'size': size,
        'hashes': {h: hashlib.new(h, output.read_bytes()).hexdigest() for h in ('sha1', 'sha512')},
        'artifact': 'observation', 'distribution': 'embed', 'archiveIncluded': True,
        'artifactRedistribution': 'allowed', 'client': True, 'server': False,
        'license': lock['license'], 'licenseUrl': source_url + '/LICENSE-MIT', 'authors': lock['authors'],
        'reason': 'Client-only loopback observation derivative of Minecraft Mod MCP; HTTP input/control commands are disabled.',
        'evidenceUrls': [lock['upstream']['releaseUrl'], source_url + '/NOTICE.md'],
        'replacesBuiltArtifact': False, 'sourceCommitUrl': source_url,
        'source': {'path': SOURCE, 'url': 'https://github.com/minefed/mods', 'commit': commit},
        'sourceReference': lock['sourceReference'],
        'sourceFiles': {n: hashlib.sha256(data).hexdigest() for n, data in contents.items()},
        'upstreamArtifact': lock['upstream'], 'readOnly': True, 'bindAddress': '127.0.0.1',
    }
    return (record, output, {'fileName': output.name, 'sha256': digest, 'size': size}), {
        'path': LOCK, 'sha256': mods.file_digest(lock_path)[0]}


def prepare(root, policy, work):
    enabled = policy.get('minecraftMcpMod', False)
    if type(enabled) is not bool:
        raise mods.ModError('minecraftMcpMod must be boolean')
    if not enabled:
        return [], None
    artifact, snapshot = build(root, work)
    return [artifact], snapshot


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', default='build/minecraft-mcp')
    parser.add_argument('--allow-uncommitted', action='store_true', help='Local development only; release packaging requires committed inputs')
    args = parser.parse_args()
    selected, snapshot = build(ROOT, mods.output_path(ROOT, args.output), require_committed=not args.allow_uncommitted)
    report = {'file': str(selected[1]), 'record': selected[0], 'manifest': snapshot}
    (selected[1].parent / 'minecraft-mcp-build.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'path': str(selected[1]), 'sha256': selected[0]['sha256'], 'size': selected[0]['size']}))


if __name__ == '__main__':
    main()
