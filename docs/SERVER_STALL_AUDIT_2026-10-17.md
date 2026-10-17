# 2026-10-17 서버 rx 감소·ticks behind 조사

코드상 서버 틱을 오래 점유할 수 있는 경로가 있다. 특히 MTR 교통 정보 계산·저장,
Oritech 채굴 탐색, 디스플레이 크기 변경이 조사 대상이다. **이번 장애의 원인은 아직 미확정**이다.
사용자가 확인한 지표는 클라이언트 F3의 rx이며, 서버에서도 `ticks behind`가 발생한다.
rx는 수신 패킷 수의 평활 평균이며 바이트 전송률이나 TPS가 아니다. Minecraft 1.20.4는
20 connection tick마다 수신 카운터와 이전 평균을 0.25:0.75로 섞는다. 정상 클라이언트에서
약 1초 간격이고 클라이언트 정지에도 영향을 받는다. 같은 시각의 서버 스택·JFR·OS 지표를 확보해야
틱 지연에 따른 패킷 감소와 클라이언트·프록시·청크 전송 문제를 구분할 수 있다.

이번 변경은 조사 기록과 [수집 도구](../tools/server-stall-capture/README.md)다.
모드 기능·운영 서버 파일·설정·JAR·재시작은 변경하지 않았다. 아래 결함도 이번에는 수정하지 않았다.

## 기준과 증거의 한계

- Minecraft 1.20.4 / Fabric. 조사 시작 상위 커밋은
  `774d488375a076d37684e14d15269316787d9636`이다.
- 현재 운영 JAR 해시, 설정, 해당 시점 월드·인원·청크·기계 수는 이번에 확보하지 못했다.
  저장소 HEAD와 실제 설치본이 같다고 가정하지 않는다.
- 소스는 현재 체크아웃, 동적 증거는 [10월 13일 서버 기록](../inventory/server-performance-profile-2026-10-13.json)이다.
  당시 300초 JFR은 10:00:35–10:05:35 KST, 지연 경고는 02:31:41·02:32:48·02:45:24 KST였다.
  로그 본문에 날짜는 없으며, JVM의 명시적 Asia/Seoul 설정으로 시간대를 대조한 자료다.
  서로 겹치지 않으므로 원인 확정이나 개선율 측정 자료로 쓰지 않는다.
- 당시 서버 Java 실행 표본 295개 중 MTR `manualTick` 포함 166개, 그중 지도 도착 정보 포함 83개였다.
  이는 샘플 비중이며 CPU 사용률·벽시간·MSPT 비율이 아니다. 현재 체크아웃에는 10월 13일
  후처리 최적화가 들어 있으므로 83개 전체를 미해결 비용으로 계산하지 않는다.
- 확인 범위는 서버 tick, 저장, 지도·교통 정보, 기계·차량, custom 패킷·지역 검색이다.
  모든 모드의 모든 경로, 서버 월드의 scarpet 앱·데이터팩, 호스트·디스크 문제를 배제한 감사가 아니다.

| 소스 | 확인한 전체 커밋 |
| --- | --- |
| Minecraft-Transit-Railway | `3456308166f1b088ab02c2f225e1d9678c0f22cd` |
| MTR-Station-Decoration-Addon | `3a3f75f37c62327d9064096b01c7166c64bcde32` |
| BlueMap | `eb9265af82412f0bb230615c53e79039a6fecdc8` |
| Oritech | `a3051c0f1ac1eaab0d995f8d1540e49561bc2ac1` |
| Automobility-Refueled | `1c9e6a416d6afb04401277acee195591b7c566c6` |
| minefed-display | `d328cfd27ac8d71a7b293a9604cb7508f8651e4b` |
| minefed-regions | `535fa27a81b12a1468669ef68e43c3e10d4b8563` |

## 우선 확인할 경로

### 1. MTR 교통 정보 계산과 자동 저장

`Minecraft-Transit-Railway/fabric/src/main/java/org/mtr/mod/Init.java:257`의 start-tick에서
`useThreadedSimulation=false`일 때 `main.manualTick()`을 실행한다(:266–267).
이 설정의 기본값은 false지만 운영 설정은 확인해야 한다.

현재 교통 정보는 `bluemap/TransitExporter.java:94`에서 simulator 큐에 넣고,
그 안에서 차량(:98), 노선 geometry(:99), 도착 정보(:102)를 만든다.
차량은 약 500ms, 도착은 2초, infrastructure와 route catalog는 30초 간격이다.
`BlueMapSnapshot.java:306`은 선택 플랫폼마다 최대 128개 도착 정보를 Core에 요청한 뒤
역별 표시 수를 줄인다. 최종 표시가 8개여도 Core의 상세 응답 생성 비용은 남는다.
`BlueMapSnapshot.java:137`의 geometry도 노선·정거장 구간·차량기지 경로를 순회한다.
큐의 pending 플래그는 중복 적재를 막지만 **한 번의 계산 비용을 tick별로 나누지는 않는다.**

이 경로는 `TransitApiConfig.enabled()`가 참일 때 활성화된다. 현재는 BlueMap 설치·렌더 실행과
독립되어 있으므로 `/bluemap stop`만으로 이 계산까지 중지됐다고 판단하면 안 된다.
HTTP 전송은 `TransitApiPublisher`의 별도 sender에서 실행되며, API 응답을 기다리는 작업 자체를
서버 스레드의 동기 네트워크 대기로 분류하지 않는다.

MTR start-tick의 30초 자동 저장(:271–273) 및 MSD 저장도 후보이다.
Core의 `Simulator.save()`는 요청 플래그를 세우고 다음 simulator tick에서 실제 저장을 한다.
기본 단일 스레드 simulation에서는 snapshot·직렬화·변경 파일 저장이 서버 tick에서 실행된다.
모든 파일을 매번 다시 쓰는 것은 아니다. `FileLoader.save` 스택과 JFR FileWrite/FileRead,
같은 시각의 IO pressure를 확인한다. **30초 간격이라는 사실만으로 저장 원인을 확정하지 않는다.**

확인할 스택: `Main.manualTick → Simulator.tick`, `TransitExporter`,
`BlueMapSnapshot.arrivals/infrastructure/routeCatalog`, `ArrivalsRequest`, `FileLoader.save`.
향후 수정 방향은 변경 revision별 정적 결과 재사용, 도착 상세 생성 축소, 불변 저장 snapshot과
순서 보장 writer다. 설정 하나로 threaded simulation을 켜는 것을 무검증 해결책으로 권하지 않는다.

Core의 큐 처리와 저장은 `libs/Transport-Simulation-Core-0.0.1.jar`의 바이트코드로 확인했다.
SHA-256 `5ad8287b07254ae65f6a76ea46ac3eb8e2c83d8192f4c21d2cc75364e5fe02b0`은
`Minecraft-Transit-Railway/patches/dependencies/provenance.json`과 일치한다.
upstream은 `ecde7247f4200a417ff19dd257276f40e666d11b`, 패치 소스 tree는
`848baa4177cee47a9be0cd2f75f932872545cbed`다.

### 2. Oritech 레이저 채굴과 에너지 네트워크

`Oritech/src/main/java/rearth/oritech/block/entity/machines/interaction/LaserArmBlockEntity.java:235`는
다음 채굴 영역을 준비할 때 `(2 × scanDist)³` 블록을 동기 조회하고 후보를 정렬한다.
`:211`에서 영역이 소진된 뒤 재구축하며, `:255`의 raycast도 원거리 블록을 순회한다.
시간 예산이나 로딩된 청크만 검사하는 조건이 없다. 기본 사거리는 128이고 Quarry addon이
탐색 폭을 늘린다. 예를 들어 **scanDist가 실제로 16인 구성이라면** 32,768회 블록 조회가 된다.
이는 현재 서버에 그런 구성이 있다는 뜻이나 실제 지연시간 추정이 아니다.

`EnergyPipeInterfaceEntity.tick`은 에너지가 있는 인터페이스마다 모든 목적지를 순회하고
목록을 섞어 삽입을 시도한다. 대규모 네트워크의 인터페이스 수 × 목적지 수에 비례하는
반복 비용이 있다. 우선 장애 구역에 해당 설비가 있고 로드·tick 중인지 확인한다.
반면 파이프 BFS의 256개 제한, 펌프의 작업 분할, 기존 레시피 snapshot 개선은 이미 존재한다.

확인할 스택: `LaserArmBlockEntity.findNextAreaBlockTarget/basicRaycast`,
`EnergyPipeInterfaceEntity.tick`, 이 호출 아래의 `ServerChunkManager.getChunk` 및 청크 대기.

### 3. minefed-display 크기 변경의 검증 결함

`minefed-display/src/main/java/team/minefed/mods/display/network/DisplayModMessages.java:30–43`은
클라이언트 크기를 서버 스레드의 `resizeDisplay()`에 그대로 전달한다.
`blocks/CustomSizeDisplayBlock.java:158–188`은 그 크기를 사용해 전체 공간 조회·기존 구조 제거·
새 구조 설치를 수행하고, **32 제한은 작업 후** `CustomSizeDisplayBlockEntity.setDisplaySize()`에서
적용한다(:195). 서버에서 작업량을 제한하기에는 늦다. 위치의 거리·로딩 여부 검사도 없다.

정상 GUI는 1–32로 제한하므로 과도한 값의 경로에는 비정상 입력 등이 필요하다.
공격이나 이번 장애의 원인이라는 증거는 없다. 정상 범위에서도 32×31→32×32 변경은
최대 2,016회의 블록 변경과 이웃 알림을 같은 작업에서 실행한다.
NBT 읽기(`CustomSizeDisplayBlockEntity.java:23–35`)도 최소값만 제한하여,
과도한 저장값이 있다면 파괴 시 구조 제거 루프가 커질 수 있다.

이는 코드에서 확인한 입력 검증 결함이다. 후속 수정은 **루프 진입 전** 크기·위치·권한 검증,
NBT 상한 검증 및 정상적인 구조 보존 검사가 필요하다. 운영에 비정상 패킷을 보내 재현하지 않는다.
장애 직전 디스플레이 생성·크기 변경·파괴가 있었는지와 해당 스택을 먼저 대조한다.

## 추가 후보와 제외한 오해

- Automobility `AutomobileEntity.java:578,1087`은 정차 차량에도 충돌 모양·주변 엔티티 검색을 한다.
  차고·C&B 충돌 블록이 밀집한 구역에서는 확인할 후보다. 큰 Displacement 탐색은 client-only이며
  서버 원인으로 세지 않는다. 최근 정차 차량 패킷 최적화는 충돌 계산을 생략하지 않는다.
- minefed-regions는 5틱마다 이동 플레이어의 주소를 지역·정점 순회로 찾는다.
  큰 지도와 다수 이동 플레이어에서는 후보지만 API/캐시 IO는 worker이며 HTTP 대기가 직접 tick을 막지는 않는다.
- MTR 터널·교량의 `RailAction.java:134–160`은 바깥 루프에서 2ms 예산을 검사하지만,
  한 단면의 블록 조회·변경 내부에서 발생하는 긴 청크 로드는 그 예산으로 중단하지 못한다.
  해당 도구 사용 중이면 `RailAction/getChunk` 스택도 확인한다.
- BlueMap `/bluemap update`, `/bluemap force-update`는 `FabricWorld.java:62`에서 서버 executor를 통해
  `world.save(null, true, false)`를 호출한다. 명령 직후의 저장 지연을 확인한다.
  일반 지도 렌더는 worker이고, CPU·IO 경합 가능성과 서버 스레드 실행을 구분한다.
- `worldedit-hang-fix`는 **종료 시** WorldEdit executor를 정리하는 모드다.
  운영 중 큰 WorldEdit 편집으로 생기는 tick 지연을 방지한다는 뜻은 아니다.
- wireless-redstone의 일반 전파는 로드된 수신기를 사용하고 P2P는 로딩 여부를 확인한다.
  mc-realtime에서도 직접적인 외부 통신·대기를 찾지 못했다.
- 클라이언트 이미지 다운로드·모델 로딩 지연은 별도 문제다. 그 사실만으로 서버의
  `ticks behind` 원인을 설명하지 않는다.

## 다음 발생 시 수집

실행 명령과 결과 파일은 [수집 도구 README](../tools/server-stall-capture/README.md)에 있다.
Linux Podman 호스트에서 실행하는 두 명령으로 준비했다.

1. 평소 문제가 나타나는 시간대에 `record`로 10분 JFR과 OS 지표를 기록한다.
2. rx 저하 또는 서버 응답 정지 **진행 중** 다른 터미널에서 `snapshot`을 실행한다.
   서버 콘솔 명령 처리와 별개인 JVM attach를 사용한다. JVM 전체가 응답하지 않으면
   attach도 실패할 수 있으며 타임아웃과 OS 지표를 증거로 보존한다.
3. 발생·회복 시각(KST 또는 UTC), 당시 위치·이동·열차·편집·채굴 여부, 한 명만 영향인지
   모든 플레이어가 같은 현상인지 함께 기록한다. 로그의 시간대도 명시한다.
4. `ticks behind` 경고는 틱이 회복된 뒤 나올 수도 있다. 경고를 본 뒤의 정상 스택 한 장으로
   원인을 제외하지 않는다. 선행 JFR과 연속 덤프가 필요한 이유다.
5. 운영 릴리스 ID와 해당 릴리스 manifest/JAR SHA-256을 함께 확인한다.
   설정은 simulation 여부·transit 활성 여부·BlueMap render 수·view/simulation distance처럼
   관련 항목만 별도로 기록한다. 토큰·전체 환경변수·RCON 비밀번호는 공유하지 않는다.

서버가 응답하는 상태라면 현재 Carpet 코드의 `/profile health 200`으로 평균 tick 시간을
함께 확인할 수 있다. `commandProfile` 설정과 권한에 따라 사용 가능 여부가 달라진다.
200 **완료 tick**을 측정하므로 20TPS일 때 약 10초이며 지연 중에는 더 오래 걸린다.
완전 정지 시에는 이 명령도 처리되지 않아 외부 수집을 우선한다.
근거는 `fabric-carpet/src/main/java/carpet/commands/ProfileCommand.java:21–27`이다.

| 같은 시각의 증거 | 다음 판단 |
| --- | --- |
| 여러 덤프에서 Server thread가 같은 모드 계산을 실행, 관련 JFR 샘플 증가 | 해당 입력 크기·반복 작업을 조사 |
| Server thread가 청크 future/IO를 기다림 | 요청한 모드 스택과 청크 worker·디스크 상태를 함께 조사 |
| 여러 덤프에서 같은 락을 기다림 | 소유 스레드와 순환 대기를 확인; WAITING만으로 교착 확정 금지 |
| GC pause가 장애 구간과 겹침 | 할당·힙·GC 설정 조사; 단순한 GC 총횟수만으로 판정 금지 |
| cgroup `nr_throttled/throttled_usec` 증가 또는 memory/io pressure | CPU 제한·메모리·디스크 경합 조사; 누적값 자체가 아니라 구간 차이를 비교 |
| 서버 tick은 정상이고 특정 클라이언트만 rx 저하 | 클라이언트 정지·프록시·청크 ACK·네트워크 경로 조사 |

`Thread.print`와 profile JFR도 측정 부하가 있다. 덤프는 3회로 제한하며 지속적인
고빈도 전체 덤프, 강제 GC, heap dump는 사용하지 않는다. 수집 JFR·로그·스택에는 경로와
사용자 정보가 들어갈 수 있으므로 로컬 보관 후 공유할 범위를 검토한다.
운영에서 실제로 실행한 수집 결과는 아직 없으며, 준비한 도구의 성공을 장애 해결로 해석하지 않는다.

수집 도구의 실패·timeout·중단·예약 종료 후 파일 복구·해시 불일치 등 단위 테스트 15개를 통과했다.
별도 Java 21.0.12.1 JVM에서도 JFR 옵션·스레드 덤프·녹화 종료와 유효 파일을 확인했다.
이 검사는 Minecraft 월드 실행이나 Linux Podman 전체 연동 검증은 아니다.

## 기존 로컬 진단 모드

작업 시작 시 상위 저장소에 미등록인 `minefed-diagnostics/`가 이미 존재했다.
해당 독립 저장소의 `f9e99a6`과 README를 읽었고 이번 작업에서는 수정·등록·설치하지 않았다.
운영 적용 여부는 미확인이다. 이미 설치돼 있다면 같은 시각의
`logs/minefed-diagnostics/` 보고서와 `/mfdiag status`를 함께 확보하면 도움이 된다.

단, 다음 표현을 원인 확정으로 받아들이지 않는다.

- watchdog의 sleep 지연은 해당 감시 스레드의 실행 지연이다. 그것만으로 전체 JVM 정지,
  GC 원인, 또는 게임 코드와 무관함을 증명하지 않는다. 게임 코드의 할당도 GC를 유발할 수 있다.
- 대기 청크·ACK 수가 줄지 않았어도 이동하면서 새 작업이 추가되면 송수신은 진행 중일 수 있다.
  `CHUNKS_NOT_READY` 라벨은 준비 상태를 직접 검사한 확정 결과가 아니다.
- 스택의 `culprit` 모드 표시는 후보이며 연속 스택·GC·OS 지표로 확인해야 한다.
- `/mfdiag` 자체는 서버 스레드가 처리하므로 완전 정지 시 명령이 지연될 수 있다.
  운영에서 `selftest stall`을 실행하거나 `resetStuckAcks`를 켜는 절차는 이번 수집에 포함하지 않는다.

## 참고

- [10월 13일 조사와 실제 JFR 해석](PERFORMANCE_AUDIT_2026-10-13.md)
- [이미 적용한 최적화와 남은 범위](PERFORMANCE_IMPLEMENTATION_2026-10-13.md)
- [Oracle Java 21 jcmd](https://docs.oracle.com/en/java/javase/21/docs/specs/man/jcmd.html): 같은 JVM 사용자로 attach, JFR 시작·저장·정지와 스레드 덤프.
- [Oracle Java 21 jfr](https://docs.oracle.com/en/java/javase/21/docs/specs/man/jfr.html): summary로 유효한 녹화 확인, 사건 시각의 이벤트·스택 분석.
- [Podman exec](https://docs.podman.io/en/latest/markdown/podman-exec.1.html): 컨테이너 안 사용자와 PID 사용, TTY 없이 결과 수집.
