# Minecraft Mod MCP 전체 조작 클라이언트

Minecraft 1.20.4 / Fabric용 `mcpmod` **0.3.0+minefed.2**는 원본 게임 조작 기능을 모두 노출한다.
이전 `.1`의 관찰 전용 명령 제한은 사용자의 요청에 따라 제거했다. 클라이언트 전용이며
서버 모드나 별도 봇 계정이 아니다. JAR를 교체한 후 게임을 완전히 종료하고 다시 실행해야 한다.
동일 `mcpmod` ID의 원본·이전 버전 JAR와 중복 설치하지 않는다.

## 원본과 빌드
- 원본: [langyo/minecraft-mod-mcp v0.3.0](https://github.com/langyo/minecraft-mod-mcp/releases/tag/v0.3.0)
- 고정 소스: `50e059dccb09a9e23b91833ffdbf42efd97fa6e6`, 추적 브랜치 `master`.
- 원본 JAR SHA-256: `44551aebaf63baf79a4585d2d9330cd21692e61cc573f28604178e1af4c9cd78`.
- 배포 입력·라이선스·컴파일 의존성은 `inventory/minecraft-mcp.lock.json`에서 관리한다.
- 라이선스는 MIT 선택이며 원본 MIT/Apache-2.0/CC0 원문과 변경 고지를 모두 보존한다.
- `compatibility/minecraft-mcp`의 변경 소스는 JAR에도 포함된다.
- 최종 해시·크기·소스 커밋은 생성된 `minecraft-mcp-build.json`과 모드팩 manifest가 기준이다.

```sh
python scripts/release_mcp.py --output build/minecraft-mcp
python -m unittest discover -s scripts -p test_release_mcp.py -v
```

Java 17을 사용한다. 개발 빌드에는 `--allow-uncommitted`를 쓸 수 있지만 배포 패키징은
커밋된 소스·잠금 파일만 허용한다. 실제 Java/HTTP 검사는 `MINEFED_MCP_JAVA_TESTS=1`로 실행한다.
기존 pack record의 `artifact: observation` 키는 manifest 호환을 위해 유지하며,
현재 기능은 `readOnly:false`와 `.2` 버전으로 구분한다.

## 연결과 기능
기본 주소는 `127.0.0.1:9876`이다. 자동 포트 선택 및 `-Dmcp.port`/`MC_MCP_PORT` 지원은 유지한다.
외부 Origin/Host는 거부하고 같은 출처의 로컬 웹 대시보드는 허용한다.

| 경로 | 기능 |
| --- | --- |
| `GET /api/status` | 버전·PID·포트·`readOnly:false`·`controlMode` |
| `GET /api/screenshot` | 실제 화면 원본·격자 PNG와 치수 |
| `POST /api/cmd` | 원본의 모든 게임 명령 |
| `GET /api/calls` | 최근 호출 기록 |
| `GET /api/events` | 원본 SSE 이벤트 |
| `/`, `/debug`, `/index.html` | 원본 웹 제어 화면 |

명령 형식은 `{"method":"press_key","params":{"key":"W","hold_seconds":0.25}}`이며
평면형 `{"cmd":"press_key","key":"W","hold_seconds":0.25}`도 지원한다.
이동, 시선, 마우스/키보드, 텍스트 입력, GUI, 아이템 사용, 블록 설치, 게임 명령,
스크린샷 저장, 반사 기반 화면 호출을 특정 명령 목록으로 막지 않는다.
`enter_control_mode`/`exit_control_mode`와 게임 서버의 플레이어 권한은 그대로 적용한다.
제어 모드를 끝낼 때는 남은 키를 해제한다. `release_all_keys`도 별도로 제공한다.

## 1.20.4 호환 처리
원본의 범용 반사 코드 중 게임 버전과 맞지 않는 기본 동작을 `GameplayControl`이 처리한다.
기준은 [Yarn 1.20.4+build.3](https://maven.fabricmc.net/docs/yarn-1.20.4+build.3/)이다.
- `press_key`: 정확한 Keyboard.onKey 호출과 별도 타이머로 키를 해제한다. 게임 스레드에서 키 유지 시간만큼 sleep하지 않는다.
- `set_view_angle`, `look_delta`: 실제 Entity yaw/pitch 접근자를 호출한다.
- `right_click`, `use_item`, `place_block`: 월드에서는 바닐라 아이템 사용 흐름을 호출한다.
- `execute_command`, `set_gamemode`: 연결된 플레이어의 네트워크 핸들러로 명령을 보낸다.
- `close_screen`: 실제 MinecraftClient.setScreen을 호출한다.

다른 원본 명령은 그대로 위임한다. 모드 GUI의 반사 지원 여부는 화면마다 실사용 검증이 필요하다.
`place_block` 응답이나 명령 전송 응답은 서버가 실제로 블록을 변경했다는 확인이 아니다.
시공 결과는 새 화면·상태로 확인한다. UI가 열려 있을 때 월드 사용 요청은 명확한 오류를 반환한다.

## 검증
MCP 브리지의 도구 목록·인자 전달·오류 표시·이미지 반환을 Node 테스트에서 검증한다.
Java 테스트는 실제 HTTP에서 모든 원본 명령 전달, 대시보드·기록, 외부 Origin 차단,
명령·파일 스크린샷과 JAR 원본/라이선스 보존을 검사한다.
`ControlProbe`는 1.20.4 intermediary 이름만 가진 가짜 클라이언트에서 키 유지 중 게임
스레드가 계속 실행되는지, 키 해제·시선·명령 전송·아이템 사용이 동작하는지 확인한다.
실제 게임에서의 이동/시공 검증 여부는 별도 설치 기록과 구분한다.

`minefed-game`은 이 모드에 연결하는 전체 조작 MCP 어댑터를 관리한다.
별도 upstream Node 런처의 버전 설치·계정·서버 관리 기능은 클라이언트 모드 명령이 아니다.
