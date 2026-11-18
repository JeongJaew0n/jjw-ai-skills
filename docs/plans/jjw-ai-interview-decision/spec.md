# spec — jjw-ai-interview-decision

## 목표
`ai-interview-tech` 를 `jjw-ai-interview-decision` 으로 이름을 바꾸고 본문을 새로 쓴다.
새 본문은 2026-11-17~18 DevOpsit NPT-1917 설계에서 쓴 방식을 따른다.

- 질문 라벨링: 영역 문자 + 번호(`Q-A1`), 우선순위 `P1`/`P2`/`P3`
- 문서 설계: 계획서(맥락별 설계) · 결정-질문(질문과 결정 칸) · 맥락노트(결정 로그) · 체크리스트(Phase)
- 단계 나누기: 큰 맥락 지도 → 맥락별 설계 → 질문 추출 → P1 부터 하나씩 결정 → 기록 → 구현 Phase

## 범위
- `skills/ai-interview-tech/` → `skills/jjw-ai-interview-decision/` (git mv, 기록 문서 보존)
- `SKILL.md` 새로 작성, `references/document-templates.md` 신설, `references/decision-axes.md` 유지
- 참조 갱신: `README.md` 표, `ai-plan-docs` 연동 절, `review-code-intent` 인터뷰 산출물 절
- 설치 링크: 옛 링크 2개(`~/.claude/skills`, `~/.codex/skills`) 제거, `bin/install.sh` 로 새 링크

## 완료 조건
- frontmatter 가 AGENTS.md 규칙(`user-invocable: true`, `disable-model-invocation: true`, 권장 description)을 따른다
- 저장소 안에 `ai-interview-tech` 를 가리키는 살아 있는 참조가 없다(과거 기록 문서 제외)
- `bin/install.sh --check` 가 새 이름을 `이미 연결됨` 으로 보여준다
