# Texture repack

블록 모델 텍스처에서 모델 면이 실제로 쓰는 텍셀만 남기는 도구다.

```sh
python tools/texture-repack/repack_model_textures.py <assets/<namespace> 디렉터리> <namespace> <texture> [<texture> ...]
```

- 지정한 텍스처를 쓰는 모든 모델 면의 UV 영역(1픽셀 여백 포함)을 원본 텍셀 그대로 새 이미지에 복사한다. 겹치는 영역은 한 번만 복사한다.
- 모델 파일은 `"uv"` 배열 값만 바꾸고 나머지 서식은 그대로 둔다.
- UV 단위와 텍셀의 비율은 바뀌지 않는다. 따라서 모든 면이 이전과 같은 텍셀을 샘플링한다. 도구는 모든 면의 모든 텍셀 중심을 비교해 확인한 뒤에만 파일을 쓴다.
- 결과 크기는 양 변 모두 16의 배수라서 블록 아틀라스 밉맵 단계를 낮추지 않는다. 줄어들지 않는 텍스처는 그대로 둔다.
- Pillow가 필요하다.

2026-09-29 MSD의 대형 텍스처 8개에 적용했다([결과](../../docs/RAM_GPU_OPTIMIZATION_RESULTS_2026-09-29.md)).
