# MTR 서버 시작 시 Mixin 변환 오류 수정

## 원인

릴리즈 `20260912202910`의 `mods/fabric-4.0.5.jar`는 Fabric Loader 최신 버전을
조회하는 빌드 설정으로 컴파일됐다. 새 Mixin API는 `@Redirect.at`을 배열로 기록한다.
운영 로그의 Loader 0.18.4에 포함된 MixinExtras 0.5.0은 이 값을 단일
`AnnotationNode`로 읽으므로 `Siding` 변환에서 `ClassCastException`이 발생한다.
동일한 방식으로 컴파일된 `Vehicle` 속도 제한 mixin도 영향을 받는다.

Codex의 **서버 RX TX와 FPS 최적화 찾기** 작업에서 이 문제를 수정한
`7075255dd3aa62badb254fb9003a122869dd272b`가 별도 MTR 체크아웃에 있었지만,
모드팩이 사용한 소스 pin `3cdeeeb2951dfd1d9f2ddfe28dd4844e0b732e0e`에는
반영되지 않았다. 해당 호환성 수정과 회귀 검사를 현재 통합 소스에 이식한다.

## 변경

- MTR의 컴파일용 Fabric Loader를 0.18.4로 고정하고 최신 버전 자동 조회를 제거한다.
- 서버팩과 mrpack의 Loader 선언도 실제 변환 검사를 통과한 0.18.4로 맞춘다.
- 속도 제한 기능을 유지하면서 `@Redirect.at`의 호환 가능한 형식으로 컴파일한다.
- 모드팩의 MTR 빌드가 `:fabric:verifyMixinCompatibility`를 실행하도록 한다.
  이 작업은 `remapJar`에 의존하며, 완성된 배포 JAR에서 모든 등록 mixin의 어노테이션
  형식과 두 속도 제한 주입 대상의 존재를 확인한다. 실패하면 팩 생성을 중단한다.
- JDK 21 Gradle 데몬의 `file.encoding=COMPAT`로 Windows 한글 경로의 테스트
  워커 인자 파일을 읽을 수 있게 한다. Java 소스 인코딩은 기존 UTF-8 설정을 유지한다.
  `COMPAT`의 의미는 [OpenJDK 설명](https://inside.java/2021/10/04/the-default-charset-jep400/)을 따른다.

대상은 Minecraft 1.20.4 / Fabric / MTR 4.0.5이며 Java 17 바이트코드를 유지한다.
추적 브랜치는 `codex/fix-mixin-loader-compatibility`이고 전체 커밋은
[`139b0170d9065673767d7caa988847505c310ca0`](https://github.com/minefed/Minecraft-Transit-Railway/commit/139b0170d9065673767d7caa988847505c310ca0)이다.
원격에 올린 이 커밋을 인벤토리와 상위 gitlink에 고정한다.

## 검증 범위와 적용

기존 릴리즈에서 직접 추출한 실패 JAR의 SHA-256:
`2dead745c073e2c44b6ef1325e74317fc4248774952147b35719a38f0ceb8cd4`.
실제 Fabric Knot / Loader 0.18.4 / MixinExtras 0.5.0으로 로그와 같은 오류를 재현했다.

수정 JAR의 SHA-256은
`6eba7fb9602c1428e4d0861ae8810c5b7e7183ba28bb5c46b71b97780fe713ad`이다.
45개 회귀 테스트와 최종 remap JAR 검사 3개를 통과했다. 실제 Knot에서도
Loader 0.18.4 / MixinExtras 0.5.0 및 Loader 0.19.5 / MixinExtras 0.5.5 각각
`Siding`, `Vehicle`, `VehicleExtraData`, `PathDataSchema` 변환 검사를 통과했다.
구·신 JAR의 10,132개 파일을 비교했을 때 두 speed-limit mixin 클래스와
`META-INF/MANIFEST.MF`만 달라졌고, 나머지 10,129개 파일은 내용이 같다.

수정팩은 MTR만 새 소스 pin과 필수 검증 task로 다시 빌드한다. 다른 45개 소스
빌드 JAR와 21개 바이너리는 검증된 기존 distribution의 바이트를 승계한다.
승계 대상의 소스 상태와 레시피가 동일한지 대조하고, 원래 `compiledRun`과
`buildTools` 및 기준 ZIP의 SHA-256을 `ASSEMBLY-PROVENANCE.json`과
`BUILD-PROVENANCE.json`에 보존한다. 모든 모드를 현재 빌드 도구로 다시
컴파일한 것으로 표기하지 않는다.

수정본은 서버와 클라이언트에 같은 MTR JAR를 포함한다. 기존 요청의 모든 모드 동봉,
Modern Lights 2.5.0 양쪽 포함, TCPShield의 서버 `plugins/` 포함 정책을 유지한다.
교체 시 서버를 정상 종료하고 기존 `mods/fabric-4.0.5.jar`를 수정 JAR로 교체한다.
동일한 `mtr` 모드 ID의 구버전 JAR를 추가로 남겨 두지 않는다.

Knot 검사는 실제 클래스 변환을 확인하지만 Minecraft 서버 main, 월드, 운영 서버를
시작하지 않는다. 전체 모드팩의 게임 플레이 검증과 구분하여 기록한다.
