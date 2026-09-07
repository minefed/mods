# Automobility 관리 Q&A

## Q. 왜 Automobility와 Automobility-Refueled 저장소가 둘 다 있나요?

**기존 백포트 작업의 소스를 보존하면서, 실제 운영 JAR에 대응하는 Refueled 소스를 별도로 등록했기 때문이다.** 두 모드가 함께 필요한 구조는 아니다.

| 구분 | Automobility | Automobility-Refueled |
| --- | --- | --- |
| 원본 프로젝트 | [FoundationGames/Automobility](https://github.com/FoundationGames/Automobility) | [codenobacon4u/Automobility](https://github.com/codenobacon4u/Automobility) — 원본에서 파생된 포크 |
| Minefed에서의 역할 | 기존 1.20.4 백포트 작업 보존 | 관측한 운영 JAR의 소스 및 현재 빌드 입력 |
| 소스 버전 | `0.5.0.h` | `0.4.3.b+1.20.4-fabric` |
| Fabric 모드 ID | `automobility` | `automobility-refueled` |
| Fabric 메타데이터의 요구사항 | Minecraft `1.21.x`, Java `>=21` | Minecraft `1.20.x`, Java `>=17` |
| 현재 모드팩 입력 | 제외 | 포함 |

역할과 고정 커밋은 [mods.lock.json](../inventory/mods.lock.json)에 기록되어 있다. 기존 `Automobility`는 `sourceRepositories`의 `included: false` 항목이고, 운영 JAR 목록에는 `automobility-refueled`만 있다. [빌드 recipe](../inventory/build-recipes.json)도 `Automobility-Refueled`의 `:fabric:remapJar`만 호출한다.

Refueled의 [1.20.4 배포 페이지](https://github.com/codenobacon4u/Automobility/releases/tag/v0.4.3.b%2B1.20.4)는 해당 버전을 Minecraft 1.20.4로 이식한 배포물로 설명하며, GitHub에서 사전 릴리즈로 표시한다. 현재 선택은 이 운영 기준본과의 대응에 따른 것이며, 모든 버전 중 최신 안정판이라는 의미는 아니다.

## Q. Refueled는 원본 Automobility가 필요한 확장 모드인가요?

**아니다. Refueled가 차량 기능을 자체적으로 포함하는 대체 포크다.**

- Refueled의 [fabric.mod.json](../Automobility-Refueled/fabric/src/main/resources/fabric.mod.json)에 선언된 필수 의존성은 Fabric Loader, Fabric API, Minecraft, Java다. 원본 `automobility` 의존성은 없다.
- [settings.gradle](../Automobility-Refueled/settings.gradle)은 같은 저장소 안의 `common`과 `fabric` 프로젝트만 구성한다. [Fabric 빌드 설정](../Automobility-Refueled/fabric/build.gradle)은 내부 `common` 코드와 리소스를 JAR에 포함하며, 형제 저장소 `Automobility`를 참조하지 않는다.
- Fabric API 등 외부 빌드 의존성은 Maven 좌표로 가져온다. Refueled를 빌드하기 위해 `fabric-api` 소스 저장소를 함께 컴파일할 필요도 없다.

따라서 원본과 Refueled를 둘 다 설치할 대상으로 취급하면 안 된다. 두 저장소를 가지고 있다는 사실이 두 JAR를 모드팩에 넣는다는 뜻은 아니다.

## Q. 기존 Automobility를 바로 사용하거나 두 소스를 합쳐도 되나요?

**현재 Minecraft 1.20.4 / Fabric 구성에서는 Refueled를 유지한다. 원본으로의 교체나 코드 통합은 별도의 이식·호환성 검증 작업이다.**

기존 `Automobility`의 [gradle.properties](../Automobility/gradle.properties)는 Minecraft `1.20.4`로 바뀌었지만, [fabric.mod.json](../Automobility/fabric/src/main/resources/fabric.mod.json)은 여전히 Minecraft `1.21.x`와 Java 21을 요구한다. 버전 숫자만 낮췄다고 1.20.4 이식이 완료된 것은 아니다.

보존한 소스 이력은 다음과 같다. 전체 커밋과 브랜치는 lock 파일에서도 확인할 수 있다.

- 기존 Automobility 기준: `1.20.4-backport` / `831011268f914a308bde4500ec510d7659de7398`. 해당 커밋은 의존성 버전을 변경하며, 앞선 `277319bbd9e05c2845925b47bede0cb63f944797`은 Quilt Maven 저장소를 추가한다.
- 기존 Automobility 관리: `minefed-1.20.4` / `d636cdaefa81933b6e73e435ef37b4b8e5846c96`.
- Refueled 배포 기준: `v0.4.3.b+1.20.4` / `96a6369eed2e5528ba8d09c643e032cf7fa15c51`.
- Refueled 관리: `minefed-1.20.4` / `13160075fb4be333fe2b425183c02f9dc2348184`. 배포 기준과의 차이는 `AGENTS.md` 추가이며, Minefed 전용 차량 기능 변경은 없다.

기존 소스는 이전 작업의 복구·참조를 위해 남아 있다. 운영 빌드에는 필요하지 않으므로, 앞으로 활성 서브모듈에서 분리할 경우에도 원격 저장소 URL, 추적 브랜치와 위 전체 커밋을 보존하면 된다. 실제 기능을 옮길 필요가 생기면 변경별로 검토하고 이식한다.

## Q. 모드 ID가 다르면 리소스팩과 월드 데이터도 완전히 분리되어 있나요?

**아니다. Fabric의 모드 ID와 게임 리소스의 namespace를 구분해야 한다.**

두 코드의 내부 namespace 상수는 모두 `automobility`다. [원본 상수](../Automobility/common/src/main/java/io/github/foundationgames/automobility/util/InitlessConstants.java)와 [Refueled 상수](../Automobility-Refueled/common/src/main/java/io/github/foundationgames/automobility/util/InitlessConstants.java)에서 확인할 수 있다. Java 패키지와 Fabric 진입점도 `io.github.foundationgames.automobility`를 공유한다.

따라서 Refueled의 모드 ID에 맞춘다는 이유로 리소스팩의 `assets/automobility/`, 데이터팩의 `data/automobility/`, `automobility:` 리소스 참조를 일괄적으로 `automobility-refueled`로 바꾸면 안 된다. 반대로 namespace가 같다는 사실만으로 두 버전의 모델 형식, 등록 항목, 저장 데이터와 네트워크 처리가 호환된다고 판단할 수도 없다. 두 JAR를 함께 넣으면 클래스와 등록 이름이 겹칠 가능성도 있다.

원본으로 교체할 때는 별도 테스트 월드에서 기존 차량·부품 데이터와 사용자 정의 리소스를 확인하고, 서버와 클라이언트 양쪽에서 로딩·승차·렌더링을 검증해야 한다. 이 문서는 소스와 관리 설정을 확인한 결과이며, 교체 후 Minecraft 실행 호환성을 검증한 기록은 아니다.

## Q. 앞으로 무엇을 기준으로 관리하나요?

- **활성 차량 모드:** `Automobility-Refueled` 하나를 현재 1.20.4 빌드·배포 입력으로 사용한다.
- **보존 소스:** 기존 `Automobility`는 미완성 백포트 이력을 보존하는 자료로 구분한다. 보존 소스를 업데이트하더라도 자동으로 운영 모드에 포함하지 않는다.
- **외부 공통 라이브러리:** Fabric API처럼 자체 수정이 필요하지 않은 의존성은 호환되는 공식 배포물을 버전·해시·출처로 고정할 수 있다. 이 선택은 차량 모드 소스 관리와 별개다.
- **변경 검증:** 소스 변경, 빌드 결과 검증, 게임 실행 확인과 운영 서버 적용을 구분한다. 운영 서버 파일 변경·업로드·재시작은 별도 요청이 있을 때 수행한다.
