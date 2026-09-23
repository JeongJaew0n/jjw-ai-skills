# jjw-ai-skills

Claude Code 와 Codex 에서 쓰는, 직접 만든 스킬 모음입니다.
스킬은 `/스킬이름` 으로 부르는 작은 작업 절차예요. 자주 반복하는 일을 한 번 정리해 두고 매번 같은 방식으로 시키기 위해 만들었습니다.

## 3분 만에 시작하기

```bash
git clone https://github.com/JeongJaew0n/jjw-ai-skills.git
cd jjw-ai-skills
./bin/install.sh
```

이게 전부입니다. 이제 **새 세션을 열고** `/` 를 치면 아래 스킬들이 목록에 나옵니다.

> 이미 켜 둔 세션에는 안 보여요. 스킬은 세션이 시작될 때 읽히기 때문에, 설치한 뒤 한 번은 새로 열어야 합니다.

상태줄(hud)까지 쓰고 싶으면 새 세션에서 한 번만 더 입력합니다.

```
/hud:setup
```

## 스킬 부르는 법

- **`/스킬이름`** 또는 **`$스킬이름`** 으로 부릅니다. 예: `/diagnose 저장 버튼 누르면 500 에러`
- 이름만 말하는 건("diagnose 로 봐줘") 호출이 아니에요. AI 가 스킬을 알아서 고르지 않도록 막아 뒀기 때문입니다. 대신 슬래시로 불러 달라고 안내할 거예요.
- 예외는 `cmux-where` 하나입니다. "왼쪽 터미널에 물어봐" 같은 말을 하면 위치 파악까지는 알아서 합니다. 읽기만 하고 아무것도 바꾸지 않는 스킬이라서요. ([왜 이렇게 했는지](AGENTS.md))

## 어떤 스킬이 있나

<!-- 스킬을 추가·수정하면 아래 표도 함께 고칩니다. 맞는 묶음에 한 줄 넣으면 됩니다. -->

### 개발 흐름 — 계획하고, 만들고, 리뷰하고, 고치기

| 스킬 | 언제 쓰나 |
|---|---|
| [my-app-init](skills/my-app-init/) | 새 프로젝트를 시작할 때. git 규칙·`docs/` 골격·README·CLAUDE.md 같은 첫 세팅을 물어보며 한 번에 끝냅니다 |
| [ai-interview-tech](skills/ai-interview-tech/) | 기능을 만들기 **전에**. 코드를 근거로 "실패하면 어떻게 하지", "두 번 실행돼도 괜찮나" 같은 숨은 결정을 질문으로 끌어내 함께 정합니다 |
| [ai-plan-memory](skills/ai-plan-memory/) | 작업 계획을 `docs/plans/` 에 남겨 두고 싶을 때. 다음 세션에서 그대로 이어서 할 수 있습니다 |
| [review-code-intent](skills/review-code-intent/) | PR 을 리뷰할 때. "왜 만들었나 / 안전한가 / 의도대로 됐나" 세 갈래로 나눠 `docs/reviews/` 에 문서로 남깁니다 |
| [diagnose](skills/diagnose/) | 버그를 잡을 때. 원인을 찾기 전에는 고치지 않고, 찾은 원인은 기록으로 남겨 다음에 다시 겪지 않게 합니다 |

### Claude Code 자체를 다루기

| 스킬 | 언제 쓰나 |
|---|---|
| [hud](skills/hud/) | 상태줄에 레포·브랜치·현재 폴더·모델·컨텍스트 사용률·비용을 보여줍니다. 설치 후 `/hud:setup` 한 번 |
| [what-did-i-do-today](skills/what-did-i-do-today/) | "오늘 내가 뭘 시켰지?" 모든 세션의 입력을 모아 세션별로 보여줍니다. 기간을 바꿀 수도 있어요 |
| [ai-skill-integration](skills/ai-skill-integration/) | Claude 와 Codex 에 설치된 스킬이 서로 달라졌을 때. 어느 쪽이 최신인지 근거를 보여주고, 고른 방향으로 맞춥니다 |
| [claude-sessions](skills/claude-sessions/) | "지금 다른 Claude 세션 돌고 있나?" 이 맥의 세션을 모두 찾아 폴더·작업 중/대기·마지막 활동을 표로 보여줍니다. 읽기만 해요 |
| [create-another-rc-session](skills/create-another-rc-session/) | 폰(Remote Control)에서 다른 폴더로 옮길 수 없을 때. 그 폴더에서 새 세션을 띄워 줍니다 |

### 터미널(cmux)

| 스킬 | 언제 쓰나 |
|---|---|
| [cmux-where](skills/cmux-where/) | "왼쪽 터미널", "아래 창" 이 실제로 어디인지 화면 좌표로 알아냅니다. 유일하게 알아서 불리는 스킬 |
| [cmux-appearance](skills/cmux-appearance/) | 지금 쓰는 색감·글꼴 설정을 기록해 둔 곳. 설정이 날아갔거나 다른 컴퓨터에서 같은 화면을 만들 때 되돌립니다 |

### 플러그인·확장 프로그램 만들기

| 스킬 | 언제 쓰나 |
|---|---|
| [obsidian-plugin-local-deployment](skills/obsidian-plugin-local-deployment/) | 만든 Obsidian 플러그인을 내 vault 에 바로 배포합니다. vault 위치는 처음 한 번만 물어봅니다 |
| [obsidian-plugin-troubleshooting](skills/obsidian-plugin-troubleshooting/) | Obsidian 플러그인 만들다 겪은 문제들의 색인. 앱이 멈추거나 클립보드 서식이 깨지면 먼저 여기서 찾아봅니다 |
| [vscode-vsix-local-deployment](skills/vscode-vsix-local-deployment/) | 로컬에서 만든 VS Code 확장(VSIX)을 설치하고, 제대로 들어갔는지 ID 와 버전으로 확인합니다 |
| [chrome-extension-ai-guidance](skills/chrome-extension-ai-guidance/) | Chrome 팀의 "AI 로 확장 만들기" 가이드를 매번 새로 읽어와 내 프로젝트에 적용할지 판단합니다. 판단만 하고 설치는 하지 않아요 |

## 설치가 잘 됐는지 보기

```bash
./bin/install.sh --check      # 지금 상태만 보여줍니다. 아무것도 바꾸지 않아요
./bin/install.sh --dry-run    # 설치하면 무슨 일이 일어날지 미리 보기
```

스킬마다 `.claude` 와 `.codex` 두 줄이 나옵니다. `이미 연결됨` 이면 끝난 것이고, `연결 예정` 이면 `./bin/install.sh` 를 한 번 더 돌리면 됩니다.

## 알아두면 좋은 것

**복사가 아니라 링크로 설치됩니다.** `~/.claude/skills/` 와 `~/.codex/skills/` 에 이 저장소를 가리키는 심볼릭 링크가 걸려요. 그래서 여기서 `git pull` 만 하면 설치된 스킬도 같이 새 버전이 됩니다. (예전에 복사본으로 설치했다가 어느 쪽이 최신인지 알 수 없게 된 적이 있어서 이렇게 바꿨습니다.)

**`agents/openai.yaml` 은 손대지 않아도 됩니다.** 각 스킬 폴더에 있는 이 파일은 Codex 용인데, `install.sh` 가 `SKILL.md` 를 보고 자동으로 만들어요. 고쳐도 다음 설치 때 덮어씌워집니다.

**저장소에 없는 스킬은 건드리지 않습니다.** 전역에 따로 넣어 둔 스킬이 있어도 `install.sh` 는 목록에만 보여주고 지우지 않아요.

## 더 알아보기

- 스킬을 새로 만들거나 고치려면 → [AGENTS.md](AGENTS.md) (작성 규칙과 "왜 슬래시로만 부르게 했나")
- 이 저장소에서 작업하는 규칙(커밋·브랜치·문서 위치) → [CLAUDE.md](CLAUDE.md)
- 각 스킬이 정확히 무엇을 하는지 → 해당 폴더의 `SKILL.md`
