#!/usr/bin/env python3
"""Minefed scheduled game server deployment agent.

Runs on the game server host (Python 3.11+, standard library only). It asks
minefed-api what to deploy, announces maintenance over RCON, stops the podman
compose service, backs up the world, swaps the release-managed files, restarts,
checks health and reports the result. A failed deployment rolls back to the
previous release. The API changes the release launchers receive only after a
reported success. See docs/SCHEDULED_DEPLOYMENT.md in minefed/mods.
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
import re
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import time
import tomllib
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, OpenerDirector, Request, build_opener
import uuid
import zipfile

TAG = re.compile(r'[0-9]{14}')
RELEASE_DOWNLOAD = 'https://github.com/minefed/mods/releases/download/'
# Files the server pack owns outside mods/. They are replaced on every deploy.
MANAGED_FILES = ('config/bluemap/packs/10-minefed.zip', 'config/mtr/bluemap-vehicles.json')
# Owner-edited files the server pack only creates when missing.
EDITABLE_DEFAULTS = ('config/mtr/bluemap-public-routes.json',)
HEALTH_FAILURES = ('Mixin apply failed', 'Incompatible mods found', 'Failed to start the minecraft server',
                   'This crash report has been saved to', 'Encountered an unexpected exception')
MINECRAFT_PROTOCOL = 765  # 1.20.4

log = logging.getLogger('minefed-deploy')


class AgentError(Exception):
    """A deployment step failed; the message never contains secrets."""


@dataclass
class Config:
    profile: str
    api_url: str
    token_file: Path
    deploy_root: Path
    server_root: Path
    compose_dir: Path
    rcon_password_file: Path
    compose_command: list[str] = field(default_factory=lambda: ['podman', 'compose'])
    rcon_host: str = '127.0.0.1'
    rcon_port: int = 25575
    server_host: str = '127.0.0.1'
    server_port: int = 25565
    announce_minutes: list[int] = field(default_factory=lambda: [30, 10, 5, 1])
    weekly_restart: bool = True
    manage_resource_pack: bool = True
    stop_timeout: int = 180
    start_timeout: int = 600
    keep_releases: int = 4
    keep_backups: int = 4
    backup_exclude: list[str] = field(default_factory=list)
    dry_run: bool = False

    @classmethod
    def load(cls, path: Path) -> 'Config':
        try:
            values = tomllib.loads(path.read_text(encoding='utf-8'))
        except (OSError, tomllib.TOMLDecodeError) as error:
            raise AgentError(f'cannot read configuration {path}: {error}') from None
        known = set(cls.__dataclass_fields__)
        unknown = set(values) - known
        if unknown:
            raise AgentError('unknown configuration keys: ' + ', '.join(sorted(unknown)))
        for key in ('token_file', 'deploy_root', 'server_root', 'compose_dir', 'rcon_password_file'):
            if key in values:
                values[key] = Path(values[key]).expanduser()
        try:
            config = cls(**values)
        except TypeError as error:
            raise AgentError(f'invalid configuration: {error}') from None
        config.validate()
        return config

    def validate(self) -> None:
        if self.profile not in ('prod', 'dev'):
            raise AgentError('profile must be prod or dev')
        url = urlparse(self.api_url)
        loopback = url.hostname in ('127.0.0.1', '::1', 'localhost')
        if url.scheme not in ('https', 'http') or (url.scheme == 'http' and not loopback) or not url.hostname \
                or url.username or url.password or url.query or url.fragment or url.path not in ('', '/'):
            raise AgentError('api_url must be an HTTPS origin (HTTP only on loopback)')
        for name in ('token_file', 'deploy_root', 'server_root', 'compose_dir', 'rcon_password_file'):
            if not getattr(self, name).is_absolute():
                raise AgentError(f'{name} must be an absolute path')
        if not self.announce_minutes or any(type(m) is not int or m < 0 for m in self.announce_minutes):
            raise AgentError('announce_minutes must list non-negative whole minutes')
        if not self.compose_command or not all(isinstance(part, str) and part for part in self.compose_command):
            raise AgentError('compose_command must be a non-empty list of strings')
        for name in ('stop_timeout', 'start_timeout', 'keep_releases', 'keep_backups', 'rcon_port', 'server_port'):
            if type(getattr(self, name)) is not int or getattr(self, name) < 1:
                raise AgentError(f'{name} must be a positive integer')
        for name in ('weekly_restart', 'manage_resource_pack', 'dry_run'):
            if type(getattr(self, name)) is not bool:
                raise AgentError(f'{name} must be true or false')
        if self.keep_releases < 2 or self.keep_backups < 1:
            raise AgentError('keep at least two releases and one backup')
        for pattern in self.backup_exclude:
            if not relative_path(pattern):
                raise AgentError('backup_exclude entries must be relative paths inside the world')


def relative_path(value: str) -> bool:
    parts = PurePosixPath(value).parts
    return bool(parts) and not value.startswith('/') and '\\' not in value \
        and all(p not in ('', '.', '..') and not re.search(r'[\x00-\x1f]', p) for p in parts)


def read_secret(path: Path) -> str:
    try:
        info = path.stat()
        if os.name == 'posix' and info.st_mode & 0o077:
            raise AgentError(f'{path} must be readable only by its owner (chmod 600)')
        value = path.read_text(encoding='utf-8').strip()
    except OSError:
        raise AgentError(f'cannot read secret file {path}') from None
    if not value or re.search(r'\s', value):
        raise AgentError(f'{path} must contain one secret without whitespace')
    return value


# --- minefed-api -------------------------------------------------------------

class ApiError(AgentError):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(f'API {status} {code}: {message}')
        self.status, self.code = status, code


class Api:
    def __init__(self, base: str, profile: str, token: str, opener: OpenerDirector | None = None):
        self.base = base.rstrip('/') + f'/v1/deployments/{profile}/'
        self.token = token
        self.opener = opener or build_opener(NoRedirect())

    def call(self, method: str, path: str, body: dict | None = None) -> dict:
        data = None if body is None else json.dumps(body).encode('utf-8')
        request = Request(self.base + path, data=data, method=method)
        request.add_header('Authorization', 'Bearer ' + self.token)
        request.add_header('Accept', 'application/json')
        if data is not None:
            request.add_header('Content-Type', 'application/json')
        try:
            with self.opener.open(request, timeout=30) as response:
                return json.loads(response.read(1 << 20))
        except HTTPError as error:
            try:
                detail = json.loads(error.read(1 << 16))
            except (ValueError, OSError):
                detail = {}
            raise ApiError(error.code, str(detail.get('code', 'UNAVAILABLE')), str(detail.get('message', 'request failed'))) from None
        except (URLError, OSError, ValueError) as error:
            raise AgentError(f'API request {method} {path} failed: {type(error).__name__}') from None

    def plan(self) -> dict:
        return self.call('GET', 'plan')

    def start(self, kind: str, target: str, previous: str, agent: str) -> dict:
        return self.call('POST', 'runs', {'kind': kind, 'targetRelease': target, 'previousRelease': previous, 'agent': agent})

    def heartbeat(self, run_id: str) -> dict:
        return self.call('POST', f'runs/{run_id}/heartbeat')

    def finish(self, run_id: str, result: str, message: str, manifest: str = '') -> dict:
        return self.call('POST', f'runs/{run_id}/finish',
                         {'result': result, 'serverManifestSha256': manifest, 'message': message[:2000]})


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # never forward the bearer token elsewhere


class HTTPSRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if urlparse(newurl).scheme != 'https':
            raise AgentError('download redirected to a non-HTTPS URL')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def download(url: str, destination: Path, size: int, sha256: str, opener: OpenerDirector | None = None) -> str:
    """Download a release asset, verify size and SHA-256, and return its SHA-1."""
    if not url.startswith(RELEASE_DOWNLOAD) or not re.fullmatch(r'[0-9a-f]{64}', sha256) or type(size) is not int or size <= 0:
        raise AgentError('refusing an unreviewed release asset')
    opener = opener or build_opener(HTTPSRedirects())
    digest, sha1, received = hashlib.sha256(), hashlib.sha1(), 0
    temporary = destination.with_name('.' + destination.name + '.part')
    try:
        with opener.open(Request(url, headers={'User-Agent': 'minefed-deploy'}), timeout=60) as response, temporary.open('wb') as out:
            for block in iter(lambda: response.read(1 << 20), b''):
                received += len(block)
                if received > size:
                    raise AgentError(f'{destination.name} is larger than published')
                digest.update(block)
                sha1.update(block)
                out.write(block)
        if received != size or digest.hexdigest() != sha256:
            raise AgentError(f'{destination.name} does not match the published size and SHA-256')
        os.replace(temporary, destination)
    except (URLError, OSError) as error:
        raise AgentError(f'downloading {destination.name} failed: {type(error).__name__}') from None
    finally:
        temporary.unlink(missing_ok=True)
    return sha1.hexdigest()


def file_hashes(path: Path) -> tuple[str, str]:
    sha256, sha1 = hashlib.sha256(), hashlib.sha1()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''):
            sha256.update(block)
            sha1.update(block)
    return sha256.hexdigest(), sha1.hexdigest()


# --- server pack ---------------------------------------------------------------

def extract_release(archive: Path, releases: Path, tag: str) -> Path:
    """Extract and verify a server pack into releases/<tag> atomically."""
    final = releases / tag
    if final.is_dir():
        verify_release(final, tag)
        return final
    releases.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f'.{tag}-', dir=releases))
    try:
        with zipfile.ZipFile(archive) as pack:
            for member in pack.infolist():
                name = member.filename
                if member.is_dir():
                    continue
                if not relative_path(name) or (member.external_attr >> 16) & 0o170000 == 0o120000:
                    raise AgentError(f'unsafe server pack entry: {name!r}')
                target = staging.joinpath(*PurePosixPath(name).parts)
                target.parent.mkdir(parents=True, exist_ok=True)
                with pack.open(member) as source, target.open('xb') as out:
                    shutil.copyfileobj(source, out)
        verify_release(staging, tag)
        os.replace(staging, final)
    except (zipfile.BadZipFile, OSError) as error:
        raise AgentError(f'cannot extract server pack: {type(error).__name__}') from None
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return final


def verify_release(directory: Path, tag: str) -> dict:
    try:
        release = json.loads((directory / 'MINEFED-RELEASE.json').read_text(encoding='utf-8'))
        manifest = json.loads((directory / 'download-manifest.json').read_text(encoding='utf-8'))
    except (OSError, ValueError):
        raise AgentError('server pack has no readable release manifest') from None
    if release.get('version') != tag or release.get('side') != 'server' or manifest.get('version') != tag:
        raise AgentError('server pack manifest does not match the approved release')
    items = manifest.get('files', []) + manifest.get('bluemapPacks', []) + manifest.get('generatedConfigs', [])
    listed_mods = set()
    for item in items:
        path = item.get('path')
        if not isinstance(path, str) or not relative_path(path):
            raise AgentError('server pack lists an unsafe path')
        if path.startswith('mods/'):
            listed_mods.add(path)
        elif path not in MANAGED_FILES:
            raise AgentError(f'server pack lists an unmanaged path: {path}')
        local = directory / path
        if not local.is_file() or local.stat().st_size != item.get('size') or file_hashes(local)[0] != item.get('sha256'):
            raise AgentError(f'server pack file does not match its manifest: {path}')
    present = {'mods/' + p.name for p in (directory / 'mods').iterdir()} if (directory / 'mods').is_dir() else set()
    if not listed_mods or present != listed_mods:
        raise AgentError('server pack mods/ differs from its manifest')
    for item in manifest.get('editableDefaults', []):
        local = directory / str(item.get('path'))
        if item.get('path') not in EDITABLE_DEFAULTS or item.get('preserveExisting') is not True \
                or not local.is_file() or file_hashes(local)[0] != item.get('sha256'):
            raise AgentError('server pack lists an unreviewed editable default')
    return release


def manifest_sha256(directory: Path) -> str:
    return file_hashes(directory / 'MINEFED-RELEASE.json')[0]


# --- Minecraft protocols -----------------------------------------------------

class Rcon:
    """Minimal Source RCON client; one connection per command."""

    def __init__(self, host: str, port: int, password: str, timeout: float = 10):
        self.host, self.port, self.password, self.timeout = host, port, password, timeout

    @staticmethod
    def _packet(request_id: int, kind: int, body: str) -> bytes:
        payload = struct.pack('<ii', request_id, kind) + body.encode('utf-8') + b'\x00\x00'
        return struct.pack('<i', len(payload)) + payload

    @staticmethod
    def _read(sock: socket.socket) -> tuple[int, str]:
        def exact(count: int) -> bytes:
            data = b''
            while len(data) < count:
                chunk = sock.recv(count - len(data))
                if not chunk:
                    raise AgentError('RCON connection closed')
                data += chunk
            return data
        (length,) = struct.unpack('<i', exact(4))
        if not 10 <= length <= 1 << 20:
            raise AgentError('invalid RCON response')
        data = exact(length)
        request_id, _ = struct.unpack('<ii', data[:8])
        return request_id, data[8:-2].decode('utf-8', 'replace')

    def command(self, command: str) -> str:
        try:
            with socket.create_connection((self.host, self.port), timeout=self.timeout) as sock:
                sock.sendall(self._packet(1, 3, self.password))
                if self._read(sock)[0] != 1:
                    raise AgentError('RCON authentication failed')
                sock.sendall(self._packet(2, 2, command))
                return self._read(sock)[1]
        except OSError as error:
            raise AgentError(f'RCON unavailable: {type(error).__name__}') from None


def server_list_ping(host: str, port: int, timeout: float = 5) -> dict:
    def varint(value: int) -> bytes:
        out = b''
        while True:
            byte = value & 0x7F
            value >>= 7
            out += bytes([byte | (0x80 if value else 0)])
            if not value:
                return out

    def read_varint(stream) -> int:
        result = 0
        for shift in range(0, 35, 7):
            byte = stream.read(1)
            if not byte:
                raise AgentError('server list ping closed')
            result |= (byte[0] & 0x7F) << shift
            if not byte[0] & 0x80:
                return result
        raise AgentError('invalid server list ping varint')

    address = host.encode('utf-8')
    handshake = b'\x00' + varint(MINECRAFT_PROTOCOL) + varint(len(address)) + address + struct.pack('>H', port) + varint(1)
    try:
        with socket.create_connection((host, port), timeout=timeout) as sock:
            sock.sendall(varint(len(handshake)) + handshake + varint(1) + b'\x00')
            stream = sock.makefile('rb')
            read_varint(stream)
            if read_varint(stream) != 0:
                raise AgentError('unexpected server list ping packet')
            text = stream.read(read_varint(stream))
            return json.loads(text)
    except (OSError, ValueError) as error:
        raise AgentError(f'server list ping failed: {type(error).__name__}') from None


# --- server.properties -------------------------------------------------------

def read_properties(path: Path) -> dict[str, str]:
    values = {}
    for line in path.read_text(encoding='latin-1').splitlines():
        stripped = line.lstrip()
        if not stripped or stripped[0] in '#!':
            continue
        match = re.match(r'((?:\\.|[^=:\s\\])+)\s*[=:\s]\s*(.*)', stripped)
        if match:
            values[unescape(match[1])] = unescape(match[2])
    return values


def unescape(value: str) -> str:
    return re.sub(r'\\(u[0-9a-fA-F]{4}|.)', lambda m: chr(int(m[1][1:], 16)) if len(m[1]) == 5 else
                  {'t': '\t', 'n': '\n', 'r': '\r', 'f': '\f'}.get(m[1], m[1]), value)


def update_properties(path: Path, changes: dict[str, str]) -> None:
    """Set keys in place, keeping comments, order and every other line."""
    lines = path.read_text(encoding='latin-1').splitlines()
    pending = dict(changes)
    for index, line in enumerate(lines):
        match = re.match(r'\s*((?:\\.|[^=:\s\\#!])+)\s*[=:\s]', line)
        if match and unescape(match[1]) in pending:
            key = unescape(match[1])
            lines[index] = f'{key}={pending.pop(key)}'
    lines += [f'{key}={value}' for key, value in pending.items()]
    atomic_write(path, ('\n'.join(lines) + '\n').encode('latin-1'))


def atomic_write(path: Path, data: bytes) -> None:
    temporary = path.with_name('.' + path.name + '.minefed-tmp')
    temporary.write_bytes(data)
    with contextlib.suppress(OSError):
        shutil.copymode(path, temporary)
    os.replace(temporary, path)


# --- host operations -----------------------------------------------------------

class Runner:
    def run(self, args: list[str], *, cwd: Path | None = None, timeout: float | None = None) -> str:
        log.info('run: %s', ' '.join(args))
        try:
            result = subprocess.run(args, cwd=cwd, timeout=timeout, capture_output=True, text=True, check=False)
        except (OSError, subprocess.TimeoutExpired) as error:
            raise AgentError(f'{args[0]} failed: {type(error).__name__}') from None
        if result.returncode != 0:
            raise AgentError(f'{" ".join(args[:3])} exited with {result.returncode}: {result.stderr.strip()[-300:]}')
        return result.stdout


class TarBackup:
    """World backups as tar + zstd archives, keeping the newest few."""

    def __init__(self, runner: Runner, directory: Path, keep: int):
        self.runner, self.directory, self.keep = runner, directory, keep

    def latest_size(self) -> int:
        archives = sorted(self.directory.glob('*.tar.zst')) if self.directory.is_dir() else []
        return archives[-1].stat().st_size if archives else 0

    def create(self, root: Path, members: list[str], excludes: list[str], name: str) -> Path:
        self.directory.mkdir(parents=True, exist_ok=True)
        archive = self.directory / f'{name}.tar.zst'
        partial = archive.with_name(archive.name + '.part')
        args = ['tar', '--zstd', '-cf', str(partial), '-C', str(root)]
        args += [f'--exclude={e}' for e in excludes] + ['--', *members]
        try:
            self.runner.run(args, timeout=3600)
            os.replace(partial, archive)
        finally:
            partial.unlink(missing_ok=True)
        for old in sorted(self.directory.glob('*.tar.zst'))[:-self.keep]:
            old.unlink()
        return archive

    def restore(self, archive: Path, root: Path, members: list[str]) -> None:
        for member in members:
            target = root / member
            if target.is_dir() and not target.is_symlink():
                shutil.rmtree(target)
            else:
                target.unlink(missing_ok=True)
        self.runner.run(['tar', '--zstd', '-xf', str(archive), '-C', str(root)], timeout=3600)


class Server:
    def __init__(self, config: Config, runner: Runner, rcon: Rcon, ping: Callable[[str, int], dict],
                 clock: Callable[[], float], sleep: Callable[[float], None]):
        self.config, self.runner, self.rcon, self.ping, self.clock, self.sleep = config, runner, rcon, ping, clock, sleep

    def compose(self, *args: str, timeout: float) -> None:
        self.runner.run([*self.config.compose_command, *args], cwd=self.config.compose_dir, timeout=timeout)

    def stop(self) -> None:
        with contextlib.suppress(AgentError):
            self.rcon.command('save-all flush')
        self.compose('stop', '-t', str(self.config.stop_timeout), timeout=self.config.stop_timeout + 60)

    def latest_log(self) -> Path:
        return self.config.server_root / 'logs' / 'latest.log'

    def recreate(self) -> tuple[float, int | None]:
        """Recreate containers so bind mounts re-resolve the current release link.

        Returns the start time and the previous latest.log inode; the server
        rotates that file on start, so only a different file is this start's log.
        """
        self.compose('down', '-t', str(self.config.stop_timeout), timeout=self.config.stop_timeout + 60)
        previous = self.latest_log().stat().st_ino if self.latest_log().is_file() else None
        started = self.clock()
        self.compose('up', '-d', timeout=300)
        return started, previous

    def wait_healthy(self, launch: tuple[float, int | None], beat: Callable[[], None]) -> None:
        root = self.config.server_root
        started, previous_log = launch
        deadline = started + self.config.start_timeout
        last_beat = self.clock()
        while self.clock() < deadline:
            latest = self.latest_log()
            text = ''
            if latest.is_file() and latest.stat().st_ino != previous_log:
                text = latest.read_text(encoding='utf-8', errors='replace')
            failure = next((pattern for pattern in HEALTH_FAILURES if pattern in text), None)
            crashes = [p for p in (root / 'crash-reports').glob('*.txt') if p.stat().st_mtime >= started - 1] \
                if (root / 'crash-reports').is_dir() else []
            if failure or crashes:
                raise AgentError(f'server failed to start: {failure or "crash report " + crashes[0].name}')
            if re.search(r'Done \([0-9.]+s\)!', text):
                try:
                    self.ping(self.config.server_host, self.config.server_port)
                    self.rcon.command('list')
                    return
                except AgentError as error:
                    log.info('server not ready yet: %s', error)
            if self.clock() - last_beat >= 60:
                beat()
                last_beat = self.clock()
            self.sleep(5)
        raise AgentError(f'server did not become healthy within {self.config.start_timeout}s')


# --- deployment ------------------------------------------------------------------

class Deployment:
    def __init__(self, config: Config, api: Api, server: Server, backup: TarBackup,
                 fetch: Callable[[str, Path, int, str], str], clock: Callable[[], float],
                 sleep: Callable[[float], None], agent: str):
        self.config, self.api, self.server, self.backup = config, api, server, backup
        self.fetch, self.clock, self.sleep, self.agent = fetch, clock, sleep, agent
        self.root = config.deploy_root
        self.run_id: str | None = None
        self.notes: list[str] = []
        self.access_error: str | None = None

    def note(self, message: str) -> None:
        log.info(message)
        self.notes.append(message)

    def beat(self) -> None:
        if self.run_id:
            try:
                self.api.heartbeat(self.run_id)
            except AgentError as error:
                log.warning('heartbeat failed: %s', error)

    def execute(self, dry_run: bool = False) -> int:
        plan = self.api.plan()
        active = plan.get('activeRelease')
        if not isinstance(active, str) or not TAG.fullmatch(active):
            raise AgentError('the profile has no active release; record the running release first')
        target = plan.get('target')
        if target:
            kind, version = 'deploy', target.get('version')
            if not isinstance(version, str) or not TAG.fullmatch(version) or version == active:
                raise AgentError('the plan target is not a deployable release')
        elif self.config.weekly_restart:
            kind, version = 'restart', active
        else:
            log.info('nothing to deploy for %s (active %s)', self.config.profile, active)
            return 0
        if not self.installed(active):
            raise AgentError(f'{self.root / "current"} must point to releases/{active}; adopt the running release with --adopt')
        release_dir = pack_sha1 = None
        if kind == 'deploy':
            release_dir, pack_sha1 = self.prepare(target)
        self.check_disk()
        lead = max(self.config.announce_minutes)
        maintenance_at = self.clock() + lead * 60
        if dry_run:
            for minutes in sorted(set(self.config.announce_minutes), reverse=True):
                log.info('dry run: T-%d announce: %s', minutes, announcement(kind, minutes))
            log.info('dry run: would %s %s -> %s at %s', kind, active, version, time.ctime(maintenance_at))
            return 0
        self.announce(kind, maintenance_at)
        run = self.api.start(kind, version, active, self.agent)
        self.run_id = run['id']
        self.note(f'{kind} {active} -> {version} started as run {self.run_id}')
        state = Progress()
        try:
            self.apply(kind, active, version, release_dir, pack_sha1, state)
        except AgentError as error:
            log.error('deployment failed: %s', error)
            self.note(f'failed: {error}')
            result = self.recover(active, state)
            self.api.finish(self.run_id, result, '\n'.join(self.notes))
            return 1
        manifest = manifest_sha256(self.root / 'releases' / version) if kind == 'deploy' else ''
        self.api.finish(self.run_id, 'succeeded', '\n'.join(self.notes), manifest)
        self.cleanup(version, active)
        return 1 if self.access_error else 0

    def prepare(self, target: dict) -> tuple[Path, str]:
        version = target['version']
        downloads = self.root / 'downloads'
        downloads.mkdir(parents=True, exist_ok=True)
        server, pack = target.get('server') or {}, target.get('resourcepack') or {}
        for asset, name in ((server, 'server.zip'), (pack, 'resourcepack.zip')):
            if asset.get('url') != f'{RELEASE_DOWNLOAD}{version}/{name}':
                raise AgentError(f'plan {name} URL does not belong to release {version}')
        archive = downloads / f'{version}-server.zip'
        self.fetch(server['url'], archive, server['size'], server['sha256'])
        pack_sha1 = self.fetch(pack['url'], downloads / f'{version}-resourcepack.zip', pack['size'], pack['sha256'])
        release_dir = extract_release(archive, self.root / 'releases', version)
        archive.unlink(missing_ok=True)
        log.info('prepared release %s', version)
        return release_dir, pack_sha1

    def installed(self, active: str) -> bool:
        current = self.root / 'current'
        return current.is_symlink() and Path(os.readlink(current)) == Path('releases') / active \
            and (self.root / 'releases' / active / 'mods').is_dir()

    def adopt(self, archive: Path) -> int:
        """Register the server pack of the running release as releases/<active>."""
        active = self.api.plan().get('activeRelease')
        if not isinstance(active, str) or not TAG.fullmatch(active):
            raise AgentError('the profile has no active release; record the running release first')
        extract_release(archive, self.root / 'releases', active)
        switch_link(self.root / 'current', Path('releases') / active)
        log.info('adopted %s; mount %s over the server mods/ directory', active, self.root / 'current' / 'mods')
        return 0

    def check_disk(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        needed = int(self.backup.latest_size() * 1.5)
        free = shutil.disk_usage(self.root).free
        if free < needed:
            raise AgentError(f'not enough disk space for a backup: {free} bytes free, {needed} needed')

    def announce(self, kind: str, maintenance_at: float) -> None:
        for minutes in sorted(set(self.config.announce_minutes), reverse=True):
            wait = maintenance_at - minutes * 60 - self.clock()
            if wait > 0:
                self.sleep(wait)
            try:
                self.server.rcon.command('say ' + announcement(kind, minutes))
            except AgentError as error:
                log.warning('announcement failed: %s', error)
        wait = maintenance_at - self.clock()
        if wait > 0:
            self.sleep(wait)

    def apply(self, kind: str, active: str, version: str, release_dir: Path | None, pack_sha1: str | None, state: 'Progress') -> None:
        root = self.config.server_root
        state.work = self.root / 'runs' / self.run_id
        state.work.mkdir(parents=True)
        state.stopping = True
        self.server.stop()
        state.stopped = True
        self.note('server stopped')
        self.beat()
        properties = read_properties(root / 'server.properties')
        level = properties.get('level-name', 'world')
        if not relative_path(level):
            raise AgentError('level-name is not a relative directory')
        members = [m for m in (level, 'server.properties', 'whitelist.json', *MANAGED_FILES, *EDITABLE_DEFAULTS) if (root / m).exists()]
        state.backup_members = members
        state.backup = self.backup.create(root, members, [f'{level}/{e}' for e in self.config.backup_exclude],
                                          time.strftime('%Y%m%d%H%M%S', time.gmtime(self.clock())) + f'-{kind}-{version}')
        self.note(f'backup {state.backup.name}')
        self.beat()
        shutil.copy2(root / 'server.properties', state.work / 'server.properties')
        state.whitelist = (root / 'whitelist.json').read_bytes() if (root / 'whitelist.json').is_file() else None
        state.whitelist_flags = {key: properties.get(key, 'false') for key in ('white-list', 'enforce-whitelist')}
        self.block(root)
        state.blocked = True
        if kind == 'deploy':
            self.replace(root, version, release_dir, pack_sha1, state)
        started = self.server.recreate()
        state.started_new = True
        self.beat()
        self.server.wait_healthy(started, self.beat)
        self.note('health checks passed')
        state.blocked = False
        try:
            self.unblock(root, state)
        except (AgentError, OSError) as error:
            # The new release is healthy; rolling back would not restore access either.
            self.access_error = str(error)
            self.note(f'player access was not restored; finish it manually: {error}')

    def block(self, root: Path) -> None:
        atomic_write(root / 'whitelist.json', b'[]\n')
        update_properties(root / 'server.properties', {'white-list': 'true', 'enforce-whitelist': 'true'})

    def unblock(self, root: Path, state: 'Progress') -> None:
        if state.whitelist is None:
            (root / 'whitelist.json').unlink(missing_ok=True)
        else:
            atomic_write(root / 'whitelist.json', state.whitelist)
        self.server.rcon.command('whitelist reload')
        self.server.rcon.command('whitelist on' if state.whitelist_flags['white-list'] == 'true' else 'whitelist off')
        update_properties(root / 'server.properties', state.whitelist_flags)
        self.note('player access restored')

    def replace(self, root: Path, version: str, release_dir: Path, pack_sha1: str, state: 'Progress') -> None:
        for relative in MANAGED_FILES + EDITABLE_DEFAULTS:
            current = root / relative
            if current.is_file():
                saved = state.work / 'files' / relative
                saved.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(current, saved)
        state.saved_files = True
        for relative in MANAGED_FILES:
            source = release_dir / relative
            if source.is_file():
                (root / relative).parent.mkdir(parents=True, exist_ok=True)
                atomic_write(root / relative, source.read_bytes())
        for relative in EDITABLE_DEFAULTS:
            if (release_dir / relative).is_file() and not (root / relative).exists():
                shutil.copy2(release_dir / relative, root / relative)
        if self.config.manage_resource_pack:
            url = f'{RELEASE_DOWNLOAD}{version}/resourcepack.zip'
            update_properties(root / 'server.properties', {
                'resource-pack': url, 'resource-pack-sha1': pack_sha1,
                'resource-pack-id': str(uuid.uuid5(uuid.NAMESPACE_URL, url))})
        switch_link(self.root / 'current', Path('releases') / version)
        state.replaced = True
        self.note(f'release files switched to {version}')

    def recover(self, active: str, state: 'Progress') -> str:
        root = self.config.server_root
        if state.stopping and not state.stopped:
            self.note('server stop did not complete; leaving it for an operator')
            return 'failed'
        if not state.stopped:
            return 'rolled_back'
        try:
            with contextlib.suppress(AgentError):
                self.server.compose('down', '-t', str(self.config.stop_timeout), timeout=self.config.stop_timeout + 60)
            if state.replaced or state.saved_files:
                switch_link(self.root / 'current', Path('releases') / active)
                for relative in MANAGED_FILES + EDITABLE_DEFAULTS:
                    saved = state.work / 'files' / relative
                    if saved.is_file():
                        atomic_write(root / relative, saved.read_bytes())
                    else:
                        (root / relative).unlink(missing_ok=True)
            if state.started_new and state.backup:
                self.backup.restore(state.backup, root, [m for m in state.backup_members if m not in ('server.properties', 'whitelist.json')])
                self.note('world restored from backup')
            if (state.work / 'server.properties').is_file():
                shutil.copy2(state.work / 'server.properties', root / 'server.properties')
            if state.whitelist_flags:
                self.block(root)
            started = self.server.recreate()
            self.server.wait_healthy(started, self.beat)
            if state.whitelist_flags:
                self.unblock(root, state)
            self.note(f'rolled back to {active}')
            return 'rolled_back'
        except (AgentError, OSError) as error:
            self.note(f'rollback failed: {error}')
            return 'failed'

    def cleanup(self, version: str, previous: str) -> None:
        releases = self.root / 'releases'
        keep = {version, previous}
        tags = sorted(p.name for p in releases.iterdir() if p.is_dir() and TAG.fullmatch(p.name))
        for tag in tags[:-self.config.keep_releases]:
            if tag not in keep:
                shutil.rmtree(releases / tag)
        for download in (self.root / 'downloads').glob('*-resourcepack.zip'):
            if not download.name.startswith(version):
                download.unlink()
        runs = sorted((p for p in (self.root / 'runs').iterdir() if p.is_dir()), key=lambda p: p.stat().st_mtime)
        for old in runs[:-self.config.keep_backups]:
            shutil.rmtree(old)


@dataclass
class Progress:
    work: Path | None = None
    stopping: bool = False
    stopped: bool = False
    backup: Path | None = None
    backup_members: list[str] = field(default_factory=list)
    whitelist: bytes | None = None
    whitelist_flags: dict[str, str] = field(default_factory=dict)
    blocked: bool = False
    saved_files: bool = False
    replaced: bool = False
    started_new: bool = False


def announcement(kind: str, minutes: int) -> str:
    reason = '서버 업데이트' if kind == 'deploy' else '정기 점검'
    if minutes == 0:
        return f'[Minefed] {reason}를 시작합니다. 잠시 후 다시 접속해 주세요.'
    return f'[Minefed] {minutes}분 뒤 {reason}로 서버가 재시작됩니다. 잠시 접속이 끊겨요.'


def switch_link(link: Path, target: Path) -> None:
    temporary = link.with_name('.' + link.name + '.next')
    temporary.unlink(missing_ok=True)
    temporary.symlink_to(target, target_is_directory=True)
    os.replace(temporary, link)


@contextlib.contextmanager
def exclusive(lock: Path):
    import fcntl
    lock.parent.mkdir(parents=True, exist_ok=True)
    with lock.open('w') as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise AgentError('another deployment agent is running for this profile') from None
        yield


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--config', type=Path, required=True)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--dry-run', action='store_true', help='download and verify only; no announcements, stop or API state change')
    mode.add_argument('--adopt', type=Path, metavar='SERVER_ZIP', help="register the running release's server.zip before the first deployment")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format='%(levelname)s %(message)s', stream=sys.stdout)
    try:
        config = Config.load(args.config)
        api = Api(config.api_url, config.profile, read_secret(config.token_file))
        rcon = Rcon(config.rcon_host, config.rcon_port, read_secret(config.rcon_password_file))
        runner = Runner()
        server = Server(config, runner, rcon, server_list_ping, time.time, time.sleep)
        backup = TarBackup(runner, config.deploy_root / 'backups', config.keep_backups)
        deployment = Deployment(config, api, server, backup, download, time.time, time.sleep, socket.gethostname()[:253] or 'minefed-agent')
        with exclusive(config.deploy_root / f'.{config.profile}.lock'):
            if args.adopt:
                return deployment.adopt(args.adopt)
            return deployment.execute(dry_run=args.dry_run or config.dry_run)
    except AgentError as error:
        log.error('%s', error)
        return 1


if __name__ == '__main__':
    sys.exit(main())
