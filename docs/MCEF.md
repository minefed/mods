# MCEF 클라이언트 브라우저 구성

Minefed Display의 웹 화면을 표시하기 위해 공식 MCEF `2.1.6-1.20.4` Fabric
JAR를 클라이언트 모드팩에 포함한다. 기존 `MCEF is not installed` 경고는 이
실행 라이브러리가 없어 브라우저 렌더링이 비활성화되었다는 뜻이다.

2026-09-13 [공식 Modrinth 릴리즈](https://modrinth.com/version/3koDiBl0)의 원본
바이너리를 내려받아 게시된 SHA-512·크기와 대조하고 실제 Fabric 메타데이터를 확인했다.
Minecraft `1.20.4`, Java `>=17`, Fabric Loader `>=0.14.25`가 필요하다.
Fabric API가 `0.91.1+1.20.4`보다 오래되면 충돌 대상으로 선언되어 있으며,
현재 팩의 `0.97.3+1.20.4`는 이 조건을 충족한다.

| 항목 | 고정값 |
| --- | --- |
| 파일 | `mcef-fabric-2.1.6-1.20.4.jar` |
| 크기 | `221800` bytes |
| SHA-256 | `98f0dd8821dee74d7430ac82089ed7abbaf77d578c99e624940792d0f729c5f1` |
| Modrinth 프로젝트 / 릴리즈 | `TObQ0HxZ` / `3koDiBl0` |
| 원본 소스 | [CinemaMod/mcef](https://github.com/CinemaMod/mcef) |
| 추적 브랜치 / 릴리즈 ref | `1.20.4` / `2.1.6-1.20.4` |
| 전체 소스 커밋 | `bb85d521e79662592fa72a67fadcbd622c664ce8` |
| 내장 Java-CEF 커밋 | `a78e832f9f13c2c688caea3d04d8b84fcd238d94` |

정확한 URL·SHA-512·호환성은 [dependencies.lock.json](../inventory/dependencies.lock.json)에
기록한다. [build-recipes.json](../inventory/build-recipes.json)의 `dependency: true`
바이너리 recipe로 선택하고, [release-policy.json](../inventory/release-policy.json)은
`client: true`, `server: false`로 제한한다. JAR 자체의 `environment`는 `*`지만
공식 프로젝트가 서버를 지원하지 않는다고 명시하므로 서버 팩에는 넣지 않는다.
현재 `archiveMode: bundled`에서는 검증한 공식 JAR를 클라이언트 mrpack에 포함한다.
캡처한 운영 기준본 `mods.lock.json`과 Minefed Display 소스는 변경하지 않는다.

## 네이티브 브라우저 준비

MCEF JAR는 Chromium 실행 파일 전체를 포함하지 않는다. 첫 클라이언트 실행에서
MCEF가 [공식 다운로드 서버](https://mcef-download.cinemamod.com)에 연결하여
운영체제·CPU 아키텍처별 Java-CEF/CEF 네이티브 파일을 준비한다.
이 JAR의 `META-INF/MANIFEST.MF`가 요구하는 Java-CEF 버전은 위의 `a78e832…` 커밋이다.
따라서 JAR 설치와 네이티브 다운로드·초기화 완료를 각각 확인해야 한다.

이번 의존성 pin은 네이티브 런타임을 Git이나 모드팩에 함께 배포하지 않는다.
별도로 준비한 네이티브 캐시를 사용할 때에는 같은 커밋·플랫폼의 원본 파일을
사용하고 함께 제공되는 Chromium/CEF 및 제3자 라이선스 고지를 보존한다.
다른 플랫폼의 네이티브 캐시를 공유하면 브라우저가 초기화되지 않는다.
JAR 해시 검증만으로 Minecraft 안의 웹 화면 표시까지 검증한 것으로 간주하지 않는다.

Windows x64에서는 위 공식 JAR와 동일한 Java-CEF 커밋의 네이티브를 사용하여,
Modrinth의 Java 17에서 별도 비표시 테스트를 수행했다. Chromium `116.0.5845.190`
초기화, 로컬 HTML 응답 200, JavaScript 실행과 320×180 화면 픽셀 생성이 성공했다.
이 테스트는 Minecraft 내부 블록 렌더링·입력과 실제 접속할 웹사이트의 호환성을
대신하지 않는다. 이미 네이티브가 준비된 경우에도 MCEF는 시작 시 공식 체크섬을
조회하므로 최초 다운로드 완료를 영구적인 오프라인 지원으로 해석하지 않는다.

## 라이선스와 대응 소스

MCEF 프로젝트 메타데이터는 `LGPL-2.1-only`, 해당 소스 파일의 저작권 머리말은
`LGPL-2.1-or-later`를 명시한다. 두 표기를 그대로 기록하고 이번 원본 바이너리
배포에는 공통으로 허용되는 LGPL 2.1 조건을 적용한다. 내장 Java-CEF는
별도의 BSD 3-Clause 조건을 따른다. 원본 JAR에 독립적인 라이선스 파일이 없어
정확한 소스 커밋의 [MCEF 라이선스](https://github.com/CinemaMod/mcef/blob/bb85d521e79662592fa72a67fadcbd622c664ce8/LICENSE)와
[Java-CEF 라이선스](https://github.com/CinemaMod/java-cef/blob/a78e832f9f13c2c688caea3d04d8b84fcd238d94/LICENSE.txt)를
[고지 폴더](../inventory/notices/mcef-98f0dd8821de/)에 저작권·출처와 함께 보존한다.
기존 패키징 경로가 이 폴더를 모드팩의 라이선스 자료에 포함한다.

공식 Maven의 `mcef-fabric-2.1.6-1.20.4-sources.jar`에는 Fabric 진입부만 있으며,
공통 구현과 Java-CEF 소스가 빠져 있다. 대응 소스에는 다음 두 아카이브가 모두 필요하다.
전체 커밋·아카이브 SHA-256·SHA-512·크기는 고지 폴더의 `provenance.json`에 기록한다.

- [MCEF 전체 소스와 빌드 파일](https://github.com/CinemaMod/mcef/archive/bb85d521e79662592fa72a67fadcbd622c664ce8.zip)
- [해당 버전의 Java-CEF 서브모듈 소스](https://github.com/CinemaMod/java-cef/archive/a78e832f9f13c2c688caea3d04d8b84fcd238d94.zip)

재배포 시 라이선스·저작권 고지와 위 전체 대응 소스에 대한 접근을 함께 제공해야 한다.
별도 다운로드되는 Chromium/CEF 네이티브 파일의 라이선스를 MCEF의 LGPL 하나로
대체하지 않는다. 공식 JAR·소스 아카이브는 검증용 로컬 캐시에만 두며 Git에는 추가하지 않는다.

## 검증

```sh
python scripts/check_dependencies.py --id mcef
python scripts/mods.py --manifest inventory/dependencies.lock.json verify
python scripts/build_modpack.py plan
```

공식 바이너리의 게시된 해시, JAR 내부 메타데이터, 소스 태그와 Java-CEF gitlink,
원본 라이선스 본문, 전체 소스 ZIP의 CRC를 확인했다. 이 저장소의 의존성 검증과
release-policy에 의해 MCEF는 클라이언트에만 선택된다.
