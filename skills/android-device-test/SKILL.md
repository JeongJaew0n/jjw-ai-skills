---
name: android-device-test
description: |
  adb 로 연결된 Android 실기기에서 앱 동작을 확인하는 절차와 보조 스크립트, 그리고 실기기에서
  겪은 Android 함정 색인. 탭 전 최상단 앱 확인, 기기 설정 스냅샷·원복, 스크린샷 픽셀 판정,
  DataStore 읽기를 스크립트로 한다.
  다음 상황에서 사용한다 — 사용자가 `/android-device-test` 로 부를 때; "기기에서 확인해",
  "폰에서 테스트해", "폰 연결해 놨어" 처럼 Android 실기기 테스트를 말할 때; adb·무선 디버깅으로
  기기에 붙어 작업할 때; 기기 스크린샷으로 화면을 판정할 때; 실기기에서 본 동작이 코드에서 기대한
  것과 다를 때.
  에뮬레이터 전용 작업, iOS, 기기를 쓰지 않는 일반 Android·Kotlin 코드 질문, Gradle 빌드 오류에는
  사용하지 않는다.
user-invocable: true
disable-model-invocation: false
argument-hint: "[devices | state | shot | snapshot | diff | restore | ...]"
allowed-tools:
  - Bash
  - Read
---

# android-device-test

adb 로 붙은 실기기에서 앱을 검증하는 방법이야. 여기 있는 건 **어느 앱·어느 기기에서도 참인 것**뿐이야. 패키지명, 판정할 좌표·색, DataStore 키의 뜻, 그 앱이 바꾸는 설정 같은 **앱별 값은 그 프로젝트 문서**(CLAUDE.md, docs/)에서 찾아. 없으면 추측하지 말고 물어봐.

기기 작업은 스크립트 하나로 해. 표준 라이브러리만 써서 설치할 게 없어.

```bash
D=~/.claude/skills/android-device-test/bin/android-device.py
$D devices                              # 연결된 기기 (시리얼·USB/무선·모델·Android 버전)
$D state [--package <pkg>]              # 최상단 앱·포커스 창·회전·잠금·화면·배터리·음량·글자 크기·다크 모드
$D guard <pkg>                          # 그 앱이 최상단·포커스이고 잠금이 아니면 0, 아니면 5

$D shot [out.png]                       # 스크린샷 (생략하면 $TMPDIR/android-device/)
$D px <png> 이름=x,y ...                # 지점 색
$D stats <png> [--rect x,y,w,h]         # 최대 밝기·밝은 픽셀 수·무게중심 ("순수 검정인가", "옮겨 갔나")
$D crop <png> x,y,w,h [out.png] --scale 4   # 잘라 확대 → Read 로 눈으로 보기
$D ui [--find 정규식] [--switch-near 라벨]  # uiautomator 덤프에서 좌표 찾기
$D datastore <pkg> [키...]              # Preferences DataStore 디코드 (debuggable 빌드만)
$D snapshot [out.json] --package <pkg>  # 되돌릴 설정 기록
$D diff <snapshot.json>                 # 지금과 다르면 목록 + 종료 코드 6

$D restore <snapshot.json> [--yes]      # 다른 값만 되돌림. --yes 없으면 계획만 출력
$D tap x y --package <pkg>              # guard 통과해야 보냄
$D swipe x1 y1 x2 y2 ms --package <pkg>
```

종료 코드: 0 성공 · 1 오류 · 2 사용법·기기 미지정(여러 대면 `-s <serial>`) · 3 adb 없음 · 4 기기 없음 · 5 가드 실패 · 6 스냅샷과 다름.
**3·4 가 나오면 거기서 멈춰.** 기기가 없으면 할 수 있는 게 없어. 사용자에게 연결 상태를 알리고 물러나.

## 타협 불가 가드레일

**알아서 불렸을 때 할 수 있는 건 아래 첫 줄까지야.** 사용자가 Android 얘기를 했다고 기기를 만지지 마.

| 언제 | 해도 되는 것 |
|---|---|
| 알아서 불렸을 때 | references 읽기, `devices`, `state` |
| 사용자가 기기를 보라고 했을 때 ("확인해 봐", "화면 어때") | 위 + `shot`·`px`·`stats`·`crop`·`ui`·`datastore`·`snapshot`·`diff`. 화면 내용과 앱 데이터를 가져오는 일이라 요청이 있어야 해 |
| 사용자가 기기 테스트를 직접 시켰을 때 | 위 + `tap`·`swipe`·`input`, `restore --yes`, 테스트 대상 앱의 `adb install -r`·`am start`·`am force-stop`, `settings put`(**snapshot 이 기록하는 키만**), 테스트 대상 앱의 `pm grant`/`revoke`·`appops set` |
| 확인받은 뒤에만 | `pm clear`, `uninstall`, 앱 데이터 삭제, `install -d`(다운그레이드)·`install -g`(모든 권한), 다른 앱 `force-stop`, snapshot 밖의 `settings put`, 기기 언어 변경, 무선 adb 페어링·`adb connect`·`adb tcpip`, 재부팅, 화면을 잠그는 동작 |
| 하지 마 | `adb kill-server`. 같은 adb 서버를 쓰는 다른 세션의 작업까지 끊어. 필요하면 명령만 알려 주고 사용자가 하게 해 |

- **입력은 `tap`/`swipe --package` 로만 보내.** `adb shell input` 을 직접 쓰지 마. 사용자가 폰을 쓰는 중일 수 있어. 실제로 확인 없이 보낸 탭이 사용자의 메신저 대화창에 들어간 적이 있어. 가드가 실패하면(5) 다시 시도하지 말고 사용자에게 상황을 말해.
- **잠금 화면이면 멈춰.** adb 로 잠금을 풀 수 없고, 풀려고 시도하지도 마.
- **테스트를 시작하면 먼저 `snapshot`, 끝나면 `restore` → `diff` 가 비었는지까지 확인해.** 원복을 못 한 값이 있으면 무엇인지 사용자에게 그대로 말해.
- **`install -r` 전후에 snapshot·diff 를 돌려.** 재설치하면 접근성 서비스·알림 접근이 조용히 꺼져.
- **서명이 달라 설치가 실패하면 멈춰.** uninstall 로 넘어가지 마. 사용자가 쓰던 스토어판 앱이 데이터째 지워져.
- **기능을 켜기 전에 부작용 있는 앱 설정부터 읽어** (`datastore`). 예: "켜면 볼륨을 0 으로" 같은 옵션이 켜져 있으면 테스트 한 번에 사용자 볼륨이 0 이 돼.
- **스크린샷·스냅샷·덤프를 저장소 안에 두지 마.** 사용자 화면 내용과 기기 정보가 커밋돼. 스크립트가 git 작업 트리 안이면 거부해. `--in-repo` 는 사용자가 그걸 원한다고 말했을 때만 써.
- 기기 시리얼, 무선 adb 주소·포트·페어링 코드를 문서·커밋에 적지 마. 실행할 때 `devices` 로 알아내.

## 검증 순서

1. `devices` → 기기가 하나인지, `device` 상태인지. `unauthorized` 면 폰에서 "USB 디버깅 허용" 을 눌러야 해.
2. `state --package <pkg>` → 잠금·화면 상태, 최상단 앱, 회전이 0(세로)인지.
3. `snapshot --package <pkg>` → 스냅샷 경로를 기억해 둬.
4. 앱의 저장된 설정을 읽어(`datastore <pkg>`). 테스트에 영향을 주거나 사용자 상태를 바꾸는 옵션이 있는지 봐.
5. 조작: `ui --find`/`--switch-near` 로 좌표를 찾고 `tap --package`. **누를 때마다 다시 덤프해.** 하나를 바꾸면 목록이 접히거나 밀려서 다음 좌표가 틀려.
6. 판정: 아래 표대로.
7. `restore <snapshot> --yes` → `diff <snapshot>` 가 "스냅샷과 같습니다" 인지.
8. 보고할 때 **무엇으로 확인했는지**를 같이 말해(픽셀인지, 창 목록인지, 사람 눈이 필요한지).

## 무엇으로 판정하나

| 확인할 것 | 방법 | 쓰면 안 되는 것 |
|---|---|---|
| 화면에 보이나 | `shot` → `px`·`stats` (픽셀) | uiautomator 덤프 — 이미 사라진 노드가 남아 있어 |
| 순수 검정인가 | `stats --rect ...` 의 `bright` 가 0 | 평균 밝기 |
| 위치가 옮겨 갔나 | 두 장의 `stats` 무게중심 차이 | 눈대중 |
| 서서히 변하나(페이드) | 고대비 지점 하나의 `px` | 평균 밝기 — 배경이 어두우면 안 움직여 |
| 창이 떠 있나·누수가 없나 | `state --package` 의 창 수(종류별), `dumpsys window windows` | 스크린샷 |
| 패널 밝기 | `dumpsys display | grep mWindowManagerBrightnessOverride` + **사람 눈** | 스크린샷 — 밝기는 안 찍혀 |
| 생체 인증 프롬프트 | 창 이름(`BiometricPromptRoot` 등) + 실제 손가락 | 스크린샷 — 별도 레이어라 안 찍혀 |
| 저장된 설정값 | `datastore` | `strings` — boolean 은 값이 안 보여 |
| 새 UI 가 붙었나 | 기기 화면에 실제로 떴는지 | 빌드·lint 성공 — 안 불리는 Composable 도 통과해 |

작은 영역을 직접 봐야 하면 `crop ... --scale 4` 로 저장하고 Read 로 이미지를 봐.

## 무선 연결

연결을 바꾸는 일이라 **확인받고** 해.

- **페어링 코드 방식** (Android 11+, 개발자 옵션 → 무선 디버깅)
  1. `adb pair <ip>:<pair-port>` 에 코드 6자리를 넣어.
  2. `adb connect <ip>:<connect-port>` 로 붙어.
  - 연결 포트는 페어링 포트와 달라.
  - 맥이면 `dns-sd -B _adb-tls-connect._tcp` 나 `adb mdns services` 로 연결 포트를 찾을 수 있어.
- **tcpip 방식**
  1. USB 를 꽂은 채로 `adb tcpip 5555`.
  2. `adb connect <ip>:5555`.
  - 폰이 오래 잠들거나 adbd 가 재시작되면 리스너가 사라져. 그러면 USB 를 다시 꽂아야 해.
- 무선이 끊겨도 `kill-server` 하지 마. `devices` 로 상태를 보고 사용자에게 알려.

## 함정 색인

증상이 맞으면 해당 파일을 읽어.

**검증하다 속는 것** → `references/device-testing-pitfalls.md`

입력·판정·adb 연결·기기 상태 함정이 다 여기 있어. 기기 테스트를 시작하기 전에 한 번 훑어.

**배터리 소모를 재야 할 때** → `references/power-measurement.md`

USB 를 빼야 하고, 카운터 눈금 때문에 조건당 30분이 필요해.

**플랫폼 함정** → `references/platform/`

| 증상 | 파일 |
|---|---|
| `TYPE_APPLICATION_OVERLAY` 창이 상태바·내비바를 못 덮음 | `overlay-window-cannot-cover-status-bar.md` |
| 재설치·force-stop 뒤 접근성 서비스가 조용히 꺼짐 | `accessibility-service-silently-disabled-by-reinstall.md` |
| adb 로 비공개 서비스 시작 시 `Requires permission not exported` | `adb-cannot-start-non-exported-service.md` |
| 무선 adb `Connection refused` (폰이 잠든 뒤) | `adb-wireless-connection-refused-after-phone-sleeps.md` |
| 생체 인증만 허용한 해제 수단에 갇힘 | `biometric-only-unlock-locks-user-out.md` |
| 다른 앱 이름 대신 패키지 이름이 나옴 (`<queries>`) | `media-app-name-shows-package-name.md` |
| `transportControls.pause()` 가 무시됨 | `media-pause-ignored-use-media-button.md` |
| 항상 어두운 앱에서 상태바 아이콘이 어둡고 내비바가 밝음 | `system-bar-icons-dark-on-always-dark-app.md` |

아래는 기기와 상관없는 **코드 함정**이야. 기기에서 본 증상이 이것과 맞을 때만 읽어.

| 증상 | 파일 |
|---|---|
| Compose 직접 포인터 루프에서 드래그 delta 가 항상 0 | `compose-drag-delta-always-zero-after-consume.md` |
| RESUME 직후 옛 설정값으로 동작 (`collectAsStateWithLifecycle`) | `compose-state-stale-right-after-resume.md` |
| `launch { 저장 }` 직후 `stopSelf()` 하면 저장이 사라짐 | `datastore-write-lost-when-service-stops-right-after-launch.md` |
| 시계 패턴에서 앞자리 0 이 빠지고 `java.time` 이 예외 | `icu-time-pattern-loses-leading-zero-and-breaks-java-time.md` |

새로 찾은 함정은 그 프로젝트의 `docs/troubleshootings/` 에 먼저 남겨. 어느 앱에서도 참이면 이 `references/` 에도 앱 이름을 빼고 옮겨.

## 한계

- PNG 판독은 순수 파이썬이라 1080×2400 전체 통계에 몇 초 걸려. `--rect` 로 영역을 좁히면 빨라져.
- `datastore` 는 `run-as` 가 되는 debuggable 빌드만 읽어. release 빌드는 동작으로 검증해.
- `restore` 가 되돌리는 건 snapshot 이 기록한 항목뿐이야. 기록하는 항목은 아래와 같아.
  - 설정: 화면 시간 초과, 글자 크기, 밝기, 접근성·알림 접근, 애니메이션 배율, 방해 금지, 회전, 터치 표시
  - 음량 3종, 다크 모드
  - `--package` 를 준 앱: 앱 로케일, 오버레이 appop, 런타임 권한, 배터리 최적화 예외
  - 이 밖에 바꾼 건 직접 되돌려야 해. 그래서 snapshot 밖의 `settings put` 은 확인받고 해.
- 주사율, 절전 모드의 부수 효과처럼 사람이 설정 화면에서 되돌려야 하는 것도 있어. `references/device-testing-pitfalls.md` 의 "기기 상태" 절을 봐.
