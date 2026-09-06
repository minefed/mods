# Minefed mods

Minefed 서버의 모드 소스와 운영 JAR를 한 곳에서 관리한다. Minecraft **1.20.4 / Fabric** 서버에서 2026-09-06 확인한 JAR **70개**를 기준으로 준비했다.

## 관리 구조

- **소스:** 운영 JAR 58개에 대응하는 minefed 저장소 57개를 Git 서브모듈로 관리한다. 기존 Automobility도 운영 중인 Automobility Refueled와 구분해 보존하므로 서브모듈은 총 58개다.
- **바이너리:** 소스가 없거나 라이선스상 수정이 제한된 12개는 JAR로 관리한다. 재배포 가능한 Dusty Decorations는 `vendor/jars/`에 커밋하고, 나머지는 `vendor/local/`에 보관한다.
- **운영 기준본:** 소스로 관리하는 모드도 실제 운영 JAR를 `artifacts/local/`에 보존한다. 소스 업데이트와 배포물 교체는 별도 작업이다.
- **목록과 근거:** [전체 모드 목록](docs/MOD_INVENTORY.md), [고정 버전·해시 목록](inventory/mods.lock.json), [라이선스 조사](inventory/license-audit.json), [원본 고지](inventory/notices/)를 함께 관리한다.

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

`inventory/build-recipes.json`은 소스 빌드 53개와 JAR 사용 15개를 구분한다. 기존 소스 중
CityCraft와 Macaw Doors/Fences는 현재 Fabric 1.20.4용 빌드 입력이 아니므로 운영 JAR를 사용한다.
각 소스는 전용 wrapper/JDK로 빌드하며 실패 시 운영 JAR로 자동 대체하지 않는다.

완성 ZIP과 SHA-256은 `build/distributions/`, 최근 성공 결과 경로는 `latest.json`에 기록된다.
각 JAR의 실제 버전·해시, 소스 커밋과 내용 해시, 라이선스 고지도 ZIP에 포함한다.
환경 설정과 개별 모드 빌드, 로그 확인 방법은 [빌드 안내](docs/BUILDING.md)를 참고한다.

## 운영 JAR 기준본 패키징

```sh
python scripts/mods.py stage
python scripts/mods.py pack --private
```

`stage`는 `build/staged-mods/`에 68개 JAR를 모으고, `pack --private`는 `build/minefed-baseline.zip`에 JAR와 출처·라이선스 기록을 넣는다. 동일 모드 ID가 겹치는 MTR 4.0.3과 Fabric 모드가 아닌 TCPShield는 패키지에서 제외하되 원본 목록에는 보존한다.

이 ZIP은 로컬 검토용 운영 바이너리 기준본이다. 공개 재배포 권한이 확인되지 않은 파일을 포함하므로 `--private` 없이 전체 ZIP을 생성하면 실패한다. 공개 배포에는 lock 파일의 라이선스 조건과 대응 소스 제공 의무를 별도로 충족해야 한다.

운영 기준본 패키징은 원본 JAR를 보존한다. 소스를 컴파일하는 Gradle 빌드와 구분하며,
두 방식 모두 Minecraft 서버/클라이언트 기동 검증이나 운영 서버 업로드·재시작을 수행하지 않는다.

자세한 명령과 실패 처리 방식은 [도구 사용법](scripts/README.md), 소스 업데이트와 빌드 전 확인 사항은 [소스 관리 기록](docs/SOURCE_MANAGEMENT.md)을 참고한다.

## 변경과 커밋

[AGENTS.md](AGENTS.md)는 모든 하위 모드에 적용된다. 각 minefed 서브모듈의 `minefed-1.20.4` 브랜치에도 지침을 커밋해 독립 작업 시 적용한다. lock 파일은 조사한 원래 커밋과 지침을 포함한 관리 커밋을 구분한다.

작고 되돌릴 수 있는 단위마다 검증 후 Conventional Commits 형식으로 커밋한다. 하위 변경을 먼저 커밋하고 원격에서 가져올 수 있도록 한 뒤, 상위 gitlink와 lock 파일을 갱신한다. `git submodule update --remote`만 실행해 버전을 임의로 바꾸지 않는다.

## 라이선스

관리 도구는 [MIT](LICENSE) 라이선스다. 각 모드와 자산은 해당 저작자의 라이선스를 따른다. 원본 JAR 내부의 저작권·라이선스 고지는 변경하지 않는다.
