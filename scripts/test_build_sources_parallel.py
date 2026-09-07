"""Real subprocess scheduling tests; the fixture CLI never launches Gradle."""

from contextlib import ExitStack, redirect_stdout
from concurrent.futures import ThreadPoolExecutor
import io
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

import build_modpack as builder
import build_sources_parallel as parallel


FIXTURE_CLI = r'''
import argparse, json, os, pathlib, sys, time
p = argparse.ArgumentParser()
p.add_argument('command', choices=['source'])
p.add_argument('--run', required=True)
p.add_argument('--id', required=True)
a = p.parse_args()
root = pathlib.Path(__file__).resolve().parents[1]
events = root / 'build/events'
control = json.loads((root / 'build/control.json').read_text())[a.id]
home = pathlib.Path(os.environ['GRADLE_USER_HOME'])
assert home.is_absolute() and home.is_dir()
assert not (home / 'in-use').exists(), 'A Gradle home is shared by concurrent sources'
(home / 'in-use').write_text(a.id)
record = {'id': a.id, 'home': str(home), 'start': time.monotonic_ns(), 'pid': os.getpid(),
          'command': a.command, 'run': a.run, 'marker': os.environ.get('FIXTURE_MARKER')}
(events / (a.id + '.start')).write_text(json.dumps(record))
deadline = time.monotonic() + 10
for other in control.get('waitFor', []):
    while not (events / (other + '.start')).exists():
        if time.monotonic() > deadline: raise RuntimeError('The other slot did not overlap')
        time.sleep(.01)
if control.get('nested'):
    sys.path.insert(0, os.environ['FIXTURE_TOOL_DIR'])
    import build_modpack
    script = 'import os,pathlib,time; pathlib.Path(' + repr(str(events / (a.id + '.wrapper'))) + ').write_text(str(os.getpid())); time.sleep(30)'
    try:
        with (events / (a.id + '.log')).open('w') as log:
            build_modpack.run_gradle_process([sys.executable, '-c', script], cwd=root, env=dict(os.environ), stdout=log)
    except BaseException:
        record['interrupted'] = True
        record['end'] = time.monotonic_ns()
        (events / (a.id + '.json')).write_text(json.dumps(record))
        raise
else:
    time.sleep(control.get('seconds', .08))
(home / 'in-use').unlink()
record['end'] = time.monotonic_ns()
(events / (a.id + '.json')).write_text(json.dumps(record))
sys.exit(control.get('code', 0))
'''


class ParallelSourceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='minefed-parallel-test-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        (self.root / 'scripts').mkdir()
        (self.root / 'scripts/build_modpack.py').write_text(FIXTURE_CLI, encoding='utf-8')
        (self.root / 'build/events').mkdir(parents=True)
        self.identities = ['alpha', 'beta', 'gamma', 'delta', 'epsilon']
        self.run = 'fixture-run'
        self.manifest = {'schemaVersion': 1, 'minecraftVersion': '1.20.4', 'loader': 'fabric', 'entries': []}
        self.plan = {'schemaVersion': 1, 'minecraftVersion': '1.20.4', 'loader': 'fabric', 'entries': []}
        for identity in self.identities:
            source = 'source-' + identity
            (self.root / source).mkdir()
            self.manifest['entries'].append({
                'modId': identity, 'fileName': identity + '.jar', 'sha256': '1' * 64, 'size': 1,
                'included': True, 'management': 'submodule',
                'source': {'path': source, 'url': 'https://github.com/minefed/' + identity,
                           'upstream': 'https://example.invalid/' + identity, 'ref': 'main', 'commit': '2' * 40},
                'artifact': {'path': 'artifacts/local/' + identity + '.jar', 'redistribution': 'local-only'}})
            self.plan['entries'].append({'modId': identity, 'sourcePath': source, 'mode': 'source',
                                         'reason': 'Fixture', 'java': 17, 'tasks': ['remapJar'],
                                         'artifactGlobs': ['build/libs/' + identity + '.jar']})
        self.save_inputs()
        self.control = {identity: {} for identity in self.identities}
        self.write_control()
        self.default_home = self.root / 'original-gradle-home'
        self.default_home.mkdir()
        (self.default_home / 'keep-this-cache').write_text('untouched')
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.dict(os.environ, {'GRADLE_USER_HOME': str(self.default_home),
                                                        'FIXTURE_MARKER': 'inherited',
                                                        'FIXTURE_TOOL_DIR': str(Path(__file__).resolve().parent)}))
        self.stack.enter_context(redirect_stdout(io.StringIO()))

    def save_inputs(self):
        builder.write_json(self.root / 'inventory/mods.lock.json', self.manifest)
        builder.write_json(self.root / builder.RECIPES, self.plan)
        builder.write_json(self.root / 'build/modpack-work' / self.run / 'run.json', {
            'run': self.run, 'planSha256': builder.canonical_digest(self.plan),
            'inventorySha256': builder.canonical_digest(self.manifest)})

    def write_control(self):
        builder.write_json(self.root / 'build/control.json', self.control)

    def events(self):
        return [json.loads(path.read_text()) for path in (self.root / 'build/events').glob('*.json')]

    def test_two_real_children_overlap_with_isolated_homes_and_preserved_environment(self):
        self.control['alpha']['waitFor'] = ['beta']
        self.control['beta']['waitFor'] = ['alpha']
        self.write_control()
        result = parallel.build_sources(self.root, self.run)
        self.assertEqual(set(result), set(self.identities))
        events = self.events()
        self.assertEqual(len(events), len(self.identities))
        timeline = sorted([(e['start'], 1) for e in events] + [(e['end'], -1) for e in events])
        active = maximum = 0
        for _, change in timeline:
            active += change
            maximum = max(maximum, active)
        self.assertEqual(maximum, 2)
        homes = {e['home'] for e in events}
        self.assertEqual(homes, {str(self.root / 'build/modpack-work' / self.run / 'gradle-homes' / ('worker-' + str(i))) for i in range(2)})
        for home in homes:
            ordered = sorted([e for e in events if e['home'] == home], key=lambda e: e['start'])
            for previous, following in zip(ordered, ordered[1:]):
                self.assertLessEqual(previous['end'], following['start'])
        self.assertTrue(all(e['run'] == self.run and e['command'] == 'source' and e['marker'] == 'inherited' for e in events))
        self.assertEqual(os.environ['GRADLE_USER_HOME'], str(self.default_home))
        self.assertEqual((self.default_home / 'keep-this-cache').read_text(), 'untouched')
        self.assertFalse((self.root / 'build/distributions').exists())

    def test_failure_stops_new_sources_but_waits_for_the_other_running_child(self):
        self.control['alpha'] = {'waitFor': ['beta'], 'seconds': .05, 'code': 7}
        self.control['beta'] = {'waitFor': ['alpha'], 'seconds': .35}
        self.write_control()
        with self.assertRaisesRegex(builder.mods.ModError, 'alpha: source CLI exited with status 7'):
            parallel.build_sources(self.root, self.run)
        self.assertEqual({e['id'] for e in self.events()}, {'alpha', 'beta'})
        self.assertFalse(any((self.root / 'build/events' / (identity + '.start')).exists() for identity in self.identities[2:]))
        self.assertFalse(any(self.root.glob('build/modpack-work/*/gradle-homes/*/in-use')))

    def test_custom_gradle_configuration_is_rejected_before_any_child(self):
        for name in ('gradle.properties', 'init.gradle', 'init.gradle.kts', 'init.d/company.gradle', 'init.d/company.gradle.kts'):
            with self.subTest(name=name):
                custom = self.default_home / name
                custom.parent.mkdir(exist_ok=True)
                custom.write_text('custom settings remain untouched')
                with self.assertRaisesRegex(builder.mods.ModError, 'sourceBuildWorkers=1'):
                    parallel.build_sources(self.root, self.run)
                self.assertEqual(custom.read_text(), 'custom settings remain untouched')
                custom.unlink()
        self.assertFalse(list((self.root / 'build/events').iterdir()))
        self.assertFalse((self.root / 'build/modpack-work' / self.run / 'gradle-homes').exists())

    def test_existing_worker_home_is_not_reused_or_deleted(self):
        home = self.root / 'build/modpack-work' / self.run / 'gradle-homes/worker-0'
        home.mkdir(parents=True)
        (home / 'keep').write_text('existing cache')
        with self.assertRaisesRegex(builder.mods.ModError, 'not pristine'):
            parallel.build_sources(self.root, self.run)
        self.assertEqual((home / 'keep').read_text(), 'existing cache')
        self.assertFalse(self.events())

    def test_overlapping_source_directories_are_rejected(self):
        for path in ('source-alpha', 'source-alpha/nested'):
            with self.subTest(path=path):
                self.plan['entries'][1]['sourcePath'] = path
                self.manifest['entries'][1]['source']['path'] = path
                self.save_inputs()
                with self.assertRaisesRegex(builder.mods.ModError, 'directories overlap'):
                    parallel.build_sources(self.root, self.run)
        self.assertFalse(self.events())

    def test_changed_prepared_plan_and_invalid_worker_count_do_not_start_children(self):
        self.plan['entries'][0]['args'] = ['--stacktrace']
        builder.write_json(self.root / builder.RECIPES, self.plan)
        with self.assertRaisesRegex(builder.mods.ModError, 'changed during this run'):
            parallel.build_sources(self.root, self.run)
        for workers in (0, 1, 3, True):
            with self.subTest(workers=workers), self.assertRaises(builder.mods.ModError):
                parallel.build_sources(self.root, self.run, workers)
        self.assertFalse(self.events())

    def test_interrupt_during_dispatch_stops_owned_real_source_processes(self):
        for identity in ('alpha', 'beta'):
            self.control[identity] = {'seconds': 30}
        self.write_control()
        real_popen = subprocess.Popen
        children = []

        def capture(command, *args, **kwargs):
            process = real_popen(command, *args, **kwargs)
            if len(command) > 1 and command[1] == str(self.root / 'scripts/build_modpack.py'):
                children.append(process)
            return process

        def interrupted(*args, **kwargs):
            deadline = time.monotonic() + 10
            while not all((self.root / 'build/events' / (identity + '.start')).exists() for identity in ('alpha', 'beta')):
                if time.monotonic() > deadline:
                    self.fail('Source fixture children did not start')
                time.sleep(.01)
            raise KeyboardInterrupt

        start = time.monotonic()
        with patch.object(parallel.subprocess, 'Popen', side_effect=capture), patch.object(parallel, 'wait', side_effect=interrupted):
            with self.assertRaises(KeyboardInterrupt):
                parallel.build_sources(self.root, self.run)
        self.assertLess(time.monotonic() - start, 10)
        self.assertEqual(len(children), 2)
        self.assertTrue(all(process.poll() is not None for process in children))
        self.assertFalse((self.root / 'build/events/gamma.start').exists())

    def test_cancellation_cannot_miss_a_child_while_popen_registers_it(self):
        processes = parallel.SourceProcesses()
        spawned, release = threading.Event(), threading.Event()
        real_popen = subprocess.Popen
        children = []
        command = [sys.executable, '-c', 'import signal,time; signal.signal(signal.SIGINT, lambda *_: exit(130)); time.sleep(30)']

        def delayed_popen(candidate, *args, **kwargs):
            process = real_popen(candidate, *args, **kwargs)
            if candidate == command:
                children.append(process)
                spawned.set()
                if not release.wait(10):
                    raise RuntimeError('Fixture registration barrier timed out')
            return process

        with patch.object(parallel.subprocess, 'Popen', side_effect=delayed_popen), ThreadPoolExecutor(max_workers=2) as pool:
            running = pool.submit(processes.run, command, self.root, dict(os.environ))
            self.assertTrue(spawned.wait(10))
            cancelling = pool.submit(processes.cancel)
            try:
                time.sleep(.05)
                self.assertFalse(cancelling.done())
            finally:
                release.set()
            cancelling.result(timeout=10)
            self.assertNotEqual(running.result(timeout=10), 0)
        self.assertTrue(all(process.poll() is not None for process in children))
        with self.assertRaisesRegex(builder.mods.ModError, 'launch cancelled'):
            processes.run(command, self.root, dict(os.environ))

    def assert_dispatch_signal_cleanup(self, requested_signal):
        for identity in ('alpha', 'beta'):
            self.control[identity] = {'nested': True}
        self.write_control()
        entry = self.root / 'scripts/dispatch.py'
        entry.write_text('import sys\nfrom pathlib import Path\nsys.path.insert(0, '
                         + repr(str(Path(__file__).resolve().parent)) + ')\nimport build_sources_parallel as p\n'
                         + 'p.ROOT=Path(' + repr(str(self.root)) + ')\nraise SystemExit(p.main())\n', encoding='utf-8')
        process = subprocess.Popen([sys.executable, str(entry), '--run', self.run, '--workers', '2'],
                                   cwd=self.root, env=dict(os.environ), stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, start_new_session=True)
        try:
            deadline = time.monotonic() + 10
            while not all((self.root / 'build/events' / (identity + '.wrapper')).exists() for identity in ('alpha', 'beta')):
                if process.poll() is not None or time.monotonic() > deadline:
                    self.fail('Source/wrapper fixture processes did not start')
                time.sleep(.01)
            process.send_signal(requested_signal)  # Only the dispatcher PID receives this signal.
            stdout, stderr = process.communicate(timeout=10)
            self.assertEqual(process.returncode, 130, (stdout, stderr))
            self.assertEqual({e['id'] for e in self.events()}, {'alpha', 'beta'})
            self.assertTrue(all(e['interrupted'] for e in self.events()))
            for path in (self.root / 'build/events').glob('*.wrapper'):
                with self.assertRaises(ProcessLookupError):
                    os.kill(int(path.read_text()), 0)
            self.assertFalse((self.root / 'build/events/gamma.start').exists())
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()

    @unittest.skipUnless(os.name == 'posix', 'POSIX dispatcher-only SIGINT contract')
    def test_sigint_to_dispatcher_pid_cleans_up_nested_wrapper_processes(self):
        self.assert_dispatch_signal_cleanup(signal.SIGINT)

    @unittest.skipUnless(os.name == 'posix', 'POSIX dispatcher-only SIGTERM contract')
    def test_sigterm_to_dispatcher_pid_cleans_up_nested_wrapper_processes(self):
        self.assert_dispatch_signal_cleanup(signal.SIGTERM)


if __name__ == '__main__':
    unittest.main()
