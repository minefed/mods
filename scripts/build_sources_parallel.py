#!/usr/bin/env python3
"""Run audited source CLIs in two or three slots with separate, disposable Gradle homes."""

import argparse
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time

import build_modpack as builder
import mods

ROOT = Path(__file__).resolve().parents[1]
# Each worker runs one Gradle JVM (up to 2 GiB heap) with its own caches; three
# fit the 4-core, 16 GB hosted runner. More would compete for memory and disk.
WORKER_COUNTS = (2, 3)


def require_plain_gradle_home(root):
    """Keep each worker's build-tool fingerprint equal to the assembler's."""
    home = builder.gradle_user_home(root)
    inputs = [home / 'gradle.properties', home / 'init.gradle', home / 'init.gradle.kts']
    if (home / 'init.d').is_dir():
        inputs.extend((home / 'init.d').glob('*.gradle*'))
    found = [str(path) for path in inputs if path.exists() or path.is_symlink()]
    if found:
        raise mods.ModError('Parallel source builds require a Gradle home without custom '
                            'properties/init scripts. Use -PsourceBuildWorkers=1 to preserve them: '
                            + ', '.join(sorted(found)))
    return home


def source_recipes(root, plan):
    recipes = [recipe for recipe in plan['entries'] if recipe['mode'] == 'source']
    if not recipes:
        raise mods.ModError('Parallel source build has no source recipes')
    paths = []
    for recipe in recipes:
        path = mods.safe_path(root, recipe['sourcePath'])
        for previous in paths:
            if path == previous or path.is_relative_to(previous) or previous.is_relative_to(path):
                raise mods.ModError('Parallel source directories overlap: ' + str(path) + ' and '
                                    + str(previous) + '; use -PsourceBuildWorkers=1')
        paths.append(path)
    return recipes


def previous_build_seconds(root):
    """Read compile durations from earlier source cache receipts; only used for ordering."""
    durations = {}
    for record in (root / 'build/source-cache').glob('*/result.json'):
        try:
            value = json.loads(record.read_text(encoding='utf-8'))
            identity, seconds = value['modId'], value['buildSeconds']
        except (OSError, ValueError, TypeError, KeyError):
            continue
        if (isinstance(identity, str) and type(seconds) in (int, float)
                and math.isfinite(seconds) and seconds >= 0):
            durations[identity] = max(seconds, durations.get(identity, 0))
    return durations


def longest_first(recipes, durations):
    """Start unmeasured sources, then the slowest, so one long build does not end the run alone."""
    order = {recipe['modId']: index for index, recipe in enumerate(recipes)}
    return sorted(recipes, key=lambda recipe: (recipe['modId'] in durations,
                                               -durations.get(recipe['modId'], 0),
                                               order[recipe['modId']]))


def worker_homes(root, work, workers, default_home):
    base = mods.safe_path(root, (work / 'gradle-homes').relative_to(root).as_posix())
    if default_home == base or default_home.is_relative_to(base):
        raise mods.ModError('Default GRADLE_USER_HOME overlaps this run\'s worker homes')
    # Never reuse, clean, or link an existing cache: these directories belong to this run.
    try:
        base.mkdir()
    except FileExistsError as exc:
        raise mods.ModError('Worker Gradle homes are not pristine; start a new Gradle invocation: '
                            + str(base)) from exc
    homes = []
    for slot in range(workers):
        home = base / ('worker-' + str(slot))
        home.mkdir()
        homes.append(home)
    return homes


class SourceProcesses:
    """Own source CLI processes until they exit, including cancellation races."""

    def __init__(self):
        self.lock = threading.Lock()
        self.active = set()
        self.cancelled = False

    def run(self, command, root, environment):
        options = ({'creationflags': subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == 'nt'
                   else {'start_new_session': True})
        # Cancellation cannot observe a started process before it is registered.
        with self.lock:
            if self.cancelled:
                raise mods.ModError('Source launch cancelled')
            process = subprocess.Popen(command, cwd=root, env=environment,
                                       stdin=subprocess.DEVNULL, **options)
            self.active.add(process)
        try:
            return process.wait()
        finally:
            with self.lock:
                self.active.discard(process)

    def cancel(self):
        with self.lock:
            self.cancelled = True
            processes = list(self.active)
        for process in processes:
            if process.poll() is not None:
                continue
            if os.name == 'nt':
                # The existing helper kills only this owned PID and descendants.
                builder.stop_process_tree(process)
            else:
                # Interrupt the trusted source CLI so its BaseException cleanup
                # kills the wrapper's separate process group before releasing locks.
                try:
                    process.send_signal(signal.SIGINT)
                except ProcessLookupError:
                    pass


def run_source(root, run, recipe, home, environment, processes):
    command = [sys.executable, str(root / 'scripts/build_modpack.py'),
               'source', '--run', run, '--id', recipe['modId']]
    child_environment = {**environment, 'GRADLE_USER_HOME': str(home)}
    return processes.run(command, root, child_environment)


def print_timings(work, timings):
    """Log each finished source's wall time so slow CI builds can be compared."""
    if not timings:
        return
    print('Source wall times (cache: hit = reused verified build):', flush=True)
    for identity, seconds in sorted(timings.items(), key=lambda item: -item[1]):
        try:
            receipt = json.loads((work / 'sources' / identity / 'result.json').read_text(encoding='utf-8'))
            cache = 'hit' if receipt.get('cacheHit') else 'miss'
        except (OSError, ValueError):
            cache = 'none'
        print(f'  {seconds:7.1f}s  {cache:4}  {identity}', flush=True)


def build_sources(root, run, workers=2):
    if type(workers) is not int or workers not in WORKER_COUNTS:
        raise mods.ModError('This optional dispatcher supports two or three workers; '
                            'use -PsourceBuildWorkers=1 for the default serial build')
    root = Path(root).resolve()
    manifest, plan = builder.load_plan(root)
    work = builder.check_run(root, run, manifest, plan)
    recipes = source_recipes(root, plan)
    default_home = require_plain_gradle_home(root)
    homes = worker_homes(root, work, workers, default_home)
    environment = dict(os.environ)
    # Earlier receipts only change the start order; every source still runs.
    pending = iter(longest_first(recipes, previous_build_seconds(root)))
    successes, failures = [], []
    timings = {}
    active = {}
    processes = SourceProcesses()

    def launch(pool, slot):
        recipe = next(pending, None)
        if recipe is None:
            return
        print(f"Source worker {slot}: {recipe['modId']} (Gradle home {homes[slot]})", flush=True)
        active[pool.submit(run_source, root, run, recipe, homes[slot], environment, processes)] = (
            slot, recipe['modId'], time.monotonic())

    # At most one subprocess uses each home. On failure, drain running sources
    # without submitting more work; their existing CLI retains locks/receipts.
    with ThreadPoolExecutor(max_workers=workers) as pool:
        try:
            for slot in range(workers):
                launch(pool, slot)
            while active:
                wait(active, return_when=FIRST_COMPLETED)
                finished = [future for future in active if future.done()]
                free_slots = []
                for future in finished:
                    slot, identity, started = active.pop(future)
                    timings[identity] = time.monotonic() - started
                    free_slots.append(slot)
                    try:
                        code = future.result()
                    except Exception as exc:
                        failures.append(f'{identity}: {exc}')
                    else:
                        if code:
                            failures.append(f'{identity}: source CLI exited with status {code}')
                        else:
                            successes.append(identity)
                if not failures:
                    for slot in sorted(free_slots):
                        launch(pool, slot)
        except BaseException:
            # Cancel before ThreadPoolExecutor.__exit__ waits for active futures.
            processes.cancel()
            raise
    print_timings(work, timings)
    if failures:
        raise mods.ModError('Parallel source build failed; running sources were allowed to finish '
                            'and no pack was assembled. ' + '; '.join(failures))
    if len(successes) != len(recipes) or len(set(successes)) != len(recipes):
        raise mods.ModError('Parallel source completion does not cover every recipe exactly once')
    current_manifest, current_plan = builder.load_plan(root)
    builder.check_run(root, run, current_manifest, current_plan)
    require_plain_gradle_home(root)
    print(f'Completed {len(successes)} source CLIs; the existing assembler must verify every receipt.', flush=True)
    return successes


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', required=True)
    parser.add_argument('--workers', type=int, choices=WORKER_COUNTS, default=2)
    args = parser.parse_args(argv)
    def interrupted(signum, frame):
        raise KeyboardInterrupt

    previous_term = signal.signal(signal.SIGTERM, interrupted)
    try:
        build_sources(ROOT, args.run, args.workers)
    except KeyboardInterrupt:
        print('ERROR: Parallel source build interrupted; owned child processes were stopped.', file=sys.stderr)
        return 130
    except (mods.ModError, OSError, ValueError, subprocess.CalledProcessError) as exc:
        print('ERROR: ' + str(exc), file=sys.stderr)
        return 1
    finally:
        signal.signal(signal.SIGTERM, previous_term)
    return 0


if __name__ == '__main__':
    sys.exit(main())
