# Mixin audit

테스트 전용 도구다. 서버·클라이언트 팩에는 넣지 않는다.
실제 Fabric Loader 0.18.4 Knot 실행에서 주어진 모드 JAR의 모든 Mixin을 적용해 본 뒤, 게임 창을 열기 전에 종료한다.

```sh
python tools/mixin-audit/run_mixin_audit.py --mods <client.mrpack의 overrides/mods> \
    --replace Minecraft-Transit-Railway/fabric/build/libs/fabric-4.0.5.jar
```

- 처음 실행하면 Minecraft 1.20.4 클라이언트·라이브러리와 Loader 프로필을 `~/.cache/minefed-mixin-audit`에 받는다. Mojang이 게시한 SHA-1로 검사한다.
- `--replace`에 준 JAR는 같은 모드 ID의 기존 JAR를 대신한다.
- 프로브 모드의 `preLaunch` 진입점이 `MixinEnvironment.audit()`를 호출한다. 이 호출은 모든 대상 클래스를 불러와 Mixin을 적용한다. 필수 Mixin이 하나라도 실패하면 종료 코드 1이다.
- 전체 출력은 `tools/mixin-audit/last-audit-<side>.log`에 남는다(Git 제외).
- 게임 시작·월드 생성·렌더링은 하지 않는다. 따라서 Mixin의 적용 여부만 확인하며, 적용된 코드의 실제 동작은 검증하지 않는다.
