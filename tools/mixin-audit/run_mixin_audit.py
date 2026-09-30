#!/usr/bin/env python3
"""Apply every Mixin of a Fabric mod set in a real Knot launch, without starting the game.

Downloads the Minecraft 1.20.4 client, its libraries and the pinned Fabric Loader profile into a cache,
builds the probe mod, copies the given mods into a temporary game directory and runs Knot. The probe's
preLaunch entrypoint calls MixinEnvironment.audit(), which loads every target class and applies every
Mixin, and then halts the JVM. Exit code 0 means every Mixin applied.

Usage: run_mixin_audit.py --mods <dir with mod JARs> [--replace <jar> ...] [--side client|server]
"""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile

MINECRAFT_VERSION = '1.20.4'
LOADER_VERSION = '0.18.4'
HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(os.path.expanduser('~'), '.cache', 'minefed-mixin-audit')


def fetch(url, path, sha1=None):
    if os.path.exists(path) and (sha1 is None or hashlib.sha1(open(path, 'rb').read()).hexdigest() == sha1):
        return path
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with urllib.request.urlopen(url) as response, open(path + '.part', 'wb') as stream:
        shutil.copyfileobj(response, stream)
    if sha1 is not None and hashlib.sha1(open(path + '.part', 'rb').read()).hexdigest() != sha1:
        raise SystemExit(f'SHA-1 mismatch for {url}')
    os.replace(path + '.part', path)
    return path


def maven_path(name):
    group, artifact, version = name.split(':')[:3]
    return f"{group.replace('.', '/')}/{artifact}/{version}/{artifact}-{version}.jar"


def classpath(side):
    manifest = json.load(open(fetch('https://piston-meta.mojang.com/mc/game/version_manifest_v2.json', os.path.join(CACHE, 'version_manifest_v2.json'))))
    version_url = next(v['url'] for v in manifest['versions'] if v['id'] == MINECRAFT_VERSION)
    version = json.load(open(fetch(version_url, os.path.join(CACHE, f'{MINECRAFT_VERSION}.json'))))
    entries = []
    for library in version['libraries']:
        artifact = library.get('downloads', {}).get('artifact')
        rules = library.get('rules')
        if rules and not any(rule.get('action') == 'allow' and rule.get('os', {}).get('name') in (None, 'linux') for rule in rules):
            continue
        if artifact:
            entries.append(fetch(artifact['url'], os.path.join(CACHE, 'libraries', artifact['path']), artifact['sha1']))
    download = version['downloads'][side]
    game_jar = fetch(download['url'], os.path.join(CACHE, f'minecraft-{side}-{MINECRAFT_VERSION}.jar'), download['sha1'])
    profile = json.load(open(fetch(f'https://meta.fabricmc.net/v2/versions/loader/{MINECRAFT_VERSION}/{LOADER_VERSION}/profile/json', os.path.join(CACHE, f'fabric-{LOADER_VERSION}.json'))))
    for library in profile['libraries']:
        path = maven_path(library['name'])
        entries.append(fetch(library['url'] + path, os.path.join(CACHE, 'libraries', path), library.get('sha1')))
    return entries, game_jar


def build_probe(work, javac):
    classes = os.path.join(work, 'probe-classes')
    os.makedirs(classes)
    loader = os.path.join(CACHE, 'libraries', maven_path(f'net.fabricmc:fabric-loader:{LOADER_VERSION}'))
    mixin = os.path.join(CACHE, 'libraries', maven_path('net.fabricmc:sponge-mixin:0.17.0+mixin.0.8.7'))
    sources = [os.path.join(root, file) for root, _, files in os.walk(os.path.join(HERE, 'src')) for file in files if file.endswith('.java')]
    subprocess.run([javac, '--release', '17', '-proc:none', '-cp', os.pathsep.join([loader, mixin]), '-d', classes] + sources, check=True)
    jar = os.path.join(work, 'minefed-mixin-audit.jar')
    with zipfile.ZipFile(jar, 'w') as archive:
        archive.write(os.path.join(HERE, 'fabric.mod.json'), 'fabric.mod.json')
        for root, _, files in os.walk(classes):
            for file in files:
                archive.write(os.path.join(root, file), os.path.relpath(os.path.join(root, file), classes))
    return jar


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--mods', required=True, help='directory with the mod JARs to audit')
    parser.add_argument('--replace', action='append', default=[], help='JAR that replaces the JAR with the same mod ID')
    parser.add_argument('--side', choices=['client', 'server'], default='client')
    parser.add_argument('--jvm-arg', action='append', default=[], help='extra JVM argument, e.g. -Dmixin.debug.verbose=true')
    parser.add_argument('--java', default=os.path.join(os.environ.get('JAVA_HOME', ''), 'bin', 'java') if os.environ.get('JAVA_HOME') else 'java')
    args = parser.parse_args()
    entries, game_jar = classpath(args.side)
    javac = os.path.join(os.path.dirname(args.java), 'javac') if os.path.dirname(args.java) else 'javac'
    with tempfile.TemporaryDirectory(prefix='mixin-audit-') as work:
        game_dir = os.path.join(work, 'game')
        mods_dir = os.path.join(game_dir, 'mods')
        os.makedirs(mods_dir)

        def mod_id(jar):
            with zipfile.ZipFile(jar) as archive:
                return json.loads(archive.read('fabric.mod.json').decode('utf-8-sig'), strict=False)['id']

        replacements = {mod_id(jar): jar for jar in args.replace}
        for file in sorted(os.listdir(args.mods)):
            if file.endswith('.jar') and mod_id(os.path.join(args.mods, file)) not in replacements:
                shutil.copy(os.path.join(args.mods, file), mods_dir)
        for jar in replacements.values():
            shutil.copy(jar, mods_dir)
        shutil.copy(build_probe(work, javac), mods_dir)
        main_class = 'net.fabricmc.loader.impl.launch.knot.KnotClient' if args.side == 'client' else 'net.fabricmc.loader.impl.launch.knot.KnotServer'
        command = [args.java, '-Xmx3G'] + args.jvm_arg + [f'-Dfabric.gameJarPath={game_jar}', '-cp', os.pathsep.join(entries + [game_jar]), main_class]
        if args.side == 'client':
            command += ['--gameDir', game_dir, '--accessToken', '0', '--version', MINECRAFT_VERSION]
        result = subprocess.run(command, cwd=game_dir, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        output = result.stdout
        with open(os.path.join(HERE, f'last-audit-{args.side}.log'), 'w') as log:
            log.write(output)
        passed = result.returncode == 0 and '[mixin-audit] PASSED' in output
        print('\n'.join(line for line in output.splitlines() if 'mixin' in line.lower() and ('error' in line.lower() or 'fail' in line.lower() or 'audit' in line.lower()))[-6000:])
        print('RESULT:', 'PASSED' if passed else f'FAILED (exit {result.returncode})')
        return 0 if passed else 1


if __name__ == '__main__':
    sys.exit(main())
