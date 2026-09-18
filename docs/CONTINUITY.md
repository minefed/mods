# Continuity 클라이언트 구성

Yuushya의 연결 텍스처를 표시하기 위해 공식 Continuity `3.0.0+1.20.2`를
클라이언트 모드팩에 추가한다. 버전 이름은 `1.20.2`지만 공식 릴리즈와 JAR 모두
Minecraft `1.20.2–1.20.4`를 지원한다. `fabric.mod.json`의 실행 환경이 `client`이므로
서버 프로필에는 포함하지 않는다.

2026-09-13 [공식 Modrinth 릴리즈](https://modrinth.com/version/WMwDkIY8)를 확인했다.
Fabric Loader `>=0.15.0`, Fabric API `>=0.89.0`이 필요하며 현재 팩의 Loader
`0.18.4`, Fabric API `0.97.3+1.20.4`가 이 조건을 충족한다.

| 항목 | 고정값 |
| --- | --- |
| 파일 | `continuity-3.0.0+1.20.2.jar` |
| 크기 | `1016209` bytes |
| SHA-256 | `0fa002f7c67b800e50038e64d8fae4fb0e7386cd2841287cd47046f2b18fe1e3` |
| 원본 소스 | [PepperCode1/Continuity](https://github.com/PepperCode1/Continuity) |
| 추적 브랜치 | `1.20.2/dev` |
| 릴리즈 ref | `v3.0.0+1.20.2` |
| 전체 소스 커밋 | `7deaa8c3f8005bf002a63a7ae97fb0227e381236` |
| 소스·바이너리 라이선스 | `LGPL-3.0-only` |

정확한 다운로드 URL, SHA-512, 호환성과 출처는
[dependencies.lock.json](../inventory/dependencies.lock.json)에 기록한다.
[build-recipes.json](../inventory/build-recipes.json)의 `dependency: true` 바이너리
recipe로 선택하며, [release-policy.json](../inventory/release-policy.json)은
`client: true`, `server: false`로 제한한다. `archiveMode: bundled`에서는 공식
JAR를 mrpack에 직접 넣는다. 캡처한 운영 기준본 `mods.lock.json`은 수정하지 않는다.

JAR의 원본 LGPL 고지, GPL v3 본문, 대응 소스 다운로드 URL·SHA-256·SHA-512와
소스 아카이브 링크는 [고지 폴더](../inventory/notices/continuity-0fa002f7c67b/)에
보존하며 패키징 시 함께 수록한다. 소스 JAR는 검증을 위해 로컬에 내려받지만
실행 모드 목록에는 넣지 않는다.

```sh
python scripts/check_dependencies.py --id continuity
python scripts/mods.py --manifest inventory/dependencies.lock.json hydrate
python scripts/mods.py --manifest inventory/dependencies.lock.json verify
python scripts/build_modpack.py plan
```

Continuity는 연결 텍스처 구현이며 Yuushya Foliage Addon 리소스팩과 별개의 파일이다.
2026-09-18부터 함께 포함한 Sodium 0.5.8 환경에서는 Fabric Rendering API 구현을
제공하는 Indium 1.0.31도 필요하다. 둘 다 [Sodium 구성](SODIUM.md)에 고정했다.
이 JAR의 메타데이터·해시 검증은 실제 게임 화면의 렌더링 확인을 대체하지 않는다.
