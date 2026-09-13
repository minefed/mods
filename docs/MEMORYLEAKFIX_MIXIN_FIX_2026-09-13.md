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

## 적용

수정된 `client.mrpack`을 새 프로필로 가져오거나, 기존 프로필을 종료한 뒤
`mods/memoryleakfix-fabric-1.17+-1.1.5.jar` 한 개를 수정 JAR로 교체한다.
동일한 모드 ID를 가진 구·신 JAR를 함께 두지 않는다.

당장 수정팩을 사용할 수 없다면 해당 프로필에서 MemoryLeakFix만 비활성화하면
이 Mixin 오류를 우회할 수 있다. 전체 모드팩의 다른 시작 오류나 게임 플레이까지
해결되었다는 뜻은 아니며, 추가 오류가 있으면 새 로그로 확인한다.
