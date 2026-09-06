# 소스 관리 기록

## 원격 커밋과 운영 JAR

서브모듈은 모두 minefed의 `minefed-1.20.4` 브랜치를 추적한다. 이 브랜치는 조사한 소스 기준 커밋 위에 하위 저장소용 `AGENTS.md`를 추가한 관리 브랜치다. 원래 upstream/기존 fork 브랜치의 이력은 그대로 보존한다.

`inventory/mods.lock.json`의 각 `source`는 다음 값을 구분한다.

- `baselineRef`, `baselineCommit`: 라이선스와 운영 버전을 조사한 원래 소스 ref와 전체 커밋.
- `ref`, `commit`: minefed 관리 브랜치와 지침을 포함한 전체 커밋. 상위 gitlink는 이 커밋을 가리킨다.
- `upstream`, `url`: 원래 소스 위치와 minefed fork 위치.

JAR의 `sha256`, `version`은 실제 서버에서 내려받은 파일의 값이다. 소스와 JAR가 정확히 대응하는지 확인된 범위는 항목별 `notes`와 `inventory/license-audit.json`에 기록한다. 소스 pin만으로 빌드 결과의 바이트 동일성을 주장하지 않는다.

## 기존 소스 확인

| 저장소 | 원래 추적 브랜치 | 확인한 최신 소스 커밋 |
| --- | --- | --- |
| Minecraft-Transit-Railway | main | 53cdc36ebef57c42bdc8633957be1b0e923c40b5 |
| Automobility | 1.20.4-backport | 831011268f914a308bde4500ec510d7659de7398 |
| fabric-webstreamer | master | ff3796b835d7a61055f218cdddb718429507a1c4 |
| minefed-display | main | 79708da179682295df0dfc379320a0759c25a97d |
| Chisels-and-Bits | version/1.20.4 | f64db2d6124e004ae498cd1a1154909afd81a96d |

MTR와 기존 Automobility의 gitlink는 이전 등록 커밋보다 최신 소스로 갱신했다. display와 webstreamer는 이미 최신 기준 커밋이었다. Chisels-and-Bits는 조직에 있던 fork를 새로 서브모듈에 등록했다. 위 모든 저장소의 최종 gitlink에는 하위 커밋 지침도 포함된다.

## 일괄 빌드의 소스 관리

- **서로 다른 빌드 도구:** 루트 Gradle이 모드별 wrapper/JDK를 순서대로 호출한다. `inventory/build-recipes.json`에 태스크, 버전, 명시적인 최종 Fabric JAR 경로와 JAR 전용 선택 이유를 기록한다. 자세한 내용은 [빌드 안내](BUILDING.md)를 따른다.
- **루트 구성:** 이전 composite build와 파일명 추측 방식의 수집을 대체했다. `build`는 소스 컴파일과 JAR 전용 모드 검증을 거쳐 새 결과 ZIP을 만든다. 원래 운영 JAR는 별도로 유지한다.
- **기존 Automobility:** 1.20.4-backport의 properties와 달리 Fabric 메타데이터는 1.21.x/Java 21을 요구한다. 운영 파일은 별개인 Automobility Refueled 0.4.3.b이며 독립 서브모듈로 고정했다.
- **소스와 바이너리 차이:** CityCraft와 Macaw Doors/Fences의 공개 소스는 운영 Fabric JAR의 직접적인 빌드 입력이 아니므로 JAR 전용으로 구성한다. Paladin Furniture, Modern Lights 및 일부 라이브러리는 관리 소스 버전으로 빌드하며 운영 버전과 구분하여 결과 목록에 기록한다. CrossStitch는 정상 revert 커밋으로 1.20.4와 호환되는 0.1.6 소스를 복구했다.
- **Yuushya Townscape:** GitHub mirror보다 최신인 운영 2.2.3 소스는 원저자의 Gitee `v2.2.3` 커밋 `e76ea8ac5454ec424771f593ce05ee0082e4b278`에서 가져와 minefed 관리 브랜치에 보존했다.
- **커밋 수 기반 버전:** AGENTS.md만 추가해도 커밋 수나 해시 기반 버전이 달라질 수 있다. BlueMap·Chunky에는 명시적 releaseVersion, Carpet에는 buildDate 입력을 추가했고 recipe에서 지정한다. 그 외 Git 기반 버전도 expectedVersion에 기록하며 소스 변경 시 함께 검토한다.
- **Windows 경로:** Modern-Lights에는 긴 파일 경로가 있으므로 초기화 명령의 `-c core.longpaths=true`를 유지한다. BlueMap의 중첩 BlueMapAPI 의존성은 원본 gitlink를 유지하며 `--recursive`로 가져온다.
- **외부 개발 환경 설정:** Yuushya Modelling recipe는 원본의 개발자 로컬 프록시를 비활성화한다. Fuzss 계열 6개 모드는 재귀적으로 불러오는 외부 빌드 스크립트까지 호환되는 전체 커밋 SHA로 고정한다.
- **클라이언트와 서버:** 이 목록은 서버 디렉터리에서 관측한 파일 기준이다. 클라이언트 모드팩 배포에는 MCEF 등 클라이언트 의존성과 모드 환경을 별도로 확인해야 한다.

## 이후 업데이트 순서

1. 해당 하위 저장소의 AGENTS.md와 항목별 라이선스를 읽는다.
2. 원래 추적 브랜치에서 업데이트를 조사하고 Minecraft 1.20.4/Fabric 대상임을 확인한다.
3. 관리 브랜치에서 작은 단위로 변경·검증·Conventional Commit을 수행한다. 지침과 라이선스 고지를 보존한다.
4. 하위 커밋을 minefed 원격에 push하고 그 커밋을 원격에서 가져올 수 있는지 확인한다.
5. 상위 gitlink, lock의 소스 정보 및 필요할 때만 운영 JAR 해시를 함께 갱신한다. `python scripts/mods.py verify --sources` 후 상위 변경을 별도 커밋한다.

운영 서버 업로드·재시작과 공개 모드팩 배포는 이 준비 작업의 결과에 포함되지 않는다.
