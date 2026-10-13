# Minefed 이미지와 리소스 로딩 및 서버 지연 감사

2026년 10월 13일 기준으로 **기능과 화질을 유지하면서 개선할 여지가 있다.**
가장 강한 실행 증거는 WebStreamer의 반복 이미지 로딩과 긴 전체 리소스 재로딩이다.
서버에는 전차선 ID 검색, 자동 저장과 지도 연동 계산을 개선할 후보가 있다.
운영 서버의 `ticks behind` 원인과 전체 MSPT 개선율은 서버 프로파일을 받은 뒤 확정해야 한다.

## 조사 대상과 측정 범위

- 소스 기준: 상위 `cdab06282cf25e319c1922e3bcec38d7358b6f86`, Minecraft 1.20.4 / Fabric.
  `scripts/mods.py verify --sources`로 기록된 아티팩트 70개와 소스 pin을 확인했다.
  빌드 레시피는 소스 47개와 바이너리 25개이며 실제 로컬 프로필에는 최상위 JAR 72개가 있다.
  서로 다른 집합이므로 숫자를 합쳐 모드 수로 해석하지 않는다.
- 실제 클라이언트: Modrinth `client`, 팩 `20261012140108`, 배포 명세상 Java 17.
  로컬 설치 명세의 상위 소스는 `67c81d63115fb9ad7a3047b1b166eb6b147e6e95`다.
  최신 저장소와 운영 설치가 모두 같다고 가정하지 않았다.
- 사용자 확인 서버: Podman `minefed_fabric_1`, GraalVM JDK 21 이미지,
  Java PID 1 / UID 0. 운영 서버 모드 해시·설정은 미확인이고, 후속 전달된 JFR은
  0바이트여서 유효한 tick 프로파일은 아직 확보하지 못했다.
- 전체 인벤토리와 기존 최적화 이력을 확인하고, 증상과 연결된 이미지·모델 리로드·MTR·MSD·
  BlueMap·C&B·PFM 등의 실행 경로를 집중 분석했다. 모든 모드의 모든 실행 경로를
  동적으로 디버깅 완료했다는 의미는 아니다. 바이너리 전용 모드는 설치 JAR와 로그를 사용했다.
- 최초 분석은 기존 코드와 로그를 읽어 수행했다. 이후 적용한 중복 클라이언트팩 제거는
  마지막 절에 별도로 기록한다. 운영 서버 파일·설정·업로드·재시작, 새 게임 실행과
  운영 A/B 성능 측정은 하지 않았다. 게임 연결 도구는 unavailable이었다.

## 실제로 확인한 지연

클라이언트 로그의 시각은 초 단위다. `Game took`은 모드가 기록한 시작 시간이고,
리소스 표의 종료점은 **블록 아틀라스 생성 로그**다. 조작 가능한 화면까지의 전체 시간과 다르다.

| 실행 | 기록된 시작 시간 | 초기 리로드부터 아틀라스까지 | 서버팩 적용부터 아틀라스까지 |
| --- | ---: | ---: | ---: |
| 10월 12일 23시 실행 | 175.027초 | 90초 | 49초 |
| 10월 13일 02시 실행 | 118.070초 | 59초 | 54초 |

서버팩 제거는 종료 시 리로드 시작만 있고 완료 로그가 없어 소요 시간을 산정할 수 없다.
10월 6일의 시작 시간 85.215~109.060초, 접속 리로드 44~51초 기록도 존재한다.
장면·JVM·OS 캐시·주변 부하가 통제되지 않은 과거 기록이므로, 이 차이를 최근 변경의
인과적 회귀율로 계산하지 않는다.

WebStreamer는 10월 12일 23시부터 13일 02시까지 이어진 것으로 보이는 자정 분할 로그를 분석했다.
두 번째 파일에는 새 시작 메시지가 없으며 02:22:43에 종료된다.

| 이미지 지표 | 관측값 |
| --- | ---: |
| 사용된 서로 다른 PNG URL | 43개 |
| 이미지 레이어 생성 | 1,137회 |
| 성공 업로드 로그 | 928회 |
| HTTP 요청 타임아웃 | 186회, 실패 URL 40개 |
| 생성부터 업로드 로그까지 중앙값 / p95 / 최대 | 7초 / 21초 / 148초 |
| 10초 초과 성공 업로드 | 282건 |
| 업로드 전에 제거된 레이어 | 209개 |

대상 호스트는 모두 `cdn.minefed.team`이다. 지연은 대기열·통신·디코딩·렌더 대기·게임 중단을
포함하며, CDN 단독 응답시간이나 실제 GPU 업로드 완료시간이 아니다. 다음 실행의 최신 로그에는
HTTP timeout이 0회여서 모든 실행에서 동일하게 발생하는 상시 장애로 단정할 수 없다.

## WebStreamer 이미지 캐시와 작업 대기열

근거 코드는 `fabric-webstreamer/src/main/java/fr/theorozier/webstreamer/` 아래에 있다.
설치 JAR의 바이트코드에서도 timeout·retry·eviction 설정을 확인했다.

| 경로와 줄 | 동작 | 영향 |
| --- | --- | --- |
| `display/render/DisplayLayerSimple.java:24,48` | 15초 미사용 시 texture 정리 | 5초 정리 주기와 합쳐 약 15~20초 뒤 재로딩 가능 |
| `display/render/DisplayLayerMap.java:29` | 정리한 레이어를 맵에서 제거 | GPU 자원을 돌려줄 때 다운로드 원본도 잃음 |
| `display/render/DisplayLayerResources.java:36` | 공유 작업 스레드 2개 | 이미지·URL 조회·HLS·일부 정리가 같은 큐에서 경쟁 |
| `display/render/DisplayLayerImage.java:50,83` | HTTP 요청과 디코딩을 작업 스레드에서 수행, 요청 5초 제한 | 큐 대기시간은 5초 제한에 포함되지 않음 |
| `display/render/DisplayLayerImage.java:28,69` | 실패 후 30초 재시도 대기 | 5초 실패와 합쳐 재시도 시작까지 약 35초 이상 가능 |

원본 PNG 캐시와 GPU texture 캐시를 분리하는 것이 우선이다. 바이트 예산이 있는 LRU,
동일 URL 요청 합치기, ETag·Last-Modified 등 갱신 검증으로 이미지 변경 기능을 보존한다.
이미 보유한 원본은 GPU texture만 복원하고, 통신·CPU 디코딩·정리를 별도 예산으로 관리한다.
실제 보이는 이미지를 우선하고 일시 실패에는 단계적 backoff를 적용한다.
timeout만 길게 늘리면 작업 스레드 점유가 길어져 대기열이 악화될 수 있다.

**조건부 예상:** 43개 이미지가 변경되지 않고 캐시에 모두 들어간다면 1,137회 레이어 생성 중
반복 1,094회에 대한 cold fetch 기회, 즉 최대 96.2%를 없앨 수 있다.
이는 실제 다운로드 수나 게임 전체 시간의 96.2% 개선을 뜻하지 않는다.
캐시 적중 재표시 1초 미만은 구현 후 검증할 목표이며 현재 보장값이 아니다.

각 cold 이미지가 정확히 1초 걸린다는 단순 가정에서는 43개 마지막 완료가 작업자 2개일 때
22초, 6개일 때 8초다. 약 64% 단축의 산술 예시이며 회선·CDN·CPU 한계나 우선순위를 반영한
실게임 예측이 아니다. 모두 5초에 실패한다면 마지막 초기 실패까지 110초와 40초다.
작업자 증설은 캐시·중복 요청·취소와 함께 검증해야 한다.

`DisplayLayerImage.java:32,58,73`은 Future 결과를 정상 tick에서만 회수하고 STB 메모리를 해제한다.
다운로드 도중 레이어가 제거되면 cleanup override가 없어 작업이 계속되고, 이후 성공한 native
buffer의 해제 경로를 잃을 수 있다. 취소·완료 경쟁까지 고려한 명시적 메모리 소유권이 필요하다.
209개 조기 제거가 모두 누수라는 뜻은 아니다. RGBA 누수 이미지 한 장의 크기는 폭×높이×4로,
4096×2560이면 40MiB이며 실제 누수 수량은 별도 계측 대상이다.

과거 실패 이미지 3개를 2회씩 GET한 현재 검사에서는 HTTP 200이 6/6,
TTFB 0.162~1.100초, 전체 전송 0.269~1.281초였다. HTTP/1.1 curl 경로이며 게임의 Java
HttpClient와 같은 연결 실험이 아니다. 과거 CDN·회선·DNS·Java 연결 상태 중 어느 것이
timeout을 일으켰는지는 아직 구분할 수 없다.

PNG 요청과 수명 코드는 2022~2024 upstream에서 이어졌다. 최근
`58fa06bbe8fa3e7c22a4dd426093e2b72880fc58` 등 변경은 HLS 프레임·FFmpeg·버퍼 정리 위주이며
PNG HTTP 경로를 직접 바꾸지 않았다. 최근 최적화가 PNG timeout을 도입했다고 단정하지 않는다.

## 시작과 서버팩 적용 때의 전체 리소스 재로딩

실제 최상위 설치 JAR에는 모델 JSON **77,203개**, blockstate JSON **18,653개**,
PNG **9,606개**가 있다. 중첩 JAR·바닐라·런타임 생성 자원을 제외한 정적 집계이며,
실제로 베이크한 모델 수 또는 각각의 CPU 비용을 뜻하지 않는다.
모델 JSON 상위는 Yuushya 18,871개, Rechiseled 13,855개, Handcrafted 12,394개다.

| 적용 중 팩 | ZIP 크기 | 파일 수 |
| --- | ---: | ---: |
| 로컬 Minefed 팩 | 799,511 bytes | 117 |
| 최근 내려받은 서버팩 | 798,136 bytes | 121 |

96파일은 바이트까지 같고, 공통 파일 중 19개가 다르다. 그중 18개는 JSON 공백·개행 차이뿐이다.
의미가 다른 공통 파일은 MTR pending migration 등록이며, 서버팩에 두 차량의 팬터그래프
모델·PNG·properties 총 6파일이 추가된다. 로컬에만 있는 2파일은 고지 문서다.
서버팩을 거절하거나 무조건 동일하게 취급하면 차량 표시가 달라질 수 있다.

변경의 대부분이 MTR 차량 리소스인데 일반 블록 아틀라스를 포함한 전체 리로드가 다시 실행된다.
따라서 단순 ZIP 축소보다 **변경 없는 모델 처리의 재사용과 리로드 범위 제한**이 더 큰 후보다.
팩을 먼저 정확히 동기화하고, 유효 리소스와 순서·메타데이터가 같은 경우의 무변경 처리 또는
MTR 전용 변경의 선택적 갱신을 검토한다. 팩 동일화만으로 바닐라 리로드가 자동 생략되지는 않는다.
실제 1.20.4 `ServerResourcePackLoader.reload`는 provider 교체 뒤 전체 reload를 호출하며,
`ReloadableResourceManagerImpl`은 기존 manager를 닫고 새 manager와 전체 listener 목록을 실행한다.
Fabric의 listener 의존 순서 API는 namespace별 안전한 부분 갱신 API가 아니다.
리스너 의존성, 서버팩 상태 응답, 리소스 manager의 수명, 적용·제거·실패 복구를 검증해야 한다.

접속 리로드의 49~54초 구간에 줄일 잠재력이 있지만, 이를 전부 제거하거나 특정 완료시간을
달성한다고 아직 약속할 수 없다. 최초 실행도 이 조치만으로 동일하게 빨라지지 않는다.
최초 실행에는 변경 없는 JSON 파싱·모델 데이터 공유 등 별도 개선이 필요하다.

`minefed-client-compat`의 `BlockAtlasSpriteMixin.java:43`과 `AtlasSpriteOptimizer.java:151,202`는
리로드마다 픽셀을 검사한다. 입력 지문별 결과 캐시는 개선 후보다. 다만 최신 접속 로그에서는
리로드 시작 4초 뒤 optimizer가 완료되고 아틀라스는 54초 뒤 생성된다.
후속 작업량과 경합이 같다는 가정에서 앞 구간 자체의 직접 절약은 약 4초 이내다.
메모리·worker 경합 변화까지 포함한 전체 개선의 절대 상한은 아니다. 현재 증거로 이 최적화를
50초 지연의 주원인으로 돌릴 수 없다. 현재 블록 아틀라스 로그는 8192×4096×4다.

Yuushya의 모델마다 128상태를 순회하던 문제는 이미 맵 lookup으로 개선되어 있다.
과거 문서의 큰 개선율을 이번에 추가로 얻을 수치로 재사용하지 않는다.
ModernFix의 `dynamic_resources`는 현재 비활성이고 Fusion·Continuity도 설치되어 있으므로,
켜기만 해서 기능 유지가 보장된 해결책으로 계산할 수 없다.

## 서버 tick 지연 후보

정상 목표는 초당 20 tick, 한 tick의 시간 예산은 50ms다.
이는 정상성 기준이며 현재 서버의 측정 결과가 아니다.
[spark의 tick 설명](https://spark.lucko.me/docs/guides/The-tick-loop).

### 전차선 ID 검색

MSD의 `fabric/src/main/java/top/mcmtr/core/operation/MSDDataRequest.java:23,32`는
가까운 전차선마다 ArrayList의 `contains`를 호출한다. `MSDDataResponse.java:26,28`도
각 객체에 keep-ID 선형 검색을 한다. 목록 형식은 generated schema에 정의되어 있다.
10월 12일 keep-only graph 재구축 생략에 도달하기 전에도 이 검색 비용은 남는다.

N개를 모두 보유한 경우 목록 비교 수는 N(N+1)/2다. 5,000개면 12,502,500회다.
패킷 배열과 순서를 유지하면서 처리용 HashSet을 한 번 만들면 평균 O(N)으로 줄일 수 있다.
청크 로딩 후 500ms batch 요청이므로 이동·접속 때 의미가 있으며, 항상 초당 두 번 보내는
고정 polling이라고 해석하면 안 된다.

실제 MTR shaded fastutil을 사용한 **독립 검색 kernel** 측정 결과는 다음과 같다.
Ryzen 7 7730U / Java 17.0.20.1, 임의 16자리 문자열, 40회 warmup 후 21회 중앙값이며,
HashSet은 매 요청 생성 비용을 포함한다.

| ID 수 | ArrayList | HashSet 생성과 조회 | 해당 부분 감소 |
| --- | ---: | ---: | ---: |
| 1,000 | 1.450ms | 0.190ms | 86.9% |
| 5,000 | 42.931ms | 0.427ms | 99.0% |
| 10,000 | 217.174ms | 0.822ms | 99.6% |

실제 월드·거리 검색·JSON·네트워크·운영 GraalVM 21의 측정이 아니다.
전체 MSPT가 99% 낮아진다는 뜻은 아니다. 서버 검색은 2024년 코드부터 존재해 최신 회귀와 구분한다.

### 자동 저장과 지도 계산

MTR `fabric/src/main/java/org/mtr/mod/Init.java:257`과 `generated/config/ServerSchema.java:12`에서
기본 `useThreadedSimulation=false`이면 simulator를 메인 서버 tick에서 실행한다.
MTR와 MSD는 30초 자동 저장을 요청한다. 실제 Core 바이트코드의 `FileLoader.save`는
스냅샷·pack/hash·변경 파일 쓰기와 삭제를 호출 스레드에서 수행한다.
모든 파일을 무조건 다시 쓰는 구조는 아니다. MSD는 접속 해제 때도 저장을 요청한다.

변경 revision, 불변 저장 snapshot과 순서가 보장된 writer로 메인 tick의 파일 I/O를
분리할 수 있다. 저장 간격·실패 처리·종료 flush·복구 의미를 그대로 유지해야 한다.
30초 주기 지연과 JFR 파일 I/O를 맞춰보기 전에는 절약 ms를 산정할 수 없다.

최근 MTR `bluemap/BlueMapLiveBridge.java:302`는 `simulator.run`에 캡처 작업을 넣는다.
Core의 이 큐는 simulator tick 안에서 시간 예산 없이 처리된다. 차량 500ms,
도착 2초, 정적 geometry 30초 간격의 계산이 기본 설정에서는 메인 tick에 올라갈 수 있다.
파일 쓰기 자체는 전용 I/O worker에서 하므로 쓰기까지 동기라고 설명하면 부정확하다.
`BlueMapSnapshot.java:117,342,460`에서는 노선 탐색과 1블록 간격 geometry가 반복 생성된다.

정적 geometry를 데이터 revision마다 재사용하면 변경 없는 시간의 전체 재생성을
최대 약 120회/시간에서 최초 1회로 줄일 수 있다. 최소 snapshot만 simulator에서 만들고
나머지 처리를 worker로 옮기는 방안도 가능하다. 동적 갱신 주기와 자료 일관성은 유지해야 한다.
bridge 도입은 10월 12일이며 **운영 서버 배포 여부 미확인**이다. 기존 증상의 원인으로
선정할 수 없고, 최신 JS 웹 화면 최적화가 서버 계산까지 해결한 것도 아니다.

BlueMap 본체 렌더는 별도 worker이며 서버 CPU·디스크와 경합할 가능성을 확인해야 한다.
수동 지도 update 등의 `FabricWorld.persistWorldChanges`는 서버 executor에서 저장을 실행한다.
이를 평상시 매 tick 실행하는 것으로 해석하지 않는다. Oritech의 레시피 조회도 후보지만
실제 기계 수와 프로파일 비중을 보기 전에는 이득을 수치화할 수 없다.

## 추가 클라이언트 병목

C&B 로그에는 모델 큐 2,048/2,048과 누적 dropped 15,006이 기록되어 있다.
15,006은 요청 수이며 서로 다른 블록 수가 아니다. 설치 JAR와 현재 로컬 빌드의 해시도 일치한다.
`core/src/main/java/mod/chiselsandbits/client/model/data/ChiseledBlockModelDataExecutor.java:128`은
큐가 차면 새 위치의 요청을 완료 콜백만 실행한 뒤 버린다. 이는 중복 제거와 별도 카운터다.
청크 로딩·상호작용 경로는 NOOP 콜백을 쓰며 폐기된 위치의 재시도를 보장하지 않는다.
초기 modelData가 없는 블록은 NullBakedModel을 반환하므로 새 사건이 발생할 때까지
표시가 누락될 가능성도 있다. 실제 누락 블록 수는 로그만으로 확정할 수 없다.
`utils/ModelDataUpdateCoalescer.java:73`은 매 선택마다 대기 목록 전체의 우선순위를 계산한다.
생산 coalescer를 직접 실행한 검사에서 2,048개를 비우며 scorer를 **2,098,176회** 호출했다.
이는 게임 CPU 시간 측정은 아니지만 큐가 길어질 때의 추가 작업을 입증한다.
취소할 불필요한 요청과 반드시 처리할 최신 상태를 구분하고, 누락 없는 재시도 및 제한된
우선순위 계산을 검토한다. 단순 큐 확장만으로 해결하면 계산량과 메모리를 더 늘릴 수 있다.

PFM `common/src/main/java/com/unlikepaladin/pfm/runtime/PFMGenerator.java:149`의
`HashCode.fromBytes(stream.readAllBytes()).toString()`은 해시 계산이 아니라 원본 전체의 hex 변환이다.
설치 공식 JAR에서도 확인했다. 현재 1,911파일의 원본 842,344 bytes에 대해 캐시 JSON은
1,701,171 bytes다. 값 부분을 SHA-256으로 바꾸면 1,684,688자에서 122,304자로 92.7% 줄어든다.
전체 JSON 감소율 또는 시작시간 감소율이 아니다. `TextureReloadQueue.java:126`의
클라이언트 스레드 전체 캐시 쓰기와 `levelRenderer.allChanged()`도 합치거나 범위를 줄일 수 있다.
1.7MB 캐시만으로 54초 리로드를 설명할 수는 없다. 공개 배포는 공식 PFM 바이너리 정책이므로
선택적 호환 mixin 등 배포 방식까지 확인해야 한다.

SVG의 PNG 인코딩 후 STB 재디코딩 왕복은 직접 RGBA 복사로 대체할 여지가 있다.
합성 SVG의 픽셀 동일성 비교에서 변환 부분은 1024×640 기준 38.693→3.605ms,
4096×2560 기준 491.540→52.140ms였다. 이는 로컬 CPU 변환 실험이고 현재 PNG timeout 해결책은 아니다.
별도 Minefed Display의 30초 브라우저 폐기 정책도 재표시 지연을 만들 수 있지만 이번 대상은
WebStreamer PNG로 확인되었으므로 원인에서 구분한다.

## 개선 수치를 해석하는 방법과 구현 순서

| 우선순위 | 작업 | 현재 근거로 제시할 수 있는 수치 |
| --- | --- | --- |
| 1 | WebStreamer 원본 캐시와 GPU 수명 분리, 요청 합치기·취소 | 불변 43개 캐시 적중 조건에서 반복 cold fetch 기회 최대 96.2% 제거 |
| 1 | 클라이언트 리로드 단계 계측과 변경 범위 제한 | 현재 접속 아틀라스 구간 49~54초, 제거 가능한 비중은 프로파일·구현 검증 필요 |
| 1 | 운영 서버 JFR와 로그의 지연 시점 대조 | 서버 전체 MSPT/TPS 개선율은 아직 계산 불가 |
| 2 | MSD ID lookup을 처리용 HashSet으로 변경 | 독립 5,000-ID kernel 42.931→0.427ms, 전체 tick과 구분 |
| 2 | C&B 누락 없는 backpressure와 우선순위 계산 개선 | 2,048개 drain의 2,098,176 scorer 호출이 개선 대상 |
| 2 | 서버 저장과 정적 지도 snapshot 작업 축소 | 정적 재생성 약 120회/시간→최초 1회와 실제 변경 시점 |
| 3 | PFM digest/비동기 기록, sprite 결과 캐시, SVG 왕복 제거 | 값 저장량·특정 변환 단계의 수치만 확인, 게임 전체 개선율 미측정 |

전체 실행시간 예측은 병목의 비중을 알아야 한다. 전체의 p 비중인 단계를 s배 빠르게 만들면
새 시간 비율은 `(1-p)+p/s`다. **가정 예시:** 120초 중 60초인 단계가 2배 빨라지면
전체는 90초, 25% 감소다. 서버 60ms tick 중 20ms가 2ms로 줄면 42ms가 된다.
두 예시의 입력값은 이 서버의 측정값이 아니며 목표 TPS 20 달성이나 FPS 배수를 약속하지 않는다.

기능 유지 검증에는 PNG 갱신·재접속·차원 전환·취소 경쟁, 모델/UV/픽셀 동일성,
서버팩 적용·제거·실패 복구, 전차선 추가·삭제·동일 ID 교체와 저장 복구를 포함한다.
전후 비교는 동일 JAR·팩·JVM·월드·인원·동선으로 반복하고 p50/p95/p99와 실패 수를 함께 본다.
기존 10월 12일 최적화의 작업량 감소와 과거 한 장면의 FPS 결과는 이번 개선 예상치에 더하지 않는다.

## 서버 자료 수집

후속 전달본은 `minefed-container-stats.txt`만 287 bytes이고, 로그 두 파일과
`minefed-perf.jfr`은 각각 0 bytes였다. 통계의 메모리 12.05GB / 33.14GB는 컨테이너
메모리이며 Java 힙 사용량이 아니다. CPU 19.93%는 `--no-stream` 첫 표본이므로
순간 부하를 판정하는 데 쓰지 않는다. 현재 자료로 CPU·디스크·GC 병목을 배제할 수 없다.
[Podman 첫 CPU 표본 설명](https://github.com/podman-container-tools/podman/issues/25709).

현재 사용자의 `podman-compose`는 `ps -q fabric`을 지원하지 않아 컨테이너 이름을 직접 사용한다.
`jcmd -l`에는 도구 자신만 표시되었지만 `/proc`에서 서버 PID 1 / UID 0을 확인했다.
다음 직접 attach에서 `Started recording`이 확인되면 5분 동안 평소 부하를 기록한다.
기록 완료 후 `jfr summary`가 유효한 이벤트 표를 출력한 경우에만 복사한다.

```bash
podman exec --user 0 minefed_fabric_1 jcmd 1 JFR.start \
  name=minefed_perf_retry settings=profile duration=300s filename=/tmp/minefed-perf-retry.jfr
# Started recording 성공을 확인한 경우에만 아래를 실행
sleep 310
podman exec --user 0 minefed_fabric_1 jfr summary /tmp/minefed-perf-retry.jfr &&
podman cp minefed_fabric_1:/tmp/minefed-perf-retry.jfr ./minefed-perf-retry.jfr
podman exec minefed_fabric_1 sh -c 'cat /proc/1/cwd/logs/latest.log' > minefed-latest.log
timeout 30s podman stats --interval 2 minefed_fabric_1 > minefed-stats-stream.txt
wc -c minefed-perf-retry.jfr minefed-latest.log minefed-stats-stream.txt
```

재시작은 필요 없고 profile 기록은 측정 부하를 추가한다. JFR에서 `Server thread`,
simulator·FileLoader·BlueMapSnapshot·MSDDataRequest, GC 정지와 파일 I/O를 확인한다.
로그의 tick 경고와 시각을 맞추며, 컨테이너 CPU 제한·메모리/스왑과 경쟁 worker도 구분한다.
[Oracle Java 21 jcmd 문서](https://docs.oracle.com/en/java/javase/21/docs/specs/man/jcmd.html),
[Podman cp 문서](https://docs.podman.io/en/latest/markdown/podman-cp.1.html),
[Podman compose provider 설명](https://docs.podman.io/en/latest/markdown/podman-compose.1.html).

원시 로그·URL·프로파일은 공개 Git에 넣지 않는다. 비식별 집계와 계산 근거는
`inventory/performance-audit-2026-10-13.json`에 기록한다. 유효한 서버 프로파일이 없는 현재는
운영 지연의 원인 규명과 모든 문제의 해결이 완료된 상태가 아니다.

## 후속 클라이언트팩 수정

사용자 요청에 따라 중복 Minefed ZIP만 클라이언트 패키징과 새 인스턴스 기본 선택에서 제거했다.
기존 로컬 프로필의 `minefed-20261012140108.zip`은 프로필 밖에 백업한 뒤 제거하고,
`options.txt`의 해당 선택만 해제했다. Foliage·내장 팩·나머지 개인 옵션·서버 다운로드 캐시와
모드 JAR는 보존했다. 패키징 테스트 43개가 통과했으며 서버용 리소스팩 출력은 유지된다.
변경 내역은 `inventory/client-resourcepack-server-only-2026-10-13.json`에 기록했다.
이 조치는 위 조사의 중복 팩 상태를 변경하지만, 전체 리로드 생략이나 시간 개선은 별도 실측 대상이다.
