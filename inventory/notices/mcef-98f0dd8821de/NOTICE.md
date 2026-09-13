# MCEF and Java-CEF notices

MCEF (Minecraft Chromium Embedded Framework)
Copyright (C) 2023 CinemaMod Group.

This pack selects the unmodified official Fabric MCEF 2.1.6-1.20.4 JAR from
https://modrinth.com/version/3koDiBl0 under the GNU Lesser General Public License
version 2.1. Official project metadata says LGPL-2.1-only; upstream source headers
permit version 2.1 or any later version. The original license is reproduced in
LICENSE-MCEF-LGPL-2.1.txt. MCEF is provided without warranty; see that license.

Java-CEF code is included in the official JAR.
Copyright (c) 2008-2013 Marshall A. Greenblatt.
Portions Copyright (c) 2006-2009 Google Inc. All rights reserved.
Its BSD 3-Clause terms and disclaimer are reproduced in
LICENSE-Java-CEF-BSD-3-Clause.txt.

Complete corresponding MCEF source, including its build files:
https://github.com/CinemaMod/mcef/archive/bb85d521e79662592fa72a67fadcbd622c664ce8.zip

The source build also requires its exact common/java-cef submodule:
https://github.com/CinemaMod/java-cef/archive/a78e832f9f13c2c688caea3d04d8b84fcd238d94.zip

Provide access to both source archives with redistribution. The upstream Maven
Fabric sources JAR contains only the Fabric module and is not the complete source.
Archive hashes, source commits, binary hashes and license provenance are in
provenance.json. No claim of a byte-for-byte reproducible build is made.

Chromium/CEF native runtime files are downloaded separately by MCEF. They are not
included in this dependency pin and retain their own copyright notices and
third-party license terms. Preserve those files and notices if preparing an offline
native cache. No extra permission is granted for their redistribution by this notice.
