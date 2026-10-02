# spec — skill-tone-casual

## 목표
이 저장소의 모든 스킬 `SKILL.md` 본문을 문어체(`~한다`, `~이다`)에서 반말 대화체(`~해`, `~야`,
`~하지 마`)로 바꾼다. 동작·규칙·절차의 **의미는 하나도 바꾸지 않는다.**

기준 문체는 이미 바꿔 둔 `skills/ai-plan-docs/SKILL.md` (커밋 `7cd065b`) 다.

## 범위
- 포함 (15개 파일, 본문만):
  - `skills/ai-interview-tech/SKILL.md` (192줄)
  - `skills/ai-skill-integration/SKILL.md` (161줄)
  - `skills/chrome-extension-ai-guidance/SKILL.md` (191줄)
  - `skills/claude-sessions/SKILL.md` (63줄)
  - `skills/cmux-appearance/SKILL.md` (109줄)
  - `skills/cmux-where/SKILL.md` (220줄)
  - `skills/create-another-rc-session/SKILL.md` (229줄)
  - `skills/diagnose/SKILL.md` (257줄)
  - `skills/hud/skills/setup/SKILL.md` (199줄)
  - `skills/my-app-init/SKILL.md` (296줄)
  - `skills/obsidian-plugin-local-deployment/SKILL.md` (199줄)
  - `skills/obsidian-plugin-troubleshooting/SKILL.md` (102줄)
  - `skills/review-code-intent/SKILL.md` (394줄)
  - `skills/vscode-vsix-local-deployment/SKILL.md` (88줄)
  - `skills/what-did-i-do-today/SKILL.md` (116줄)
- 제외:
  - `skills/ai-plan-docs/SKILL.md` — 이미 바뀜 (기준 문서)
  - frontmatter 전체 — 특히 `description` 은 AGENTS.md 의 권장 형식("명시적으로 호출했을 때만
    사용한다")을 지켜야 하고, 트리거 문구가 바뀌면 호출 동작이 달라질 수 있다
  - 코드 블록(```` ``` ````) 안의 내용 — 명령어·주석·스크립트 출력 예시
  - **스킬이 파일로 찍어내는 템플릿·문구** — 산출물의 문체가 바뀌는 건 동작 변경이다.
    예: `review-code-intent/templates/*.md`, `my-app-init` 이 `CLAUDE.md` 에 쓰는 결정 블록,
    `ai-plan-docs` 의 파일 템플릿 헤더
  - `docs/refactor-review.md` 들 — 과거 리뷰 기록이라 원문 보존
  - `skills/hud/README.md` — 사람용 문서. 저장소 README(해요체)와 맞출지 별도 판단 [미정]
  - `obsidian-plugin-troubleshooting/references/*.md`, `ai-interview-tech/references/*.md` —
    트러블슈팅·참조 기록 [미정]
  - 저장소 밖 전역 스킬(`~/.claude/skills` 에만 있는 것) — 이 저장소 관리 대상이 아님

## 문체 규칙
- 종결: `~한다/~이다` → `~해/~야/~돼`, 금지는 `~하지 마`, 강조는 `**절대 ~하지 마**`
- 공식 용어는 그대로 (`frontmatter`, `surface`, `pixel_frame`, `Definition of Done` …)
- 왜 그런지 설명하는 문장은 지우지 말고 말투만 바꿔. 근거가 이 저장소 규칙의 핵심이다
- 표 셀·목록 항목의 명사형 종결(`~함`, `~확인`)은 그대로 둬도 된다
- 헤더 제목은 다른 스킬·문서가 참조하는 경우 그대로 둔다 (예: ai-interview-tech 의
  `결정 스펙을 영속화한다` 절은 ai-plan-docs 가 이름으로 가리킨다)
- 과한 구어(`ㄱㄱ`, 이모지, 감탄)는 쓰지 않는다

## 완료 조건 (Definition of Done)
- [ ] 15개 파일 본문이 반말 대화체로 바뀜
- [ ] 15개 파일 모두 frontmatter diff 0 (`git diff` 로 확인)
- [ ] 15개 파일 모두 코드 블록 diff 0 (변경 전후 fenced block 추출해 비교)
- [ ] 다른 문서가 참조하는 헤더 이름이 깨지지 않음 (`grep` 으로 교차 확인)
- [ ] 파일마다 원본과 나란히 읽어 규칙·조건·숫자가 빠지거나 바뀐 게 없음
- [ ] `./bin/install.sh --check` 결과가 작업 전과 같음

## 인터페이스 / 데이터 형식
없음. 텍스트만 바뀐다.

## 의존성
- 사전 작업: 없음 (`ai-plan-docs` 는 이미 완료)

## 비고
- 다른 세션이 같은 파일을 동시에 고칠 수 있어서 파일 단위로 커밋·푸시한다. 충돌 범위를 줄이려고.
- `cmux-where` 는 자동 호출 예외 스킬이라 description 의 트리거·비트리거 문구가 특히 중요하다.
  frontmatter 제외 규칙으로 보호된다.
