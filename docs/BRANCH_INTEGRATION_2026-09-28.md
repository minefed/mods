# Minefed 브랜치 통합 기록 — 2026-09-28

상위 `minefed/mods`와 활성 하위 저장소 52개의 로컬·origin 브랜치를 조사했다. Minefed 기능 브랜치의 커밋 포함 관계를 기준으로 대상 브랜치를 통합했다. 다른 Minecraft 버전용 브랜치와 Minefed 변경을 포함하지 않는 upstream 개발 브랜치는 대상에서 제외했다.

대상 호환성은 Minecraft 1.20.4 / Fabric이며, 리소스팩은 기존 pack format 22 / MTR 4.0.5 입력을 유지한다. 하위 소스 커밋은 모두 통합 전 gitlink와 동일하다. 이번 작업은 브랜치와 추적 설정을 정리하며 소스, JAR 목록·해시·출처, 라이선스, 운영 서버 파일을 변경하지 않는다.

상위 `main`에는 `codex/add-minecraft-mcp-client`의 6개 커밋이 이미 fast-forward되어 있었다. 해당 기능 tip은 `44484a1da6a31b22555613fc1a4af612185a339d`이며, 상위의 다른 기능 브랜치는 모두 여기에 포함된다. 하위 추적 설정은 저장소별 Conventional Commit으로 기록한다.

## 통합 및 push한 하위 저장소

기존 대상 브랜치 14개를 fast-forward했다. `minefed-client-compat`에는 기존 대상 브랜치가 없어 현재 기능 tip으로 `main`을 생성했다. 아래 각 원격 대상 tip은 push 후 `git ls-remote`로 검증했다.

| 저장소 | 기능 브랜치 | 대상 브랜치 | 검증한 전체 커밋 |
| --- | --- | --- | --- |
| Decorative-Blocks | `codex/fix-copy-tool-model` | `minefed-1.20.4` | `8550e3b988d1d7f1c27c1c15732070569ded051e` |
| diagonal-fences | `codex/fix-macaw-compatibility` | `minefed-1.20.4` | `aa41b9f39f744455258c27d3728a1ff77908731f` |
| MemoryLeakFix | `codex/fix-common-mixin-refmap` | `minefed-1.20.4` | `f01909746ee3ad595a3ed91e4abb4779a06a47c2` |
| Minecraft-Transit-Railway | `codex/fix-minecart-sounds` | `minefed-1.20.4` | `e1b99f86794eae70bdd00e2c604ad9a61236af1f` |
| minefed-client-compat | `codex/pts-recipe-sync` | `main` | `e27ee63ddc883343e554d32f511fe3bebcc565dd` |
| minefed-display | `codex/fix-display-depth` | `minefed-1.20.4` | `a1e8f94df20c22c1ccfc4083b1dc01dc7f757e45` |
| mishanguc | `codex/fix-gradle-download` | `minefed-1.20.4` | `07028d29c741f688fafd271e5fb0f51937042184` |
| modern-glass-doors | `codex/fix-glass-door-generated-resources` | `minefed-1.20.4` | `3c65e91eee397e91496f78345165451d86b28932` |
| MTR-Station-Decoration-Addon | `codex/update-msd-1.4.5` | `minefed-1.20.4` | `b06fc0725b20a5b7a6c72bdacd20814dd8d8aabf` |
| MythicMetalsDecorations | `codex/fix-chest-particle` | `minefed-1.20.4` | `f5af39239697e9ed89a108da59c2f8eac695d3df` |
| Oritech | `codex/fix-capacitor-model` | `minefed-1.20.4` | `0ace08abb384f0e38288f4bc82b6c58606509f86` |
| resourcepack | `codex/fix-mod-assets` | `main` | `cbcc8cc1f0f0dbf490a485423b3cbd3959726d21` |
| worldedit-hang-fix | `codex/update-worldedit-hang-fix-1.0.5` | `minefed-1.20.4` | `45c744113850a55f844c7195d5e074b6845d28eb` |
| Yuushya-Modelling | `codex/optimize-model-loading` | `minefed-1.20.4` | `6256abeee58ca8952ada2ac617aa15ef16ec23dd` |
| Yuushya-Townscape | `codex/fix-runtime-resources` | `minefed-1.20.4` | `dda6be38dc069885cd21bb952f3587db209d05b1` |

MTR의 `codex/fix-mixin-loader-compatibility`와 `codex/optimize-3d-rails`도 `codex/fix-minecart-sounds`의 조상이므로 함께 반영되었다. 기능 브랜치 삭제나 이력 재작성은 수행하지 않았다.

`.gitmodules`와 `inventory/mods.lock.json`의 현재 `ref`/`trackingBranch`를 대상 브랜치로 바꿨다. 리소스팩은 `inventory/resourcepacks.lock.json`의 `ref`도 일치시켰다. 기존 `baselineRef`와 과거 검증 기록은 보존했다.

## 이미 반영된 하위 저장소

아래 37개는 추가 병합 없이 로컬 대상 브랜치, 현재 HEAD, 원격 대상 tip이 같은 것을 확인했다.

| 저장소 | 대상 브랜치 | 검증한 전체 커밋 |
| --- | --- | --- |
| alloy-forgery | `minefed-1.20.4` | `badd26ba735ffe18723f97db49c5f6c1d0c50ee9` |
| Automobility-Refueled | `minefed-1.20.4` | `13160075fb4be333fe2b425183c02f9dc2348184` |
| BlueMap | `minefed-1.20.4` | `dd63c74e1b8251cde574e1beca1025a840e6761c` |
| CC-Tweaked | `minefed-1.20.4` | `c3264ade27b032f4b4b480169e67bcb08a01bc0a` |
| Chisels-and-Bits | `minefed-1.20.4` | `12fd1d23b3e6fb929ccba01e034c46ae632acbe0` |
| Chunky | `minefed-1.20.4` | `1fe63d9331b5cbad47dac40b48aabd1b0085c000` |
| CityCraft | `minefed-1.20.4` | `32f4d36ff7865630f102e8f71302f483311aed39` |
| CrossStitch | `minefed-1.20.4` | `aa5545ce774566f3c09f2b34ac4ec0412274dec8` |
| diagonal-walls | `minefed-1.20.4` | `452eb0a4a633ee2d0908f166b0e17315ee99d197` |
| diagonal-windows | `minefed-1.20.4` | `7209c6ea3cb2b05157eeae3ddced087556889bb9` |
| fabric-carpet | `minefed-1.20.4` | `72248bbebe61dc0b2b7316378aa7629955d0f91a` |
| fabric-seasons | `minefed-1.20.4` | `8e7833a58f54180c6fc6a96a2fb08c63ace5a726` |
| fabric-webstreamer | `minefed-1.20.4` | `f9c03980c9cb31ca891e4429bc2529c6c0cce033` |
| FabricProxy-Lite | `minefed-1.20.4` | `7391c12684820b14039a42c0e5ae2e9178bf4290` |
| FallingTree | `minefed-1.20.4` | `0a70a01d3d682a9069f12a00a5c9dbd96d53f2cb` |
| Fences | `minefed-1.20.4` | `c9821fbd10fe55cdb0cc9e91fefb19a5d6d6aa4b` |
| FerriteCore | `minefed-1.20.4` | `1df30b595e231bc0dc9a8eabe65d34cce542d3f9` |
| forge-config-api-port | `minefed-1.20.4` | `b102873873cd9d0bd70685cd7bec524666e2d190` |
| geckolib | `minefed-1.20.4` | `fb968c0379ef0f6ef5c0d6672a464b2f2712553f` |
| Handcrafted | `minefed-1.20.4` | `7b5501555b4683757800e9ca7df264d0850caad3` |
| lithium | `minefed-1.20.4` | `c40b7585606e8434b7a8f1e7ef15c20d99685f19` |
| MacawsDoors | `minefed-1.20.4` | `b07c8caa4a45f0f9aac98d04a972fd359d7a84ca` |
| mc-realtime | `minefed-1.20.4` | `bd05e0fe8ad18184354dff9453da4b0d8b4703b5` |
| Modern-Lights | `minefed-1.20.4` | `6b04f156a3e24a778fa2e0697d98bfd3aeca0256` |
| ModernFix | `minefed-1.20.4` | `479096893321f5dc3e97791e5fa7dcf3ed58e15b` |
| MythicMetals | `minefed-1.20.4` | `cfa897b7e6b2ab856f08582c5e525e675633b33c` |
| NiceMod | `minefed-1.20.4` | `c344763657eaa90d878d858a74c1cdb93cf9d66f` |
| paladins-furniture | `minefed-1.20.4` | `131ac50fa74b0896f0a6d4b56c003076e036b318` |
| Patchouli | `minefed-1.20.4` | `5bb9e96cd8256c0bcd2fa87eff2d65be0a7290d5` |
| puzzles-lib | `minefed-1.20.4` | `1dc5d1305d9d93527d09b84c826d30216bb5d468` |
| RealIP | `minefed-1.20.4` | `b0a1956154fee51616ce396bf355a466001c6467` |
| Starlight | `minefed-1.20.4` | `c2b8391d83ddadbd8136d2abead7e1014da19a6d` |
| stoneworks | `minefed-1.20.4` | `6f492401ca95bec909e0f0f634c58780fa67793a` |
| TimeOutOut | `minefed-1.20.4` | `0d27ca115902c93d132a2d062b166c5a544da0c7` |
| TrafficCraft | `minefed-1.20.4` | `40b9405380f3baae0aa45e9e744e14efd9eecf6c` |
| wireless-redstone | `minefed-1.20.4` | `85cd6b45cd660deeba6ac5cb58b8d5f82795dae0` |
| WorldEdit | `minefed-1.20.4` | `f2cdc4aa7816a0184adf3fcfaf3ff5712d8dfd68` |

## 검증 및 제외 범위

- 활성 하위 저장소 52개 모두 원격 대상 tip = 로컬 대상 브랜치 = 현재 고정 소스 HEAD. 각 Minefed `codex/*` 기능 브랜치 tip이 대상 브랜치에 포함되는지 확인했다.
- 각 하위 저장소의 기본 checkout은 깨끗하며, 상위 gitlink와 소스 잠금 커밋은 통합 전후 동일하다.
- 소스 목록 검증(`mods.check_sources`)과 릴리스 추적 설정(`release_inputs.configured_sources`)을 확인했다.
- `python -m unittest test_mods test_release_inputs`: 38개 중 37개 통과, 1개 건너뜀. 이 Windows 환경에서 심볼릭 링크 생성이 지원되지 않아 해당 검사만 건너뛰었다.
- 이번 작업에서는 소스 코드가 바뀌지 않아 모드 전체 재빌드와 Minecraft 실행 검증을 반복하지 않았다.
- 과거 삭제된 기반 라이브러리 7개의 로컬 보관본은 통합·push 대상에서 제외했다: `architectury-api`, `Common-Storage-Lib`, `fabric-api`, `lavender`, `owo-lib`, `Resourceful-Config`, `ResourcefulLib`.
- BlueMap의 중첩 `BlueMapAPI`는 Minefed 소유 모드 저장소가 아닌 upstream 의존성이므로 기존 pin을 유지했다.
