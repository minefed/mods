#!/usr/bin/env python3
"""Check upstream Fabric exclusivity and local-only Loom remapped resolution."""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import subprocess
import sys
import threading
import uuid
import zipfile

import build_modpack

ROOT = Path(__file__).resolve().parents[1]


def run_gradle(root: Path, fixture: Path, init_script: Path, task: str, *, offline: bool) -> None:
    java = build_modpack.java_home(root, 17) / 'bin' / ('java.exe' if sys.platform == 'win32' else 'java')
    command = [str(java), '-Xmx64m', '-Dfile.encoding=UTF-8', '-classpath',
               str(root / 'gradle/wrapper/gradle-wrapper.jar'), 'org.gradle.wrapper.GradleWrapperMain',
               '-p', str(fixture), '--no-daemon', '--max-workers=1', '--console=plain',
               '-Dorg.gradle.jvmargs=-Xmx128m -Dfile.encoding=UTF-8',
               '--init-script', str(init_script), task]
    if offline:
        command.append('--offline')
    log_path = fixture / 'gradle.log'
    with log_path.open('w', encoding='utf-8') as log:
        result = subprocess.run(command, cwd=root, stdout=log, stderr=subprocess.STDOUT)
    if result.returncode:
        print(log_path.read_text(encoding='utf-8', errors='replace'), file=sys.stderr)
        raise RuntimeError(f'Repository policy regression ({task}); log: {log_path}')


def verify_exclusive_fabric(root: Path, fixture: Path, init_script: Path) -> None:
    artifact = fixture / 'repository/net/fabricmc/minefed-policy-probe/1.0'
    artifact.mkdir(parents=True)
    (artifact / 'minefed-policy-probe-1.0.pom').write_text(
        '<project><modelVersion>4.0.0</modelVersion><groupId>net.fabricmc</groupId>'
        '<artifactId>minefed-policy-probe</artifactId><version>1.0</version></project>', encoding='utf-8')
    with zipfile.ZipFile(artifact / 'minefed-policy-probe-1.0.jar', 'w') as jar:
        jar.writestr('META-INF/MANIFEST.MF', 'Manifest-Version: 1.0\n')
    (fixture / 'settings.gradle').write_text("rootProject.name = 'minefed-repository-policy-check'\n", encoding='utf-8')
    # This is the policy used by CC-Tweaked's vanilla-extract plugin. The
    # dependency exists only in the local repository; no network is permitted.
    (fixture / 'build.gradle').write_text('''
repositories {
    exclusiveContent {
        forRepository { maven { name = 'Fabric'; url = uri('repository') } }
        filter {
            includeGroup('net.fabricmc')
            includeGroup('net.fabricmc.unpick')
        }
    }
}
configurations { probe }
dependencies { probe 'net.fabricmc:minefed-policy-probe:1.0' }
tasks.register('checkRepositoryPolicy') {
    doLast {
        assert configurations.probe.singleFile.name == 'minefed-policy-probe-1.0.jar'
        assert repositories.first().name == 'MinefedFabric'
        println('Upstream exclusive Fabric repository resolved successfully')
    }
}
''', encoding='utf-8')
    run_gradle(root, fixture, init_script, 'checkRepositoryPolicy', offline=True)
    print('Fabric repository policy verified offline', flush=True)


def verify_local_remapped(root: Path, fixture: Path, init_script: Path) -> None:
    # Use the exact synthetic group from the failed Forge Config API Port build.
    # A unique version prevents an earlier cached resolution from hiding a leak.
    group = 'loom_mappings_1_20_4_layered_hash_200895789_v2.net.fabricmc.fabric-api'
    # Keep the Maven path below Windows MAX_PATH despite the long group name.
    version = uuid.uuid4().hex[:16]
    module = 'probe'
    repository = fixture / 'repository'
    artifact = repository / group.replace('.', '/') / module / version
    artifact.mkdir(parents=True)
    (artifact / f'{module}-{version}.pom').write_text(
        '<project><modelVersion>4.0.0</modelVersion>'
        f'<groupId>{group}</groupId><artifactId>{module}</artifactId>'
        f'<version>{version}</version></project>', encoding='utf-8')
    jar_path = artifact / f'{module}-{version}.jar'
    with zipfile.ZipFile(jar_path, 'w') as jar:
        jar.writestr('META-INF/MANIFEST.MF', 'Manifest-Version: 1.0\n')
        jar.writestr('probe-version.txt', version)
    (fixture / 'settings.gradle').write_text(
        "rootProject.name = 'minefed-remapped-repository-check'\n", encoding='utf-8')

    requests = []

    class FailureHandler(BaseHTTPRequestHandler):
        def reject(self):
            requests.append({'method': self.command, 'path': self.path})
            self.send_response(500)
            self.send_header('Content-Length', '0')
            self.end_headers()

        do_GET = reject
        do_HEAD = reject

        def log_message(self, format, *args):
            pass

    server = ThreadingHTTPServer(('127.0.0.1', 0), FailureHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        # This deliberately precedes the file repository, matching the failing
        # Sponge lookup. Only loopback HTTP is eligible for this coordinate:
        # MinefedFabric's existing net.fabricmc filter does not match its group.
        (fixture / 'build.gradle').write_text('''
repositories {
    maven {
        name = 'FailingRemoteBeforeLoom'
        url = uri('http://127.0.0.1:PORT/maven/')
        allowInsecureProtocol = true
        content { includeGroup('GROUP') }
    }
    maven {
        name = 'LoomLocalRemappedMods'
        url = uri('repository')
    }
}
configurations { remappedProbe }
dependencies { remappedProbe 'GROUP:MODULE:VERSION' }
tasks.register('checkRemappedRepositoryPolicy') {
    doLast {
        assert configurations.remappedProbe.singleFile.canonicalFile == file('ARTIFACT').canonicalFile
        println('Loom remapped artifact resolved from its local Maven repository')
    }
}
'''.replace('PORT', str(server.server_port)).replace('GROUP', group)
            .replace('MODULE', module).replace('VERSION', version)
            .replace('ARTIFACT', jar_path.relative_to(fixture).as_posix()), encoding='utf-8')
        # Do not use --offline: it would silently skip the failing HTTP repository
        # and make the uncorrected init script pass this regression check.
        run_gradle(root, fixture, init_script, 'checkRemappedRepositoryPolicy', offline=False)
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
        (fixture / 'http-requests.json').write_text(
            json.dumps(requests, indent=2) + '\n', encoding='utf-8')
    if requests:
        raise RuntimeError(f'Loom remapped coordinates leaked to HTTP; log: {fixture / "http-requests.json"}')
    print('Loom remapped repository policy verified with zero HTTP requests', flush=True)


def verify(root: Path, init_script: Path | None = None) -> None:
    # Keep diagnostics in isolated build directories without modifying any mod.
    fixture = root / 'build/repository-policy-checks' / uuid.uuid4().hex[:12]
    init_script = init_script or root / 'scripts/source-repositories.gradle'
    verify_exclusive_fabric(root, fixture / 'exclusive-fabric', init_script)
    verify_local_remapped(root, fixture / 'local-remapped', init_script)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--init-script', type=Path,
                        help='Alternate init script for comparing a regression with the corrected policy')
    args = parser.parse_args()
    try:
        verify(ROOT, args.init_script.resolve() if args.init_script else None)
    except (OSError, RuntimeError) as error:
        print(error, file=sys.stderr)
        sys.exit(1)
