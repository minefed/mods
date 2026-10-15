# 예약 배포 에이전트

게임 서버 VPS에서 실행하는 배포 에이전트다. 정해진 시각에 minefed-api에서 배포 계획을 받아
공지, 저장, 백업, 서버팩 교체, 재시작, 상태 확인을 수행하고 결과를 보고한다. 성공을 보고한
뒤에만 API가 운영 런처에 같은 릴리스를 제공한다. 실패하면 이전 릴리스·월드·설정으로 되돌린다.
전체 설계와 결정 사항은 [예약 배포 설계](../../docs/SCHEDULED_DEPLOYMENT.md), API 계약은
minefed-api의 `docs/DEPLOYMENT_API.md`를 따른다.

이 디렉터리의 파일은 설치 재료다. 운영 서버의 파일 변경, 설치, 재시작은 별도 요청이 있을 때만 수행한다.

| 파일 | 용도 |
| --- | --- |
| `minefed_deploy.py` | 에이전트. Python 3.11 이상, 표준 라이브러리만 사용 |
| `test_minefed_deploy.py` | 가짜 API·podman·RCON·백업으로 절차를 검증하는 테스트 (Linux) |
| `prod.toml.example`, `dev.toml.example` | 프로필별 설정 예시 |
| `systemd/` | systemd user 단위: 서비스 1개, 운영·개발 timer |

## 동작

timer가 에이전트를 시작하면 다음 순서로 진행한다.

1. `GET plan`으로 활성·승인 릴리스를 확인한다. 승인 릴리스가 활성과 다르면 `deploy`,
   아니면 `weekly_restart = true`일 때 `restart`, 둘 다 아니면 아무것도 하지 않는다.
2. `deploy`면 `server.zip`과 `resourcepack.zip`을 내려받아 API가 준 크기·SHA-256으로 확인하고,
   `releases/<태그>/`에 풀어 서버팩 안의 manifest와 모든 파일 해시를 검사한다. 실패하면 공지 없이 중단한다.
3. 가장 긴 공지 시간(운영 30분) 뒤를 점검 시각으로 잡고 RCON `say`로 공지한다.
4. 점검 시각에 API 실행을 연다. 그때부터 런처에는 점검 중으로 표시된다.
5. `save-all flush`, `podman compose stop` 후 월드·`server.properties`·`whitelist.json`·관리 파일을
   `tar` + zstd로 백업한다.
6. 빈 화이트리스트와 `white-list`·`enforce-whitelist`로 OP 외 접속을 막는다.
7. `deploy`면 `current` 링크를 새 릴리스로 바꾸고 `config/bluemap/packs/10-minefed.zip`,
   `config/mtr/bluemap-vehicles.json`을 교체한다. `config/mtr/bluemap-public-routes.json`은 없을 때만 만든다.
   `manage_resource_pack = true`면 `resource-pack`, `resource-pack-sha1`, `resource-pack-id`를
   새 릴리스의 GitHub `resourcepack.zip`으로 바꾼다. 그 밖의 설정과 월드는 건드리지 않는다.
8. `podman compose down`·`up -d`로 컨테이너를 다시 만들고, 새 `logs/latest.log`의 `Done (`,
   crash report·Mixin 오류 부재, Server List Ping, RCON `list`를 확인한다.
9. 화이트리스트와 설정을 원래대로 돌리고 `finish succeeded`를 보고한다.

8단계가 실패하면 링크·관리 파일·`server.properties`·월드를 백업 시점으로 되돌리고 다시 시작해
`rolled_back`을 보고한다. 되돌린 서버도 정상이 아니면 `failed`를 보고하며, 점검 표시와 접속
차단을 유지한다. 서버가 정상인데 접속 복구만 실패하면 롤백하지 않고 성공을 보고하되 종료 코드 1로
남긴다. 별도 알림은 없으므로 결과는 journald와 API의 `deployment_runs`로 확인한다.

## 요구 사항

- Python 3.11 이상 (`tomllib`), GNU tar와 zstd (`tar --zstd`)
- rootless podman과 podman compose. 에이전트는 compose를 실행하는 사용자로 실행한다.
- `systemctl --user`와 linger (`loginctl enable-linger <사용자>`)
- RCON 활성화. 포트는 `127.0.0.1`에만 게시한다.
- minefed-api의 배포 리스너와 이 프로필의 토큰(`DEPLOY_PROD_TOKEN` 또는 `DEPLOY_DEV_TOKEN`),
  운영 nginx의 `/v1/deployments/` 전달
- API DB에 현재 실행 중인 릴리스가 `active_release`로 기록되어 있어야 한다.

## 최초 설치

아래 `<...>`는 실제 경로로 바꾼다.

1. 에이전트와 단위를 설치한다. 검토한 `minefed/mods` 커밋에서 복사한다.

   ```sh
   install -Dm644 deploy/server-agent/minefed_deploy.py ~/minefed-deploy/agent/minefed_deploy.py
   install -Dm644 -t ~/.config/systemd/user deploy/server-agent/systemd/*
   install -Dm600 deploy/server-agent/prod.toml.example ~/.config/minefed-deploy/prod.toml
   ```

2. `prod.toml`의 경로를 채운다. 토큰과 RCON 비밀번호는 한 줄 파일로 두고 `chmod 600`을 적용한다.
   에이전트는 다른 사용자가 읽을 수 있는 비밀 파일을 거부한다.
3. 현재 서버가 실행 중인 릴리스의 `server.zip`을 GitHub Releases에서 내려받고, 릴리스 페이지의
   SHA-256과 비교한 뒤 등록한다. 서버팩 안의 manifest와 파일 해시도 함께 검사한다.

   ```sh
   python3 -I ~/minefed-deploy/agent/minefed_deploy.py --config ~/.config/minefed-deploy/prod.toml --adopt <다운로드한 server.zip>
   ```

4. 등록한 `~/minefed-deploy/releases/<태그>/mods`와 서버의 현재 `mods/`가 같은지 확인한다.
5. compose의 Minecraft 서비스에 `mods/`만 덮는 bind mount를 추가하고 컨테이너를 다시 만든다.
   기존 데이터 마운트 구조와 관계없이 동작한다. SELinux가 켜진 호스트면 레이블 옵션(`z`)을 더한다.

   ```yaml
   volumes:
     - <HOME>/minefed-deploy/current/mods:<컨테이너 안 서버 루트>/mods:ro
   ```

6. `server.properties`, `whitelist.json`, 월드 파일이 컨테이너 사용자에 대응하는 subuid 소유라면
   서비스의 `ExecStart` 앞에 `podman unshare`를 붙이는 drop-in을 둔다
   (`systemctl --user edit minefed-deploy@prod.service`).
7. 먼저 수동으로 dry run을 실행해 계획 조회·다운로드·검증을 확인한다.

   ```sh
   python3 -I ~/minefed-deploy/agent/minefed_deploy.py --config ~/.config/minefed-deploy/prod.toml --dry-run
   ```

8. timer를 켠다. 예시 설정은 `dry_run = true`라서 첫 정기 점검은 공지·중지 없이 준비만 한다.
   결과를 확인한 뒤 `dry_run = false`로 바꾼다.

   ```sh
   systemctl --user daemon-reload
   systemctl --user enable --now minefed-deploy-prod.timer
   systemctl --user list-timers minefed-deploy-prod.timer
   ```

개발 서버는 `dev.toml.example`과 `minefed-deploy-dev.timer`를 같은 방식으로 사용한다.
개발 프로필은 최신 prerelease를 자동 승인하고, 1분 공지 후 반영하며, 정기 재시작은 하지 않는다.

`manage_resource_pack = true`인 첫 배포에서 `resource-pack`이 자체 호스팅 URL에서 GitHub Release URL로
바뀐다. 이 경로는 개발 서버에서 1.20.4 클라이언트가 실제로 받는지 먼저 확인한다.

## 운영

- 승인: 운영자가 API DB에 `approved_release`를 기록한다(minefed-api `docs/LAUNCHER_DATABASE.md`).
  에이전트 자격으로는 승인할 수 없다.
- 기록: `journalctl --user -u minefed-deploy@prod`, API의 `deployment_runs`
- 파일: `~/minefed-deploy/releases/<태그>/`(최근 4개), `backups/*.tar.zst`(최근 4개),
  `runs/<실행 ID>/`(변경 전 `server.properties`·관리 파일), `current` 링크
- 수동 복구: 서버를 멈추고 `current`를 이전 `releases/<태그>`로 바꾼 뒤 `runs/<실행 ID>/`의 파일과
  필요하면 `backups/`의 월드를 되돌리고 `podman compose down`·`up -d`를 실행한다.
  복구 후 API의 `active_release`가 실제 실행 중인 릴리스와 같은지 확인한다.
- 한 프로필에 에이전트는 하나만 실행된다(로컬 잠금과 API 실행 임대).

## 검증

Linux에서 이 디렉터리를 작업 디렉터리로 두고 실행한다.

```sh
python3 -m unittest test_minefed_deploy
```

가짜 API·podman·RCON·백업으로 배포 성공, 정기 재시작, 롤백, 롤백 실패, 접속 복구 실패,
시작 거부, 서버팩 변조·경로 탈출, 공개되지 않은 URL, 미등록 활성 릴리스, dry run, 오래된 릴리스 정리와
다운로드 검증·설정 파일·RCON·Server List Ping을 확인한다. 이 테스트는 실제 Minecraft 서버나
운영 VPS에서의 동작을 보장하지 않는다.
