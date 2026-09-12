# 세 팩 자동 배포

`.github/workflows/release.yml`은 공개 `minefed/mods` 저장소의 GitHub Releases에 서버팩,
클라이언트팩, 리소스팩을 함께 게시한다. 버전과 태그는 `Asia/Seoul` 기준
`yyyyMMddHHmmss` 형식이다. 각 버전의 Release 파일은 정확히 다음 세 개다.

| 파일 | 용도 |
| --- | --- |
| `server.zip` | 전체 서버용 모드 JAR, TCPShield 플러그인과 설치 안내·출처 정보 |
| `client.mrpack` | Modrinth 형식을 지원하는 런처에서 가져오는 클라이언트팩 |
| `resourcepack.zip` | ZIP 루트의 `pack.mcmeta`·`assets/`를 사용하는 게임용 리소스팩 |

모드별 포함 환경과 배포 기록은 `inventory/release-policy.json`에 기록한다.
`archiveMode: bundled`는 선택한 실행 JAR를 모두 서버팩 `mods/` 및 클라이언트팩
`overrides/mods/`에 직접 포함한다. 공식 바이너리는 기존 `built`/`baseline`/`published`
선택과 원본 URL·해시를 유지한다. MRPACK의 `modrinth.index.json.files`는 비워
런처가 같은 JAR를 다시 다운로드하지 않게 한다.

2026-09-12 전체 포함 요청을 반영한 구성은 서버 모드 67개/클라이언트 모드 65개이며
각 팩에 전부 내장된다. 이전 구성의 내장 36개·공식 다운로드 30개·수동 복원 1개는
배포 판단 이력으로 유지한다. Modern Lights는 공식 sources JAR 대신 검증된
2.5.0 소스 빌드 실행 JAR를 서버·클라이언트 모두에 포함한다.

동봉 manifest의 `archiveIncluded`는 실제 파일 포함 여부, `distribution`은 기존 배포
방식 기록, `artifactRedistribution`은 선택한 JAR의 기존 재배포 분류다. 전체 포함 요청은
원저자 라이선스나 재배포 권한을 변경하지 않으며, `local-only`를 `allowed`로 바꾸지 않는다.
현재 실행 파일과 과거 운영 JAR의 라이선스 차이, 원저자 고지 및 대응 소스 링크를 보존한다.
JAR는 Git에 추가하지 않는다. `install-mods.py`는 정상적으로 압축 해제한 팩에서 다운로드
없이 모든 모드의 해시를 검사하는 선택적 검증 도구다.

`serverPlugins`로 지정한 TCPShield 2.8.1은 서버팩 `plugins/TCPShield-2.8.1.jar`에
추가된다. 서버팩은 `mods/`의 Fabric 모드 67개와 `plugins/`의 플러그인 1개, 총 JAR
68개다. TCPShield는 Bukkit/Bungee/Velocity용으로 Fabric Loader가 실행하지 않는다.
해당 플랫폼의 플러그인 폴더에 사용하는 파일이며 클라이언트 MRPACK에는 포함하지 않는다.
공식 원본의 URL·크기·SHA-256·플러그인 메타데이터와 MIT 고지를 검증·보존한다.
기존 운영 인벤토리의 Fabric 빌드 제외 표시는 유지하고, 릴리즈 기록의 `plugins`와
`pluginCount`로 별도 추적한다. `install-mods.py`는 동봉 플러그인의 해시도 검사한다.

PFM/Puzzles Lib는 소스 빌드를 유지하면서 `artifact: published`로 공식 JAR를 선택한다.
`publishedManifest`가 지정한 `inventory/published-artifacts.lock.json`은 해당 두 항목과
정확히 대응하며 URL·SHA-256·SHA-512·실제 Fabric 메타데이터를 검증한다. 공식 파일의
고지를 별도로 보존하고 자체 빌드와의 차이를 기록한다. lock 파일 해시도 패키징 및
게시 전에 검사한다. 새 작업 공간에서는 공식 파일을 임시 패키징 폴더로 복원한다.
리소스팩은 `inventory/resourcepacks.lock.json`의 `resource_pack/` 게임용 파일만 공개한다.
비공개 `minefed/resourcepack` 저장소와 `design/`의 제작 자료는 공개하지 않는다.

## 실행 조건과 변경 감지

- 이 통합 저장소의 `main` push는 실행을 요청한다.
- Actions의 **Publish Minefed packs → Run workflow**에서도 `main`을 선택해 요청할 수 있다.
- 매시 UTC 7·22·37·52분에 각 대상 브랜치의 실제 원격 HEAD를 조회한다.
  모드는 고정 목록의 관리 브랜치, 리소스팩은 `main`을 추적한다.

모든 실행은 현재 root 커밋과 소스 브랜치 HEAD로 지문을 만들고 마지막 공개 Release와 비교한다.
변경이 없으면 소스 다운로드·컴파일·게시를 건너뛴다. 통합 도구·정책이 바뀐 root `main` 커밋도
새 릴리스 입력이므로 소스 HEAD가 같아도 배포 대상이 된다.

수동 실행의 **Rebuild and publish even when inputs are unchanged** (`force`) 옵션은 기본으로
꺼져 있다. 명시적으로 켜면 입력이 같아도 전체 빌드와 검증을 다시 수행하고 새 날짜·시간 버전으로
게시한다. 첫 로컬 릴리스 이후 hosted runner 빌드를 확인할 때 사용할 수 있다. 기존 버전의 파일은
덮어쓰지 않으며, `main` push와 정기 실행은 계속 변경 없는 입력을 건너뛴다.

다른 저장소의 push가 이 workflow를 즉시 호출하는 webhook은 설치하지 않는다. 별도 쓰기 PAT
없이 15분 간격으로 확인하며, GitHub 스케줄 지연과 이전 빌드 대기 시간이 더해질 수 있다.
`minefed-release` 동시성 그룹은 진행 중 배포를 취소하지 않고 겹치는 실행을 직렬화한다.
여러 변경이 쌓이면 실행 시점에 조회한 최신 브랜치 상태가 하나의 릴리스에 반영될 수 있다.

## 최초 설정

1. 공개 `minefed/mods`의 Actions를 활성화한다.
2. 비공개 `minefed/resourcepack`에 **읽기 전용 deploy key**를 등록한다. 대응하는 개인키는
   `minefed/mods` Actions secret **`MINEFED_RESOURCEPACK_SSH_KEY`**에 저장한다.
   원본 리소스팩 저장소의 공개 범위는 변경하지 않는다.
3. 공식 URL이 없는 승인된 바이너리의 정확한 원본을 로컬에 준비하고, 첫 공개 세 팩을
   로컬 검증 후 게시한다. 이후 `bootstrap`이 공개 `client.mrpack`에서 필요한 승인된 파일만
   원본 SHA-256과 대조해 복원한다. 없거나 해시가 다르면 자동 빌드는 실패한다.
4. `main`에서 workflow를 수동 실행해 세 파일과 태그를 확인한다. 첫 로컬 릴리스와 입력이 같다면
   `force`를 켜서 hosted runner의 전체 빌드도 검증한다.

일반 실행에는 별도 쓰기 PAT가 필요 없다. GitHub가 job에 부여하는 `GITHUB_TOKEN`을
읽기 전용 준비 단계와 쓰기 전용 게시 단계에서 각각 사용한다.

## 실행 순서와 권한

첫 job은 `contents: read`로 root 커밋만 checkout하고 인증 정보를 Git 설정에 남기지 않는다.
Python 3.13을 준비한 뒤 리소스팩 키를 임시 디렉터리에 저장한다. SSH host key는 TLS로
조회한 [GitHub 공식 `/meta` API](https://docs.github.com/en/rest/meta/meta#get-github-meta-information)의
공개 host key를 사용하며, HTTPS→SSH 변환은 리소스팩 저장소 URL에만 적용한다.

```sh
python scripts/release_control.py plan --output build/release-plan.json
python scripts/release_control.py materialize --plan build/release-plan.json
python scripts/release_control.py bootstrap --plan build/release-plan.json
```

`plan`이 버전과 원격 커밋을 정하고, `materialize`가 조회한 정확한 커밋으로 소스와 중첩
서브모듈을 준비한다. 변경된 pin과 빌드 입력은 `build/release-inputs.patch`에 남긴다.
키와 임시 Git URL 설정은 이 단계 직후 제거하며 실패한 경우에도 정리를 실행한다.
그 뒤 모드 소스를 실행하는 환경에는 리소스팩 키나 게시 토큰을 전달하지 않는다.

JDK 17·21과 Node.js 22를 준비한 후 CI는 `./gradlew check assemble -PsourceBuildWorkers=2`를 실행한다.
`build`와 같은 검사·조립 태스크를 실행하되 도구 회귀 검사와 저장소 정책 검사를 먼저 끝낸다.
Linux에서만 실행하는 프로세스 취소 검사도 긴 소스 컴파일 전에 통과해야 한다.
루트 Gradle은 JDK 17을 사용하고, 모드 46개는 각자의 wrapper로 최대 두 개씩 빌드한다. 두 작업자는
서로 다른 `GRADLE_USER_HOME`을 사용해 Loom의 Minecraft 캐시 충돌을 막으며, 각 작업자 안에서는
모드를 직렬 빌드한다. 준비·최종 무결성 검사·패키징은 기존 단일 실행 경로를 사용한다.

`sourceBuildWorkers`는 `1` 또는 `2`만 허용하며 생략한 로컬 `./gradlew build`는 기존처럼 직렬로
실행한다. 병렬 모드는 사용자 Gradle 설정이나 init script가 있으면 직렬 모드 사용을 안내하고
중단한다. 개인 PC의 공유 캐시나 다른 작업 공간을 삭제하지 않는다.

```sh
python scripts/release_pack.py \
  --result-json build/distributions/latest.json \
  --version <yyyyMMddHHmmss> \
  --policy inventory/release-policy.json \
  --output build/releases/<yyyyMMddHHmmss>
```

job 간 artifact에는 세 공개 파일과 `release-assets.json`, 계획 JSON, 입력 patch만 명시적으로
전달하며 보관 기간은 3일이다. 비공개 기준 ZIP, 전체 소스, 제작 자료, 캐시, 로그는 artifact로
업로드하지 않는다. GitHub Actions 자체 실행 로그에는 빌드 진단이 남는다.

게시 job은 별도의 깨끗한 runner에서 같은 root 커밋의 게시 도구를 checkout한다. 이 job만
`contents: write`를 가지며 모드 소스를 checkout하거나 Gradle을 실행하지 않는다.

```sh
python scripts/release_control.py publish \
  --assets build/releases/<yyyyMMddHHmmss>/release-assets.json \
  --plan build/release-plan.json \
  --patch build/release-inputs.patch
```

게시 도구는 해당 root 커밋 위에 pin patch를 반영한 Conventional Commit을 만들어 릴리스 태그를
원격에 남긴다. root `main`을 자동 갱신하지 않으므로 pin 반영 push가 다시 배포를 요청하는
반복을 만들지 않는다. 세 파일을 draft Release에 올리고 검증한 뒤 공개한다.
실패한 빌드를 성공한 새 Release로 대체하거나 기존 버전의 파일을 임의로 덮어쓰지 않는다.

## 실행 환경과 한계

공개 저장소의 `ubuntu-24.04` hosted runner에서 실행한다. 많은 소스를 처음 빌드하면 Minecraft,
Gradle 및 플러그인 다운로드로 수 시간이 걸릴 수 있다. job 간 빌드 캐시를 업로드하지 않으므로
다음 변경의 빌드는 새 runner에서 다시 시작하며, 한 build job의 제한 시간은 6시간이다.

디스크 확보는 이 임시 GitHub hosted Ubuntu 이미지에만 적용한다. 공식 이미지 설치 경로인
`/usr/local/lib/android`, `/usr/share/dotnet`, `/usr/local/.ghcup`,
`/opt/hostedtoolcache/CodeQL`이 실제로 같은 절대 경로인지 확인한 뒤 사용하지 않는 SDK를 지운다.
두 작업자의 독립 캐시 공간을 위해 소스 checkout 전에 55 GiB 이상 남아 있는지 확인한다.
이 값은 초기 하한이며 전체 빌드 용량을
보증하지 않는다. 디스크나 시간 한도를 넘으면 runner 용량·빌드 구성을 검토해야 한다.

GitHub Action은 확인한 공식 릴리스의 전체 커밋 SHA로 고정한다. 버전을 갱신할 때는 공식
Action의 변경 사항과 runner 요구사항을 확인하고 SHA도 함께 검토한다.
이미지 경로 근거는 [Ubuntu 24.04 이미지 목록](https://github.com/actions/runner-images/blob/main/images/ubuntu/Ubuntu2404-Readme.md)과
[공식 설치 스크립트](https://github.com/actions/runner-images/tree/main/images/ubuntu/scripts/build)다.

ZIP·해시·정책 검증 성공은 실제 Minecraft 클라이언트 접속이나 서버 기동 검증을 뜻하지 않는다.
`runtimeValidated`는 별도 게임 검증을 마치기 전까지 `false`다. 이 배포 흐름은 GitHub Release를
게시하며 운영 서버 파일·설정·월드 변경, 업로드 또는 재시작을 수행하지 않는다.
