# 서버 tick 정지 자료 수집

운영자가 **Linux Podman 호스트에서 직접 실행**하는 Python 3 표준 라이브러리 도구다. 서버를 재시작하거나 설정을 바꾸지 않는다. 이 도구를 저장소에 추가한 것만으로 운영 서버에서 실행되지는 않는다.

호스트에는 Python 3와 Podman, 컨테이너에는 `sh`, `timeout` (`-k` 지원), `jcmd`, `jfr`, `sha256sum`, `cat`, `awk`가 필요하다. `--pid`는 **컨테이너 내부 JVM PID**이며 0은 허용하지 않는다. `--user`는 해당 JVM에 attach할 권한이 있는 컨테이너 UID다. 컨테이너 이름·PID·UID는 자동 탐색하거나 기본값으로 추정하지 않는다.

아래 `minefed_fabric_1`, PID `1`, UID `0`은 과거 관측값을 사용하는 **예시**다. 현재 실행 대상을 확인하고 값을 바꾼다. 출력 폴더는 존재하지 않는 새 경로여야 한다.

```bash
python3 tools/server-stall-capture/capture.py record \
  --container minefed_fabric_1 --pid 1 --user 0 \
  --output .cache/server-stall/record-20261017-01
```

기본 수집 시간은 600초다. `--duration 300`으로 바꿀 수 있고 허용 범위는 10~3600초다. JVM은 고유한 이름의 `profile` JFR을 기록하며 `maxage=10m`, `maxsize=128M`으로 제한한다. 10분보다 긴 실행은 마지막 최대 10분이 남는다. 정상 종료 시 도구가 자기 recording만 중지하고, 도구가 사라진 경우에도 요청 시간 +30초 후 JVM이 자체 종료해 `/tmp/minefed_stall_<고유값>.jfr`에 저장한다. **Ctrl+C 한 번**은 recording을 중지·검증·복사한 뒤 마무리한다. 마무리 중 다시 중단하면 자료가 불완전할 수 있다.

외부 명령을 실행하기 전에 `manifest.json`에 `collecting` 상태와 고유 recording 이름·원격 파일 경로를 저장한다. 도구가 강제 종료됐다면 이 경로에서 복구할 수 있다. 중지 명령이 실패하거나 시간이 초과돼도 해당 고유 파일의 검증·복사를 시도하며, 파일이 복구됐더라도 실패와 불확실성은 `failed` 상태로 남긴다. 명령 timeout 전의 stdout/stderr도 원문 파일에 보존한다.

완전 정지가 발생하면 첫 번째 기록을 계속 둔 채 **별도 터미널**에서 다음을 실행한다.

```bash
python3 tools/server-stall-capture/capture.py snapshot \
  --container minefed_fabric_1 --pid 1 --user 0 \
  --output .cache/server-stall/snapshot-20261017-01
```

`snapshot`은 `Thread.print -l`을 약 2초 간격으로 3회 수집한다. 다른 JFR을 시작하거나 종료하지 않는다. JVM attach 자체가 멈췄다면 각 명령은 실패로 남으며, 덤프를 얻었다고 보고하지 않는다. 컨테이너 안의 `timeout`과 호스트의 subprocess timeout을 함께 사용한다. 권한 부족, 도구 부재, attach 실패, timeout, JFR 검증 실패는 종료 코드 1과 `manifest.json`의 `failed`로 표시된다. 실행 전 인수·출력 경로 오류는 종료 코드 2다.

두 명령 모두 3초 간격(`--interval 2`~`5`)으로 JVM `/proc` 상태·I/O와 컨테이너에서 보이는 CPU·메모리·pressure·네트워크 카운터를 별도 작업에서 수집한다. 샘플 명령이 오래 걸리면 실제 간격은 늘어난다. cgroup v2의 보고 경로와 후보 경로, 각 파일의 존재 여부를 그대로 기록한다. 파일 부재를 압력 0으로 해석하면 안 된다. `/proc` 일부 값은 컨테이너 제한값이 아닌 호스트 전체일 수 있으므로 `cpu.stat`, `cpu.max`, `memory.events` 및 실제 cgroup 경로와 함께 판독한다. `net/dev`는 컨테이너 네트워크 namespace 합계이며 Minecraft 연결만의 RX가 아니다.

출력에는 UTC 시작·종료 시각, 최근 15분의 최대 10,000줄 컨테이너 로그, OS 원문 샘플, 덤프 또는 검증된 `recording.jfr`가 들어간다. JFR은 컨테이너의 `jfr summary` 성공·양수 chunk 수, 복사본의 헤더·최소 크기, 원격 파일과 복사본의 SHA-256 일치를 확인한다. 로그·덤프·JFR에는 플레이어 이름, 좌표, IP, 경로 등 민감한 정보가 들어갈 수 있으므로 공유 전에 비식별화한다. JFR 시작 시 `jdk.InitialEnvironmentVariable`, `jdk.InitialSystemProperty`, `jdk.JVMInformation` 이벤트를 비활성화하며 환경변수·전체 프로세스 명령행을 별도 수집하지 않는다. 다른 JFR recording이 이미 실행 중이면 JVM 전체 이벤트 설정의 영향으로 이 이벤트가 함께 기록될 수 있으므로 민감정보가 없다고 보장하지 않는다. heap dump와 GC 강제 실행은 하지 않는다. 컨테이너의 고유 `/tmp` JFR은 복구를 위해 남긴다.

출력 디렉터리는 Linux에서 사용자 전용 권한(0700)으로 생성한다. 예시의 `.cache/`는 이 저장소의 Git 제외 경로다. 다른 출력 경로를 쓰더라도 원본 자료를 공개 Git에 추가하지 않는다. 컨테이너 로그 드라이버에 Minecraft 로그가 나오지 않는 구성에서는 서버의 `logs/latest.log`도 별도로 보관해야 한다. 이 도구는 로그 경고를 감지해 자동으로 덤프하지 않으므로, rx 정지 시 두 번째 터미널에서 `snapshot`을 실행한다.

확인할 것은 지연 시각과 같은 구간의 `Server thread` 스택, CPU throttle 증가, I/O·메모리 압력, GC pause, 네트워크 RX 변화다. `ticks behind`의 수치는 누적 일정 지연이므로 단일 tick 실행시간으로 읽지 않는다. JFR profiling과 thread dump에도 일시적 부하가 있으므로 동일 조건의 평상시 자료와 비교한다.

로컬 검증(운영 서버에 연결하지 않음):

```bash
python3 -m unittest discover -s tools/server-stall-capture -p 'test_*.py'
python3 tools/server-stall-capture/capture.py --help
```

2026-10-17 검증: 가짜 Podman runner를 사용한 단위 테스트 15개 통과. 별도 로컬 Java 21.0.12.1 JVM에서 동일 JFR 옵션·스레드 덤프·이름 지정 중지를 실행해 258,207바이트, 1 chunk의 유효 JFR을 확인했다. 해당 단독 recording에서 위 민감 메타데이터 이벤트는 각각 0개였다. Linux Podman 전체 연동 및 운영 Minecraft 장애 재현은 수행하지 않았다.
