# BlueMap 모드 렌더링

Minefed는 Minecraft 1.20.4 / Fabric용 BlueMap 5.3을 기반으로
`5.3-minefed.1` 호환 빌드를 사용한다. 소스는 `BlueMap` 서브모듈의
`minefed-1.20.4` 브랜치이며, 정확한 커밋은 `inventory/mods.lock.json`에 고정한다.
운영 기준본 5.3의 파일명·해시는 과거 입력 기록으로 보존한다.

## 수정 범위

- TrafficCraft 1.1.3의 색상 BlockEntity NBT `color`를 읽고, 게임과 같은
  16색 팔레트 및 미도색 기본색을 모델의 `tintindex` 면에 적용한다.
  같은 블록 ID라도 각 좌표의 저장 색상을 독립적으로 사용한다.
  기본 Asphalt 바탕처럼 tint가 없는 면은 원래 텍스처를 유지한다.
  이후 다시 칠한 색상은 월드 저장과 BlueMap의 지도 갱신 주기에 맞춰 반영된다.
  색상 처리기가 없는 TrafficCraft 가로등 등은 흰색 배율을 사용한다.
  명시적인 `blockColors.json` 블록별 재정의는 계속 우선한다.
- Minecraft `assets/minecraft/atlases/blocks.json`의 `single` sprite 별칭을
  해석한다. Minefed 팩의 Exline Furniture / CityCraft 텍스처 별칭이
  BlueMap에서도 실제 PNG에 연결된다. 같은 sprite 이름의 PNG가 이미 있는
  경우에도 별칭을 적용하고, 기존 텍스처 캐시를 함께 교체한다.
- 클라이언트에서만 생성되는 모델을 읽기 위한 `bluemap_quads` 모델 확장을
  추가한다. 일반 JSON `elements`로 표현하기 어려운 사각형의 네 꼭짓점,
  UV, 텍스처, tint와 cull 방향을 유지한다.
- `server.zip`에도 클라이언트와 동일한 Minefed 리소스팩을
  `config/bluemap/packs/10-minefed.zip`으로 포함하고 해시를 검사한다.
  이 팩에는 기존 Jonn's Palette / Dusty Decorations 모델 보정도 들어 있다.
- PFM 가구의 tint index를 구분해 일반 면에는 흰색 배율, 싱크·욕조의
  물 면에는 바이옴 물 색을 사용한다. 변기는 `toilet=dirty`일 때 원래의
  갈색을 사용한다. 같은 모델의 면마다 tint index가 달라도 이전 면의
  색상 캐시를 재사용하지 않는다. 현재 모드팩의 가구 소재를 기준으로 하며,
  별도 모드가 색상 처리기를 추가하는 소재는 추가 지원이 필요하다.

## PFM·Diagonal 모델 준비

PFM과 Diagonal 계열은 게임 시작 시 모델을 만든다. 모드 JAR의 정적
JSON만 읽는 BlueMap에는 이 결과가 없으므로, 클라이언트에서 생성한
모델과 이미지를 별도 팩으로 전달해야 한다.

[모델 추출 도구](../tools/bluemap-model-exporter/README.md)를 사용한다.
운영 서버에 접속하지 않는 일회용 클라이언트에서 실제 모드·설정·활성
리소스팩을 로드한 뒤 생성한다. 도구 JAR는 운영 모드팩에 넣지 않는다.
생성 결과의 `export-report.json`과 다음 검사를 모두 확인한다.

```text
python tools/bluemap-model-exporter/verify.py <생성_디렉터리>
python tools/bluemap-model-exporter/verify.py <생성_디렉터리> --require-all
```

두 번째 검사는 선택한 블록 중 미지원 블록이 하나라도 있으면 실패한다.
`complete: true`는 추출 순회를 마쳤다는 뜻이며 모든 블록의 성공을 뜻하지 않는다.
하나의 블록에 속한 모든 상태를 추출했을 때만 해당 blockstate를 대체한다.

PFM 연결 가구는 저장된 blockstate가 같아도 주변 가구 배치에 따라 모양이
달라질 수 있다. `-Dminefed.bluemap.contextual=isolated`는 이 경우 독립 배치
모델을 생성한다. 보고서의 `isolatedContextStates`와 모델의
`minefed_export_context`로 구분하며, 연결된 가구의 모양까지 일치한다는
의미는 아니다. 일부 대각선 블록의 Continuity CTM 효과도 주변이 비어 있는
조건을 기준으로 한다. 일반 블록 모델 외의 BlockEntity 전용 렌더러는 별도 지원이 필요하다.
PFM 기본 램프의 BlockEntity에 저장된 염색·소재 변경도 이번 지원 범위에
포함되지 않는다. TrafficCraft의 저장된 도색은 위에서 설명한 전용 경로로 처리한다.

생성 모델은 원작 모드의 자산 라이선스를 따른다. PFM 자산의 PolyForm Shield,
다른 모드와 Minecraft 자산의 조건을 보존하고, 생성 팩은 무시되는 `build/`
아래에서 로컬로 관리한다. 추출 도구의 MIT 라이선스가 생성 자산의 재배포
권한을 부여하지 않는다. 생성 JSON·PNG를 Git이나 공개 릴리즈에 추가하지 않는다.

## 운영 반영

이 저장소의 빌드·테스트는 운영 서버를 변경하거나 지도를 재생성하지 않는다.
별도 운영 반영 작업에서 다음을 함께 적용한다.

1. 서버를 정지한 상태에서 기존 BlueMap JAR를 호환 빌드로 교체한다.
   같은 모드 ID의 JAR 두 개를 두지 않는다.
2. `config/bluemap/packs/10-minefed.zip`과 검증한 생성 모델 팩을 배치한다.
   생성 팩은 `90-minefed-models.zip`처럼 후순위 이름으로 배치하여 모델 재정의를 우선한다.
   ZIP 루트에 `pack.mcmeta`와 `assets/`가 있어야 한다.
3. 서버를 시작하여 새 호환 빌드가 로드되었는지 확인한 뒤
   `/bluemap force-update <map-id>`로 해당 지도를 다시 렌더링한다.
   JAR 교체에는 서버 재시작이 필요하며 `/bluemap reload`만으로는 적용되지 않는다.
   리소스팩만 바꾼 경우에는 `/bluemap reload` 후 강제 갱신할 수 있다.
   기존 렌더 타일은 리소스팩이나 JAR만 교체해도 자동으로 새 모습으로 바뀌지 않는다.
4. 기존 보라색 위치와 서로 다른 색으로 칠한 Asphalt 위치를 근거리·원거리에서 확인한다.

배치 전 운영 설정의 resource-pack 적용 순서와 모드 리소스 검색 설정도 확인한다.
모드·리소스팩 버전을 바꾸면 생성 모델 팩도 다시 만들고 검증한다.

## 검증

BlueMap Core 테스트는 저장 NBT를 실제 청크 파서로 읽은 뒤 모델 색상과
직렬화한 타일을 검사한다. 16색, 미도색, 색상 없음, 개별 블록 위치,
기본 Asphalt 바탕, 가로등, 명시 재정의와 바닐라 색상 경로를 포함한다.
모델 확장 테스트는 텍스처 우선순위·sprite 별칭·부모 모델·UV·tint·culling을 검사한다.
투명 텍스처에 색상을 곱한 뒤에도 저해상도 지도 색상이 올바른 premultiplied
alpha 형식을 유지하는지 검사한다. 이 변환이 없으면 일부 가구 렌더가 예외로 중단된다.

실제 생성 팩도 같은 렌더 경로로 검사할 수 있다. 환경 변수
`BLUEMAP_TEST_PACK`에 생성 디렉터리의 절대 경로를 설정하고 BlueMap Core의
`test`를 `--rerun`으로 실행한다([명령](../tools/bluemap-model-exporter/README.md)).
참조 모델을 모두 로드하여 누락 텍스처가 없는지,
삼각형 수·꼭짓점·UV가 추출 결과와 같은지 확인한다.

2026-10-12의 로컬 검증 결과는 다음과 같다.

| 항목 | 결과 |
| --- | --- |
| BlueMap Core | 일반 34개와 실제 모델 팩 통합시험 1개, 모두 통과 |
| PFM | 2,005종, 저장 blockstate 17,258개 |
| Diagonal Fences / Walls / Windows | 127 / 159 / 35종, blockstate 245,760개 |
| 합계 | 2,326종, blockstate 263,018개, 미지원 블록 0개 |
| 생성 자산 | 모델 16,031개, 텍스처 436개, 애니메이션 텍스처 5개 |
| 실제 BlueMap 렌더 검사 | 삼각형 1,389,352개, 누락 텍스처 0개, 꼭짓점·UV 일치 |

위의 모델 수는 이번 추출 대상의 범위이며 모든 설치 모드의 모든 렌더러를
지원한다는 의미는 아니다. 주변 블록의 영향을 받는 상태 16,225개는 앞서
설명한 독립 배치 조건으로 추출했다. PFM 전체 추출, Diagonal 전체 추출,
정상 빈 상태를 가진 사암 벽 2종 재추출의 원본 보고서와 사용한 도구 JAR 해시를
생성 팩의 `capture-evidence/` 및 `export-report.json`에 보존한다.

검증된 로컬 배포 묶음은 `build/bluemap-compat/deliverable/`에 보관한다.
`MANIFEST.json`의 JAR·팩 SHA-256과
`inventory/bluemap-rendering-2026-10-12.json`의 소스·검증 기록을 함께 확인한다.
운영 서버 적용 및 실제 지도 화면의 변경은 이 로컬 검증에 포함되지 않는다.
