# 모드 검사 작업의 통합과 지침 반영 — 2026-09-28

사용자 요청에 따라 [모드 검사 작업](MOD_HEALTH_AUDIT_2026-09-28.md)을 상위
`main`과 하위의 기존 통합 브랜치에 반영했다. 분기 충돌 없이 fast-forward로
통합했으며 기존 기능 브랜치와 이력을 보존했다.

이번 기능 수정이 있었던 하위 저장소의 최종 통합 커밋은 다음과 같다.
각 커밋은 검사 때 사용한 기능 커밋을 포함하고, 그 뒤에 공통 지침 커밋을 추가했다.

| 저장소 | 대상 브랜치 | 검사한 기능 커밋 | 통합 커밋 |
| --- | --- | --- | --- |
| Minecraft-Transit-Railway | `minefed-1.20.4` | `e33269ecb041c55503053b72ccec4ec68d7bc01c` | `25cf42b49c788814f10cead1615acd9b08d3d87c` |
| alloy-forgery | `minefed-1.20.4` | `e4d10145142f7d3dc12effc1b3083723a9d08d4d` | `fe660cd7c31be0232e952064b6a1b726eda04b8a` |
| fabric-seasons | `minefed-1.20.4` | `d5ff75050e02f131ea82fee0e7904e92eb7214f3` | `7cfb70e58ebc5cdd1ee95a5fe37bc135400f27ab` |
| TrafficCraft | `minefed-1.20.4` | `69a09747437289bcda71a8bfaa1c72aeca848cad` | `48605568e12d9cec7e85d4057d180b461925a28f` |
| Yuushya-Townscape | `minefed-1.20.4` | `ca14f0658a05e4d53ec302fa01f27de4311359b8` | `f2fab506bbe69368eff27d5d4dc6afa23170f0b7` |
| minefed-client-compat | `main` | `3ac78cb964693b0cbd098e63041f1592d98a99ca` | `6e4630945e8c8c5e9f080c02e81b41f908bad7b3` |

일반 하위 저장소 50개는 `minefed-1.20.4`, `minefed-client-compat`와
`resourcepack`은 기존 `main`을 사용한다. 하위 52개 모두 지침 커밋을 push한 뒤
원격 tip과 로컬 HEAD의 일치를 확인했다. 코드와 게임 자산이 검사 당시와 같고
차이가 `AGENTS.md`와 `CLAUDE.md`뿐임을 각 저장소의 diff로 확인했다.

상위 및 52개 하위 저장소의 `AGENTS.md`에는 검증·커밋을 마치면 지정된
통합 브랜치에 병합·push하는 절차를 추가했다. `CLAUDE.md`는 해당 `AGENTS.md`를
읽도록 안내한다. 리소스팩의 차량 제작 지침은 보존하고 공통 완료 절차를 덧붙였다.
운영 서버 변경은 계속 별도의 요청이 있어야 수행한다.

원격에서 가져올 수 있는 하위 커밋으로 gitlink, 모드·리소스팩 소스 고정값 및
추적 브랜치를 갱신한 뒤 `mods.py verify --sources`로 운영 기준 JAR 70개와
전체 소스 고정값을 검증했다. 과거 빌드·실행 증거에 기록된 소스 해시는 그 당시의
기록으로 보존한다. 이번 지침 변경은 게임 코드·자산을 바꾸지 않아 다시 빌드하지
않았고, 이미 검사한 배포팩을 그대로 설치했다.

로컬 Modrinth `client` 프로필은 버전 `20260928133356`으로 갱신했다.
전체 72개 JAR가 배포 명세와 일치한다. 사용자 데이터와 설정 보존, 백업 경로,
복구 절차는 [로컬 적용 기록](LOCAL_MOD_HEALTH_INSTALL_2026-09-28.md)에 있다.
설치 후 게임을 추가 실행하거나 운영 서버를 수정하지 않았다.

저장소별 이전·최종 전체 커밋, 통합 브랜치, 원격 검증 결과와 설치 요약은
[통합 기록](../inventory/mod-health-integration-2026-09-28.json)에 보관한다.
