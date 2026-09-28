# 운영 설정 최적화 안내 — 2026-09-28

[최적화 계획](OPTIMIZATION_PLAN_2026-09-28.md)의 5단계 항목이다. 코드를 바꾸지 않고, 운영 서버·프록시 설정만으로 네트워크와 서버 틱 비용을 줄인다.
릴리즈 팩은 `config/`와 `server.properties`를 포함하지 않으므로 아래 값은 운영자가 서버에서 직접 적용한다.
운영 서버의 파일 변경·업로드·재시작은 [AGENTS.md](../AGENTS.md)에 따라 별도 요청이 있을 때만 수행하며, 이 문서 작성 때 운영 서버는 변경하지 않았다.
각 항목은 플레이어가 보는 게임 동작을 바꾸지 않는 설정만 다룬다.

적용 전후는 같은 월드·위치·접속 인원으로 측정한다.
패킷은 [패킷 통계 도구](../tools/packet-stats/README.md), 서버 틱은 spark 또는 `/carpet profile`의 MSPT로 비교한다.

## 1. Velocity 뒤 백엔드 압축

FabricProxy-Lite를 사용하므로 플레이어는 Velocity에 접속한다([레시피 동기화 기록](RECIPE_SYNC_FIX_2026-09-18.md)).
플레이어와 Velocity 사이의 압축은 `velocity.toml`의 `[advanced]` 설정이 결정한다.
백엔드 `server.properties`의 `network-compression-threshold`는 백엔드와 Velocity 사이 연결에만 적용된다.
이 연결을 압축하면 Velocity가 해제한 뒤 다시 압축하므로 CPU를 두 번 쓴다.

| 조건 | 권장 설정 | 효과 |
| --- | --- | --- |
| 백엔드와 Velocity가 같은 호스트나 LAN에 있음 | 백엔드 `network-compression-threshold=-1` | 백엔드 압축, Velocity 해제·재압축 CPU 제거. 플레이어가 받는 바이트는 Velocity 설정으로 결정되므로 같다. |
| 백엔드와 Velocity가 원격 링크로 연결됨 | 백엔드 값 유지 | 원격 링크 전송량 증가를 피한다. |
| 플레이어 방향 전송량을 더 줄여야 함 | Velocity `compression-level` 상향 검토 | 압축률 대신 프록시 CPU 사용량이 늘어난다. 해제 결과는 같다. |

적용 전 [Velocity 설정 문서](https://docs.papermc.io/velocity/configuration)의 현재 권장값과 운영 배치를 확인한다.
백엔드와 프록시 사이 소켓 바이트는 패킷 통계 도구의 `wireBytes`로 전후를 비교한다.

## 2. BlueMap 렌더 스레드

BlueMap은 렌더 스레드를 일반 우선순위로 실행한다(`RenderManager.java:328-335`).
기본 스레드 수는 코어와 힙에 따라 1~3개다(`BlueMapConfigManager.java:142-151`).
region 파일이 저장될 때마다 변경 영역을 다시 렌더하며, Chunky 사전 생성 중에도 같은 렌더가 이어진다.

- `config/bluemap/core.conf`의 `render-thread-count`를 물리 코어 여유에 맞춘다.
  서버 메인 스레드와 청크 작업 스레드를 뺀 나머지만 배정한다.
- Chunky 사전 생성 중에는 `/bluemap stop`으로 렌더를 멈추고, 끝난 뒤 `/bluemap start`로 재개한다.
- `/bluemap update`와 `force-update`는 서버 스레드에서 월드 저장을 실행한다(`FabricWorld.java:58-82`). 한가한 시간에 실행한다.

지도 갱신 시점만 달라지고 게임플레이는 같다. MSPT를 렌더 중·중지 상태로 비교해 효과를 확인한다.

## 3. Chunky 사전 생성

Chunky는 JVM 속성 `-Dchunky.maxWorkingCount`로 동시 생성 청크 수를 제한한다(기본 50, `GenerationTask.java:25`).
플레이어가 접속한 상태에서 사전 생성하면 이 값을 낮춰 틱 경합을 줄인다.
생성 결과는 같고 완료 시간만 늘어난다.

## 4. Carpet scarpet 앱 점검

scarpet 앱은 저장소가 아닌 서버 월드 폴더(`world/scripts`)에 있다.
`__on_tick`에서 매 틱 도형·패킷을 보내는 앱이 있는지 `/script` 목록과 파일을 점검한다.
Carpet 로거의 HUD 패킷은 `/log`를 구독한 플레이어에게만 초당 최대 1회 전송되며 기본값은 구독 없음이다.

## 5. 클라이언트·서버 최적화 모드 설정

| 모드 | 판단 |
| --- | --- |
| Lithium 0.12.1 | 모든 `mixin.*` 기본 활성. 꺼진 항목(`ai.nearby_entity_tracking`, `world.block_entity_ticking.support_cache`, `experimental.*`, `gen.cached_generator_settings`)은 저자가 동등성을 보장하지 않거나 오류로 끈 것이므로 유지한다. WorldEdit이 있으면 `block.hopper.worldedit_compat`가 자동으로 켜진다. |
| FerriteCore 6.0.3 | 선택 옵션(`useSmallThreadingDetector`, `compactFastMap`, `populateNeighborTable`)은 속도 이득이 없거나 위험하므로 기본값을 유지한다. |
| Starlight 1.1.3 | 설정 없음. 제거는 다른 광원 엔진으로 바꾸는 것이라 동작이 같다고 보장할 수 없어 유지한다. |
| ModernFix | 운영 기준본은 5.17.0이지만 빌드·배포본은 소스 빌드 `5.17.1-beta.5+mc1.20.4.6c6e`이다(`inventory/build-recipes.json`). 이 버전 문자열은 git 태그 거리와 해시로 만들어진다. 지침 문서만 추가한 커밋 `6c6e57a` 때문에 beta.4에서 beta.5로 바뀌었고, 코드는 2026-09-21 측정 클라이언트의 5.17.1-beta.4(`4790968`)와 같다. 추가 조치는 없다. |
| ModernFix `mixin.perf.faster_item_rendering` | GUI 아이템의 보이지 않는 면을 생략해 인벤토리 FPS를 높일 수 있다. 저자가 "아이템이 GUI에서 사라지거나 평면으로 보일 수 있다"고 명시했고 이번 작업 환경에서는 실제 클라이언트로 비교할 수 없었다. 따라서 기본값(꺼짐)을 유지한다. |

`faster_item_rendering` 채택 절차는 다음과 같다.
1. 일회용 클라이언트 프로필에서 [크리에이티브 인벤토리 감사](../tools/creative-inventory-probe/README.md)를 옵션 꺼짐·켜짐으로 각각 실행한다.
2. 모든 검색 탭 아이템의 첫 프레임과 리로드 후 스크린숏을 픽셀 단위로 비교한다.
3. 차이가 없을 때만 `config/modernfix-mixins.properties`에 `mixin.perf.faster_item_rendering=true`를 적용한다.

## 6. 채택하지 않은 항목

| 항목 | 이유 |
| --- | --- |
| Krypton 0.2.6 추가 | LGPL-3.0으로 포함은 가능하다. 1번 설정을 적용하면 백엔드 압축 자체가 없어져 효과가 거의 없다. FabricProxy-Lite 등 네트워크 파이프라인 모드와의 호환성도 검증되지 않았다. 모드 목록 변경은 별도 결정 사항이다. |
| `sync-chunk-writes=false` | 저장 속도는 빨라지지만 서버 장애 시 데이터 보존성이 약해져 동작이 같지 않다. |
| ModernFix `remove_spawn_chunks`, `remove_chat_signing` | 게임 동작이 바뀐다. |
| ModernFix `dynamic_resources` | Fusion·Continuity와 알려진 문제가 있고 FPS가 아닌 시작 시간·메모리 최적화다. |
