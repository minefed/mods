# Minecraft Mod MCP 관찰용 클라이언트 구성

Minecraft 1.20.4 / Fabric 클라이언트에서 사용자가 보는 화면과 상태를 읽기 위해
`mcpmod` **0.3.0+minefed.1**을 포함한다. 서버에 접속하는 봇이나 서버 모드가 아니다.
클라이언트 팩에만 포함하며 설치 후 Minecraft를 완전히 종료하고 다시 실행해야 한다.
원본 `mcpmod` JAR와 동시에 넣지 않는다. Modrinth·Codex 전역 설정 변경이나
MCP 브리지 설치는 이 저장소의 빌드·패키징 작업에 포함되지 않는다.

검증한 로컬 산출물은 `minecraft-mcp-1.20.4-fabric-0.3.0+minefed.1.jar`, 938350 bytes이며
SHA-256은 `2352c0f58e0f6ed6c6ac757736fc3e5641077de23a5b2e79e58225bdaf4ebe67`이다.
최종 팩의 정확한 JAR 해시는 해당 팩의 `download-manifest.json`에도 기록한다.

## 원본과 라이선스

- 원본: [langyo/minecraft-mod-mcp v0.3.0](https://github.com/langyo/minecraft-mod-mcp/releases/tag/v0.3.0)
- 소스 ref: `v0.3.0`, 추적 브랜치: `master`
- 전체 소스 커밋: `50e059dccb09a9e23b91833ffdbf42efd97fa6e6`
- 공식 파일: `minecraft-mcp-1.20.4-fabric-v0.3.0.jar`, 920529 bytes
- 공식 SHA-256: `44551aebaf63baf79a4585d2d9330cd21692e61cc573f28604178e1af4c9cd78`
- 소스·바이너리 라이선스: `MIT OR Apache-2.0 OR CC0-1.0` 중 MIT 조건 적용
- 저작권: Copyright (c) 2025 langyo. 세 라이선스 원문과 변경 고지를 모두 보존한다.

원본 JAR에는 독립적인 라이선스 파일이 없다. 정확한 소스 커밋에서 가져온
[원본 라이선스와 변경 고지](../compatibility/minecraft-mcp/NOTICE.md)를 수정 JAR에
내장하고 팩의 `licenses/selected-jars/`에도 포함한다. 원본 JAR를 Git에 넣지 않는다.
전체 SHA-512, 크기, 원본 다운로드 URL, 소스 경로와 컴파일용 Gson 고정값은
[전용 인벤토리](../inventory/minecraft-mcp.lock.json)에 기록한다.

## Minefed 변경

원본 HTTP 서버는 인증 없이 `0.0.0.0`에 바인딩하고 입력·명령 실행 기능도 제공한다.
Minefed는 원본의 `McpHttpServer` 클래스를 Java 17로 다시 컴파일하여 교체하고
정확한 1.20.4 이름으로 플레이어·월드를 조회하는 `ObservationState`를 추가한다.
`ObservationScreenshot`은 1.20.4 `ScreenshotRecorder`와 `NativeImage`를 호출하여
실제 프레임버퍼를 캡처한다. upstream이 FPS 등의 다른 정수를 화면 크기로 잘못
추론하는 문제를 피하고, PNG 인코딩 후 네이티브 이미지를 닫는다.
Fabric 메타데이터에 별도 버전, 라이선스와 1.20.4/Java 17 호환 조건을 명시한다.
그 외 원본 클래스·자원은 바이트 단위로 보존한다. Java 소스와 원본 인벤토리도 JAR에 내장한다.

- 모든 포트 선택 경로에서 **127.0.0.1**에만 바인딩한다.
- HTTP는 아래 정확한 세 경로만 허용한다. 나머지는 404, 잘못된 메서드는 405다.
- 변경 명령·임의 반사 호출·파일 저장·조작 모드·입력 명령은 HTTP 403으로 거절한다.
- 브라우저 Origin 및 비로컬 Host를 거절하고 CORS 허용 헤더를 제공하지 않는다.
- 명령 본문은 16 KiB로 제한한다. 읽기 전용 웹 대시보드나 SSE도 제공하지 않는다.

| 요청 | 용도 |
| --- | --- |
| `GET /api/status` | 버전·Fabric·PID·포트·관찰 모드 확인 |
| `GET /api/screenshot` | `original`, `grid` PNG data URL과 `width`, `height` |
| `POST /api/cmd` | `ping`, `get_player_info`, `get_world_info`, `get_screen_buttons`만 허용 |

명령은 `{"cmd":"get_player_info"}` 또는 `{"method":"get_player_info","params":{}}`다.
스크린샷은 `/api/cmd`에서 허용하지 않고 전용 GET 경로로만 제공한다.
status의 `version`은 `0.3.0+minefed.1`, `minecraftVersion`은 `1.20.4`,
`loader`는 `fabric`, `readOnly`는 `true`, `bindAddress`는 `127.0.0.1`이다.
`minefed-game`의 전용 관찰 어댑터는 이 식별값을 확인한 뒤 연결한다.

기본 포트는 9876이며 사용 중이면 9875부터 9000까지 찾는다.
`-Dmcp.port=9860` 또는 `MC_MCP_PORT`로 고정하면 그 포트만 시도한다.
브리지는 `/api/status`의 PID로 원하는 게임 인스턴스인지 확인해야 한다.
동일 사용자 PC의 네이티브 프로그램에는 인증 없이 조회가 허용되므로
loopback 제한을 운영체제 사용자별 접근 제어로 해석하지 않는다.

## 빌드와 패키징

```sh
python scripts/release_mcp.py --output build/minecraft-mcp
python -m unittest discover -s scripts -p test_release_mcp.py -v
```

JDK 17과 Python 표준 라이브러리를 사용한다. 컴파일에는 해시가 고정된 원본 JAR와
Minecraft 1.20.4의 Gson 2.10.1을 사용하며 Gson은 새 모드에 포함하지 않는다.
실제 Java/HTTP 검사는 `MINEFED_MCP_JAVA_TESTS=1`로 실행한다.
모드팩 패키징은 커밋된 수정 소스만 허용하며 결과 해시·원본·소스 파일 해시를
`download-manifest.json`, `MINEFED-RELEASE.json`, `release-assets.json`에 남긴다.
입력 인벤토리가 패키징 후 바뀌면 게시 검증이 실패한다. 일반 Modrinth 의존성 검사기는
이 GitHub pin을 자동 갱신하지 않으며 새 upstream 릴리스는 별도로 검토해야 한다.

`build-recipes.json`의 기존 47개 소스/25개 바이너리 기준본은 바꾸지 않는다.
패키징 단계가 리소스 호환 모드와 이 관찰용 모드를 추가하여 최종 클라이언트 72개,
서버 68개를 만든다. `server.zip`에는 관찰용 JAR가 들어가지 않는다.

## 검증과 한계

2026-09-26 실제 Java HTTP 테스트에서 loopback 바인딩, 조회 허용, 변경 명령 차단,
Origin/Host 검사, 경로·메서드·본문 제한, PNG 응답과 원본 클래스 보존을 확인했다.
별도 테스트 인스턴스에서 Minecraft 1.20.4 / Fabric Loader 0.18.4 / Java 17 초기화와
상태 조회 및 854×480 PNG 스크린샷 HTTP 200 응답을 확인했다.
임시 싱글플레이 월드에 들어간 후에도 실제 시간·차원·난이도·체력·음식·월드 이름과
854×480 전체 프레임버퍼를 확인했다. 동일 Minefed 모드팩의 별도 실서버 접속 검증에서도
실제 플레이어 좌표·시선·체력·차원·크리에이티브 모드 조회가 정상임을 확인했다.
Java/HTTP/상태/원본 보존 검사는 7개 통과했다. 릴리스 관련 Python 검사는
93개 중 87개 통과·6개 생략했고, 생략된 MCP Java 5개는 위 실제 Java 실행에서 따로 확인했다.
Windows의 일부 기존 테스트 하위 프로세스에서 콘솔 인코딩 경고가 있었으나 검사 실패는 없었다.

로컬 검증 팩 `build/releases/20260926022500/`에서 클라이언트 모드 72개, 서버 모드
68개를 확인했다. `client.mrpack` 안의 MCP JAR는 위 SHA-256과 바이트가 일치하고,
`server.zip`의 모드 파일·manifest에는 MCP가 없다. 원본 MIT 고지 보존, 클라이언트와
서버의 실제 JAR 의존성·충돌 검사, 입력 잠금 파일과 세 배포 파일의 CRC·해시 검증이 통과했다.
이 팩은 로컬 검증 산출물이며 원격 릴리스를 게시하지 않았다.

월드에 들어가기 전 플레이어·월드 조회는 `available:false, error:not_in_world`다.
좌표·시선은 숫자 `x/y/z/yaw/pitch`와 기존 `pos/rotation` 문자열로 함께 반환한다.
시간·난이도·날씨는 클라이언트에 동기화된 실제 값을 클라이언트 스레드에서 읽는다.
원격 서버 월드 이름은 클라이언트가 알 수 없어 `world_name:null, world_name_available:false`다.
필드·메서드를 읽지 못하면 `available:false`를 반환하며 그럴듯한 기본값을 만들지 않는다.
화면 버튼 조회는 upstream 리플렉션 구현이며 모든 모드 화면에서 정확하다고 보장하지 않는다.
이 저장소 작업은 사용자 Modrinth 설치·운영 서버·Codex 전역 설정을 수정하지 않는다.
