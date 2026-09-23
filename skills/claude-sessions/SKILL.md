---
name: claude-sessions
description: |
  이 맥에서 지금 돌고 있는 Claude Code 세션을 보여준다 — 몇 개인지, 각각 어느 폴더에서
  작업 중인지 대기 중인지, 마지막 활동이 언제인지. Claude Code 가 스스로 쓰는 세션
  레지스트리와 실제 프로세스 목록을 대조하므로 레지스트리에서 빠진 세션도 잡는다.
  읽기 전용이다.
  사용자가 `/claude-sessions` 또는 `$claude-sessions` 를 명시적으로 호출했을 때만
  사용한다. 세션·터미널·프로세스 관련 요청이 관련 분야에 해당한다는 이유만으로 자동
  사용하지 않는다.
user-invocable: true
disable-model-invocation: true
argument-hint: "[--all] [--json]"
allowed-tools:
  - Bash
---

# claude-sessions

지금 이 맥에서 돌고 있는 Claude Code 세션을 확인한다.

## 실행

스크립트를 그대로 돌리고, 출력을 **가공하지 말고** 보여준다. 표가 이미 읽기 좋게 나온다.

```bash
~/.claude/skills/claude-sessions/bin/claude-sessions.py          # 살아 있는 세션
~/.claude/skills/claude-sessions/bin/claude-sessions.py --all    # 끝난 세션의 남은 기록까지
~/.claude/skills/claude-sessions/bin/claude-sessions.py --json   # 다른 처리에 넘길 때
```

인자가 `--all` 이나 `--json` 이면 그대로 넘긴다.

## 보여준 다음

- 첫 줄의 요약("이 세션 말고 N개가 돌고 있습니다")을 먼저 말한다. 사용자가 물은 것이 그것이다.
- `작업 중` 인 세션이 있으면 짚어준다. 같은 폴더에서 두 세션이 동시에 작업 중이면
  파일이 서로 덮일 수 있으니 그 사실을 알린다.
- `(레지스트리 없음)` 줄이 있으면 **세션이 없다고 말하지 않는다.** 프로세스는 살아 있다.
  이름·상태를 모를 뿐이다.

**여기서 멈춘다.** 세션을 종료하거나 메시지를 보내는 것은 이 스킬의 일이 아니다.
사용자가 원하면 따로 요청받는다.

## 어떻게 알아내나

cmux 는 쓰지 않는다. Claude Code 가 세션마다 `~/.claude/sessions/<pid>.json` 을 쓰고,
거기에 이름·폴더·상태(`busy`/`idle`)가 들어 있다. 다만 이 파일만 믿으면 틀린다.

| 경우 | 실제로 본 것 | 스크립트 처리 |
|---|---|---|
| 파일 O, 프로세스 살아 있음 | 대부분 | 그대로 표시 |
| **파일 X, 프로세스 살아 있음** | 2026-09-23 에 1건 (`.key`·소켓은 있고 `.json` 만 없음) | `ps` 로 찾아 `lsof` 로 폴더를 읽고 `(레지스트리 없음)` 으로 표시 |
| 파일 O, 프로세스 죽음 | 가능 | 기본은 숨김, `--all` 에서 `종료됨` |

모델 도구인 `ListAgents` 도 같은 레지스트리를 읽어서, 위 두 번째 경우를 똑같이 놓친다.

화면에서 어느 pane 인지(좌/우/위/아래)까지 알고 싶으면 그건 `/cmux-where` 의 몫이다.

## 한계

- 이 맥의 로컬 세션만 본다. claude.ai 의 클라우드 세션이나 다른 컴퓨터의 Remote Control 세션은 보이지 않는다.
- `작업 중`/`대기` 는 Claude Code 가 레지스트리에 쓴 값이다. 방금 바뀌었으면 몇 초 늦을 수 있다.
