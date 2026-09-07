"""Plan and materialize reviewed release inputs without changing the main branch."""

import base64
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
from urllib.error import HTTPError

import mods


KST = timezone(timedelta(hours=9), 'Asia/Seoul')
MARKER = re.compile(r'<!--\s*minefed-state:([A-Za-z0-9+/=]+)\s*-->')
SHA = re.compile(r'[0-9a-f]{40}')
GITHUB = re.compile(r'https://github\.com/(minefed/[A-Za-z0-9_.-]+?)(?:\.git)?/?$')
INPUTS = 'inventory/release-inputs.json'


class InputError(mods.ModError):
    pass


def github(method, path, body=None):
    # release_control imports this module only in CLI dispatch.
    from release_control import github as request
    return request(method, path, body)


def git(root, *args, binary=False):
    result = subprocess.run(['git', '-C', str(root), *args], capture_output=True,
                            env={**os.environ, 'GIT_OPTIONAL_LOCKS': '0'})
    if result.returncode:
        raise InputError('git ' + args[0] + ' failed: ' + result.stderr.decode('utf-8', errors='replace').strip())
    return result.stdout if binary else result.stdout.decode('utf-8').strip()


def read_json(root, path):
    return json.loads((Path(root) / path).read_text(encoding='utf-8-sig'))


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def local_path(root, relative):
    path = PurePosixPath(relative)
    if not relative or '\\' in relative or path.is_absolute() or any(p in ('..', '.') for p in path.parts):
        raise InputError('Unsafe repository path: ' + relative)
    root = Path(root).resolve()
    target = root.joinpath(*path.parts).resolve()
    if not target.is_relative_to(root) or target == root:
        raise InputError('Repository path leaves workspace: ' + relative)
    return target


def repository_name(url):
    match = GITHUB.fullmatch(url)
    if not match:
        raise InputError('Release sources must use https://github.com/minefed/: ' + url)
    return match[1]


def configured_sources(root):
    """Track every mod source in the inventory, plus authorized resource packs."""
    root = Path(root)
    modules = {}
    names = git(root, 'config', '--file', '.gitmodules', '--name-only', '--get-regexp', r'^submodule\..*\.path$')
    for key in names.splitlines():
        prefix = key[:-5]
        path = git(root, 'config', '--file', '.gitmodules', '--get', key)
        url = git(root, 'config', '--file', '.gitmodules', '--get', prefix + '.url')
        repository_name(url)
        result = subprocess.run(['git', '-C', str(root), 'config', '--file', '.gitmodules', '--get', prefix + '.branch'], capture_output=True)
        ref = result.stdout.decode('utf-8').strip() if result.returncode == 0 else 'main'
        if ref == '.' or not ref or ref.startswith('-'):
            raise InputError('Explicit tracking branch required for ' + path)
        git(root, 'check-ref-format', 'refs/heads/' + ref)
        local_path(root, path)
        if path in modules:
            raise InputError('Duplicate submodule path: ' + path)
        modules[path] = {'path': path, 'url': url, 'ref': ref, 'kind': 'mod'}
    wanted = {e['source']['path'] for e in read_json(root, 'inventory/mods.lock.json')['entries'] if e.get('source')}
    packs = read_json(root, 'inventory/resourcepacks.lock.json')['entries'] if (root / 'inventory/resourcepacks.lock.json').is_file() else []
    for pack in packs:
        wanted.add(pack['sourcePath'])
        if pack['sourcePath'] in modules:
            modules[pack['sourcePath']]['kind'] = 'resourcepack'
    missing = wanted - modules.keys()
    if missing:
        raise InputError('Inventory sources missing from .gitmodules: ' + ', '.join(sorted(missing)))
    return [modules[path] for path in sorted(wanted)]


def assert_clean(root):
    if git(root, 'status', '--porcelain', '--untracked-files=all', '--ignore-submodules=none'):
        raise InputError('Release materialization requires a clean root and all initialized submodules')


def remote_commit(root, source):
    ref = 'refs/heads/' + source['ref']
    result = git(root, 'ls-remote', '--exit-code', source['url'], ref)
    pairs = [line.split('\t') for line in result.splitlines() if line]
    if len(pairs) != 1 or len(pairs[0]) != 2 or pairs[0][1] != ref or not SHA.fullmatch(pairs[0][0]):
        raise InputError('No unique full remote branch commit for ' + source['path'])
    return pairs[0][0]


def fingerprint(root_commit, sources):
    value = {'rootCommit': root_commit, 'sources': sorted(sources, key=lambda s: s['path'])}
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def release_state(body):
    matches = MARKER.findall(body or '')
    if not matches:
        return None
    if len(matches) != 1:
        raise InputError('Release contains multiple minefed-state markers')
    try:
        value = json.loads(base64.b64decode(matches[0], validate=True))
    except (ValueError, UnicodeError) as exc:
        raise InputError('Invalid release state marker') from exc
    if not isinstance(value, dict) or not re.fullmatch(r'[0-9a-f]{64}', str(value.get('fingerprint', ''))):
        raise InputError('Release state must contain a SHA256 fingerprint')
    return value


def next_version(tags, now=None):
    current = (now or datetime.now(KST)).astimezone(KST).replace(microsecond=0)
    dated = []
    for tag in tags:
        if re.fullmatch(r'\d{14}', tag):
            try:
                dated.append(datetime.strptime(tag, '%Y%m%d%H%M%S').replace(tzinfo=KST))
            except ValueError as exc:
                raise InputError('Invalid timestamp release tag: ' + tag) from exc
    if dated:
        current = max(current, max(dated) + timedelta(seconds=1))
    return current.strftime('%Y%m%d%H%M%S')


def plan(root, output, force=False):
    root = Path(root).resolve()
    assert_clean(root)
    root_commit = git(root, 'rev-parse', 'HEAD')
    repo = repository_name(git(root, 'remote', 'get-url', 'origin'))
    sources = configured_sources(root)
    with ThreadPoolExecutor(max_workers=4) as pool:
        commits = list(pool.map(lambda source: remote_commit(root, source), sources))
    sources = [{**source, 'commit': commit} for source, commit in zip(sources, commits)]
    releases = github('GET', '/repos/' + repo + '/releases?per_page=50')
    if not isinstance(releases, list):
        raise InputError('GitHub release list was not an array')
    published = [release for release in releases if not release.get('draft') and release.get('published_at')]
    published.sort(key=lambda release: release['published_at'], reverse=True)
    latest = published[0] if published else None
    if releases:
        # A page full of drafts must not hide the last completed publication.
        try:
            candidate = github('GET', '/repos/' + repo + '/releases/latest')
        except HTTPError as exc:
            if exc.code != 404:
                raise
        else:
            if not isinstance(candidate, dict) or candidate.get('draft'):
                raise InputError('GitHub latest release was not a published release')
            latest = candidate
    previous = release_state(latest.get('body')) if latest else None
    digest = fingerprint(root_commit, sources)
    tags = [release.get('tag_name', '') for release in releases]
    for line in git(root, 'ls-remote', '--tags', 'origin').splitlines():
        if '\trefs/tags/' in line:
            tags.append(line.split('\trefs/tags/', 1)[1].removesuffix('^{}'))
    value = {'schemaVersion': 1, 'rootCommit': root_commit, 'fingerprint': digest,
             'changed': bool(force) or previous is None or previous['fingerprint'] != digest,
             'force': bool(force),
             'version': next_version(tags), 'timezone': 'Asia/Seoul', 'sources': sources}
    # Do not label an unstaged/root mutation during remote reads as the saved commit.
    assert_clean(root)
    if git(root, 'rev-parse', 'HEAD') != root_commit:
        raise InputError('Root HEAD changed while planning')
    write_json(root / output, value)
    if os.environ.get('GITHUB_OUTPUT'):
        with Path(os.environ['GITHUB_OUTPUT']).open('a', encoding='utf-8') as stream:
            stream.write('changed=' + str(value['changed']).lower() + '\nversion=' + value['version'] + '\n')
    return value


def license_files(source, commit):
    """Hash Git blobs, not CRLF-sensitive checkout bytes; detect additions/removals."""
    files = {}
    tree = git(source, 'ls-tree', '-r', '-z', commit, binary=True)
    for record in tree.split(b'\0'):
        if not record:
            continue
        info, name = record.split(b'\t', 1)
        path = name.decode('utf-8')
        # READMEs frequently contain the modpack grant; include them as evidence.
        if not re.search(r'(^|/)(licen[cs]e[^/]*|copying[^/]*|notice[^/]*|terms[^/]*|readme[^/]*)(/|$)', path, re.I):
            continue
        mode, kind, blob = info.decode('ascii').split()
        if kind == 'blob':
            data = git(source, 'cat-file', 'blob', blob, binary=True)
            files[path] = hashlib.sha256(data).hexdigest()
    return dict(sorted(files.items()))


def check_licenses(source, commit, reviewed):
    actual = license_files(source, commit)
    if actual != reviewed:
        changed = sorted(path for path in actual.keys() | reviewed.keys() if actual.get(path) != reviewed.get(path))
        raise InputError('License/notice inputs changed; review required: ' + ', '.join(changed))


def nested_gitlinks(source, commit):
    """Nested source upgrades need review; unchanged pins retain reviewed licenses."""
    links = {}
    for record in git(source, 'ls-tree', '-r', '-z', commit, binary=True).split(b'\0'):
        if not record:
            continue
        info, name = record.split(b'\t', 1)
        mode, kind, sha = info.decode('ascii').split()
        if mode == '160000' and kind == 'commit':
            links[name.decode('utf-8')] = sha
    return dict(sorted(links.items()))


def check_nested_sources(source, commit, reviewed):
    actual = nested_gitlinks(source, commit)
    if actual != reviewed:
        changed = sorted(path for path in actual.keys() | reviewed.keys() if actual.get(path) != reviewed.get(path))
        raise InputError('Nested source changed; review required: ' + ', '.join(changed))


def _validated_plan(root, value):
    if value.get('schemaVersion') != 1 or not SHA.fullmatch(str(value.get('rootCommit', ''))):
        raise InputError('Invalid release plan version/root commit')
    if git(root, 'rev-parse', 'HEAD') != value['rootCommit']:
        raise InputError('Root HEAD does not match the planned root commit')
    configured = configured_sources(root)
    sources = value.get('sources', [])
    if not isinstance(sources, list) or len({s.get('path') for s in sources}) != len(sources):
        raise InputError('Invalid/duplicate planned sources')
    if [{k: s.get(k) for k in ('path', 'url', 'ref', 'kind')} for s in sorted(sources, key=lambda s: s['path'])] != configured:
        raise InputError('Planned source coverage differs from the tracked inventories')
    if any(not SHA.fullmatch(str(s.get('commit', ''))) for s in sources):
        raise InputError('Every source must pin a full commit SHA')
    if value.get('fingerprint') != fingerprint(value['rootCommit'], sources):
        raise InputError('Release plan fingerprint mismatch')
    return sources


def materialize(root, plan_path, patch_path=None):
    root = Path(root).resolve()
    value = read_json(root, plan_path)
    assert_clean(root)
    sources = _validated_plan(root, value)
    inputs = read_json(root, INPUTS)
    if inputs.get('schemaVersion') != 1 or inputs.get('minecraftVersion', '1.20.4') != '1.20.4':
        raise InputError('Unsupported release input policy')
    reviewed = {e['path']: e for e in inputs['sources']}
    if len(reviewed) != len(inputs['sources']) or set(reviewed) != {s['path'] for s in sources}:
        raise InputError('Reviewed license inputs do not cover planned sources exactly')
    if any(not isinstance(entry.get('nestedGitlinks'), dict) for entry in reviewed.values()):
        raise InputError('Reviewed nested source inputs are required for every source')
    recipes = read_json(root, 'inventory/build-recipes.json')
    globs = {e['modId']: e for e in inputs['entries']}
    source_recipes = [e for e in recipes['entries'] if e['mode'] == 'source']
    if len(globs) != len(inputs['entries']) or set(globs) != {e['modId'] for e in source_recipes}:
        raise InputError('Reviewed release globs do not cover source recipes exactly')
    for recipe in source_recipes:
        entry = globs[recipe['modId']]
        if entry['sourcePath'] != recipe['sourcePath'] or not entry.get('releaseGlobs'):
            raise InputError('Invalid release glob inputs for ' + recipe['modId'])
        for pattern in entry['releaseGlobs']:
            local_path(root / recipe['sourcePath'], pattern)
            if '**' in pattern or not pattern.endswith('.jar') or '*' in str(PurePosixPath(pattern).parent):
                raise InputError('Release glob must retain an exact artifact directory: ' + pattern)
    git(root, 'submodule', 'update', '--init', '--recursive')
    for source in sources:
        path = local_path(root, source['path'])
        # Fetch the approved branch, then require the planned SHA to remain reachable.
        git(path, 'fetch', '--no-tags', source['url'], 'refs/heads/' + source['ref'])
        git(path, 'merge-base', '--is-ancestor', source['commit'], 'FETCH_HEAD')
        check_licenses(path, source['commit'], reviewed[source['path']]['licenseFiles'])
        check_nested_sources(path, source['commit'], reviewed[source['path']]['nestedGitlinks'])
    assert_clean(root)
    if git(root, 'rev-parse', 'HEAD') != value['rootCommit']:
        raise InputError('Root HEAD changed during source verification')
    # All permission checks precede changes to root recipe/lock and checked-out pins.
    for source in sources:
        path = local_path(root, source['path'])
        git(path, 'checkout', '--detach', source['commit'])
        git(path, 'submodule', 'update', '--init', '--recursive')
        assert_clean(path)
    commits = {s['path']: s['commit'] for s in sources}
    manifest = read_json(root, 'inventory/mods.lock.json')
    previous = {entry['source']['path']: entry['source']['commit'] for entry in manifest['entries'] if entry.get('source')}
    changed_paths = {path for path, commit in commits.items() if previous.get(path) != commit}
    for entry in manifest['entries']:
        if entry.get('source') and entry['source']['path'] in commits:
            entry['source']['commit'] = commits[entry['source']['path']]
    for source in manifest.get('sourceRepositories', []):
        if source['path'] in commits:
            source['commit'] = commits[source['path']]
    write_json(root / 'inventory/mods.lock.json', manifest)
    tracked = ['inventory/mods.lock.json', 'inventory/build-recipes.json']
    if (root / 'inventory/resourcepacks.lock.json').is_file():
        packs = read_json(root, 'inventory/resourcepacks.lock.json')
        for pack in packs['entries']:
            pack['commit'] = commits[pack['sourcePath']]
        write_json(root / 'inventory/resourcepacks.lock.json', packs)
        tracked.append('inventory/resourcepacks.lock.json')
    for recipe in source_recipes:
        if recipe['sourcePath'] in changed_paths:
            recipe.pop('expectedVersion', None)
            recipe['artifactGlobs'] = globs[recipe['modId']]['releaseGlobs']
    write_json(root / 'inventory/build-recipes.json', recipes)
    git(root, 'add', '--', *tracked, *commits.keys())
    patch = git(root, 'diff', '--cached', '--binary', '--submodule=short', binary=True)
    target = root / patch_path if patch_path is not None else root / 'build/release-inputs.patch'
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(patch)
    # Only root inventories and gitlink records are emitted: never private source files.
    return {'rootCommit': value['rootCommit'], 'fingerprint': value['fingerprint'],
            'version': value['version'], 'patch': str(target), 'sources': sources}
