# 스킬 전체 검토 (2026-11-03)

> 리뷰 문서예요. 저장소 규칙(`CLAUDE.md`)에 따라 자동으로 커밋하지 않았어요.
> 읽고 반영할 것을 고르면 그것만 고쳐서 커밋하면 돼요.

## 무엇을 기준으로 봤나

| 기준 | 어떻게 확인했나 |
|---|---|
| Claude Code 2.1.312 | 실행 파일에서 SKILL.md frontmatter 스키마를 직접 뽑아 [공식 문서](https://code.claude.com/docs/en/skills)와 대조 |
| Codex 0.162 (ChatGPT 앱) | Codex 동봉 skill-creator 지침(11/01 갱신)과 `codex debug prompt-input` 으로 모델에 실제로 보이는 스킬 목록 확인 |
| Agent Skills 표준 | [agentskills.io 명세](https://agentskills.io/specification) (2026-09-10 갱신) |
| 실제 사용 기록 | 이 맥에서 `claude -p "/skill-doctor"` 결과 |
| 동작 | 스크립트는 읽기 전용 모드로만 실행. 기기(adb)·세션 생성·설정 변경 명령은 실행하지 않음 |

스킬 18개를 네 묶음으로 나눠 따로 검토했고, 중요한 주장은 다시 직접 확인했어요.
세션 기록이나 실행 파일을 읽어서만 알아낸 것은 그렇다고 적었어요.

## 한눈에

- **깨진 채 쓰이는 것이 있어요.**
  - what-did-i-do-today 는 Codex 입력을 하나도 못 모아요.
  - VSIX 설치 스크립트는 cmux 안의 Claude 세션에서 엉뚱한 오류로 죽어요.
  - 스킬끼리 일을 넘기는 단계와, 셸 변수를 다음 명령에서 다시 쓰는 단계도 지금 구조에서는 동작하지 않아요.
- **저장소 밖의 `ai-decision-interview` 가 가장 시급해요.**
  - ai-interview-tech 의 옛 원본이에요.
  - 저장소 규칙이 금지하는 "반드시 먼저 적용" 문구 그대로 Claude·Codex 양쪽에서 저절로 불리고 있어요.
- **최신 기능 쪽에서 볼 것.**
  - `AGENTS.md` 의 frontmatter 키 목록이 2.1.251 기준에 멈춰 있어서, `context: fork`·`model` 같은 새 키를 규칙 안에서 쓰려면 먼저 갱신해야 해요.
  - 자동 스킬 3개의 `allowed-tools: Bash` 는 저장소 원칙("frontmatter 로 강제")과 반대 방향이에요.
- **18개 중 12개가 이 맥에서 한 번도 안 불렸어요.**
  - 수동 스킬은 평소 비용이 0 이라, 비용 때문에 지울 이유는 없어요.
  - 문제는 말로 요청하면 스킬로 연결되지 않는다는 거예요. Obsidian 배포는 스킬 없이 손으로 14번 했어요.
  - 그래서 자동으로 바꿀 후보 4개를 골랐어요.
- **한글 SKILL.md 는 생각보다 커요.**
  - 8개가 5천 토큰을 넘어요.
  - 대화가 자동 압축되면 스킬 본문은 5천 토큰까지만 다시 붙어서, 끝에 둔 금지선·자체 점검부터 잘려요.

## 1. 바로 고칠 것

| # | 대상 | 무엇이 깨졌나 | 근거 | 제안 |
|---|---|---|---|---|
| 1 | 저장소 밖 `ai-decision-interview` (`~/.claude/skills`, `~/.codex/skills` 의 실디렉터리) | ai-interview-tech 의 6/19 원본이에요. description 이 "…요청을 받았을 때 반드시 먼저 이 스킬을 적용한다", "명시적으로 말하지 않더라도 사용한다" 라서 일반 구현 요청에도 AI 가 스스로 불러요. 낡은 절차라 gisa-dojo 에 기준 커밋 없는 `decision-spec.md` 2개(10/29)를 남겼어요 | description 원문, `/skill-doctor` 최근 5일 10회, Codex 자동 목록에 포함, gisa-dojo 파일 확인. 세션 기록상 "버튼 만들어" 같은 요청에서도 불림(검토 에이전트) | 두 복사본을 스킬 폴더 밖으로 옮겨 은퇴시켜요. 내용은 ai-interview-tech 가 이미 대체해요(`decision-axes.md` 동일). 저장소 밖이라 git 으로 못 되돌리니 백업 후 이동 |
| 2 | what-did-i-do-today | ① `--codex` 가 0건이에요. Codex 0.162 기록에서는 사용자 입력이 다른 형식(`item_completed` 의 UserMessage)으로 들어가요. ② 대화 압축 요약과 세션 간 메시지가 "판별 정보 없음"으로 섞여 나와요 | 직접 실행: 최근 7일 Codex 기록 파일이 있는데 0건, 판별 불가 19건 | 새 형식을 읽게 고치거나 옵션을 빼요. `isCompactSummary`·`isVisibleInTranscriptOnly` 필드와 세션 메시지 표식을 기계 입력으로 분류해요 |
| 3 | vscode-vsix-local-deployment | `bin/vsix-install.sh` 의 `node -e` 3곳(93·139·159행)이 cmux 안 Claude 세션의 깨진 `NODE_OPTIONS` 때문에 죽어요. 그러면서 "package.json 필드 필요"나 "VS Code 업데이트"로 잘못 안내해요 | 이 세션에서 `node -e` 가 MODULE_NOT_FOUND 로 죽는 것 재현 | hud 런처처럼 `env -u NODE_OPTIONS node` 로 부르거나 JSON 파싱을 python3 로 바꿔요. 실패 종류도 구분해서 알려요 |
| 4 | ai-interview-tech → ai-plan-docs | 157행이 "ai-plan-docs 스킬에 맡겨" 라고 하는데, ai-plan-docs 는 수동 스킬이라 AI 가 부를 수 없어요 | SKILL.md:157-161, 공식 문서의 `disable-model-invocation` 정의 | "사용자에게 `/ai-plan-docs <slug>` 를 안내하고, 원하지 않으면 `docs/decisions/` 에 저장"으로 바꿔요 |
| 5 | ai-plan-docs, review-code-intent | 셸 가정이 틀려요. ai-plan-docs 는 52행에서 잡은 `$ROOT` 를 75행에서 다시 쓰는데, Bash 호출마다 새 셸이라 비어 있어요. 그래서 기존 폴더 충돌 확인이 조용히 "없음"이 돼요. review-code-intent 275행 `ls docs/plans/*/spec.md docs/decisions/*.md` 는 zsh 에서 글롭 하나만 비어도 통째로 실패해요 | 원문 확인. zsh 글롭 실패는 이번 검토 중 gisa-dojo 를 찾다가 그대로 재현됨 | 명령 블록 하나로 끝나게 쓰거나, 절대경로를 출력해 다음 명령에 그대로 써요. 글롭 대신 `find docs/plans docs/decisions -maxdepth 2 -name '*.md'` |
| 6 | `bin/install.sh` | ① 끊긴 링크 `ai-plan-memory`(7cd065b 에서 ai-plan-docs 로 이름이 바뀐 잔재)가 `--check` 에 안 보이고 지워지지도 않아요(120행 `[ -e ]`). ② 중첩 스킬 `hud/skills/setup` 에 openai.yaml 을 안 만들어서 Codex 가 `hud:setup` 을 알아서 고를 수 있어요 | 끊긴 링크 2개(Claude·Codex) 확인, `codex debug prompt-input` 자동 목록에 `hud` 포함 | 저장소를 가리키는 끊긴 링크는 보고하고 정리해요. hud 는 Codex 링크에서 빼거나, 중첩 SKILL.md 에도 정책 파일을 만들어요(플러그인 스킬에 먹는지는 확인 필요) |
| 7 | cmux-appearance | "지금 쓰는 값"(9/21 기록)은 외관 light 인데 지금 설정은 dark 예요. 이대로 "복원"하면 다크를 라이트로 덮어써요 | `defaults read com.cmuxterm.app appearanceMode` = dark, `references/appearance-defaults.json` = light | 지금의 다크가 의도한 거면 기록을 갱신하고, 아니면 표 이름을 "9/21 프리셋"으로 바꿔요. 복원 전에 현재 값과 비교하는 단계도 넣어요 |
| 8 | obsidian-plugin-troubleshooting | 색인이 낡았어요. my-obsidian-tools 의 새 기록 2건(IME 조합 중 단축키 무시 9/24, Live Preview 장식 미갱신 10/2)이 빠졌고, freeze-rules 사본은 "미측정"인데 원본은 "58~86ms 실측"으로 바뀌었어요 | 원본 저장소와 대조(검토 에이전트) | 색인과 사본을 갱신해요. `scan-sources.py` 가 `~/my/Dev` 고정이라 원본이 없으면 조용히 빠지는 것도 같이 고쳐요 |

## 2. 최신 흐름에 맞춰 갱신할 것

### 2-1. 저장소 규칙 (`AGENTS.md`)

- **frontmatter 키 목록을 2.1.312 기준으로 갱신.**
  - 지금 목록(99-104행)에 없는 키: `model`, `context`(inline|fork), `agent`, `background`, `hooks`, `shell`, `metadata`, `license`, `compatibility`.
  - `effort` 는 이제 `xhigh` 도 받아요.
  - 표준 키(`name`, `description`, `license`, `compatibility`, `metadata`, `allowed-tools`)와 Claude 전용 키를 나눠 적어 두면 좋아요. Claude 전용 키가 있으면 claude.ai 업로드가 거부돼요.
- **"오타 키는 조용히 무시된다"는 여전히 맞아요.** 2.1.312 에서 알 수 없는 키 경고는 에이전트 파일에만 있고 SKILL.md 에는 없어요. 기준 버전 숫자만 고치면 돼요.
- **"자동 스킬로 바꿀 때 할 일"에 두 가지를 추가.**
  - `allowed-tools` 를 스킬 자신의 스크립트로 좁히기 (2-2 참고)
  - 트리거 점검 문장 세트 만들기: 불려야 하는 말, 불리면 안 되는 말, 다른 스킬로 가야 하는 말. 2026년 들어 스킬 eval 이 사실상 기본이 됐어요([AI Engineer 발표](https://www.ai.engineer/talks/0vphxNt4wyk-dont-ship-skills-without-evals), [평가 매뉴얼](https://www.iwoszapar.com/resources/agent-skill-evals-manual.pdf)).
- **트리거는 지금처럼 description 에 두는 게 맞아요.** Claude 의 `when_to_use` 는 목록에서 description 뒤에 붙기만 해서 토큰이 줄지 않고, Codex 는 description 만 읽어요.

### 2-2. 자동 스킬의 권한 범위

cmux-where, tailnet-home, android-device-test 가 모두 `allowed-tools: [Bash, Read]` 예요. Claude Code 에서 `allowed-tools` 는 그 턴 동안 사전 승인이에요. 그래서 AI 가 스스로 이 스킬을 부르면, 그 턴의 셸 명령이 전부 확인 없이 돌아요. 가드레일이 "확인받은 뒤"로 묶어 둔 `cmux send`, `adb uninstall`, `pm clear` 도 마찬가지예요.

- `Bash(${CLAUDE_SKILL_DIR}/bin/<스크립트> *)` 처럼 자기 스크립트와 읽기 명령만 허용하면, 나머지는 평소처럼 권한 확인을 거쳐요.
- 평소 세션은 bypass 모드라 지금 당장 체감은 없어요. 하지만 다른 모드의 세션이나 저장소를 받아 쓰는 사람에게는 이게 유일한 강제 장치예요.
- Codex 는 이 키를 무시하니 이식성 손해는 없어요.
- 수동 스킬도 대부분 `Bash` 를 통째로 열어 두지만, 사용자가 직접 부른 경우라 우선순위는 낮아요.

### 2-3. 자동으로 바꿀 만한 스킬 (10/30 에 바꾼 기준으로)

| 스킬 | 왜 | 먼저 할 것 |
|---|---|---|
| claude-sessions | 전부 읽기이고 0.1초에 끝나요. 쓰는 상황도 좁게 적을 수 있어요. 2.1.312 에 생긴 `claude agents --json` 이 놓치는 레지스트리 밖 세션(오늘도 be-ccp 1개)을 잡아요 | cmux-where 의 "세션 목록을 물을 때" 트리거와 겹치니 한쪽으로 정리 |
| what-did-i-do-today | 읽기 전용이고, "오늘 내가 뭐 시켰지"처럼 좁게 적을 수 있어요 | 1번 표 2번의 수집 버그부터. 원문이 통째로 들어가니 `--max-chars 200` 과 `context: fork` 를 같이 |
| obsidian-plugin-troubleshooting | 읽기 전용 색인이고, 증상 문장으로 좁게 적을 수 있어요 | 색인 갱신, `allowed-tools: Bash` 정리. `paths` 는 쓰지 않기(루트 고정이 까다롭고, 지금 문제는 너무 안 불리는 쪽) |
| obsidian-plugin-local-deployment | 같은 배포를 9/17~10/18 에 스킬 없이 손으로 14번 했어요(세션 기록). "재설치해줘"가 수동 스킬로 연결되지 않아서, 빌드 신선도·기존 버전 확인을 한 번도 못 썼어요 | tailnet-home 방식으로 나눠요. 탐지와 `--dry-run` 은 알아서, 복사·리로드는 "배포해줘"라고 했을 때, 설정 변경은 확인 후. 덮어쓰기 전 백업 추가 |

나머지는 수동이 맞아요.

- 일하는 방식을 정하는 스킬: diagnose, ai-interview-tech, review-code-intent, my-app-init, ai-plan-docs
- 산출물을 남기는 스킬: chrome-extension-ai-guidance
- 설정이나 전역 상태를 바꾸는 스킬: create-another-rc-session, cmux-appearance, vscode-vsix-local-deployment, hud:setup
- 거의 안 쓰는 관리 스킬: ai-skill-integration

자동 스킬끼리 겹치는 곳도 하나 있어요. android-device-test 의 "폰에서 확인해"와 tailnet-home 의 "폰에서 열어줘"는 같은 폰을 가리켜요(adb 기기이자 tailnet 기기). 두 description 에 서로를 제외하는 문구를 넣어요.

### 2-4. 크기와 실행 방식

Claude Code 의 추정(`claude plugin details`)으로는 한글 SKILL.md 가 약 2.2바이트당 1토큰이에요. 이 기준으로 8개가 5천 토큰을 넘어요.

| 스킬 | 추정 토큰 | 잘리면 사라지는 곳 |
|---|---|---|
| review-code-intent | ~8.6k | 326-394행 리뷰 원칙·자체 점검 |
| my-app-init | ~7.5k | 뒷부분 템플릿·마무리 |
| cmux-where | ~6.3k | 함정·참고 표 (스크립트가 이미 처리하는 내용) |
| create-another-rc-session | ~6.0k | 150-220행 플래그 표·한계 |
| android-device-test | ~6.0k | 함정 색인 |
| ai-interview-tech | ~5.7k | 영속화·인계 절차 |
| diagnose | ~5.5k | 멈춤 규칙 |
| obsidian-plugin-local-deployment | ~5.2k | 리로드 절차 |

- **넘으면 생기는 일**: 대화가 자동 압축되면 스킬 본문은 5천 토큰까지만 다시 붙어요. Agent Skills 표준도 본문 5천 토큰 미만을 권해요.
- **제안**: 금지선은 위로 올리고, 참고 표·함정 목록·플래그 표는 `references/` 로 옮겨요.
- **`context: fork` 후보**: 다른 에이전트에서 따로 돌려 메인 대화를 가볍게 두는 방식이에요. Codex 는 이 키를 무시하고 그대로 돌아요.
  - what-did-i-do-today: 원문이 많아요.
  - chrome-extension-ai-guidance: 큰 HTML 을 다뤄요.
  - review-code-intent: 무거운 분석이라 잘 맞지만, 중간에 사용자에게 묻는 단계가 있어 설계가 필요해요.

### 2-5. 바깥 사정이 바뀐 것

| 스킬 | 바뀐 것 | 제안 |
|---|---|---|
| my-app-init | Codex 등 다른 AI 는 `AGENTS.md` 를 읽어요. 이 스킬은 README 와 CLAUDE.md 만 만들어서, 이 스킬로 만든 프로젝트 3곳 모두 AGENTS.md 가 없어요(9/17 에 직접 요청한 적이 있음, 세션 기록) | 규칙 정본은 AGENTS.md 에 두고, CLAUDE.md 에는 `@AGENTS.md` 한 줄 |
| obsidian-plugin-local-deployment | 이 맥에 Obsidian CLI 가 있어요(`obsidian plugin:reload`). 다른 세션이 8번 직접 썼는데 스킬의 리로드 절차(147-165행)는 토글·재시작뿐이에요. hot-reload 저장소는 `pjeby/hot-reload` 예요(스킬의 `pjeby/obsidian-hot-reload` 는 404). Bun 의 `bun.lock` 판별도 없어요 | CLI 로 리로드한 뒤 `dev:errors` 를 확인하는 순서로 |
| hud | 상태줄 설정에 `refreshInterval` 이 생겼어요. 안 쓰면 대기 중인 세션의 5시간 한도·경과 시간이 멈춰 보여요. 페이로드에도 `session_name`, `remote.session_id`(RC 여부) 같은 새 필드가 있어요 | setup 병합에 `refreshInterval` 추가, RC 배지 검토, `payload-example.json` 갱신 |
| create-another-rc-session | 플래그 표가 낡았어요(`--sandbox` 는 이제 remote-control 에서 거부됨). Claude 는 상위 폴더 신뢰를 따라가는데 스크립트는 정확한 경로만 봐서, 이미 신뢰된 `~/my` 아래 새 폴더에도 신뢰 절차를 요구해요. 새 `claude --bg --remote-control` 이 서버 관리를 대신할 수 있는지도 볼 만해요 | 실행 파일만 읽고 알아낸 거라, 실제로 한 번 실행해 보고 고쳐요 |
| claude-sessions | 2.1.312 에 `claude agents` 와 `ListAgents`(다른 맥·클라우드 세션까지)가 생겼어요 | 한계 절에 안내 추가, RC 열(`bridgeSessionId`) 추가 |
| vscode-vsix-local-deployment | `vsce` 패키지는 deprecated 예요 | 54행 `npx vsce` → `@vscode/vsce` |
| chrome-extension-ai-guidance | MV2 는 Chrome 138(2025-07)부터 꺼졌고 2026-08-31 에 웹스토어에서도 내려갔어요(검토 에이전트가 developer.chrome.com 에서 확인) | 70행 "지원 종료 대상" → "MV3 이전이 먼저" |
| review-code-intent | diff 기준(84행 `origin/{base}...origin/{head}`)에 fetch 가 없어서 fork PR 이나 삭제된 head 에서 틀려요 | `git fetch origin pull/{n}/head` 후 API 의 base·head SHA 로 diff |

### 2-6. 금지선의 빈틈

- **tailnet-home**
  > 이 검토 뒤에 REA 세션이 tailnet-home 에 리뷰 반영분을 커밋하지 않은 채 올려 뒀어요(`SKILL.md`, `bin/tailnet-home.py`).
  > - 홈 서버와 tailscaled 프록시를 `[::1]` 로 옮겼어요. userspace tailscaled 가 tailnet 연결을 `127.0.0.1` 로 넘겨서, 거기서 듣던 것이 tailnet 에서 닿았기 때문이에요.
  > - 비밀 파일 패턴을 홈 공유 규칙과 맞췄어요.
  > - `apps.json` 잠금을 홈 서버와 같이 쓰게 했어요.
  >
  > 아래 네 항목은 모두 그 미커밋 수정에 들어 있어요. 사용자 확인 후 커밋만 남았어요.
  - 홈 서버에 쓰기 API 가 생겼어요.
    - `/api/webclient`: 스킬이 금지한 `tailscale set --webclient` 를 대신 실행해요.
    - `/api/apps/<id>`: 앱을 켜고 꺼요.
    - `/api/sites/publish`, `/api/shares/*` 업로드도 쓰기예요.
  - 그래서 가드레일에 "홈 서버 쓰기 API 를 부르지 않기"를 넣어요. **(REA 수정에 포함: SKILL.md 57행)**
  - ~~비밀 파일 패턴이 7개뿐이라 홈 서버 `shares.py` 의 22개보다 적어요.~~ **(REA 수정에 포함)**
  - 파일 2만 개 상한(`SCAN_LIMIT`)에 걸리면 검사를 다 못 했는데도 등록해요(검토 에이전트). **(REA 수정에 포함: 상한에 닿으면 `add --root` 실패)**
  - `remove`·`--replace` 에 스크립트 단 `--yes` 를 두면 Codex 에서도 지켜져요. **(REA 수정에 포함: `--yes` 없으면 거부)**
- **android-device-test**
  - 58행은 "직접 시켰을 때 `input` 허용", 62행은 "`input` 직접 금지"라 서로 달라요.
  - 원인은 텍스트 입력·뒤로 가기를 보낼 가드된 명령이 없다는 거예요.

## 3. 그냥 갱신할 만한 것

- **안 쓰는 스킬 정리.** 수동 스킬은 평소 비용이 0 이라, 기준은 "내용이 낡았는지"예요.
  - **ai-plan-docs**
    - 형식은 my-app-init 골격이 이미 퍼뜨렸어요. plan 폴더 45개 중 26개가 3파일 형식이에요.
    - 고유 규칙인 이어가기 절차를 골격 README 로 옮기고, 이 스킬은 축소하거나 은퇴하는 걸 검토해요.
    - 템플릿의 커밋 항목(176-177행)은 없는 `.claude/commands/commit.md` 를 가리키니 바로 고쳐요.
  - **diagnose**
    - 기록 기능은 my-app-init 이 심는 CLAUDE.md 규칙이 대신하고 있어요. 기록은 34건인데 호출은 0회예요.
    - "원인 전 수정 금지", "3회 실패 시 중단" 같은 고유 규칙만 남겨 축소하는 걸 검토해요.
    - 멈춤 규칙 숫자도 148행(가설 3개)과 249행(수정 3회)이 서로 달라요.
  - **ai-skill-integration**
    - claude.ai 동기화 폴더(`synced/`)를 Claude 에만 있는 스킬로 잘못 잡아요.
    - 한쪽에만 있는 스킬에도 "덮어쓴다" 경고를 내요.
    - `install.sh --check` 로 합치는 걸 검토해요.
  - **chrome-extension-ai-guidance**: 대상 후보인 gpt-skin 에 한 번 돌려 보고 남길지 판단해요.
- **스킬 폴더 안의 리뷰 기록 4개.**
  - 대상: `skills/{ai-interview-tech,ai-plan-docs,hud,review-code-intent}/docs/refactor-review.md`
  - 설치 폴더로 같이 배포되고 있어요.
  - 전 항목이 해소된 기록이니 저장소 `docs/reviews/` 로 옮겨요. 리뷰 문서라 확인 후 커밋해요.
- **공개 저장소 정리.**
  - LICENSE 가 없어요(`claude plugin validate` 도 지적).
  - hud `plugin.json` 에 회사 메일이 있어요. 의도한 게 아니면 커밋용 메일로 바꿔요.
  - create-another-rc-session 174행에 맥 호스트명이 있어요(낮음).
  - tailnet 이름은 이력을 포함해 커밋된 적이 없어요.
- **Codex 화면용 메타데이터.**
  - `install.sh` 가 만드는 openai.yaml 에 `short_description` 이 없고, `default_prompt` 는 "Use $이름." 뿐이에요.
  - frontmatter 에 `metadata.short-description` 을 두고 그걸로 생성하면 Codex 화면이 나아져요.
- **자잘한 것.**
  - my-app-init: `$SKILL_DIR` 를 정의하는 문장이 없어요(49·98행).
  - my-app-init: 템플릿에 `diagnose-log:` 줄이 없어서 diagnose 가 다시 물어요.
  - my-app-init: 중첩 저장소를 `.git` 존재로만 판정해서, 모노레포 하위 폴더에서 `--git-init` 을 권해요.
  - cmux-where: 178행 "아래 함정 4"는 실제로 위에 있어요.
  - android-device-test: docstring 의 diff 종료 코드가 1로 적혀 있는데 실제는 6 이에요.
  - 저장소 밖 `~/.claude/commands/cmux-send.md` 는 cmux-where 함정 1과 반대로 가르쳐요(`cmux tree` 순서로 대상 고르기).

## 4. 스킬별 판정

"이 맥 사용"은 `/skill-doctor` 기록 기준이에요. 다른 컴퓨터에서 쓴 건 안 잡혀요.

| 스킬 | 모드 | 이 맥 사용 | 본문 추정 | 판정 | 핵심 |
|---|---|---|---|---|---|
| ai-interview-tech | 수동 | 0 | ~5.7k | 손볼 것 | ai-plan-docs 위임 불가, `argument-hint` 추가 |
| ai-plan-docs | 수동 | 0 | ~4.0k | 손볼 것 | `$ROOT` 버그, 템플릿 커밋 항목, 축소 검토 |
| ai-skill-integration | 수동 | 0 | ~4.1k | 손볼 것 | `synced/` 오탐, 거짓 경고, 끊긴 링크 못 봄 |
| android-device-test | 자동 | 0 (10/30 추가) | ~6.0k | 손볼 것 | `allowed-tools`, `input` 모순, tailnet-home 과 트리거 겹침 |
| chrome-extension-ai-guidance | 수동 | 0 | ~4.3k | 경미 | MV2 문구 |
| claude-sessions | 수동 | 1 | ~1.5k | 경미 | 자동 전환 후보 |
| cmux-appearance | 수동 | 0 | ~2.1k | 손볼 것 | 기록과 실제 설정 불일치 |
| cmux-where | 자동 | 3 | ~6.3k | 손볼 것 | `allowed-tools`, 본문 축소 |
| create-another-rc-session | 수동 | 1 | ~6.0k | 손볼 것 | 신뢰 판정·플래그 표(실행 확인 필요) |
| diagnose | 수동 | 0 | ~5.5k | 경미 | 멈춤 규칙 숫자, 축소 검토 |
| hud (+setup) | 수동 | 상태줄은 매일 | ~4.2k | 손볼 것 | Codex 자동 노출, `refreshInterval` |
| my-app-init | 수동 | 6 | ~7.5k | 손볼 것 | AGENTS.md 생성, 중첩 저장소 판정 |
| obsidian-plugin-local-deployment | 수동 | 0 (손으로 14회) | ~5.2k | 손볼 것 | Obsidian CLI, 자동 전환 후보 |
| obsidian-plugin-troubleshooting | 수동 | 0 | ~3.1k | 손볼 것 | 색인 낡음, 자동 전환 후보 |
| review-code-intent | 수동 | 0 | ~8.6k | 손볼 것 | zsh 글롭, diff 기준, 크기 |
| tailnet-home | 자동 | 2 | ~4.4k | 사용자 확인 대기 | 리뷰 항목 4개 모두 REA 의 미커밋 수정에 들어감. 남은 건 `allowed-tools` 좁히기(2-2) |
| vscode-vsix-local-deployment | 수동 | 0 | ~2.0k | 손볼 것 | `NODE_OPTIONS` 로 스크립트 실패 |
| what-did-i-do-today | 수동 | 2 | ~3.2k | 손볼 것 | Codex 0건, 판별 불가 섞임 |

## 5. 확인했고 그대로 둬도 되는 것

- **description 길이**: 모두 1,024자·1,024바이트 아래예요. 가장 긴 cmux-where 가 918바이트예요. Claude 목록 한도(1,536자)에도 여유가 있어요.
- **Codex 로드 상태**: 10/24 이후 로그에 스킬 로드 오류가 없어요. 수동 스킬은 Codex 의 자동 목록에서 의도대로 빠져 있어요.
- **이름 규칙**: 소문자·하이픈이고 폴더명과 일치해서, Agent Skills 표준과 Codex 검사기를 모두 통과해요.
- **`$SKILL_DIR` 관례**: 본문 문장으로 정의하는 지금 방식은 Claude·Codex 양쪽에서 통해요.
  - `${CLAUDE_SKILL_DIR}`, `` !`명령` ``, `context: fork` 는 Claude 전용이에요.
  - 그래서 쓰려면 Codex 용 대체 문장을 함께 둬야 해요.
- **`bin/` 폴더명**: 표준과 Codex 는 `scripts/` 를 권하지만 관례일 뿐이라 바꿀 필요는 없어요.
- **hud 플러그인 검증**: `claude plugin validate skills/hud` 는 통과해요. LICENSE·아이콘 지적은 공식 디렉터리에 제출할 때만 문제예요.
- **옛 용어**: "자동 호출 예외"는 스킬 본문에서 모두 사라졌어요(리뷰 기록 제외).
- **바깥 참조**: chrome 가이드 URL 4개는 모두 살아 있고, 페이지도 5/19 이후 바뀌지 않았어요. VS Code CLI 플래그도 1.141.2 기준으로 유효해요.

## 6. 검토하면서 생긴 일

- 검토 에이전트 하나가 `cmux shortcuts` 를 목록 명령으로 알고 실행했어요. "OK"만 나왔는데, cmux 단축키 설정 창이 열렸을 수 있어요. 설정은 바뀌지 않았어요.
- 다른 에이전트가 실행 파일 문자열을 실수로 저장소 루트(`trust.txt`)에 썼다가 바로 지웠어요. 지금 `git status` 는 깨끗해요.
- 다음 명령은 읽기 전용으로 실행했어요: `claude -p "/skill-doctor"`, `claude plugin validate`, `claude plugin details`, `codex debug prompt-input`.

## 출처

- Claude Code 스킬 문서: <https://code.claude.com/docs/en/skills>
- Agent Skills 명세: <https://agentskills.io/specification>
- Codex skill-creator 지침: `~/.codex/skills/.system/skill-creator/SKILL.md`, `references/openai_yaml.md` (Codex 0.162 동봉, 11/01 갱신)
- 스킬 eval: <https://www.ai.engineer/talks/0vphxNt4wyk-dont-ship-skills-without-evals>, <https://www.iwoszapar.com/resources/agent-skill-evals-manual.pdf>
- `context: fork`·`paths` 활용 사례: <https://smartscope.blog/en/generative-ai/claude/claude-code-best-practices-advanced-2026/>
