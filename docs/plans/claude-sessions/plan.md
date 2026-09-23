# claude-sessions — 로컬에서 돌고 있는 Claude Code 세션 확인

## 목표

"지금 이 맥에서 Claude Code 세션이 돌고 있나?" 에 한 번에 답한다.
각 세션의 이름·폴더·상태(작업 중/대기)·마지막 활동 시각을 보여준다.

## 조사 결과 (2026-09-23, Claude Code 2.1.280)

cmux 가 필요 없다. Claude Code 가 스스로 기록하는 곳이 있다.

| 출처 | 주는 것 | 한계 |
|---|---|---|
| `~/.claude/sessions/<pid>.json` | 이름, cwd, `status`(busy/idle), `kind`, `updatedAt`, sessionId | **파일이 없는 살아 있는 세션이 있었다** (pid 7683, `.key`·소켓은 있음). 죽은 pid 의 파일이 남을 수도 있다 |
| `ps` | 실제로 살아 있는 claude 프로세스 | 이름·상태 없음 |
| `lsof -d cwd` | 레지스트리에 없는 프로세스의 폴더 | 9개에 0.18s — 레지스트리 누락분에만 쓴다 |
| `ListAgents` 도구 | 위 레지스트리를 읽은 결과 | 7683 을 똑같이 놓쳤다. 스크립트가 아니라 모델 도구라 스킬에서 재현 불가 |
| cmux | 화면 위치(좌/우 pane) | 세션 존재 여부에는 불필요. 위치는 `cmux-where` 의 몫 |

## 설계

- `bin/claude-sessions.py` — Python 표준 라이브러리만. 읽기 전용.
  1. 레지스트리를 읽는다
  2. `ps` 로 claude 프로세스를 모아 대조한다
     - 레지스트리 O + 살아 있음 → 정상
     - 레지스트리 X + 살아 있음 → **미등록** (cwd 는 lsof, 상태는 "알 수 없음")
     - 레지스트리 O + 죽음 → 남은 파일 (`--all` 에서만)
  3. 자기 자신은 부모 프로세스 체인으로 찾아 표시한다
- 시각은 **로컬 시간**으로 (jq strftime 은 UTC 라 9시간 틀렸다)
- `--json` 으로 기계 판독 출력

## 호출 정책

AGENTS.md 기본값(`disable-model-invocation: true`)을 따른다. 읽기 전용이라 예외 조건을
만족할 수는 있지만, 예외 추가는 사용자 결정이므로 여기서 넓히지 않는다.
