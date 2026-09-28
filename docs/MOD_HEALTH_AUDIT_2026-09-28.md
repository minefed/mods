# 모드 빌드와 첫 크리에이티브 표시 검사 — 2026-09-28

대상은 Minecraft 1.20.4 / Fabric Loader 0.18.4 / Java 17이다. 운영 서버와
설치된 Modrinth 클라이언트 프로필은 변경하지 않았다. 실행 검사는 복사한 모드와
설정, 검사용으로 만든 월드를 사용하는 별도 오프라인 프로필에서 수행했다.

## 재현한 원인과 수정

Paladin's Furniture 1.5.0의 헤링본 판자 11종은 크리에이티브 검색 목록에서
처음 그릴 때 보라색 체크무늬였다가 정상으로 바뀌었다. 모델이 첫 렌더링 중
텍스처 이미지를 생성하지만 GPU 업로드는 `END_CLIENT_TICK`까지 미루는 것이
원인이다. 일반적인 모델 조회나 리소스 재로드만 먼저 검사하면 텍스처가 준비되어
이 증상을 놓칠 수 있다.

해당 ID는 `pfm:<wood>_herringbone_planks`이며 wood는 oak, bamboo, spruce,
birch, jungle, acacia, cherry, dark_oak, mangrove, crimson, warped이다.

`minefed-client-compat` 1.1.1은 렌더 스레드에서 이 텍스처가 생성되면 해당
스프라이트만 즉시 업로드한다. 이전 OpenGL 바인딩을 복원하며, PFM의 기존 대기열은
유지해 캐시 저장과 월드 메시 갱신은 원래의 일괄 처리에 맡긴다. 개별 아이콘마다
전체 렌더러를 다시 만드는 방식은 사용하지 않는다. 기존 PTS 레시피 통신 수정도
유지한다. 공식 PFM JAR와 제한된 라이선스의 자산은 수정하거나 복제하지 않는다.

## 함께 발견한 월드 데이터 오류

기존 조합에서 월드에 진입하면 잘못된 레시피 14개, 전리품 테이블 16개,
태그 참조 1개, 가이드북 레시피 9개, 가이드북 아이콘 1개의 진단이 발생했다.

| 대상 | 수정 |
| --- | --- |
| Alloy Forgery | 유리 레시피의 재료 수량 문자열 `"2"`를 숫자 `2`로 고쳤다. |
| Fabric Seasons | 눈이 대체하는 블록 태그의 이전 `minecraft:grass` ID를 1.20.4의 `minecraft:short_grass`로 고쳤다. |
| Minecraft Transit Railway | 아이템이 등록되지 않은 내부 cargo loader/unloader 블록의 전리품을 유효한 빈 풀로 고쳤다. |
| Yuushya Townscape | 1.20.4 선물 상자 레시피의 잔디 ID, 안내서의 현재 석재 절단기 도면 레시피와 도구 레시피 참조를 고쳤다. 공유된 구버전 입력은 그대로 둔다. |
| Exline Furniture | 실제 아이템/블록 등록이 없는 서랍장 11종의 남은 레시피를 로딩 조건으로 제외하고, 서랍장과 대나무 통나무 탁자의 남은 전리품 13개를 빈 풀로 고쳤다. 등록된 가구는 제거하지 않는다. |
| Dusty Decorations | 등록되지 않은 이전 `pot`의 남은 전리품만 빈 풀로 고쳤다. 현재 `cooking_pot`은 유지한다. |
| Japan Props | 찻잔 레시피의 얻을 수 없는 덤불 블록 아이템을 실제 `sweet_berries` 아이템으로 고쳤다. |
| PFM 안내서 | 존재하지 않는 샤워 아이콘을 등록된 `basic_shower_head`로 고쳤다. 설명은 별도로 작성했고 기존 두 제작법을 연결한다. |

마지막 네 항목은 독립적으로 작성한 리소스 전용 호환 모드
`minefed-resource-fixes` 1.1.0에 포함한다. 기존 상자 모델/담장 태그와 합해
허용 목록은 33개 파일이다. 라이선스와 변경 출처는
[`compatibility/resource-fixes/NOTICE.md`](../compatibility/resource-fixes/NOTICE.md)에
기록했다. 원본 JAR의 해시와 운영 기준 목록은 보존했다.

추가 로그 점검에서는 TrafficCraft에 포함된 DragonLib의 위키 조회 두 건이 HTTP
403으로 실패했다. [공식 API 지침](https://www.mediawiki.org/wiki/API:Etiquette#The_User-Agent_header)에
따른 식별 가능한 User-Agent와 연락처 URL을 넣으면 같은 두 항목이 정상 응답했다.
클라이언트 호환 모드 1.1.1의 Mixin으로 해당 Wikidata 요청에만 헤더와 10초 연결/읽기
제한을 적용했다. 전역 HTTP 설정, 다른 주소 및 기존 실패 시 대체 동작은 유지한다.
원본 DragonLib JAR도 변경하지 않는다. 실제 Java 17 요청 코드로 두 항목의
sitelink 수신을 검증하고 최종 게임에서도 언어별 링크 맵을 확인한다.
TrafficCraft의 공식 번들을 선택하는 배포 정책 때문에 별도 호환 모드에서 적용하며,
소스 빌드 TrafficCraft에는 중복 redirect를 등록하지 않는다. 실제 패키지 실행에서
이 선택 차이를 확인한 뒤 수정 경로를 바로잡았다.

수정한 하위 소스는 각각 먼저 커밋해 아래 원격 브랜치로 올리고, 상위 저장소의
gitlink와 소스 목록은 모드별 별도 커밋으로 갱신했다. 모두 동일한
Minecraft 1.20.4 / Fabric 조합의 수정이며 버전 이식은 하지 않았다.

| 소스 | 추적 브랜치 | 고정 커밋 |
| --- | --- | --- |
| alloy-forgery | `codex/fix-glass-recipe-count` | `e4d10145142f7d3dc12effc1b3083723a9d08d4d` |
| fabric-seasons | `codex/fix-snow-grass-tag` | `d5ff75050e02f131ea82fee0e7904e92eb7214f3` |
| Minecraft-Transit-Railway | `codex/fix-cargo-loot` | `e33269ecb041c55503053b72ccec4ec68d7bc01c` |
| Yuushya-Townscape | `codex/fix-survival-data` | `ca14f0658a05e4d53ec302fa01f27de4311359b8` |
| minefed-client-compat | `codex/fix-pfm-first-frame` | `3ac78cb964693b0cbd098e63041f1592d98a99ca` |
| TrafficCraft | `codex/fix-wikipedia-requests` | `69a09747437289bcda71a8bfaa1c72aeca848cad` |

## 검사 범위

하위 저장소 52개 중 현재 Fabric 소스 빌드 대상은 47개다. CityCraft,
Macaw's Doors/Fences는 저장소의 Minecraft 버전 또는 Forge/Fabric 대상이 운영
바이너리와 일치하지 않아 이미 검토된 공식 Fabric 바이너리를 사용한다. RealIP는
별도의 Bukkit/Bungee/Velocity 플러그인이며 Fabric 모드가 아니다. resourcepack은
리소스팩이다. 따라서 52개를 모두 Fabric Java 프로젝트라고 간주하지 않는다.

첫 강제 빌드 `20260928-011940-7de71450`에서는 27개 결과가 검증되었다. MTR의
자체 빌드와 검사는 통과했지만, 이번 전리품 수정과 소스 해시 채집 시점이 겹쳐
상위 빌드의 변경 감지 장치가 해당 결과를 거절했다. 이 실행을 전체 성공으로
계산하지 않았다. 확정한 소스로 남은 대상과 수정된 두 선행 대상을 다시 빌드했다.
47개가 모두 완료된 뒤 위키 조회의 최종 적용 경로를 반영한 TrafficCraft와
클라이언트 호환 모드만 다시 빌드했다.

Yuushya 생성기의 기존 `slab_cube_yellow_wool` 읽기 메시지 3건은 그대로 발생한다.
해당 생성기는 바닐라 부모 모델을 로컬 입력에서 찾지 못하지만, 이 slab 계열은
별도의 블록 구현에서 충돌 모양을 계산한다. 생성 작업은 성공하며 게임의 누락
텍스처 진단과는 구별한다. 근거는 [이전 감사](RESOURCE_AUDIT_2026-09-25.md)의
생성기 분석에 기록되어 있다.

최종 통합 빌드와 실제 배포물 검사 결과는 아래에 확정 기록한다.

## 최종 검증 결과

- 통합 실행 `20260928-043405-06622ed9`: 소스 47개, 바이너리 25개, JAR 72개의 빌드·해시·리소스 포장 검사 성공.
- 도구 테스트 213개: 201개 통과, 12개 조건부 건너뛰기. Windows의 POSIX/심볼릭 링크 제약 및 별도 활성화가 필요한 통합 검사이며, 실제 Fabric 저장소 정책 검사는 별도로 통과했다.
- 운영 기준 JAR 70개와 최종 소스 고정값 재검증 성공. 수정한 하위 소스 6개의 고정 커밋은 모두 원격에서 가져올 수 있다.
- 실제 클라이언트팩의 모드 JAR 72개가 배포 명세의 SHA-256과 모두 일치했다. 여기에 관찰용 검사 모드만 추가한 별도 프로필에서 실행했다.
- 최초 표시와 리소스 재로드 후 각각 검색 탭 스택 18,970개, 396페이지를 완료했다. 후보 이미지를 확인했고 누락 텍스처 체크무늬는 없었다. PFM 11종도 첫 프레임부터 정상이다.
- 수정 전 데이터/안내서 진단 41건은 최종 팩에서 0건이다. 누락 모델·텍스처·스프라이트·블록 상태, 존재하지 않는 사운드 파일 참조 및 잘못된 CTM 진단도 0건이다.
- Macaw 담장의 기존 대각선 모델 변환 경고 14건은 남는다. 실제 월드에서 14종 모두 `diagonalfences:non_diagonal_fences` 태그에 포함됨을 확인했다. 경고를 숨기거나 전체 로그가 경고 없이 통과했다고 처리하지 않았다.
- TrafficCraft의 위키 항목 두 개 모두 실제 게임에서 언어별 링크 맵이 채워졌다. 원본 라이브러리의 403 실패를 재현한 후 검증한 결과다.
- 최종 클라이언트팩: 외부 JAR 72개와 중첩 JAR 138개의 CRC 오류 0건, 일반 클래스 28,579개의 Java 17 초과 바이트코드 0건. 별도 multi-release 클래스 16개는 일반 클래스 수에서 구분했다.

수치, 소스별 전체 커밋·컴파일 실행·JAR 해시, 진단 리소스 ID는
[`검증 기록`](../inventory/mod-health-audit-2026-09-28.json)에 보존한다.

## 완성한 로컬 배포물

버전은 `20260928133356`이다. 클라이언트는 72개 모드, 서버는 68개 모드와
별도 TCPShield 플러그인 1개를 포함한다. 서버 ZIP은 패키징을 검증했으며 운영
서버 또는 별도 Bukkit 서버에서 실행하지 않았다. 설치된 클라이언트 프로필,
운영 서버 파일, 서버 프로세스는 변경하지 않았고 릴리즈 파일을 외부에 업로드하지 않았다.

| 파일 | SHA-256 |
| --- | --- |
| [server.zip](../build/releases/20260928133356/server.zip) | `113446337c4ef5cb35519fb133a4680ad3a1e2e379761e590ce4f97a297ed328` |
| [client.mrpack](../build/releases/20260928133356/client.mrpack) | `df765d9a87697770bd5902a9fb3a279821d2b943dfd38ed0c50916a106235449` |
| [resourcepack.zip](../build/releases/20260928133356/resourcepack.zip) | `35212ed7082891fffe008e3f93a29ef02491ac2b8338924ec592e4d674505239` |

## 재현 가능한 검사 도구

[`creative-inventory-probe`](../tools/creative-inventory-probe/README.md)는 실제
크리에이티브 검색 탭의 스택을 가져와 모델을 미리 조회하지 않고 Minecraft GUI
아이템 렌더러로 그린다. 48개씩 첫 번째와 세 번째 프레임을 비교한 뒤 리소스를
다시 읽고 반복한다. 모든 페이지의 연속성, 예외, 이미지 누락, 재로드 누락은
[`audit_creative_inventory.py`](../scripts/audit_creative_inventory.py)로 검증한다.
월드의 레시피/전리품/태그/안내서 진단은
[`audit_client_log.py`](../scripts/audit_client_log.py)의 `--require-world`로 검사한다.
검사용 모드는 배포물에 포함하지 않는다.

보라색 픽셀 자체를 결함으로 판정하지 않는다. Mishang 회전 도구, Mythic Metals
unobtainium, 자홍색 Chisels & Bits 가방, 애니메이션되는 stormyx 상자 등은 실제로
보라색을 포함한다. 검출된 페이지 이미지를 별도로 확인하며, 해당 ID를 앞으로의
검사에서 일괄 제외하지 않는다. 원본 실행 로그, 월드, 게임 화면은 로컬 `build/`에
두고 공개 기록에는 필요한 수치와 리소스 ID, 해시만 남긴다.

PFM 회귀 검사는 공식 1.5.0의 실제 `requestReload` 바이트코드에 배포되는 Mixin을
적용한다. 기존 지연 업로드 재현, 렌더 스레드의 즉시 업로드, 다른 텍스처/작업
스레드/null 처리 보존, 대기열 보존, 성공과 실패 시 GL 바인딩 복원을 확인했다.
GPU 경계는 격리된 fixture이므로 실제 게임 검사와 함께 해석해야 한다. 기존 PTS
실제 바이트코드 검사도 재료 0/1/3개에 대해 다시 통과했다.

이 검사는 첫 아이템 표시와 리소스 재로드, 통합 서버의 월드 데이터 로딩을
검증한다. 모든 블록 상태의 배치, 모든 모드 기능, 외부 운영 서버 로그인 및
Bukkit 플러그인 실행까지 검증했다는 뜻은 아니다. 배포 도구의 포괄적인
`runtimeValidated: false` 값은 그대로 두고 실제로 실행한 범위를 이 기록에 명시한다.
BlueMap 지도 출력은 검사 프로필의 기본 리소스 다운로드 동의 설정이 꺼져 있어
검증 범위에 포함하지 않았다. 사용자 또는 운영 서버의 동의 설정은 변경하지 않았다.

로그 전체가 경고 없이 실행된 것은 아니다. 선택적 연동 모드의 부재, 일부 refmap과
Mixin 우선순위, 비표준 텍스처 크기에 따른 mipmap 조정, PFM 업데이트 확인 실패 등의
경고는 남는다. 바닐라 네임스페이스의 `item.goat_horn.play`,
`entity.goat.screaming.horn_break`, `entity.generic.wind_burst` 사운드 이벤트 경고도
남으며, 위의 사운드 파일 참조 검사 수치에는 포함하지 않는다. 별도 오프라인 검사
계정의 사용자 속성 조회 401은 실제 계정의 접속 검증을 대신하지 않는다.
