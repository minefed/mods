# Minefed 모드 업데이트 전수 조사 — 2026-09-12

**Minecraft 1.20.4 / Fabric 유지**를 전제로 조사했다. 관리 목록 70 JAR 중 중복 MTR 4.0.3과 TCPShield를 제외한 **68개 모드**가 대상이다. 공식 후속 버전 표시는 15개이며, **실행용 JAR 후보 14개(정식 13·beta 1), Modern Lights 소스 JAR 문제로 보류 1개**로 나뉜다. 추가로 **미출시 소스 후보 5개**, 운영 기준본 이후 **이미 준비된 Minefed 자체 수정 2개**를 확인했다.

여기서 “현재 운영”은 **2026-09-06에 보관한 운영 JAR 기준본**이다. 실제 서버를 다시 조회하지 않았으므로 9월 12일 현재 배포 상태를 확정하지 않는다. “빌드”와 “공개팩”은 이 저장소의 recipe/dependency lock/release policy가 선택하는 값이며 실제 최근 배포 완료 여부와도 구분한다. 정식 배포가 없는 항목은 현재 beta/alpha 채널을 유지해 비교했다.

조사 기준 상위 커밋: `2f096b98f25ea920c0d84124e570e837e59e3112`. 근거는 [운영 기준 lock](../inventory/mods.lock.json), [빌드 recipe](../inventory/build-recipes.json), [공식 의존성 pin](../inventory/dependencies.lock.json), [공개팩 선택 정책](../inventory/release-policy.json)이다. 정확한 버전 ID·URL·새 파일 SHA256/SHA512·실제 Fabric 메타데이터·현재 소스 커밋은 [정규화 조사 데이터](../inventory/update-audit-2026-09-12.json)에 기록했다.

## 공식 후속 버전 15개

| 모드 | 운영 기준 → 후속 버전 | 빌드 / 공개팩 선택 | 판정·변경 핵심 |
| --- | --- | --- | --- |
| Axiom | 5.3.0 → [5.4.2](https://modrinth.com/version/yt1TxRll) | 5.3.0 / 5.3.0 | 새 정식판 — Blend·조명/데이터 복구·Lua·편집/렌더 오류 수정 |
| CityCraft | 2.0.0 → [2.1.1](https://modrinth.com/version/gRav2TDu) | 2.0.0 / 2.0.0 | 새 정식판 — 2.1.0/2.1.1 로그 공란; 교통/상점 관련 자원 차이 확인 |
| Fabric API | 0.97.2+1.20.4 → [0.97.3+1.20.4](https://modrinth.com/version/BPX6fK06) | 0.97.3+1.20.4 / 0.97.3+1.20.4 | 공개팩 반영됨 — 인챈트 테이블 수정; 빌드·공개팩은 이미 반영 |
| Fusion | 1.2.12 → [1.3.15a](https://modrinth.com/version/Qyr4qxvT) | 1.2.12 / 1.2.12 | 새 정식판 — 모델/텍스처 개편·메모리·호환성·충돌 수정; API≥0.97.3 필요 |
| Macaw’s Doors | 1.1.2 → [1.1.5](https://modrinth.com/version/8l41DNKc) | 1.1.2 / 1.1.2 | 새 정식판 — 차고문·낙하문 작동 개편, 충돌·음향·터틀/물 이동 수정 |
| Macaw’s Fences & Walls | 1.2.0 → [1.2.1](https://modrinth.com/version/UjYIrEaO) | 1.2.0 / 1.2.0 | 새 정식판 — Diagonal Fences 연동·누락 텍스처·불연성 난간문 수정 |
| Macaw’s Windows | 2.3.1 → [2.4.2](https://modrinth.com/version/DbNK4q5P) | 2.3.1 / 2.3.1 | 새 정식판 — 창 열림 방향·커튼/셔터·역조합·소리/조명 수정 |
| Modern Lights | 2.4.2 → [2.5.0 (소스 아티팩트)](https://modrinth.com/version/chMskrKw) | 2.5.0 / 2.4.2 | 보류: 소스 JAR — 레시피/발전과제 수정; 공식2.5.0은 소스 JAR뿐 |
| MTR Station Decoration Addon (MSD) | 1.3.15 → [1.4.5](https://modrinth.com/version/nMixopsa) | 1.3.15 / 1.3.15 | 새 beta — MTR4.0.5 대상 빌드로 갱신; beta |
| Paladin’s Furniture | 1.4.4 → [1.5.0](https://modrinth.com/version/CFrrGcF0) | 1.5.0 / 1.4.4 | 소스 준비/공개팩 갱신 후보 — 책상의자·스타일·오븐·목재·모델 등 변경; 공개팩은1.4.4 |
| PTS Deco | 2.1.0 → [4.0.0](https://modrinth.com/version/etl5lvBR) | 2.1.0 / 2.1.0 | 새 정식판 — 대규모 장식 확장/재작성; 기존 블록 ID 이전 검증 필요 |
| Puzzles Lib | 20.4.52 → [20.4.53](https://modrinth.com/version/PYkg1A3a) | 20.4.53 / 20.4.52 | 소스 준비/공개팩 갱신 후보 — SlotWrapper 접근 허용; 소스 준비/공개팩은20.4.52 |
| Rechiseled | 1.2.1 → [1.2.5](https://modrinth.com/version/H4YTGQ1N) | 1.2.1 / 1.2.1 | 새 정식판 — 스택 초과·저장·JEI·텍스처 수정; Loader≥0.18.0 |
| SuperMartijn642 Core Lib | 1.1.20 → [1.1.24](https://modrinth.com/version/3bdJYmjw) | 1.1.20 / 1.1.20 | 새 정식판 — 블록 동기화·상호작용·등록 성능·GUI 수정 |
| WorldEdit Hang Fix | 1.0.2 → [1.0.5](https://modrinth.com/version/CcLdaS7o) | 1.0.2 / 1.0.2 | 새 정식판 — 종료 감시 스레드 수정; WE7.3.0에서는 낮은 우선 |

Fabric API는 빌드·공개팩 모두 이미 최신이다. Paladin’s Furniture와 Puzzles Lib는 소스가 최신이지만 공개팩은 예전 공식 JAR를 선택한다. Modern Lights 역시 소스 2.5.0/공개팩 2.4.2이며, Modrinth의 2.5.0 파일은 실행 진입점 클래스·중첩 JAR 없이 Java 소스 24개만 들어 있고 버전이 미치환된 `sources.jar`이므로 실행용 교체 대상으로 사용하면 안 된다.

## 정식 JAR 이외의 업데이트 후보

| 모드 | 후보 | 변화·판단 |
| --- | --- | --- |
| Minecraft Transit Railway (MTR) | `4.0.6` / [240524a1](https://github.com/Minecraft-Transit-Railway/Minecraft-Transit-Railway/commit/240524a18d59edeb75cf8040cb209b91b428b5d7) | 4.0.5 (4.0.6 개발 브랜치): MQO 변환·BVE 음원·차량 보간 수정, 문 막아 열어두기 일시 비활성화 |
| Wireless Redstone | `1.20.4` / [90957d56](https://github.com/Razzokk/wireless-redstone/commit/90957d561c3922fde76935614b4ab609c62777c9) | 1.3.0 Unreleased: 부착형 송수신기, 즉시 신호 반영, P2P·리모컨·표시 수정, NBT 저장 형식 변경 |
| Patchouli | `1.20.4` / [b9173fb4](https://github.com/VazkiiMods/Patchouli/commit/b9173fb4654818bb606d41501f1a841acc5f8384) | 85 이후 미출시: 책/항목/페이지 열기에 따른 발전과제 트리거, 위키 링크 수정 |
| Mythic Metals | `1.20.4` / [38d245cd](https://github.com/Noaaan/MythicMetals/commit/38d245cdd3b8b81529d09a1b09b4dc2ef5588edc) | 0.19.7 이후 미출시: 운영자용 광석 위키 내보내기 명령과 출력 수정; 생성 규칙 변화 없음 |
| Yuushya Townscape | `master` / [4453f228](https://gitee.com/yuushyatownscape/yuushya-townscape/commit/4453f228d22d476f5228e367458ec75fda0f717b) | 2.3.0 소스, 1.20.4 미배포: 애드온 경로·Fusion 자원·제작법 수정, 포스터/구조물 확장; 1.20.4 빌드·실행 미검증 |
| Webstreamer | 관리 소스에 이미 반영 | 1.5.0+minefed.1: 실제 청크 표시 거리를 사용하는 화면 렌더링 수정; 운영 적용 확인 대상 |
| Minefed Display | 관리 소스에 이미 반영 | 1.0.0 유지: MCEF 선택적 로딩; 버전이 같아도 JAR/커밋으로 구별; 운영 적용 확인 대상 |

검토 우선순위는 다음과 같다. 이는 실행 검증을 통과했다는 의미가 아니라 변경 영향에 따른 조사 판단이다.

1. **MSD**를 현재 MTR 4.0.5 대상 빌드와 맞추는 검토. beta 채널과 Minefed MTR 패치를 함께 확인한다.
2. **Fusion + Rechiseled + Core Lib**를 묶어 검토. Fusion은 Fabric API 0.97.3 이상, Rechiseled는 Loader 0.18.0 이상이 필요하다. 현재 공개팩 설정은 이를 만족하지만 운영 서버의 실제 Loader는 별도 확인이 필요하다.
3. Axiom·Macaw 계열·CityCraft·Paladin’s Furniture·Puzzles Lib. CityCraft는 공식 로그가 비어 있어 JAR 자원 비교 결과와 기능 해석을 구분한다.
4. **PTS Deco**는 대규모 재작성으로 기존 블록 자원 경로가 많이 바뀌어 기존 건축물의 이전/호환 검증을 먼저 해야 한다. **Modern Lights**는 정상 실행용 산출물 확보가 선행되어야 한다.
5. 미출시 소스는 개별 선택 통합. Wireless Redstone은 NBT 저장 형식·롤백 조건, MTR는 차량/패킷 커스텀 수정과 문 동작을 검토한다. Patchouli·MythicMetals·현재 WE7.3.0에서의 Hang Fix는 필요성에 따라 낮은 우선순위다.

## 전체 68개 판정표

“호환판 유지”는 후속 1.20.4/Fabric 공식 배포가 확인되지 않았다는 뜻이다. 모든 개발 브랜치에 코드 변화가 없다는 뜻은 아니다. 다른 Minecraft/Forge/NeoForge 전용 최신판은 업데이트 수에 포함하지 않는다.

| # | 모드 | 운영 기준 | 최신 호환 공식판 | 판정 |
| ---: | --- | --- | --- | --- |
| 1 | Alloy Forgery | 2.1.4+1.20.3 | [2.1.4+1.20.3](https://modrinth.com/version/X1pKXaia) | 호환판 유지 |
| 2 | Architectury API | 11.1.17 | [11.1.17+fabric](https://modrinth.com/version/kVjQWX0l) | 호환판 유지 |
| 3 | Automobility Refueled | 0.4.3.b+1.20.4-fabric | 0.4.3.b+1.20.4 (prerelease) | 호환판 유지 |
| 4 | Axiom | 5.3.0 | [5.4.2](https://modrinth.com/version/yt1TxRll) | 새 정식판 |
| 5 | BlueMap | 5.3 | [5.3-fabric-1.20](https://modrinth.com/version/lHRktt6S) | 호환판 유지 |
| 6 | Botarium | 3.2.2 | [3.2.2](https://modrinth.com/version/Eqw90l8p) | 호환판 유지 |
| 7 | CC: Tweaked | 1.110.2 | [1.110.2](https://modrinth.com/version/afcOmjVN) (alpha) | 호환판 유지 |
| 8 | Chisels & Bits | 1.5.10-FC | 공식1.4.157 / Minefed1.5.10-FC 유지 | 호환판 유지 |
| 9 | Chunky | 1.3.146 | [1.3.146](https://modrinth.com/version/NHWYq9at) | 호환판 유지 |
| 10 | CityCraft | 2.0.0 | [2.1.1](https://modrinth.com/version/gRav2TDu) | 새 정식판 |
| 11 | CrossStitch | 0.1.6 | [0.1.6](https://modrinth.com/version/dJioNlO8) | 호환판 유지 |
| 12 | Decorative Blocks | 5.0.2 | [5.0.2+fabric](https://modrinth.com/version/txbqjIbZ) | 호환판 유지 |
| 13 | Diagonal Fences | 20.4.1 | [v20.4.1-1.20.4-Fabric](https://modrinth.com/version/vRnCnKBa) | 호환판 유지 |
| 14 | Diagonal Walls | 20.4.1 | [v20.4.1-1.20.4-Fabric](https://modrinth.com/version/lfD849Zm) | 호환판 유지 |
| 15 | Diagonal Windows | 20.4.1 | [v20.4.1-1.20.4-Fabric](https://modrinth.com/version/1p2S1mYf) | 호환판 유지 |
| 16 | Dusty Decorations Refabricated | 1.1-1.20.3+1.20.4 | [1.1](https://modrinth.com/version/DHsgxScD) | 호환판 유지 |
| 17 | Exline Furniture | 2.7.2 | [2.7.2](https://modrinth.com/version/DfuDGYlp) | 호환판 유지 |
| 18 | Fabric API | 0.97.2+1.20.4 | [0.97.3+1.20.4](https://modrinth.com/version/BPX6fK06) | 공개팩 반영됨 |
| 19 | Carpet | 1.4.128+v231205 | [1.4.128](https://modrinth.com/version/yYzR60Xd) | 호환판 유지 |
| 20 | Fabric Seasons | 2.4.2-BETA+1.20.4 | [2.4.2-BETA+1.20.4](https://modrinth.com/version/kSoN9Hi9) (beta) | 호환판 유지 |
| 21 | FabricProxy-Lite | 2.7.0 | [v2.7.0](https://modrinth.com/version/Mxw3Cbsk) | 호환판 유지 |
| 22 | FallingTree | 1.20.4.3 | [1.20.4-1.20.4.3](https://modrinth.com/version/mb15RrXi) | 호환판 유지 |
| 23 | FerriteCore | 6.0.3 | [6.0.3-fabric](https://modrinth.com/version/pguEMpy9) | 호환판 유지 |
| 24 | Forge Config API Port | 20.4.3 | [v20.4.3-1.20.4-Fabric](https://modrinth.com/version/xbVGsTLe) | 호환판 유지 |
| 25 | Furniture Expanded | 1.1-1.20.4 | [1.1-1.20.4](https://modrinth.com/version/LJGCDWzS) (beta) | 호환판 유지 |
| 26 | Fusion | 1.2.12 | [1.3.15a-fabric-mc1.20.4](https://modrinth.com/version/Qyr4qxvT) | 새 정식판 |
| 27 | GeckoLib | 4.4.4 | [4.4.4](https://modrinth.com/version/9xn1SoTo) | 호환판 유지 |
| 28 | Handcrafted | 3.2.1 | [3.2.1](https://modrinth.com/version/K4jSQsxb) | 호환판 유지 |
| 29 | Japan Props | 0.0.3.3 | [0.0.3.3](https://modrinth.com/version/hnS8fdTL) | 호환판 유지 |
| 30 | Lavender | 0.1.9+1.20.3 | [0.1.9+1.20.3](https://modrinth.com/version/7T1hNPCw) | 호환판 유지 |
| 31 | Lithium | 0.12.1 | [mc1.20.4-0.12.1](https://modrinth.com/version/nMhjKWVE) | 호환판 유지 |
| 32 | Macaw’s Doors | 1.1.2 | [1.1.5](https://modrinth.com/version/8l41DNKc) | 새 정식판 |
| 33 | Macaw’s Fences & Walls | 1.2.0 | [1.2.1](https://modrinth.com/version/UjYIrEaO) | 새 정식판 |
| 34 | Macaw’s Roofs | 2.3.2 | [2.3.2](https://modrinth.com/version/rHJugAn6) | 호환판 유지 |
| 35 | Macaw’s Windows | 2.3.1 | [2.4.2](https://modrinth.com/version/DbNK4q5P) | 새 정식판 |
| 36 | MemoryLeakFix | 1.1.5 | [v1.1.5](https://modrinth.com/version/5xvCCRjJ) | 호환판 유지 |
| 37 | Minefed Display | 1.0.0 | 자체1.0.0 | 준비된 Minefed 수정 |
| 38 | Mishang Urban Construction | 1.5.3 | [1.5.3-1.20.4](https://modrinth.com/version/558v19j3) | 호환판 유지 |
| 39 | Modern Glass Doors | 5.3.0+1.20.3-and-later | [5.3.0+1.20.3-and-later](https://modrinth.com/version/8LNbqvAF) | 호환판 유지 |
| 40 | Modern Lights | 2.4.2 | [2.5.0](https://modrinth.com/version/chMskrKw) | 보류: 소스 JAR |
| 41 | ModernFix | 5.17.0+mc1.20.4 | [5.17.0+mc1.20.4](https://modrinth.com/version/CV2Vtn5m) | 호환판 유지 |
| 42 | MTR Station Decoration Addon (MSD) | 1.3.15 | [4.0.5-1.4.5](https://modrinth.com/version/nMixopsa) (beta) | 새 beta |
| 43 | Minecraft Transit Railway (MTR) | 4.0.5 | [FABRIC-4.0.5+1.20.4](https://modrinth.com/version/Xurz5xWy) | 공식판 유지/미출시 소스 후보 |
| 44 | Mythic Metals | 0.19.7+1.20.4 | [0.19.7+1.20.4](https://modrinth.com/version/SKfkZKbj) (beta) | 공식판 유지/미출시 소스 후보 |
| 45 | Mythic Metals Decorations | 0.6.1+1.20.3 | [0.6.1+1.20.3](https://modrinth.com/version/L97C9D39) (beta) | 호환판 유지 |
| 46 | NiceMod | 1.4.1 - 1.20 | [1.4.1](https://modrinth.com/version/2dlfm8yY) | 호환판 유지 |
| 47 | Oritech | 0.5.1+1.20.4 | [0.5.1+1.20.4](https://modrinth.com/version/Fz5w3V0S) (beta) | 호환판 유지 |
| 48 | owo-lib | 0.12.6+1.20.3 | [0.12.6+1.20.3](https://modrinth.com/version/Her7Z3CG) | 호환판 유지 |
| 49 | Paladin’s Furniture | 1.4.4 | [1.20.4-v1.5.0-fabric](https://modrinth.com/version/CFrrGcF0) | 소스 준비/공개팩 갱신 후보 |
| 50 | Patchouli | 1.20.4-85-FABRIC | [1.20.4-85-fabric](https://modrinth.com/version/RRjoMz5N) | 공식판 유지/미출시 소스 후보 |
| 51 | PTS Deco | 2.1.0 | [4.0.0-fabric1.20.4](https://modrinth.com/version/etl5lvBR) | 새 정식판 |
| 52 | Puzzles Lib | 20.4.52 | [v20.4.53-1.20.4-Fabric](https://modrinth.com/version/PYkg1A3a) | 소스 준비/공개팩 갱신 후보 |
| 53 | Realtime | 1.0.3-1.20-1.21.1 | [1.0.3-1.20-1.21.1](https://modrinth.com/version/3JUK9zwP) | 호환판 유지 |
| 54 | Rechiseled | 1.2.1 | [1.2.5-fabric-mc1.20.4](https://modrinth.com/version/H4YTGQ1N) | 새 정식판 |
| 55 | Resourceful Config | 2.4.8 | [2.4.8](https://modrinth.com/version/1yfzKLu6) | 호환판 유지 |
| 56 | ResourcefulLib | 2.4.10 | [2.4.10](https://modrinth.com/version/TiIWVg2u) | 호환판 유지 |
| 57 | Starlight | 1.1.3+fabric.f5dcd1a | [1.1.3+1.20.4](https://modrinth.com/version/HZYU0kdg) | 호환판 유지 |
| 58 | Stoneworks | 20.4.0 | [v20.4.0-1.20.4-Fabric](https://modrinth.com/version/iaCtNo4p) | 호환판 유지 |
| 59 | SuperMartijn642 Config Lib | 1.1.8+a | [1.1.8a-fabric-mc1.20.2](https://modrinth.com/version/cp6X3Hrn) | 호환판 유지 |
| 60 | SuperMartijn642 Core Lib | 1.1.20 | [1.1.24-fabric-mc1.20.4](https://modrinth.com/version/3bdJYmjw) | 새 정식판 |
| 61 | TimeOutOut | 1.0.4+1.20.2 | [1.0.4](https://modrinth.com/version/VAYNN78f) | 호환판 유지 |
| 62 | TrafficCraft | 1.20.4-1.1.3 | [1.20.4-1.1.3](https://modrinth.com/version/rzrY1Buf) | 호환판 유지 |
| 63 | Webstreamer | 1.5.0 | [1.5.0](https://modrinth.com/version/ondpQ8lg) | 준비된 Minefed 수정 |
| 64 | Wireless Redstone | 1.2.2+1.20.4 | [1.2.2+1.20.4-fabric](https://modrinth.com/version/fgUwUN3e) | 공식판 유지/미출시 소스 후보 |
| 65 | WorldEdit Hang Fix | 1.0.2 | [v1.0.5-mc1.18.2-fabric](https://modrinth.com/version/CcLdaS7o) | 새 정식판 |
| 66 | WorldEdit | 7.3.0+6678-55745ad | [7.3.0](https://modrinth.com/version/ZOhVauWn) | 호환판 유지 |
| 67 | Yuushya Townscape | 2.2.3 | [2.2.3](https://modrinth.com/version/g5TBlA52) | 공식판 유지/미출시 소스 후보 |
| 68 | Yuushya Modelling | 2.2.0 | [2.2.0](https://modrinth.com/version/FQMpG8yv) | 호환판 유지 |

별도 보관: `MTR-fabric-4.0.3+1.20.4.jar`는 4.0.5와 modId 중복으로 제외, `TCPShield-2.8.1.jar`는 Bukkit/Bungee/Velocity 플러그인이므로 Fabric 팩에서 제외한다. 리소스팩은 JAR 모드 목록에 포함하지 않았다.

## 변경사항 상세

공식 릴리즈 노트의 누적 목록에서 **현재 버전 이하의 기존 변경은 제외**했다. 로그가 없는 모드는 누락을 감추지 않고 JAR 자원 비교로 확인한 사실과 미확인 동작을 표시한다. 자체 패치 모드는 운영 JAR의 해시·클래스를 확인해 이미 들어간 성능 최적화를 신규 변경으로 중복 계산하지 않았다.

## 기반 라이브러리·편집 도구

### Axiom — 5.3.0 → 5.4.2

1.20.3–1.20.4/Fabric용 정식판이다. 현재 Minefed 바이너리/공개팩 선택은 5.3.0이다.

- **5.4.1:** Blend Tool, 블록 업데이트와 틱 실행 작업, 조명·데이터 복구 작업 추가. Noise Painter에서 블록 색상을 표시하고 Lua 편집기를 개선했다. Veil/Sable/Create Aeronautics 호환 및 기타 수정도 포함한다. [5.4.1](https://modrinth.com/mod/axiom/version/xuCzf89f)
- **5.4.2:** Sinytra Connector 환경 충돌, macOS Ctrl/Cmd 뒤바뀜, 높이맵 선택 불가, 달리기 키가 미지정일 때 충돌, 블루프린트·클립보드 미리보기, 일부 도구의 블록 회전을 수정했다. 매끄러운 돌의 Type Replace 변형을 추가했다. [5.4.2](https://modrinth.com/mod/axiom/version/yt1TxRll)

실제 JAR 요구사항은 Java 17+, Fabric Loader 0.14.21+, Fabric API다. Sodium ≤0.5.0, OptiFabric 전체, Immersive Portals ≤6.0.6과의 충돌 선언이 있다. 현재 관리 목록에 이 세 모드는 없지만 별도 클라이언트 구성을 사용할 때 확인해야 한다.

### Fusion — 1.2.12 → 1.3.15a

표시 버전은 1.3.15a, 실제 JAR 메타데이터는 `1.3.15+a`다. 1.3.0과 1.3.1은 beta, 1.3.2 이후는 정식판이다. 아래는 현재 버전 다음의 **호환 배포 18개**를 모두 거친 누적 변화다. 이번 구간에는 모델·텍스처 체계 개편이 있으므로 Minefed 리소스팩, Rechiseled, ModernFix와 함께 검토할 가치가 크다.

| 버전 | 현재 버전 이후 변경사항 |
| --- | --- |
| [1.3.0 beta](https://modrinth.com/mod/fusion-connected-textures/version/x8SHDneK) | 모델/텍스처 로딩 개편. Fusion 부모·텍스처를 사용하는 모델도 Fusion 모델로 처리. 모델·요소·면의 발광/음영/AO 및 GUI 조명 설정, 모델 modifier 우선순위·누락 대상 무시·기본 모델 변경·조건부 모델 추가, 파괴 오버레이 개별 설정. 블록 조건식(논리·주변 블록/상태·바이옴·차원·고도), 아이템 조건식(논리·수량·내구도·인챈트·이름/정규식·포션), 조건부 합성/이동/확대/회전 모델 추가. 텍스처의 다중 스프라이트·하위 텍스처·범용 quad 처리, base/connecting 모델 제약 완화. connecting/random 타일별 스프라이트·투명 타일 제외·하위 텍스처·타일별 애니메이션, 연결 기본 조건·누락 무시·다중 블록 매칭. random의 위치/방향/축 난수 선택·격자 상한 100, continuous 상한 32, scrolling wrap 지원. 오류 표시 개선. legacy square 연결, modifier 난수/geometry key/순서, 생성 아이템 모델, pane culling 동시성, item transform 직렬화, 회전 원점 비율, cuboid 속성 직렬화, 회전한 continuous와 텍스처 가장자리 선을 수정. 1.12 mipmap·1.20.1/1.21.1 FramedBlocks 수정도 로그에 있으나 Minefed 대상 환경 밖이다. |
| [1.3.1 beta](https://modrinth.com/mod/fusion-connected-textures/version/Nod3UcOc) | overlay 연결 모델의 과도한 quad, connections 속성 무시, connecting/random 기본 속성, base 기하 중복, ModernFix 동적 리소스 사용 시 텍스처, Quick Pack 충돌 수정. builder 이름 정리, cuboid material 재귀호출, material 참조 직렬화 수정. |
| [1.3.2](https://modrinth.com/mod/fusion-connected-textures/version/LxLhwazp) | 잘못된 mixin 충돌과 reference map 경고 수정, Mod Menu의 library 태그 제거. |
| [1.3.2a](https://modrinth.com/mod/fusion-connected-textures/version/2Adll4Td) | 다른 모드가 일반 처리 구간 밖에서 모델을 bake할 때 발생하는 충돌 수정. |
| [1.3.3](https://modrinth.com/mod/fusion-connected-textures/version/mWKCkDfS) | 블록 dimension/match_block/match_state와 엔티티 dimension 조건의 역직렬화 수정. |
| [1.3.4](https://modrinth.com/mod/fusion-connected-textures/version/Rk2JfHsf) | 블록 조건식의 스레드 충돌·오판정, 면 UV 속성 무시 수정. |
| [1.3.5](https://modrinth.com/mod/fusion-connected-textures/version/YeJJCOBg) | 합성 모델 회전에 방향 조건식을 맞추고 블록 범위 밖 요소의 기본 UV 계산 개선. display 역직렬화, 다중 블록 조건의 마지막 항목만 적용되는 문제, 합성 변환 원점·적용 순서, Sodium 애니메이션 보간 문제 수정. |
| [1.3.6](https://modrinth.com/mod/fusion-connected-textures/version/EYMsQ2DU) | 모델 random_offset 속성, 난수 품질 개선, 모델 메모리 감소. 아이템 변환, match_state_in_front, 애니메이션 프레임 UV, 반투명 아이템, cuboid 상속 처리, 회전 조건식 부동소수점 오차, 아이템과 같은 ID의 부모 모델 로드 수정. |
| [1.3.7](https://modrinth.com/mod/fusion-connected-textures/version/PNQ5YK4I) | model modifier 대상 블록 파괴 시 Mixin 관련 충돌 수정. |
| [1.3.8](https://modrinth.com/mod/fusion-connected-textures/version/sOKJ0W8D) | continuous를 하위 텍스처로 사용할 때 충돌 수정. |
| [1.3.9](https://modrinth.com/mod/fusion-connected-textures/version/IoNuNiNE) | 청크 기하에서 dimension 모델 조건이 작동하지 않는 문제 수정. |
| [1.3.10](https://modrinth.com/mod/fusion-connected-textures/version/WdPRHaod) | Fabulous 반투명 아이템 누락, display 이동값의 1/16 배율, ModernFix dynamic_resources와 모델 로드 문제 수정. |
| [1.3.11](https://modrinth.com/mod/fusion-connected-textures/version/XIiBjr08) | quad 방향·렌더 유형을 비트로 저장하고 연결 조건/빈 타일 저장·초기화를 최적화하여 모델 메모리를 줄였다. |
| [1.3.12](https://modrinth.com/mod/fusion-connected-textures/version/eF4qjBVD) | MutableQuad 청크 렌더 계층의 플래그 덮어쓰기 수정. |
| [1.3.13](https://modrinth.com/mod/fusion-connected-textures/version/rFemxlRZ) | 텍스처 렌더 유형 API, Iris 노멀/스페큘러 텍스처 연동. 빈 기하 모델, random 하위 텍스처 데이터, 아이템의 is_face_visible 조건 충돌, pane culling의 월드 문맥, Sodium 보간 클래스 간섭 수정. |
| [1.3.14](https://modrinth.com/mod/fusion-connected-textures/version/YogGsy8Z) | BLOCK_ENTITY_MARKER 추가, builtin/entity 부모 모델의 커스텀 렌더러 표시와 ITEM_MODEL_GENERATOR 등록 수정. 빈 타일을 가진 Iris PBR 텍스처의 스프라이트 수 차이로 발생하는 충돌 수정. |
| [1.3.15](https://modrinth.com/mod/fusion-connected-textures/version/tkrN3XHN) | 하위 텍스처에서 AO/음영/발광 속성 적용 누락, 청크 기하의 is_biome 조건 오판정 수정. |
| [1.3.15a](https://modrinth.com/mod/fusion-connected-textures/version/Qyr4qxvT) | 비순차 프레임 목록을 사용하는 애니메이션 텍스처의 프레임 인덱스 수정. |

**의존성:** 실제 1.3.15a JAR는 Fabric API ≥0.97.3과 Loader ≥0.16.1, Java ≥17을 요구한다. 운영 기준 Fabric API 0.97.2와 함께 교체하면 요구사항을 만족하지 못한다. 현재 빌드/공개팩의 Fabric API 0.97.3 및 Loader 0.18.0 설정은 이 최소 요구를 만족한다.

### Rechiseled — 1.2.1 → 1.2.5

- **[1.2.2](https://modrinth.com/mod/rechiseled/version/U3Ps6sOM):** 끌에서 최대 수량을 초과한 아이템 스택을 얻을 수 있는 문제 수정.
- **[1.2.3](https://modrinth.com/mod/rechiseled/version/wzoRcWAy):** JEI 빠른 제작 버튼과 Edged Block of Amethyst의 연결 텍스처 수정.
- **[1.2.4](https://modrinth.com/mod/rechiseled/version/lJHnOFsP):** Shift 클릭 시 끌 슬롯 갱신, 128개 이상 스택의 저장 오류 수정.
- **[1.2.5](https://modrinth.com/mod/rechiseled/version/H4YTGQ1N):** Fusion 1.3.0에서 비연결 블록까지 연결되는 문제와 Compacted Coal Block 텍스처 수정.

계단·반블록 및 UI 대개편은 1.2.0에서 이미 들어온 내용이므로 이번 업데이트의 신규 기능으로 계산하지 않는다. 실제 JAR는 **Loader ≥0.18.0**, Core Lib ≥1.1.20,<1.2.0, Config Lib ≥1.1.6, Fusion ≥1.2.12, Java ≥17을 요구한다. 현재 공개팩 Loader 설정과 라이브러리 버전이 최소 요구를 만족한다. Fusion 1.3.x 교체 시 Rechiseled 1.2.5를 함께 올리는 것이 맞다.

### SuperMartijn642's Core Lib — 1.1.20 → 1.1.24

- **[1.1.21](https://modrinth.com/mod/supermartijn642s-core-lib/version/fhclxR7O):** 블록 엔티티의 클라이언트 데이터가 빈 태그일 때 동기화되지 않는 문제 수정. 이후 누적 변경 기록에는 자체 datagen 진입점과 `GeneratorRegistrationHandler`를 사용하는 모드에서 데이터 생성이 실패하는 문제 수정도 이 버전의 변경으로 추가되어 있다. [보강된 누적 기록](https://modrinth.com/mod/supermartijn642s-core-lib/version/3bdJYmjw)
- **[1.1.22](https://modrinth.com/mod/supermartijn642s-core-lib/version/dtdj5PxE):** 상호작용 PASS 반환값, shape 좌표의 정수/실수 타입, 블록 설치 실패 반환값 수정.
- **[1.1.23](https://modrinth.com/mod/supermartijn642s-core-lib/version/fZ5w6Obm):** 위젯 조회 API 추가, multipart 블록 상태 조건 펼침 수정.
- **[1.1.23a](https://modrinth.com/mod/supermartijn642s-core-lib/version/8QeJGnR0):** 모드가 많을 때 크리에이티브 그룹 아이템 등록이 매우 느려지는 문제 수정.
- **[1.1.23b](https://modrinth.com/mod/supermartijn642s-core-lib/version/iA0bwDn4):** ImmediatelyFast와 GUI 렌더링 호환 수정.
- **[1.1.24](https://modrinth.com/mod/supermartijn642s-core-lib/version/3bdJYmjw):** 커스텀 슬롯의 마우스 판정 영역이 2픽셀 큰 문제 수정.

1.1.24a라는 다른 Minecraft용 버전과 혼동하지 않는다. 1.20.4/Fabric 최신은 1.1.24다. Config Lib 1.1.8a는 별개이며 이번 환경의 새 배포판이 없다.

### Fabric API — 운영 0.97.2 → 0.97.3, 빌드·공개팩은 이미 반영

변경사항은 **인챈트 테이블에서 잘못된 인챈트가 적용되는 문제 수정(#4714)** 하나다. [공식 0.97.3](https://modrinth.com/mod/fabric-api/version/BPX6fK06)

`dependencies.lock.json`과 `release-policy.json`은 이미 0.97.3을 선택한다. 운영 기준본은 관측 기록인 0.97.2로 유지되어 있으므로, 소스/빌드 입력을 새로 업그레이드할 작업으로 중복 계산하면 안 된다. 운영 서버에 적용됐는지는 이 저장소만으로 확인할 수 없다.

### Puzzles Lib — 운영 20.4.52 → 20.4.53, 소스 빌드는 이미 반영

**CreativeModeInventoryScreen$SlotWrapper에 대한 access widener 추가**가 이 구간의 변경사항이다. 20.4.52 이하 수정은 이미 사용 중인 버전에 포함되어 있으므로 제외한다. [공식 20.4.53](https://modrinth.com/mod/puzzles-lib/version/PYkg1A3a)

현재 소스/recipe는 20.4.53이다. 공개팩 정책은 공식 **20.4.52 원본 다운로드**를 선택한다. 따라서 남은 일은 원격 소스 재업데이트가 아니라 공식 배포 참조를 20.4.53으로 변경하는 검토다. upstream `1.20.4` HEAD `dff8529b28db23e197c34f47792839ae305571e5`는 현 관리 소스의 기반 커밋과 같아 추가 소스 차이가 없다.

필수 의존성은 Fabric API ≥0.96.0과 Forge Config API Port이며 현재 선택한 0.97.3/20.4.3으로 충족한다.

### Patchouli — 정식 85 유지, 미출시 소스 기능 1건

1.20.4/Fabric 최신 정식 JAR는 여전히 `1.20.4-85-FABRIC`이다. 다만 공식 `1.20.4` 브랜치에는 릴리즈 이후 커밋 2개가 있고 현재 Minefed HEAD에 포함되지 않았다.

| 종류 | 현재 기준 → 대상 | 변경사항 |
| --- | --- | --- |
| 기능 | `4522fbb3e42b5a31688c7c7666cf13c12c0fdb83` → `9405a11e66824d33a5d61797db108881d013e27e` | `patchouli:open_book` 발전과제 트리거. 책 ID, 선택적 항목 ID, 페이지 범위, 플레이어 조건으로 책 열기 동작을 판정하도록 API에 연결. [커밋](https://github.com/VazkiiMods/Patchouli/commit/9405a11e66824d33a5d61797db108881d013e27e) |
| 문서 | → 브랜치 HEAD `b9173fb4654818bb606d41501f1a841acc5f8384` | 위키 Discord 초대 링크 수정. 런타임 기능 변화 없음. [커밋](https://github.com/VazkiiMods/Patchouli/commit/b9173fb4654818bb606d41501f1a841acc5f8384) |

Minefed 관리 브랜치는 `minefed-1.20.4`, 현재 pin은 `5bb9e96cd8256c0bcd2fa87eff2d65be0a7290d5`다. 공식 완성 JAR 교체 후보가 아니라 기능이 필요할 때 선택적으로 병합·빌드할 후보이며, 이번 조사에서는 실행 효과를 검증하지 않았다.


## 장식·건축 모드

기준은 `inventory/mods.lock.json`의 운영 JAR 버전이며 Minecraft 1.20.4/Fabric 유지 조건이다. 24종 중 공식 호환 후속판은 7종이다. 그중 Modern Lights는 공개 파일이 실행용 JAR가 아닌 소스 JAR여서 바로 교체할 수 없는 조건부 대상으로 분리한다. 나머지 17종은 같은 환경에서 더 새로운 공개 실행판을 찾지 못했다. 이 17종 중 **Yuushya Townscape는 1.20.4 빌드 대상이 남아 있는 2.3.0 upstream 소스 검토 후보**가 추가로 있다. 변경사항은 공식 릴리스 기록 전체를 누적하되, 운영에 이미 포함된 이전 버전 변경과 Forge/다른 Minecraft 버전 전용 수정을 구별했다.

### 호환 업데이트 대상

| 모드 ID | 운영 버전 | 최신 1.20.4/Fabric | 공개일 | 판정 |
|---|---|---|---|---|
| citycraft | 2.0.0 | [2.1.1](https://modrinth.com/mod/citycraft/version/gRav2TDu) | 2025-08-09 | 실행 JAR 후보; 공식 변경로그 공란을 실제 JAR 자원 비교로 보강 |
| mcwdoors | 1.1.2 | [1.1.5](https://modrinth.com/mod/macaws-doors/version/8l41DNKc) | 2026-02-13 | 실행 JAR 후보; 기존 차고문·낙하문 동작 변경 확인 필요 |
| mcwfences | 1.2.0 | [1.2.1](https://modrinth.com/version/UjYIrEaO) | 2025-12-08 | 실행 JAR 후보; 운영 Diagonal Fences와의 연결 수정 포함 |
| mcwwindows | 2.3.1 | [2.4.2](https://modrinth.com/version/DbNK4q5P) | 2025-12-10 | 실행 JAR 후보; 창·커튼·셔터 동작/렌더링 개선 |
| modernlights | 2.4.2 | [2.5.0](https://modrinth.com/mod/modern-lights/version/chMskrKw) | 2025-06-17 | 조건부: 공개 1.20–1.20.4 파일은 sources.jar, .class 0개. 현재 관리 소스로 빌드하는 경로 필요 |
| pfm | 1.4.4 | [1.5.0](https://modrinth.com/version/CFrrGcF0) | 2026-08-10 | 실행 JAR 후보; 관리 소스·빌드 예상 버전은 이미 1.5.0 |
| ptsdeco | 2.1.0 | [4.0.0](https://modrinth.com/mod/pts-deco/version/etl5lvBR) | 2025-11-09 | 실행 JAR 후보; 대규모 재작성으로 기존 블록 보존 검증 우선 |

#### City Craft: 2.0.0 → 2.1.0 → 2.1.1

이 모드는 XiaoYao-MC의 Fabric 모드 NCASj2oY이다. RexRaptor의 동명 Forge/NeoForge 모드는 별개이므로 그 변경기록을 사용하지 않았다. [2.1.0](https://modrinth.com/mod/citycraft/version/WcmDIbmS)과 [2.1.1](https://modrinth.com/mod/citycraft/version/gRav2TDu)은 모두 공식 변경로그가 비어 있다. 공식 GitHub도 릴리스 목록이 없고, 관리 소스는 운영 2.0.0과 동일한 소스가 아니다.

따라서 아래는 **공식 SHA-512와 일치하는 운영/후속 JAR의 파일·번역·레시피 JSON을 비교한 확인 결과**다. 추가 자원은 식별할 수 있지만, 변경된 실행 코드의 모든 행동·버그수정까지 단정하지 않았다. 비교 원문은 `citycraft-resource-diff.json`에 있다.

**2.1.0 (2025-02-22):**

- 파란 고가도로 가드레일, 높이 제한 표지 3종, 회전교차로·보행자 통행금지 표지 추가.
- 어린이·보행자·횡단보도·공사·터널·노면 불량·철도 건널목·사거리·좌/우 측면 교차로·T/Y 교차로·양측/좌측/우측 도로 좁아짐 경고 표지 자원 추가.
- 선불카드, 카드 충전기, 계산대, 계산대 관리 도구 및 거래용 크리에이티브 탭 자원/클래스 추가. 카드 잔액, 충전·이체·결제, 잔액 부족, 결제액 설정을 위한 번역키도 추가됐다. 충전기는 중국어 원문상 전기차 충전소가 아닌 카드 잔액 충전기다.
- 파란색·초록색·빨간색 아스팔트 염색 레시피 산출량이 각각 8개→1개로 변경됐다. 시멘트 레시피의 잘못된 아스팔트 산출물을 시멘트로 수정했다. Amazing Block 레시피의 검은 염료를 흰 염료로 변경했다. 파란 가드레일 레시피 추가.
- 흰색/노란색 대각선 노면표시 모델·텍스처와 가드레일·노면표시 공용 모델 변경. 신호등 3종 이름에서 문제 있음 표시가 제거됐고 관련 클래스가 변경됐으나 구체적인 버그 해결 범위는 미공개다.
- 곡괭이 채굴/석재 도구 태그 수정. 기존 물품 탭 번역키 제거 및 거래 탭 번역키 추가. ZIP 항목 기준 158개 추가·2개 제거·32개 변경; 제거 항목은 CC0 예제 라이선스 파일과 ImplementedInventory 클래스다. 이 숫자는 게임 블록 개수가 아니다.

**2.1.1 (2025-08-09):**

- 일반 상품 매대, 긴 상품 매대, 냉동고의 블록상태·모델·텍스처·번역키·클래스 추가.
- Amazing Block 중국어 설명 문구 수정, 채굴 태그 갱신. 계산대·모드 등록·명령 클래스 변경은 확인되지만 구체적인 기능/버그수정 설명은 미공개다.
- ZIP 항목 26개 추가·제거 0개·8개 변경. 2.0.0 대비 누적 184개 추가·2개 제거·32개 변경이다.

한계: 공식 변경로그가 없으므로 이 결과를 모든 실행 동작 변경의 완전한 목록으로 표현하면 안 된다. 상위 source pin의 1.19.4/1.0.0 계열 소스와 신규 Fabric 바이너리를 같은 구현으로 취급하지 않는다.

#### Macaw's Doors: 1.1.2 → 1.1.5

공식 [누적 변경로그](https://github.com/sketchmacaw/MacawsModsIssues/blob/master/changelogs/doors.txt)에서 1.1.2 이후 항목을 확인했다. 1.20.4에서 1.1.5가 두 번 등록됐으나 릴리스 8l41DNKc와 lcEJY9Hl의 파일명·SHA-512가 같아 한 업데이트로 계산한다.

- 차고문과 낙하문(Portcullis)을 위쪽 한 줄만 놓으면 닫을 때 아래의 고체 블록까지 내려오도록 변경했다. 기존처럼 전체 높이를 블록으로 채울 필요가 없다. 열린 문의 불필요한 충돌/선택 영역을 줄여 몹 길찾기 문제를 해결한다.
- 위쪽 열린 상태 모델 변경, 설명 툴팁 추가, 차고문 블록상태 수 축소. 닫았을 때 빈칸이 생기면 해당 칸에 임시 블록을 놓았다가 제거하라는 제작자 안내가 있다.
- 맹그로브 Whispering 문이 GUI에서 빠진 문제, 쇼지/감옥문/차고문 소리의 거리 감쇠, 주민이 쇼지문을 열 때 잘못된 일반 문 소리가 나는 문제 수정.
- 열린 차고문/낙하문을 몹이 통과하지 못하는 문제, 차고문이 CC:Tweaked 터틀과 물 이동을 막는 문제, 차고문/낙하문에 파란색 블록이 보이는 문제 수정.
- 스페인어(멕시코)·프랑스어·일본어·포르투갈어(브라질) 추가, 스페인어(칠레/스페인)·한국어·러시아어·중국어(간체) 갱신.
- 누적 로그의 1.1.3은 1.21.3/1.21.4 Fabric 전용 연결 수정이고, 1.1.5의 배열 인덱스 예외는 Forge 전용이다. 이 둘을 1.20.4/Fabric 개선으로 계산하지 않았다. 1.1.4 항목은 공식 누적 로그에 없다.

#### Macaw's Fences and Walls: 1.2.0 → 1.2.1

[1.2.1 공식 변경기록](https://modrinth.com/version/UjYIrEaO):

- 잔디 덮인 담장에 `#diagonalfences:non_diagonal_fences` 태그 추가; Diagonal Fences 사용 시 형태가 잘못 보이는 문제 수정.
- 잔디 담장이 울타리문/금속 울타리에 붙을 때 텍스처가 누락되는 문제 수정.
- 석재·안산암 등 불연성 재료 난간문이 용암에 타는 문제 수정.
- 스페인어·일본어·중국어 간체/번체·포르투갈어(브라질) 추가, 프랑스어·한국어·러시아어 갱신.

#### Macaw's Windows: 2.3.1 → 2.4.0 → 2.4.2

[2.4.0](https://modrinth.com/version/Z8JXQH0h), [2.4.2](https://modrinth.com/version/DbNK4q5P), [공식 누적 로그](https://github.com/sketchmacaw/MacawsModsIssues/blob/master/changelogs/windows.txt)를 함께 확인했다.

**2.4.0 (2025-07-05):**

- 창문을 누를 때 열림 방향을 순환하던 동작을 마우스로 가리키는 좌/우 방향에 따라 여는 방식으로 변경.
- 커튼 충돌 제거. 블라인드를 놓으면 닫힌 상태 대신 열린 상태로 시작.
- 셔터에 창문 열기 소리 적용, 선택 영역을 실제 모델 크기에 맞춤. 손에 셔터를 들고 기존 셔터를 누르면 열고 닫지 않아 연속 설치가 쉬워짐.
- Four Pane/Half Pane 창틀 재료 역조합 허용, 창틀 재료의 조합법 그룹화. 모델 파일 이름 Golden→Gold, Metal→Iron으로 변경.
- 커튼이 유리판에 연결되는 문제, 철제 셔터가 너무 느리게 부서지거나 아이템을 떨어뜨리지 않는 문제, 같은 방향으로 연 셔터끼리 겹치는 문제 수정.
- 연결형/고딕 창문에서 망치 변경이 저장되지 않거나 망치가 예전처럼 작동하지 않는 문제, 일부 버전에서 셔터가 눌러도 움직이지 않는 문제 수정.
- 스페인어 3종·프랑스어·일본어·러시아어·터키어·한국어 번역 갱신.

**2.4.1 누적 수정:** 고체 블록에 붙인 커튼이 그 블록 면을 투명하게 보이게 하는 문제 수정. 1.20.4 별도 2.4.1 릴리스는 없으나 2.4.2까지의 공식 공통 변경 이력에 포함된다. 1.20.1 Fabric의 iron 모델 재명명 항목은 현 환경과 무관하다.

**2.4.2 (2025-12-10):** 창문/고딕 창문/블라인드 소리의 거리 감쇠, 커튼의 고르지 않은 조명 수정. 포르투갈어(브라질) 추가·러시아어 갱신. Pale Oak는 1.21.4 이상 전용, 2.3.2는 1.20.6/1.21 충돌 수정, Forge 태그/배열 오류는 Forge 전용이므로 현 환경 변경에서 제외한다.

#### Modern Lights: 운영 2.4.2 → 관리 소스 2.5.0

[2.5.0 변경기록](https://modrinth.com/mod/modern-lights/version/chMskrKw)과 [제작자 프로젝트 설명](https://modrinth.com/mod/modern-lights)을 합치면 다음과 같다.

- 작동하지 않던 레시피 및 발전과제 수정.
- Luminous Block 제작에 필요한 발광석 블록 4개→5개로 증가.
- 일반/수직 슬래브 2개로 대응 원블록 1개를 되돌리는 레시피 추가.
- 석재절단기로 슬래브 1개→미니 블록 4개 제작 추가.
- 모드 아이콘/로고 교체.

**배포상 제한:** Modrinth의 유일한 1.20–1.20.4 primary 파일은 `modern-lights-2.5.0+[1.20-1.20.4]-sources.jar`다. 실제 검사 결과 `.class` 0개, Java 소스 24개, 메타데이터 버전이 `${version}` 그대로여서 실행 모드로 설치할 수 없다. [동일 제작자의 CurseForge 파일 목록](https://www.curseforge.com/minecraft/mc-mods/modern-lights-mod/files/all?version=1.20.4)에도 2.4.2만 있어 대체 2.5.0 실행 JAR를 확인하지 못했다.

`inventory/build-recipes.json`은 이미 관리 소스의 `expectedVersion`을 2.5.0으로 기록한다. 업데이트 후보 자체는 유효하지만 공식 sources.jar를 운영 폴더에 넣는 방식은 사용할 수 없고, 관리 소스 빌드·호환 확인이 필요하다. 선언상 Java 17, Fabric Loader ≥0.16.14, Minecraft ≥1.20 ≤1.20.4. 운영 관측 버전 2.4.2와 혼동하지 않는다.

#### Paladin's Furniture: 운영 1.4.4 → 1.5.0

[1.5.0 공식 릴리스](https://modrinth.com/version/CFrrGcF0)의 누적 로그에서 **1.5 Changes and Fixes**만 운영 대비 신규다. 그 아래 다시 붙은 1.4.4/1.4.3/1.4.2/1.4 내용은 이미 현재 버전 범위다.

- 움직일 수 있는 책상 의자, 새로운 책상·의자 스타일 2종 추가.
- 오븐을 최대 9개 아이템 조리가 가능하도록 개선하고 기존 연료 효율 유지. 과도하게 채우면 음식이 타는 동작 추가.
- 헤링본 판자를 동적으로 생성해 다른 모드 목재에도 대응.
- 서버에서 작업대 검색 개선. 일부 램프 등 아이템의 중첩 문제, 여러 버전의 누락 레시피, 토스터 아이템이 보이지 않던 문제, CFBH 호환 문제 수정.
- 모델 개선, 냉동고 연료 균형 조정, 스페인어 추가 및 유니코드 문자 번역 문제 수정.
- Forge/NeoForge 블록 렌더링 충돌 및 Forge 냉장고 수정, 1.16.5 레시피/Fabric 충돌 수정, 1.21.5·1.21.6·1.21.8·1.21.10·1.21.11 포트도 공통 로그에 있으나 1.20.4/Fabric의 신규 기능으로 계산하지 않았다.

관리 소스와 빌드 예상 버전은 이미 1.5.0이며 운영 관측 JAR만 1.4.4다. 기존 LGPL 운영 바이너리의 대응 소스와 현재 자산 조건을 동일하다고 가정하지 않는다는 lock의 주의를 유지한다.

#### PTS-Deco: 2.1.0 → 3.0.3 → 3.0.3.5 → 3.0.5 → 4.0.0

기존 lock에는 배포처 매핑이 없었으나 공식 Modrinth 프로젝트 `VIkNIHtW`/`pts-deco`와 CurseForge `1178846`을 찾았다. CurseForge의 1.20.4/Fabric 전체 목록에 후속판 네 개가 있고, 그중 Modrinth에는 3.0.5와 4.0.0만 등록되어 있다.

- **[3.0.3, 2025-06-27](https://www.curseforge.com/minecraft/mc-mods/pts-deco/files/6702418):** v3를 1.20.4로 포트, 신규 장식 모델 추가, 모델 로딩 속도와 효율 개선. 제작자가 1.20.4 같은 보조 Minecraft 버전에는 초기 포트/버그수정 위주로 배포한다는 방침을 기록했다. 구체적인 신규 모델 이름 전체는 이 릴리스에 미기재.
- **[3.0.3.5, 2025-06-28](https://www.curseforge.com/minecraft/mc-mods/pts-deco/files/6705701):** 심각한 버그 수정이라고만 기록됨. 어떤 버그인지는 미공개.
- **[3.0.5, 2025-07-03](https://www.curseforge.com/minecraft/mc-mods/pts-deco/files/6725405):** Fabric 투명도 버그 수정. 함께 기재된 crafting ore 생성 문제는 NeoForge 전용이므로 제외. Modrinth의 2025-07-27 날짜는 기존 파일의 플랫폼 등록일이다.
- **[4.0.0, 2025-11-09](https://www.curseforge.com/minecraft/mc-mods/pts-deco/files/7204362):** 1.20.4 백포트. [v4 최초 공식 공통 릴리스](https://modrinth.com/mod/pts-deco/version/FIv9FEgM)는 다수 신규 모델 추가를 알리지만 모델별 명세가 없다. 실제 1.20.4 JAR 메타데이터는 전면 재작성, 새 모델·텍스처·기능 및 1,500개 이상 모델을 설명한다.

공통 개발 이력 참고로 [3.1.0](https://www.curseforge.com/minecraft/mc-mods/pts-deco/files/6818812)은 DecoMaker JEI 연계, 새 모델 로더, 불필요 코드 제거, 다수 레시피 조정과 332개 모델(다이너 원탁·동전·2층 침대·천장 팬·코너 소파·비치타월·노트북·배낭·서류더미·쓰레기통·태블릿·TV 선반·대나무 재질)을 명시했다. [3.2.0 Fabric](https://modrinth.com/mod/pts-deco/version/fabric1.20.1-3.2.0)은 이벤트·DecoMaker 화면/필터·화로처럼 작동하는 스토브·16색 풍선·금/은/동 주방 롤을, [3.2.1](https://modrinth.com/mod/pts-deco/version/5CSsY82o)은 Fabric 지원 모델 로더 교체와 새 모델을 기록했다. **이 공통 가지의 세부 기능 모두가 1.20.4 백포트에 들어간다는 별도 명세는 없으므로 이 목록은 배경 자료이며 확정된 1.20.4 기능 목록과 구분한다.**

**운영 영향:** 실제 2.1.0→4.0.0 JAR 비교에서 `assets/ptsdeco/blockstates/*.json`은 876개→1,882개, 기존 경로 505개 제거·신규 1,511개였다. 사라진 경로에는 `acacia_bed_*`, `acacia_bench`, `acacia_table` 등이 포함된다. 이는 파일명 변경/재구성일 수도 있어 곧바로 블록 손실을 뜻하지는 않지만, 기존 월드의 가구·침대·보관함과 레시피·DecoMaker 보존을 복제 환경에서 검증할 충분한 근거다. 차이 전체는 `ptsdeco-blockstate-diff.json` 참조.

후보 메타데이터: Fabric Loader ≥0.15.11, Fabric API ≥0.97.1+1.20.4, Java ≥17, Minecraft 정확히 1.20.4. 전체 최신 13.0은 26.2용이므로 현 환경 대상이 아니다. 운영 2.1.0의 공개 해시 매핑이 아직 없다는 기존 lock의 한계도 유지한다.

### 현 환경에서 후속판이 없는 17종

아래 현재 버전과 최신 호환 릴리스가 같은 경우 차이 없음이다. 플랫폼의 배포용 버전 문자열에 `v`, `fabric`, MC 접미사가 붙어도 동일 release ID이면 버전 상승으로 세지 않는다. 다른 MC 열은 후속 개발 상황만 보여주며 설치 후보가 아니다. 발행 순서상 가장 최근이 더 낮은 MC용인 경우도 있다.

| 모드 ID | 운영 = 최신 호환 버전 | 다른 MC 공개 현황/주의 | 확인 근거 |
|---|---|---|---|
| decorative_blocks | 5.0.2 | 최근 Fabric도 1.20.4/5.0.2 | [릴리스](https://modrinth.com/version/txbqjIbZ) |
| diagonalfences | 20.4.1 | 26.2용 26.2.0 있음 | [릴리스](https://modrinth.com/version/vRnCnKBa) |
| diagonalwalls | 20.4.1 | 26.2용 26.2.0 있음 | [릴리스](https://modrinth.com/version/lfD849Zm) |
| diagonalwindows | 20.4.1 | 26.2용 26.2.0 있음 | [릴리스](https://modrinth.com/version/1p2S1mYf) |
| dustydecorations | 1.1-1.20.3+1.20.4 | 1.21.2/1.21.3용도 버전 1.1 | [릴리스](https://modrinth.com/version/DHsgxScD) |
| exlinefurniture | 2.7.2 | 최근 Fabric 발행은 1.21용 1.0.7; 번호 체계가 달라 단순 다운그레이드 아님 | [릴리스](https://modrinth.com/version/DfuDGYlp) |
| furnitureexpanded | 1.1-1.20.4 **beta** | 현 호환 안정판 없음; 기존부터 실험판. 1.21.1용 1.2 있음 | [릴리스](https://modrinth.com/version/LJGCDWzS) |
| handcrafted | 3.2.1 | 1.21.1용 4.0.3 | [릴리스](https://modrinth.com/version/K4jSQsxb) |
| jpp | 0.0.3.3 | 원래 프로젝트가 1.20.4 호환 문제 가능성을 알려 1.20.1을 권장; 업데이트로 해결된 후속판 없음 | [릴리스](https://modrinth.com/version/hnS8fdTL) |
| mcwroofs | 2.3.2 | 26.2용도 버전 2.3.2 | [릴리스](https://modrinth.com/version/rHJugAn6) |
| mishanguc | 1.5.3 | 최근 Fabric 발행은 1.20/1.20.1용 1.6.5; 1.20.4용 아님 | [릴리스](https://modrinth.com/version/558v19j3) |
| modern_glass_doors | 5.3.0+1.20.3-and-later | 동일 호환판이 최근 공개판 | [릴리스](https://modrinth.com/version/8LNbqvAF) |
| nicemod | 1.4.1 - 1.20 | 1.21/1.21.1용 1.4.3 | [릴리스](https://modrinth.com/version/2dlfm8yY) |
| stoneworks | 20.4.0 | 26.2용 26.2.0 | [릴리스](https://modrinth.com/version/iaCtNo4p) |
| trafficcraft | 1.20.4-1.1.3 | 1.21.1용 beta-1.2.0+3 | [릴리스](https://modrinth.com/version/rzrY1Buf) |
| yuushya | 2.2.3 | 공식 2.3.0 실행판은 1.21/1.21.1용; 아래 동일 MC 소스 검토 후보 별도 | [릴리스](https://modrinth.com/version/g5TBlA52) |
| yuushya_modelling | 2.2.0 | 다른 MC별 발행본도 버전 2.2.0 | [릴리스](https://modrinth.com/version/FQMpG8yv) |

각 모드 전체 호환/비호환 버전 및 변경로그 원문은 같은 감사 폴더의 `<modId>.json`, 추가 수집한 `ptsdeco-modrinth.json`에 보존되어 있다. 더 높은 Minecraft 버전용 변경을 1.20.4의 누적 수정으로 가져오지 않았다.

### 동일 Minecraft 소스 브랜치 확인

`git ls-remote`만 사용해 작업트리/remote refs를 바꾸지 않고 확인했다. 다음 현재 upstream HEAD는 모두 lock의 `source.baselineCommit`와 일치한다. 즉 관리 fork의 Minefed 커밋과 별개로 새 upstream source-only 업데이트는 이 브랜치들에서 없다.

| 모드 | 확인 브랜치 | upstream 전체 커밋 |
|---|---|---|
| Decorative Blocks | main | 5775f8bb2c3fa57e041a2d40d377239e7c78d58d |
| Diagonal Fences | 1.20.4 | 57e3bc3958e313c772cf68c2bfcb06a367fceb5d |
| Diagonal Walls | 1.20.4 | 250c86bd48638d7f6979850a36e0240aed38fc85 |
| Diagonal Windows | 1.20.4 | 4116d6bab254219ee1e78f25c8ecbd44ac42594b |
| Handcrafted | 1.20.x | 5d3260b2882ebe5de1aa7a4ca4aa2336a593f31d |
| Mishang Urban Construction | 1.20.4 | ff9925d49a8e9512bfd0160038421b829c5ff68e |
| Modern Glass Doors | 1.20 | bf38d4feb851041357c81caa696450498cda0048 |
| Modern Lights | 1.20---1.20.4 | 5df1c7567ac7f4dd8d40118000187585e5e9b725 |
| Paladin's Furniture | architectury-1.20.4 | 0921e7cdd2684061f2372088bdedd37a9dce838d |
| Stoneworks | 1.20.4 | fc6ff7702dcf3bc203a4466039a2abe9c55b560f |
| TrafficCraft | 1.20.4-dev | c6c7092df4c1f77e438e507756255eb47e7a3585 |
| Yuushya Modelling | master | 3e36b9f66c0ae10202379f7287f88f7906976163 |

CityCraft/Macaw's Doors/Fences의 공개 소스는 이미 lock에 대응 Fabric 소스 부재가 기록되어 있으므로 최신 공개 default 소스를 곧바로 1.20.4/Fabric source-only 후보로 취급하지 않았다. NiceMod에는 현재 main 하나만 존재하고 [현재 properties](https://raw.githubusercontent.com/MIUNO/NiceMod/main/gradle.properties)가 MC1.21/1.4.3이므로 같은 MC 업데이트 후보가 아니다.

#### 추가 소스 검토 후보: Yuushya Townscape 2.2.3 → master 2.3.0

- 운영/기준 소스: Gitee `v2.2.3`, `e76ea8ac5454ec424771f593ce05ee0082e4b278`. 태그는 변하지 않았다.
- 새 후보: Gitee `master`, **`4453f228d22d476f5228e367458ec75fda0f717b`**, root 버전 2.3.0. [고정 커밋 gradle.properties](https://gitee.com/yuushyatownscape/yuushya-townscape/blob/4453f228d22d476f5228e367458ec75fda0f717b/gradle.properties).
- [settings.gradle](https://gitee.com/yuushyatownscape/yuushya-townscape/blob/4453f228d22d476f5228e367458ec75fda0f717b/settings.gradle)에 `1.20.4:fabric`이 포함되고 [1.20.4 properties](https://gitee.com/yuushyatownscape/yuushya-townscape/blob/4453f228d22d476f5228e367458ec75fda0f717b/1.20.4/gradle.properties)는 Minecraft 1.20.4 / Fabric Loader 0.16.0 / Fabric API 0.97.1+1.20.4를 유지한다. 공통 빌드도 gen-1.20.4를 유지한다. 따라서 다른 MC의 코드만 있는 경우와 달리 소스 빌드 검토 후보로 볼 근거가 있다. **공식 호환 실행 릴리스, 실제 빌드 성공, Minefed 적용 성공을 뜻하지 않는다.**

[기준 태그 대비 upstream 비교](https://gitee.com/yuushyatownscape/yuushya-townscape/compare/e76ea8ac5454ec424771f593ce05ee0082e4b278...4453f228d22d476f5228e367458ec75fda0f717b)의 30개 커밋 메시지와 변경 파일 및 공통 번역키에서 확인한 변화:

- **동일 MC 코드 수정:** 1.20.4 AddonLoader가 URL 디코딩/문자열 치환 대신 URI 기반 경로 처리를 사용하도록 변경. 1.20.4 Fabric JAR 제작을 내장 리소스팩 복사 뒤에 수행하도록 작업 순서 보강.
- **Fusion 연계:** 연결 텍스처 리소스/모델 생성 변경, 템플릿 및 무작위 모델 개선. 1.20.4 내장 fusion_combine 팩의 메타데이터는 Fusion 최소 1.2.0을 명시한다. 표지판 모델, 아스팔트 누락 텍스처, TV 모델 누락 및 술집 모델 부모 참조 수정; 발광 및 잔디 오버레이 관련 자원 변경.
- **제작법:** 도구 레시피(블록상태 브러시·형태 렌치 등) 추가/조정, Rechiseled 조합 연계 및 석재 절단·혼합·세척 등 제작 데이터 보강. 이 공통 1.16.5 데이터 디렉터리는 gen-1.20.4가 복사하는 입력이다. Create/Ecliptic Seasons 관련 데이터도 추가되지만 해당 모드가 운영 1.20.4에서 없거나 지원하지 않으면 그 연계 기능은 사용할 수 없다.
- **모델·구조물:** 무작위 포스터/게시물 및 변형 확장. 번역키 기준 작은 포스터 변형 3→8, 다른 작은 포스터·큰 포스터·세로 포스터 2→6, 긴 포스터 2→5, 목록 5→6. 그랜드 피아노·주방 템플릿·Mori 고양이 펫숍·Mori 식료품점·술집 구조 생성기 설명 추가; 완전한 구조는 Block Modelling 모드를 요구한다고 적혀 있다.
- **그 외:** 포르투갈어(브라질) 번역, Ecliptic Seasons의 눈 덮인 단풍/벚꽃 모델 데이터, 등록 가이드, Yuushya 작품이 무료이며 비공식 유료 재판매를 주의하라는 안내 문구 추가. 마지막 커밋은 TeaCon 빌드 트리거다.

**월드 ID/삭제 확인:** 공통 register 디렉터리 전체의 Git blob SHA를 기준 태그와 대조했으며 바뀐 파일은 `_class.json`, `block_furniture.json`, `block_sign.json`, `structure.json` 네 개였다. 이 네 파일의 이름 필드를 비교하면 기존 블록 등록 이름의 추가/삭제는 없고, 구조 생성기 아이템 다섯 개만 추가된다. 따라서 삭제된 수동 `sign_11.json`/`sign_14.json` 블록상태 파일을 블록 ID 삭제라고 해석하면 안 된다. 기존 ID를 유지하면서 포스터·표지판·앨범·목록의 모델/형태 정의가 변경되므로 기존 배치의 외관/형태 상태 확인은 필요하다. 공통 클래스 설정에는 창·의자 분류 태그, 식물의 괭이 채굴 및 식물 분류 태그가 추가됐다. API의 파일 목록 제한을 보완하기 위해 실제 register JSON과 전체 디렉터리 메타데이터도 저장했다. 생성 결과/런타임 레지스트리·월드 로딩을 시험한 것은 아니므로 최종 호환 보장은 하지 않는다.

공식 API는 파일 목록을 200개에서 잘랐으며 `truncated` 표시가 있어 파일별 전체 변화 수는 보고하지 않는다. 30개 커밋 목록의 마지막 부모는 기준 태그와 일치한다. 원문 `yuushya-compare.json`과 직접 읽은 고정 커밋의 빌드 설정 및 `yuushya-lang-diff.json`을 보존했다. 이 후보는 관리 fork의 기존 빌드 수정과 신규 upstream 변경을 함께 검토해야 한다.

## 교통·커스텀·광물 모드

조사일: 2026-09-12. 운영 기준은 `inventory/mods.lock.json`의 included=true 항목이다. 관리 소스 pin/빌드 레시피와 운영 보관 JAR를 구별했다. 1.20.4/Fabric을 유지한다. 공식 배포 업데이트 1개(MSD), 아직 배포되지 않은 동일 Minecraft 소스 검토 대상 2개(MTR/MythicMetals), 관리 소스에 준비되어 있으나 운영 기준본에는 없는 자체 수정 2개(Webstreamer/Minefed Display)가 있다. 다른 항목은 아래에 모두 기록했다.

### 전체 판정

| 모드 | 운영 버전 | 1.20.4/Fabric 판정 | 후보·현황 |
|---|---|---|---|
| MTR | 4.0.5, Minefed 바이너리 | 공식 배포는 최신. 미출시 소스 검토 가능 | 공식 `4.0.6` 브랜치의 37개 커밋. 내부 버전은 아직 4.0.5이며 정식 4.0.6 JAR가 아님 |
| MSD | 1.3.15 / MTR 4.0.0-beta.14 대상 빌드 | **공식 업데이트 대상** | **1.4.5 / MTR 4.0.5 대상 빌드**, beta. 중간 배포 10개 |
| Automobility Refueled | 0.4.3.b+1.20.4-fabric | 최신 | 최신 공식 GitHub 1.20.4 prerelease와 동일. 대응 소스 head도 동일 |
| Chisels & Bits | Minefed 1.5.10-FC | 기능 업데이트 확인 안 됨 | 공식 1.20.4 최신 1.4.157; Minefed 패치판과 별개. 공식 sameMC branch는 이미 포함 |
| Minefed Display | 1.0.0 | **자체 수정 적용 후보** | 버전 1.0.0 유지, MCEF 선택적 로딩 수정은 이미 관리 소스에 있음 |
| Webstreamer | Minefed 1.5.0 | **자체 수정 적용 후보** | 관리 소스 **1.5.0+minefed.1**, 화면 표시 거리 수정. 공식 최신은 1.5.0 |
| Oritech | 0.5.1+1.20.4 | 최신 | 동일 Minecraft 공개 배포/소스 head 모두 같은 버전 |
| MythicMetals | 0.19.7+1.20.4 | 공개 배포는 최신. 미출시 소스 검토 가능 | 동일 버전 소스에 운영자용 위키 내보내기 명령 2개 커밋. 낮은 우선 |
| MythicMetals Decorations | 0.6.1+1.20.3 | 최신 | 파일명은 1.20.3이지만 1.20.4 공식 지원. 대응 소스 head도 동일 |
| Alloy Forgery | 2.1.4+1.20.3 | 최신 | 파일명은 1.20.3이지만 1.20.4 공식 지원. 대응 소스 head도 동일 |
| 보관 제외 MTR | 4.0.3 | 별도 업데이트 대상 아님 | 같은 modId의 운영 정책상 기준은 4.0.5 |
| 보관 제외 TCPShield RealIP | 2.8.1 | Fabric 범위 밖, 공개 배포도 최신 | Bukkit/Bungee/Velocity 플러그인; Fabric 메타데이터 없음 |

### MSD: 1.3.15 → 1.4.5

최종 파일은 `MSD-fabric-1.20.4-4.0.5-1.4.5.jar`, 공개일 2026-06-23, Modrinth `nMixopsa`, **beta**다. 대응 MTR 빌드 버전이 현재 운영 4.0.5와 일치한다. 현 관리 소스는 아직 1.3.15이므로 앞으로 실제 업데이트할 때 소스 통합/빌드 레시피 업데이트가 필요하다. [공식 최종 배포](https://modrinth.com/mod/station-decoration/version/nMixopsa)

운영본 이후 1.20.4/Fabric 배포의 변경사항 전부:

| MSD | 공개일(UTC) | 공식 변경사항 | 배포 |
|---|---|---|---|
| 1.3.16 | 2025-03-11 | MTR 4.0.0-beta.15+hotfix.1에 대응 | [WPk34Qes](https://modrinth.com/version/WPk34Qes) |
| 1.3.17 | 2025-03-25 | MTR 4.0.0-beta.16에 대응 | [A3l3GRmG](https://modrinth.com/version/A3l3GRmG) |
| 1.3.18 | 2025-04-30 | MTR 4.0.0-prerelease.1에 대응 | [wKoqAUc8](https://modrinth.com/version/wKoqAUc8) |
| 1.3.19 | 2025-06-07 | MTR 4.0.0-prerelease.2에 대응 | [2ckcp1IM](https://modrinth.com/version/2ckcp1IM) |
| 1.4.0 | 2025-08-16 | MTR 4.0.0 정식판에 대응 | [x2cnF5IS](https://modrinth.com/version/x2cnF5IS) |
| 1.4.1 | 2025-08-27 | MTR 4.0.1에 대응 | [oSHwBS4i](https://modrinth.com/version/oSHwBS4i) |
| 1.4.2 | 2025-10-18 | MTR 4.0.2에 대응 | [phuHuYkq](https://modrinth.com/version/phuHuYkq) |
| 1.4.3 | 2026-02-24 | MTR 4.0.3에 대응 | [i6IYQODD](https://modrinth.com/version/i6IYQODD) |
| 1.4.4 | 2026-04-17 | MTR 4.0.4에 대응 | [ex8HZpex](https://modrinth.com/version/ex8HZpex) |
| 1.4.5 | 2026-06-23 | MTR 4.0.5에 대응 | [nMixopsa](https://modrinth.com/version/nMixopsa) |

위 10개는 모두 beta이며, 공식 배포 설명은 각각 MTR 대응 버전 변경만 기재한다. 따라서 새 장식 블록이나 대규모 콘텐츠가 추가됐다고 볼 근거는 없다.

소스도 비교했다. 기준 `c0221a39c4b7829a47478bce4303f1f29f84527e` → upstream `4.0.0` 브랜치 `14b0a8c9687bdbbfd755f282bbfab4030a92f3d3`의 전체 차이는 다음과 같다.

- 야마노테 역명판 설정 화면이 승강장 목록을 얻을 때 기존 `station` 인자 대신 `station.savedRails`로 만든 목록을 넘기도록 MTR의 변경된 API에 대응한다.
- 빌드에 참조하는 MTR 라이브러리를 beta.14에서 4.0.5로 갱신하고 각 Minecraft/Fabric/Forge 파일들을 교체한다.
- Gradle wrapper 8.12→8.14.5, Fabric Loom 무제한 동적 버전→1.10-SNAPSHOT, ForgeGradle 무제한 동적 버전→6.+ 변경. Forge 빌드 수정도 포함되지만 Fabric 게임 기능 변경으로 세지 않는다.
- 실제 소스의 변경된 게임 Java 파일은 `YamanoteRailwaySignScreen.java` 한 개다. 나머지는 빌드 설정/버전/라이브러리다. [전체 비교](https://github.com/AIDA64S/MTR-Station-Decoration-Addon/compare/c0221a39c4b7829a47478bce4303f1f29f84527e...14b0a8c9687bdbbfd755f282bbfab4030a92f3d3)

최종 공식 JAR를 메모리에서 열어 `fabric.mod.json`도 확인했다. MC는 정확히 `1.20.4`, Fabric API 필수, MTR 선언 범위는 여전히 `>=4.0.0-beta.14 <4.1`이다. 버전명에 4.0.5가 들어가는 것은 4.0.5를 대상으로 컴파일했다는 뜻이며 메타데이터 최소 버전이 4.0.5라는 뜻은 아니다. 이 범위는 MTR 4.1 계열을 허용하지 않는다. Fabric Loader/Java 최소 버전은 이 메타데이터에 별도로 쓰이지 않았다. 추출 결과: `custom-msd-1.4.5-metadata.json`.

현재 Minefed 소스 `4c1ce7298690b1036c8f58e30409799b57c11b6c`에는 JDK/Loom/buildSrc 빌드 수정이 있으므로 upstream으로 교체하면서 이 수정을 잃지 않아야 한다. 현재 레시피 expectedVersion은 1.3.15다.

### MTR: 공개 배포는 4.0.5 유지, 4.0.6 브랜치는 미출시 소스 후보

공식 1.20.4/Fabric 최신은 2026-06-14의 `FABRIC-4.0.5+1.20.4`다. 운영 기준과 버전 번호는 같다. [공식 배포](https://modrinth.com/version/Xurz5xWy)

운영 JAR SHA512는 `895fe3d6927a6df28378eae9c3ee1644a01c4056c3fdf19e2619dbceb6dc1b0cb329b3bcdf648e7dfa7757bef0b8c270ee6a047fd88648d5342dab143616ecfb`, 공식 JAR는 `a88a39094d5a95f426bd555818ae6d21f669da2f83a95d30b272c61449f90a0da730b39dd83547feac2fe280cdc3afbd85381d394e0ff394e5a1456dba2a16be`로 다르다. 운영 보관 파일의 SHA256이 lock과 같음을 재검증했고, 그 안에서 `BinaryPacketCodec`와 `PacketCodecCapabilities` 클래스를 확인했다. 따라서 Minefed의 패킷 협상/압축 표현 최적화는 이미 운영 기준본에 존재한다. 9월 소스 로그만 보고 새로 적용할 업데이트로 계산하면 안 된다.

관리 브랜치 `minefed-1.20.4`의 전체 pin은 `3cdeeeb2951dfd1d9f2ddfe28dd4844e0b732e0e`. 공식 master `739dba4488fd17aaee9a601276387e315876f39e`는 이미 이 pin의 ancestor다. 그 뒤 Minefed의 렌더 큐/도착정보/PIDS 캐시, 차량·리프트 부분 갱신, 레거시 상대와 협상하는 손실 없는 compact packet, 기존 차량 속도 제한 및 Core/Mappings 패치가 유지되어 있다. 9월 7일의 추가 소스 변경은 웹사이트 빌드 순서, Java17 바이트코드 유지, 라이선스 고지 보존 등 빌드 영역이다. [Minefed 최적화 문서](https://github.com/minefed/Minecraft-Transit-Railway/blob/3cdeeeb2951dfd1d9f2ddfe28dd4844e0b732e0e/docs/performance-optimizations.md)

별도로 공식 `4.0.6` 브랜치가 있다. 조사 시 head `240524a18d59edeb75cf8040cb209b91b428b5d7`(2026-07-16)는 master에서 37개 커밋 앞서며, `gradle.properties`는 여전히 **Minecraft 1.20.4 / version 4.0.5**다. 공식 4.0.6 배포가 확인된 것은 아니므로 즉시 JAR 업데이트가 아닌 선택적 소스 통합 후 검증 대상으로 분류한다. 모든 실질 변화:

- MQO→OBJ 변환에서 같은 재질이 계속되면 `usemtl`을 반복 기록하지 않아 출력/처리량을 줄인다.
- MQO 인용 문자열, 객체 이름의 중괄호, 텍스처 경로의 역슬래시 파싱을 고친다. 관련 회귀 테스트도 추가한다.
- Class 345(Aventra), Class 377(Electrostar)의 구동·제동·문·주행 음원을 BVE 구성으로 전환한다. 이전 음원/설정 삭제, 새 CSV/CFG/OGG 및 차량 템플릿과 sound reference 수정이 포함된다. 37개 커밋 중 상당수는 이 파일 추가·정리 작업이다.
- 동기화 시 차량이 튀거나 순간이동하듯 움직이는 현상을 다루는 보간 변경: 오차 리셋 임계값의 최소 10 확보, 보간 속도의 최소 가속도 적용, 차량기지 밖에서는 정차점을 넘지 않도록 상한 처리.
- **문 앞에 서서 문을 열어두는 기능을 일시 비활성화**한다. 승차 패킷의 door override 전달을 끄고 문 막힘 검사도 비활성화한다. 이는 기능 제거에 가까운 동작 변경이므로 별도 판단이 필요하다.

현재 Minefed 소스에서 기존 문자열 파서, 기존 보간식, doorOverride 전달이 남아 있음을 직접 확인했다. 이 변경들이 이미 흡수된 것은 아니다. 패킷/차량 보간 파일이 Minefed 성능 패치와 겹치므로 upstream 브랜치 전체로 바꾸면 안 되고 기존 기능을 보존하는 통합 검토가 필요하다. [공식 37개 커밋 전체 비교](https://github.com/Minecraft-Transit-Railway/Minecraft-Transit-Railway/compare/739dba4488fd17aaee9a601276387e315876f39e...240524a18d59edeb75cf8040cb209b91b428b5d7)

다른 Minecraft 버전용 최신은 `4.1.0-beta.2`, Fabric 1.21.1/1.21.4(2026-07-04)이며 1.20.4 호환 파일은 없다. 공식 changelog는 Discord 참고만 제공한다. 사용자의 1.20.4 유지 범위와 MSD `<4.1` 조건 때문에 대상에서 제외한다. [1.21.1 배포](https://modrinth.com/version/JSuVAgAb), [1.21.4 배포](https://modrinth.com/version/XCtvQnaw)

### Webstreamer: 1.5.0 → 준비된 Minefed 1.5.0+minefed.1

공식 최신 1.20.3/1.20.4 버전은 여전히 1.5.0(2024-03-09)이고 upstream master는 `62d2f5bd26364aa994055ab55d2fd55461f87321`로 해당 release와 같다. [공식 배포](https://modrinth.com/version/ondpQ8lg)

Minefed 소스는 이미 2026-09-07의 `f9c03980c9cb31ca891e4429bc2529c6c0cce033`을 가리키고 빌드 레시피도 1.5.0+minefed.1이다. 핵심 수정 `ae9cb634ca532c9381adb849c6cb56c75a719ebc`은 화면의 기존 64블록/높이 포함 거리 제한을 제거하고 클라이언트/서버에서 실제 적용된 청크 표시 거리의 수평 범위를 사용하도록 바꾼다. 멀리 있거나 높이가 다른 화면이 지형보다 먼저 사라지는 문제를 해결한다. 테스트 추가와 테스트 로그 위치 정리도 포함된다. [수정 커밋](https://github.com/minefed/fabric-webstreamer/commit/ae9cb634ca532c9381adb849c6cb56c75a719ebc)

운영 1.5.0은 공식 배포와 해시가 다른 기존 Minefed 수정본이다. 관리 소스에는 2025년의 X/Y 위치 조절, Z 오프셋, 의존성 갱신도 있지만 이들을 전부 새 변경으로 계산하지 않는다. lock SHA256과 일치하는 운영 JAR의 renderer class에는 새 거리 helper `isInRenderDistance`가 없음을 확인했고, lock의 운영 버전도 1.5.0 그대로다. 즉 이번 소스의 새 표시 거리 동작은 운영 기준과 구별된다. MC 1.20.4 / Java17 / Fabric Loader0.16.14 대상이며 LGPL 대응 소스와 동봉 FFmpeg/JavaCV 등 고지는 보존해야 한다.

### Minefed Display: 같은 1.0.0의 MCEF 선택적 로딩 수정

공개 main은 `79708da179682295df0dfc379320a0759c25a97d`, 관리 브랜치는 `869b976756be38f298105d4adf6be2d22e3a0b8c`다. 후자의 2026-09-07 수정으로:

- 전용 서버에서 MCEF를 필수 의존성으로 요구하지 않는다.
- 클라이언트에 MCEF가 있을 때만 브라우저 renderer를 초기화한다.
- MCEF가 없어도 블록/URL/크기 설정은 쓸 수 있고 웹 화면만 비활성화하며 이유를 로그로 남긴다.
- 1.20.4용 MCEF 2.1.6 이상을 선택 의존성으로 안내하고, 그보다 오래된 호환되지 않는 MCEF는 Loader가 차단하도록 선언한다.

버전 번호/레시피는 여전히 1.0.0이므로 버전 문자열만으로 새 빌드를 구별할 수 없다. lock SHA256이 일치하는 운영 JAR에 기존 커스텀 크기 디스플레이 클래스는 이미 있고, 새 `McefDisplayRendering` 클래스는 없다. 커스텀 크기 블록을 신규 기능으로 잘못 계산하지 않고 위 선택 로딩 수정만 적용 후보로 본다. MC~1.20.4, Java>=17, FabricLoader>=0.16.14. [변경 전체](https://github.com/minefed/minefed-display/commit/869b976756be38f298105d4adf6be2d22e3a0b8c)

### MythicMetals: 배포 최신, 동일 버전 소스 2개 커밋은 낮은 우선

운영 0.19.7+1.20.4는 1.20.4/Fabric 최신 공개 beta다. 그 이후 1.20.4 호환 공개 배포는 없다. [현재 공식 배포](https://modrinth.com/version/SKfkZKbj)

관리 pin `cfa897b7e6b2ab856f08582c5e525e675633b33c`의 upstream 기준은 release tag `4f61b8a7d01c0edbc57fd3e14f9d2a413e0e62cf`다. 공식 `1.20.4` 브랜치 `38d245cdd3b8b81529d09a1b09b4dc2ef5588edc`는 2개 커밋 앞서며 버전도 여전히 0.19.7+1.20.4다. 변화 전부:

- 운영자 권한의 `/mythicmetals wiki ores <ore-config>` 명령 추가: 광석/변형 이름과 이미지 템플릿, 광맥 최대 크기, 생성 높이·분포·discard 확률을 위키 문서 형태로 로그에 출력한다.
- 광석 설정 및 block set 명령 인자/목록과 이름 대응을 등록한다.
- armor/tool/block/ore config 인자 오류 메시지를 영문 번역 문자열로 제공한다.
- 출력의 누락 줄바꿈과 discard 확률 표현을 정리한다. 광석 생성량이나 월드 생성 규칙을 바꾸는 업데이트는 아니다.

일반 플레이 목적의 업그레이드 우선순위는 낮다. 현재 Minefed 소스에 새 명령 인자가 없음을 확인했다. [2개 커밋 전체 비교](https://github.com/Noaaan/MythicMetals/compare/4f61b8a7d01c0edbc57fd3e14f9d2a413e0e62cf...38d245cdd3b8b81529d09a1b09b4dc2ef5588edc)

다른 Minecraft 계열은 1.21.4용 0.25.3+1.21.4, 1.21.1용 0.24.6+1.21, 1.20.1용 0.19.12+1.20.1이며 모두 1.20.4 호환 근거가 없다. 업로드 날짜로 최신인 1.20.1 유지보수판을 1.20.4 최신판으로 잘못 제시하지 않는다. [1.21.4](https://modrinth.com/version/poyAM7Ti), [1.21.1](https://modrinth.com/version/fKQ4feyG), [1.20.1](https://modrinth.com/version/qdgcAVPf)

### 나머지: 최신/제외 판정의 근거

- **Chisels & Bits**: 공식 Fabric 1.20.4 최신 파일은 1.4.157(2024-06-21). 공식 `version/1.20.4` head `6f5630a21dc11156384fe0e3b2efd8f71e7df148`가 Minefed 현재 pin `12fd1d23b3e6fb929ccba01e034c46ae632acbe0`의 ancestor임을 확인했다. Minefed의 WorldEdit 복사/붙여넣기 대응 및 성능 수정이 있으며 공식 JAR로 단순 교체할 수 없다. 운영 JAR는 manifest에 2026-02-17이라고 쓰이지만 nested API/core에 2월20일 소스 패치의 `IncrementalGreedyMeshBuilder`, `UpdateChiseledBlockDeltaPacket`, `ChiseledRenderingPerformanceMode`, `IRevisionedAreaShapeIdentifierProvider`가 실제 존재하고 lock SHA256과 일치한다. 따라서 날짜만 근거로 성능 수정이 운영에 없다고 판정하지 않는다. 현재 추가 소스 변경은 Java21로 access transformer를 실행하는 빌드 수정이다. 타 Minecraft 최신은 26.1.2용 26.1.2.33으로 범위 밖. [공식 1.20.4 파일 목록](https://www.curseforge.com/minecraft/mc-mods/chisels-bits-for-fabric/files/all?page=1&pageSize=20&version=1.20.4), [관리 pin](https://github.com/minefed/Chisels-and-Bits/commit/12fd1d23b3e6fb929ccba01e034c46ae632acbe0)
- **Automobility Refueled**: 공식 release `v0.4.3.b+1.20.4`(2025-01-12, prerelease)와 운영판이 동일하며 공식 1.20.4 branch/tag 모두 `96a6369eed2e5528ba8d09c643e032cf7fa15c51`이다. Minefed `13160075fb4be333fe2b425183c02f9dc2348184`는 여기 정책 문서만 추가한 pin이다. 일반 Automobility 프로젝트의 버전과 Refueled를 혼동하지 않는다. 1.20.6/1.21용 같은 0.4.3.b가 있지만 새 기능 업그레이드가 아닌 다른 MC 포트이며 현재 범위 밖. [공식 1.20.4](https://github.com/codenobacon4u/Automobility/releases/tag/v0.4.3.b%2B1.20.4), [전체 배포](https://github.com/codenobacon4u/Automobility/releases)
- **Oritech**: 운영 0.5.1+1.20.4(beta)가 공식 호환 최신이며 `1.20.4` branch는 기준 commit `83ba099a700478e4fd7e85548ced4f5d7227d114` 그대로다. `v0.6.1+1.20.4`라는 tag도 정확히 같은 commit을 가리키므로 실제 0.6.1 기능 업데이트로 계산하지 않는다. 최신 Fabric 1.2.12는 MC1.21/1.21.1, 전체 최신2.0.0-exp6는 NeoForge26.1/26.1.2다. [현행](https://modrinth.com/version/Fz5w3V0S), [다른 MC Fabric 최신](https://modrinth.com/version/lYkwnT9Q), [동일 commit의 태그](https://github.com/Rearth/Oritech/tree/v0.6.1%2B1.20.4)
- **MythicMetals Decorations**: 0.6.1+1.20.3(beta)가 1.20.4 최신이며 공식 `1.20.4` branch `e31a9c7c4ffcdd6b38370a38519593c34f0b92f2`도 release 기준과 같다. 새 공식 0.10.0+1.21.4 및 0.9.2+1.21은 다른 MC용이다. JAR metadata의 `1.20.x` 같은 넓은 표기만으로 타 release의 1.20.4 실행 가능성을 추정하지 않았다. [현행](https://modrinth.com/version/L97C9D39), [1.21.4판](https://modrinth.com/version/tF9mdCya)
- **Alloy Forgery**: 2.1.4+1.20.3(release)가 1.20.4 최신이며 공식 `1.20.4` head `f1b61a1b1c0dc7d483b9c44472237cc1c9cc8711`도 release 기준과 같다. 3.1.1(beta)는 MC26.1.2, 3.0.7은 MC1.21.4/1.21.10용이므로 범위 밖. [현행](https://modrinth.com/version/X1pKXaia), [26.1.2판](https://modrinth.com/version/7bsTNh92)
- **TCPShield RealIP**: 현재 공개 최신2.8.1(2024-08-04)과 보관본이 같으며 이 파일은 Fabric 모드가 아니어서 included=false다. 이후 배포에 의한 변경사항 없음. [공식 release](https://github.com/TCPShield/RealIP/releases/tag/2.8.1)

### 조사 검증 및 자료

운영/소스/서버 파일을 변경하지 않았고, fetch/checkout/build도 하지 않았다. 원격은 공식 Modrinth/GitHub/CurseForge와 read-only `git ls-remote`로 확인했다. JAR 검증은 기존 보관본의 SHA256 및 ZIP 클래스/메타데이터를 읽었으며 최종 MSD 공식 JAR는 메모리에서만 열었다. 실제 Minecraft 기동이나 플레이 호환성 검증을 수행한 보고서는 아니다.

원시 자료: `custom-minecraft-transit-railway.json`, `custom-webstreamer.json`, `msd.json`, `custom-msd-compare.json`, `custom-msd-1.4.5-metadata.json`, `custom-mtr406-compare.json`, `custom-mythic-compare.json`, `codenobacon4u_Automobility.json`, `TCPShield_RealIP.json`, 각 광물 모드 `<modId>.json`. 후보 버전/commit 전체 식별자는 본문에 보존했다.

## 운영·성능 모드

기준은 `inventory/mods.lock.json`의 운영 관측 JAR(Minecraft 1.20.4 / Fabric, 2026-09-06 관측)이다. 아래 18개를 모두 확인했다. **호환 공식 배포판 업데이트는 WorldEdit Hang Fix 1개이며, 별도로 Wireless Redstone 1.3.0 미릴리즈 소스가 검토할 만한 변경을 포함한다.** “없음”은 호환 공식 배포판을 뜻하며 모든 개발 브랜치에 수정이 없다는 뜻은 아니다.

### 전수 목록

| 모드 | 현재 Minefed 운영 버전 | 최신 1.20.4/Fabric 공식판 | 판정 | 근거 |
|---|---|---|---|---|
| BlueMap | 5.3 | 5.3-fabric-1.20 | 호환 공식 업데이트 없음 | [공식 배포](https://modrinth.com/version/lHRktt6S) |
| CC: Tweaked | 1.110.2 | 1.110.2 **alpha** | 호환 공식 업데이트 없음; 1.20.4 정식판 없음 | [공식 배포](https://modrinth.com/version/afcOmjVN) |
| Chunky | 1.3.146 | 1.3.146 | 호환 공식 업데이트 없음 | [공식 배포](https://modrinth.com/version/NHWYq9at) |
| CrossStitch | 0.1.6 | 0.1.6 | 호환 공식 업데이트 없음 | [공식 배포](https://modrinth.com/version/dJioNlO8) |
| Carpet | 1.4.128+v231205 | 1.4.128 | 호환 공식 업데이트 없음; 표기 차이만 있음 | [공식 배포](https://modrinth.com/version/yYzR60Xd) |
| Fabric Seasons | 2.4.2-BETA+1.20.4 | 2.4.2-BETA+1.20.4 **beta** | 호환 공식 업데이트 없음; 1.20.4 정식판 없음 | [공식 배포](https://modrinth.com/version/kSoN9Hi9) |
| FabricProxy-Lite | 2.7.0 | v2.7.0 | 호환 공식 업데이트 없음 | [공식 배포](https://modrinth.com/version/Mxw3Cbsk) |
| FallingTree | 1.20.4.3 | 1.20.4-1.20.4.3 | 호환 공식 업데이트 없음 | [공식 배포](https://modrinth.com/version/mb15RrXi) |
| FerriteCore | 6.0.3 | 6.0.3-fabric | 호환 공식 업데이트 없음 | [공식 배포](https://modrinth.com/version/pguEMpy9) |
| Lithium | 0.12.1 | mc1.20.4-0.12.1 | 호환 공식 업데이트 없음 | [공식 배포](https://modrinth.com/version/nMhjKWVE) |
| MemoryLeakFix | 1.1.5 | v1.1.5 | 호환 공식 업데이트 없음 | [공식 배포](https://modrinth.com/version/5xvCCRjJ) |
| ModernFix | 5.17.0+mc1.20.4 | 5.17.0+mc1.20.4 | 호환 공식 업데이트 없음 | [공식 배포](https://modrinth.com/version/CV2Vtn5m) |
| Realtime | 1.0.3-1.20-1.21.1 | 1.0.3-1.20-1.21.1 | 호환 공식 업데이트 없음 | [공식 배포](https://modrinth.com/version/3JUK9zwP) |
| Starlight | 1.1.3+fabric.f5dcd1a | 1.1.3+1.20.4 | 호환 공식 업데이트 없음; 개발 중단 | [공식 배포](https://modrinth.com/version/HZYU0kdg), [유지보수 상태](https://github.com/PaperMC/Starlight) |
| TimeOutOut | 1.0.4+1.20.2 | 1.0.4 | 호환 공식 업데이트 없음 | [공식 배포](https://modrinth.com/version/VAYNN78f) |
| WorldEdit Hang Fix | 1.0.2 | **v1.0.5-mc1.18.2-fabric** | **업데이트 가능** | [공식 배포](https://modrinth.com/version/CcLdaS7o) |
| WorldEdit | 7.3.0+6678-55745ad | 7.3.0 | 호환 공식 업데이트 없음 | [공식 배포](https://modrinth.com/version/ZOhVauWn) |
| Wireless Redstone | 1.2.2+1.20.4 | 1.2.2+1.20.4-fabric | 공식판은 최신; **1.3.0 미릴리즈 소스 검토 대상** | [공식 배포](https://modrinth.com/version/fgUwUN3e), [개발 변경](https://github.com/Razzokk/wireless-redstone/blob/90957d561c3922fde76935614b4ab609c62777c9/CHANGELOG.md) |

### WorldEdit Hang Fix: 1.0.2 → 1.0.5

- 대상 파일: `worldedit-hang-fix-v1.0.5-mc1.18.2-fabric.jar`(39,515 bytes). 파일명은 1.18.2지만 공식 호환 목록은 Minecraft 1.18.1–1.20.4이고, 소스의 Minecraft 범위는 `>=1.18 <1.20.5`이다. Java 17 대상 빌드이며 JAR의 Fabric Loader 최소 선언은 `>=0.11.4`로 유지된다. 빌드 의존성 Loader 0.18.6과 런타임 최소 선언을 혼동하면 안 된다. [배포 메타데이터](https://api.modrinth.com/v2/version/CcLdaS7o), [버전 설정](https://github.com/Fallen-Breath/worldedit-hang-fix/blob/583c7ceab5031d0864bf85a5934662a8def870e2/versions/1.18.2-fabric/gradle.properties), [Java 설정](https://github.com/Fallen-Breath/worldedit-hang-fix/blob/583c7ceab5031d0864bf85a5934662a8def870e2/common.gradle)
- 공식 태그 `v1.0.5`, 커밋 `583c7ceab5031d0864bf85a5934662a8def870e2`, 공개 2026-04-17. SHA-256: `7f15d0a4a3defabcaa278665b927b8f9c38aa56ecb9b8ab97bb918d7c40072d3`. Minefed 현재 관리 브랜치는 `minefed-1.20.4`, 소스 pin `ae96bc02ab25322d7ee727125901fde785be7365`, 운영 대응 기준 소스는 `a68f1feda94d3cc2fa496726e3983d440bad2466`이다. [릴리즈](https://github.com/Fallen-Breath/worldedit-hang-fix/releases/tag/v1.0.5)
- **1.0.3 개발 단계:** 빌드 템플릿·CI 정비, Yarn에서 Mojang/Parchment 매핑으로 변경, Minecraft 26.1 대응 준비. Git 이력에는 버전 증가가 있으나 공개 GitHub 릴리즈는 없고 이번 Modrinth 목록에서도 독립 배포가 확인되지 않는다. [누적 비교](https://github.com/Fallen-Breath/worldedit-hang-fix/compare/v1.0.2...v1.0.5)
- **1.0.4:** Minecraft 26.1.x 지원을 추가하고, Java 8/16/17/21/25 구간에 맞춰 Minecraft별 빌드를 나눈다. 따라서 1.20.4에서는 기존 `mc1.20.6` 이름의 공용 JAR 대신 새 `mc1.18.2-fabric` 빌드를 선택한다. [1.0.4 릴리즈](https://github.com/Fallen-Breath/worldedit-hang-fix/releases/tag/v1.0.4)
- **1.0.5:** WorldEdit 7.4.1에서 추가된 `RecursiveDirectoryWatcher` 감시 스레드를 daemon으로 바꿔 서버 종료 후 프로세스가 남는 추가 원인을 제거한다. 기존 작업 실행기 종료와 진행률 Timer 수정은 유지한다. [1.0.5 릴리즈](https://github.com/Fallen-Breath/worldedit-hang-fix/releases/tag/v1.0.5), [실제 수정](https://github.com/Fallen-Breath/worldedit-hang-fix/commit/185f6e0dec13adaccf82496d4c627685b6817a1c)
- 부수 변경: 로그 API/메시지 정리, `fabric.mod.json` 라이선스 필드 추가, 아이콘 경로 통일, CI 배포 메타데이터 정비. Modrinth의 required dependency 목록은 빈 배열로 바뀌었지만 JAR 소스에는 `worldedit: "*"` 의존성이 남아 있다. [누적 소스 비교](https://github.com/Fallen-Breath/worldedit-hang-fix/compare/v1.0.2...v1.0.5)
- **Minefed 적용 우선순위는 낮음:** 운영 WorldEdit은 7.3.0으로, 신규 수정의 주된 발생 조건인 7.4.1 이상이 아니다. 업데이트 가능 여부와 현재 서버에서의 체감 이득을 구분해야 한다. 새 JAR의 시작·정상 종료 동작은 이번 조사에서 실행 검증하지 않았다.

### Wireless Redstone: 1.2.2 → 미릴리즈 1.3.0 소스

공식 JAR은 현재 1.2.2가 최신이다. 다만 upstream `1.20.4` 브랜치의 `90957d561c3922fde76935614b4ab609c62777c9`(2026-08-23)는 운영 대응 태그 `3a7b4d614bb3cc45cd90a809052f0eefb2ae1201` 이후 31개 커밋을 포함한다. 소스 내부 버전은 **1.3.0**, 상태는 **Unreleased**이다. 현재 Minefed `minefed-1.20.4` pin은 `85cd6b45cd660deeba6ac5cb58b8d5f82795dae0`이며 이 추가 기능들은 포함하지 않는다. [버전 선언](https://github.com/Razzokk/wireless-redstone/blob/90957d561c3922fde76935614b4ab609c62777c9/build-logic/src/main/kotlin/mod/gradle/Mod.kt), [비교](https://github.com/Razzokk/wireless-redstone/compare/v1.2.2%2B1.20.4...90957d561c3922fde76935614b4ab609c62777c9)

Minecraft 1.20.4/Java 17을 유지한다. 런타임 Loader 범위는 `>=0.17`, 빌드 의존성은 Loader 0.19.3/Fabric API 0.97.2+1.20.4다. 공식 배포판이 없으므로 소스 통합·자체 빌드·별도 검증이 필요한 대상으로 분류한다. [호환성 설정](https://github.com/Razzokk/wireless-redstone/blob/90957d561c3922fde76935614b4ab609c62777c9/gradle/libs.versions.toml)

변경사항은 다음과 같다.

- 일반/P2P 레드스톤 송수신기에 벽·바닥·천장 부착형 블록 4종, 제작법·드롭·모델·텍스처 추가.
- Linker로 P2P 블록을 바라보면 조준점 아래 목표 위치 표시. 주파수 아이템으로 복사/설정할 때 메시지 표시.
- 송신기 ON/OFF를 수신기에 즉시 반영하여 기존 1레드스톤틱 지연 제거. 관측기 등의 1게임틱 펄스를 전달할 수 있게 변경.
- 주파수가 들어 있는 블록의 설치, `/setblock`, `/fill` 직후 네트워크 등록·상태 갱신 수정. 수신기의 배치/제거 시 등록과 해제 처리를 정비하고 별도 청크 로딩 로직 제거. ProjectRed 프레임으로 이동한 수신기 처리도 개선.
- P2P 송수신기 데이터 갱신, 먼 좌표에서 Sniffer/목표 강조 표시가 흔들리는 현상 및 강조 표시 알파 블렌딩 수정.
- Fabric 서버에서 레드스톤 가루 연결 문제와, 리모컨을 놓거나 버리거나 다른 핫바 아이템으로 바꿨을 때 주파수가 켜진 채 남는 문제 수정. 클라이언트에만 등록되던 mixin 문제도 정비.
- 설정 화면을 로더 공통으로 통합하고 설정 이름·설명·초깃값과 Cloth Config/Mod Menu 오류 처리 수정. 패킷 구현을 로더 간 공통화하고 불필요한 mixin 제거.
- Forge 1.20.4의 1.2.0–1.2.2 배포 JAR 시작 실패와 HUD 이벤트 처리 수정은 Minefed Fabric의 직접 적용 효과와 구분한다.
- Gradle 9.6.1/Loom 1.17 계열 등 빌드 체계와 CI·데이터 생성 정비. **빌드는 이번 조사에서 수행하지 않았다.**

위 내용은 [개발 변경 기록](https://github.com/Razzokk/wireless-redstone/blob/90957d561c3922fde76935614b4ab609c62777c9/CHANGELOG.md), [즉시 갱신 수정](https://github.com/Razzokk/wireless-redstone/commit/9367d8e), [공통화 수정](https://github.com/Razzokk/wireless-redstone/commit/c0d9b4fa26491bb465b02a61d1b7846f3227c55f)과 현재 소스의 차이를 함께 검토했다.

**데이터 호환 변경:** 송신기 위치/P2P 링크 등의 NBT 좌표를 int 배열로 바꾼다. 새 소스는 기존 데이터 읽기를 지원하지만, 이 버전으로 저장된 데이터를 1.2.2로 되돌리면 레드스톤 네트워크가 손상될 수 있다고 upstream이 명시한다. 실제 적용 시 월드·네트워크 데이터의 되돌리기 기준을 함께 설계해야 한다. [저장 형식 변경](https://github.com/Razzokk/wireless-redstone/commit/457ef60)

**개발 변경 기록의 오류도 확인했다:** 기록에 남아 있는 “Attachment Mode 설정”은 최종 소스에서 제거되었다. 또 기록의 “Sniffer 스택 크기 1 수정”과 달리 실제 1.2.2 대비 코드는 **Linker**의 스택 크기를 1로 바꾼다. 따라서 이 두 항목은 변경 기록 문구를 그대로 기능으로 약속하면 안 된다. [Attachment Mode 제거](https://github.com/Razzokk/wireless-redstone/commit/c0d9b4fa26491bb465b02a61d1b7846f3227c55f), [Linker 스택 수정](https://github.com/Razzokk/wireless-redstone/commit/5cc4f70)

### 후속 버전이 있어도 현재 조건의 업데이트가 아닌 항목

Modrinth의 Fabric 배포 중 최근 게시판을 기준으로 확인한 참고 정보다. 다른 Minecraft 버전의 기능을 1.20.4에서 사용하려면 별도 포팅이 필요하다. 이 표는 1.20.4 업데이트 수에 포함하지 않는다.

| 모드 | 다른 Minecraft용 후속판 | 현재 조건에 포함하지 않은 이유 |
|---|---|---|
| BlueMap | [5.24](https://github.com/BlueMap-Minecraft/BlueMap/releases/tag/v5.24) | Fabric 26.1–26.3 / Java 25. 기존 MC1.20–1.20.4 전용 Fabric 산출물은 5.3이 마지막. Modrinth 목록은 26.2까지여서 호환 상한은 공식 GitHub 릴리즈와 차이가 있음. |
| CC: Tweaked | [1.120.2](https://modrinth.com/version/Qc4JFhxl) | 최신 Fabric 정식 빌드는 MC1.20.1용. 최신 `mc-1.20.y` 소스 역시 이미 MC1.20.6/1.111.0으로 전환. |
| Chunky | [1.5.3](https://modrinth.com/version/4Eotm6ov) | MC26.1–26.2용. |
| CrossStitch | [0.1.7](https://modrinth.com/version/8h1nxay1) | MC1.21.8용. Minefed 소스는 1.20.4 동작을 복원한 상태. |
| Carpet | [26.2](https://modrinth.com/version/bGrLxJ8v) | MC26.2용. GitHub에는 26.3-beta-3도 있으나 1.20.4 대상 아님. |
| Fabric Seasons | [2.4.2-BETA+1.21](https://github.com/lucaargolo/fabric-seasons/releases/tag/2.4.2-BETA%2B1.21) | 동일 기능 버전의 MC1.21 포트. |
| FabricProxy-Lite | [2.12.0](https://modrinth.com/version/CsEpiziv) | MC26.1–26.2용. 2.8은1.20.5, 2.9는1.21, 2.10은1.21.8 전환. |
| FallingTree | [26.2.0.3](https://modrinth.com/version/sOoH5kkd) | MC26.2용. [CurseForge 1.20.4 파일 목록](https://www.curseforge.com/minecraft/mc-mods/falling-tree/files/all?page=1&version=1.20.4)도 1.20.4.3이 마지막. |
| FerriteCore | [9.0.0](https://modrinth.com/version/d5ddUdiB) | MC26.1–26.2용. |
| Lithium | [0.25.3](https://modrinth.com/version/f7vZ0VWU) | MC26.2용. |
| ModernFix | [Fabric 5.25.2+mc1.20.1](https://modrinth.com/version/rPmgLeZC) | MC1.20.1용. GitHub/CurseForge의 더 높은 Forge·NeoForge 버전을 Fabric 후보로 쓰면 안 됨. [CurseForge 1.20.4 목록](https://www.curseforge.com/minecraft/mc-mods/modernfix/files/all?page=1&pageSize=20&version=1.20.4)도5.17.0 확인. |
| Realtime | [1.0.3-1.21.2-1.21.6](https://modrinth.com/version/Ml7zUgJa) | MC1.21.2–1.21.6 포트. |
| TimeOutOut | [1.0.5](https://modrinth.com/version/eZtpMLAt) | MC1.21.10용. GitHub Releases는 1.0.4에 머물러 있어 Modrinth 확인이 필요함. |
| WorldEdit | [7.4.5](https://modrinth.com/version/6YnCYPwc) | Fabric MC26.2용. Bukkit판의 넓은 Minecraft 호환 범위를 Fabric에 적용하면 안 됨. |

### 소스 브랜치 및 Minefed 고유 차이

온라인 `git ls-remote --heads`와 로컬에 이미 존재하던 커밋을 대조했다. fetch·checkout·빌드는 하지 않았다.

- Fabric Seasons `1.20.4` / ModernFix `eol/1.20.4` / Realtime `1.20-1.21.1` upstream HEAD는 운영 대응 baseline과 같다.
- FallingTree `minecraft/1.20.4` HEAD `99a63674f855ef0b422abcf9050cc118d1860d1c`: 운영 태그 이후 9커밋은 Gradle·CI 및 빌드용 Commons IO/Guava/Lombok/Log4j 의존성 정비이며 게임 런타임 소스 변경은 없다. 새 기능 업데이트로 계산하지 않았다. [비교](https://github.com/RakambdaOrg/FallingTree/compare/1.20.4.3...99a63674f855ef0b422abcf9050cc118d1860d1c)
- Starlight `fabric` HEAD `cca03d62da48e876ac79196bad16864e8a96bbeb`: 운영 baseline 이후 README 1커밋만 있다. 저장소는 2024-03-08 archived이며 향후 업데이트 중단을 명시한다. [공식 저장소](https://github.com/PaperMC/Starlight)
- CC: Tweaked의 후속 공통 코드에는 WebSocket `CharsetDecoder` 스레드 공유 수정, Cobalt 갱신 등이 있으나 현재 `mc-1.20.y` 브랜치를 통째로 갱신하면 Minecraft1.20.6으로 바뀐다. 별도 백포트 조사 없이 1.20.4 업데이트로 계산하지 않았다. [문자 디코더 수정](https://github.com/cc-tweaked/CC-Tweaked/commit/4980b7355d72b4d001ef886e5a4cad2950363f6d)
- Minefed의 BlueMap·Chunky·Carpet·FerriteCore·Lithium·MemoryLeakFix·ModernFix·WorldEdit pin 추가분은 정책 문서와 빌드 재현성/의존성/Windows 빌드 수정이다. 운영 기능이 업그레이드되었다는 근거로 취급하지 않았다.
- CrossStitch Minefed `aa5545ce774566f3c09f2b34ac4ec0412274dec8`는 upstream의1.21.8 전환을 되돌려 운영0.1.6/1.20.4를 복원한 소스다. 최신 upstream HEAD로 단순 교체하면 이 호환성 복원이 사라진다.

### 검증 범위와 근거 파일

- 18/18개 운영 버전, 공식 Modrinth 호환 목록 및 전체 공개 버전 목록 확인. GitHub Releases 및 관련 태그·브랜치로 보완.
- WorldEdit Hang Fix의 1.0.2→1.0.5 전체 12커밋/33파일 비교 확인. Wireless Redstone의 전체 31커밋/202파일 변경 범위와 주요 런타임 소스 확인.
- `infrastructure-github-releases.json`: 공식 GitHub 릴리즈 API 원문(저장소별 최근100개 최대).
- `infrastructure-upstream-heads.json`: 이번 조사 시점 공개 upstream 브랜치 전체 HEAD.
- `worldedithangfix-compare.json`: 공식 누적 비교 API 원문.
- `wirelessredstone-upstream-log.txt`: 운영 대응 태그 이후 전체 커밋 목록.
- 각 `<modId>.json` 및 `modrinth.json`: 공식 Modrinth 조회 원문과 호환 판정용 데이터.
- 공식 배포판 전수 확인과 의미있는 관련 브랜치 확인이며, 모든 개발 브랜치의 모든 코드를 감사했다는 뜻은 아니다. JAR 설치·서버 변경·실행 검증은 하지 않았다.


## 이번 조사에서 확인한 범위

공식 Modrinth 버전 목록을 전수 조회하고 GitHub/CurseForge·동일 Minecraft 소스 브랜치로 보완했다. 후속 버전 표시에 해당하는 15개 파일을 공식 URL에서 받아 SHA512를 대조하고 Fabric 메타데이터를 읽었다. Modern Lights의 소스 파일 오등록도 이 단계에서 확인했다. 다운로드 파일과 API 원문은 Git에서 제외되는 `build/mod-update-audit-20260912/`에만 보관한다.

이 문서와 조사 데이터만 추가했다. 모드 소스·gitlink·운영 기준/의존성 lock·배포 정책·서버 파일을 바꾸지 않았으며, 후보를 설치하거나 Minecraft를 실행하지 않았다. 따라서 이 보고서는 실제 기능 전체/월드 호환성/업데이트 후 성능을 보증하는 테스트 결과가 아니다. 최신판의 모든 변경을 원문만으로 확정할 수 없는 CityCraft·일부 PTS 구간은 그 한계를 본문에 표시했다.
