# Minefed Resource Fixes

This resource-only Fabric mod contains no textures, executable classes or third-party JARs.
Its zz_ ID loads after the original models in the pinned Fabric Loader 0.18.4 production ordering. Dependency declarations alone do not control resource priority. The original third-party JARs retain their own licenses.

The two hydrargym chest model JSON files derive from the MIT-licensed software in
Mythic Metals Decorations by Noaaan and its contributors. Copyright (c) 2021.
Minefed corrected the particle texture namespace; model parents and display transforms are preserved.
The upstream MIT copyright, permission and warranty notice is reproduced in LICENSE.
The upstream texture reservation remains applicable: all textures belong to their respective
artists and are all rights reserved. No such textures are included here.

Source: https://github.com/Noaaan/MythicMetalsDecorations/blob/0.6.1%2B1.20.3/LICENSE
Correction: https://github.com/minefed/MythicMetalsDecorations/commit/f5af39239697e9ed89a108da59c2f8eac695d3df

The optional non_diagonal_fences tag entries are authored by Minefed contributors,
Copyright (c) 2026, under MIT. They refer to 14 Macaw grass-topped walls and merge with
the existing Diagonal Fences tag. No Diagonal Fences assets are included.

Source: https://github.com/minefed/diagonal-fences/commit/aa41b9f39f744455258c27d3728a1ff77908731f

The Exline's Furniture overrides are independently authored by Minefed (MIT).
Version 2.7.2 registers neither the eleven wood dressers nor the two bamboo log
tables, but still bundles their recipes/loot. The obsolete dresser recipes use
Fabric's false empty-OR load condition, and the thirteen unused loot tables have
empty pools. No registered block, item, or usable recipe is removed. Registry
absence was checked in the complete Minecraft 1.20.4 client. Review these exact
overrides before changing Exline's version; the metadata rejects other versions.
No Exline code, models, textures, recipe patterns, or prose is included here.
The original mod retains its separate All Rights Reserved terms and official
download: https://modrinth.com/mod/exlines-furniture/version/DfuDGYlp

The empty Dusty Decorations `pot` loot table is independently authored by Minefed
(MIT). The pinned Fabric 1.1 release has no `pot` block/item; its registered
`cooking_pot` already has a separate, valid loot table which remains untouched.
Source release: https://modrinth.com/mod/dusty-decorations/version/DHsgxScD

The Japan Props teacup recipe is independently authored by Minefed (MIT).
It preserves the three-slab-and-berry crafting arrangement and single teacup
output, using the obtainable `minecraft:sweet_berries` item instead of the
non-item `minecraft:sweet_berry_bush` block. It loads only when Japan Props is
installed. No Japan Props code, artwork, or text is redistributed.
Source release: https://modrinth.com/mod/japan-props/version/hnS8fdTL
