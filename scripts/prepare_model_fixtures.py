#!/usr/bin/env python3
"""Prepare hash-pinned model probes independently of Gradle/Loom worker caches.

Only a local, ignored build directory receives downloaded or remapped JARs.
The official client contains all classes used by these client-only probes; a
server merge and other mods' builds are unnecessary. Production-class pins in
the Java probes remain a separate check and are never changed by this tool.
"""

from __future__ import annotations

import argparse
from contextlib import nullcontext
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import zipfile

import build_modpack as builder
import mods

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = 'scripts/model-probe-fixtures.json'
SCRIPT = 'scripts/prepare_model_fixtures.py'
DIRECTORY = 'build/compatibility-fixtures'
MINECRAFT = 'minecraft-1.20.4-intermediary.jar'
SCENA = 'scena-fabric-1.0.141.jar'
PROBE_TASKS = frozenset({'verifyModelVariantMixin', 'verifyModelRotation', 'verifyScenaModelCache'})
CLASSES = ('net/minecraft/class_1088.class', 'net/minecraft/class_796.class',
           'net/minecraft/class_796$1.class', 'net/minecraft/class_789.class')


def load_manifest(root: Path) -> dict:
    data = builder.read_json(mods.safe_path(root, MANIFEST))
    if data.get('schemaVersion') != 1 or data.get('minecraftVersion') != '1.20.4':
        raise mods.ModError('Unsupported model probe fixture manifest')
    artifacts = data.get('artifacts', {})
    if set(artifacts) != {'minecraft', 'mappings', 'remapper', 'scena'}:
        raise mods.ModError('Model probe fixtures require exactly four reviewed artifacts')
    names = set()
    for artifact in artifacts.values():
        name = artifact.get('fileName', '')
        if '/' in name or name in names or not name.endswith('.jar'):
            raise mods.ModError('Invalid or duplicate model fixture filename')
        mods.safe_path(root, DIRECTORY + '/downloads/' + name)
        names.add(name)
        if (type(artifact.get('size')) is not int or artifact['size'] <= 0 or
                not isinstance(artifact.get('sha256'), str) or
                len(artifact['sha256']) != 64 or
                any(c not in '0123456789abcdef' for c in artifact['sha256'])):
            raise mods.ModError('Model fixture requires a reviewed size and SHA-256')
        mods.validate_url(artifact.get('url'))
        if not artifact.get('license') or not artifact.get('licenseUrl') or not artifact.get('source'):
            raise mods.ModError('Model fixture requires source and license evidence')
    return data


def directory(root: Path) -> Path:
    return mods.output_path(root, DIRECTORY)


def fixture_lock(root: Path):
    return builder._file_lock(mods.output_path(root, DIRECTORY + '/prepare.lock'),
                              'Waiting for model probe fixture preparation')


def download_artifacts(root: Path, manifest: dict) -> dict[str, Path]:
    paths = {}
    for key, artifact in manifest['artifacts'].items():
        path = mods.output_path(root, DIRECTORY + '/downloads/' + artifact['fileName'])
        paths[key] = path
        if path.exists():
            mods.check_bytes(path, artifact)
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        # A temporary sibling is published only after its complete bytes match.
        with tempfile.NamedTemporaryFile(dir=path.parent, suffix='.part', delete=False) as output:
            temporary = Path(output.name)
            try:
                with mods.download(artifact['url']) as response:
                    total = 0
                    while block := response.read(min(mods.CHUNK_SIZE, artifact['size'] - total + 1)):
                        total += len(block)
                        if total > artifact['size']:
                            raise mods.ModError('Download larger than recorded fixture: ' + artifact['fileName'])
                        output.write(block)
                output.flush()
                os.fsync(output.fileno())
            except BaseException:
                output.close()
                temporary.unlink(missing_ok=True)
                raise
        try:
            mods.check_bytes(temporary, artifact)
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)
    return paths


def generator_inputs(root: Path, manifest: dict) -> dict:
    return {
        'schemaVersion': 1,
        'minecraftVersion': manifest['minecraftVersion'],
        'generatorSha256': mods.file_digest(mods.safe_path(root, SCRIPT))[0],
        'manifestSha256': mods.file_digest(mods.safe_path(root, MANIFEST))[0],
        'artifacts': {key: {'sha256': value['sha256'], 'size': value['size']}
                      for key, value in manifest['artifacts'].items()},
    }


def describe(path: Path) -> dict:
    digest, size = mods.file_digest(path)
    return {'fileName': path.name, 'sha256': digest, 'size': size}


def class_hashes(path: Path) -> dict:
    with zipfile.ZipFile(path) as jar:
        if json.loads(jar.read('version.json'))['id'] != '1.20.4':
            raise mods.ModError('Remapped fixture is not Minecraft 1.20.4')
        return {name: hashlib.sha256(jar.read(name)).hexdigest() for name in CLASSES}


def check_receipt(root: Path, expected: dict) -> dict:
    base = directory(root)
    receipt_path = mods.output_path(root, DIRECTORY + '/receipt.json')
    if not receipt_path.is_file():
        raise mods.ModError('Model probe fixtures are missing; run scripts/prepare_model_fixtures.py prepare')
    receipt = builder.read_json(receipt_path)
    if receipt.get('inputs') != expected:
        raise mods.ModError('Model probe fixture generator changed; run scripts/prepare_model_fixtures.py prepare')
    outputs = receipt.get('outputs', {})
    if set(outputs) != {MINECRAFT, SCENA}:
        raise mods.ModError('Model probe fixture receipt has unexpected outputs')
    for name, recorded in outputs.items():
        path = mods.output_path(root, DIRECTORY + '/' + name)
        if recorded.get('fileName') != name:
            raise mods.ModError('Model probe fixture receipt filename mismatch')
        mods.check_bytes(path, recorded)
    if class_hashes(base / MINECRAFT) != receipt.get('minecraftClassSha256'):
        raise mods.ModError('Model probe fixture class hashes do not match the receipt')
    # Scena's hash is an independent upstream pin, not just a generated receipt.
    mods.check_bytes(base / SCENA, {'fileName': SCENA, **expected['artifacts']['scena']})
    return receipt


def fingerprint(root: Path) -> dict:
    """Used by source-build receipts, including cache hits and final rechecks."""
    with fixture_lock(root):
        return check_receipt(root, generator_inputs(root, load_manifest(root)))


def remap_command(java: Path, paths: dict, mappings: Path, output: Path) -> list[str]:
    # Keep debug/stack frames and normal propagation; do not ignore conflicts.
    return [str(java), '-Xmx768m', '-XX:ActiveProcessorCount=2', '-Dfile.encoding=UTF-8',
            '-jar', str(paths['remapper']), str(paths['minecraft']), str(output),
            str(mappings), 'official', 'intermediary', '--threads=2']


def prepare(root: Path, *, download_only: bool = False) -> dict | None:
    # Source builds recheck fingerprints while holding the Gradle lock. Keep
    # that same lock order here, otherwise two invocations could deadlock.
    heavy_lock = nullcontext() if download_only else builder.gradle_cache_lock(root)
    with heavy_lock, fixture_lock(root):
        manifest = load_manifest(root)
        expected = generator_inputs(root, manifest)
        receipt_path = mods.output_path(root, DIRECTORY + '/receipt.json')
        if not download_only and receipt_path.is_file():
            existing = builder.read_json(receipt_path)
            if existing.get('inputs') == expected:
                return check_receipt(root, expected)
        paths = download_artifacts(root, manifest)
        if download_only:
            return None
        base = directory(root)
        with tempfile.TemporaryDirectory(prefix='prepare-', dir=base) as temporary:
            staging = Path(temporary)
            mappings = staging / 'mappings.tiny'
            with zipfile.ZipFile(paths['mappings']) as jar:
                content = jar.read('mappings/mappings.tiny')
            if content.splitlines()[0] != b'tiny\t2\t0\tofficial\tintermediary':
                raise mods.ModError('Expected Fabric intermediary v2 official -> intermediary mapping')
            mappings.write_bytes(content)
            minecraft = staging / MINECRAFT
            java = builder.java_home(root, 17) / 'bin' / ('java.exe' if os.name == 'nt' else 'java')
            log_path = base / 'remap.log'
            # Serialize with the pack's other heavy Java work, even though no
            # Loom cache is used. Failed/cancelled processes publish no receipt.
            with log_path.open('w', encoding='utf-8') as log:
                result = subprocess.run(remap_command(java, paths, mappings, minecraft),
                                        cwd=root, stdout=log, stderr=subprocess.STDOUT,
                                        stdin=subprocess.DEVNULL, timeout=300)
            if result.returncode:
                raise mods.ModError('Minecraft fixture remapping failed; see build/compatibility-fixtures/remap.log')
            hashes = class_hashes(minecraft)
            scena = staging / SCENA
            shutil.copyfile(paths['scena'], scena)
            mods.check_bytes(scena, manifest['artifacts']['scena'])
            receipt = {'inputs': expected, 'outputs': {p.name: describe(p) for p in (minecraft, scena)},
                       'minecraftClassSha256': hashes}
            for path in (minecraft, scena):
                os.replace(path, mods.output_path(root, DIRECTORY + '/' + path.name))
            pending = staging / 'receipt.json'
            builder.write_json(pending, receipt)
            os.replace(pending, receipt_path)
        return check_receipt(root, expected)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('prepare', 'check', 'download'))
    args = parser.parse_args(argv)
    try:
        if args.command == 'check':
            fingerprint(ROOT)
        else:
            prepare(ROOT, download_only=args.command == 'download')
        print('Verified model probe fixture ' + ('downloads' if args.command == 'download' else 'outputs'))
        return 0
    except (mods.ModError, OSError, ValueError, KeyError, zipfile.BadZipFile,
            subprocess.SubprocessError) as error:
        print('ERROR: ' + str(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
