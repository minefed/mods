# 로컬 Modrinth 렌더링 수정 적용 — 2026-09-24

2026-09-24 22:20:41 KST에 Modrinth `client` 프로필의 두 모드를 교체했다.
대상은 Minecraft 1.20.4 / Fabric Loader 0.18.4이며 적용 직전 Java 게임 프로세스가
실행 중이지 않음을 확인했다.

- 프로필: `C:/Users/강찬/AppData/Roaming/ModrinthApp/profiles/client`
- 백업: 프로필의 `minefed-backups/render-fixes-20260924-222041/`
- 로컬 적용 기록: 프로필의 `MINEFED-RENDER-FIXES.json`
- 새 JAR의 전체 SHA-256, 소스 커밋·추적 브랜치, 호환성과 라이선스:
  [검증된 수정 산출물](../inventory/render-fixes-2026-09-24.json)

| 모드 | 교체 전 SHA-256 | 교체 후 SHA-256 |
| --- | --- | --- |
| Modern Glass Doors | `9fec5fc3f4fc0f72f7ef1c75d6161d3fab0945604b3885140c0c051eb4d5d08f` | `38220292bd00260c364fc0ce30667087ca0d567ed775be9307dd3de3d7f7d94a` |
| Minefed Display | `883fdaca486e3de9a2c27f741902b4eb84ee2424a7929adaddafc3c17953a718` | `78c8359f70b6ecf2d012e9a94ec7ef68b706b935cde41efaea544eb043ee5835` |

기존 두 JAR와 `download-manifest.json`, `MINEFED-RELEASE.json`, `SOURCES.md`,
`LICENSES.md`를 백업하고 복사본의 해시를 검증했다. 설치 기록의 해당 두 항목은
새 JAR의 크기·해시·소스 링크·커밋 날짜로 갱신했다. 기존 팩 버전 표시는 유지한다.

적용 후 설치된 두 JAR의 해시가 검증 산출물과 일치한다. 전체 활성 JAR 70개 중
나머지 68개는 교체 전과 바이트가 동일하며, 중복 모드는 추가하지 않았다.
게임을 시작하면 수정본이 로드된다. 이 적용 작업에서는 게임 실행이나 실제 게임 내
시각 검증, 운영 서버 파일 변경·업로드·재시작을 수행하지 않았다.

복구하려면 게임을 종료한 상태에서 위 백업의 두 JAR와 네 설치 기록 파일을
프로필의 같은 상대 경로로 복사한다. 백업의 `before-mod-hashes.json`에 전체 모드의
교체 전 해시를 보존했다.
