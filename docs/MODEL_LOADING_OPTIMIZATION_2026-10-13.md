# 모델 로딩 추가 최적화 검증 — 2026-10-13

`minefed-client-compat` 1.6.0에서 블록 상태의 모델 선택, 표준 회전 계산, Scena의 일반 모델 JSON 중복 파싱을 줄였다. 실제 모드팩을 실행한 비교에서 조사한 42,651개 모델의 출력은 시작·팩 적용·팩 해제 세 단계 모두 일치했다. 시간 측정은 실행 간 편차가 커서, 이 문서는 개별 측정값과 검증 범위를 공개하고 일정한 전체 로딩 개선율을 보장하지 않는다.

이 작업은 앞선 [성능 감사](PERFORMANCE_AUDIT_2026-10-13.md)의 후속 클라이언트 모델 로딩 개선이다. 비교 기준선에는 기존 1.5.0의 PFM·atlas 개선 등이 이미 포함되어 있다. 이번 결과를 최초 모드팩 대비 누적 개선율로 해석하면 안 된다. 운영 서버의 파일 변경·업로드·재시작과 사용자 런처 프로필 교체는 이 검증에서 수행하지 않았다.

| 산출물 | 확인값 |
| --- | --- |
| 모드 / 버전 | `minefed-client-compat` 1.6.0 |
| 통합 브랜치 | `main` — 원격 push 확인 |
| 소스 커밋 | `ec5f7204ce10188f87e7d6cb3a59d69bcd114a14` |
| JAR | `minefed-client-compat/build/libs/minefed-client-compat-1.6.0.jar` |
| SHA-256 | `6adcf9280c8d71f31163c7069b9e92f7e3302f235c0b30c388f09b243e1004dc` |
| 크기 | 68,893 bytes |
| 호환성 | Minecraft 1.20.4 / Fabric / Java 17 이상 |
| 라이선스 | 독립 호환 모드 MIT; 공식 모드·검증용 바이너리의 기존 라이선스는 별도 유지 |

교체용 파일은 로컬 [minefed-model-loading-patch-20261013.zip](../build/model-loading-20261013/minefed-model-loading-patch-20261013.zip)에 준비했다. 기존 여섯 모드 최적화 묶음 중 compat 1.5.0만 1.6.0으로 교체하는 패치이며, 같은 mod ID의 JAR를 두 개 남기면 안 된다. 소스·바이너리·ZIP 해시와 검증 근거는 [출처 기록](../inventory/model-loading-optimization-2026-10-13.json)에 보관했다. 기존 Yuushya Foliage Addon과 설정은 유지하며, 중복 클라이언트 Minefed 팩은 계속 제외한다.

JAR의 CRC, Java 17 class 버전, 신규 Mixin의 클라이언트 전용 등록을 확인했다. Minecraft 서명 stub, 검증용 클래스, Gson·Guava·JOML 의존성 클래스는 배포 JAR에 포함하지 않는다. Scena가 설치되어 있다면 검증한 1.0.141만 허용하며, 다른 버전은 재검토 없이 적용되지 않도록 메타데이터에서 차단한다.

세 변경의 범위는 다음과 같다. 텍스처 해상도나 픽셀, 모델 JSON을 낮추거나 전체 리소스 리로드를 건너뛰는 변경은 없다.

| 변경 | 줄이는 작업 | 유지하는 동작과 메모리 범위 |
| --- | --- | --- |
| 블록 상태 variant 선택 | 같은 상태 목록을 각 variant마다 전부 검색하는 반복 | 바닐라가 파싱한 조건으로 후보를 좁힌 뒤 원래 predicate를 다시 실행한다. 상태 순서, 등록, 중복 모델 오류 처리를 유지한다. 작은 목록·지원하지 않는 값은 기존 검색을 사용한다. 로딩 스레드별 최근 인덱스 한 개, 최대 32,768개 상태·262,144개 속성 소속 관계를 보관한다. |
| 표준 모델 회전 | 같은 축·각도·rescale 조합의 quaternion/matrix 계산 | signed zero를 구분한 36개 조합을 사용한다. 가변 원점은 매번 읽고 matrix/scale은 복사하여 원래 vertex transform을 호출한다. 비표준 각도, null, 비유한 수와 극단적인 좌표는 기존 메서드를 사용한다. |
| Scena의 loader 없는 JSON | provider 세 개가 같은 일반 모델의 JSON tree를 반복 생성하는 작업 | 매 호출 현재 내용을 다시 읽는다. 전체 내용이 정확히 같고 기본 Gson 2.10.1 정책에서 유효한 object이며 최상위 `loader`가 없을 때만 판정을 재사용한다. 최대 256개·추정 보관 payload 2 MiB이며 모델·Sprite·Reader·Gson·리소스팩 객체는 보관하지 않는다. |

Scena의 custom loader, 잘못된 JSON, object가 아닌 입력, 다른 Gson adapter 또는 lenient 설정은 원래 파서가 처리한다. 캐시 적중 때는 새로운 빈 `JsonObject`를 반환하여 Scena의 기존 null-result 분기로 보낸다. 보관 한도를 넘는 입력은 이미 읽은 prefix를 포함해 원래 파서에 전달한다. 2 MiB는 보관하는 문자열과 항목의 추정 예산이며, 임시 버퍼·파서 할당까지 합친 순간 heap 상한은 아니다. 실제 구현과 적용 조건은 [하위 저장소 README](../minefed-client-compat/README.md)에 기록했다.

기능 비교와 시간 측정은 별도 실행으로 나누었다. 모델 해시 생성은 많은 모델을 추가 호출하므로 기능 비교 실행의 시간은 아래 성능 표에 사용하지 않았다. 테스트 구성은 실제 모드 72개와 검증용 probe 한 개, Minecraft 1.20.4 / Fabric Loader 0.18.4 / Java 17 / `-Xmx8G`였다. 신규 `minefed-regions` 모드는 이 구성에 포함하지 않았다. 비교용 게임 디렉터리에서 동결한 입력을 사용했으며, 기능 비교에서는 변경 대상과 probe를 제외한 비교 대상 입력 225개가 일치했다.

시작 시간은 JVM 기동 후 타이틀 화면의 로딩 종료를 확인할 때까지의 uptime이다. 런처 자체 실행, 로그인 인증, 런처의 모드·게임 파일 다운로드 시간은 포함하지 않는다. 팩 적용·해제는 이미 로컬에 있는 서버팩 사본 `probe-server-pack.zip`을 선택 목록에 추가·제거하고 Minecraft의 리로드 완료를 기다린 시간이다. 서버 접속, 서버의 팩 전송, HTTP 다운로드·캐시, 서버 지연은 포함하지 않는다. 따라서 실제 접속 시 기다리는 총시간과 동일한 측정은 아니다.

`correctness-base3`와 `correctness-candidate2`를 비교했다. 각 단계에서 블록의 기본 상태 21,898개와 아이템 모델 20,753개, 합계 42,651개를 조사했다. seed `0`, `1`, `42`, `Long.MIN_VALUE` 각각에 대해 여섯 방향과 방향 없는 quad를 조회했다. 모델의 네 Boolean flag와 particle Sprite ID, quad의 vertex 정수 데이터·tint·방향·shade·Sprite ID를 해시에 포함했다.

| 기능 비교 단계 | 모델 수 | 조회한 quad 수 | 순서를 포함한 모델 해시 불일치 | quad 순서만 정규화한 해시 |
| --- | ---: | ---: | ---: | --- |
| 시작 완료 | 42,651 | 6,098,910 | 0 | 일치 |
| 로컬 팩 적용 후 | 42,651 | 6,099,014 | 0 | 일치 |
| 로컬 팩 해제 후 | 42,651 | 6,098,910 | 0 | 일치 |

초기 비교에서 관찰한 아이템 모델 1,990개의 quad 순서 차이는 최종 재실행에서 해소되었다. 최종 판정은 순서 정규화 결과만으로 차이를 무시한 것이 아니라 순서를 포함한 해시도 일치한 결과에 근거한다. 정규화는 같은 seed·방향 그룹 안에서 완전한 quad 레코드의 순서만 바꾸며, vertex 값이나 float 정밀도를 바꾸지 않는다. 기존 리소스 경고는 전후 86개로 수와 대상이 같았다. 이는 새 경고가 늘지 않았다는 비교이며 기존 86개 문제가 해결되었다는 뜻은 아니다. 별도의 showblock 구조 검사도 단계마다 129개를 확인했다.

이 검증은 기본 블록 상태와 아이템의 해당 `getQuads` 출력 동등성이다. 모든 블록 상태 조합, 모든 난수 seed, 월드·블록 엔티티 데이터에 따라 달라지는 모델, Fabric Renderer API의 별도 emit 경로, 아이템 override·변환 전체, 셰이더·광원·투명도 합성 및 최종 화면의 모든 픽셀을 검증한 것은 아니다. 전체 화면 품질 검증이나 장시간 플레이 검증과 구분해야 한다.

실제 클라이언트에서도 Scena 캐시가 사용됨을 확인했다. 아래 적중·미스 수는 단계별 차분이며, 원본 로그의 카운터는 누적값이다.

| 단계 | 캐시 적중 | 캐시 미스 | 단계 종료 보관 항목 | 단계 종료 추정 보관 bytes |
| --- | ---: | ---: | ---: | ---: |
| 시작 완료까지 | 146,968 | 90,607 | 256 | 127,798 |
| 팩 적용 | 147,023 | 90,609 | 256 | 127,798 |
| 팩 해제 | 146,968 | 90,607 | 256 | 127,798 |

캐시 미스는 캐시 조회를 수행한 입력의 미스다. 정책 fallback과 초과 크기 입력 등 모든 파서 호출의 총수를 나타내는 것은 아니다. 공식 Scena bytecode 회귀 검사에서는 독립적인 Gson을 사용하는 provider 세 개의 일반 모델 호출을 1회 tree 파싱과 2회 적중으로 처리했다. 이 호출 묶음에서 tree 파싱 횟수는 66.7% 줄지만, 파일 읽기와 custom model 역직렬화·bake는 계속 수행한다. 이전 JFR 분석의 `Scena-platform` 카테고리 포함 표본은 팩 적용 100/3,379개(약 2.96%), 해제 100/3,922개(약 2.55%)였다. 분모는 각 단계의 `jdk.ExecutionSample` 수이며 카테고리는 서로 겹칠 수 있다. 실행 표본 비율을 CPU 시간이나 전체 리로드 시간의 엄밀한 상한으로 환산하거나 전체 모델 비용의 85~90%가 이 캐시로 제거된다고 해석할 수 없다.

별도의 bytecode·경계 검사는 다음과 같이 통과했다. 이 결과 역시 전체 클라이언트 속도 개선율을 뜻하지 않는다.

| 검사 | 결과와 범위 |
| --- | --- |
| Variant 순수 알고리즘 | 80개 완전 조건 질의에서 원래 predicate 호출 327,680회 대비 4,175회. 부분·빈 조건, alias·중복 속성, 127을 넘는 Integer, 순서, 목록 교체, 예외와 지원 밖 입력도 비교했다. |
| Variant 실제 Mixin | Minecraft 1.20.4의 원래 파싱·predicate·중복 처리·forEach를 유지하면서 두 주입이 적용됨을 확인했다. |
| Rotation | 원본·변경 코드 19,392개 비교, 표준 조합 36개, 동시 worker 6개. 유한 결과는 raw float bit가 일치했고 원점 변경과 transform hook의 가변 인자도 검사했다. |
| Rotation NaN 경계 | 비유한 입력은 변경하지 않은 원래 메서드로 보낸다. JIT 실행에서는 원래 경로에서도 NaN payload/sign 변동이 관찰되어 NaN의 모든 비트 동일성을 주장하지 않는다. 별도 interpreter 실행에서는 엄격한 NaN payload 비교도 통과했다. |
| Scena | 공식 1.0.141 bytecode에 배포 Mixin을 적용한 61개 검사 통과. 내용 변경, custom loader·Gson 정책, 비정상 입력, prefix 보존, I/O 예외, Reader 소유권과 캐시 예산을 포함한다. |
| 기존 호환 기능 | PTS recipe, PFM 동작·첫 texture upload·캐시, TrafficCraft, atlas의 기존 검증도 통과했다. |
| 상위 저장소 도구 | 최종 테스트 146개 중 145개 통과, 환경 조건에 따른 1개 skip. 실패 없음. 실행 약 150.7초. |
| 전용 서버 Mixin audit | 로컬 dedicated-server 환경의 Mixin 전환 검사 `RESULT PASSED`, 5,819 ms. 운영 서버 적용·재시작을 수행한 것은 아니다. |

최종 서버 검사 원문은 `.cache/performance/20261013-model-loading/server-mixin-audit.log`에 보관한다.

검증용 Minecraft·Scena JAR는 병렬 빌드 worker의 우연한 Gradle 캐시에 의존하지 않도록 별도로 준비한다. 공식 client, Fabric intermediary, TinyRemapper, Scena를 크기·SHA-256으로 고정하고 로컬 `build/compatibility-fixtures`에만 둔다. 다운로드와 생성 결과를 검증한 뒤 receipt를 마지막에 게시하며, 소스 빌드 receipt에도 이 입력·출력 fingerprint가 포함된다. 이 바이너리는 릴리스팩에 추가하지 않는다.

기존 Loom merged fixture와 official-client/TinyRemapper 0.10.3 fixture는 원시 class bytes가 다르므로 두 개의 완전한 SHA 집합을 구분해 고정했다. 네 대상 클래스의 61개 메서드, 53개 필드, 2,376개 명령어, 18개 예외 처리 구간을 비교하고 여섯 개 변조 대조 검사도 수행했다. 정규화 대상은 source·line·local-variable debug 데이터와 parameter 이름(개수·flag는 유지), verifier frame 표기, 명령 위치 label, 정확히 지정한 Fabric CLIENT marker 및 5건의 빈 Nullable annotation descriptor 치환이다. 정규화 후 실행 명령·멤버·제어 흐름·예외 범위의 동등성을 확인한 것이며, reflection으로 관찰하는 모든 메타데이터까지 완전히 같다는 주장은 하지 않는다. 두 fixture에서 실제 모델 Mixin 프로브를 각각 통과했다.

시간 측정의 단위는 초이며, 원본은 밀리초로 보관했다. 각 실행의 시작·팩 적용·팩 해제는 모두 같은 순서로 진행했다. B는 기준선 1.5.0, C는 후보 1.6.0이다.

아래 표는 `-Xmx8G` 조건에서 완료한 다섯 실행 전부다. 앞선 `-Xmx6G` 탐색 실행 `timing-b1`은 시작 290.387초·적용 174.323초 이후 해제까지 완료하지 못한 채 중단되어 비교에서 제외했다. 초기 probe 수정 과정과 모델 해시 생성 실행 역시 시간 통계에 섞지 않았다.

| 실행 순서 | 실행 | 시작 | 팩 적용 | 팩 해제 | 해석 |
| ---: | --- | ---: | ---: | ---: | --- |
| 1 | B1 (`timing-base1`) | 216.937 | 117.598 | 132.476 | 다른 완료 실행보다 현저히 느림. 원인 확정 없이 보존한다. |
| 2 | C1 (`timing-candidate1`) | 131.651 | 52.202 | 48.828 | 완료 |
| 3 | B2 (`timing-base2`) | 132.796 | 52.604 | 53.316 | 완료 |
| 4 | C2 (`timing-candidate2`) | 130.972 | 48.411 | 49.760 | 완료 |
| 5 | B3 (`timing-base3`) | 311.912 | 106.455 | 107.870 | 완료. 호스트 메모리 압박·다른 Java 동시 실행을 관찰했다. |

B3 실행 중에는 사용 가능 물리 메모리가 약 432 MiB로 낮았고, 공유 빌드 잠금 밖의 다른 Java 프로세스도 관찰되었다. 호스트 메모리 압박과 동시 작업이 있었음을 확인한 관찰이며, 이것만으로 B1·B3 지연의 단일 원인을 확정하지 않는다. 입력 파일이 같아도 OS 캐시·메모리·다른 프로세스의 상태까지 동일했다고 볼 수 없다.

다섯 실행 모두 팩 적용·해제 완료와 단계별 showblock 129개 검사를 통과했다. 전체 개별값을 유지하되, 느린 B1·B3의 영향을 받은 중앙값 차이를 최적화의 인과적 개선율로 사용하지 않는다. 가까운 실행 구간만 탐색적으로 비교하면 B2 대비 C1/C2 중앙값은 시작 132.796→131.312초(약 1.12% 감소), 적용 52.604→50.307초(약 4.37%), 해제 53.316→49.294초(약 7.54%)다. 이는 기준선 한 회와 후보 두 회를 선택한 참고 비교이며, 전체 표본의 대표 추정치·통계적 유의성·반복 가능한 보장 수치가 아니다. 세 최적화 각각의 시간 기여도도 이 묶음 비교만으로 분리할 수 없다.

| 최종 집계 | 시작 중앙값 | 적용 중앙값 | 해제 중앙값 |
| --- | ---: | ---: | ---: |
| 전체 기준선 B1/B2/B3 | 216.937 | 106.455 | 107.870 |
| 전체 후보 C1/C2 | 131.312 | 50.307 | 49.294 |

전체 중앙값은 관측 요약이다. 큰 실행 편차와 호스트 압박 때문에 이 차이를 성능 개선율이나 보장값으로 사용하지 않는다. 인접 실행의 작은 차이 역시 다른 작업과 메모리 압박을 통제한 환경에서 재현 확인이 필요하다. 이번 보고서를 위해 추가 시간 측정은 시작하지 않았다.

서버의 `ticks behind`, 월드 틱 처리, 이미지 HTTP 다운로드·캐시, 운영 서버 접속 시 팩 전송 시간은 이번 모델 로딩 비교의 측정 대상이 아니다. 이 보고서만으로 해당 문제가 모두 해결되었다고 판정하지 않는다. 또한 신규 모드나 모델 관련 Mixin이 원래 회전 메서드 또는 variant predicate의 의미를 바꾸는 경우에는 고정한 모드팩 범위 밖이므로 다시 검증해야 한다.

근거 자료는 로컬 `.cache/performance/20261013-model-loading/`에 보관한다. `canonical-summary.json`은 최종 기능 비교, `correctness-base3/`와 `correctness-candidate2/`는 원본 digest와 단계별 결과, `timing-summary.json`과 각 `timing-*` 디렉터리는 시간 측정, `new-probes.log`·`scena-probes-retry.log`·`rotation-final-*-summary.json`은 회귀 검사, `fixture-probes/client.log`·`fixture-probes/loom.log`와 하위 저장소의 `build/model-fixture-equivalence-probe/`는 fixture 동등성 근거다. `artifact-verified.json`은 최종 JAR 확인 기록이다. 이전 Scena JFR 비율의 근거는 `.cache/performance/20261013-implementation/baseline-b1/jfr-phases.json`의 `phases`에서 `pack-apply`·`pack-remove` 각각의 `overlappingCategories.Scena-platform`과 `events.jdk.ExecutionSample`이다. 중간 파일과 최종 집계에 있는 단순 중앙값 차이 비율은 인과적 성능 개선율로 사용하지 않는다. 원문 런처 인자나 사용자·서버 식별 정보는 이 문서에 복사하지 않았다.
