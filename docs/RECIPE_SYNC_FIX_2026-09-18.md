# PTS Deco 레시피 동기화 접속 오류 수정

Minecraft 1.20.4 / Fabric에서 서버 접속 직후 발생한 다음 오류를 조사했다.

```text
DecoderException: InvalidIdentifierException:
Non [a-z0-9/._-] character in path of location:
inecraft:crafting_shaped\u001Dyuushya:wood/raw_cherry_table...
```

## 원인과 수정 범위

문제는 Yuushya의 레시피 이름이 아니라 **PTS Deco 4.0.0의 레시피 읽기 코드**다.
`WorkbenchContructingRecipe$Serializer.fromNetwork()`가 재료와 결과 아이템 뒤에서
사용되지 않는 `readBoolean()`을 한 번 호출한다. 대응 `toNetwork()`는 이 Boolean을
쓰지 않는다. 따라서 바로 다음 레시피 문자열 길이인 `25` (`0x19`)를 소비하고,
첫 문자 `m` (`0x6d`)을 길이 `109`로 잘못 해석한다. 첨부 이미지처럼 문자열이
`inecraft:crafting_shaped`로 시작하면서 다음 레시피 데이터까지 섞이는 이유다.

2026-09-18 FileZilla로 `/home/minefed/fabric/mods`의 67개 파일을 조회했다.
서버에도 `PTS-Deco-4.0.0-Fabric1.20.4.jar`가 있으며, 내려받은 서버 로그의
22:50:59 입장 및 22:51:00 연결 종료가 로컬 클라이언트 오류 시각과 일치한다.
운영 서버 파일 변경·업로드·재시작은 수행하지 않았다.

[Minefed Client Compatibility](https://github.com/minefed/minefed-client-compat)의
클라이언트 전용 Mixin은 **해당 호출 하나만** 버퍼를 읽지 않고 `false`를 반환하도록
바꾼다. 원본 PTS JAR와 서버의 송신 형식은 유지한다. 대상 Minecraft `=1.20.4`,
PTS Deco `=4.0.0`, Java `>=17`, Fabric Loader `>=0.18.0`을 명시하고,
Mixin의 `require/expect/allow = 1`로 대상 호출 수를 제한한다.
PTS 버전을 바꿀 때는 호환 모드도 함께 검토해야 한다.

새 모드는 기존 운영 기준본에서 캡처한 JAR가 아니다. `mods.lock.json`의
`capturedServerBaseline: false`로 구분하며, `minefed-client-compat/` 서브모듈과
`codex/pts-recipe-sync` 추적 브랜치, 전체 커밋, 빌드 JAR 해시·라이선스를 기록한다.
공개팩은 검증한 소스 빌드 결과를 사용하며 서버팩에는 포함하지 않는다.
운영 기준본 CLI의 hydrate/verify/stage/pack은 이 추가 항목을 제외한다.
verify --sources는 새 서브모듈의 pin도 검사하며, 통합 빌드·공개팩에는 검증한 소스 빌드 결과를 포함한다.

## 원본과 라이선스

해당 [공식 PTS Deco 배포본](https://modrinth.com/version/etl5lvBR)의 SHA-256은
`aa75d6e205c34a063fead0dc5cbd564fcbca640172db718e22ac17ebdcc64919`다.
공식 Fabric 1.20.4 후속 수정판은 조사 시점에 없었다.
[원저자의 모드팩 허용 조건](https://www.curseforge.com/minecraft/mc-mods/pts-deco)과
All Rights Reserved 분류를 유지한다. 원본 JAR를 수정하거나 재라이선스하지 않는다.
새 호환 모드는 독립 작성한 MIT 코드이며 PTS 코드·자산을 포함하지 않는다.

## 회귀 검증

원본 JAR의 실제 직렬화 메서드를 사용해 재료 수 0/1/3에 대해 같은 오류를 재현했다.
원본은 세 경우 모두 1바이트를 초과 소비한다. 이어서 **원본 전체 Serializer 클래스에
실제 Sponge Mixin으로 배포할 호환 JAR를 적용**하고, 동일한 세 경우의 다음 레시피
식별자가 보존됨을 확인했다. Minecraft 값·버퍼는 격리된 테스트 대역을 사용한다.
이는 실제 게임의 서버 재접속과 구분하는 검증이다.

빌드 recipe는 `build`와 `verifyPtsCompatibility`를 실행하므로 공식 PTS JAR의
SHA-256 확인 및 실제 Mixin 회귀 검증이 새 소스 빌드에도 적용된다.

```powershell
.\build-modpack.ps1 -Task source_minefed_client_compat
```

검증 Java 소스와 단독 실행법은 호환 모드 저장소에 보존한다.
로컬 조사 자료는 Git에서 제외한 `build/recipe-sync-20260918/`에 둔다.

등록 당시 참고 JAR는 3,174바이트, SHA-256
`5ddcb4933ac9d766fb4a8c311dd7d43a04c55d72802f6e0f9bec0dcb97dc27e9`이며
`mods.lock.json`과 로컬 artifact에 보존한다. 원격 커밋을 clone한 서브모듈에서
빌드한 배포 JAR는 3,185바이트, SHA-256
`beb824078b9d42a350ad0a466d96fe7954ce66e6b428b07c0dd33c5d8ebdb273`이다.
두 파일의 차이는 `LICENSE`의 LF/CRLF 줄바꿈뿐이며 클래스·설정은 바이트 단위로 같다.
배포 manifest와 빌드 receipt는 실제 배포 JAR의 해시를 기록한다.

이번 조립은 기존 소스 배포본의 69개 JAR와 원래 컴파일 기록을 그대로 사용한다.
해시·recipe·소스 상태를 다시 검사하고 Sodium·Indium 공식 JAR 및 새 호환 모드 빌드를
추가한다. 기존 46개 소스를 다시 컴파일한 것으로 기록하지 않는다.

## 클라이언트 구성

이 수정과 함께 [Sodium 구성](SODIUM.md)에 기록한 Sodium `0.5.8+mc1.20.4`,
Continuity 호환용 Indium `1.0.31+mc1.20.4`를 포함한다.
전체 빌드 입력은 72개(소스 47개, 바이너리 25개), 최종 클라이언트는 70개,
서버는 기존 67개 모드와 TCPShield 플러그인 1개다.
