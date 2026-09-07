# 통합 빌드 검증 기록

2026-09-07 Windows 작업 공간에서 기본 명령 `./build-modpack.ps1`의 전체 빌드를 완료했다.
소스 빌드 53개와 JAR 전용 15개를 포함하는 Minecraft 1.20.4 / Fabric 모드팩이다.

## 실행과 결과

- 빌드 입력의 상위 커밋: `10606abe02775293a777888372b95fe0f27e5a85`
- 실행 ID: `20260907-021301-c9b9b939`
- 기본 `build` 종료 코드: 0 (`BUILD SUCCESSFUL`, 8분 21초)
- ZIP: `build/distributions/minefed-1.20.4-20260907-021301-c9b9b939.zip`
- 크기: 305,637,157바이트
- SHA-256: `dc86f1798df132afd04375f135e428634e6078e20d6ebf038214802a65bada17`

53개 소스 모드는 고정한 커밋과 빌드 방침으로 실제 컴파일을 성공한 뒤, 최종 통합 실행에서
소스 내용·도구·빌드 방침·결과 해시가 일치하는 캐시를 재사용했다. 최종 ZIP 안의
`BUILD-PROVENANCE.json`에 모드별 최초 컴파일 실행과 이번 실행의 재사용 기록이 있다.
소스 모드를 운영 바이너리로 대체한 항목은 없다.

## 확인한 범위

- `testModpackTools`: 53개 검사 중 52개 통과, Windows 심볼릭 링크 권한에 따른 1개 건너뜀.
- `verifySourceRepositories`: 실제 Gradle의 오프라인 저장소 정책 검사 통과.
- 완성 ZIP을 다시 읽어 JAR 68개의 ID·버전·크기·SHA-256과 소스/JAR 분류를 확인했다.
  소스 결과 53개, 원본 바이너리 15개이며 미빌드 소스를 대신한 기준본은 0개다.
- ZIP의 CRC와 외부 SHA-256 파일이 일치한다.
- 실제 중첩 JAR 140개를 포함해 Fabric 메타데이터 208개와 Java 17에 적용되는 클래스
  35,158개를 검사했다. 누락된 중첩 JAR와 preview 클래스는 0개다.
- 중첩 JAR까지 확인한 메타데이터에서 필수 의존성 누락, 불일치, 피할 수 없는 `breaks`,
  요구 버전을 동시에 만족하지 못하는 항목은 서버·클라이언트 모두 0개다.
  Fabric Loader 0.18.4의 `VersionPredicate`로 Minecraft 1.20.4 / Java 17 /
  Fabric Loader 0.18.0을 평가했다. 게임 기동이나 Loader의 전체 SAT 해석을 대신하지 않는다.
- 서브모듈 58개의 gitlink·목록·실제 HEAD·원격 커밋과 커밋된 `AGENTS.md`가 일치한다.
  운영 기준 JAR 70개의 원본 버전·크기·해시·출처 필드는 보존했다.

Java 17 클래스 검사의 기존 예외는 원본 Axiom에 포함된 Lattice의 다른 Minecraft 버전용
클라이언트 mixin 17개다. 이 Java 21 클래스들은 전용 서버에서 선택되지 않고,
Lattice의 버전 선택 조건에서도 Minecraft 1.20.4에서는 제외된다. 원본 JAR는 변경하지 않았다.

Minecraft 서버/클라이언트는 실행하지 않았으며 `runtimeValidated`는 `false`다.
브라우저 렌더링의 선택 의존성 MCEF와 환경 준비 방법은 [빌드 안내](BUILDING.md)를 따른다.
결과물은 라이선스 고지를 포함하는 로컬 비공개 ZIP이며, 운영 서버에는 업로드하지 않았다.
ZIP과 도구 경로의 로컬 설정은 Git에 포함하지 않는다.
