# 클라이언트 옵션 및 MCEF 준비 수정

Minecraft 1.20.4 / Fabric Loader 0.18.4 / Java 17을 대상으로 한다.

## 옵션 로딩과 리소스팩 선택

`scripts/release_resources.py`가 새 인스턴스의 `options.txt`에
`version:3700`을 기록하도록 수정했다. 버전 정보가 없으면 Minecraft는 버전 0의
옵션으로 간주하여 이미 현재 형식인 `key.mouse.middle`을 정수로 변환하려 하고,
전체 옵션 로딩이 실패할 수 있다. 키 이름을 숫자로 바꾸는 방식으로 우회하지 않는다.

실제 Minecraft 1.20.4의 `Schemas.getFixer()`와 `DataFixTypes.OPTIONS.update()`로
같은 입력을 검증했다. 0→3700에서는 첨부 로그와 같은 `NumberFormatException`이
발생하고, 3700→3700에서는 키와 리소스팩 목록을 포함한 전체 NBT가 유지된다.
생성된 mrpack의 옵션 데이터 버전을 검사하는 회귀 검증도 기존 패키징 테스트에 추가했다.

새 인스턴스의 기본 리소스팩 순서는 낮은 우선순위부터 다음과 같다.

1. `vanilla`, `fabric`
2. `yuushya:mcpatcher_feature`
3. `file/Yuushya Foliage Addon 1.3.zip`
4. `file/minefed-<version>.zip`

현재 로컬 프로필 `%APPDATA%/ModrinthApp/profiles/client`에는 별도 복구를 적용했다.
게임 종료 상태에서 기존 옵션을
`minefed-backups/client-startup-20260913194655/options.txt`에 보관했다.
이미 다시 선택된 Continuity 및 다른 선택 팩을 보존하면서 위 세 관리 팩의
순서를 복구하고 Minefed를 마지막에 두었다. 현재 프로필이 사용하는
`minefed-20260913144426.zip`과 Foliage ZIP의 원본 바이트를 확인했다.
다른 키·화면·음량 등 개인 옵션 값은 변경하지 않았다.

## MCEF 설치와 배포 구성

[MCEF 구성](MCEF.md)에 기록한 공식 `mcef-fabric-2.1.6-1.20.4.jar`를
클라이언트 전용 의존성으로 추가했다. 소스·바이너리 라이선스, 전체 소스 커밋,
원본 다운로드와 JAR 해시는 해당 문서 및 잠금 파일에 보존한다.

현재 프로필에는 공식 JAR와 Windows amd64 네이티브를 설치했다.
네이티브는 JAR가 지정하는 Java-CEF 커밋
`a78e832f9f13c2c688caea3d04d8b84fcd238d94`에 맞추었다.

- 원본 네이티브 압축 크기: `124309275` bytes.
- 원본 SHA-256: `e98c385542620f31a594d6fc3c38ed6bca8a547e24ced982a1339bb3333668be`.
- 설치 위치: `mods/mcef-libraries/windows_amd64/`.
- 파일 71개 전체를 해시로 대조하고 원본 네이티브 라이선스 파일을 유지했다.
- `windows_amd64.tar.gz.sha256`는 공식 응답 314바이트를 그대로 보존했다.
  MCEF는 이 파일을 원격 응답과 바이트 단위로 비교하므로 내용을 정규화하지 않는다.
- `skip-download`, 다운로드 서버 및 JVM 라이브러리 경로를 덮어쓰지 않았다.
- 기존 모드 JAR 66개는 모두 이전 프로필 manifest의 해시와 일치했다.
  추가 설치 정보와 옵션 백업 위치는 프로필의 `MINEFED-CLIENT-REPAIR.json`에 남겼다.

공식 JAR와 Modrinth의 Java 17로 별도 windowless 브라우저 검증을 수행했다.
Chromium `116.0.5845.190` 초기화, HTML 로딩, JavaScript 실행,
320×180 화면의 실제 paint callback과 지정 색상 픽셀을 확인하고 정상 종료했다.
이는 Minecraft 안의 디스플레이 블록, OpenGL 연동, 월드 입장 전체에 대한 검증은 아니다.

새 mrpack에는 MCEF JAR가 포함되며, 다른 PC의 네이티브 파일은 MCEF가 첫 실행에서
공식 서버로부터 플랫폼에 맞게 준비한다. 현재 PC에 준비한 Windows 네이티브를
다른 플랫폼용 모드팩에 함께 배포하지 않는다.

## 로컬 배포본 검증

버전 `20260913195327`의 산출물은
`build/releases/20260913195327/client.mrpack`,
`server.zip`, `resourcepack.zip`이다. 공개 게시나 운영 서버 변경은 수행하지 않았다.
클라이언트팩 크기는 `256847142` bytes이며 SHA-256은
`1e9b63dadc73118168aff43afd5d5a981093c5252eedafd14950d384c8613268`이다.

소스 변경이 없어 기존 빌드 입력의 모드 68개를 원본 바이트로 재사용하고
공식 MCEF만 추가했다. 소스 46개의 상태, 기존 recipe, JAR와 빌드 이력을 대조했으며
새 소스 컴파일을 수행한 것으로 기록하지 않는다. 입력은 총 69개이고,
완성된 클라이언트팩에는 67개, 서버팩에는 기존과 같은 67개 모드가 포함된다.
서버 플러그인과 Minefed 게임 리소스의 내용도 보존한다.

패키징 테스트 35개, 의존성 조회 테스트 9개, recipe 검사 2개를 통과했다.
실제 의존성 pin 17개와 recipe 69개, 완성된 ZIP의 CRC·해시,
이전 클라이언트 JAR 66개의 보존, MCEF의 클라이언트 전용 포함,
옵션 데이터 버전과 팩 순서, 라이선스 고지 보존을 검사했다.
압축 해제한 새 클라이언트팩의 설치 검증도 통과했다.
이전 고지 본문 130개와 원본 경로→내용 대응 696개가 보존됨을 확인했다.
상속 경로 인덱스는 현재 경로로 다시 생성되므로 각 대상 파일의 해시와 기존 대응 관계를
검사했다. 검증된 입력을 `build/distributions/latest.json`에 반영하고 이전 입력은
새 조립 폴더의 `base-summary.json`과 기존 원본 아카이브에 보존했다.

검증 기록은 `build/client-startup-fix-20260913/release-verification.json`,
`options-recovery.json`, `profile-mcef-installation.json`,
`mcef-native-preparation/native-manifest.json`,
`mcef-native-preparation/smoke/result.json`에 보관한다.
월드 플레이 검증과 구분하기 위해 전체 게임 `runtimeValidated`는 `false`로 유지한다.
