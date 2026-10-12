"""Validate a local baked-model export before giving it to BlueMap."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import re
import struct

IDENTIFIER = re.compile(r'[a-z0-9_.-]+:[a-z0-9_./-]+')
DIRECTIONS = {'down', 'up', 'north', 'south', 'west', 'east'}


def resource(root: Path, identity: str, family: str, suffix: str) -> Path:
    if not isinstance(identity, str) or not IDENTIFIER.fullmatch(identity) or '..' in identity:
        raise ValueError(f'Invalid resource identifier: {identity!r}')
    namespace, path = identity.split(':', 1)
    return root / 'assets' / namespace / family / (path + suffix)


def read(path: Path):
    return json.loads(path.read_text(encoding='utf-8'))


def vectors(value, width: int, label: str):
    if not isinstance(value, list) or len(value) != 4:
        raise ValueError(f'{label}: expected four vertices')
    for vector in value:
        if (not isinstance(vector, list) or len(vector) != width or
                any(type(x) not in (float, int) or not math.isfinite(x) for x in vector)):
            raise ValueError(f'{label}: invalid vertex')


def texture_animation(path: Path):
    """Return the vertical frame count, or None for a static texture."""
    image = path.read_bytes()
    if len(image) < 24 or image[:8] != b'\x89PNG\r\n\x1a\n' or image[12:16] != b'IHDR':
        raise ValueError('Missing/invalid exported PNG: ' + str(path))
    width, height = struct.unpack('>II', image[16:24])
    if width == 0 or height == 0:
        raise ValueError('Empty exported PNG')
    metadata_path = path.with_name(path.name + '.mcmeta')
    if not metadata_path.exists():
        return None
    if height % width != 0:
        raise ValueError('Animated texture must be a vertical strip of square frames')
    metadata = read(metadata_path)
    animation = metadata.get('animation') if isinstance(metadata, dict) else None
    if not isinstance(animation, dict):
        raise ValueError('Missing animation metadata')
    for dimension in ('width', 'height'):
        if dimension in animation and animation[dimension] != width:
            raise ValueError('Animation frame dimensions differ from its square strip')
    frame_count = height // width
    default_time = animation.get('frametime', 1)
    if type(default_time) is not int or default_time <= 0:
        raise ValueError('Invalid animation frame time')
    if type(animation.get('interpolate', False)) is not bool:
        raise ValueError('Invalid animation interpolation flag')
    frames = animation.get('frames')
    if not isinstance(frames, list) or not frames:
        raise ValueError('Exported animation must list its playback frames')
    for frame in frames:
        if type(frame) is int:
            index, duration = frame, default_time
        elif isinstance(frame, dict):
            index, duration = frame.get('index'), frame.get('time', default_time)
        else:
            raise ValueError('Invalid animation frame')
        if type(index) is not int or not 0 <= index < frame_count:
            raise ValueError('Animation frame index is outside the texture strip')
        if type(duration) is not int or duration <= 0:
            raise ValueError('Invalid animation frame duration')
    return frame_count


def multipart_variants(block: dict, blockstate: dict):
    """Check every Cartesian state at once using exact integer truth-table bitsets."""
    parts = blockstate.get('multipart')
    domain = block.get('propertyValues')
    counts = block.get('matchedStateCounts')
    if (not isinstance(parts, list) or not parts or type(block.get('components')) is not int or
            block['components'] != len(parts)):
        raise ValueError('Invalid multipart component count')
    if not isinstance(domain, dict) or not isinstance(counts, list) or len(counts) != len(parts):
        raise ValueError('Multipart is missing its state-domain verification metadata')
    combinations = 1
    for key, values in domain.items():
        if (not isinstance(key, str) or not key or key in {'AND', 'OR'} or
                not isinstance(values, list) or not values or
                any(not isinstance(value, str) or not value or '|' in value for value in values) or
                len(set(values)) != len(values)):
            raise ValueError('Invalid multipart property domain')
        combinations *= len(values)
    if combinations != block['states']:
        raise ValueError('Multipart state-domain coverage differs from the report')
    all_states = (1 << combinations) - 1
    masks = {}
    stride = 1
    for key, values in reversed(list(domain.items())):
        period = stride * len(values)
        repeated = all_states // ((1 << period) - 1)
        masks[key] = {value: repeated * ((1 << stride) - 1) << (index * stride)
                      for index, value in enumerate(values)}
        stride = period

    def evaluate(condition):
        if not isinstance(condition, dict):
            raise ValueError('Multipart condition must be an object')
        result = all_states
        for key, value in condition.items():
            if key in {'AND', 'OR'}:
                if not isinstance(value, list):
                    raise ValueError('Multipart AND/OR must contain condition arrays')
                selected = all_states if key == 'AND' else 0
                for child in value:
                    if key == 'AND':
                        selected &= evaluate(child)
                    else:
                        selected |= evaluate(child)
            else:
                if key not in masks or type(value) not in (str, bool):
                    raise ValueError('Unknown multipart property or invalid selector')
                if type(value) is bool:
                    value = str(value).lower()
                selected = 0
                for name in value.split('|'):
                    if name not in masks[key]:
                        raise ValueError('Unknown multipart property value')
                    selected |= masks[key][name]
            result &= selected
        return result

    covered = 0
    variants = []
    for part, expected_count in zip(parts, counts):
        if not isinstance(part, dict) or not isinstance(part.get('apply'), dict):
            raise ValueError('Multipart apply must contain one captured model')
        selected = evaluate(part.get('when', {}))
        if type(expected_count) is not int or expected_count != selected.bit_count():
            raise ValueError('Multipart condition coverage differs from the report')
        covered |= selected
        variants.append(part['apply'])
    empty = block.get('emptyStates')
    if type(empty) is not int or empty != combinations - covered.bit_count():
        raise ValueError('Multipart empty-state coverage differs from the report')
    return variants


def verify(root: Path, *, require_all: bool = False) -> dict:
    report = read(root / 'export-report.json')
    if report.get('schemaVersion') != 1 or report.get('minecraft') != '1.20.4':
        raise ValueError('Unsupported export version')
    if report.get('complete') is not True or report.get('distribution') != 'local-only':
        raise ValueError('Export is unfinished or lacks its local-only restriction')
    if read(root / 'pack.mcmeta').get('pack', {}).get('pack_format') != 22:
        raise ValueError('Export must use Minecraft 1.20.4 pack format 22')
    blocks, states, contextual = 0, 0, 0
    model_files, texture_files = set(), set()
    animated_files = {}
    rejected = []
    identities = set()
    for block in report['blocks']:
        identity = block['block']
        if identity in identities:
            raise ValueError('Duplicate block in export report: ' + identity)
        identities.add(identity)
        path = resource(root, identity, 'blockstates', '.json')
        if not block['exported']:
            rejected.append(identity)
            if path.exists():
                raise ValueError('Rejected block has a partial override: ' + identity)
            continue
        if block['failures']:
            raise ValueError('Exported block has failed states: ' + identity)
        if type(block['states']) is not int or block['states'] <= 0:
            raise ValueError('Invalid block state count')
        blockstate = read(path)
        if 'variants' in blockstate and 'multipart' in blockstate:
            raise ValueError('Ambiguous blockstate export format')
        if block.get('format') == 'multipart':
            variants = multipart_variants(block, blockstate)
        else:
            variants_by_state = blockstate.get('variants')
            if (not isinstance(variants_by_state, dict) or
                    len(variants_by_state) != block['states'] or not variants_by_state):
                raise ValueError('Blockstate coverage differs from the report: ' + identity)
            variants = variants_by_state.values()
        blocks += 1
        states += block['states']
        contextual += block.get('isolatedContextStates', 0)
        for variant in variants:
            if not isinstance(variant, dict):
                raise ValueError('Expected one captured variant model')
            if variant.get('x', 0) != 0 or variant.get('y', 0) != 0 or variant.get('uvlock', False):
                raise ValueError('Exported geometry is already rotated')
            model_path = resource(root, variant['model'], 'models', '.json')
            if model_path in model_files:
                continue
            model_files.add(model_path)
            model = read(model_path)
            if model.get('minefed_export_context') and report.get('contextualMode') != 'isolated':
                raise ValueError('Unacknowledged context-dependent snapshot')
            quads = model.get('bluemap_quads')
            if (not isinstance(quads, list) or
                    not quads and model.get('minefed_export_empty') is not True):
                raise ValueError('Missing final baked quads: ' + str(model_path))
            for quad in quads:
                vectors(quad.get('positions'), 3, 'positions')
                vectors(quad.get('uv'), 2, 'uv')
                if quad.get('direction') not in DIRECTIONS or quad.get('cullface') not in DIRECTIONS | {None}:
                    raise ValueError('Invalid face direction')
                if type(quad.get('tintindex')) is not int or quad['tintindex'] < -1:
                    raise ValueError('Invalid tint index')
                if type(quad.get('shade')) is not bool or not re.fullmatch(r'#[0-9a-fA-F]{6}', quad.get('color', '')):
                    raise ValueError('Invalid quad shading/color')
                texture = quad['texture']
                if texture.startswith('#'):
                    texture = model['textures'][texture[1:]]
                texture_path = resource(root, texture, 'textures', '.png')
                if texture_path in texture_files:
                    continue
                texture_files.add(texture_path)
                frame_count = texture_animation(texture_path)
                if frame_count is not None:
                    animated_files[texture_path] = frame_count
    declared_animations = report.get('animatedTextures', {})
    if not isinstance(declared_animations, dict):
        raise ValueError('Invalid animated texture manifest')
    declared_paths = set()
    for original, animation in declared_animations.items():
        exported_texture = report.get('textures', {}).get(original)
        path = resource(root, exported_texture, 'textures', '.png')
        actual_frames = animated_files.get(path)
        if actual_frames is None:
            actual_frames = texture_animation(path)
        if (not isinstance(animation, dict) or type(animation.get('frames')) is not int or
                animation['frames'] != actual_frames):
            raise ValueError('Animated texture frame count differs from the report')
        declared_paths.add(path)
    if animated_files.keys() - declared_paths:
        raise ValueError('Animated texture is missing from the export manifest')
    if blocks == 0 or blocks != report['exportedBlocks'] or states != report['exportedStates']:
        raise ValueError('Export totals differ from blockstate coverage')
    if require_all and rejected:
        raise ValueError('Unsupported blocks remain: ' + ', '.join(rejected))
    return {'exportedBlocks': blocks, 'exportedStates': states, 'isolatedContextStates': contextual,
            'models': len(model_files), 'textures': len(texture_files), 'rejectedBlocks': rejected,
            'animatedTextures': len(declared_animations), 'distribution': 'local-only'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    parser.add_argument('--require-all', action='store_true')
    args = parser.parse_args()
    print(json.dumps(verify(args.output, require_all=args.require_all), indent=2))
