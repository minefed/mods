#!/usr/bin/env python3
"""Coordinate locked Minefed builds and publish exactly three verified assets."""
from __future__ import annotations

import argparse
import base64
import hashlib
import http.client
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen
import zipfile

import mods

ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = 'minefed/mods'


def token() -> str:
    return os.environ.get('GH_TOKEN') or os.environ.get('GITHUB_TOKEN', '')


def github(method: str, path: str, body=None):
    """Send credentials only to GitHub's API, never to asset redirects."""
    if path.startswith('/'):
        path = path[1:]
    if '://' in path or '\\' in path or any(p == '..' for p in path.split('/')):
        raise mods.ModError('Invalid GitHub API path')
    headers = {'Accept': 'application/vnd.github+json', 'User-Agent': 'minefed-releases',
               'X-GitHub-Api-Version': '2022-11-28'}
    if token():
        headers['Authorization'] = 'Bearer ' + token()
    if method != 'GET' and not token():
        raise mods.ModError('Publishing requires GH_TOKEN or GITHUB_TOKEN with contents:write')
    data = None if body is None else json.dumps(body).encode('utf-8')
    if data is not None:
        headers['Content-Type'] = 'application/json'
    request = Request('https://api.github.com/' + path, data=data, headers=headers, method=method)
    with urlopen(request, timeout=60) as response:
        raw = response.read()
        return json.loads(raw) if raw else None


def read_json(path: Path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def restore_embedded(root: Path, archive: Path, entries: list[dict]) -> None:
    """Restore only explicitly recorded original JARs from a published modpack."""
    with zipfile.ZipFile(archive) as pack:
        if pack.testzip() is not None:
            raise mods.ModError('Bootstrap modpack failed CRC validation')
        for entry in entries:
            destination = mods.safe_path(root, entry['artifact']['path'])
            if not any(destination.relative_to(root).as_posix().startswith(p + '/') for p in mods.ARTIFACT_DIRS):
                raise mods.ModError('Bootstrap destination is outside artifact storage')
            if destination.exists():
                mods.check_artifact(root, entry)
                continue
            name = 'overrides/mods/' + entry['fileName']
            matches = [i for i in pack.infolist() if i.filename == name]
            if len(matches) != 1 or matches[0].file_size != entry['size']:
                raise mods.ModError('Bootstrap pack lacks the exact original: ' + entry['modId'])
            destination.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(dir=destination.parent, suffix='.part', delete=False) as stream:
                temporary = Path(stream.name)
                try:
                    with pack.open(matches[0]) as source:
                        shutil.copyfileobj(source, stream, mods.CHUNK_SIZE)
                except BaseException:
                    stream.close()
                    temporary.unlink(missing_ok=True)
                    raise
            try:
                mods.check_bytes(temporary, entry)
                mods.publish_new(temporary, destination)
                mods.check_artifact(root, entry)
            finally:
                temporary.unlink(missing_ok=True)


def bootstrap(root: Path) -> None:
    from build_modpack import load_plan
    # Bootstrap only the selected build inputs. A historical URL-less binary
    # can now be replaced by a reviewed, downloadable dependency artifact.
    manifest, recipes = load_plan(root)
    binaries = {e['modId'] for e in recipes['entries'] if e['mode'] == 'binary'}
    entries = [e for e in manifest['entries'] if e['included'] and e['modId'] in binaries
               and not e['artifact'].get('url') and not mods.safe_path(root, e['artifact']['path']).exists()]
    if not entries:
        print('No release bootstrap files are missing')
        return
    policy = {e['modId']: e for e in read_json(root / 'inventory/release-policy.json')['entries']}
    for entry in entries:
        decision = policy[entry['modId']]
        if decision['distribution'] != 'embed' or decision['artifact'] != 'baseline':
            raise mods.ModError('No approved bootstrap distribution for ' + entry['modId'])
    try:
        release = github('GET', f'repos/{REPOSITORY}/releases/latest')
    except HTTPError as exc:
        if exc.code == 404:
            raise mods.ModError('The first release must be built from the local verified JAR inventory; no published bootstrap pack exists') from exc
        raise
    assets = [a for a in release['assets'] if a['name'] == 'client.mrpack' and a['state'] == 'uploaded']
    if len(assets) != 1 or not re.fullmatch(r'sha256:[0-9a-f]{64}', assets[0].get('digest', '')):
        raise mods.ModError('Published bootstrap asset has no unique verified SHA-256')
    asset = assets[0]
    expected_prefix = f'https://github.com/{REPOSITORY}/releases/download/'
    if not asset['browser_download_url'].startswith(expected_prefix):
        raise mods.ModError('Unexpected bootstrap download origin')
    output = mods.output_path(root, 'build/bootstrap/client.mrpack')
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=output.parent, suffix='.part', delete=False) as stream:
        temporary = Path(stream.name)
        try:
            with mods.download(asset['browser_download_url']) as response:
                total = 0
                while block := response.read(min(mods.CHUNK_SIZE, asset['size'] - total + 1)):
                    total += len(block)
                    if total > asset['size']:
                        raise mods.ModError('Bootstrap download exceeded recorded size')
                    stream.write(block)
        except BaseException:
            stream.close()
            temporary.unlink(missing_ok=True)
            raise
    try:
        if mods.file_digest(temporary) != (asset['digest'].split(':')[1], asset['size']):
            raise mods.ModError('Bootstrap modpack SHA-256/size mismatch')
        restore_embedded(root, temporary, entries)
    finally:
        temporary.unlink(missing_ok=True)
    print('Restored hash-pinned originals from the published client modpack: ' + ', '.join(e['modId'] for e in entries))


def validate_assets(root: Path, manifest: dict, plan: dict) -> list[tuple[dict, Path]]:
    if manifest.get('schemaVersion') != 1 or manifest.get('version') != plan.get('version'):
        raise mods.ModError('Release asset manifest/version mismatch')
    if not re.fullmatch(r'\d{14}', str(plan.get('version', ''))):
        raise mods.ModError('Release version must be yyyyMMddHHmmss')
    assets = manifest.get('assets', [])
    expected = {'server': ('server.zip', 'application/zip'),
                'client': ('client.mrpack', 'application/x-modrinth-modpack+zip'),
                'resourcepack': ('resourcepack.zip', 'application/zip')}
    if len(assets) != 3 or {a.get('kind') for a in assets} != set(expected):
        raise mods.ModError('Exactly server, client and resourcepack assets are required')
    result = []
    for asset in assets:
        name, media_type = expected[asset['kind']]
        if asset.get('name') != name or asset.get('mediaType') != media_type:
            raise mods.ModError('Unexpected release asset name or media type')
        path = mods.output_path(root, asset['path'])
        if path != mods.output_path(root, f"build/releases/{plan['version']}/{name}"):
            raise mods.ModError('Release asset is outside its version directory')
        if mods.file_digest(path) != (asset.get('sha256'), asset.get('size')):
            raise mods.ModError('Release asset SHA-256/size mismatch: ' + name)
        with zipfile.ZipFile(path) as archive:
            if archive.testzip() is not None:
                raise mods.ModError('Release asset failed CRC validation: ' + name)
        result.append((asset, path))
    if manifest.get('policySha256') != mods.file_digest(root / 'inventory/release-policy.json')[0]:
        raise mods.ModError('Release policy changed after packaging')
    policy = read_json(root / 'inventory/release-policy.json')
    published_path = policy.get('publishedManifest')
    published_snapshot = manifest.get('publishedManifest')
    if published_path is not None or published_snapshot is not None:
        if not isinstance(published_snapshot, dict) or published_snapshot.get('path') != published_path:
            raise mods.ModError('Published artifact manifest reference differs from release policy')
        if mods.file_digest(mods.safe_path(root, published_path))[0] != published_snapshot.get('sha256'):
            raise mods.ModError('Published artifact manifest changed after packaging')
    planned = {s['path']: s['commit'] for s in plan['sources']}
    for record in manifest.get('files', []):
        source = record.get('source')
        if source and record.get('artifact') == 'built' and planned.get(source['path']) != source['commit']:
            raise mods.ModError('Packaged source differs from the planned branch tip: ' + record['modId'])
    resource_sources = [s for s in plan['sources'] if s.get('kind') == 'resourcepack']
    if resource_sources and manifest.get('resourcePack', {}).get('commit') not in {s['commit'] for s in resource_sources}:
        raise mods.ModError('Packaged resource pack differs from the planned branch tip')
    return result


def git_with_token(root: Path, args: list[str], *, text_input: str | None = None) -> str:
    environment = dict(os.environ)
    environment.update(GIT_AUTHOR_NAME='github-actions[bot]', GIT_COMMITTER_NAME='github-actions[bot]',
                       GIT_AUTHOR_EMAIL='41898282+github-actions[bot]@users.noreply.github.com',
                       GIT_COMMITTER_EMAIL='41898282+github-actions[bot]@users.noreply.github.com')
    if token():
        basic = base64.b64encode(('x-access-token:' + token()).encode()).decode()
        index = int(environment.get('GIT_CONFIG_COUNT', '0'))
        environment['GIT_CONFIG_COUNT'] = str(index + 1)
        environment[f'GIT_CONFIG_KEY_{index}'] = 'http.https://github.com/.extraheader'
        environment[f'GIT_CONFIG_VALUE_{index}'] = 'AUTHORIZATION: basic ' + basic
    process = subprocess.run(['git', '-C', str(root), *args], input=text_input,
                             capture_output=True, text=True, encoding='utf-8', env=environment)
    if process.returncode:
        # Git receives credentials through its environment, never command arguments.
        detail = process.stderr.replace(token(), '[redacted]') if token() else process.stderr
        raise mods.ModError('Git release operation failed: ' + detail.strip())
    return process.stdout.strip()


def release_commit(root: Path, plan: dict, patch: Path) -> str:
    if mods.git(root, 'rev-parse', 'HEAD') != plan['rootCommit']:
        raise mods.ModError('Publisher checkout differs from the planned root commit')
    if mods.git(root, 'status', '--porcelain', '--untracked-files=no'):
        raise mods.ModError('Publisher needs a clean tracked checkout')
    if patch.stat().st_size:
        git_with_token(root, ['apply', '--check', '--index', str(patch)])
        git_with_token(root, ['apply', '--index', str(patch)])
    allowed = {s['path'] for s in plan['sources']} | {
        'inventory/mods.lock.json', 'inventory/build-recipes.json', 'inventory/resourcepacks.lock.json'}
    changed = set(mods.git(root, 'diff', '--cached', '--name-only').splitlines())
    if not changed.issubset(allowed):
        raise mods.ModError('Release pin patch contains unrelated files')
    for source in plan['sources']:
        wanted = f"160000 {source['commit']} 0\t{source['path']}"
        if mods.git(root, 'ls-files', '--stage', '--', source['path']) != wanted:
            raise mods.ModError('Release gitlink does not match the planned source: ' + source['path'])
    if not changed:
        return plan['rootCommit']
    tree = mods.git(root, 'write-tree')
    return git_with_token(root, ['commit-tree', tree, '-p', plan['rootCommit']],
                          text_input=f"chore(release): lock inputs for {plan['version']}\n")


def upload_asset(release_id: int, asset: dict, path: Path):
    connection = http.client.HTTPSConnection('uploads.github.com', timeout=300)
    destination = f"/repos/{REPOSITORY}/releases/{release_id}/assets?name={quote(asset['name'], safe='')}"
    try:
        connection.putrequest('POST', destination)
        for key, value in {'Authorization': 'Bearer ' + token(), 'User-Agent': 'minefed-releases',
                           'Accept': 'application/vnd.github+json', 'Content-Type': asset['mediaType'],
                           'Content-Length': str(asset['size'])}.items():
            connection.putheader(key, value)
        connection.endheaders()
        digest, total = hashlib.sha256(), 0
        with path.open('rb') as stream:
            while block := stream.read(mods.CHUNK_SIZE):
                digest.update(block)
                total += len(block)
                connection.send(block)
        response = connection.getresponse()
        raw = response.read()
        if response.status != 201:
            raise mods.ModError(f"GitHub asset upload failed ({response.status}): {asset['name']}; release remains a draft")
        result = json.loads(raw)
        if (digest.hexdigest(), total) != (asset['sha256'], asset['size']):
            raise mods.ModError('Asset changed during upload; release remains a draft')
        verify_remote_asset(result, asset)
        return result
    finally:
        connection.close()


def verify_remote_asset(actual: dict, expected: dict) -> None:
    if (actual.get('name'), actual.get('state'), actual.get('size'), actual.get('digest')) != (
            expected['name'], 'uploaded', expected['size'], 'sha256:' + expected['sha256']):
        raise mods.ModError('Uploaded asset metadata/hash mismatch; release remains a draft')


def release_body(manifest: dict, plan: dict, commit: str) -> str:
    state = {'schemaVersion': 1, 'fingerprint': plan['fingerprint'], 'rootCommit': plan['rootCommit'],
             'version': plan['version'], 'sources': plan['sources']}
    encoded = base64.b64encode(json.dumps(state, separators=(',', ':')).encode()).decode()
    profiles = manifest['profiles']
    bundled = manifest.get('archiveMode') == 'bundled'
    lines = [f"Minefed {plan['version']} (Asia/Seoul)", '',
             'Minecraft 1.20.4 · Fabric Loader 0.18.0 이상 · Java 17', '',
             f"- 서버팩: {profiles['server']['modCount']}개 모드, " + ('모든 모드 JAR 내장' if bundled else '공식 다운로드 설치기 포함')
             + (f", 서버 플러그인 {profiles['server']['pluginCount']}개는 plugins/에 포함" if profiles['server'].get('pluginCount') else ''),
             f"- 클라이언트팩: {profiles['client']['modCount']}개 모드, Modrinth/Prism Launcher에서 client.mrpack 가져오기",
             '- 리소스팩: resourcepack.zip; 클라이언트팩에도 동일 파일 포함',
             '- 공식 배포 파일과 Modern Lights 실행 JAR도 팩에 포함되며, 추가 모드 다운로드·수동 복원이 필요 없습니다.'
             if bundled else '- 공개 배포 정책에 따라 일부 자체 빌드 결과는 검토된 공식 원본의 다운로드 참조로 제공됩니다.',
             '- 실제 서버/클라이언트 기동은 미검증입니다.', '',
             f"고정한 빌드 입력: https://github.com/{REPOSITORY}/commit/{commit}",
             '모드별 대응 소스, 빌드 방침, 저작권 고지와 원본 참조 버전은 각 팩의 기록을 확인하세요.', '',
             '| 파일 | 바이트 | SHA-256 |', '|---|---:|---|']
    lines += [f"| {a['name']} | {a['size']} | `{a['sha256']}` |" for a in manifest['assets']]
    lines += ['', '<!-- minefed-state:' + encoded + ' -->']
    return '\n'.join(lines)


def publish(root: Path, assets_path: Path, plan_path: Path, patch: Path) -> dict:
    if not token():
        raise mods.ModError('Publishing requires a GitHub token')
    manifest, plan = read_json(assets_path), read_json(plan_path)
    assets = validate_assets(root, manifest, plan)
    repository = github('GET', f'repos/{REPOSITORY}')
    if repository.get('private') or repository.get('default_branch') != 'main':
        raise mods.ModError('Expected the public minefed/mods repository with default main')
    if not re.fullmatch(r'[0-9a-f]{64}', str(plan.get('fingerprint', ''))):
        raise mods.ModError('Invalid release input fingerprint')
    for prefix in ('releases/tags/', 'git/ref/tags/'):
        try:
            github('GET', f"repos/{REPOSITORY}/{prefix}{plan['version']}")
        except HTTPError as exc:
            if exc.code != 404:
                raise
        else:
            raise mods.ModError('Release version already exists; no tags or files were overwritten')
    remote = mods.git(root, 'remote', 'get-url', 'origin').removesuffix('.git')
    if remote != f'https://github.com/{REPOSITORY}':
        raise mods.ModError('Publisher origin is not the authorized release repository')
    commit = release_commit(root, plan, patch)
    git_with_token(root, ['push', 'origin', f"{commit}:refs/tags/{plan['version']}"])
    release = github('POST', f'repos/{REPOSITORY}/releases', {
        'tag_name': plan['version'], 'target_commitish': commit,
        'name': 'Minefed ' + plan['version'], 'body': release_body(manifest, plan, commit),
        'draft': True, 'prerelease': False})
    print(f"Created draft {plan['version']}; uploading exactly three verified files", flush=True)
    for asset, path in assets:
        upload_asset(release['id'], asset, path)
        print('Verified uploaded ' + asset['name'], flush=True)
    remote_release = github('GET', f"repos/{REPOSITORY}/releases/{release['id']}")
    if len(remote_release['assets']) != 3:
        raise mods.ModError('Draft does not contain exactly three assets')
    by_name = {a['name']: a for a in remote_release['assets']}
    for asset, path in assets:
        verify_remote_asset(by_name.get(asset['name'], {}), asset)
        if mods.file_digest(path) != (asset['sha256'], asset['size']):
            raise mods.ModError('Local release asset changed before publication')
    final = github('PATCH', f"repos/{REPOSITORY}/releases/{release['id']}", {'draft': False, 'make_latest': 'true'})
    if final.get('draft') or len(final.get('assets', [])) != 3:
        raise mods.ModError('GitHub did not confirm complete release publication')
    print(final['html_url'], flush=True)
    return final


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('bootstrap').add_argument('--plan')
    planner = commands.add_parser('plan')
    planner.add_argument('--output', default='build/release-plan.json')
    planner.add_argument('--force', action='store_true', help='Explicitly release unchanged inputs with a new version')
    materializer = commands.add_parser('materialize')
    materializer.add_argument('--plan', required=True)
    materializer.add_argument('--patch', default='build/release-inputs.patch')
    publisher = commands.add_parser('publish')
    publisher.add_argument('--assets', required=True)
    publisher.add_argument('--plan', required=True)
    publisher.add_argument('--patch', default='build/release-inputs.patch')
    args = parser.parse_args(argv)
    try:
        if args.command in ('plan', 'materialize'):
            import release_inputs
            if args.command == 'plan':
                release_inputs.plan(ROOT, mods.output_path(ROOT, args.output), force=args.force)
            else:
                release_inputs.materialize(ROOT, mods.output_path(ROOT, args.plan), mods.output_path(ROOT, args.patch))
        elif args.command == 'bootstrap':
            bootstrap(ROOT)
        else:
            publish(ROOT, mods.output_path(ROOT, args.assets), mods.output_path(ROOT, args.plan), mods.output_path(ROOT, args.patch))
        return 0
    except (mods.ModError, HTTPError, OSError, ValueError, RuntimeError, zipfile.BadZipFile, subprocess.CalledProcessError) as exc:
        print(f'Release failed: {exc}', file=__import__('sys').stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
