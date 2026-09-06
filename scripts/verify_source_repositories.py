#!/usr/bin/env python3
"""Check that canonical Fabric routing honors an upstream exclusive repository."""
from pathlib import Path
import subprocess
import sys
import uuid
import zipfile

import build_modpack

ROOT = Path(__file__).resolve().parents[1]


def verify(root: Path) -> None:
    # Keep diagnostics in an isolated build directory without modifying any mod.
    fixture = root / 'build/repository-policy-checks' / uuid.uuid4().hex
    fixture.mkdir(parents=True)
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
    java = build_modpack.java_home(root, 17) / 'bin' / ('java.exe' if sys.platform == 'win32' else 'java')
    command = [str(java), '-Xmx64m', '-Dfile.encoding=UTF-8', '-classpath',
               str(root / 'gradle/wrapper/gradle-wrapper.jar'), 'org.gradle.wrapper.GradleWrapperMain',
               '-p', str(fixture), '--offline', '--no-daemon', '--max-workers=1', '--console=plain',
               '-Dorg.gradle.jvmargs=-Xmx128m -Dfile.encoding=UTF-8',
               '--init-script', str(root / 'scripts/source-repositories.gradle'), 'checkRepositoryPolicy']
    log_path = fixture / 'gradle.log'
    with log_path.open('w', encoding='utf-8') as log:
        result = subprocess.run(command, cwd=root, stdout=log, stderr=subprocess.STDOUT)
    if result.returncode:
        print(log_path.read_text(encoding='utf-8', errors='replace'), file=sys.stderr)
        raise RuntimeError(f'Fabric repository policy regression; log: {log_path}')
    print('Fabric repository policy verified offline', flush=True)


if __name__ == '__main__':
    try:
        verify(ROOT)
    except (OSError, RuntimeError) as error:
        print(error, file=sys.stderr)
        sys.exit(1)
