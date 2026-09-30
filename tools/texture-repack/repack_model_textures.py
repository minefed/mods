#!/usr/bin/env python3
"""Repack block-model textures so that only the texels used by model faces remain.

For every face that uses one of the given textures, the pixel rectangle covered by its UV
(plus a one-pixel margin) is copied unchanged into a new, smaller image, and the face UV is
translated to the new position. Overlapping rectangles are merged first, so shared regions are
copied once. The scale between UV units and texels stays the same, so every face samples the
same texels as before (nearest filtering). The output size is a multiple of 16 on both axes so
that the texture does not lower the block atlas mipmap level.

Usage: repack_model_textures.py <assets/<namespace> directory> <namespace> <texture> [<texture> ...]
       add --check to only verify the current files against a previous run's originals (see --originals)
"""
import argparse
import json
import math
import re
import os
import sys

from PIL import Image

MARGIN = 1


def faces_using(models_dir, namespace, texture):
    target = f'{namespace}:block/{texture}'
    for root, _, files in os.walk(models_dir):
        for file in sorted(files):
            if not file.endswith('.json'):
                continue
            path = os.path.join(root, file)
            with open(path, encoding='utf-8') as stream:
                model = json.load(stream)
            textures = model.get('textures') or {}
            for element in model.get('elements', []):
                for face in element.get('faces', {}).values():
                    reference = face.get('texture', '')
                    resolved = textures.get(reference[1:], reference) if reference.startswith('#') else reference
                    if resolved == target:
                        yield path, face


def pixel_rect(uv, width, height):
    u1, v1, u2, v2 = uv
    x1 = math.floor(min(u1, u2) * width / 16) - MARGIN
    x2 = math.ceil(max(u1, u2) * width / 16) + MARGIN
    y1 = math.floor(min(v1, v2) * height / 16) - MARGIN
    y2 = math.ceil(max(v1, v2) * height / 16) + MARGIN
    return [max(0, x1), max(0, y1), min(width, max(x2, x1 + 1)), min(height, max(y2, y1 + 1))]


def merge(rects):
    rects = [list(rect) for rect in rects]
    merged = True
    while merged:
        merged = False
        result = []
        while rects:
            current = rects.pop()
            changed = True
            while changed:
                changed = False
                for other in rects[:]:
                    if current[0] < other[2] and other[0] < current[2] and current[1] < other[3] and other[1] < current[3]:
                        current = [min(current[0], other[0]), min(current[1], other[1]), max(current[2], other[2]), max(current[3], other[3])]
                        rects.remove(other)
                        changed = merged = True
            result.append(current)
        rects = result
    return rects


def pack(rects, width_limit):
    """Shelf packing, tallest first. Returns destination positions and the used size."""
    order = sorted(range(len(rects)), key=lambda i: (-(rects[i][3] - rects[i][1]), -(rects[i][2] - rects[i][0])))
    positions = [None] * len(rects)
    x = y = shelf_height = used_width = 0
    for index in order:
        w = rects[index][2] - rects[index][0]
        h = rects[index][3] - rects[index][1]
        if x + w > width_limit:
            x = 0
            y += shelf_height
            shelf_height = 0
        positions[index] = (x, y)
        x += w
        used_width = max(used_width, x)
        shelf_height = max(shelf_height, h)
    return positions, used_width, y + shelf_height


def round16(value):
    return max(16, (value + 15) // 16 * 16)


def repack(assets_dir, namespace, texture):
    texture_path = os.path.join(assets_dir, 'textures', 'block', texture + '.png')
    image = Image.open(texture_path).convert('RGBA')
    width, height = image.size
    faces = list(faces_using(os.path.join(assets_dir, 'models'), namespace, texture))
    if not faces:
        raise SystemExit(f'{texture}: no model faces use this texture')
    rects = merge(pixel_rect(face['uv'], width, height) for _, face in faces)
    area = sum((r[2] - r[0]) * (r[3] - r[1]) for r in rects)
    best = None
    for width_limit in range(max(max(r[2] - r[0] for r in rects), 16), width + 1, 16):
        positions, used_width, used_height = pack(rects, width_limit)
        size = (round16(used_width), round16(used_height))
        if best is None or size[0] * size[1] < best[0][0] * best[0][1] or (size[0] * size[1] == best[0][0] * best[0][1] and abs(size[0] - size[1]) < abs(best[0][0] - best[0][1])):
            best = (size, positions)
    (new_width, new_height), positions = best
    if new_width * new_height >= width * height:
        print(f'{texture}: {width}x{height} kept, repacking would not shrink it')
        return None
    new_image = Image.new('RGBA', (new_width, new_height), (0, 0, 0, 0))
    for rect, (x, y) in zip(rects, positions):
        new_image.paste(image.crop(tuple(rect)), (x, y))

    def remap(face):
        u1, v1, u2, v2 = face['uv']
        px = pixel_rect(face['uv'], width, height)
        for rect, (x, y) in zip(rects, positions):
            if rect[0] <= px[0] and rect[1] <= px[1] and px[2] <= rect[2] and px[3] <= rect[3]:
                dx, dy = x - rect[0], y - rect[1]
                return [
                    round((u1 * width / 16 + dx) * 16 / new_width, 6),
                    round((v1 * height / 16 + dy) * 16 / new_height, 6),
                    round((u2 * width / 16 + dx) * 16 / new_width, 6),
                    round((v2 * height / 16 + dy) * 16 / new_height, 6),
                ], (dx, dy)
        raise AssertionError(f'{texture}: no merged rectangle contains {px}')

    changes = {}
    for path, face in faces:
        new_uv, shift = remap(face)
        changes.setdefault(path, []).append((face['uv'], new_uv, shift))
    return image, new_image, rects, changes, texture_path, area


def verify(image, new_image, uv_pairs):
    """Every texel centre inside every face samples the same colour before and after."""
    width, height = image.size
    new_width, new_height = new_image.size
    old = image.load()
    new = new_image.load()
    checked = 0
    for old_uv, new_uv, _ in uv_pairs:
        u1, v1, u2, v2 = old_uv
        x_min, x_max = sorted((u1 * width / 16, u2 * width / 16))
        y_min, y_max = sorted((v1 * height / 16, v2 * height / 16))
        for py in range(math.floor(y_min), math.ceil(y_max)):
            for px in range(math.floor(x_min), math.ceil(x_max)):
                cx, cy = px + 0.5, py + 0.5
                if not (x_min <= cx <= x_max and y_min <= cy <= y_max):
                    continue
                # Same relative position inside the face in both UV spaces
                tu = (cx - u1 * width / 16) / ((u2 - u1) * width / 16) if u2 != u1 else 0
                tv = (cy - v1 * height / 16) / ((v2 - v1) * height / 16) if v2 != v1 else 0
                nx = (new_uv[0] + (new_uv[2] - new_uv[0]) * tu) * new_width / 16
                ny = (new_uv[1] + (new_uv[3] - new_uv[1]) * tv) * new_height / 16
                if old[px, py] != new[math.floor(nx), math.floor(ny)]:
                    raise AssertionError(f'texel ({px}, {py}) differs after repacking')
                checked += 1
    return checked


UV_PATTERN = re.compile(r'"uv"\s*:\s*\[[^\]]*\]')


def format_number(value):
    text = f'{value:.6f}'.rstrip('0').rstrip('.')
    return '0' if text in ('-0', '') else text


def rewrite_uvs(path, target, entries):
    """Replaces only the matching "uv" arrays in the file text, keeping the original formatting."""
    with open(path, encoding='utf-8', newline='') as stream:
        text = stream.read()
    model = json.loads(text)
    textures = model.get('textures') or {}
    faces = []
    for element in model.get('elements', []):
        for face in element.get('faces', {}).values():
            if 'uv' in face:
                reference = face.get('texture', '')
                resolved = textures.get(reference[1:], reference) if reference.startswith('#') else reference
                faces.append((face, resolved == target))
    matches = list(UV_PATTERN.finditer(text))
    if len(matches) != len(faces):
        raise AssertionError(f'{path}: {len(matches)} "uv" arrays in the text but {len(faces)} faces with a UV')
    queue = list(entries)
    pieces = []
    last = 0
    for match, (face, selected) in zip(matches, faces):
        if not selected:
            continue
        old_uv, new_uv, _ = queue.pop(0)
        if json.loads(match.group(0)[match.group(0).index('['):]) != old_uv or face['uv'] != old_uv:
            raise AssertionError(f'{path}: UV order differs between the text and the parsed model')
        pieces.append(text[last:match.start()])
        pieces.append('"uv": [' + ', '.join(format_number(value) for value in new_uv) + ']')
        last = match.end()
    if queue:
        raise AssertionError(f'{path}: {len(queue)} faces were not rewritten')
    pieces.append(text[last:])
    with open(path, 'w', encoding='utf-8', newline='') as stream:
        stream.write(''.join(pieces))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('assets_dir')
    parser.add_argument('namespace')
    parser.add_argument('textures', nargs='+')
    args = parser.parse_args()
    for texture in args.textures:
        result = repack(args.assets_dir, args.namespace, texture)
        if result is None:
            continue
        image, new_image, rects, changes, texture_path, area = result
        pairs = [pair for entries in changes.values() for pair in entries]
        checked = verify(image, new_image, pairs)
        new_image.save(texture_path, optimize=True)
        for path, entries in changes.items():
            rewrite_uvs(path, f'{args.namespace}:block/{texture}', entries)
        print(f'{texture}: {image.size[0]}x{image.size[1]} -> {new_image.size[0]}x{new_image.size[1]} '
              f'({len(rects)} regions, {len(pairs)} faces in {len(changes)} models, {checked} texels verified)')


if __name__ == '__main__':
    sys.exit(main())
