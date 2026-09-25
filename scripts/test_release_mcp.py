"""Offline policy tests and opt-in real Java HTTP/package checks for the observer mod."""
import base64
import http.client
import json
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import time
import unittest
import zipfile

import build_modpack as builder
import mods
import release_mcp as mcp


class PolicyTests(unittest.TestCase):
    def test_disabled_without_inputs_and_invalid_enablement(self):
        self.assertEqual(([], None), mcp.prepare(Path('/unused'), {}, Path('/unused')))
        for value in (None, 1, 'true', {}):
            with self.subTest(value=value), self.assertRaises(mods.ModError):
                mcp.prepare(Path('/unused'), {'minecraftMcpMod': value}, Path('/unused'))


@unittest.skipUnless(os.environ.get('MINEFED_MCP_JAVA_TESTS') == '1', 'Set MINEFED_MCP_JAVA_TESTS=1 for pinned inputs/JDK 17 checks')
class JavaObservationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='minefed-mcp-test-')
        cls.work = Path(cls.temp.name)
        cls.selected, cls.snapshot = mcp.build(mcp.ROOT, cls.work, require_committed=False)
        cls.jar = cls.selected[1]
        cls.lock = json.loads((mcp.ROOT / mcp.LOCK).read_text(encoding='utf-8'))
        cls.gson = mcp.pinned_input(mcp.ROOT, cls.lock['compileDependency'])
        cls.java = builder.java_home(mcp.ROOT, 17) / 'bin'
        ext = '.exe' if os.name == 'nt' else ''
        cls.cp = os.pathsep.join(map(str, (cls.work, cls.jar, cls.gson)))
        subprocess.run([str(cls.java / ('javac' + ext)), '--release', '17', '-cp', cls.cp, '-d', str(cls.work),
                        str(mcp.ROOT / 'tools/minecraft-mcp-tests/HttpProbe.java'),
                        str(mcp.ROOT / 'tools/minecraft-mcp-tests/StateProbe.java')], check=True, capture_output=True)
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            cls.port = sock.getsockname()[1]
        cls.log = (cls.work / 'server.log').open('w')
        cls.process = subprocess.Popen([str(cls.java / ('java' + ext)), '-cp', cls.cp,
                                       'xyz.langyo.minecraft.mcp.common.HttpProbe', str(cls.port)],
                                      stdin=subprocess.PIPE, stdout=cls.log, stderr=subprocess.STDOUT)
        for _ in range(100):
            if 'BOUND 127.0.0.1' in (cls.work / 'server.log').read_text():
                break
            if cls.process.poll() is not None:
                raise RuntimeError((cls.work / 'server.log').read_text())
            time.sleep(0.1)
        else:
            cls.process.kill()
            raise RuntimeError('HTTP fixture startup timed out')

    @classmethod
    def tearDownClass(cls):
        cls.process.communicate(b'\n', timeout=10)
        cls.log.close()
        cls.temp.cleanup()

    def request(self, method, path, body=None, headers=None):
        connection = http.client.HTTPConnection('127.0.0.1', self.port, timeout=10)
        try:
            connection.request(method, path, body=body, headers=headers or {})
            response = connection.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            connection.close()

    def command(self, value):
        return self.request('POST', '/api/cmd', json.dumps(value), {'Content-Type': 'application/json'})

    def test_exact_routes_methods_and_browser_isolation(self):
        for path in ('/debug', '/', '/api/events', '/api/calls', '/api/status/extra', '/api/%73tatus'):
            self.assertEqual(404, self.request('GET', path)[0], path)
        for method, path in [('POST', '/api/status'), ('POST', '/api/screenshot'), ('GET', '/api/cmd')]:
            self.assertEqual(405, self.request(method, path)[0])
        self.assertEqual(403, self.request('GET', '/api/status', headers={'Origin': 'https://example.invalid'})[0])
        self.assertEqual(403, self.request('GET', '/api/status', headers={'Host': 'example.invalid'})[0])
        status, headers, body = self.request('GET', '/api/status')
        self.assertEqual(200, status)
        self.assertNotIn('Access-Control-Allow-Origin', headers)
        self.assertTrue(json.loads(body)['readOnly'])
        self.assertEqual('127.0.0.1', json.loads(body)['bindAddress'])

    def test_only_observation_commands_reach_handler(self):
        before = json.loads(self.command({'cmd': 'ping'})[2])['calls']
        for command in ('execute_command', 'click', 'press_key', 'set_gamemode', 'call_screen_method',
                        'enter_control_mode', 'screenshot_to_file', 'release_mouse', 'screenshot', 'unknown'):
            self.assertEqual(403, self.command({'method': command})[0], command)
        after = json.loads(self.command({'cmd': 'ping'})[2])['calls']
        self.assertEqual(before + 1, after)
        for command in ('get_player_info', 'get_world_info', 'get_screen_buttons'):
            status, _, body = self.command({'method': command, 'params': {}})
            self.assertEqual(200, status)
            if command == 'get_screen_buttons':
                self.assertEqual(command, json.loads(body)['method'])
            else:
                self.assertFalse(json.loads(body)['available'])
                self.assertIn('error', json.loads(body))

    def test_malformed_and_oversized_requests_are_rejected(self):
        for body in ('null', '[]', '{', '{"cmd":{}}'):
            self.assertEqual(400, self.request('POST', '/api/cmd', body)[0])
        self.assertEqual(413, self.request('POST', '/api/cmd', 'x' * 16385)[0])

    def test_screenshot_response_keeps_upstream_image_shape(self):
        status, _, body = self.request('GET', '/api/screenshot')
        self.assertEqual(200, status, body)
        result = json.loads(body)
        self.assertEqual((1, 1), (result['width'], result['height']))
        for key in ('original', 'grid'):
            self.assertTrue(base64.b64decode(result[key].partition(',')[2]).startswith(b'\x89PNG\r\n\x1a\n'))

    def test_package_preserves_upstream_entries_and_adds_license_source(self):
        upstream = mcp.pinned_input(mcp.ROOT, self.lock['upstream'])
        with zipfile.ZipFile(upstream) as original, zipfile.ZipFile(self.jar) as modified:
            self.assertIsNone(modified.testzip())
            metadata = json.loads(modified.read('fabric.mod.json'))
            self.assertEqual('0.3.0+minefed.1', metadata['version'])
            self.assertEqual('client', metadata['environment'])
            self.assertEqual('1.20.4', metadata['depends']['minecraft'])
            for name in original.namelist():
                if name.endswith('/') or name == 'fabric.mod.json' or name.startswith(mcp.SERVER):
                    continue
                self.assertEqual(original.read(name), modified.read(name), name)
            for name in ('LICENSE-MIT', 'LICENSE-APACHE', 'LICENSE-CC0', 'NOTICE.md', 'src/' + mcp.SERVER + '.java'):
                self.assertIn('META-INF/minefed/' + name, modified.namelist())
            self.assertFalse(any(n.startswith('com/google/gson/') for n in modified.namelist()))
        self.assertTrue(self.selected[0]['client'])
        self.assertFalse(self.selected[0]['server'])

    def test_intermediary_state_queries_do_not_fabricate_defaults(self):
        executable = 'java.exe' if os.name == 'nt' else 'java'
        output = subprocess.run([str(self.java / executable), '-cp', self.cp,
                                 'xyz.langyo.minecraft.mcp.common.StateProbe'],
                                check=True, capture_output=True, text=True).stdout
        missing, player, world, unsupported = map(json.loads, output.splitlines())
        self.assertEqual({'available': False, 'error': 'not_in_world'}, missing)
        self.assertEqual((12.25, 80.5, -9.75, 135.5, -30.25), tuple(player[k] for k in ('x', 'y', 'z', 'yaw', 'pitch')))
        self.assertEqual('12.250 80.500 -9.750', player['pos'])
        self.assertEqual((17.5, 13, 'creative'), (player['health'], player['food'], player['gamemode']))
        self.assertEqual((13001, 77002, 'hard', 'thunder'), tuple(world[k] for k in ('time', 'game_time', 'difficulty', 'weather')))
        self.assertIsNone(world['world_name'])
        self.assertFalse(world['world_name_available'])
        self.assertFalse(unsupported['available'])


if __name__ == '__main__':
    unittest.main()
