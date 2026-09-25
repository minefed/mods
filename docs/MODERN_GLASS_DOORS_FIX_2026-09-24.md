# Modern Glass Doors 리소스 누락 수정 — 2026-09-24

Minecraft 1.20.4 / Fabric / Java 17 모드팩의 Modern Glass Doors 블록이
체크무늬로 보이는 원인은 소스 빌드에서 데이터 생성 단계를 생략한 것이다.

## 확인한 원인

`build/releases/20260918233412/client.mrpack`과 `server.zip`에 포함된
`modern-glass-doors-5.3.0+1.20.3-and-later.jar`는 65,109 bytes이며 SHA-256은
`9fec5fc3f4fc0f72f7ef1c75d6161d3fab0945604b3885140c0c051eb4d5d08f`다.
PNG 텍스처 48개가 있지만 블록 상태와 모델 JSON은 각각 0개다.
같은 버전의 보존된 공식 JAR에는 블록 상태 24개, 모델 156개, 텍스처 48개가 있다.

기존 Gradle 설정은 Git에서 제외된 `src/main/resources_generated`를 포함하기만 하고
`remapJar` 실행 시 `runDatagen`을 호출하지 않았다. 따라서 새 checkout의 일반 빌드에서
블록 상태·모델·레시피·전리품 등의 생성 리소스가 빠졌다. 팩에 동봉된 리소스팩은
이 모드의 자산을 덮어쓰지 않으므로 리소스팩 충돌이 원인은 아니다.

## 수정

생성물을 `build/generated/resources`에서 만들고 JAR 패키징이 데이터 생성에 의존하도록
연결했다. `remapJar`만 호출해도 생성물이 포함된다. CI도 같은 빌드 경로를 사용한다.
`verifyRuntimeResources`는 최종 JAR의 24개 문·다락문의 블록 상태, 모델과 텍스처 참조,
레시피 및 전리품을 검사한다. 원본 MIT 라이선스도 JAR에 포함한다.

모드 버전과 블록 ID는 유지한다. 루트의 `inventory/mods.lock.json`에 있는 운영 기준본
JAR 해시는 역사적 자료이므로 바꾸지 않고, 새 산출물의 해시와 출처는 별도 빌드 기록에 남긴다.

## 소스와 검증

- 추적 브랜치: `codex/fix-glass-door-generated-resources`
- 커밋: `3c65e91eee397e91496f78345165451d86b28932` (origin에서 확인)
- `clean remapJar verifyRuntimeResources`: 통과. 생성 JSON 312개를 포함한다.
- 전체 `build`: 통과. Windows JDK 17의 Gradle worker 인수 파일이 한글 경로를
  MS949로 읽는 환경에서는 해당 실행에만 `-Dfile.encoding=MS949`를 적용했다.
  루트의 `verifyRuntimeResources` 빌드는 기존 UTF-8 설정을 유지한다.
- 최종 JAR: 블록 상태 24개, 모델 156개, PNG 48개 및 원본 LICENSE 포함.
- 게임 안에서 직접 배치하여 확인하는 검증은 수행하지 않았다.

수정된 클라이언트 JAR로 교체하고 게임을 다시 시작하면 새 리소스가 로드된다.
운영 서버 파일 교체나 재시작은 이 작업에 포함하지 않았다.
