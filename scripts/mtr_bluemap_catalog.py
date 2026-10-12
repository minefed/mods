#!/usr/bin/env python3
"""Extract every registered MTR vehicle name and dimensions without copying art.

Reads the same two registrations as MTR 4 CustomResourceLoader, including the
temporary pending-migration registration. Modern registrations are supported;
unconverted legacy custom_trains fail explicitly rather than disappear from the
map. Colors come from the live MTR route, not from a texture approximation.
Uses Python's standard library only. Input can be the reviewed release ZIP or
its resource_pack directory. No Minecraft client or running server is required.
"""
from __future__ import annotations

import argparse
from contextlib import ExitStack
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import re
import zipfile

import mods

REGISTRATIONS = ('assets/mtr/mtr_custom_resources.json',
                 'assets/mtr/mtr_custom_resources_pending_migration.json')
OUTPUT_PATH = 'config/mtr/bluemap-vehicles.json'


class ResourceReader:
    def __init__(self, source: Path, stack: ExitStack):
        self.source = source.resolve()
        self.archive = None if source.is_dir() else stack.enter_context(zipfile.ZipFile(source))
        self.hashes = {}

    def exists(self, path):
        return path in self.archive.namelist() if self.archive else (self.source / path).is_file()

    def read(self, path):
        if (not isinstance(path, str) or '\\' in path or ':' in path or
                PurePosixPath(path).is_absolute() or any(p in ('', '.', '..') for p in path.split('/'))):
            raise mods.ModError('Unsafe MTR resource path: ' + str(path))
        try:
            if self.archive:
                infos = [i for i in self.archive.infolist() if i.filename == path]
                if len(infos) != 1 or (infos[0].external_attr >> 16) & 0o170000 == 0o120000:
                    raise mods.ModError('Missing, duplicate or linked MTR resource: ' + path)
                if infos[0].file_size > 64 * 1024 * 1024:
                    raise mods.ModError('Oversized MTR resource: ' + path)
                data = self.archive.read(infos[0])
            else:
                target = mods.safe_path(self.source, path)
                if target.stat().st_size > 64 * 1024 * 1024:
                    raise mods.ModError('Oversized MTR resource: ' + path)
                data = target.read_bytes()
        except (OSError, KeyError, zipfile.BadZipFile) as exc:
            raise mods.ModError('Missing or unreadable MTR resource: ' + path) from exc
        self.hashes[path] = hashlib.sha256(data).hexdigest()
        return data

    def json(self, path):
        try:
            return json.loads(self.read(path).decode('utf-8-sig'))
        except (UnicodeError, ValueError) as exc:
            raise mods.ModError('Invalid MTR resource JSON: ' + path) from exc

    @staticmethod
    def asset(identifier):
        if not isinstance(identifier, str) or not re.fullmatch(r'[a-z0-9_.-]+:[a-z0-9_./-]+', identifier):
            raise mods.ModError('Invalid MTR resource identifier: ' + str(identifier))
        namespace, path = identifier.split(':', 1)
        return f'assets/{namespace}/{path}'


def build_catalog(source: Path, *, require_vehicles=False):
    with ExitStack() as stack:
        reader = ResourceReader(source, stack)
        vehicles, registrations, checked = {}, [], set()
        for registration in REGISTRATIONS:
            if not reader.exists(registration):
                continue
            registrations.append(registration)
            document = reader.json(registration)
            if not isinstance(document, dict):
                raise mods.ModError('MTR registration must be an object: ' + registration)
            if 'custom_trains' in document or 'custom_signs' in document:
                if document.get('custom_trains'):
                    raise mods.ModError('Legacy custom_trains require migration before BlueMap catalog generation: ' + registration)
                # CustomResourcesConverter takes the legacy branch even if the
                # same document also contains a modern vehicles array.
                continue
            entries = document.get('vehicles', [])
            if not isinstance(entries, list):
                raise mods.ModError('MTR vehicles registration must be an array: ' + registration)
            for vehicle in entries:
                if not isinstance(vehicle, dict):
                    raise mods.ModError('MTR vehicle registration must be an object: ' + registration)
                identity = vehicle.get('id')
                if not isinstance(identity, str) or not identity or identity in vehicles:
                    raise mods.ModError('Missing or duplicate MTR vehicle ID: ' + str(identity))
                for field in ('length', 'width'):
                    value = vehicle.get(field)
                    if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
                        raise mods.ModError(f'Invalid {field} for MTR vehicle {identity}')
                if not isinstance(vehicle.get('name'), str) or not vehicle['name']:
                    raise mods.ModError('Missing MTR vehicle name: ' + identity)
                if not vehicle.get('models'):
                    raise mods.ModError('Missing MTR vehicle body models: ' + identity)
                for model_type in ('models', 'bogie1Models', 'bogie2Models'):
                    definitions = vehicle.get(model_type, [])
                    if not isinstance(definitions, list):
                        raise mods.ModError('MTR vehicle models must be an array: ' + identity)
                    for definition in definitions:
                        if not isinstance(definition, dict):
                            raise mods.ModError('MTR vehicle model must be an object: ' + identity)
                        paths = {field: reader.asset(definition.get(field)) for field in
                                 ('modelResource', 'textureResource', 'modelPropertiesResource', 'positionDefinitionsResource')}
                        for field, path in paths.items():
                            if path in checked:
                                continue
                            if field == 'textureResource':
                                reader.read(path)
                            else:
                                reader.json(path)
                            checked.add(path)
                vehicles[identity] = {field: vehicle[field] for field in ('name', 'length', 'width')}
        if require_vehicles and not vehicles:
            raise mods.ModError('Resource pack contains no supported registered MTR vehicles')
        return {'schema': 1, 'vehicles': dict(sorted(vehicles.items())),
                'source': {'registrations': registrations, 'colors': 'live-mtr-route',
                           'resourceSha256': dict(sorted(reader.hashes.items()))}}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('resource_pack', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        catalog = build_catalog(args.resource_pack, require_vehicles=True)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        print(f'Wrote {len(catalog["vehicles"])} vehicle models to {args.output}')
    except (mods.ModError, OSError, KeyError, TypeError, ValueError, zipfile.BadZipFile) as exc:
        raise SystemExit(str(exc)) from exc


if __name__ == '__main__':
    main()
