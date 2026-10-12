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
  색상 처리기가 없는 TrafficCraft 가로등 등은 흰색 배율을 사용한다.
  명시적인 `blockColors.json` 블록별 재정의는 계속 우선한다.
- Minecraft `assets/minecraft/atlases/blocks.json`의 `single` sprite 별칭을
  해석한다. Minefed 팩의 Exline Furniture / CityCraft 텍스처 별칭이
  BlueMap에서도 실제 PNG에 연결된다.
- 클라이언트에서만 생성되는 모델을 읽기 위한 `bluemap_quads` 모델 확장을
  추가한다. 일반 JSON `elements`로 표현하기 어려운 사각형의 네 꼭짓점,
  UV, 텍스처, tint와 cull 방향을 유지한다.
- `server.zip`에도 클라이언트와 동일한 Minefed 리소스팩을
  `config/bluemap/packs/10-minefed.zip`으로 포함하고 해시를 검사한다.
  이 팩에는 기존 Jonn's Palette / Dusty Decorations 모델 보정도 들어 있다.

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
의미는 아니다. 일반 블록 모델 외의 BlockEntity 전용 렌더러는 별도 지원이 필요하다.

생성 모델은 원작 모드의 자산 라이선스를 따른다. PFM 자산의 PolyForm Shield,
다른 모드와 Minecraft 자산의 조건을 보존하고, 생성 팩은 무시되는 `build/`
아래에서 로컬로 관리한다. 추출 도구의 MIT 라이선스가 생성 자산의 재배포
권한을 부여하지 않는다. 생성 JSON·PNG를 Git이나 공개 릴리즈에 추가하지 않는다.

## 운영 반영

이 저장소의 빌드·테스트는 운영 서버를 변경하거나 지도를 재생성하지 않는다.
별도 운영 반영 작업에서 다음을 함께 적용한다.

1. 기존 BlueMap JAR를 호환 빌드로 교체한다. 같은 모드 ID의 JAR 두 개를 두지 않는다.
2. `config/bluemap/packs/10-minefed.zip`과 검증한 생성 모델 팩을 배치한다.
   생성 팩은 `90-minefed-models.zip`처럼 후순위 이름으로 배치하여 모델 재정의를 우선한다.
   ZIP 루트에 `pack.mcmeta`와 `assets/`가 있어야 한다.
3. BlueMap을 다시 로드하고 해당 지도를 재생성한다. 기존 렌더 타일은
   리소스팩이나 JAR만 교체해도 자동으로 새 모습으로 바뀌지 않는다.
4. 기존 보라색 위치와 서로 다른 색으로 칠한 Asphalt 위치를 근거리·원거리에서 확인한다.

배치 전 운영 설정의 resource-pack 적용 순서와 모드 리소스 검색 설정도 확인한다.
모드·리소스팩 버전을 바꾸면 생성 모델 팩도 다시 만들고 검증한다.

## 검증

BlueMap Core 테스트는 저장 NBT를 실제 청크 파서로 읽은 뒤 모델 색상과
직렬화한 타일을 검사한다. 16색, 미도색, 색상 없음, 개별 블록 위치,
기본 Asphalt 바탕, 가로등, 명시 재정의와 바닐라 색상 경로를 포함한다.
모델 확장 테스트는 텍스처 우선순위·sprite 별칭·부모 모델·UV·tint·culling을 검사한다.

실제 생성 팩도 같은 렌더 경로로 검사할 수 있다. 환경 변수
`BLUEMAP_TEST_PACK`에 생성 디렉터리의 절대 경로를 설정하고 BlueMap Core의
`test`를 실행한다. 참조 모델을 모두 로드하여 누락 텍스처가 없는지,
삼각형 수·꼭짓점·UV가 추출 결과와 같은지 확인한다.
