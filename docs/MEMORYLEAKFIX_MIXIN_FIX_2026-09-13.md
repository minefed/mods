# MemoryLeakFix 클라이언트 시작 오류 수정

## 원인

Minecraft 1.20.4 / Fabric Loader 0.18.4 / Java 17에서 자체 빌드한
MemoryLeakFix 1.1.5의 `hugeScreenshotLeak.Minecraft_screenshotMixin`이
`grabHugeScreenshot`을 찾지 못해 클라이언트 시작이 중단됐다.

문제 JAR에는 common refmap과 `grabHugeScreenshot` → `method_35699` 매핑이
있지만, `memoryleakfix.mixins.json`에 `refmap` 속성이 없다. 따라서 실행 시
Mojang 개발용 메서드 이름이 Fabric intermediary 이름으로 변환되지 않는다.
보관 중인 공식 1.1.5 JAR는 common Mixin 설정에 이 연결이 들어 있다.

별도로 출력되는 빈 Fabric Mixin 설정의 refmap 경고는 공식 JAR에도 있다.
REI 권장 모드 누락과 버전 문자열 경고도 이 로그의 직접적인 종료 원인이 아니다.
누락 경고만 보고 다른 모드를 일괄 제거하거나 Loader를 변경하지 않는다.

## 수정과 재발 방지

- common refmap 이름을 고정하고 common Mixin 설정이 그 파일을 참조하도록 한다.
- `:fabric:verifyMixinRefmap`에서 최종 remap JAR의 활성 common Mixin 등록,
  설정과 refmap의 연결, 스크린샷 관련 intermediary 매핑을 검사한다.
- 상위 모드팩 recipe도 이 검사 태스크를 실행해 실패한 JAR의 수집을 막는다.
- 소스 pin과 내용이 바뀌므로 이전에 저장한 불량 소스 빌드 캐시는 재사용하지 않는다.

이 수정은 Minecraft 1.20.4 / Fabric용 빌드에 적용하며 MemoryLeakFix 버전은
1.1.5를 유지한다. 원래 운영 기준본 JAR의 해시와 공식 출처는 보존한다.

추적 브랜치는 `codex/fix-common-mixin-refmap`이며 원격 커밋
[`f01909746ee3ad595a3ed91e4abb4779a06a47c2`](https://github.com/minefed/MemoryLeakFix/commit/f01909746ee3ad595a3ed91e4abb4779a06a47c2)을
상위 gitlink와 인벤토리에 고정한다. 대응 소스 링크와 라이선스 고지도 갱신한다.

## 빌드 검증

기존 불량 JAR에 새 검사를 적용하면 common refmap 미선언으로 실패한다.
common/fabric clean 빌드와 상위 recipe의 `:fabric:verifyMixinRefmap` 실행은
통과했다. 상위 모드팩 도구 unittest는 156개 실행, 4개 skip, 실패 0개다.

최종 상위 소스 빌드 JAR의 SHA-256:
`cbbb30315f636dade65b080fba4e9a5fd1009842bacf1619868ba43e5249c2f3`.
기존 불량 JAR의 SHA-256:
`cc681cbc0b7c136573d3faee333009c83cbe503e8db2869e5ac4d76556714ea1`.

## 실제 클래스 변환 검증

Java 17 / Fabric Loader 0.18.4 / Mixin 0.8.7 / MixinExtras 0.5.0의 실제
Knot CLIENT에서 클라이언트 모드 65개(중첩 포함 로딩 164개)를 함께 검사했다.
동일한 검사 실행기로 기존 JAR는 사용자 로그와 같은 예외로 실패했고,
최종 JAR는 `class_310`, `class_1959` 변환과 아래 주입 3개를 모두 통과했다.

- `hugeScreenshotLeak`: 스크린샷 버퍼 회수
- `targetEntityLeak`: 클라이언트 대상 초기화
- `biomeTemperatureLeak`: biome 온도 ThreadLocal 처리

Fabric의 표준 Minecraft 바이트코드 패치도 적용한 환경이다. 게임 main과 모드
entrypoint 초기화, 화면 생성, 로그인, 월드 로딩을 실행한 검증은 아니므로
`runtimeValidated`는 `false`를 유지한다.

기존 클래스 28개는 모두 바이트가 같다. 이름을 바꾼 common refmap의 매핑 내용도
같고, common Mixin 설정 2개에 `refmap` 참조가 추가됐다. 독립 clean 빌드 JAR와
상위 recipe 빌드 JAR의 해시 차이는 ZIP 시간 정보이며 각 항목의 내용은 같다.
로컬 상세 결과는 `build/memoryleakfix-crash-20260913/knot-results.json`과
`final-client-all-mods/smoke.log`에 보존한다.

수정팩은 이전에 검증한 distribution에서 다른 66개 JAR를 그대로 승계하고
MemoryLeakFix만 새로 컴파일한 JAR로 교체한다. 승계 JAR의 소스 상태와 recipe를
대조하고 원래 컴파일 실행 ID·도구·기준 ZIP 해시를 `ASSEMBLY-PROVENANCE.json`과
`BUILD-PROVENANCE.json`에 남긴다. 소스 receipt와 이전 distribution은 덮어쓰지 않는다.

## 수정팩

로컬 결과물은 `build/releases/20260913124905/`에 생성했다.

| 파일 | SHA-256 |
| --- | --- |
| `client.mrpack` | `d07016f83f41a8ad9c1167d24d4a9e928b7589944492eadfe01649b567911ff3` |
| `server.zip` | `f2b2910f3d64f4a37351302145d3023a084d954f20da3d97b0bf7fc7de55f737` |
| `resourcepack.zip` | `25a4bbe70479eba94462540d92edd3a05482d9d94915581a6c886454bf68e83e` |

서버 모드 67개, 클라이언트 모드 65개의 JAR 해시와 오프라인 설치 검사,
두 팩에 포함된 수정 refmap을 확인한다. 이전 팩과 다른 모드 JAR는 MemoryLeakFix
하나이며 플러그인과 리소스팩의 내용은 유지한다. Windows에서 보존된 고지 경로까지
압축 해제하는 검사는 확장 길이 경로(`\\?\`)를 사용한다.
공개 릴리즈 게시와 운영 서버 변경은 수행하지 않는다.

## 적용

수정된 `client.mrpack`을 새 프로필로 가져오거나, 기존 프로필을 종료한 뒤
`mods/memoryleakfix-fabric-1.17+-1.1.5.jar` 한 개를 수정 JAR로 교체한다.
동일한 모드 ID를 가진 구·신 JAR를 함께 두지 않는다.

당장 수정팩을 사용할 수 없다면 해당 프로필에서 MemoryLeakFix만 비활성화하면
이 Mixin 오류를 우회할 수 있다. 전체 모드팩의 다른 시작 오류나 게임 플레이까지
해결되었다는 뜻은 아니며, 추가 오류가 있으면 새 로그로 확인한다.
