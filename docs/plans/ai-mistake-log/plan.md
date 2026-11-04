# ai-mistake-log — AI 가 저지른 실수를 기록하고 재발을 막는 스킬

> 이 저장소는 공개라서 이 문서와 스킬에는 호스트 이름·tailnet 이름·기기 이름·계정을 넣지 않는다.
> 실제 사고 기록은 저장소 밖 `~/.claude/mistakes/` 에 둔다.

## 왜 만드나

계기가 된 사고(2026-11-04)는 이렇다.

- 한 세션이 시험 서버를 끄려고 macOS 에서 `pkill -f "<패턴>" -U $(id -u) -n` 을 실행했다.
- macOS(BSD) 의 `pkill` 은 첫 패턴이 나오면 옵션 해석을 멈춘다. 그래서 뒤의 `-U`, `<uid>`, `-n` 이 모두 **추가 패턴**이 됐다.
- `-f` 라서 명령줄에 그 문자열이 들어간 프로세스가 전부 SIGTERM 을 받았다. 로그인 셸의 `--noprofile`, Claude 세션 인자의 `...-<uid>` 등이 걸렸다.
- 그 결과 4초 만에 터미널 탭 12개, 워크스페이스 4개, Claude 세션 10개가 닫혔다.

재현(읽기 전용 `pgrep`, 같은 모양):

```
pgrep -f -U "$(id -u)" -n '<없는 패턴>'   → 0개
pgrep -f '<없는 패턴>' -U "$(id -u)" -n   → 65개 (이 맥, 2026-11-04)
```

이런 실수는 대화 안에서 "다음엔 조심할게"로 끝나면 다음 세션이 모른다. 그래서 두 가지가 필요하다.

1. 실수를 정해진 형식으로 남기는 것
2. 거기서 나온 규칙을 **실제로 적용되는 곳**에 넣는 것

## 범위

**넣는다**

- 실수 기록 절차: 무엇을 했나 · 무엇이 망가졌나 · 왜 · 증거 · 재발 방지 규칙
- 규칙을 적용하는 두 층
  - **글로 된 규칙**: 모든 세션이 읽는 전역 지침에 한 줄씩. Claude 는 `~/.claude/CLAUDE.md`, Codex 는 `~/.codex/AGENTS.md`.
  - **기계적 차단**: Claude Code `PreToolUse` 훅이 Bash 명령을 실행 전에 검사해 거부한다. 글로 된 규칙은 잊힐 수 있지만 훅은 매번 돈다.
- 첫 사례: 위 `pkill` 사고. 훅 규칙 `bsd-pkill-trailing-options`.

**넣지 않는다**

- 실제 사고 기록(시각·세션·피해 목록)을 저장소에 넣는 것. 저장소에는 절차와 일반화된 검사 코드만 둔다.
- Codex 훅. Codex 0.162 에도 훅이 있지만 형식이 다르다. 이번에는 Codex 쪽을 글로 된 규칙까지만 다룬다.

## 설계

### 파일 배치

```
저장소 (공개)                                   저장소 밖 (이 맥)
skills/ai-mistake-log/                         ~/.claude/mistakes/
├── SKILL.md         기록·적용 절차              ├── 2026-11-04-bsd-pkill-trailing-options.md
└── bin/                                       └── .backups/   전역 지침을 고치기 전 사본
    ├── mistake-log.py   new/list/sync/check/install-hook
    └── bash-guard.py    PreToolUse 훅 (검사기 모음)
                                               ~/.claude/CLAUDE.md   ← sync 가 블록을 씀
                                               ~/.codex/AGENTS.md    ← sync 가 블록을 씀
                                               ~/.claude/settings.json ← install-hook 이 훅 등록
```

**기록 하나가 정본이다.** 전역 지침의 블록은 기록들에서 `sync` 로 다시 만든다. 손으로 고친 블록은 다음 sync 때 덮어쓴다. 블록 밖은 건드리지 않는다.

### 기록 형식 (`~/.claude/mistakes/<날짜>-<slug>.md`)

```markdown
---
date: 2026-11-04
title: BSD pkill 에서 패턴 뒤에 옵션을 붙여 무관한 프로세스를 죽임
rule: macOS(BSD) pkill/pgrep 은 옵션을 모두 패턴 앞에 둔다. ...
guard: bsd-pkill-trailing-options        # 기계적 차단이 있으면 그 id, 없으면 비움
---

## 무엇을 했나
## 무엇이 망가졌나
## 왜 (근본 원인)
## 증거
## 재발 방지 (규칙 · 적용한 곳)
```

`rule` 은 전역 지침에 그대로 들어가는 한 줄이다. 그래서 상황이 아니라 **행동**으로 쓴다("~할 때 ~한다").

### `bin/mistake-log.py` (Python stdlib)

| 하위 명령 | 하는 일 | 쓰기 |
|---|---|---|
| `new <slug> --title --rule [--guard] [--date]` | 위 형식의 빈 기록을 만든다. 같은 파일이 있으면 거부 | 기록 1개 |
| `list` | 기록 목록: 날짜, 제목, guard | 없음 |
| `sync [--dry-run]` | 기록들로 블록을 만들어 전역 지침 두 곳에 넣는다. 파일이 없으면 만들고, 바뀌는 파일은 먼저 `.backups/` 에 사본을 둔다 | 전역 지침 |
| `check` | 어긋난 곳을 보고하고, 있으면 종료 코드 1 | 없음 |
| `install-hook [--dry-run]` | `settings.json` 의 `hooks.PreToolUse` 에 Bash 훅을 병합한다. 이미 있으면 그대로 둔다. 쓰기 전에 백업하고, 쓴 뒤 JSON 을 다시 읽어 확인 | settings.json |

`check` 가 확인하는 것:

- `rule` 이 빈 기록
- 존재하지 않는 `guard` id
- 블록이 기록과 다름
- 훅 미설치

경로는 환경변수로 바꿀 수 있게 한다(`AI_MISTAKES_DIR`, `AI_MISTAKES_CLAUDE_MD`, `AI_MISTAKES_CODEX_MD`, `AI_MISTAKES_SETTINGS`). 시험은 scratch 경로로만 한다.

### `bin/bash-guard.py` (PreToolUse 훅)

- 입력: 훅 JSON(`tool_name`, `tool_input.command`).
- 거부할 때만 `hookSpecificOutput.permissionDecision: "deny"` 와 이유를 낸다. 나머지는 아무것도 출력하지 않고 종료 코드 0.
- **고장 나면 통과시킨다(fail-open).** 파싱 오류나 예외로 모든 Bash 가 막히면 그게 더 큰 사고다.
- 검사기는 id 를 가진 함수다. 새 실수로 기계적 차단이 필요해지면 검사기를 추가한다. 검사 코드는 일반적인 셸 지식이라 공개 저장소에 둬도 된다.
- `--self-test`: 막아야 할 명령과 통과시켜야 할 명령의 표를 돌린다. `--list`: 검사기 id 목록(`check` 가 씀).

**첫 검사기 `bsd-pkill-trailing-options`**

- 셸 명령을 `;` `&&` `||` `|` `&` 괄호 줄바꿈으로 나눈 뒤, 각 조각의 실제 명령이 `pkill`/`pgrep` 인지 본다.
  - 앞에 붙는 `VAR=값`, `sudo`, `env`, `command`, `exec`, `nohup`, `time`, `timeout`, `nice`, `xargs` 는 벗겨 낸다.
- `$(...)` 와 백틱은 한 단어로 묶고, 안쪽 명령은 따로 검사한다.
- 인자를 앞에서부터 읽는다.
  - 값을 받는 옵션(`-F -G -P -U -d -g -t -u`)은 다음 토큰까지 옵션으로 본다.
  - 첫 패턴이 나온 뒤에 `-` 로 시작하는 토큰이 있으면 거부한다.
- 거부 메시지에는 올바른 모양(`pkill -f -U "$(id -u)" -n '<패턴>'`)을 담는다.
- GNU(Linux) `pkill` 은 뒤에 와도 옵션으로 읽지만, 그래도 거부한다. "옵션은 앞에"가 양쪽에서 안전한 하나의 규칙이다.

알려진 한계(받아들임):

- `bash -c '...'` 처럼 문자열 안의 명령은 보지 않는다.
- 변수에 담긴 명령(`$CMD`)도 보지 않는다.

### 호출 정책

**수동 스킬**로 둔다(`disable-model-invocation: true`).

- 하는 일이 전역 지침·전역 settings 를 쓰는 것이라 `AGENTS.md` 의 자동 스킬 기준 1(알아서 하는 범위는 읽기까지)을 못 맞춘다.
- 대신 차단은 훅이 매번 하므로, 스킬이 자동으로 불릴 필요가 없다.

## 검증

1. `bash-guard.py --self-test`
   - 사고 명령, `$(...)` 뒤 옵션, `sudo`·`xargs` 접두는 거부해야 한다.
   - 올바른 순서, `echo "pkill x -n"`, 다른 명령의 `-n`, 줄바꿈 뒤 다른 명령의 옵션은 통과해야 한다.
2. scratch 경로로 `new → list → sync → check` 를 돌린다.
   - 블록 생성, 다시 sync 해도 변화 없음, 블록 밖 내용 보존, 백업 생성을 확인한다.
3. scratch settings 로 `install-hook` 을 돌린다. 다른 키 보존, 두 번 돌려도 하나만 등록되는지 본다.
4. 실제 적용(첫 사례)
   1. 기록 작성 → `sync` → `install-hook`
   2. 새 Bash 호출에서 `pgrep -f zzz -n` 이 거부되는지 본다. 읽기 전용이라 훅이 안 걸려도 해가 없다.
   3. 올바른 순서는 통과하는지 본다.
5. `./bin/install.sh --check`, README 표 갱신, frontmatter 키 철자 대조.

## 커밋

- 이 저장소 규칙대로 main 에 자동 커밋·푸시한다.
- 커밋에는 이 작업의 파일만 넣는다. 다른 세션의 미커밋 리뷰 반영분(`skills/tailnet-home/*`)과 리뷰 문서(`docs/reviews/`)는 빼고, 파일을 지정해서 add 한다.
