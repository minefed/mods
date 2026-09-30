# RAM·GPU 최적화 구현 결과 — 2026-09-29

[RAM·GPU 최적화 제안](RAM_GPU_OPTIMIZATION_PLAN_2026-09-28.md)의 1~3단계를 구현한 결과다.
4단계(JVM·운영 설정)와 5단계(모드 추가)는 이번 요청 범위가 아니어서 구현하지 않았다. 운영 서버는 변경하지 않았다.

## 반영 상태

| 저장소 | 통합 브랜치 | 새 커밋 | 상태 |
| --- | --- | --- | --- |
| Minecraft-Transit-Railway | `minefed-1.20.4` | `0eebe623db14d545c147fa58fc0c2f8f7a838935` (12개) | push 완료, 루트 gitlink·lock 갱신 |
| MTR-Station-Decoration-Addon | `minefed-1.20.4` | `91cdd24f6fbf94a1b12f5432ce93d7168246e769` (3개) | push 완료, 루트 gitlink·lock 갱신 |
| minefed-client-compat | `main` | `87f3a19f20b1317729b4cad63217596286422112` (3개, 1.4.0) | push 완료, 루트 gitlink·lock·레시피 갱신 |
| minefed-display | `minefed-1.20.4` | `8b4cd45ba84560051d021dcacdee747b5a795e03` (3개) | push 완료, 루트 gitlink·lock 갱신 |
| fabric-webstreamer | `minefed-1.20.4` | `58fa06bbe8fa3e7c22a4dd426093e2b72880fc58` (4개) | push 완료, 루트 gitlink·lock 갱신 |

- minefed-display와 fabric-webstreamer는 처음에 push 권한이 없어 로컬에만 커밋했다. 이후 사용자가 권한을 허용해 같은 커밋을 fast-forward로 push하고 고정했다. 두 저장소의 라이선스·README 파일은 바뀌지 않아 `release-inputs.json`의 검토 기록은 그대로다.
- **동시 배포:** 이번 변경에는 패킷 형식 변경이 없다. 다만 client-compat 1.4.0은 기존처럼 서버와 클라이언트 양쪽에 설치한다. 새 믹스인은 모두 클라이언트 전용 설정이다.

## 단계별 결과

"검증"에는 이 세션에서 실제로 실행한 것만 적는다. 게임은 실행하지 않았으므로 게임 안 메모리 사용량은 측정하지 않았다.

### 1단계 — 누수·수명 수정 (화면 동일)

| # | 모드 | 커밋 | 내용 |
| --- | --- | --- | --- |
| 1-1 | minefed-display | `bd688da` | 접속 종료 때 모든 브라우저를 닫는다. 블록 엔티티가 제거되거나 청크가 언로드되면 해당 브라우저를 닫는다. |
| 1-2 | webstreamer | `6fcac58` | 레이어를 해제할 때 현재 grabber도 실행기에서 멈춘다. 32회 누수 뒤 스트림을 새로 시작할 수 없던 문제도 해소된다. |
| 1-3 | webstreamer | `b68b078` | 주기 정리 때 남는 8 MiB 원시 버퍼를 2개까지만 두고, 월드를 나가면 모두 해제한다. |
| 1-4 | MTR | `7a7b7fc` | `VertexArrayReleaseMixin`이 VAO·VBO·IBO를 `Cleaner`에 등록한다. 모든 부품과 사본이 공유하는 인덱스 버퍼 객체에 더 이상 도달할 수 없으면 렌더 스레드에서 지운다. |
| 1-5 | MTR | `34db9c8` | 모델 셰이더는 리소스 리로드 뒤(또는 컴파일이 계속 실패할 때)에만 다시 컴파일한다. |
| 1-6·1-7 | MTR | `170f08b` | 월드를 나갈 때 동적 텍스처와 삭제 대기 텍스처를 모두 해제한다. 잘라낸 원본과 업로드가 끝난 RAM 사본은 닫는다. 해제한 텍스처 이름은 재사용한다. |
| 1-8 | MTR | `ac5aa43` | 월드를 나가면 작업 스레드에서 가림 판정 캐시와 대기 작업을 버린다. |
| 1-9 | MSD | `25d5fcd` | 접속 종료 때 역 캐시와 이전 월드 데이터 참조를 비운다. |
| 1-10 | webstreamer | `ec56444` | FFmpeg 디코더 스레드를 3개로 고정한다. 디코딩 결과는 같다. |

### 2단계 — 블록 아틀라스

| # | 모드 | 커밋 | 내용 |
| --- | --- | --- | --- |
| 2-1~2-3 | client-compat 1.4.0 | `f3453c4` | 블록 아틀라스를 이어 붙이기 직전(`SpriteLoader.stitch`)에 스프라이트를 정리한다. 원본 에셋은 복사하지 않는다. 아래 세 규칙을 적용한다. |
| 2-4 | MTR | `8a661ce` | 코드가 직접 그리는 PSD·APG·엘리베이터 문 텍스처 34개를 `textures/door`로 옮긴다. 파티클용으로는 16의 배수 크기로 줄인 복사본 4개를 쓴다. |
| 2-5 | MTR | `d65f228` | 에스컬레이터 애니메이션 프레임을 320×320에서 160×160으로 줄였다(화면 변화). |

2-1~2-3의 세 규칙:
- **정확한 확대본:** 픽셀을 그대로 늘린 이미지는 원래 크기로 되돌린다.
- **크기 상한:** 512 px를 넘는 정적 스프라이트는 절반씩 줄인다. `msd`는 제외한다.
- **밉맵 정렬:** 한 변이 16의 배수가 아닌 스프라이트는 최근접 확대(최대 4배·512 px) 또는 16의 배수로 재샘플링한다.

설정 파일은 `config/minefed-atlas.properties`다.

`verifyAtlasSprites`로 새 MTR·MSD를 포함한 클라이언트 팩의 블록 아틀라스 텍스처 8,928개를 검사했다.
- 173개를 조정했다. 이 중 161개는 텍셀이 원본과 같고, 12개는 재샘플링했다.
- 모든 결과가 16 px로 정렬되고, 애니메이션 프레임 수가 유지되는 것을 확인했다.

| 항목 | 이전 릴리즈 | 적용 후 (계산) |
| --- | --- | --- |
| 블록 아틀라스 스프라이트 | 67.3 Mpx | 27.9 Mpx |
| 아틀라스 크기·밉맵 | 16384×8192, 0단계 | 8192×8192, 4단계 |
| 아틀라스 VRAM | 512 MiB | 약 341 MiB |
| 스프라이트 원본 네이티브 사본 | 약 257 MiB | 약 148 MiB (밉맵 포함) |

아틀라스 크기는 바닐라 `TextureStitcher` 알고리즘을 옮긴 스크립트로 계산했다. 실제 크기는 `latest.log`의 `Created: … minecraft:textures/atlas/blocks.png-atlas` 줄로 확인한다.
밉맵이 0단계에서 4단계로 돌아오므로, 먼 거리의 블록 텍스처가 바닐라 의도대로 필터링된다. 그만큼 화면이 달라진다.

### 3단계 — 동작이 약간 바뀌는 항목

| # | 모드 | 커밋 | 바뀌는 점 |
| --- | --- | --- | --- |
| 3-1 | minefed-display | `9311780` | 시야 절두체 밖의 디스플레이에는 브라우저를 만들지 않는다. 30초 동안 보이지 않은 브라우저는 닫고, 다시 보이면 페이지를 새로 불러온다. |
| 3-2 | client-compat 1.4.0 | `3885168` | MCEF API를 처음 쓸 때(`assertInitialized`) Chromium을 시작한다. 첫 웹 화면이 약 1~2초 늦게 뜬다. |
| 3-3 | minefed-display | `8b4cd45` | `--process-per-site`로 같은 사이트의 화면이 렌더러 프로세스 하나를 공유한다. MCEF의 기본 스위치 3개도 함께 넘긴다. |
| 3-4 | webstreamer | `58fa06b` | 직전 프레임에 그려지지 않은 스트림은 텍스처 업로드를 건너뛴다. 다시 보일 때 최대 한 영상 프레임 동안 이전 이미지가 보일 수 있다. |
| 3-5 | MTR | `0dd6a44` | 5분 동안 그리지 않은 모델 리소스 텍스처를 해제한다. 다시 그릴 때 불러오므로 짧은 끊김이 생길 수 있다. |
| 3-6 | MTR | `02f4f57` | A320 텍스처 2개(4096²)와 S700 텍스처(3024²)를 절반으로 줄였다. |
| 3-7 | MTR | `46be927` | `Use MTR Font`가 꺼져 있으면 `mtr:mtr` 폰트의 TrueType 파일(28 MB CJK)을 불러오지 않는다. 옵션을 바꾸면 설정 화면을 닫을 때 리소스를 다시 불러온다. |
| 3-8 | MTR | `093b569` | 가림 판정 캐시를 16³ 칸 단위 희소 저장으로 바꿨다. 모든 연산·바이트·예외가 라이브러리 캐시와 같다. |
| 3-9 | MTR | `ec806ab` | 새 설정의 `dynamicTextureResolution` 기본값이 1이다. 기존 `mtr.json`에 적힌 값은 유지된다. |
| 3-10 | MSD | `f733735`, `91cdd24` | 참조가 없는 `railing_stair_iron`(1024²)을 제거했다. 대형 텍스처 8개는 모델이 쓰는 텍셀만 원본 그대로 재배치하고 모델의 `"uv"` 값만 고쳤다. [texture-repack 도구](../tools/texture-repack/README.md)가 텍셀 중심 6,660만 개를 비교해 샘플링 결과가 같음을 확인했다. |

MSD 재배치 결과:

| 텍스처 | 이전 | 이후 |
| --- | --- | --- |
| `yuuni_pids` | 1024² | 672×384 |
| `yuuni_2_pids` | 1024² | 864×480 |
| `railing_stair_glass` | 1024² | 336×1168 |
| `book` | 1024² | 592×784 |
| `yuuni_sign` | 900² | 640×864 |
| `yuuni_sign_en` | 900² | 400×752 |
| `board_vertically` | 1024² | 992×928 |
| `board_horizonta` | 1024² | 1024×880 |

`stair_marble_half`와 `yuuni_ticket`은 재배치해도 줄지 않아 그대로 두었다.

## 검증

- **MTR:** `:fabric:test`(71개, 희소 가림 캐시와 라이브러리 캐시의 바이트 단위 비교 포함), `:fabric:verifyRailRendering`, `:fabric:verifyMixinCompatibility`가 통과했다. JDK 21로 빌드했고 출력은 Java 17 바이트코드다. 빌드 JAR SHA-256은 `be9a154a4bdbe60e61dc47d32c5fb0562e15dd5d11f5a8b987b598b434a1d515`다.
- **MSD:** 레시피 작업 `:fabric:setupFiles :fabric:remapJar`가 통과했다(JDK 17). JAR SHA-256은 `4d8f63f8be823b9bfb11cc7df295ff043c99d032ee14fab19fb40eee0762f174`다.
- **client-compat 1.4.0:** `build`, `verifyAtlasSprites`와 기존 `verifyPtsCompatibility`, `verifyPfmCompatibility`, `verifyPfmPerformance`, `verifyTrafficCraftPerformance`가 통과했다. JAR SHA-256은 `8562382947fc0d05d0145f34f1dd8a83d55721693b1b73bab81f990d66e32f0a`다.
- **minefed-display:** `build`가 통과했다. `verifyDisplayOcclusion`은 Xvfb와 Mesa로 통과했다.
- **webstreamer:** 루트 Gradle wrapper로 `remapJar test`가 통과했다.
- **Mixin 적용:** [Mixin audit 도구](../tools/mixin-audit/README.md)를 새로 추가했다.
  - 실제 Fabric Loader 0.18.4 Knot 실행에서 새 JAR 5개를 넣은 클라이언트 모드 72개 전체의 `MixinEnvironment.audit()`가 통과했다. 새 믹스인 11개가 모두 적용된 것을 상세 로그로 확인했다.
  - 서버 쪽 감사도 통과했다.
  - 대조군으로 넣은 고장 난 Mixin은 실패로 검출됐다.
- **루트:** `scripts/build_modpack.py plan`이 통과했다. 단위 테스트 215개 중 `test_build_modpack`의 프로세스 취소 타이밍 테스트 1개만 이 환경에서 간헐적으로 실패했다.
  - 이 테스트는 단독으로 3회 실행해 모두 통과했다.
  - 루트 스크립트는 이번 작업에서 바꾸지 않았다.

## 주의 사항

- **MTR 모델 버퍼 해제는 GC 시점에 일어난다.** 해제 대상은 Java 객체가 수집된 뒤에야 렌더 스레드에서 지워진다. 따라서 해제 시점은 GC 주기를 따른다.
- **아틀라스 크기 상한은 픽셀을 바꾼다.** City Craft 가드레일은 약 50 dB로 사실상 같지만, 쓰레기통은 약 35 dB다. 원하지 않으면 `maxStaticSize=0`으로 끈다.
- **MCEF 지연 시작의 첫 호출 시점이 달라졌다.** 첫 웹 화면을 그리는 프레임에서 Chromium이 시작되므로, 그 프레임이 1~2초 멈출 수 있다.
