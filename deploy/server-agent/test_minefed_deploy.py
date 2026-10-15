"""Tests for the deployment agent with fake API, podman, RCON and backups (Linux)."""
from __future__ import annotations

import hashlib
import io
import json
import os
import re
from pathlib import Path
import shutil
import socket
import struct
import tempfile
import threading
import unittest
import zipfile

import minefed_deploy as agent

ACTIVE, TARGET = '20261001000000', '20261015120000'
RELEASE = agent.RELEASE_DOWNLOAD


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def server_pack(path: Path, tag: str, mods: dict[str, bytes], *, corrupt: bool = False, extra: str | None = None) -> None:
    files = {f'mods/{name}': data for name, data in mods.items()}
    bluemap = {'config/bluemap/packs/10-minefed.zip': f'pack {tag}'.encode()}
    generated = {'config/mtr/bluemap-vehicles.json': f'{{"release":"{tag}"}}'.encode()}
    editable = b'{"schema":1,"worlds":{}}'
    record = lambda p, d: {'path': p, 'sha256': digest(d), 'size': len(d)}
    manifest = {'schemaVersion': 1, 'version': tag, 'side': 'server',
                'files': [record(p, d) for p, d in files.items()],
                'plugins': [record('plugins/TCPShield.jar', b'plugin')],
                'bluemapPacks': [record(p, d) for p, d in bluemap.items()],
                'generatedConfigs': [record(p, d) for p, d in generated.items()],
                'editableDefaults': [record('config/mtr/bluemap-public-routes.json', editable) | {'preserveExisting': True}]}
    with zipfile.ZipFile(path, 'w') as archive:
        for name, data in {**files, **bluemap, **generated}.items():
            archive.writestr(name, b'tampered' if corrupt and name.startswith('mods/') else data)
        archive.writestr('plugins/TCPShield.jar', b'plugin')
        archive.writestr('config/mtr/bluemap-public-routes.json', editable)
        archive.writestr('download-manifest.json', json.dumps(manifest))
        archive.writestr('MINEFED-RELEASE.json', json.dumps({'version': tag, 'side': 'server', 'files': manifest['files']}))
        if extra:
            archive.writestr(extra, b'x')


class FakeApi:
    def __init__(self, plan: dict):
        self.plan_value, self.calls, self.start_error = plan, [], None

    def plan(self):
        self.calls.append(('plan',))
        return json.loads(json.dumps(self.plan_value))

    def start(self, kind, target, previous, agent_name):
        self.calls.append(('start', kind, target, previous))
        if self.start_error:
            raise self.start_error
        return {'id': '11111111-2222-4333-8444-555555555555'}

    def heartbeat(self, run_id):
        self.calls.append(('heartbeat',))

    def finish(self, run_id, result, message, manifest=''):
        self.calls.append(('finish', result, manifest))
        self.finish_message = message


class FakeRcon:
    def __init__(self):
        self.commands = []

    def command(self, command):
        self.commands.append(command)
        return ''


class Clock:
    def __init__(self):
        self.now = 1_800_000_000.0

    def time(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


class FakeRunner:
    """Simulates podman compose; each `up` starts the server described by `starts`."""

    def __init__(self, test: 'DeploymentTests'):
        self.test, self.commands, self.starts = test, [], []

    def run(self, args, *, cwd=None, timeout=None):
        self.commands.append(args[2:] if args[:2] == ['podman', 'compose'] else args)
        if args[2:4] == ['up', '-d']:
            outcome = self.starts.pop(0) if self.starts else 'ok'
            logs = self.test.server_root / 'logs'
            latest = logs / 'latest.log'
            if latest.exists():
                latest.rename(logs / f'previous-{len(self.commands)}.log')
            mods = sorted(p.name for p in (self.test.deploy_root / 'current' / 'mods').iterdir())
            (self.test.server_root / 'world' / 'level.dat').write_text('touched by ' + ','.join(mods))
            latest.write_text('[Server thread/INFO]: Done (3.2s)! For help, type "help"\n' if outcome == 'ok'
                              else '[main/ERROR]: Mixin apply failed mtr.mixins.json\n')
        return ''


class FakeBackup:
    def __init__(self, directory: Path):
        self.directory = directory

    def latest_size(self):
        return 0

    def create(self, root, members, excludes, name):
        archive = self.directory / name
        for member in members:
            source, destination = root / member, archive / member
            destination.parent.mkdir(parents=True, exist_ok=True)
            (shutil.copytree if source.is_dir() else shutil.copy2)(source, destination)
        return archive

    def restore(self, archive, root, members):
        for member in members:
            target = root / member
            shutil.rmtree(target) if target.is_dir() else target.unlink(missing_ok=True)
        shutil.copytree(archive, root, dirs_exist_ok=True)


class DeploymentTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        base = Path(self.temporary.name)
        self.deploy_root, self.server_root, self.assets = base / 'deploy', base / 'server', base / 'assets'
        for path in (self.deploy_root, self.server_root / 'world', self.server_root / 'logs', self.assets,
                     self.server_root / 'config/bluemap/packs', self.server_root / 'config/mtr'):
            path.mkdir(parents=True)
        self.properties = ('#Minecraft server properties\nlevel-name=world\nwhite-list=false\n'
                           'enforce-whitelist=false\nresource-pack=https\\://old.example/pack.zip\nmotd=Minefed\n')
        (self.server_root / 'server.properties').write_text(self.properties, encoding='latin-1')
        (self.server_root / 'whitelist.json').write_text('[{"name":"alice"}]')
        (self.server_root / 'world' / 'level.dat').write_text('original world')
        (self.server_root / 'logs' / 'latest.log').write_text('Done (1.0s)! from the previous start\n')
        (self.server_root / 'config/bluemap/packs/10-minefed.zip').write_bytes(f'pack {ACTIVE}'.encode())
        (self.server_root / 'config/mtr/bluemap-public-routes.json').write_text('{"schema":1,"worlds":{"mine":{}}}')
        self.config = agent.Config(profile='prod', api_url='https://api.example', token_file=base / 'token',
                                   deploy_root=self.deploy_root, server_root=self.server_root,
                                   compose_dir=base, rcon_password_file=base / 'rcon')
        server_pack(self.assets / 'active.zip', ACTIVE, {'a.jar': b'a1', 'b.jar': b'b1'})
        server_pack(self.assets / 'target.zip', TARGET, {'a.jar': b'a2', 'c.jar': b'c2'})
        self.pack = b'resource pack bytes'
        self.api = FakeApi(self.plan())
        self.clock, self.rcon, self.runner = Clock(), FakeRcon(), FakeRunner(self)
        self.pings = []

    def tearDown(self):
        self.temporary.cleanup()

    def plan(self, target: bool = True) -> dict:
        server = (self.assets / 'target.zip').read_bytes() if (self.assets / 'target.zip').exists() else b''
        value = {'profile': 'prod', 'activeRelease': ACTIVE, 'approvalMode': 'manual', 'target': None}
        if target:
            value['target'] = {'version': TARGET,
                               'server': {'url': f'{RELEASE}{TARGET}/server.zip', 'size': len(server), 'sha256': digest(server)},
                               'resourcepack': {'url': f'{RELEASE}{TARGET}/resourcepack.zip', 'size': len(self.pack), 'sha256': digest(self.pack)}}
        return value

    def fetch(self, url, destination, size, sha256):
        data = (self.assets / 'target.zip').read_bytes() if url.endswith('server.zip') else self.pack
        if len(data) != size or digest(data) != sha256:
            raise agent.AgentError('mismatch')
        destination.write_bytes(data)
        return hashlib.sha1(data).hexdigest()

    def deployment(self) -> agent.Deployment:
        server = agent.Server(self.config, self.runner, self.rcon, lambda host, port: self.pings.append(port) or {},
                              self.clock.time, self.clock.sleep)
        return agent.Deployment(self.config, self.api, server, FakeBackup(self.deploy_root / 'backups'),
                                self.fetch, self.clock.time, self.clock.sleep, 'test-host')

    def adopt(self):
        self.assertEqual(self.deployment().adopt(self.assets / 'active.zip'), 0)

    def props(self) -> dict:
        return agent.read_properties(self.server_root / 'server.properties')

    def link(self) -> str:
        return os.readlink(self.deploy_root / 'current')

    def test_deploy_replaces_release_files_and_restores_access(self):
        self.adopt()
        self.assertEqual(self.link(), f'releases/{ACTIVE}')
        self.assertEqual(self.deployment().execute(), 0)
        self.assertEqual(self.link(), f'releases/{TARGET}')
        self.assertEqual(sorted(p.name for p in (self.deploy_root / 'current/mods').iterdir()), ['a.jar', 'c.jar'])
        root = self.server_root
        self.assertEqual((root / 'config/bluemap/packs/10-minefed.zip').read_bytes(), f'pack {TARGET}'.encode())
        self.assertEqual((root / 'config/mtr/bluemap-vehicles.json').read_text(), f'{{"release":"{TARGET}"}}')
        self.assertIn('"mine"', (root / 'config/mtr/bluemap-public-routes.json').read_text())
        props = self.props()
        url = f'{RELEASE}{TARGET}/resourcepack.zip'
        self.assertEqual(props['resource-pack'], url)
        self.assertEqual(props['resource-pack-sha1'], hashlib.sha1(self.pack).hexdigest())
        self.assertEqual(props['resource-pack-id'], str(agent.uuid.uuid5(agent.uuid.NAMESPACE_URL, url)))
        self.assertEqual((props['white-list'], props['enforce-whitelist'], props['motd']), ('false', 'false', 'Minefed'))
        self.assertIn('#Minecraft server properties', (root / 'server.properties').read_text(encoding='latin-1'))
        self.assertEqual((root / 'whitelist.json').read_text(), '[{"name":"alice"}]')
        says = [c for c in self.rcon.commands if c.startswith('say ')]
        self.assertEqual(len(says), 4)
        self.assertIn('30분 뒤 서버 업데이트', says[0])
        self.assertEqual(self.rcon.commands[4:], ['save-all flush', 'list', 'whitelist reload', 'whitelist off'])
        self.assertEqual([c[0] for c in self.runner.commands], ['stop', 'down', 'up'])
        self.assertEqual(self.clock.now - 1_800_000_000.0 >= 30 * 60, True)
        self.assertEqual([c[0] for c in self.api.calls if c[0] != 'heartbeat'], ['plan', 'plan', 'start', 'finish'])
        self.assertEqual(self.api.calls[-1][:2], ('finish', 'succeeded'))
        self.assertEqual(self.api.calls[-1][2], agent.manifest_sha256(self.deploy_root / 'releases' / TARGET))
        self.assertEqual(self.pings, [25565])
        self.assertTrue(list((self.deploy_root / 'backups').iterdir()))

    def test_weekly_restart_keeps_release(self):
        self.adopt()
        self.api.plan_value = self.plan(target=False)
        self.assertEqual(self.deployment().execute(), 0)
        self.assertEqual(self.link(), f'releases/{ACTIVE}')
        self.assertEqual(self.props()['resource-pack'], 'https://old.example/pack.zip')
        self.assertIn(('start', 'restart', ACTIVE, ACTIVE), self.api.calls)
        self.assertEqual(self.api.calls[-1], ('finish', 'succeeded', ''))
        self.assertIn('정기 점검', [c for c in self.rcon.commands if c.startswith('say ')][0])

    def test_nothing_to_do_without_weekly_restart(self):
        self.adopt()
        self.config.weekly_restart = False
        self.api.plan_value = self.plan(target=False)
        self.assertEqual(self.deployment().execute(), 0)
        self.assertEqual(self.runner.commands, [])
        self.assertNotIn('start', [c[0] for c in self.api.calls])

    def test_failed_start_rolls_back_files_world_and_settings(self):
        self.adopt()
        self.runner.starts = ['fail', 'ok']
        self.assertEqual(self.deployment().execute(), 1)
        self.assertEqual(self.link(), f'releases/{ACTIVE}')
        root = self.server_root
        self.assertEqual((root / 'config/bluemap/packs/10-minefed.zip').read_bytes(), f'pack {ACTIVE}'.encode())
        self.assertFalse((root / 'config/mtr/bluemap-vehicles.json').exists())
        self.assertEqual((root / 'world/level.dat').read_text(), 'touched by a.jar,b.jar')
        self.assertEqual(self.props()['resource-pack'], 'https://old.example/pack.zip')
        self.assertNotIn('resource-pack-sha1', self.props())
        self.assertEqual((root / 'whitelist.json').read_text(), '[{"name":"alice"}]')
        self.assertEqual(self.props()['white-list'], 'false')
        self.assertEqual(self.api.calls[-1][:2], ('finish', 'rolled_back'))
        self.assertIn('Mixin apply failed', self.api.finish_message)
        self.assertIn('world restored from backup', self.api.finish_message)
        self.assertEqual([c[0] for c in self.runner.commands], ['stop', 'down', 'up', 'down', 'down', 'up'])

    def test_world_is_restored_before_the_previous_release_starts(self):
        self.adopt()
        self.runner.starts = ['fail', 'ok']
        original = FakeBackup.restore
        observed = []

        def restore(backup, archive, root, members):
            original(backup, archive, root, members)
            observed.append((root / 'world/level.dat').read_text())
        FakeBackup.restore = restore
        try:
            self.deployment().execute()
        finally:
            FakeBackup.restore = original
        self.assertEqual(observed, ['original world'])

    def test_failed_rollback_keeps_players_out(self):
        self.adopt()
        self.runner.starts = ['fail', 'fail']
        self.assertEqual(self.deployment().execute(), 1)
        self.assertEqual(self.api.calls[-1][:2], ('finish', 'failed'))
        self.assertEqual((self.server_root / 'whitelist.json').read_text(), '[]\n')
        self.assertEqual(self.props()['white-list'], 'true')
        self.assertIn('rollback failed', self.api.finish_message)

    def test_access_restore_failure_does_not_roll_back(self):
        self.adopt()
        deployment = self.deployment()

        def command(text):
            if text.startswith('whitelist'):
                raise agent.AgentError('RCON unavailable')
            return ''
        deployment.server.rcon.command = command
        self.assertEqual(deployment.execute(), 1)
        self.assertEqual(self.link(), f'releases/{TARGET}')
        self.assertEqual(self.api.calls[-1][:2], ('finish', 'succeeded'))
        self.assertIn('player access was not restored', self.api.finish_message)

    def test_rejected_start_changes_nothing(self):
        self.adopt()
        self.api.start_error = agent.ApiError(409, 'CONFLICT', 'another deployment is running')
        with self.assertRaises(agent.ApiError):
            self.deployment().execute()
        self.assertEqual(self.runner.commands, [])
        self.assertEqual(self.link(), f'releases/{ACTIVE}')

    def test_unverified_release_is_rejected_before_announcing(self):
        self.adopt()
        for options in ({'corrupt': True}, {'extra': '../escape.jar'}):
            shutil.rmtree(self.deploy_root / 'releases' / TARGET, ignore_errors=True)
            server_pack(self.assets / 'target.zip', TARGET, {'a.jar': b'a2'}, **options)
            self.api.plan_value = self.plan()
            with self.subTest(options=options), self.assertRaises(agent.AgentError):
                self.deployment().execute()
        self.assertEqual(self.rcon.commands, [])
        self.assertNotIn('start', [c[0] for c in self.api.calls])
        self.assertFalse((self.deploy_root / 'releases' / TARGET).exists())

    def test_foreign_asset_url_is_rejected(self):
        self.adopt()
        self.api.plan_value['target']['server']['url'] = f'{RELEASE}{ACTIVE}/server.zip'
        with self.assertRaises(agent.AgentError):
            self.deployment().execute()

    def test_requires_an_adopted_active_release(self):
        with self.assertRaisesRegex(agent.AgentError, '--adopt'):
            self.deployment().execute()
        server_pack(self.assets / 'wrong.zip', TARGET, {'a.jar': b'a'})
        with self.assertRaises(agent.AgentError):
            self.deployment().adopt(self.assets / 'wrong.zip')

    def test_dry_run_only_prepares(self):
        self.adopt()
        self.assertEqual(self.deployment().execute(dry_run=True), 0)
        self.assertTrue((self.deploy_root / 'releases' / TARGET / 'mods' / 'c.jar').is_file())
        self.assertEqual(self.rcon.commands, [])
        self.assertEqual(self.runner.commands, [])
        self.assertEqual(self.link(), f'releases/{ACTIVE}')
        self.assertNotIn('start', [c[0] for c in self.api.calls])

    def test_old_releases_are_pruned(self):
        self.adopt()
        self.config.keep_releases = 2
        for tag in ('20260101000000', '20260201000000'):
            (self.deploy_root / 'releases' / tag / 'mods').mkdir(parents=True)
        self.deployment().execute()
        self.assertEqual(sorted(p.name for p in (self.deploy_root / 'releases').iterdir()), [ACTIVE, TARGET])


class Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class Opener:
    def __init__(self, data):
        self.data = data

    def open(self, request, timeout=None):
        return Response(self.data)


class UnitTests(unittest.TestCase):
    def test_download_verifies_published_digest(self):
        data = b'server pack'
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / 'server.zip'
            url = f'{RELEASE}{TARGET}/server.zip'
            self.assertEqual(agent.download(url, destination, len(data), digest(data), Opener(data)), hashlib.sha1(data).hexdigest())
            self.assertEqual(destination.read_bytes(), data)
            for args in ((url, len(data), digest(b'other')), (url, len(data) - 1, digest(data)),
                         ('https://example.com/server.zip', len(data), digest(data))):
                destination.unlink(missing_ok=True)
                with self.subTest(args=args[1:]), self.assertRaises(agent.AgentError):
                    agent.download(args[0], destination, args[1], args[2], Opener(data))
                self.assertFalse(destination.exists())
                self.assertEqual(list(Path(directory).iterdir()), [])

    def test_properties_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'server.properties'
            path.write_text('# comment\nlevel-name=my\\ world\nresource-pack=https\\://a/b\nmotd=\\u00e9\n', encoding='latin-1')
            values = agent.read_properties(path)
            self.assertEqual((values['level-name'], values['resource-pack'], values['motd']), ('my world', 'https://a/b', 'é'))
            agent.update_properties(path, {'resource-pack': 'https://c/d', 'white-list': 'true'})
            text = path.read_text(encoding='latin-1')
            self.assertTrue(text.startswith('# comment\nlevel-name=my\\ world\nresource-pack=https://c/d\nmotd=\\u00e9\n'))
            self.assertTrue(text.endswith('white-list=true\n'))

    def test_config_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'prod.toml'
            base = ('profile = "prod"\napi_url = "https://api.minefed.team"\ntoken_file = "/etc/t"\n'
                    'deploy_root = "/srv/d"\nserver_root = "/srv/s"\ncompose_dir = "/srv/c"\nrcon_password_file = "/etc/r"\n')
            path.write_text(base)
            self.assertEqual(agent.Config.load(path).announce_minutes, [30, 10, 5, 1])
            for extra in ('api_url = "http://api.minefed.team"\n', 'profile = "staging"\n', 'unknown = 1\n',
                          'announce_minutes = []\n', 'keep_releases = 1\n', 'backup_exclude = ["../x"]\n'):
                lines = [line for line in base.splitlines(True) if line.split(' = ')[0] != extra.split(' = ')[0]]
                path.write_text(''.join(lines) + extra)
                with self.subTest(extra=extra), self.assertRaises(agent.AgentError):
                    agent.Config.load(path)

    def test_example_configurations_load(self):
        here = Path(__file__).resolve().parent
        with tempfile.TemporaryDirectory() as directory:
            for name, profile in (('prod.toml.example', 'prod'), ('dev.toml.example', 'dev')):
                text = re.sub(r'<[A-Z_]+>', '/srv/minefed', (here / name).read_text(encoding='utf-8'))
                path = Path(directory) / name
                path.write_text(text, encoding='utf-8')
                config = agent.Config.load(path)
                self.assertEqual(config.profile, profile)
                self.assertTrue(config.token_file.is_absolute())
            path.write_text(text.replace('dry_run = false', 'dry_run = "no"'), encoding='utf-8')
            with self.assertRaises(agent.AgentError):
                agent.Config.load(path)

    def test_secret_files_must_be_private(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'token'
            path.write_text('secret-value\n')
            path.chmod(0o644)
            with self.assertRaises(agent.AgentError):
                agent.read_secret(path)
            path.chmod(0o600)
            self.assertEqual(agent.read_secret(path), 'secret-value')

    def serve_once(self, handler):
        listener = socket.socket()
        listener.bind(('127.0.0.1', 0))
        listener.listen()

        def run():
            connection, _ = listener.accept()
            with connection, connection.makefile('rb') as stream:
                handler(connection, stream)
            listener.close()
        thread = threading.Thread(target=run, daemon=True)
        thread.start()
        self.addCleanup(thread.join, 5)
        return listener.getsockname()[1]

    def test_rcon_protocol(self):
        seen = []

        def handler(connection, stream):
            for reply in (b'', b'There are 0 players'):
                length = struct.unpack('<i', stream.read(4))[0]
                data = stream.read(length)
                request_id, kind = struct.unpack('<ii', data[:8])
                seen.append((kind, data[8:-2].decode()))
                payload = struct.pack('<ii', request_id, 0) + reply + b'\x00\x00'
                connection.sendall(struct.pack('<i', len(payload)) + payload)
        port = self.serve_once(handler)
        self.assertEqual(agent.Rcon('127.0.0.1', port, 'pw').command('list'), 'There are 0 players')
        self.assertEqual(seen, [(3, 'pw'), (2, 'list')])

    def test_server_list_ping_protocol(self):
        def handler(connection, stream):
            handshake = stream.read(stream.read(1)[0])
            self.assertEqual(handshake[:3], b'\x00\xfd\x05')  # packet 0, protocol 765
            self.assertEqual(stream.read(2), b'\x01\x00')
            status = json.dumps({'version': {'protocol': 765}}).encode()
            body = b'\x00' + bytes([len(status)]) + status
            connection.sendall(bytes([len(body)]) + body)
        port = self.serve_once(handler)
        self.assertEqual(agent.server_list_ping('127.0.0.1', port)['version']['protocol'], 765)

if __name__ == '__main__':
    unittest.main()
