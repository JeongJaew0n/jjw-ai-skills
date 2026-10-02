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

`/create-another-rc-session` 이나 `$create-another-rc-session` 으로 불렀을 때만 돌려. 이름만 나온 건 호출이 아니야 — `disable-model-invocation` 이 그 경로를 막으니까, 실행하지 말고 슬래시로 불러달라고 안내해. Remote Control 이나 세션 생성 얘기가 나왔다고 알아서 집어 들지 마.

**이 스킬은 `AGENTS.md` 의 `자동 호출 예외` 대상이 아니야.** 설정 파일을 쓰고 네트워크에 노출되는 서버를 띄우니까, 예외 조건(읽기 전용, 오호출 비용 낮음)을 둘 다 못 맞춰.

## 뭐 하는 스킬이냐면

Remote Control 로 붙은 세션에선 `/cd` 가 막혀 있어.

```
/cd isn't available over Remote Control.
```

그래서 "폰으로 작업하다가 다른 폴더로 옮겨서 새 컨텍스트로 시작" 이 안 돼. **해법은 cd 가 아니라 대상 디렉터리에 RC 서버를 새로 띄우는 거야.** 그러면 폰에서 그 디렉터리에 뿌리내린 빈 세션으로 갈아탈 수 있어.

## 도구

```bash
"$SKILL_DIR/bin/rc-session.py" audit --dir <경로>    # 신뢰 상태·안전성 조사 (변경 없음)
"$SKILL_DIR/bin/rc-session.py" trust --dir <경로>    # 신뢰 기록 (보안 게이트 우회)
"$SKILL_DIR/bin/rc-session.py" start --dir <경로>    # 서버 기동 + URL 추출
"$SKILL_DIR/bin/rc-session.py" list  --rc-only       # 지금 떠 있는 RC 세션
"$SKILL_DIR/bin/rc-session.py" stop  --pid <PID>     # 종료
```

**서브커맨드를 나눠둔 건 일부러야.** 한 번에 다 하는 경로를 안 뒀어. 위험한 단계(trust)를 사용자 확인 없이 통과하지 못하게 하려는 거니까 합치지 마.

`SKILL_DIR` 은 이 `SKILL.md` 가 있는 디렉터리야.

## 실행 절차

### 1. audit — 먼저 조사해

```bash
"$SKILL_DIR/bin/rc-session.py" audit --dir <경로>
```

판정에 따라 다음 단계가 달라져.

| 판정 | 뜻 | 다음 |
|---|---|---|
| 신뢰됨 | 이미 신뢰된 디렉터리 | **trust 건너뛰고 바로 3번** |
| `INERT` | 비어 있음 (또는 `.git`/`.gitignore` 뿐) | 사용자 확인 후 2번 |
| `HAS_CONTENT` | 내용물이 있다 | 내용 목록을 보여주고 확인받은 뒤 2번 |
| `HAS_CONFIG` | `.claude/`·`CLAUDE.md`·`.mcp.json` 등이 있다 | **중단.** 우회하지 않는다 |
| `MISSING` | 디렉터리가 없다 | `start --create` 로 만들거나 직접 `mkdir` |

### 2. trust — 신뢰 게이트 통과 (사용자 확인 필수)

`claude` 로 한 번도 안 연 디렉터리면 RC 서버가 바로 죽어.

```
Error: Workspace not trusted. Please run `claude` in <경로> first to review and accept the workspace trust dialog.
```

**RC 환경에선 이 다이얼로그를 띄울 수가 없어.** 신뢰 상태는 `~/.claude.json` 의 `projects["<절대경로>"].hasTrustDialogAccepted` 에 있고, 이 스킬은 그 값을 기록해서 게이트를 통과해.

**이건 보안 게이트 우회야.** 그래서 아래를 지켜.

- **먼저 사용자한테 알리고 확인받아.** audit 결과(디렉터리에 뭐가 있는지)를 그대로 보여준 다음에 물어. 확인 없이 `--i-understand-trust-bypass` 를 붙이지 마. 이 플래그는 "사용자한테 알리고 승인받았다" 는 뜻이라, 그 사실이 없으면 거짓말이 돼.
- **하고 나서도 알려.** 최종 보고에 "신뢰 게이트를 우회했고 백업은 여기 있다" 를 꼭 적어.
- **`HAS_CONFIG` 는 어떤 플래그로도 우회하지 마.** 스크립트가 하드 거부해. 신뢰 다이얼로그가 막으려는 게 정확히 그거거든 — `.claude/settings.json` 의 hook 이랑 `CLAUDE.md` 는 디렉터리를 여는 순간 자동으로 읽히고, 명령 실행까지 이어질 수 있어. 이 경우엔 맥 앞에서 직접 승인하라고 안내해.

```bash
# audit 결과를 보여주고 사용자 확인을 받은 뒤에만
"$SKILL_DIR/bin/rc-session.py" trust --dir <경로> --i-understand-trust-bypass
```

스크립트가 대신 지켜주는 것: 쓰기 전 타임스탬프 백업, 원자적 교체(`os.replace`), `ensure_ascii=False` + `indent=2`, 기존 항목의 다른 키 보존.

### 3. start — 서버 기동

```bash
"$SKILL_DIR/bin/rc-session.py" start --dir <경로> --name "<이름>" [--create] [--wait 30]
```

`--dry-run` 을 주면 띄우기 전에 실행될 명령을 먼저 볼 수 있어.

스크립트가 조립하는 명령은 이거야.

```bash
cd <대상> && <실바이너리> remote-control --create-session-in-dir --spawn same-dir --name "<이름>"
```

**바이너리 경로를 PATH 에 맡기지 마.** `which claude` 는 cmux 래퍼(`/Applications/cmux.app/Contents/Resources/bin/claude`)로 잡힐 수 있고, 그 래퍼는 `--session-id` 랑 `--settings` 를 주입해. 스크립트는 `~/.local/bin/claude` 를 쓰는데, 이게 **현재 활성 버전을 가리키는 심볼릭 링크**야. `~/.local/share/claude/versions/` 에서 mtime 으로 고르는 것보다 정확해 (최근에 받은 버전이 활성 버전이라는 보장이 없거든).

성공하면 로그가 이렇게 나와.

```
·✔︎· Connected · <이름> · main
    Capacity: 1/32 · New sessions will be created in the current directory
Continue coding in the Claude mobile app or https://claude.ai/code?environment=env_XXXXXXXX
space to show QR code · w to toggle spawn mode
```

스크립트가 로그를 폴링해서 링크 두 개를 뽑아. 세션 직링크는 OSC-8 하이퍼링크로 박혀 있어서 `session_...` id 만 뽑아 조립해.

- 환경 링크: `https://claude.ai/code?environment=env_...`
- 세션 직링크: `https://claude.ai/code/session_...`

**둘 다 사용자한테 줘.** 폰에서 여는 게 목적이니까 링크가 최종 산출물이야.

### 4. 검증

```bash
"$SKILL_DIR/bin/rc-session.py" list --rc-only
```

`cwd` 가 대상 디렉터리고 `bridgeSessionId` 가 붙은 항목이 보이면 성공이야. 실제 모양:

```json
{"pid": 12533, "kind": "interactive", "name": "airpods-battery-for-android-01",
 "nameSource": "derived", "cwd": "/Users/jjw/my/Dev/airpods-battery-for-android",
 "bridgeSessionId": "session_01CQXurWJfD2f32KRv9GGShP"}
```

### 5. 정리

작업이 끝나면 서버를 꺼. **띄워놓고 잊지 마** — 계속 떠 있으면 그 디렉터리가 계속 외부에서 접속 가능한 상태로 남아.

```bash
"$SKILL_DIR/bin/rc-session.py" stop --pid <PID>
```

스크립트는 `~/.claude/sessions` 기록에 없는 PID 는 거부해 (남의 프로세스를 죽이지 않으려고). 최종 보고에 PID 랑 끄는 방법을 같이 적어서, 사용자가 나중에 직접 끌 수 있게 해.

## 세션 이름이 폰에서 어떻게 보이나

폰 RC 목록에 나오는 이름은 `~/.claude/sessions/<pid>.json` 의 `name` 필드야. 기본값은 `nameSource: "derived"` = **cwd 폴더명 + 랜덤 2글자**라서 호스트 정보가 안 들어가. 실제로 확인된 값들이 `project-ss-8a`, `jjw-ai-skills-5e` 같은 형태야.

**맥북이 여러 대면 폰에서 구분이 안 돼.** 그래서 `--name` 에 호스트 접두어를 넣는 걸 권해.

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

**기본값이 이미 hostname 이야.** 그런데도 폰에서 호스트 구분이 안 되는 건, 이 접두어가 **RC 서버가 자동 생성하는 세션 이름**에만 붙기 때문이야. 터미널에서 먼저 `claude` 를 띄우고 나중에 `/remote-control` 로 붙인 세션은 이름이 이미 cwd 기반으로 정해져 있어서 접두어가 안 붙어.

그러니까:

- `--name` 을 주면 그게 접두어를 **덮어써.** (이 스킬로 띄운 서버가 `airpods-battery-for-android-01` 을 만든 게 그 사례야. `--name` 을 안 줬으면 `jjwui-MacBookPro-01` 이 됐을 거야.)
- 호스트 구분이 목적이면 `--name` 을 **빼거나**, 접두어를 명시해:

```bash
# 기본 hostname 접두어를 그대로 쓴다
claude rc --create-session-in-dir

# 짧은 별칭으로 덮어쓴다
claude rc --create-session-in-dir --remote-control-session-name-prefix "m3"
export CLAUDE_REMOTE_CONTROL_SESSION_NAME_PREFIX="m3"   # 환경변수로도 됨
```

프로젝트명이랑 호스트를 **둘 다** 보이게 하려면 `--name "m3·프로젝트명"` 처럼 직접 합쳐서 줘.

## 플래그 레퍼런스

`claude remote-control` 은 `claude --help` 의 `Commands:` 목록에 안 나와. 아래는 바이너리에서 직접 확인한 거야.

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

**`claude remote-control --help` 는 헬프를 출력하고 나서도 종료되지 않아.** (2.1.265 에서 진짜 바이너리로 직접 실행해 확인. cmux 래퍼랑은 무관해.) 약 2.8KB 헬프를 정상적으로 찍고 나서 프로세스가 계속 살아 있어.

그래서 `--help | head -N` 으로 부르면 **출력이 통째로 안 보여.** 헬프가 N줄이 안 되면 `head` 가 나머지를 기다리면서 붙잡고 있거든. 부를 거면 이렇게 해:

```bash
~/.local/bin/claude remote-control --help > /tmp/rc-help.txt 2>&1 &
P=$!; for i in $(seq 10); do ps -p $P >/dev/null || break; /bin/sleep 1; done
kill -9 $P 2>/dev/null; cat /tmp/rc-help.txt
```

## 동작 원칙

- **신뢰 우회는 사용자 확인 없이 하지 마.** audit 결과를 보여주고 물어. `--i-understand-trust-bypass` 는 승인받았다는 진술이라, 승인이 없으면 붙이지 마.
- **`HAS_CONFIG` 디렉터리는 우회하지 마.** 예외 없어. 사용자가 요청해도 맥 앞에서 직접 승인하라고 안내해. 이 도구로 열어야 할 이유보다 `.claude/` hook 이 자동 실행될 위험이 더 커.
- **RC 서버를 띄우는 건 외부 노출이야.** 그 디렉터리가 claude.ai 를 통해 접속 가능해져. 사용자가 요청한 디렉터리에만 띄우고, 끝나면 꺼.
- **`~/.claude.json` 은 백업 없이 쓰지 마.** 계정 전체 설정이 들어 있어서 되돌릴 수 없으면 안 돼. 스크립트가 자동으로 백업하지만, 최종 보고에 백업 경로를 적어서 사용자가 알게 해.
- **로그 파일에 접속 URL 이 남아.** 기본 경로는 `<대상>/.rc-session.log` 야. 공유 디렉터리거나 커밋될 위치면 `--log` 로 옮겨. `.gitignore` 에 추가할지는 사용자한테 확인해.
- **PID 를 보고해.** 서버는 세션이 끝나도 계속 돌아. 사용자가 나중에 끌 수 있어야 해.
