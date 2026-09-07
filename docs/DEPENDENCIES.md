# 기반 라이브러리 관리 Q&A

## Q. Fabric API 같은 모드도 Minefed Git 저장소로 관리해야 하나요?

자체 수정이 없다면 공식 JAR 의존성으로 관리하는 편이 적절하다. Fabric API는 Fabric Loader에 내장된 파일이 아니라 별도로 설치하는 공통 라이브러리다. Fabric 공식 문서도 [Minecraft 버전과 로더에 맞는 JAR 설치](https://docs.fabricmc.net/players/installing-mods)를 안내한다. 다른 모드를 컴파일할 때 사용하는 Maven 의존성과 모드팩에 넣는 런타임 JAR도 서로 구분한다. Fabric API의 소스 checkout을 함께 빌드할 필요는 없다.

이번 전환 대상은 Fabric API, Architectury, Botarium, Lavender, owo, Resourceful Config, ResourcefulLib다. 각 소스의 조사 기준 커밋과 Minefed 관리 커밋 사이 변경이 `AGENTS.md`뿐임을 확인했다. 7개 gitlink와 소스 빌드 recipe를 제거하고 공식 바이너리 recipe로 전환했다. 기존 로컬 checkout은 무시 경로로 남기며 원격 fork와 Git 이력을 보존한다. 모드팩 입력은 68개를 유지하고, 소스 빌드는 53개에서 46개로 줄었다.

소스 고지와 라이선스는 [inventory/licenses/upstream](../inventory/licenses/upstream/)에 출처·전체 커밋·파일 해시와 함께 보존한다. 원본 JAR 고지, 라이선스 조사, 과거 fork 정보도 유지한다. 공식 배포물을 사용한다는 이유로 라이선스 범위를 확대하지 않는다.

## Q. 항상 최신 버전을 자동으로 내려받으면 되나요?

업데이트 후보는 **Minecraft 1.20.4 / Fabric에 대응하는 최신 안정 릴리즈**로 정하고, 실제 빌드는 검토한 정확한 버전과 해시를 사용한다. 전체 Minecraft 버전 중 최신 버전이나 beta/alpha를 자동 설치하면 호환성이 달라질 수 있다. 동일 커밋을 다시 빌드했을 때 같은 의존성을 복원하고 문제가 생겼을 때 되돌릴 수 있어야 한다.

- [mods.lock.json](../inventory/mods.lock.json): 관측한 운영 JAR 70개의 버전·해시. 과거 소스는 `sourceProvenance`로 보존한다.
- [dependencies.lock.json](../inventory/dependencies.lock.json): 기반 라이브러리 7개의 실제 빌드 pin. 공식 배포 ID·URL·SHA-256·SHA-512·크기·호환성·라이선스·`sourceReference`를 기록한다. `dependency: true`인 recipe와 정확히 대응해야 하며 누락 시 빌드를 중단한다.
- [dependency-policy.json](../inventory/dependency-policy.json): 최신 버전 조회 대상의 공식 Modrinth 프로젝트 ID와 게임·로더·안정 채널.
- [release-policy.json](../inventory/release-policy.json): 7개 공식 JAR는 Modrinth 다운로드 참조로 배포한다. 이 항목의 `artifact: built`는 혼합 빌드 결과를 선택한다는 뜻이며, 해당 recipe는 `binary`다.

## Q. 업데이트는 어떻게 진행하나요?

```sh
python scripts/check_dependencies.py
python scripts/check_dependencies.py --id fabric-api --output build/dependency-updates.json
```

조회 명령은 공식 Modrinth 메타데이터만 읽는다. Minecraft·Fabric·안정 채널을 다시 검사하고 게시 시각으로 최신 후보를 선택한다. 잠금 파일이나 JAR를 바꾸지 않으며, 네트워크 오류·호환 릴리즈 부재·잘못된 정책은 오류로 종료한다. 같은 배포 ID의 해시가 달라진 경우도 보고한다.

후보를 적용할 때는 공식 JAR의 SHA-512·크기와 실제 Fabric 메타데이터를 확인하고 SHA-256을 계산한다. 정확한 소스 ref·전체 커밋, 라이선스와 고지, 의존성 조건을 검토한 뒤 `dependencies.lock.json`과 해당 `release-policy.json`의 공식 다운로드 URL을 함께 갱신한다. 두 URL이 다르면 공개 패키징을 중단한다. 운영 기준본은 서버에서 새로 관측한 것이 아니므로 변경하지 않는다.

```sh
python scripts/mods.py --manifest inventory/dependencies.lock.json hydrate
python scripts/mods.py --manifest inventory/dependencies.lock.json verify
python scripts/build_modpack.py plan
python -m unittest discover -s scripts -p 'test_*.py'
```

모드팩의 서버·클라이언트 의존성 검사와 별도 테스트 환경에서의 기동 확인을 거친 뒤 배포한다. 검증한 단위마다 Conventional Commit을 남긴다. 조회 명령과 일반 빌드는 운영 서버 적용이나 자동 버전 상승을 수행하지 않는다.

## Q. 다른 기본 모드도 모두 전환하나요?

공식 배포물로 충분한 라이브러리는 같은 방식으로 순차 전환할 수 있다. 이번에는 변경이 지침 파일뿐인 7개로 범위를 한정했다. GeckoLib·Forge Config API Port·Puzzles Lib 등은 빌드 수정과 라이선스 포장 이력이 있어, 공식 JAR와의 대응 및 고지 보존을 별도 단위로 검토한다. 기능 수정, 포트, 자체 모드가 필요한 경우에는 소스 관리를 유지한다.
