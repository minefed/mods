# 2차 성능 개선 구현과 검증 — 2026-10-12

Minecraft **1.20.4 / Fabric / Java 17**을 대상으로 배포용 차량 모델 정리,
Oritech 내부 Inventory 재사용, C&B 아이템 모델 캐시 예산을 구현했다.
운영 서버 파일·설정·업로드·재시작과 게임 설치 폴더는 변경하지 않았다.

## 구현한 변경

| 저장소 | 변경 | 보존한 동작·외관 |
| --- | --- | --- |
| resourcepack | 차량 BBMODEL 11개에서 MTR가 읽지 않는 최상위 제작 데이터와 내장 PNG를 배포본에서 제거 | Git 원본 전체를 비공개 design에 바이트 그대로 보존. 모든 nested 기하·숫자·UV·계층·재질·순서, PNG, 차량 등록 6개와 모델 참조 26개 유지 |
| Oritech | 안전한 내부 레시피 조회와 출력 검사의 detached Inventory를 재사용 | 보호 getter의 새로운 스냅샷 반환, ItemStack alias, 슬롯 읽기 시점과 조회·제작 순서, 호퍼·파이프 및 GUI 동작 유지 |
| Chisels-and-Bits | 기존 100개 count/FIFO 정책에 기본 64 MiB 추정 저장량 예산 추가 | 전체 ItemStack NBT 스냅샷·중첩 변경 감지, 모델 생성 본문, 정점·UV·색상·조명·그리기 순서와 random 호출 유지 |

차량 배포본은 `resolution`, `elements`, `groups`, `outliner`만 보존하며, nested
객체는 생략하거나 숫자를 반올림하지 않는다. MTR의 실제 파서·로더·렌더 소스를 확인하고
파서의 serialization과 재귀 UUID 계층을 전후 비교했다. 기존 validator는 보존 원본과
배포본 projection을 함께 확인한다. A1000 생성기는 보존 원본을 읽고 1차의 공유 텍스처 ID를
유지한다. 한 차량만 재생성한 full/compact 혼합 입력의 capture와 반복 compact도 검증했다.
BBMODEL은 scoped Git byte 정책을 사용하며, 알려진 텍스트의 LF/CRLF 표현만 허용한다.
PNG·다른 바이너리와 제작 원본·배포 모델은 정확한 바이트로 검증한다.

Oritech은 vanilla RecipeManager와 실제 `OritechRecipe`/`SmeltingRecipe`의 동기 조회만
재사용한다. 커스텀 레시피·manager·Inventory getter/view override와 재진입은 기존 경로를
사용한다. 레시피 타입 map의 동일성이 바뀌면 재사용 가능 여부를 다시 판단한다.
실제 1.20.4 `apply`/`setRecipes`의 immutable map 교체와 access widener의 named/intermediary
descriptor를 확인했다. manager와 map은 약하게 참조하고, 빌린 슬롯 참조는 `finally`에서
비운다. 기존 외부 스냅샷을 재사용 객체로 바꾸지 않았다.

C&B의 예산은 저장된 모델 배열·quad·vertex 데이터와 Minecraft NBT 크기 추정·고정 비용의
합이다. 가중치 계산은 새 항목에만 적용하며 `getQuads`·random·텍스처 조회를 추가하지 않는다.
count 또는 예산이 0이면 보관을 생략한다. 전체 예산보다 큰 항목과 알 수 없는 모델은 정상
반환하면서 보관을 생략한다. supplier·가중치 계산은 lock 밖에서 실행하며, 기존 클라이언트
리로드/캐시 clear에 연결하고 clear 이전에 시작한 build가 다시 보관되는 것을 generation으로 막는다.

## 확인한 작업량과 용량

- **차량 모델:** Git 원본 기준 7,547,160 → 2,040,498 bytes, **5,506,662 bytes(약 73%) 감소**.
  이전 7,860,995 bytes 수치는 Windows CRLF 체크아웃 표현이었다. 기준 Git blob과 전체
  원본 보존 사본이 일치하며 두 표현의 해시·크기를 구분해 기록했다.
- **게임 파일 ZIP:** 두 소스 커밋의 원본 Git blob로 같은 `resource_pack/` 115개 파일을
  기본 DEFLATE·고정 timestamp·정렬 순서로 압축해 1,053,704 → 797,604 bytes,
  **256,100 bytes 감소**를 확인했다. 체크아웃/archive 속성에 따른 줄바꿈 변환을 제외했다.
  기존 archive/export 표현의 1,060,995 → 797,712 bytes 비교도 별도로 기록했다.
  추가 릴리즈 고지·메타데이터를 제외한 로컬 패키징 비교이며 실제 릴리즈 크기나
  운영 서버 송수신량 측정은 아니다.
- **Oritech:** 재사용 warmup 뒤 입력 조회 10,000회와 출력 검사 10,000회에서 임시 varargs
  Inventory 및 `toArray` 생성 각각 **20,000 → 0회**. 전기로 1,000 tick·progress 조회 조건에서도
  각각 3,000 → 0회이며 레시피 조회 수·순서는 동일했다. 플랫폼 대역의 생성 계측으로,
  실제 CPU 시간·GC·힙 절감 측정은 아니다. 최초 사용·슬롯 크기 변경 때 재사용 Inventory를 생성한다.
- **C&B:** 항목 수와 추정 저장량을 함께 제한한다. 공유 모델·quad를 중복 계산할 수 있고,
  다른 block/model-manager 캐시는 같은 모델을 별도로 참조할 수 있다. **64 MiB는 전체 힙이나
  VRAM 상한이 아니다.** 초과 항목의 반복 재생성은 CPU 비용을 늘릴 수 있다. 설정 변경은
  다음 insertion/replacement부터 반영하며 기존 FIFO hit 수명은 유지한다.

## 소스 통합

단위별 검증 후 Conventional Commits로 커밋하고 각 하위 통합 브랜치에 FF 병합·push했다.
원격 전체 해시를 확인한 뒤 상위에서 저장소별 gitlink와 lock을 별도 커밋으로 갱신했다.
상위 통합 브랜치는 `main`이며 다른 버전의 upstream 브랜치나 기존 이력을 변경하지 않았다.

| 저장소 | 통합·추적 브랜치 | 이전 커밋 | 최종 커밋 |
| --- | --- | --- | --- |
| Oritech | minefed-1.20.4 | `a6c9c79ecf58430bdc1ead54b9d03aadd22302fc` | `a3051c0f1ac1eaab0d995f8d1540e49561bc2ac1` |
| Chisels-and-Bits | minefed-1.20.4 | `28723461a5afbfba6aa5c6e6349ffecd8da54ec0` | `4d7b7c871aec5df68156a19b5ef855f8b6e3a0a1` |
| resourcepack | main | `cb1f0cf1ed0ff9ee7ce9d2d3be56a52ba5b57914` | `ddbec63dcbbeecafe9f7044cdcd0f6dc935ec005` |

세부 단위 커밋·모델/PNG 해시·새 JAR의 SHA-256·크기·출처·호환성은
[산출물 기록](../inventory/phase2-optimizations-2026-10-12.json)에 있다.
관측한 운영 기준본 70개 JAR의 기존 해시는 바꾸지 않았다.

## 검증 범위

- **resourcepack:** 실제 MTR 파서 관련 생산 소스를 Java 17로 컴파일해 11개 모델 trace를 비교했다.
  등록 모델/PNG 26쌍, 원본 Git 바이트·nested projection·외부/내장 PNG 바이트와 RGBA 픽셀,
  나머지 추적 입력 303개, 두 기존 차량 validator를 확인했다. Git source archive와 새 Windows
  체크아웃, 강제 LF 텍스트 fixture, A1000 단일 생성/mixed capture 및 compact 멱등성 검사를 통과했다.
  디자인·서버 조각은 게임 파일 ZIP에 포함하지 않았다.
- **Oritech:** 생산 Machine/PoweredFurnace와 고정한 이전 소스를 플랫폼 대역에서 비교하여
  **12개 시나리오·433개 검사**를 통과했다. 슬롯 변경·직접 stack count 수정·출력 막힘·제작·NBT/
  dirty/network 상태·리로드·fallback·재진입·예외와 호출 순서를 확인했다. 기존 GUI **13개/96개**와
  실제 Minecraft/Fabric 의존성의 `:remapJar`도 통과했다.
- **C&B:** `:core:test` **12 suites / 50 tests**, 실패·오류·생략 0개. 새 weighted cache 9개와 실제
  DataAware factory/Chiseled/Combined model/NBT/BakedQuad 검사 7개를 포함한다. FIFO·교체·가중치/
  overflow·동시성·clear·초과/unknown bypass, 실제 ItemStack 저장 후 중첩 수정, quad 순서·packed
  정점/UV/색상/light/tint/direction/shade와 리로드를 확인했다. `:fabric:remapJar`도 통과했다.
- **상위 도구:** 전체 테스트 **226개(환경 의존 생략 12개)**, 빌드 레시피 관련 65개, offline 의존성
  정책 검사 2개와 워크플로 YAML 파싱을 통과했다. 최종 build plan과 `mods.py verify --sources`로
  기준본 70개 아티팩트, gitlink·lock·로컬 HEAD·깨끗한 하위 작업 트리 일치를 확인했다.
- **산출물:** 외부/재귀 내장 JAR CRC와 SHA-256, Fabric metadata, 변경 클래스의 Java 17 bytecode와
  테스트/동결 fixture 미포함을 확인했다. Oritech **1,144개**, C&B **517개** 리소스가 작업 직전
  소스 pin과 목록·바이트가 같다. C&B 517개는 기본 130개와 tracked datagen 387개다.
  세 저장소의 독립 읽기 검토를 완료했고 텍스트 줄바꿈 검증의 경계 사례를 수정했다.

역사적 로컬 JAR를 작업 전에 별도로 보존했다. C&B 기준 JAR는 직전 pin보다 오래된 출력이며
직전 소스를 새로 빌드한 기준본이라고 주장하지 않는다. JAR 클래스 차이에는 이전 변경이나
컴파일러 차이가 포함될 수 있다. 이번 변경 범위는 위 baseline→최종 소스 diff로 구분한다.

Oritech의 CC0-1.0, C&B의 MIT 소스 고지와 내장 의존성의 기존 출처·라이선스를 유지한다.
C&B JAR의 기존 `@license@` metadata placeholder와 고지 파일명 부재도 이번에 변경하지 않았다.
소스 라이선스와 해시·기존 의존성 라이선스 근거는 별도로 보존한다. 새 JAR는 Git에 추가하지
않았다. 전체 Blockbench 원본은 비공개 리소스팩 저장소의 `design/`에만 추가했으며 공개 게임
파일 배포 승인 범위를 확대하지 않았다.

## 재현과 측정 한계

Oritech의 `:verifyMachineInventorySnapshots :verifyFrameGuiSync :remapJar`와 C&B의
`:core:test :fabric:remapJar`를 상위 빌드 레시피 및 렌더 CI에 연결했다. 리소스팩의
[재현 절차](../resourcepack/verification/runtime-models/README.md)는 Python/기존 Node 검사와 실제
파서 probe를 설명한다. private 저장소 검사는 이번 로컬 검증에서 실행했다.

실제 게임 클라이언트·OpenGL 화면·FPS·프레임 시간·VRAM·GPU/CPU/RAM 사용률·운영 서버 TX/RX는
측정하지 않았다. 이번 묶음은 배포/JSON 로딩 입력량, 반복 Inventory 할당과 아이템 캐시 보관량을
줄이며 패킷 형식·요청 빈도·해상도·시야 거리·셰이더·게임 옵션은 바꾸지 않는다.
실제 외관과 성능 수치는 같은 팩·JVM·월드·시점에서 별도 게임 실행으로 확인해야 한다.
