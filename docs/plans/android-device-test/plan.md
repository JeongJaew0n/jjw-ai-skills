# android-device-test: Android 실기기 검증과 플랫폼 함정을 다른 세션·AI 도 쓰게 하는 스킬

> 이 저장소는 공개 저장소다. 기기 시리얼, 무선 adb IP·포트·페어링 코드, 계정명, 실제 스크린샷은
> 문서·코드·예시에 넣지 않는다. 스크립트가 실행할 때 알아내고, 문서에는 `<serial>`·`<ip>:<port>` 같은
> 자리표시를 쓴다.

## 왜 만드나

mobile-black-screen 을 만드는 동안 실기기 테스트 방법이 세 곳에 흩어졌다.

| 있던 곳 | 문제 |
|---|---|
| 세션 임시 폴더의 보조 스크립트(adb 래퍼, 최상단 앱 확인, PNG 픽셀 판독, DataStore 디코더, 스위치 찾기) | 세션이 끝나면 지워진다. 실제로 지워져 대화 기록에서 원문을 되살렸다 |
| 그 앱의 `CLAUDE.md` 실기기 레시피·함정 목록 | 다른 프로젝트 세션은 읽지 않는다. 앱 고유 값과 범용 지식이 섞여 있다 |
| 그 앱의 `docs/troubleshootings/reusable/` 12건 | 이름은 reusable 인데 다른 저장소에서는 보이지 않는다 |

사용자가 요구한 것: **"다른 AI 들이 자동으로 참조할 수 있는 skill"** (2026-10-30).
다음 Android 프로젝트를 여는 세션이 같은 함정에 다시 빠지지 않게 하는 것이 목적이다.

## 범위

**넣는다**: 어느 앱, 어느 기기에서도 참인 것.

- 실기기 검증 절차: 연결 확인 → 상태 스냅샷 → 최상단 앱 확인 후 입력 → 픽셀로 판정 → 원복 → 원복 확인
- 판정 원칙: uiautomator 덤프보다 스크린샷 픽셀이 우선이다. 밝기와 생체 인증 UI 는 스크린샷에 안 찍힌다
- 함정 색인 (`references/`)
  - adb 쪽 함정: 비공개 서비스, 무선 리스너, kill-server, 재설치 뒤 접근성 꺼짐 등
  - 플랫폼·Compose 함정: 오버레이 창 종류, 미디어 버튼, 패키지 가시성, edge-to-edge 등
- 보조 스크립트 (`bin/`): 패키지명·좌표·색은 전부 인자로 받는다

**넣지 않는다** (mobile-black-screen 저장소에 남는다):

- 패키지명, 화면별 판정 좌표·색, DataStore 키의 의미, 그 앱이 바꾸는 설정 목록
- 스킬 본문에는 "앱별 값은 그 프로젝트 문서(CLAUDE.md 등)에서 찾아" 라고만 적는다

**범위 밖, 사용자 확인 필요**

- **Gemini 등 다른 AI**: `install.sh` 는 `~/.claude/skills` 와 `~/.codex/skills` 에만 링크한다.
  - `~/.gemini` 가 이 맥에 있지만 스킬 디렉터리를 자동으로 읽는지는 확인하지 않았다.
  - 연결하려면 `install.sh` 를 고쳐야 하고, 이는 저장소 전체에 걸린 결정이다.
  - 이번 작업에서는 Claude·Codex 두 곳까지만 다룬다.
- **에뮬레이터 전용 흐름, iOS**: 다루지 않는다.

## 자동 스킬로 두는 근거 (AGENTS.md 기준 세 가지)

| 기준 | 이 스킬에서 |
|---|---|
| 1. 알아서 하는 범위가 읽기·확인까지 | 자동으로 불렸을 때 해도 되는 것은 아래 읽기 작업뿐이다: 기기 목록, 최상단 앱·잠금 상태, 스크린샷 받아 판독, 상태 스냅샷·비교, 함정 문서 읽기. 그 밖의 작업은 아래 표의 조건을 따른다 |
| 2. 잘못 불려도 손해가 작다 | adb 가 없으면 종료 코드 3, 연결된 기기가 0대면 종료 코드 4 로 즉시 물러난다. 쓰기 하위 명령은 스크립트 단에서도 막는다(아래 `--yes`·가드) |
| 3. 쓰는·안 쓰는 상황을 좁게 적을 수 있다 | 쓸 때: Android 실기기, adb, "기기에서 확인", 무선 디버깅, 기기 스크린샷 판정. 안 쓸 때: 에뮬레이터 전용, iOS, 기기를 안 쓰는 일반 Android 코드 질문, Gradle 빌드 오류 |

**자동 호출 시 할 수 있는 일의 경계** (SKILL.md 가드레일과 AGENTS.md 표에 같이 적는다)

| 구분 | 작업 |
|---|---|
| 알아서 해도 됨 | `devices`, `state`, `shot`, `px`, `stats`, `crop`, `snapshot`, `diff`, `ui`(덤프 읽기), `datastore`(읽기), references 읽기 |
| 사용자가 기기 테스트를 직접 요청했을 때만 | `tap`·`swipe`·`text`·`key`(입력), `restore`(설정 되돌리기), `settings put`, `adb install -r`, `am start`, 앱 설정 바꾸기 |
| 확인받은 뒤에만 | `pm clear`, `uninstall`, 데이터 삭제, `am force-stop`, 무선 adb 페어링·`adb connect`·`adb tcpip`, 재부팅, 잠금 화면을 거는 동작 |
| 하지 않음 | `adb kill-server` (같은 adb 서버를 쓰는 다른 세션의 작업도 끊는다). 사용자에게 명령만 알려 준다 |

## 산출물

```
skills/android-device-test/
├── SKILL.md
├── bin/
│   └── android-device.py        Python 3 stdlib 만. 하위 명령 구조, --json
└── references/
    ├── device-testing-pitfalls.md    검증하다 속은 것들 (adb·스크린샷·입력·원복)
    ├── power-measurement.md          배터리 카운터로 전력 재는 법과 함정
    └── platform/                     reusable 트러블슈팅 12건을 앱 이름 없이 옮긴 것
        ├── overlay-window-cannot-cover-status-bar.md
        ├── accessibility-service-silently-disabled-by-reinstall.md
        ├── adb-cannot-start-non-exported-service.md
        ├── adb-wireless-connection-refused-after-phone-sleeps.md
        ├── biometric-only-unlock-locks-user-out.md
        ├── compose-drag-delta-always-zero-after-consume.md
        ├── compose-state-stale-right-after-resume.md
        ├── datastore-write-lost-when-service-stops-right-after-launch.md
        ├── icu-time-pattern-loses-leading-zero-and-breaks-java-time.md
        ├── media-app-name-shows-package-name.md
        ├── media-pause-ignored-use-media-button.md
        └── system-bar-icons-dark-on-always-dark-app.md
```

`agents/openai.yaml` 은 `install.sh` 가 만든다. 손대지 않는다.

### bin/android-device.py

공통:

- **adb 찾기**: 아래 순서로 찾는다. 다 없으면 설치 안내를 내고 종료 코드 3.
  1. `ANDROID_ADB` 환경변수
  2. `PATH` 의 adb
  3. `$ANDROID_HOME`·`$ANDROID_SDK_ROOT` 아래 `platform-tools/adb`
  4. 흔한 설치 위치: Homebrew commandlinetools, `~/Library/Android/sdk`
- **기기 고르기**: 아래 순서로 정한다.
  1. `-s <serial>` 인자
  2. `ANDROID_SERIAL` 환경변수
  3. 연결된 기기가 하나뿐이면 그 기기
  - 0대면 종료 코드 4.
  - 2대 이상인데 지정하지 않았으면 목록을 보여 주고 종료 코드 2.
- **adb 호출**: 모든 호출에 타임아웃(기본 40초)을 건다. 무선 연결이 걸리면 adb 가 끝없이 기다린다.
- **종료 코드**

  | 코드 | 뜻 |
  |---|---|
  | 0 | 성공 |
  | 1 | 오류 |
  | 2 | 사용법 오류, 또는 기기를 정하지 못함 |
  | 3 | adb 없음 |
  | 4 | 기기 없음 |
  | 5 | 가드 실패: 최상단 앱이 다르거나 잠금 화면이다 |

| 하위 명령 | 하는 일 | 쓰기 |
|---|---|---|
| `devices [--json]` | 기기 목록: 시리얼, USB/무선, 모델, Android 버전, SDK | 없음 |
| `state [--package P] [--json]` | 최상단 Activity, 잠금 여부, 화면 켜짐, 배터리, 음량, 글자 크기, 다크 모드. `--package` 를 주면 그 앱 창과 서비스 수까지 | 없음 |
| `guard <package>` | 최상단이 그 패키지이고 잠금 화면이 아니면 0, 아니면 5 | 없음 |
| `shot <out.png>` | `screencap -p` 를 파일로 받는다 | 기기 쪽 없음 |
| `px <png> name=x,y ...` | 지점별 색(#RRGGBB) | 없음 |
| `stats <png> [--rect x,y,w,h] [--threshold N]` | 영역의 최대 밝기, 문턱보다 밝은 픽셀 수, 무게중심. "순수 검정인가", "글자가 옮겨 갔나" 판정 | 없음 |
| `crop <png> x,y,w,h <out.png> [--scale N]` | 잘라서 확대해 저장한다. 작은 변화를 눈으로 볼 때 쓴다 | 없음 |
| `ui [--find REGEX] [--switch-near LABEL] [--json]` | uiautomator 덤프에서 텍스트 노드의 중심 좌표, 라벨 옆 스위치의 좌표와 상태. 덤프가 비면 다시 시도한다 | 없음 |
| `datastore <package> [--file NAME] [keys...]` 또는 `datastore --local <file.pb>` | Preferences DataStore 를 `run-as` 로 받아 스키마 없이 디코드한다(debuggable 빌드만) | 없음 |
| `snapshot <out.json> [--package P]` | 아래 설정을 기록한다 | 없음 |
| `diff <snapshot.json>` | 지금 값과 스냅샷을 비교한다. 달라진 것만 출력하고, 있으면 종료 코드 1 | 없음 |
| `restore <snapshot.json> --yes` | 스냅샷과 다른 값만 되돌린다. `--yes` 가 없으면 무엇을 바꿀지만 출력한다 | **있음** |
| `tap x y --package P` / `swipe x1 y1 x2 y2 ms --package P` | 입력 직전에 `guard` 를 돈다. 실패하면 보내지 않고 종료 코드 5 | **있음** |

`snapshot` 이 기록하는 설정:

- `system`: `screen_off_timeout`, `font_scale`, `screen_brightness`, `screen_brightness_mode`
- `secure`: `enabled_accessibility_services`, `accessibility_enabled`, `enabled_notification_listeners`
- `global`: `stay_on_while_plugged_in`, `low_power`
- 음량: 미디어·벨소리·알림. `cmd media_session volume --stream N --get`
- 다크 모드: `cmd uimode night`
- 앱 로케일 (`--package` 를 줬을 때)

`tap`·`swipe` 는 `--package` 를 필수로 받는다. 근거: 지난번 확인 없이 보낸 탭이 사용자가 보던 메신저 대화창에 들어갔다.

`pm clear`·uninstall·force-stop·연결 변경은 스크립트에 넣지 않는다. 확인받아야 하는 일을 한 줄짜리 하위 명령으로 만들면 확인 단계를 건너뛰기 쉽다. 이런 일은 SKILL.md 가 adb 명령을 직접 쓰게 하고, 그 전에 확인받으라고 적는다.

**되살린 스크립트에서 옮기는 것**: PNG 디코더는 필터 0~4, 컬러 타입 2·6 을 처리한다. 여기에 회색조(0)·회색+알파(4)를 더한다. DataStore 디코더는 wire type 0/1/2/5 를 읽고, Preferences 값 타입은 bool·float·int·long·string·string set·double 이다.

### SKILL.md (반말, 150~250줄 목표)

1. 한 단락 소개 + "앱별 값은 그 프로젝트 문서에서" 원칙
2. 스크립트 사용법 블록 (`~/.claude/skills/android-device-test/bin/android-device.py`)
3. **타협 불가 가드레일**: 위 경계 표, 원복 의무, `kill-server` 금지, 잠금 화면이면 멈추기, 사용자가 폰을 쓰는 중일 수 있음
4. **검증 순서**
   1. `devices`
   2. `snapshot`
   3. 앱의 저장된 설정 확인 (테스트가 사용자 설정을 바꾸거나 부작용을 낼 수 있는지)
   4. `guard` 뒤 입력
   5. 스크린샷 픽셀로 판정
   6. `restore`
   7. `diff` 가 비었는지 확인
5. **판정 원칙**: 무엇을 무엇으로 검증하나 (창 존재 = `dumpsys window`, 보임 = 픽셀, 밝기 = 사람 눈, 설정값 = DataStore 디코드 또는 동작, 미세한 이동 = 고대비 지점·무게중심)
6. **무선 연결**: 페어링 코드 방식과 `tcpip` 방식의 차이, mDNS 로 찾기. 연결·페어링은 확인받은 뒤에 한다
7. **함정 색인**: 증상 한 줄 → references 파일, "언제 읽나"

### frontmatter

```yaml
name: android-device-test
description: |
  adb 로 연결된 Android 실기기에서 앱 동작을 확인하는 절차·보조 스크립트와, 실기기에서 드러나는
  Android 플랫폼 함정 색인. 기기 상태 스냅샷·원복, 탭 전 최상단 앱 확인, 스크린샷 픽셀 판정,
  DataStore 읽기를 스크립트로 한다.
  다음 상황에서 사용한다 — 사용자가 `/android-device-test` 로 부를 때; "기기에서 확인해", "폰에서
  테스트해", "연결해 놨어" 처럼 Android 실기기 테스트를 말할 때; adb·무선 디버깅으로 기기에 붙어
  작업할 때; 기기 스크린샷으로 화면을 판정할 때; 오버레이·접근성 서비스·미디어 세션·edge-to-edge
  처럼 실기기에서만 드러나는 Android 동작 문제를 조사할 때.
  에뮬레이터 전용 작업, iOS, 기기를 쓰지 않는 일반 Android·Kotlin 코드 질문, Gradle 빌드 오류에는
  사용하지 않는다.
user-invocable: true
disable-model-invocation: false
argument-hint: "[devices | state | shot | snapshot | diff | ...]"
allowed-tools:
  - Bash
  - Read
```

## 같이 고칠 곳

| 파일 | 고칠 것 |
|---|---|
| `AGENTS.md` | `자동 스킬` 표에 한 줄, `### android-device-test 를 자동으로 둔 이유 (사용자 결정, 2026-10-30)` 절 |
| `README.md` | "스킬 부르는 법" 의 자동 스킬 목록, 새 묶음 "Android 실기기" 에 한 줄 (해요체) |
| mobile-black-screen `CLAUDE.md` | 실기기 레시피 위에 "범용 절차·스크립트는 `android-device-test` 스킬" 한 줄. 앱 고유 레시피는 그대로 둔다 (그 저장소의 규칙대로 별도 커밋) |
| mobile-black-screen `docs/troubleshootings/reusable/README.md` | "범용 판은 android-device-test 스킬 references 에 있다. 새 항목은 스킬 쪽에 먼저" 한 줄 |

**원본 12건은 앱 저장소에 그대로 둔다.** 그 저장소의 `CLAUDE.md`·`architecture.md` 가 경로로 가리키고, 그 기록은 원문 보존 대상이다. 그래서 두 벌이 생기는데, 그중 스킬 쪽이 범용 정본이다.

스킬로 옮길 때 고치는 것:
- 앱 이름과 앱 내부 클래스명(`BlackScreenTheme` 등)을 뺀다.
- 기기 모델·OS 버전은 "실측 환경" 으로 남긴다. 버전이 원인인 경우가 많고, 기기를 식별하는 정보도 아니다.

## 검증

실기기가 필요 없는 것:

- `python3 -m py_compile`, `--help`
- adb 가 없을 때 종료 코드 3: `ANDROID_ADB=/nonexistent` 에 `PATH` 를 비워서
- 합성 PNG 로 `px`·`stats`·`crop`
  - 컬러 타입 2·6 과 필터 0~4 를 모두 쓰는 파일을 stdlib 로 만든다.
  - macOS `sips` 로 만든 PNG 도 넣는다.
- 합성 DataStore pb 로 `datastore --local`: 타입별 값을 wire format 으로 직접 인코딩한다
- `./bin/install.sh --check`
- frontmatter 키 철자를 AGENTS.md 의 목록과 직접 대조한다

실기기가 필요한 것 (**사용자 지시 후에만**. mobile-black-screen 의 규칙이자 사용자 메모리 "실기기 테스트는 지시할 때만"):

- 읽기 명령만 돌린다: `devices`, `state`, `shot`, `snapshot` → `diff`, `ui`, `datastore`
- 기기를 바꾸는 `restore --yes`·`tap` 은 사용자가 따로 테스트를 시킬 때 확인한다

새 세션에서 확인할 것 (사용자 몫):

- `/` 목록에 뜨는지
- 트리거 문장("폰에서 확인해")에는 불리고, 안 쓸 문장("Gradle 빌드가 깨져")에는 안 불리는지

## 커밋

- 이 저장소 규칙: 전자동 커밋·푸시, main, 시작 전 `git pull --ff-only`, 거부되면 `pull --rebase`, `--force` 금지.
- jjw-ai-skills-d1 세션이 이 계획을 리뷰하기로 했다. 리뷰 의견은 메시지로만 받고, 반영할지는 이 세션이 판단한다.

## 리뷰 반영 (2026-10-30, jjw-ai-skills-d1 리뷰)

위 설계에서 바뀐 것. 구현은 이쪽을 따른다.

| 리뷰 | 반영 |
|---|---|
| 자동 범위가 사용자 메모리("실기기 테스트는 지시할 때만")와 충돌. `shot`·`ui` 는 사용자 화면 내용을 가져온다 | 자동 호출로 할 수 있는 일을 `devices`·`state`·references 읽기로 줄였다. `shot`·`px`·`stats`·`crop`·`ui`·`datastore`·`snapshot`·`diff` 는 사용자가 기기를 보라고 했을 때 쓴다. 경계를 세 칸에서 다섯 칸으로 나눴다 |
| 스크린샷·스냅샷이 공개 저장소에 들어갈 위험 | `shot`·`crop`·`snapshot`·`ui --save` 의 기본 출력은 `$TMPDIR/android-device/` 다. 경로가 git 작업 트리 안이면 거부하고 종료 코드 2, `--in-repo` 를 줄 때만 허용한다 |
| `diff` 의 종료 코드 1 이 오류와 겹친다 | 차이가 있으면 종료 코드 6(`EXIT_DIFFERS`)을 쓴다 |
| `install -r` 의 부작용, 서명 불일치, `-d`·`-g` | 가드레일에 넣었다. install 전후 snapshot·diff, 서명 불일치면 멈추고 uninstall 금지. `-d`·`-g` 는 확인받는 칸 |
| `settings put` 범위 | 직접 요청이 있어도 snapshot 이 기록하는 키만 바꾼다. 그 밖의 키는 확인받는 칸 |
| `force-stop` 구분 | 테스트 대상 앱은 직접 요청 시, 다른 앱은 확인 후 |
| `pm grant`·`appops set` 이 빠짐 | 직접 요청 칸에 넣었다. snapshot 이 런타임 권한과 `SYSTEM_ALERT_WINDOW` appop 을 기록하고, restore 가 되돌린다 |
| snapshot 항목 보강 | 다음을 추가했다. 애니메이션 배율 3종, `zen_mode`, `show_touches`, `pointer_location`, 회전 2종. 패키지별로는 배터리 최적화 예외. `--package` 는 여러 번 줄 수 있다 |
| `guard` 가 최상단 Activity 만 본다 | 포커스 창(`mCurrentFocus`)도 대상 패키지인지 확인한다. 알림창·키보드·대화상자가 앞에 있으면 실패한다. 회전도 출력한다 |
| references 정본이 두 벌 | 앱 저장소의 원본 각 파일 맨 위에 "범용 정본은 스킬" 한 줄을 넣는다 |
| 패키지명·사용자 경로 | references 에서 앱 이름·클래스명·`CLAUDE.md` 언급을 지웠다. 앱 패키지명과 `/Users/` 경로가 없음을 grep 으로 확인했다 |
| description 마지막 트리거가 넓다 | 주제 나열("오버레이·접근성·미디어 세션…")을 빼고 "실기기에서 본 동작이 코드에서 기대한 것과 다를 때" 로 좁혔다. 코드 함정은 SKILL.md 색인에 "기기에서 본 증상과 맞을 때만" 이라고 달았다 |

계획에서 빠진 것: `text`·`key` 입력 하위 명령은 만들지 않았다. 필요해지면 `tap` 과 같은 가드를 붙여 추가한다.
