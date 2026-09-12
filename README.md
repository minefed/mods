# Minefed mods

Minefed 서버의 모드 소스와 운영 JAR를 한 곳에서 관리한다. Minecraft **1.20.4 / Fabric** 서버에서 2026-09-06 확인한 JAR **70개**를 기준으로 준비했다.

## 관리 구조

- **소스:** 운영 JAR 51개에 대응하는 minefed 저장소 50개를 Git 서브모듈로 관리한다. 기존 Automobility는 서브모듈에서 제거했으며, 실제 차량 모드는 Refueled 하나다. [분리 이유와 정리 방침](docs/AUTOMOBILITY.md)을 문서화했다.
- **기반 라이브러리:** Fabric API·Architectury·Botarium·Lavender·owo·Resourceful Config·ResourcefulLib 7개는 공식 JAR로 관리한다. 별도 fork 빌드 없이 [빌드 의존성 lock](inventory/dependencies.lock.json)의 버전·해시·출처를 사용한다. [관리 Q&A와 업데이트 절차](docs/DEPENDENCIES.md)를 참고한다.
- **종료한 소스 관리:** 기존 Automobility와 기반 라이브러리 7개의 Minefed 원격 fork는 삭제했다. 과거 URL·브랜치·전체 커밋과 원격 삭제 상태는 [종료 저장소 기록](inventory/retired-repositories.json)에 남긴다.
- **기타 바이너리:** 소스가 없거나 라이선스상 수정이 제한된 활성 모드 11개는 JAR로 관리한다. Axiom은 사용자 요청으로 팩에서 제외하고 과거 운영 기록만 보존한다. 재배포 가능한 Dusty Decorations는 `vendor/jars/`에 커밋하고, 나머지는 `vendor/local/`에 보관한다.
- **운영 기준본:** 소스로 관리하는 모드도 실제 운영 JAR를 `artifacts/local/`에 보존한다. 소스 업데이트와 배포물 교체는 별도 작업이다.
- **목록과 근거:** [전체 모드 목록](docs/MOD_INVENTORY.md), [고정 버전·해시 목록](inventory/mods.lock.json), [라이선스 조사](inventory/license-audit.json), [원본 고지](inventory/notices/)를 함께 관리한다.
- **업데이트 적용:** [2026-09-12 공식 후속 버전 적용 기록](docs/MOD_UPDATE_APPLIED_2026-09-12.md)에 Axiom 제외, 실제 선택 버전, 소스 커밋과 검증 결과를 정리했다.
- **업데이트 조사:** [2026-09-12 업데이트 전수 조사](docs/MOD_UPDATE_AUDIT_2026-09-12.md)에 Minecraft 1.20.4/Fabric의 후속 버전, 누적 변경사항, 미배포 소스 후보와 운영·빌드·공개팩 버전 차이를 정리했다.

로컬 전용 JAR는 Git에 포함하지 않는다. 각 JAR의 파일명, SHA-256, 크기, 공식 다운로드 URL, 소스 커밋과 라이선스 조건은 lock 파일에 고정한다. 모드팩 포함 허용은 독립 JAR 미러링 허용과 다를 수 있다.

## 시작하기

Git과 Python 3.10 이상이 필요하다. 서브모듈은 `.gitmodules`에 기록한 minefed fork와 정확한 gitlink 커밋으로 초기화한다.

```sh
git -c core.longpaths=true submodule update --init --recursive
python scripts/mods.py hydrate
python scripts/mods.py verify --sources
```

`hydrate`는 공식 URL이 확인된 누락 JAR를 다운로드하고 해시를 검증한다. URL이 없는 자체 빌드 기준본은 lock 파일에 기록된 경로에 운영 JAR를 직접 가져와야 한다. 다른 버전이나 해시가 맞지 않는 파일을 자동으로 대체하지 않는다. 이 작업 공간에는 관측한 원본 70개를 모두 준비했다.

## 소스와 JAR를 한 번에 빌드

Windows에서는 다음 명령으로 소스 모드와 JAR 전용 모드를 함께 패키징한다.

```powershell
.\build-modpack.ps1
```

Gradle 직접 실행은 `gradlew.bat build` 또는 `./gradlew build`다. JDK 17·21, Python 3.10 이상,
MTR 웹 UI용 Node.js 22/npm이 필요하다. 이 작업 공간의 도구 경로는 Git에서 제외한
`build.local.json`에 설정되어 있다.

`inventory/build-recipes.json`은 소스 빌드 46개와 JAR 사용 21개를 구분한다. 기반 라이브러리
7개와 공식 후속 바이너리 8개는 `dependencies.lock.json`의 총 15개 pin을 사용한다. 기존 소스 중
CityCraft와 Macaw Doors/Fences는 공개된 Fabric 1.20.4용 공식 JAR를 사용한다. PFM과 Puzzles Lib의
소스 빌드는 유지하고 공개팩에는 `published-artifacts.lock.json`의 공식 배포본 2개를 선택한다.
각 소스는 전용 wrapper/JDK로 빌드하며 실패 시 운영 JAR로 자동 대체하지 않는다.

완성 ZIP과 SHA-256은 `build/distributions/`, 최근 성공 결과 경로는 `latest.json`에 기록된다.
각 JAR의 실제 버전·해시, 소스 커밋과 내용 해시, 라이선스 고지도 ZIP에 포함한다.
환경 설정과 개별 모드 빌드, 로그 확인 방법은 [빌드 안내](docs/BUILDING.md)를 참고한다.
실제 통합 빌드의 결과물 해시와 확인 범위는 [빌드 검증 기록](docs/BUILD_VALIDATION.md)에 정리했다.

## 공개 릴리즈와 리소스팩

리소스팩은 `resourcepack/` 서브모듈의 `main` 브랜치에서 관리한다. 원본 저장소는 비공개로
유지하며 게임용 `resource_pack/` 파일만 공개 패키지에 포함한다. 새 작업 공간에서 이
서브모듈을 초기화하려면 해당 비공개 저장소의 읽기 권한이 필요하다.

```powershell
.\build-modpack.ps1 -Task releasePacks
```

이 명령은 모드 빌드와 검사를 수행한 뒤 `build/releases/yyyyMMddHHmmss/`에
`server.zip`, `client.mrpack`, `resourcepack.zip`을 함께 만든다. 버전은 한국 시간 기준이며
`-PreleaseVersion=20260907150000`처럼 명시할 수도 있다. 기존 버전은 덮어쓰지 않는다.

GitHub Actions는 `mods/main` 변경과 하위 배포 대상 브랜치의 변경을 감지해 세 파일을
[GitHub Releases](https://github.com/minefed/mods/releases)에 공개한다. 하위 브랜치는
15분 간격으로 확인하며, 동일 입력의 중복 릴리즈는 건너뛴다.
서버팩 `mods/`에는 전체 모드 JAR 67개, 클라이언트팩 `overrides/mods/`에는 서버 전용
2개를 제외한 65개가 직접 포함된다. 공식 JAR도 버전·해시·원본 URL을 유지한 채 내장하며,
Modern Lights는 소스 전용 공식 업로드 대신 검증된 2.5.0 실행 JAR를 양쪽에 포함한다.
정상적으로 압축 해제하거나 MRPACK을 가져오면 추가 모드 다운로드·수동 복원이 필요 없다.
선택적 `install-mods.py` 실행으로 모든 모드의 해시를 검사할 수 있다. 정책에 따른 원본
선택과 자체 빌드 결과의 차이, 기존 재배포 분류와 라이선스는 팩 안의 기록에 보존한다.
서버팩은 TCPShield 2.8.1을 `plugins/`에 별도 포함하여 총 JAR 68개다. TCPShield는
Bukkit/Bungee/Velocity용 플러그인이며 Fabric Loader가 실행하는 모드가 아니다.
자동화와 최초 릴리즈, 설치 방법은 [릴리즈 안내](docs/RELEASING.md)를 참고한다.

## 운영 JAR 기준본 패키징

```sh
python scripts/mods.py stage
python scripts/mods.py pack --private
```

`stage`는 `build/staged-mods/`에 67개 JAR를 모으고, `pack --private`는 `build/minefed-baseline.zip`에 JAR와 출처·라이선스 기록을 넣는다. 동일 모드 ID가 겹치는 MTR 4.0.3, Fabric 모드가 아닌 TCPShield, 사용자 요청으로 제거한 Axiom은 패키지에서 제외하되 원본 목록에는 보존한다.

이 ZIP은 로컬 검토용 운영 바이너리 기준본이다. 공개 재배포 권한이 확인되지 않은 파일을 포함하므로 `--private` 없이 전체 ZIP을 생성하면 실패한다. 공개 배포에는 lock 파일의 라이선스 조건과 대응 소스 제공 의무를 별도로 충족해야 한다.

운영 기준본 패키징은 원본 JAR를 보존한다. 소스를 컴파일하는 Gradle 빌드와 구분하며,
두 방식 모두 Minecraft 서버/클라이언트 기동 검증이나 운영 서버 업로드·재시작을 수행하지 않는다.

자세한 명령과 실패 처리 방식은 [도구 사용법](scripts/README.md), 소스 업데이트와 빌드 전 확인 사항은 [소스 관리 기록](docs/SOURCE_MANAGEMENT.md)을 참고한다.

## 변경과 커밋

[AGENTS.md](AGENTS.md)는 모든 하위 모드에 적용된다. 각 minefed 서브모듈의 `minefed-1.20.4` 브랜치에도 지침을 커밋해 독립 작업 시 적용한다. lock 파일은 조사한 원래 커밋과 지침을 포함한 관리 커밋을 구분한다.

작고 되돌릴 수 있는 단위마다 검증 후 Conventional Commits 형식으로 커밋한다. 하위 변경을 먼저 커밋하고 원격에서 가져올 수 있도록 한 뒤, 상위 gitlink와 lock 파일을 갱신한다. `git submodule update --remote`만 실행해 버전을 임의로 바꾸지 않는다.

## 라이선스

관리 도구는 [MIT](LICENSE) 라이선스다. 각 모드와 자산은 해당 저작자의 라이선스를 따른다. 원본 JAR 내부의 저작권·라이선스 고지는 변경하지 않는다.
