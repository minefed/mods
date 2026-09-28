#!/usr/bin/env python3
"""Summarize client resources and world data failures without exporting raw logs."""

import argparse
from collections import Counter
import json
from pathlib import Path
import re


RESOURCE_ERRORS = {
    "invalidModel": "Failed to load model ",
    "missingModel": "Unable to load model:",
    "missingState": "Exception loading blockstate definition:",
    "missingTexture": "Missing textures in model ",
    "unresolvedTexture": "Unable to resolve texture reference:",
    "missingSprite": "Missing sprite:",
    "invalidCtmBlock": "Unknown block '",
    "incompatibleModel": "is using incompatible model",
}

# These only load when a world/server is entered. Title-screen reloads alone
# cannot validate recipes, loot, block tags, or the resolved Patchouli pages.
DATA_ERRORS = {
    "invalidRecipe": r"Parsing error loading recipe ([a-z0-9_.-]+:[a-z0-9_./-]+)",
    "invalidLootTable": r"Couldn't parse element loot_tables:([a-z0-9_.-]+:[a-z0-9_./-]+)",
    "missingTagReference": r"Couldn't load tag ([a-z0-9_.-]+:[a-z0-9_./-]+) as it is missing",
    "missingBookRecipe": r"Recipe ([a-z0-9_.-]+:[a-z0-9_./-]+) \(of type [^)]+\) not found",
    "invalidBookIcon": r"Invalid icon item stack: Unknown item ID: ([a-z0-9_.-]+:[a-z0-9_./-]+)",
}


def audit(text):
    counts = Counter()
    resources = {category: Counter() for category in (*RESOURCE_ERRORS, *DATA_ERRORS)}
    reloads = 0
    world_joins = 0
    startup_seconds = []
    for line in text.splitlines():
        if "Reloading ResourceManager:" in line:
            reloads += 1
        if "logged in with entity id" in line:
            world_joins += 1
        match = re.search(r"Game took ([0-9.]+) seconds", line)
        if match:
            startup_seconds.append(float(match.group(1)))
        for category, marker in RESOURCE_ERRORS.items():
            if marker not in line:
                continue
            counts[category] += 1
            # Only resource diagnostics are exported: omit time, thread and paths.
            message = line.split("]: ", 1)[-1]
            if category == "incompatibleModel":
                match = re.search(r"Block '([^']+)'", message)
            elif category in ("missingState", "missingModel", "invalidCtmBlock"):
                match = re.search(r"'([^']+)'", message)
            else:
                match = re.search(r"(?:model |sprite: |reference: )([^\s:]+:[^\s]+)", message)
            resources[category][match.group(1).rstrip(":") if match else "unparsed"] += 1
        for category, pattern in DATA_ERRORS.items():
            match = re.search(pattern, line)
            if match:
                counts[category] += 1
                resources[category][match.group(1)] += 1
        if "does not exist, cannot add it to event" in line:
            counts["missingSound"] += 1
    return {
        "schemaVersion": 1,
        "reloadStarts": reloads,
        "worldJoinCount": world_joins,
        "startupSeconds": startup_seconds,
        "resourceDiagnosticCount": sum(counts.values()),
        "counts": dict(sorted(counts.items())),
        "resources": {key: dict(sorted(value.items())) for key, value in resources.items() if value},
        "limits": "Covers emitted model/texture/CTM/sound and world recipe/loot/tag/book diagnostics. World data coverage requires entering a world; first-frame visual correctness and remote-server login require separate checks.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--strict", action="store_true", help="fail if resource diagnostics remain or no completed startup is recorded")
    parser.add_argument("--require-world", action="store_true", help="also fail when no world join is recorded")
    args = parser.parse_args()
    result = audit(args.log.read_text(encoding="utf-8", errors="replace"))
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return int((args.strict and (result["resourceDiagnosticCount"] > 0 or not result["startupSeconds"]))
               or (args.require_world and not result["worldJoinCount"]))


if __name__ == "__main__":
    raise SystemExit(main())
