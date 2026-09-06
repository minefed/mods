# Minefed 운영 모드 인벤토리

2026-09-06 FileZilla에서 서버 `mods` 폴더의 70개 파일(433,889,641바이트)을 확인하고 원본 JAR를 내려받아 SHA256을 기록했다. 기준 환경은 Minecraft 1.20.4 / Fabric이다. 운영 서버 파일은 변경하지 않았다.

소스 관리 대상은 58개 JAR에 대응하는 57개 저장소이며, 바이너리 관리 대상은 12개다. 기존 Automobility는 운영 Refueled와 구분해 별도 보존한다. 공식 배포 파일과 해시가 일치한 항목은 64개다.

[mods.lock.json](../inventory/mods.lock.json)에 전체 SHA256·크기·소스 원격/브랜치/전체 커밋·배포 URL·의존성·포함 여부를, [license-audit.json](../inventory/license-audit.json)에 라이선스 판단과 증거 URL을 보관한다. 표의 커밋은 하위 AGENTS.md를 포함한 관리 커밋의 축약이다. 원래 소스는 baselineRef/baselineCommit, 실제 gitlink는 ref/commit으로 구분하며 전체 40자리 해시를 기록한다. 모든 관리 커밋을 minefed 원격에서 확인했다.

소스 관리 모드의 운영 JAR는 `artifacts/local/`, 재배포 조건이 제한된 바이너리는 `vendor/local/`에 보존한다. 재배포 가능한 Dusty Decorations 원본 JAR는 `vendor/jars/`에 둔다. 앞의 두 로컬 폴더는 Git에서 제외한다. JAR에 포함된 원본 라이선스 고지는 [inventory/notices](../inventory/notices/)에 추출했다.

JAR 재배포 분류는 허용 45개, 모드팩 한정 10개, 로컬 전용 15개다. ‘허용’도 원본 고지와 해당되는 대응 소스 제공 의무를 지켜야 한다. ‘모드팩 한정’은 원본 JAR의 모드팩 포함에 대한 허용이며 독립 파일 미러링이나 자산 재사용 허용을 뜻하지 않는다. ‘로컬 전용’ JAR는 Git에 추가하지 않는다.

현재 서버 모드팩 입력은 68개다. MTR 4.0.3은 동일 ID의 4.0.5가 있어 제외하고, TCPShield는 Fabric 모드가 아닌 Bukkit/Bungee/Velocity 플러그인이라 제외한다. 두 파일 모두 원본 인벤토리에 보존한다. 이 목록은 서버가 실제로 모든 모드를 성공적으로 로드했다는 기록이 아니다.

소스 관리와 일괄 빌드 준비 시 다음 차이를 유지해야 한다.

- 기존 minefed MTR·display·webstreamer와 Chisels-and-Bits는 확인된 최신 원격 커밋을 사용한다. 운영 JAR는 별도로 보존하며 빌드 결과로 자동 대체하지 않는다.
- CityCraft는 공개 소스가 운영 버전보다 오래되었고, Macaw Doors/Fences는 Forge 소스만 공개되어 있다. Dusty Decorations도 공개된 Forge 소스와 운영 Fabric 포트가 다르므로 원본 JAR를 기준으로 관리한다.
- Handcrafted, Mythic Metals 계열과 Fuzss 계열은 코드와 자산의 라이선스가 다르다. MIT/MPL 코드 허용만으로 JAR·텍스처 재배포를 허용하지 않는다. Mythic Metals의 원본 모드팩 사용 허용은 별도 기록했다.
- Modern Lights와 Patchouli의 비상업·동일조건변경허락 조건, Japan Props의 서로 다른 라이선스 표기는 별도로 보존한다. Modern Lights 소스는 2.5.0이며 운영 JAR는 2.4.2다.
- Paladin Furniture의 관리 소스는 운영 JAR와 버전이 다르다. Yuushya Townscape는 원저자의 Gitee v2.2.3 소스를 minefed 관리 브랜치에 가져와 운영 버전으로 고정했다.
- Japan Props는 배포자가 1.20.4에서의 호환성 문제 가능성을 명시한다. WorldEdit Hang Fix는 파일명에 1.20.6이 있지만 JAR 메타데이터는 1.14 이상을 허용한다. 이 준비 작업에서 서버 기동 테스트는 수행하지 않았다.

| # | 운영 JAR | ID / 버전 | 관리 소스·커밋 | JAR 정책 | 서버팩 |
| ---: | --- | --- | --- | --- | --- |
| 1 | alloy-forgery-2.1.4+1.20.3.jar | alloy_forgery / 2.1.4+1.20.3 | alloy-forgery · badd26ba | 허용 | 포함 |
| 2 | architectury-11.1.17-fabric.jar | architectury / 11.1.17 | architectury-api · d9735974 | 허용 | 포함 |
| 3 | automobility-refueled-0.4.3.b+1.20.4-fabric.jar | automobility-refueled / 0.4.3.b+1.20.4-fabric | Automobility-Refueled · 13160075 | 허용 | 포함 |
| 4 | Axiom-5.3.0-for-MC1.20.4.jar | axiom / 5.3.0 | 바이너리 | 로컬 전용 | 포함 |
| 5 | BlueMap-5.3-fabric-1.20.jar | bluemap / 5.3 | BlueMap · 129769c0 | 허용 | 포함 |
| 6 | botarium-fabric-1.20.4-3.2.2.jar | botarium / 3.2.2 | Common-Storage-Lib · ae864ea9 | 허용 | 포함 |
| 7 | cc-tweaked-1.20.4-fabric-1.110.2.jar | computercraft / 1.110.2 | CC-Tweaked · c3264ade | 허용 | 포함 |
| 8 | chisels-and-bits-fabric-1.5.10-FC.jar | chiselsandbits / 1.5.10-FC | Chisels-and-Bits · 2142e101 | 허용 | 포함 |
| 9 | Chunky-1.3.146.jar | chunky / 1.3.146 | Chunky · e6aac5fe | 허용 | 포함 |
| 10 | City Craft-2.0.0-Fabric-1.20.x(ex.5.6).jar | citycraft / 2.0.0 | CityCraft · 32f4d36f | 허용 | 포함 |
| 11 | crossstitch-0.1.6.jar | crossstitch / 0.1.6 | CrossStitch · b509f10b | 허용 | 포함 |
| 12 | Decorative Blocks-Fabric-1.20.4-5.0.2.jar | decorative_blocks / 5.0.2 | Decorative-Blocks · 7c8f25ae | 허용 | 포함 |
| 13 | DiagonalFences-v20.4.1-1.20.4-Fabric.jar | diagonalfences / 20.4.1 | diagonal-fences · dca73bef | 로컬 전용 | 포함 |
| 14 | DiagonalWalls-v20.4.1-1.20.4-Fabric.jar | diagonalwalls / 20.4.1 | diagonal-walls · 4fefe0eb | 로컬 전용 | 포함 |
| 15 | DiagonalWindows-v20.4.1-1.20.4-Fabric.jar | diagonalwindows / 20.4.1 | diagonal-windows · 0dea1267 | 로컬 전용 | 포함 |
| 16 | DustyDecoRefabricated-1.1-1.20.3+1.20.4.jar | dustydecorations / 1.1-1.20.3+1.20.4 | 바이너리 | 허용 | 포함 |
| 17 | exlinefurniture-v2.7.2-fabric-1.20.4.jar | exlinefurniture / 2.7.2 | 바이너리 | 로컬 전용 | 포함 |
| 18 | fabric-api-0.97.2+1.20.4.jar | fabric-api / 0.97.2+1.20.4 | fabric-api · b0291a8c | 허용 | 포함 |
| 19 | fabric-carpet-1.20.3-1.4.128+v231205.jar | carpet / 1.4.128+v231205 | fabric-carpet · 9e4083fc | 허용 | 포함 |
| 20 | fabric-seasons-2.4.2-BETA+1.20.4.jar | seasons / 2.4.2-BETA+1.20.4 | fabric-seasons · 8e7833a5 | 허용 | 포함 |
| 21 | FabricProxy-Lite-2.7.0.jar | fabricproxy-lite / 2.7.0 | FabricProxy-Lite · 7391c126 | 허용 | 포함 |
| 22 | FallingTree-1.20.4-1.20.4.3.jar | fallingtree / 1.20.4.3 | FallingTree · 0a70a01d | 허용 | 포함 |
| 23 | ferritecore-6.0.3-fabric.jar | ferritecore / 6.0.3 | FerriteCore · a6b89994 | 허용 | 포함 |
| 24 | ForgeConfigAPIPort-v20.4.3-1.20.4-Fabric.jar | forgeconfigapiport / 20.4.3 | forge-config-api-port · 6bcbe199 | 로컬 전용 | 포함 |
| 25 | furnitureexpanded-1.1-1.20.4-FABRIC-EXP.jar | furnitureexpanded / 1.1-1.20.4 | 바이너리 | 로컬 전용 | 포함 |
| 26 | fusion-1.2.12-fabric-mc1.20.4.jar | fusion / 1.2.12 | 바이너리 | 모드팩 한정 | 포함 |
| 27 | geckolib-fabric-1.20.4-4.4.4.jar | geckolib / 4.4.4 | geckolib · 0645b106 | 허용 | 포함 |
| 28 | handcrafted-fabric-1.20.4-3.2.1.jar | handcrafted / 3.2.1 | Handcrafted · 7421fc23 | 로컬 전용 | 포함 |
| 29 | JapanProps_1.20.1_0.0.3.3_Fabric.jar | jpp / 0.0.3.3 | 바이너리 | 로컬 전용 | 포함 |
| 30 | lavender-0.1.9+1.20.3.jar | lavender / 0.1.9+1.20.3 | lavender · cc99a048 | 허용 | 포함 |
| 31 | lithium-fabric-mc1.20.4-0.12.1.jar | lithium / 0.12.1 | lithium · 6bb7238e | 허용 | 포함 |
| 32 | mcw-doors-1.1.2-mc1.20.4fabric.jar | mcwdoors / 1.1.2 | MacawsDoors · b07c8caa | 허용 | 포함 |
| 33 | mcw-fences-1.2.0-1.20.4fabric.jar | mcwfences / 1.2.0 | Fences · c9821fbd | 허용 | 포함 |
| 34 | mcw-roofs-2.3.2-mc1.20.4fabric.jar | mcwroofs / 2.3.2 | 바이너리 | 모드팩 한정 | 포함 |
| 35 | mcw-windows-2.3.1-mc1.20.4fabric.jar | mcwwindows / 2.3.1 | 바이너리 | 모드팩 한정 | 포함 |
| 36 | memoryleakfix-fabric-1.17+-1.1.5.jar | memoryleakfix / 1.1.5 | MemoryLeakFix · 0105090f | 허용 | 포함 |
| 37 | minefed-display-1.0.0.jar | minefed-display / 1.0.0 | minefed-display · d4ce3226 | 허용 | 포함 |
| 38 | mishanguc-1.5.3-1.20.4.jar | mishanguc / 1.5.3 | mishanguc · b8addb77 | 허용 | 포함 |
| 39 | modern-glass-doors-5.3.0+1.20.3-and-later.jar | modern_glass_doors / 5.3.0+1.20.3-and-later | modern-glass-doors · 155e732f | 허용 | 포함 |
| 40 | modern-lights-1.20[2.4.2].jar | modernlights / 2.4.2 | Modern-Lights · 6b04f156 | 로컬 전용 | 포함 |
| 41 | modernfix-fabric-5.17.0+mc1.20.4.jar | modernfix / 5.17.0+mc1.20.4 | ModernFix · 2856e289 | 허용 | 포함 |
| 42 | MSD-fabric-1.20.4-4.0.0-beta.14-1.3.15.jar | msd / 1.3.15 | MTR-Station-Decoration-Addon · d59160ac | 허용 | 포함 |
| 43 | MTR-fabric-4.0.3+1.20.4.jar | mtr / 4.0.3 | Minecraft-Transit-Railway · 34a4a8db | 허용 | 제외 |
| 44 | MTR-fabric-4.0.5+1.20.4.jar | mtr / 4.0.5 | Minecraft-Transit-Railway · 34a4a8db | 허용 | 포함 |
| 45 | mythicmetals-0.19.7+1.20.4.jar | mythicmetals / 0.19.7+1.20.4 | MythicMetals · cfa897b7 | 모드팩 한정 | 포함 |
| 46 | mythicmetals-decorations-0.6.1+1.20.3.jar | mythicmetals_decorations / 0.6.1+1.20.3 | MythicMetalsDecorations · c9326608 | 로컬 전용 | 포함 |
| 47 | nicemod-1.4.1 - 1.20.jar | nicemod / 1.4.1 - 1.20 | NiceMod · c3447636 | 허용 | 포함 |
| 48 | oritech-0.5.1+1.20.4.jar | oritech / 0.5.1+1.20.4 | Oritech · 1cf7cfe9 | 허용 | 포함 |
| 49 | owo-lib-0.12.6+1.20.3.jar | owo / 0.12.6+1.20.3 | owo-lib · 715959e5 | 허용 | 포함 |
| 50 | paladin-furniture-mod-1.4.4-fabric-mc1.20.4.jar | pfm / 1.4.4 | paladins-furniture · 131ac50f | 허용 | 포함 |
| 51 | Patchouli-1.20.4-85-FABRIC.jar | patchouli / 1.20.4-85-FABRIC | Patchouli · 9b18022c | 로컬 전용 | 포함 |
| 52 | PTS-Deco-2.1.0-Fabric+Quilt1.20-1.20.4.jar | ptsdeco / 2.1.0 | 바이너리 | 모드팩 한정 | 포함 |
| 53 | PuzzlesLib-v20.4.52-1.20.4-Fabric.jar | puzzleslib / 20.4.52 | puzzles-lib · 5d2f50b9 | 로컬 전용 | 포함 |
| 54 | realtime-1.0.3-1.20-1.21.1.jar | realtime / 1.0.3-1.20-1.21.1 | mc-realtime · bd05e0fe | 허용 | 포함 |
| 55 | rechiseled-1.2.1-fabric-mc1.20.4.jar | rechiseled / 1.2.1 | 바이너리 | 모드팩 한정 | 포함 |
| 56 | resourcefulconfig-fabric-1.20.4-2.4.8.jar | resourcefulconfig / 2.4.8 | Resourceful-Config · 6f5fb83c | 허용 | 포함 |
| 57 | resourcefullib-fabric-1.20.4-2.4.10.jar | resourcefullib / 2.4.10 | ResourcefulLib · 5404f9f6 | 허용 | 포함 |
| 58 | starlight-1.1.3+fabric.f5dcd1a.jar | starlight / 1.1.3+fabric.f5dcd1a | Starlight · c2b8391d | 허용 | 포함 |
| 59 | Stoneworks-v20.4.0-1.20.4-Fabric.jar | stoneworks / 20.4.0 | stoneworks · c9c0c785 | 로컬 전용 | 포함 |
| 60 | supermartijn642configlib-1.1.8a-fabric-mc1.20.2.jar | supermartijn642configlib / 1.1.8+a | 바이너리 | 모드팩 한정 | 포함 |
| 61 | supermartijn642corelib-1.1.20-fabric-mc1.20.4.jar | supermartijn642corelib / 1.1.20 | 바이너리 | 모드팩 한정 | 포함 |
| 62 | TCPShield-2.8.1.jar | Fabric 메타데이터 없음 | RealIP · b0a19561 | 허용 | 제외 |
| 63 | timeoutout-1.0.4+1.20.2.jar | timeoutout / 1.0.4+1.20.2 | TimeOutOut · 0d27ca11 | 허용 | 포함 |
| 64 | trafficcraft-fabric-1.20.4-1.1.3.jar | trafficcraft / 1.20.4-1.1.3 | TrafficCraft · 40b94053 | 로컬 전용 | 포함 |
| 65 | webstreamer-1.5.0.jar | webstreamer / 1.5.0 | fabric-webstreamer · a952b941 | 허용 | 포함 |
| 66 | wirelessredstone-fabric-1.2.2+1.20.4.jar | wirelessredstone / 1.2.2+1.20.4 | wireless-redstone · 85cd6b45 | 허용 | 포함 |
| 67 | worldedit-hang-fix-v1.0.2-mc1.20.6-fabric.jar | worldedithangfix / 1.0.2 | worldedit-hang-fix · ae96bc02 | 허용 | 포함 |
| 68 | worldedit-mod-7.3.0.jar | worldedit / 7.3.0+6678-55745ad | WorldEdit · 088da04a | 허용 | 포함 |
| 69 | yuushya-1.20.4-fabric-2.2.3.jar | yuushya / 2.2.3 | Yuushya-Townscape · 67dc8719 | 모드팩 한정 | 포함 |
| 70 | yuushya-modelling-1.20.4-fabric-2.2.0.jar | yuushya_modelling / 2.2.0 | Yuushya-Modelling · d7302257 | 모드팩 한정 | 포함 |

모든 하위 저장소 작업에도 상위 [AGENTS.md](../AGENTS.md)의 작은 단위 커밋, Conventional Commits, 원격에서 가져올 수 있는 gitlink, 라이선스 보존 지침을 적용한다.
