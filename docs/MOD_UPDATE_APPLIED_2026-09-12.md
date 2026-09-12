# 공식 후속 버전 적용 — 2026-09-12

Minecraft **1.20.4 / Fabric**을 유지하여 공식 후속 버전 14종을 선택했다. Fabric API 0.97.3은 기존 반영을 유지하며, 나머지는 운영 기준본과의 버전 차이를 빌드·공개팩 입력에 반영했다. Axiom은 활성 목록·빌드·서버팩·클라이언트팩에서 제외했다. 서버 67개, 클라이언트 65개, 소스 빌드 46개, 바이너리 21개다.

2026-09-06에 관측한 JAR 70개의 원본 버전·해시·파일은 보존한다. `mods.lock.json`의 버전이 아래 적용 버전과 다른 것은 서버에서 새로 관측한 기록으로 덮어쓰지 않았기 때문이다. 운영 서버의 파일·업로드·재시작과 GitHub Release 게시는 이번 작업에 포함하지 않았다. root 변경은 로컬 커밋이며, 수정한 하위 소스 커밋만 원격의 별도 브랜치에 보존했다.

## 실제 선택 버전

| 모드 | 관측 운영 버전 | 적용 버전 | 처리 | 공개팩 선택 |
| --- | --- | --- | --- | --- |
| CityCraft | 2.0.0 | 2.1.1 | 공식 JAR 갱신 | embed / built |
| Fabric API | 0.97.2+1.20.4 | 0.97.3+1.20.4 | 기존 반영 유지 | download / built |
| Fusion | 1.2.12 | 1.3.15+a | 공식 JAR 갱신 | download / built |
| Macaw’s Doors | 1.1.2 | 1.1.5 | 공식 JAR 갱신 | embed / built |
| Macaw’s Fences and Walls | 1.2.0 | 1.2.1 | 공식 JAR 갱신 | embed / built |
| Macaw’s Windows | 2.3.1 | 2.4.2 | 공식 JAR 갱신 | download / built |
| Modern Lights | 2.4.2 | 2.5.0 | 기존 소스 빌드 유지·공개 선택 갱신 | manual / built |
| MTR Station Decoration | 1.3.15 | 1.4.5 | 공식 소스 병합·빌드 | embed / built |
| Paladin’s Furniture | 1.4.4 | 1.5.0 | 기존 소스 빌드 유지·공개 선택 갱신 | download / published |
| PTS Decoration | 2.1.0 | 4.0.0 | 공식 JAR 갱신 | embed / built |
| Puzzles Lib | 20.4.52 | 20.4.53 | 기존 소스 빌드 유지·공개 선택 갱신 | download / published |
| Rechiseled | 1.2.1 | 1.2.5 | 공식 JAR 갱신 | download / built |
| SuperMartijn642’s Core Lib | 1.1.20 | 1.1.24 | 공식 JAR 갱신 | download / built |
| WorldEdit Hang Fix | 1.0.2 | 1.0.5 | 공식 소스 병합·빌드 | embed / built |

`built`는 혼합 빌드의 결과를 선택한다는 뜻이다. binary recipe인 모드는 공식 JAR를 그대로 사용한다. `published`는 기존 소스 빌드와 별도로 검토한 공식 배포 파일을 선택한다. `manual` 파일은 공개팩에 직접 넣거나 자동 다운로드하지 않으며 안내된 정확한 JAR를 복원해야 설치가 완료된다.

비공개 혼합 ZIP의 소스 빌드 항목은 기존 도구 계약에 따라 운영 기준본의 `license` 판정과 과거 고지를 함께 보존한다. Modern Lights의 `embedded MIT` 기록은 관측한 2.4.2 JAR에 해당하며, 실제 2.5.0 실행 JAR의 `fabric.mod.json`과 `LICENSE_modern-lights`는 CC-BY-NC-SA-4.0이다. 아래 적용 JSON과 공개팩 기록·고지는 현재 실행 파일의 라이선스를 명시하고 과거 판정을 구분한다.

버전별 전체 누적 변경사항과 공식 릴리스 링크는 [사전 전수 조사](MOD_UPDATE_AUDIT_2026-09-12.md)에 있다. 현재 선택·출처·전체 해시는 [적용 기록 JSON](../inventory/update-applied-2026-09-12.json), [공식 바이너리 15개](../inventory/dependencies.lock.json), [공개 배포 선택 2개](../inventory/published-artifacts.lock.json), [소스 빌드 recipe](../inventory/build-recipes.json)에 고정했다.

## 소스와 라이선스

- **MSD:** 공식 1.4.5는 beta 채널이다. upstream `4.0.0`의 `14b0a8c9687bdbbfd755f282bbfab4030a92f3d3`를 병합하고 기존 Minefed Loom 1.10.5 및 buildSrc 호환 설정을 유지했다. 최종 [b06fc0725b20a5b7a6c72bdacd20814dd8d8aabf](https://github.com/minefed/MTR-Station-Decoration-Addon/commit/b06fc0725b20a5b7a6c72bdacd20814dd8d8aabf), 추적 브랜치 `codex/update-msd-1.4.5`. 기존 JAR에서 누락됐던 원본 MIT 고지를 포함하는 별도 수정도 검증했다. 컴파일 대상 MTR은 4.0.5이며 현재 MTR 4.0.5를 유지한다.
- **WorldEdit Hang Fix:** 공식 태그 `v1.0.5`, upstream `583c7ceab5031d0864bf85a5934662a8def870e2`를 병합했다. 최종 [45c744113850a55f844c7195d5e074b6845d28eb](https://github.com/minefed/worldedit-hang-fix/commit/45c744113850a55f844c7195d5e074b6845d28eb), 추적 브랜치 `codex/update-worldedit-hang-fix-1.0.5`. JDK 21로 `1.18.2-fabric` 대상을 빌드하며 실제 호환 범위는 `>=1.18 <1.20.5`, 출력은 Java 17이다. 원본 LGPL 고지와 기존 AGENTS 지침을 보존했다.
- **Modern Lights:** 공식 [2.5.0 업로드](https://modrinth.com/version/chMskrKw)는 `.class`가 없는 sources JAR이며 버전 치환도 완료되지 않아 실행 파일로 채택하지 않았다. 이미 관리하던 정상 2.5.0 소스 빌드를 사용한다. CC-BY-NC-SA-4.0의 공개 배포 조건 충족은 확인되지 않아 `local-only`를 유지하고 공개팩은 `manual/built`로 변경했다. **비공개 혼합 ZIP에는 실행 JAR가 들어가지만 공개팩은 수동 복원 1개가 필요하다.**
- **PFM:** 코드 LGPL-3.0-only와 자산 PolyForm-Shield-1.0.0을 구분했다. 새 `assets/pfm/LICENSE-ASSETS.md`, 중첩 color-thief-java의 CC-BY-2.5 출처·저작자 고지를 보존한다. 자산 조건은 경쟁 제품 제한이며 비상업 전용으로 표시하지 않았다. 공개팩은 수정하지 않은 공식 다운로드를 사용한다.
- **Puzzles Lib:** MPL-2.0 코드와 ARR 자산 구분, 갱신된 2023–2025 저작권 고지를 보존했다. 공개팩은 공식 다운로드를 사용한다.
- **CityCraft·Macaw 계열:** 새 JAR의 고지를 [해시별 notice 폴더](../inventory/notices/)에 보존했다. CityCraft의 CC0 고지 파일명 변경과 Macaw 저작자·공식 페이지 출처 조건을 기록했다. 기존 CityCraft/Doors/Fences 소스가 새 공식 Fabric 바이너리와 동일한 대응 소스라고 단정하지 않는다.
- **Fusion·Rechiseled·Core Lib·PTS:** ARR 및 모드팩 포함 허용 조건을 유지한다. 원본 공식 JAR, 정확한 출처와 해시를 고정하며 JAR를 Git에 추가하지 않았다. 소스 ref가 확인되는 라이브러리는 전체 커밋과 버전 선언을 함께 기록했다.

## 검증

- 공식 후보의 실제 파일 크기, SHA-256/SHA-512, Fabric ID·버전·환경·Minecraft/Java/Loader 조건을 검사했다.
- 빈 캐시에서 현재 binary 21개와 공개 선택 2개, 총 23개를 공식 URL로 복원하고 해시와 메타데이터를 재검증했다.
- 도구 회귀 검사 136개: 오류 없음, 환경별 4개 건너뜀.
- MSD와 Hang Fix 새 소스의 개별 빌드 및 Java 17 바이트코드·원본 고지 일치를 확인했다. 두 원격 브랜치의 전체 커밋 해시도 확인했다.
- 전체 소스 46개와 공식 바이너리 21개로 67개 모드의 혼합 ZIP을 생성했다. 최종 팩의 CRC·JAR 해시·버전·Axiom 부재·고지 보존 검사가 통과했다.
- 최종 실제 JAR를 대상으로 서버·클라이언트의 필수 의존성 누락·버전 충돌·차단 조건을 검사했고 오류가 없었다. 실제 Minecraft 기동은 수행하지 않았다.

Fabric Loader 정책은 0.18.0을 유지한다. Rechiseled 1.2.5가 `>=0.18.0`, Fusion이 Fabric API `>=0.97.3`을 요구하므로 실제 설치에도 이 조건이 필요하다. 메타데이터 검사는 Minecraft 기동, Mixin·클래스 연결 및 실제 플레이 검증을 대신하지 않는다. **PTS Decoration 4.0.0의 블록 ID 변경에 대한 기존 월드 마이그레이션은 검증하지 않았다.**

공식 후속 릴리스가 없는 개발 소스 후보 MTR 4.0.6, Wireless Redstone, Patchouli, Mythic Metals, Yuushya Townscape의 추가 변경은 이번 공식 버전 적용에 포함하지 않았다.


## 최종 로컬 산출물

빌드 실행 `20260912-023109-c1a1a771`. 로컬 팩 버전 `20260912124625`. 원격 Release 게시와 운영 서버 적용은 하지 않았다.

| 산출물 | 로컬 경로 | 크기(bytes) | SHA-256 |
| --- | --- | ---: | --- |
| 비공개 혼합 ZIP | `build/distributions/minefed-1.20.4-20260912-023109-c1a1a771.zip` | 254844055 | `f901781c85394070d77093af86ea0b225a77746bdd87888af624e50464bbe77f` |
| server.zip | `build/releases/20260912124625/server.zip` | 200138973 | `ad44d477e70f64373ae96cb776a8f591539c188a6e9abc7de270f6bd81f5de0f` |
| client.mrpack | `build/releases/20260912124625/client.mrpack` | 200898752 | `e12585e6a7b88d1f424cb94d89a09d00bde8c9ba54000a36dec2effd32873a2a` |
| resourcepack.zip | `build/releases/20260912124625/resourcepack.zip` | 1058344 | `1df46328e8fbfa004c7aaf745c1994745c21bf251cc46000d3b8fd229e5cd75e` |

서버팩은 67개(내장 36·다운로드 30·수동 1), 클라이언트팩은 65개다. 공개 Modern Lights 항목은 정확한 2.5.0 빌드 해시와 필수 수동 복원 안내를 포함한다. 소스 JAR를 실행 파일로 채택하지 않았다. 최종 PFM 자산 고지·Sven Woltmann의 Java 포트 크레딧·Macaw 저작자와 공식 페이지 링크 보존을 확인했다.

상세 로컬 증거: `build/mod-update-apply-20260912/final-pack-verification.json`, `python-tests.log`, `repository-policy.log`, `baseline-verification.log`, `cold-artifact-verification.json`. 최종 배포 선택과 의존성 보고서는 각 팩의 `download-manifest.json`, `DEPENDENCIES.json`, `LICENSES.md` 및 로컬 `release-assets.json`에도 들어 있다.

선택한 14종과 선언된 중첩 런타임 JAR의 클래스 헤더가 Java 17 기준 검사를 통과했다. Java 17에서 사용하는 클래스는 major 61 이하이며 preview 클래스는 없었다. 더 높은 Java용 멀티릴리스 항목은 별도로 구분했다. 실제 클래스 로딩과 Minecraft 기동 검증은 수행하지 않았다.

기존 Yuushya Townscape의 리소스 생성 중 `yuushya:template/slab_cube_yellow_wool` 모델을 읽지 못했다는 로그가 3회 있었으나 생성 작업과 실행 JAR 빌드는 성공했다. 이 모델의 게임 내 표현은 확인하지 않았다. 관련 로그는 `build/modpack-work/20260912-023109-c1a1a771/sources/yuushya/gradle-1.log`에 보존했다.
