# 진단 모드의 스레드 수집 정지 수정 — 2026-10-18

`minefed-diagnostics` 1.1.2는 진단 스레드가 스택을 수집할 때 힙 전체를 조사하던 경로를 제거한다.
운영 서버의 파일 변경·업로드·재시작은 수행하지 않았다. 기존 10월 17일 검증 기록은 보존한다.

## 원인과 수정

기존 `ThreadMXBean.getThreadInfo(ids, true, true)`는 한 스레드만 조회해도
소유 중인 synchronizer 목록을 얻으려고 safepoint에서 힙을 조사한다.
첨부된 운영 JFR에서 진단 watchdog/capture가 요청한 `ThreadDump` VM operation이
수 초씩 반복됐다. 힙 증설만으로 해결할 수 있는 문제가 아니었다.
구현 근거는 [OpenJDK 21 ThreadService](https://github.com/openjdk/jdk21u/blob/jdk-21.0.10%2B7/src/hotspot/share/services/threadService.cpp)
및 [HeapInspection](https://github.com/openjdk/jdk21u/blob/jdk-21.0.10%2B7/src/hotspot/share/memory/heapInspection.cpp)이다.

- 단일·락 소유자 표본은 `getThreadInfo(id, 256)`을 사용한다.
- 전체 스택은 `dumpAllThreads(false, false, 256)`, 교착 상세는 깊이 제한 조회를 사용한다.
  현재 기다리는 락과 소유자는 보존하고 소유 락 전체 목록은 생략한다.
- 기존 설정 파일에 50ms가 남아 있어도 최소 표본 간격은 250ms다.
  간격은 수집 완료부터 계산하고, 느린 수집 후에는 소요 시간의 4배를 기다린다(최대 30초).
  새 정지가 시작돼도 이 대기를 우회하지 않는다.
- 자동·진행 중·청크·수동 보고서의 전체 스냅샷과 교착 검사는 공통 제한을 사용한다.
  동시에 들어온 요청은 기다리지 않고 생략하며, 완료 또는 실패 후 30초를 기다린다.
  보고서에는 생략 사유를 남긴다.
- 자체 순환 JFR의 `jdk.ThreadDump`를 꺼서 별도 전체 덤프 경로를 제거한다.
  실행 표본·틱·GC·VM operation 기록은 유지한다.
- 표본 수집 중 서버가 회복했다면 예정돼 있던 정지 중 전체 덤프를 생략한다.

## 빌드와 검증

대상은 Minecraft 1.20.4 / Fabric Loader 0.18.4 이상 / Java 17 이상이며 서버 전용이다.
Fabric API가 필요하다. 통합 브랜치는 `minefed-1.20.4`, 소스 커밋은
`b67a7241f95273160564a75b63d8d3f4e4c4f56e`다. MIT 라이선스를 JAR에 보존했다.

| 항목 | 결과 |
| --- | --- |
| Java 17 `test build` | 49개 통과, 실패·오류·건너뜀 0 |
| Java 21 전체 테스트 | 49개 통과, 실패·오류·건너뜀 0 |
| Vanilla + Fabric 격리 서버 | 자동 수집·회복·정상 종료, 내부 오류 0 |
| Lithium 0.12.1 + Fabric 격리 서버 | 자동 수집·회복·정상 종료, 내부 오류 0 |
| 실제 서비스의 기존 50ms 설정 | 두 서버 모두 250ms 적용 확인 |
| 대기 락 소유자·256프레임 제한·30초 생략 | 보고서에서 확인 |
| 생성된 4개 JFR | 파싱 성공, 틱·GC·VM operation 증거 유지 |
| `jdk.ThreadDump` 이벤트 | 4개 JFR 모두 0 |
| 10ms 이상 `ThreadDump` VM operation | 두 서버 모두 기록 0건 |

단위 테스트는 락 목록 수집 옵션을 요청하면 즉시 실패하는 MXBean 대역, 실제 BLOCKED 스레드의
소유자 정보, 깊은 스택의 제한, 느린 표본 이후 대기, 동시 덤프·실패 후 재시도 제한을 검증한다.
격리 서버는 테스트용 락으로 첫 틱을 6.5초 막은 뒤 해제하고, 40틱에 각각 90ms 지연을 넣었다.
비서버 스레드의 청크 요청과 명시적 GC 1회도 시험했다. 운영 월드나 서버는 사용하지 않았다.

운영 성능 수치는 아니다. 격리 검증은 Windows / OpenJDK 21 / G1 / 최대 2GiB 힙에서 수행했다.
`ExecuteVMOperation` 기록 임계값은 10ms이므로 기록 0건을 실제 호출 0회 또는 소요 시간 0ms로
해석하지 않는다. 짧은 JVM safepoint와 JFR·파일 쓰기의 비용은 남는다.
다른 JFR 녹화가 같은 이벤트를 켜면 JVM의 합쳐진 설정에 영향을 줄 수 있다.
실제 Linux/GraalVM 서버의 잔여 랙은 교체 후 기록으로 확인해야 한다.

빌드는 `./gradlew test build`를 사용했다. Windows 한글 경로 때문에 테스트 실행 시
Java 17은 `-Dorg.gradle.jvmargs=-Xmx1G`, Java 21은
`"-Dorg.gradle.jvmargs=-Xmx1G -Dfile.encoding=COMPAT"`로 Gradle 데몬 인코딩을 조정하고,
테스트 JVM의 `java.io.tmpdir`에 ASCII 경로를 지정했다. 제품 소스의 인코딩은 UTF-8이다.
자세한 결과는 [검증 JSON](../inventory/diagnostics-pause-fix-2026-10-18.json)에 기록한다.

## 교체 파일

- 파일: `artifacts/local/minefed-diagnostics-1.1.2.jar` (113,708바이트)
- SHA256: `ff689ff13db4f43982669b063265ca142ff03f458a3563b7681bad6e4953d81e`
- 대응 소스: `minefed-diagnostics/build/libs/minefed-diagnostics-1.1.2-sources.jar`

서버를 정상 종료한 뒤 `mods`에서 기존 `minefed-diagnostics-*.jar`를 빼고 새 JAR 한 개를 넣어
재기동한다. 클라이언트에는 설치하지 않는다. 기존 설정 파일은 그대로 사용할 수 있다.
이번 교체에 JVM 힙·GC 설정 변경은 필요하지 않다.
교체 후에도 랙이 남으면 같은 시각의 `latest.log`와 `logs/minefed-diagnostics`를 함께 수집한다.
