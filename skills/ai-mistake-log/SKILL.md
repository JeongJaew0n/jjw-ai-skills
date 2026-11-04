---
name: ai-mistake-log
description: AI 가 작업 중 저지른 실수를 무엇을 했나·무엇이 망가졌나·왜·증거·재발 방지 규칙으로 기록하고, 그 규칙을 실제로 적용되는 곳에 넣는다 — 모든 세션이 읽는 전역 지침(~/.claude/CLAUDE.md, ~/.codex/AGENTS.md)과, 기계적으로 막을 수 있으면 Bash 명령을 실행 전에 거부하는 Claude Code 훅. 사용자가 `/ai-mistake-log` 또는 `$ai-mistake-log` 를 명시적으로 호출했을 때만 사용한다. 요청 내용이 관련 분야에 해당한다는 이유만으로 자동 사용하지 않는다.
user-invocable: true
disable-model-invocation: true
argument-hint: "[무슨 실수였는지 | sync | check]"
---

# ai-mistake-log

AI 가 저지른 실수를 남기고, 다음 세션이 같은 실수를 못 하게 만드는 스킬이야. "다음엔 조심할게" 는 다음 세션에 안 남아. 그래서 규칙을 **실제로 읽히는 곳**과 **실제로 막는 곳**에 넣어.

| 층 | 어디 | 언제 효과가 있나 |
|---|---|---|
| 기록(정본) | `~/.claude/mistakes/<날짜>-<slug>.md` (저장소 밖) | 사람이 경위를 다시 볼 때 |
| 글로 된 규칙 | `~/.claude/CLAUDE.md`, `~/.codex/AGENTS.md` 의 `ai-mistake-log` 블록 | 모든 세션이 시작할 때 읽음 |
| 기계적 차단 | Claude Code `PreToolUse` 훅 `bin/bash-guard.py` | Bash 명령마다 실행 전에 |

스크립트는 이 파일 옆 `bin/` 에 있어. 전역 설치본이면 `~/.claude/skills/ai-mistake-log/bin/` 이야. Codex 에서는 `~/.codex/skills/ai-mistake-log/bin/` 도 같은 파일이야.

```bash
M=~/.claude/skills/ai-mistake-log/bin/mistake-log.py
G=~/.claude/skills/ai-mistake-log/bin/bash-guard.py
```

셸 변수는 다음 Bash 호출에 안 남아. 명령마다 전체 경로를 쓰거나 같은 호출 안에서 정의해.

## 타협 불가 가드레일

- **`/ai-mistake-log` 나 `$ai-mistake-log` 호출에만 반응해.** 이름만 나온 건 호출이 아니야.
- **피해가 진행 중이면 기록보다 멈추는 게 먼저야.** 기록은 그다음이야.
- **실제 사고 기록은 저장소에 넣지 마.**
  - jjw-ai-skills 는 공개 저장소야. 호스트 이름, tailnet 이름, 기기 이름, 계정, 세션 id, 실제 경로 목록은 `~/.claude/mistakes/` 에만 둬.
  - 저장소에 들어가는 건 일반화한 검사 코드와 그 시험 명령뿐이야.
- **전역 지침은 블록 안만 고쳐.**
  - `<!-- ai-mistake-log:begin -->` 과 `end` 사이는 `sync` 가 기록으로 다시 만들어. 손으로 고치지 마.
  - 블록 밖은 사용자 것이니 건드리지 마.
- **`settings.json` 은 `install-hook` 으로만 고쳐.** 스크립트가 백업하고, 다른 키를 보존하고, JSON 을 다시 읽어 확인해.
- **훅은 고장 나면 통과시켜야 해(fail-open).** 예외로 모든 Bash 가 막히면 그게 더 큰 사고야. 검사기를 고칠 때 이 성질을 깨지 마.
- **재현은 해가 없는 방법으로 해.** 예를 들어 `pkill` 사고는 같은 인자의 `pgrep` 으로 재현해. 같은 명령을 다시 실행해서 "확인"하지 마.

## 절차

### 1. 사실을 모아

남길 것은 다섯 가지야. 대화 기록, 셸 히스토리, 로그에서 **원문**을 가져와.

| 항목 | 쓸 것 |
|---|---|
| 무엇을 했나 | 실행한 명령·도구 호출을 그대로. 무엇을 하려던 중이었는지 |
| 무엇이 망가졌나 | 피해 범위. 셀 수 있으면 숫자로 (탭 12개, 세션 10개처럼) |
| 왜 | 메커니즘. "부주의" 말고 **무엇을 잘못 알고 있었나**. 예: "BSD pkill 은 첫 패턴에서 옵션 해석을 멈춘다는 걸 몰랐다" |
| 증거 | 해가 없는 재현과 그 출력, 로그 줄 |
| 재발 방지 | 아래 2·3 단계의 결과 |

원인이 확실하지 않으면 "추정"이라고 적어. 추정을 사실처럼 쓰면 틀린 규칙이 전역 지침에 박혀.

### 2. 규칙을 한 줄로 만들어

`rule` 은 전역 지침에 그대로 들어가. 모든 세션이 매번 읽으니까 짧고 행동으로 써.

- 상황 말고 행동: "pkill 을 조심한다" ✗ → "macOS(BSD) pkill/pgrep 은 옵션을 모두 패턴 앞에 둔다" ○
- 너무 좁으면 이름만 바뀐 같은 실수가 다시 나와. 너무 넓으면 아무도 안 지켜. **같은 메커니즘으로 생기는 실수 부류**를 덮는 정도가 맞아.
- 사용자에게 규칙 문장을 보여 주고 넘어가. 전역 지침에 들어가는 문장이라 사용자 확인이 필요해.

### 3. 기계적으로 막을 수 있는지 판단해

훅으로 막는 건 아래를 **모두** 만족할 때만이야.

- 실행 전에 명령 문자열만 보고 판정할 수 있어
- 오탐이 거의 없어. 정상 명령을 자주 막으면 사용자가 훅을 꺼 버리고, 그러면 전부 잃어
- 막혔을 때 올바른 대안을 메시지에 줄 수 있어

만족하면 `bin/bash-guard.py` 에 검사기를 추가해.

1. `check_<이름>(cmd)` 함수를 만들어. 막을 때 이유 문자열을 돌려주고, 아니면 `None`.
2. `CHECKERS` 에 id 와 함께 등록해.
3. `BLOCK`·`ALLOW` 표에 시험 명령을 넣어. 사고 명령 그대로, 접두(`sudo`·`xargs`) 변형, 비슷하지만 정상인 명령을 꼭 넣어.
4. 실행해: `~/.claude/skills/ai-mistake-log/bin/bash-guard.py --self-test`, 하나만 볼 때는 `--check '<명령>'`.

메시지와 시험 명령에는 일반화한 예만 써(공개 저장소). 셸 명령을 나누는 도우미(`segments`, `real_command`)는 이미 있으니 재사용해.

만족하지 못하면 글로 된 규칙만 둬. 억지로 정규식 하나로 막으려 하지 마.

### 4. 기록을 만들어

```bash
~/.claude/skills/ai-mistake-log/bin/mistake-log.py new <slug> \
  --title "<한 줄 제목>" --rule "<2단계의 규칙>" [--guard <3단계의 검사기 id>] [--date YYYY-MM-DD]
```

만들어진 파일(`~/.claude/mistakes/<날짜>-<slug>.md`)의 각 절을 1단계에서 모은 사실로 채워. slug 는 소문자·숫자·하이픈이고 메커니즘을 드러내게 지어(`bsd-pkill-trailing-options`).

### 5. 적용해

```bash
~/.claude/skills/ai-mistake-log/bin/mistake-log.py sync           # 전역 지침 블록 갱신 (--dry-run 으로 미리 보기)
~/.claude/skills/ai-mistake-log/bin/mistake-log.py install-hook   # 처음 한 번. 이미 있으면 그대로 둠
~/.claude/skills/ai-mistake-log/bin/mistake-log.py check          # 어긋난 곳이 있으면 종료 코드 1
```

- `sync` 는 전역 지침 파일이 없으면 만들고, 바뀌는 파일은 먼저 `~/.claude/mistakes/.backups/` 에 사본을 둬.
- 처음 만들거나 처음 훅을 등록할 때는 무엇이 생겼는지 사용자에게 말해. 모든 세션에 영향이 가는 변경이야.
- `install-hook` 은 저장소의 `./bin/install.sh` 로 스킬이 링크돼 있어야 해. 훅은 저장소 실물이 아니라 설치 경로를 가리켜.

### 6. 확인해

- 훅을 추가했으면, 다음 Bash 호출에서 **해가 없는** 위반 명령이 실제로 거부되는지 봐. 예: `pgrep -f zzz -n`.
  - 훅 설정이 실행 중인 세션에 바로 반영되는지는 버전마다 달라. 안 막히면 새 세션에서 다시 봐.
- 올바른 형태의 명령은 통과하는지도 봐.
- `check` 가 "문제 없음"이어야 끝이야.

### 7. 커밋

- 검사기를 바꿨으면 저장소 규칙대로 커밋해. 커밋 메시지에도 개인 식별 정보는 넣지 마.
- 기록과 전역 지침은 저장소 밖이라 커밋 대상이 아니야.

## 명령 요약

| 명령 | 하는 일 |
|---|---|
| `mistake-log.py new <slug> --title --rule [--guard] [--date]` | 빈 기록 만들기 |
| `mistake-log.py list` | 기록 목록 |
| `mistake-log.py sync [--dry-run]` | 전역 지침 블록 갱신 |
| `mistake-log.py check` | 어긋난 곳 보고 |
| `mistake-log.py install-hook [--dry-run]` | settings.json 에 훅 등록 |
| `bash-guard.py --self-test` / `--list` / `--check '<명령>'` | 검사기 시험·목록·단건 판정 |

인자 없이 불렸으면 무슨 실수였는지부터 물어봐. `sync`·`check` 로 불렸으면 그 명령만 돌리고 결과를 보고해.

## 한계

- 훅은 Claude Code 에만 걸려. Codex 는 전역 지침(`~/.codex/AGENTS.md`)의 글로 된 규칙까지만 받아.
- `bash -c '…'` 처럼 문자열 안에 든 명령과, 변수에 담긴 명령은 검사하지 않아.
