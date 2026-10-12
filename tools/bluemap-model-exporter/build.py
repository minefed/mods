"""Compile the offline exporter against the selected disposable client's libraries."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import tempfile
import zipfile


def build(jdk: Path, classpath_file: Path, fabric_api: Path, indium: Path,
          sodium: Path, output: Path) -> None:
    source = Path(__file__).resolve().parent
    classpath = classpath_file.read_text(encoding='utf-8-sig').strip()
    if not classpath:
        raise ValueError('The intermediary Minecraft / launcher library classpath is empty')
    for path in classpath.split(os.pathsep):
        if not Path(path).is_file():
            raise FileNotFoundError(path)
    for path in (fabric_api, indium, sodium):
        if not path.is_file():
            raise FileNotFoundError(path)
    suffix = '.exe' if os.name == 'nt' else ''
    javac, jar = (jdk / 'bin' / (name + suffix) for name in ('javac', 'jar'))
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='minefed-bluemap-exporter-') as scratch:
        root = Path(scratch)
        with zipfile.ZipFile(fabric_api) as archive:
            entries = [name for name in archive.namelist()
                       if name.startswith('META-INF/jars/fabric-renderer-api-v1-') and name.endswith('.jar')]
            if len(entries) != 1:
                raise ValueError('Expected one nested Fabric renderer API JAR')
            renderer = root / 'fabric-renderer-api.jar'
            renderer.write_bytes(archive.read(entries[0]))
        compile_classpath = os.pathsep.join((classpath, str(renderer), str(indium.resolve()), str(sodium.resolve())))
        classes = root / 'classes'
        classes.mkdir()
        sources = sorted((source / 'src').rglob('*.java'))
        subprocess.run([str(javac), '--release', '17', '-proc:none', '-encoding', 'UTF-8',
                        '-cp', compile_classpath, '-d', str(classes), *map(str, sources)], check=True)
        subprocess.run([str(jar), '--create', '--file', str(output), '-C', str(classes), '.',
                        '-C', str(source), 'fabric.mod.json', '-C', str(source), 'LICENSE'], check=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for argument in ('jdk', 'classpath-file', 'fabric-api', 'indium', 'sodium', 'output'):
        parser.add_argument('--' + argument, type=Path, required=True)
    args = parser.parse_args()
    build(args.jdk, args.classpath_file, args.fabric_api, args.indium, args.sodium, args.output)
