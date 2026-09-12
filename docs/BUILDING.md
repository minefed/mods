# 모드팩 빌드

이 저장소는 Minecraft 1.20.4 / Fabric용 소스 빌드와 운영 JAR를 하나의 Gradle 작업으로 묶는다.
빌드 대상과 JAR 전용 대상은 `inventory/build-recipes.json`에 명시한다. `mods.lock.json`은
원래 서버의 바이너리 목록과 소스 커밋을 보존하며, 소스를 컴파일했다고 원본 JAR 해시를 바꾸지 않는다.

현재 구성은 소스 빌드 46개와 바이너리 21개다. 그중 기반 라이브러리 7개는 recipe의
`dependencyManifest`가 지정한 `inventory/dependencies.lock.json`을 사용한다. 이 목록은
포함된 binary recipe만 대체하며, 운영 기준본은 그대로 보존한다. 의존성 JAR는 빌드 중
공식 URL에서 복원하고 해시를 검사한다. 호환 최신 버전 확인과 업데이트는 [의존성 관리](DEPENDENCIES.md)를 따른다.

## 한 번에 실행

Windows에서는 저장소 루트에서 실행한다.

```powershell
.\build-modpack.ps1
```

JDK와 Python이 환경 변수에 설정되어 있으면 Gradle wrapper를 직접 실행해도 된다.

```powershell
.\gradlew.bat build
```

Linux/macOS에서는 `JAVA_HOME`, `MINEFED_JAVA17_HOME`, `MINEFED_JAVA21_HOME` 및
`MINEFED_PYTHON`을 준비한 뒤 `./gradlew build`를 실행한다.

빌드는 다음 순서로 실행된다.

1. 전체 포함 모드에 소스 또는 바이너리 빌드 방침이 하나씩 있는지 확인한다.
2. JAR 전용 모드의 누락 파일을 공식 URL에서 복원하고 기록된 SHA-256을 검사한다.
3. 각 소스 모드를 해당 프로젝트의 Gradle 배포판과 JDK로 순서대로 컴파일한다.
   소스 내용·빌드 방침·JDK·빌드 도구가 같으면 해시를 검증한 소스 빌드 캐시를 사용할 수 있다.
4. 명시한 출력 경로에서 Fabric 런타임 JAR를 하나만 선택한다. 소스/Javadoc/dev JAR,
   모드 ID·버전·Minecraft/Java 요구사항 불일치, 중복 파일명은 오류로 처리한다.
5. 이번 실행에서 성공한 소스 JAR와 검증된 바이너리 JAR를 합쳐 ZIP을 생성한다.
   최종 ZIP의 CRC와 모든 JAR SHA-256을 다시 검사한다.

`build`는 제작을 담당하는 `assemble`과 검사를 담당하는 `check`를 모두 실행한다.
`check`에는 다음 검사가 포함되며, `modpack`은 이 검사 태스크 없이 제작 흐름만 실행한다.

- `testModpackTools`: JAR 무결성, 캐시·잠금, 실제 자식 프로세스 취소 등을 검사하는 Python unittest.
  심볼릭 링크를 만들 수 없는 환경에서는 해당 검사만 건너뛴다. 모드 컴파일이나 게임 실행은 하지 않는다.
- `verifySourceRepositories`: 로컬 테스트 저장소와 실제 Gradle의 `--offline` 실행으로
  Fabric 저장소 우선순위와 하위 프로젝트의 전용 저장소 정책이 함께 동작하는지 검사한다.
  모드 소스나 Minecraft는 빌드하지 않는다. 루트 Gradle 배포판이 준비된 뒤에는 네트워크가 필요 없다.

첫 실행에는 Gradle, Minecraft 및 모드 의존성 다운로드가 필요하다. 같은 `GRADLE_USER_HOME`
(미설정 시 사용자 홈의 `.gradle`)을 사용하는 이 도구의 실제 하위 Gradle 호출은 OS 파일 잠금으로
직렬화한다. 서로 다른 모드, 독립적인 루트 Gradle 실행, 별도 checkout도 같은 캐시 경로를 사용하면
같은 잠금을 따르며, 여러 단계로 구성된 모드의 생성·컴파일 호출도 잠금을 유지한 채 실행한다.
검증된 소스 JAR 캐시를 재사용할 때는 이 전역 잠금을 잡지 않는다. 같은 checkout에서 같은 모드의
중복 작업은 별도의 모드 잠금으로 보호한다.
실행기에 전달된 중단·예외는 해당 wrapper와 자식 프로세스를 정리한 뒤 잠금을 해제한다.

하위 디렉터리에서 직접 실행한 `gradlew` 등 외부 수동 Gradle 실행은 이 도구의 잠금에 참여하지 않는다.
첫 빌드로 캐시가 채워진 뒤에도 같은 Gradle 캐시를 사용하는 수동 빌드와 도구 빌드를 겹쳐 실행하지 않는다.

## 개발 환경

- JDK 17과 JDK 21. 루트 Gradle은 17로 실행하고, 21이 필요한 하위 프로젝트에는 별도로 선택한다.
  모드팩의 대상 Java 버전은 17이며, 빌드 JDK 버전과 구분한다.
- Python 3.10 이상. 추가 Python 패키지는 필요 없다.
- Git 및 초기화된 모든 서브모듈.
- Node.js 22와 npm. MTR의 웹 UI 생성에 사용하며 잠긴 `package-lock.json`으로 설치한다.
- 실행할 Minecraft 환경은 1.20.4 / Fabric Loader 0.18.0 이상을 준비한다.

minefed-display의 브라우저 화면을 렌더링하는 클라이언트에는 MCEF 2.1.6-1.20.4 이상이
추가로 필요하다. 서버에는 필수 의존성으로 두지 않으며, MCEF가 없는 클라이언트에서는
브라우저 렌더러를 활성화하지 않고 블록·URL 설정 UI는 유지한다.

Windows 실행기는 Git에 포함하지 않는 `build.local.json`의 도구 경로를 사용할 수 있다.
이 작업 공간에는 설치된 도구를 가리키는 로컬 설정이 준비되어 있다. 다른 PC에서는 예를 들어 다음과 같이 설정한다.

```json
{
  "java17Home": "C:/tools/jdk-17",
  "java21Home": "C:/tools/jdk-21",
  "pythonExecutable": "C:/tools/Python313/python.exe"
}
```

Gradle을 직접 실행할 때는 `MINEFED_PYTHON` 또는 `-PpythonExecutable=...`으로 Python을
지정한다. 하위 JDK는 `MINEFED_JAVA17_HOME`, `MINEFED_JAVA21_HOME`, 로컬 설정,
`JAVA_HOME`, 사용자의 `.gradle/jdks` 및 `.jdks`, 프로젝트 `.cache/jdks`에서 찾는다.
전역 환경 변수나 시스템 설치를 자동 변경하지 않는다.

```powershell
git -c core.longpaths=true submodule update --init --recursive
.\build-modpack.ps1 -Task modpackPlan
.\build-modpack.ps1 -Task source_alloy_forgery
.\build-modpack.ps1 -Task testModpackTools
.\build-modpack.ps1 -Task check
.\build-modpack.ps1 -Task build '-PrebuildSources=true'
```

`modpackPlan`은 전체 소스/JAR 구분과 이유를 출력한다. `source_<모드ID>` 태스크는 모드 ID의
하이픈을 밑줄로 바꾼 이름이며, 해당 모드만 빌드한다. 전체 목록은 `gradlew tasks --all`에서 확인한다.
`-PrebuildSources=true`는 소스 결과 캐시를 사용하지 않고 하위 Gradle 태스크를 다시 실행한다.
외부 의존성 업데이트를 확인하거나 컴파일 환경을 검토할 때 사용한다. 하위 Gradle의 자체
증분 컴파일은 그대로 적용된다. 소스나 빌드 방침을 바꾸면 별도 옵션 없이 캐시가 무효화된다.

## 결과물과 실패 처리

- 최종 파일: `build/distributions/minefed-1.20.4-<실행ID>.zip`
- 해시 파일: ZIP 옆의 `.sha256`
- 최근 패키징 성공 결과: `build/distributions/latest.json`
- 실행별 로그와 수집한 JAR: `build/modpack-work/<실행ID>/sources/<모드ID>/`

실행별 ZIP 이름을 사용하므로 이전 결과를 덮어쓰지 않는다. 소스 컴파일이나 최종 ZIP 발행 전의
소스·JAR·ZIP 검증이 실패하면 해당 실행의 배포 ZIP을 발행하거나 `latest.json`을 갱신하지 않는다.
진단용 로그와 임시 파일은 실행 작업 디렉터리에 남을 수 있다.

`check`는 `modpack`의 선행 조건이 아니므로, 패키징이 끝난 뒤 검사 태스크에서 실패하면 ZIP과
`latest.json`이 이미 만들어져 있을 수 있다. `latest.json`은 패키징 성공을 가리키며 전체 `build`의
검사 통과를 보증하지 않는다. 전체 빌드의 성공 여부는 Gradle 종료 코드와 검사 결과를 함께 확인한다.

ZIP에는 `mods/`의 JAR, 실제 결과의 해시·버전을 담은 `inventory/mods.lock.json`, 빌드 방침,
`BUILD-PROVENANCE.json`, 저작권·라이선스 고지와 `PACK-INFO.json`이 들어 있다.
provenance에는 소스 커밋, 소스 파일의 내용 해시, 작업 트리 상태, JDK, 태스크, 최초 컴파일
실행 ID와 캐시 재사용 여부가 기록된다.
소스가 빌드 후 달라졌거나 결과의 실행 ID가 일치하지 않으면 패키징을 거부한다.
빌드 스크립트, JDK 및 사용자 Gradle 설정 등의 도구 지문도 캐시 재사용·빌드 완료·패키징 시
다시 확인한다. 도중에 도구가 바뀐 결과는 성공 캐시나 최종 ZIP에 넣지 않는다.

이전 하위 JAR가 잘못 선택되는 일을 막기 위해, 명시한 출력 경로의 기존 JAR는 실행 작업
디렉터리의 `previous/`에 보존한 뒤 다시 생성한다. 소스 빌드 실패를 운영 JAR로 자동 대체하지 않는다.
JAR 전용 모드 중 공식 다운로드 URL이 없는 파일은 원래 기록된 해시와 일치하는 파일을 직접 복원해야 한다.

소스 코드를 수정한 상태에서도 내용 해시와 변경 상태를 기록하여 빌드할 수 있다. 브랜치의 HEAD를
바꿨다면 하위 커밋을 원격에 push한 뒤 상위 gitlink와 lock을 함께 갱신한다. 버전 변경 시에는
빌드 방침의 `expectedVersion`과 필요한 출력 경로도 검토하여 수정한다.

## 운영 기준 ZIP과 구분

`python scripts/mods.py pack --private`는 이전과 같이 서버에서 수집한 JAR만 묶는다.
새 Gradle 빌드는 관리 중인 소스를 컴파일하므로 모드 버전이나 바이트가 운영 기준본과 달라질 수 있다.
ZIP 안의 결과 목록을 기준으로 확인한다.

생성물은 로컬 검토용 비공개 ZIP이다. 소스·자산의 라이선스 고지를 보존하며, 공개 배포 권한이나
대응 소스 제공 의무는 모드별 기록을 따른다. 이 작업은 서버 파일 변경·업로드·재시작을 하지 않는다.
Minecraft 서버/클라이언트 기동 검증은 별도 단계이며 `runtimeValidated`는 `false`로 기록한다.

## 빌드 방식

모드별 wrapper를 보존하는 Gradle `Exec` 태스크를 사용한다. 전체 저장소를 단일 composite build로
묶으면 루트의 Gradle 버전이 하위 프로젝트에도 적용되어 서로 다른 Loom·Forge 플러그인 요구사항이
충돌할 수 있다. 각 하위 Gradle에서 만든 최종 Fabric JAR를 명시적으로 수집한다.
참고: [Gradle composite builds](https://docs.gradle.org/current/userguide/composite_builds.html),
[Gradle Exec 태스크](https://docs.gradle.org/current/dsl/org.gradle.api.tasks.Exec.html).

wrapper JAR가 생략된 프로젝트는 루트의 추적된 bootstrap JAR와 하위 배포판 properties를
실행 디렉터리에 복사해 사용한다. wrapper 자체가 없는 fabric-webstreamer는 명시적으로 루트의
Gradle 8.13을 사용한다. BlueMap의 1.20 구현과 Yuushya의 1.20.4 생성/컴파일 단계처럼 별도
작업 디렉터리나 여러 호출이 필요한 경우도 빌드 방침에 기록한다.
