# 클라이언트 Yuushya 시각 효과 구성

클라이언트 시작 화면에서 안내된 Continuity와 Yuushya Foliage Addon을 mrpack에
포함했다. 대상은 Minecraft 1.20.4 / Fabric Loader 0.18.4다.

- Continuity `3.0.0+1.20.2`: 공식 JAR를 클라이언트 전용으로 추가했다.
  공식 릴리즈는 1.20.4를 지원한다. 소스 ref·전체 커밋·추적 브랜치·원저자 고지는
  [Continuity 구성](CONTINUITY.md) 및 `inventory/dependencies.lock.json`에 기록했다.
- Yuushya Foliage Addon `1.3`: CurseForge 파일 `5084380`의 원본 ZIP을 포함했다.
  원본 SHA-256은 `0a612f147a560acafe029307a4428193e8da39d1ef7414c7f96194ec1d3fbfac`다.
  독립적인 리소스팩이므로 Yuushya 16x 추가는 필요하지 않다.
  소스 저장소·커밋이 공표되지 않은 자산이라 공식 파일 ID와 원본 바이트 해시로 고정한다.
- 새 인스턴스에서 `yuushya:mcpatcher_feature`, Foliage, Minefed 팩을 이 순서로 활성화한다.
  Yuushya의 연결 텍스처 정의는 이 내장 팩에 있으므로 Continuity와 함께 선택한다.
  Foliage의 원본 `pack_format: 8`은 바꾸지 않으며, 배포자의 1.20.4 지원 설명에 따라
  해당 파일을 `incompatibleResourcePacks`에 기록했다.
- Foliage의 CC BY-NC-SA 4.0 자산 조건과 제작자 링크를 동봉한다.
  [자산 고지](../inventory/licenses/client-resourcepacks/yuushya-foliage-addon/LICENSE.md)와
  [출처 기록](../inventory/licenses/client-resourcepacks/yuushya-foliage-addon/provenance.json)을 참고한다.

현재 빌드 입력은 68개이며, 서버 프로필 67개와 클라이언트 프로필 66개다.
과거 운영 목록 `mods.lock.json`은 수정하지 않고 신규 binary dependency로 등록했다.
새 JAR와 리소스팩 ZIP은 Git에 추가하지 않는다. 향후 빌드·패키징은 잠금 파일에
기록한 공식 URL에서 원본을 복원하고 SHA-256·SHA-512·크기를 검사한다.

## 검증한 로컬 배포본

버전 `20260913144426`, 클라이언트 파일:
`build/releases/20260913144426/client.mrpack`

- 크기: `256604519` bytes
- SHA-256: `a0bd6929fd5f856bc1e572e755b156e12194349277df63ebea1cb7286d22c124`
- 검증 보고: `build/client-visuals-research/release-verification.json`
- 원본 빌드 입력: `build/client-visuals-20260913/source-distribution/result.json`
- 원본 빌드 ZIP SHA-256: `7ae9187baa46e9ef508c3a3bc2071da631e5f1e0afb120c9cb4e76589de8ad0a`

이 로컬 조립에서는 새 소스 컴파일 없이 이전에 검증한 67개 JAR를 그대로 재사용했다.
46개 소스의 전체 커밋·작업 트리 해시·recipe를 이전 receipt와 대조했고, 원래의
`compiledRun`·`buildTools`와 기준 ZIP·summary를 보존했다. Continuity만 추가했다.
원래 ZIP은 보존하고 `build/distributions/latest.json`은 검증된 새 입력을 가리킨다.

검사 결과:

- 전체 도구 테스트: 168개 중 164개 통과, 4개 환경 조건에 따라 제외.
  제외 사유는 POSIX 신호 테스트 2개, Windows 심볼릭 링크 생성 권한 1개,
  별도 활성화하는 JDK 통합 테스트 1개다.
- Windows 고지 경로 보완 후 패키징 테스트 35개 통과.
- Fabric 저장소 및 Loom remapped 저장소 정책 검사 통과.
- 캐시 없는 상태의 공식 Foliage 다운로드·해시·내장 팩·고지 검사 통과.
- 실제 선택된 최상위/내장 모드 메타데이터 204개에 대해 Fabric 0.18.4의 버전 조건을 검사했다.
  클라이언트·서버 모두 누락/비호환 필수 의존성, 불가피한 충돌, 버전 교집합 실패가 없다.
- 최종 ZIP CRC, 파일 크기 및 해시 검사 통과. 기존 클라이언트 JAR 65개,
  서버 JAR 67개·플러그인 1개, Minefed 게임 리소스의 바이트를 이전 배포본과 비교해 보존을 확인했다.
- Windows에서 클라이언트 `overrides/`를 인스턴스 구조로 압축 해제하고 동봉
  `install-mods.py`를 실행하여 모든 모드와 Foliage ZIP의 해시 검증을 통과했다.
- 누적된 과거 고지 경로를 `licenses/inherited/`로 짧게 정리하고 원래 경로·전체 해시를
  인덱스로 보존했다. 이전 배포본의 모든 고지 내용이 남아 있으며 최대 상대 경로 길이는 121자다.

Minecraft 클라이언트 실행·렌더링·서버 접속은 수행하지 않았다. 의존성 검사는 실제 게임
기동이나 전체 SAT 해석을 대신하지 않으며 `runtimeValidated`는 `false`다.
이 작업은 로컬 생성·검증·커밋까지이며 원격 게시나 운영 서버 변경을 수행하지 않았다.
