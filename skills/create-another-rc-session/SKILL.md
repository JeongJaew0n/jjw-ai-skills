---
name: create-another-rc-session
description: |
  Remote Control(폰 / claude.ai/code)에서 `/cd` 가 막혀 다른 폴더로 옮길 수 없을 때,
  대상 디렉터리에 RC 서버를 새로 띄워 그 디렉터리에 뿌리내린 세션을 만든다
  (= `/cd` + `/clear` 와 같은 결과). 폰에서 다른 프로젝트로 갈아타기, 새 폴더에서
  빈 컨텍스트로 시작하기가 이 스킬이 다루는 상황이다. 신뢰되지 않은 디렉터리에서는
  워크스페이스 신뢰 게이트에 걸리며, 그 우회는 사용자 확인을 받아야 한다.
  사용자가 `/create-another-rc-session` 또는 `$create-another-rc-session` 를
  명시적으로 호출했을 때만 사용한다. Remote Control·세션 생성·디렉터리 이동 요청이
  관련 분야에 해당한다는 이유만으로 자동 사용하지 않는다.
user-invocable: true
disable-model-invocation: true
argument-hint: "<대상 디렉터리> [세션 이름]"
allowed-tools:
  - Bash
  - Read
  - AskUserQuestion
---

# /create-another-rc-session — 다른 디렉터리에 RC 세션 띄우기

## 활성화 조건

사용자가 `/create-another-rc-session` 또는 `$create-another-rc-session` 로 호출한 경우에만 이 스킬을 실행한다. 이름만 언급한 경우는 호출로 보지 않는다 — `disable-model-invocation` 이 그 경로를 차단하므로, 실행하지 말고 슬래시 호출을 안내한다. Remote Control 이나 세션 생성과 내용이 유사하다는 이유만으로 자동 선택하지 않는다.

**이 스킬은 `AGENTS.md` 의 `자동 호출 예외` 대상이 아니다.** 설정 파일을 쓰고 네트워크에 노출되는 서버를 띄우므로 예외 조건(읽기 전용, 오호출 비용 낮음)을 둘 다 만족하지 않는다.

## 무엇을 하는 스킬인가

Remote Control 로 붙은 세션에서는 `/cd` 가 막혀 있다.

```
/cd isn't available over Remote Control.
```

그래서 "폰에서 작업 중인데 다른 폴더로 옮겨 새 컨텍스트로 시작" 이 안 된다. **해법은 cd 가 아니라 대상 디렉터리에 RC 서버를 새로 띄우는 것이다.** 그러면 폰에서 그 디렉터리에 뿌리내린 빈 세션으로 갈아탈 수 있다.

## 도구

```bash
"$SKILL_DIR/bin/rc-session.py" audit --dir <경로>    # 신뢰 상태·안전성 조사 (변경 없음)
"$SKILL_DIR/bin/rc-session.py" trust --dir <경로>    # 신뢰 기록 (보안 게이트 우회)
"$SKILL_DIR/bin/rc-session.py" start --dir <경로>    # 서버 기동 + URL 추출
"$SKILL_DIR/bin/rc-session.py" list  --rc-only       # 지금 떠 있는 RC 세션
"$SKILL_DIR/bin/rc-session.py" stop  --pid <PID>     # 종료
```

**서브커맨드가 나뉘어 있는 것은 의도다.** 한 번에 다 하는 경로를 두지 않았다. 위험한 단계(trust)를 사용자 확인 없이 통과하지 못하게 하기 위한 것이므로 합치지 않는다.

`SKILL_DIR` 은 이 `SKILL.md` 가 있는 디렉터리다.

## 실행 절차

### 1. audit — 먼저 조사한다

```bash
"$SKILL_DIR/bin/rc-session.py" audit --dir <경로>
```

판정이 네 가지로 갈리고, 각각 다음 단계가 다르다.

| 판정 | 뜻 | 다음 |
|---|---|---|
| 신뢰됨 | 이미 신뢰된 디렉터리 | **trust 건너뛰고 바로 3번** |
| `INERT` | 비어 있음 (또는 `.git`/`.gitignore` 뿐) | 사용자 확인 후 2번 |
| `HAS_CONTENT` | 내용물이 있다 | 내용 목록을 보여주고 확인받은 뒤 2번 |
| `HAS_CONFIG` | `.claude/`·`CLAUDE.md`·`.mcp.json` 등이 있다 | **중단.** 우회하지 않는다 |
| `MISSING` | 디렉터리가 없다 | `start --create` 로 만들거나 직접 `mkdir` |

### 2. trust — 신뢰 게이트 통과 (사용자 확인 필수)

한 번도 `claude` 로 열지 않은 디렉터리면 RC 서버가 즉시 죽는다.

```
Error: Workspace not trusted. Please run `claude` in <경로> first to review and accept the workspace trust dialog.
```

**RC 환경에서는 이 다이얼로그를 띄울 수가 없다.** 신뢰 상태는 `~/.claude.json` 의 `projects["<절대경로>"].hasTrustDialogAccepted` 에 있고, 이 스킬은 그 값을 기록해 게이트를 통과한다.

**이것은 보안 게이트 우회다.** 그래서 아래를 지킨다.

- **먼저 사용자에게 고지하고 확인을 받는다.** audit 결과(디렉터리에 무엇이 있는지)를 그대로 보여주고 나서 묻는다. 확인 없이 `--i-understand-trust-bypass` 를 붙이지 않는다. 이 플래그는 "사용자에게 알리고 승인받았다" 는 뜻이며, 그 사실이 없으면 거짓이 된다.
- **한 뒤에도 고지한다.** 최종 보고에 "신뢰 게이트를 우회했고 백업은 여기에 있다" 를 반드시 적는다.
- **`HAS_CONFIG` 는 어떤 플래그로도 우회하지 않는다.** 스크립트가 하드 거부한다. 신뢰 다이얼로그가 막으려는 대상이 정확히 그것이기 때문이다 — `.claude/settings.json` 의 hook 과 `CLAUDE.md` 는 디렉터리를 여는 순간 자동으로 읽히고 명령 실행까지 이어질 수 있다. 이 경우 맥 앞에서 직접 승인하도록 안내한다.

```bash
# audit 결과를 보여주고 사용자 확인을 받은 뒤에만
"$SKILL_DIR/bin/rc-session.py" trust --dir <경로> --i-understand-trust-bypass
```

스크립트가 대신 지켜주는 것: 쓰기 전 타임스탬프 백업, 원자적 교체(`os.replace`), `ensure_ascii=False` + `indent=2`, 기존 항목의 다른 키 보존.

### 3. start — 서버 기동

```bash
"$SKILL_DIR/bin/rc-session.py" start --dir <경로> --name "<이름>" [--create] [--wait 30]
```

`--dry-run` 으로 띄우기 전에 실행될 명령을 먼저 확인할 수 있다.

스크립트가 조립하는 명령은 이렇다.

```bash
cd <대상> && <실바이너리> remote-control --create-session-in-dir --spawn same-dir --name "<이름>"
```

**바이너리 경로를 PATH 에 맡기지 않는다.** `which claude` 는 cmux 래퍼(`/Applications/cmux.app/Contents/Resources/bin/claude`)로 잡힐 수 있고, 그 래퍼는 `--session-id` 와 `--settings` 를 주입한다. 스크립트는 `~/.local/bin/claude` 를 쓰는데, 이것이 **현재 활성 버전을 가리키는 심볼릭 링크**다. `~/.local/share/claude/versions/` 를 mtime 으로 고르는 것보다 정확하다 (최근에 받은 버전이 활성 버전이라는 보장이 없다).

성공 로그는 이 모양이다.

```
·✔︎· Connected · <이름> · main
    Capacity: 1/32 · New sessions will be created in the current directory
Continue coding in the Claude mobile app or https://claude.ai/code?environment=env_XXXXXXXX
space to show QR code · w to toggle spawn mode
```

스크립트가 로그를 폴링해 두 링크를 뽑는다. 세션 직링크는 OSC-8 하이퍼링크로 박혀 있어 `session_...` id 만 뽑아 조립한다.

- 환경 링크: `https://claude.ai/code?environment=env_...`
- 세션 직링크: `https://claude.ai/code/session_...`

**둘 다 사용자에게 준다.** 폰에서 여는 것이 목적이므로 링크가 최종 산출물이다.

### 4. 검증

```bash
"$SKILL_DIR/bin/rc-session.py" list --rc-only
```

`cwd` 가 대상 디렉터리이고 `bridgeSessionId` 가 붙은 항목이 보이면 성공이다. 실제 모양:

```json
{"pid": 12533, "kind": "interactive", "name": "airpods-battery-for-android-01",
 "nameSource": "derived", "cwd": "/Users/jjw/my/Dev/airpods-battery-for-android",
 "bridgeSessionId": "session_01CQXurWJfD2f32KRv9GGShP"}
```

### 5. 정리

작업이 끝나면 서버를 종료한다. **띄운 채로 잊지 않는다** — 계속 떠 있으면 그 디렉터리가 계속 외부에서 접속 가능한 상태로 남는다.

```bash
"$SKILL_DIR/bin/rc-session.py" stop --pid <PID>
```

스크립트는 `~/.claude/sessions` 기록에 없는 PID 는 거부한다 (남의 프로세스를 죽이지 않기 위한 것). 최종 보고에 PID 와 종료 방법을 함께 적어 사용자가 나중에 직접 끌 수 있게 한다.

## 세션 이름이 폰에서 어떻게 보이는가

폰 RC 목록의 이름은 `~/.claude/sessions/<pid>.json` 의 `name` 필드다. 기본값은 `nameSource: "derived"` = **cwd 폴더명 + 랜덤 2글자**라서 호스트 정보가 안 들어간다. 실제로 확인된 값들이 `project-ss-8a`, `jjw-ai-skills-5e` 형태다.

**맥북이 여러 대면 폰에서 구분이 안 된다.** 그래서 `--name` 에 호스트 접두어를 넣는 것을 권한다.

```bash
--name "m3·프로젝트명"
```

### `--remote-control-session-name-prefix` — 호스트 구분의 정공법

`remote-control --help` 원문:

```
--remote-control-session-name-prefix <prefix>
      Prefix for auto-generated session names
      (default: hostname; env: CLAUDE_REMOTE_CONTROL_SESSION_NAME_PREFIX)
```

**기본값이 이미 hostname 이다.** 그런데도 폰에서 호스트 구분이 안 되는 이유는, 이 접두어가 **RC 서버가 자동 생성하는 세션 이름**에만 붙기 때문이다. 터미널에서 먼저 `claude` 를 띄우고 나중에 `/remote-control` 로 붙인 세션은 이름이 이미 cwd 기반으로 정해져 있어서 접두어가 적용되지 않는다.

따라서:

- `--name` 을 주면 그것이 접두어를 **덮어쓴다.** (이 스킬로 띄운 서버가 `airpods-battery-for-android-01` 을 만든 것이 그 사례다. `--name` 을 안 줬다면 `jjwui-MacBookPro-01` 이 됐을 것이다.)
- 호스트 구분이 목적이면 `--name` 을 **생략**하거나, 접두어를 명시한다:

```bash
# 기본 hostname 접두어를 그대로 쓴다
claude rc --create-session-in-dir

# 짧은 별칭으로 덮어쓴다
claude rc --create-session-in-dir --remote-control-session-name-prefix "m3"
export CLAUDE_REMOTE_CONTROL_SESSION_NAME_PREFIX="m3"   # 환경변수로도 됨
```

프로젝트명과 호스트를 **둘 다** 보이게 하려면 `--name "m3·프로젝트명"` 처럼 직접 합쳐서 준다.

## 플래그 레퍼런스

`claude remote-control` 은 `claude --help` 의 `Commands:` 목록에 나오지 않는다. 아래는 바이너리에서 직접 확인한 것이다.

| 플래그 | 의미 |
|---|---|
| `--spawn <mode>` | `same-dir` / `worktree` / `session` |
| `--capacity <n>` | 동시 세션 수 |
| `--create-session-in-dir` / `--no-create-session-in-dir` | 서버 디렉터리에 새 세션 생성 허용 |
| `--name <이름>` | claude.ai/code 에 표시될 이름. 접두어를 덮어쓴다 |
| `--remote-control-session-name-prefix <prefix>` | 자동 생성 이름의 접두어 (기본: hostname, env: `CLAUDE_REMOTE_CONTROL_SESSION_NAME_PREFIX`) |
| `-c` / `--continue` | 이 디렉터리에 마지막으로 기록된 세션에 재연결 (약 4시간 이내) |
| `--enable-live-preview`, `--preview-port <n>` | 라이브 프리뷰 (기본 꺼짐) |
| `--sandbox`, `--permission-mode=<mode>` | 세션 권한 |

바이너리에 박힌 제약 메시지 그대로:

- `--session-id and --continue cannot be used with --spawn, --capacity, or --create-session-in-dir.`
- `--capacity cannot be used with --spawn=session (single-session mode has fixed capacity 1).`
- `--spawn may only be specified once`, `--capacity may only be specified once`
- `--preview-port requires --enable-live-preview (the tunnel is off by default).`

런타임 키: `space` = QR 토글, `w` = spawn 모드 토글.

**`claude remote-control --help` 는 헬프를 출력한 뒤에도 종료되지 않는다.** (2.1.265 에서 진짜 바이너리로 직접 실행해 확인. cmux 래퍼와는 무관하다.) 약 2.8KB 의 헬프를 정상적으로 찍고 나서 프로세스가 살아 있는다.

그래서 `--help | head -N` 으로 부르면 **출력이 통째로 안 보인다.** 헬프가 N줄에 못 미치면 `head` 가 나머지를 기다리며 붙잡고 있기 때문이다. 부를 거면 이렇게 한다:

```bash
~/.local/bin/claude remote-control --help > /tmp/rc-help.txt 2>&1 &
P=$!; for i in $(seq 10); do ps -p $P >/dev/null || break; /bin/sleep 1; done
kill -9 $P 2>/dev/null; cat /tmp/rc-help.txt
```

## 동작 원칙

- **신뢰 우회는 사용자 확인 없이 하지 않는다.** audit 결과를 보여주고 묻는다. `--i-understand-trust-bypass` 는 승인받았다는 진술이므로 승인이 없으면 붙이지 않는다.
- **`HAS_CONFIG` 디렉터리는 우회하지 않는다.** 예외 없다. 사용자가 요청해도 맥 앞에서 직접 승인하도록 안내한다. 이 도구로 열어야 할 이유보다 `.claude/` hook 이 자동 실행되는 위험이 크다.
- **RC 서버 기동은 외부 노출이다.** 그 디렉터리가 claude.ai 를 통해 접속 가능해진다. 사용자가 요청한 디렉터리에만 띄우고, 끝나면 끈다.
- **`~/.claude.json` 은 백업 없이 쓰지 않는다.** 계정 전체 설정이 들어 있어 되돌릴 수 없으면 안 된다. 스크립트가 자동으로 백업하지만, 최종 보고에 백업 경로를 적어 사용자가 알게 한다.
- **로그 파일에 접속 URL 이 남는다.** 기본 경로는 `<대상>/.rc-session.log` 다. 공유 디렉터리나 커밋될 위치라면 `--log` 로 옮긴다. `.gitignore` 에 추가할지 사용자에게 확인한다.
- **PID 를 보고한다.** 서버는 세션이 끝나도 계속 돈다. 사용자가 나중에 끌 수 있어야 한다.
