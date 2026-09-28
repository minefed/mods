# 2026-09-28 성능 최적화 서브모듈 패치

[최적화 계획](../../docs/OPTIMIZATION_PLAN_2026-09-28.md)을 구현한 서브모듈 커밋을 `git format-patch` 형식으로 보존한다.
이 작업 세션에는 서브모듈 저장소(`minefed/<mod>`)에 push할 권한이 없었다. 따라서 각 서브모듈의 로컬 `perf/2026-09-28` 브랜치 커밋을 이 폴더에 내보냈다.

적용 방법은 다음과 같다. 서브모듈을 현재 gitlink 커밋으로 둔 상태에서 실행한다.

```sh
git -C <submodule> switch -c perf/2026-09-28
git -C <submodule> am ../patches/perf-2026-09-28/<submodule>/*.patch
```

적용한 뒤에는 [AGENTS.md](../../AGENTS.md)의 절차를 따른다. 각 서브모듈의 `minefed-1.20.4`(client-compat은 `main`)에 병합해 push하고, 원격 커밋으로 상위 gitlink와 `inventory/mods.lock.json`을 갱신한다.
gitlink는 원격에 없는 커밋을 가리키면 안 되므로, 이 브랜치의 gitlink는 아직 기존 커밋을 유지한다.
