# Sodium 클라이언트 렌더링 구성

2026-09-18 공식 Modrinth API에서 Minecraft 1.20.4 / Fabric 호환 최신 정식 배포본을
확인해 Sodium `0.5.8+mc1.20.4`와 Indium `1.0.31+mc1.20.4`를 추가했다.
Sodium은 클라이언트 렌더링을 최적화하며, 이 0.5.x 버전에서 기존 Continuity의
연결 텍스처와 Fabric Rendering API 모드를 사용하려면 Indium이 필요하다.
이 관계는 [해당 Indium 소스의 설명](https://github.com/comp500/Indium/blob/56c79304a50cd894b06f28bf51f80bbfbdd097cd/README.md)에 명시되어 있다.

| 항목 | Sodium | Indium |
| --- | --- | --- |
| 공식 릴리즈 | [4GyXKCLd](https://modrinth.com/version/4GyXKCLd) | [VlLxDisa](https://modrinth.com/version/VlLxDisa) |
| 파일 | `sodium-fabric-0.5.8+mc1.20.4.jar` | `indium-1.0.31+mc1.20.4.jar` |
| 크기 | `949085` bytes | `105350` bytes |
| SHA-256 | `3c363ec0122157f65e55a8edf6545a60955091387cd0e94b3ecdcd64a93284f7` | `a6acf309f91886db6c66c1a8fce7937745053926fa114fe12cb3fdf174dfb57d` |
| 소스 태그 | `mc1.20.4-0.5.8` | `1.0.31+mc1.20.4` |
| 전체 소스 커밋 | `82f4af61fd4ea4c4c5c8e02897202f627d4e68cb` | `56c79304a50cd894b06f28bf51f80bbfbdd097cd` |
| 추적 브랜치 | 현재 1.20.4 브랜치 없음; 공식 호환 릴리즈 추적 | `1.20.x/stable` |
| 해당 소스·바이너리 라이선스 | `LGPL-3.0-only` | `Apache-2.0` |

정확한 다운로드 URL·SHA-512·Fabric 메타데이터·소스 ref는
[dependencies.lock.json](../inventory/dependencies.lock.json)에 기록한다.
[dependency-policy.json](../inventory/dependency-policy.json)은 호환 정식 릴리즈를 조회하고,
[build-recipes.json](../inventory/build-recipes.json)의 `dependency: true` 항목은 검증한
공식 JAR를 선택한다. [release-policy.json](../inventory/release-policy.json)은 두 모드를
`client: true`, `server: false`로 제한한다. `archiveMode: bundled`에서 원본 JAR는
`client.mrpack/overrides/mods/`에 직접 포함된다. 운영 기준본은 그대로 보존한다.

Indium의 JAR는 Sodium `0.5.8`, Fabric Renderer API `>=3.2.0`, Minecraft `~1.20.1`을
요구한다. 이 Minecraft 조건은 Fabric 버전 비교에서 1.20.4를 허용하며 공식 배포본도
1.20.4를 명시한다. Sodium은 오래된 Indium `<=1.0.28`을 충돌 대상으로 선언하므로
고정한 1.0.31을 함께 유지한다. 현재 Fabric API `0.97.3+1.20.4`의 내장 모듈과
Fabric Loader `0.18.4`를 기준으로 실제 JAR의 의존성·충돌 조건을 검증한다.

Sodium 프로젝트의 현재 페이지는 새 버전의 Polyform 라이선스를 표시하지만,
이번 0.5.8 JAR 메타데이터와 정확한 릴리즈 소스는 LGPL v3를 사용한다.
해당 소스의 `COPYING`, `COPYING.LESSER`, 원본 README와 JAR에 포함된 Vanilla Tweaks
고지를 [Sodium 고지 폴더](../inventory/notices/sodium-3c363ec01221/)에 보존한다.
내장 Fabric API JAR와 그 고지는 원본 그대로 유지한다. Indium의 원본 Apache 2.0
라이선스와 README는 [Indium 고지 폴더](../inventory/notices/indium-a6acf309f918/)에 보존한다.
각 `provenance.json`에는 전체 대응 소스 아카이브 URL·SHA-256·SHA-512·크기를 기록한다.
공식 JAR와 소스 ZIP은 로컬 검증용 캐시에 두며 Git에는 추가하지 않는다.

```sh
python scripts/check_dependencies.py --id sodium --id indium
python scripts/mods.py --manifest inventory/dependencies.lock.json verify
python scripts/build_modpack.py plan
```

공식 JAR의 게시 SHA-512·크기·ZIP CRC, 소스 아카이브 CRC와 태그의 전체 커밋을
검증했다. 기존 `20260913195327` 공개팩의 실제 JAR에 이 두 pin을 더한 서버 67개/
클라이언트 69개 구성의 내장 모듈 포함 메타데이터 212개를 Fabric Loader의 버전
비교기로 검사했다. 누락·버전 불일치 의존성, 피할 수 없는 충돌, 후보 버전 교집합
오류가 없었다. 렌더링 성능과 실제 게임 화면은 클라이언트 실행 후 별도로 확인해야 한다.
