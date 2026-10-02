---
name: cmux-appearance
description: |
  cmux 터미널의 색감(테마·팔레트)과 글자 크기를 기록해 둔 것. 지금 쓰는 값이
  무엇인지 확인하거나, 설정이 날아갔을 때 되돌리거나, 다른 머신에서 같은 화면을
  재현할 때 쓴다. 설정 파일 위치와 값을 바꾸는 절차도 함께 담는다.
  사용자가 `/cmux-appearance` 또는 `$cmux-appearance` 를 명시적으로 호출했을 때만
  사용한다. cmux·터미널·폰트 관련 요청이 관련 분야에 해당한다는 이유만으로 자동
  사용하지 않는다.
user-invocable: true
disable-model-invocation: true
argument-hint: "[확인|복원]"
allowed-tools:
  - Bash
  - Read
  - Write
---

# /cmux-appearance — cmux 색감과 글자 크기

2026-09-21 기준으로 실제 쓰고 있는 값이야. `references/` 에 설정 파일 사본이 있어.

## 지금 쓰는 값

| 항목 | 값 |
|---|---|
| 테마 | **Rose Pine Dawn** (light). dark 는 `inherit` |
| 외관 모드 | `light` |
| 글꼴 | **D2Coding** |
| 글자 크기 | **15pt** |
| 전역 폰트 배율 | **100%** (미설정 = 기본값) |
| 배경 / 전경 | `#f5f5f3` / `#3b3948` |

**실효 글자 크기는 15pt 야.** 터미널 폰트(pt)랑 전역 배율(%)은 서로 곱해지는 별개 레이어인데, 배율이 기본 100% 라서 지금은 `font-size` 가 그대로 실효값이야.

## 설정 파일이 어디 있나

**이게 이 기록의 핵심이야.** cmux 의 Ghostty 설정은 흔히 아는 `~/.config/ghostty/config` 가 **아니야.**

| 무엇 | 경로 |
|---|---|
| 테마·팔레트·글꼴·크기 | `~/Library/Application Support/com.cmuxterm.app/config.ghostty` |
| 사이드바·외관 | `defaults read com.cmuxterm.app` (plist) |
| 전역 폰트 배율 | `~/.config/cmux/cmux.json` 의 `app.globalFontMagnification` |

```bash
cmux themes        # 현재 테마와 config 경로를 함께 알려준다
```

`~/.config/ghostty/config` 는 이 머신에 **아예 없어.** 거기에 써봤자 아무 일도 안 일어나.

## 두 레이어를 헷갈리지 마

글자가 작아지는 경로가 두 개고, 둘이 겹치면 과하게 작아져.

| 레이어 | 단위 | 어디에 |
|---|---|---|
| 터미널 폰트 | **절대 pt** | `config.ghostty` 의 `font-size` |
| 전역 배율 | **% (50~200, 10 단위)** | `cmux.json` 의 `app.globalFontMagnification` |

전역 배율은 터미널뿐 아니라 **탭 제목·사이드바·설정창·앱 크롬까지** 같이 키우고 줄여.

단축키도 갈려.

| 키 | 동작 |
|---|---|
| `⌃⌘-` / `⌃⌘=` / `⌃⌘0` | 워크스페이스 터미널 폰트 **±1pt** / 리셋 |
| `⌘-` / `⌘=` | **브라우저 줌** — 폰트와 무관 |

`⌃⌘` 로 조정한 건 디스크에 안 남아. 영구히 바꾸려면 `config.ghostty` 의 `font-size` 를 고쳐.

## 값을 바꿀 때

```bash
# 1. 백업
cp -p ~/Library/Application\ Support/com.cmuxterm.app/config.ghostty{,.bak-$(date +%Y%m%d%H%M%S)}

# 2. 편집 (font-size, theme, palette 등)

# 3. 재시작 없이 반영
cmux reload-config

# 4. 확인
cmux themes
```

`cmux.json` 을 고쳤으면 반영하기 전에 검증해.

```bash
cmux config validate     # JSONC 유효성 + 인식되는 키
```

**주의** — `cmux.json` 에 값을 쓰면 그 키는 **file-managed** 가 돼서, 앱 설정창이나 단축키로 조정한 값을 덮어써. 파일에서 그 키를 지우면 다시 앱 설정값으로 돌아가.

## 복원

```bash
cp skills/cmux-appearance/references/config.ghostty \
   ~/Library/Application\ Support/com.cmuxterm.app/config.ghostty
cmux reload-config
```

사이드바·외관은 `references/appearance-defaults.json` 의 값을 `defaults write com.cmuxterm.app <키> <값>` 으로 되돌려. **앱을 끈 상태에서 써야 해** — 앱이 돌고 있으면 종료할 때 메모리에 있던 값으로 덮어써버려.

## 동작 원칙

- **이 문서는 스냅샷이야.** 값을 바꿨으면 `references/` 사본이랑 위 표를 같이 갱신해. 안 그러면 복원했을 때 옛날 화면이 나와.
- **팔레트 16색은 테마가 준 거야.** `theme = light:Rose Pine Dawn` 아래에 펼쳐져 있어서, 테마를 바꾸면 그 블록도 같이 바뀌어. 색만 따로 손대면 테마랑 어긋나.
- **복원하기 전에 현재 파일을 백업해.** 지금 값이 마음에 들어서 기록해둔 거라, 되돌리는 쪽이 오히려 손해일 수도 있어.
