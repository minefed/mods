# 운영 JAR 준비 도구

Python 3.10 이상과 표준 라이브러리만 사용합니다. 소스 검증에는 Git도 필요합니다.
저장소 루트에서 실행합니다. Python 실행 파일이 `python`으로 등록되지 않았다면 설치된
Python 실행 파일의 전체 경로를 사용하세요.

기반 라이브러리 빌드 pin은 `inventory/dependencies.lock.json`에 별도로 둡니다.
`python scripts/check_dependencies.py`로 Minecraft 1.20.4/Fabric의 최신 안정 릴리즈를
조회하며, `--id fabric-api`로 대상을 좁히거나 `--output build/dependency-updates.json`으로
결과를 저장할 수 있습니다. 이 명령은 메타데이터만 조회하고 lock과 JAR를 바꾸지 않습니다.
업데이트 절차와 운영 기준본과의 구분은 [의존성 관리 Q&A](../docs/DEPENDENCIES.md)를 참고하세요.

```powershell
python scripts/mods.py verify
python scripts/mods.py verify --sources
python scripts/mods.py stage
python scripts/mods.py pack --private
python scripts/mods.py hydrate
python -m unittest discover -s scripts -p test_mods.py
```

- `verify`: `inventory/mods.lock.json`의 모든 항목을 검사합니다. 제외된 JAR도 크기,
  SHA-256, Fabric의 ID·버전·실행 환경을 확인합니다. Fabric 메타데이터가 없는 플러그인은
  `modId: null`로 기록하며 Fabric 메타데이터 비교를 적용하지 않습니다.
- `verify --sources`: 위 검사와 함께 `.gitmodules`의 경로·URL, Git 인덱스의 gitlink,
  초기화된 서브모듈의 HEAD 및 작업 트리 변경 여부를 확인합니다. 별도 `sourceRepositories`
  항목도 검사하며, lock에 없는 `.gitmodules` 경로는 오류로 처리합니다. 네트워크 요청을 하지
  않으므로 원격 커밋의 접근 가능성은 별도로 확인해야 합니다.
- `stage`: `included: true`인 JAR만 `build/staged-mods/`로 복사합니다. 포함된 모드 ID가
  중복되거나 무결성 검사가 실패하면 진행하지 않습니다. 동일한 파일로 다시 실행할 수
  있지만 출력에 수정된 파일이나 예상하지 못한 파일이 있으면 보존한 채 실패합니다.
- `pack`: 포함된 JAR, 전체 lock 파일, `LICENSES.md`, 원본 JAR 내부의 라이선스 고지,
  존재하는 소스 저장소의 최상위 라이선스 파일, `inventory/notices/`, `inventory/licenses/` 및 `licenses/`의
  고지를 `build/minefed-baseline.zip`에 넣습니다. 기존 ZIP은 덮어쓰지 않습니다.
  `local-only` 항목이 포함되어 있으면 기본적으로 실패하며, 개인 로컬 보관용 ZIP을
  만들 때만 `--private`를 사용합니다. `modpack-only`는 모드팩에 포함할 수 있다는
  기록으로 취급합니다. 이 옵션과 도구는 추가적인 재배포 권한을 부여하지 않습니다.
- `hydrate`: 기록된 공식 HTTPS `artifact.url`에서 없는 JAR만 다운로드합니다. 기록된
  크기와 SHA-256을 검증한 뒤 같은 파일시스템에서 원자적으로 설치합니다. 기존 파일은
  검증 후 유지하며, 수정된 파일은 덮어쓰지 않습니다. URL이 없는 항목은 다운로드 가능한
  파일을 복원한 다음 목록으로 보고하고 오류 종료합니다. 그 항목은 기록된 JAR를 직접
  복원해야 합니다. 쓰기 위치는 `.cache/server-mods/`, `artifacts/local/`, `vendor/jars/`,
  `vendor/local/`로 제한합니다. 다른 파일시스템에서 하드링크를 지원하지 않으면 안전하게
  실패합니다. 다운로드된 파일은 `verify`로 전체 메타데이터도 확인하세요.

출력 위치는 `--output build/다른이름`으로 지정할 수 있습니다. `pack` 출력은 `.zip`으로
끝나야 합니다. 경로는 저장소 기준 `/` 구분자를 사용하며 절대 경로, `..`, 심볼릭 링크,
Windows junction을 허용하지 않습니다. 도구는 디렉터리를 재귀 삭제하지 않습니다.
실패 전에 생성한 정상 stage 파일은 남을 수 있으며, 다시 실행해 검증하고 이어갈 수 있습니다.
다른 lock은 공통 옵션을 명령 앞에 지정합니다.

```powershell
python scripts/mods.py --manifest inventory/mods.lock.json pack --private --output build/private-baseline.zip
```

이 도구는 기록된 운영 바이너리의 준비와 복사를 담당합니다. 서브모듈을 컴파일하거나,
의존성·Minecraft API 호환성을 해결하거나, 서버 실행 검증·업로드·배포·재시작을 수행하지
않습니다. ZIP 생성 성공은 공개 배포 또는 실제 실행 가능성의 검증을 의미하지 않습니다.
일부 소스 pin은 운영 JAR와 다른 버전일 수 있으므로 lock의 버전 및 주석을 확인하세요.
