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

2026-09-21 기준으로 실제 쓰고 있는 값이다. `references/` 에 설정 파일 사본이 있다.

## 지금 쓰는 값

| 항목 | 값 |
|---|---|
| 테마 | **Rose Pine Dawn** (light). dark 는 `inherit` |
| 외관 모드 | `light` |
| 글꼴 | **D2Coding** |
| 글자 크기 | **15pt** |
| 전역 폰트 배율 | **100%** (미설정 = 기본값) |
| 배경 / 전경 | `#f5f5f3` / `#3b3948` |

**실효 글자 크기는 15pt 다.** 터미널 폰트(pt)와 전역 배율(%)은 곱해지는 별개 레이어인데, 배율이 기본 100% 라 지금은 `font-size` 가 그대로 실효값이다.

## 설정 파일이 어디 있나

**이게 이 기록의 핵심이다.** cmux 의 Ghostty 설정은 흔히 아는 `~/.config/ghostty/config` 가 **아니다.**

| 무엇 | 경로 |
|---|---|
| 테마·팔레트·글꼴·크기 | `~/Library/Application Support/com.cmuxterm.app/config.ghostty` |
| 사이드바·외관 | `defaults read com.cmuxterm.app` (plist) |
| 전역 폰트 배율 | `~/.config/cmux/cmux.json` 의 `app.globalFontMagnification` |

```bash
cmux themes        # 현재 테마와 config 경로를 함께 알려준다
```

`~/.config/ghostty/config` 는 이 머신에 **존재하지 않는다.** 거기에 쓰면 아무 일도 일어나지 않는다.

## 두 레이어를 헷갈리지 않는다

글자가 작아지는 경로가 둘이고, 겹치면 과하게 작아진다.

| 레이어 | 단위 | 어디에 |
|---|---|---|
| 터미널 폰트 | **절대 pt** | `config.ghostty` 의 `font-size` |
| 전역 배율 | **% (50~200, 10 단위)** | `cmux.json` 의 `app.globalFontMagnification` |

전역 배율은 터미널뿐 아니라 **탭 제목·사이드바·설정창·앱 크롬까지** 함께 키우고 줄인다.

단축키도 갈린다.

| 키 | 동작 |
|---|---|
| `⌃⌘-` / `⌃⌘=` / `⌃⌘0` | 워크스페이스 터미널 폰트 **±1pt** / 리셋 |
| `⌘-` / `⌘=` | **브라우저 줌** — 폰트와 무관 |

`⌃⌘` 조정은 디스크에 남지 않는다. 영구히 바꾸려면 `config.ghostty` 의 `font-size` 를 고친다.

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

`cmux.json` 을 고쳤다면 반영 전에 검증한다.

```bash
cmux config validate     # JSONC 유효성 + 인식되는 키
```

**주의** — `cmux.json` 에 값을 쓰면 **file-managed** 가 되어 앱 설정창·단축키 조정을 덮어쓴다. 파일에서 그 키를 지우면 다시 앱 설정값으로 돌아간다.

## 복원

```bash
cp skills/cmux-appearance/references/config.ghostty \
   ~/Library/Application\ Support/com.cmuxterm.app/config.ghostty
cmux reload-config
```

사이드바·외관은 `references/appearance-defaults.json` 의 값을 `defaults write com.cmuxterm.app <키> <값>` 으로 되돌린다. **앱을 끈 상태에서 쓴다** — 돌고 있으면 종료할 때 메모리 값으로 덮어쓴다.

## 동작 원칙

- **이 문서는 스냅샷이다.** 값을 바꿨으면 `references/` 사본과 위 표를 함께 갱신한다. 안 그러면 복원했을 때 옛 화면이 나온다.
- **팔레트 16색은 테마가 준 것이다.** `theme = light:Rose Pine Dawn` 아래에 펼쳐져 있으므로, 테마를 바꾸면 그 블록도 함께 바뀐다. 색만 따로 손대면 테마와 어긋난다.
- **복원 전에 현재 파일을 백업한다.** 지금 값이 마음에 들어서 기록해둔 것이므로, 되돌리는 쪽이 오히려 손실일 수 있다.
