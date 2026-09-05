# jjw-ai-skills

직접 만든 Claude Code 스킬 모음.

## 구조

```
skills/
└── <skill-name>/
    └── SKILL.md      # 스킬 1개 = 디렉터리 1개 + SKILL.md (디렉터리명 = 스킬명)
```

단계가 여러 개인 묶음 스킬은 해당 디렉터리 안에 하위 디렉터리로 중첩한다.
(Claude Code는 깊이와 무관하게 `SKILL.md`를 탐색한다.)

## 스킬 목록

| Skill | Description |
|-------|-------------|
| [ai-plan-memory](skills/ai-plan-memory/) | 작업 계획을 `docs/plans/<slug>/`에 영속 기록(spec·context·checklist)해 세션 간 재개 가능하게 함 |
| [ai-interview-tech](skills/ai-interview-tech/) | 요구사항을 바로 구현으로 넘기기 전에, 숨은 기술 결정(트랜잭션 경계·멱등성·실패 처리·호환성 등)을 코드베이스 근거로 드러내 사람과 확정 |
| [review-code-intent](skills/review-code-intent/) | PR 리뷰를 Intent Review(사람의 이해·기억용), Tech Review(구현 안전성 검증용), Intent Implementation Review(의도 달성도 측정용) 세 축으로 분리해 `docs/reviews/[PR번호] [PR이름]/`에 산출 |
| [hud](skills/hud/) | Claude Code 상태줄 HUD 플러그인 — 의존성 0·spawn 0·MCP 0. `/hud:setup` 으로 `statusLine` 을 설치한다 |
| [obsidian-plugin-local-deployement](skills/obsidian-plugin-local-deployement/) | 직접 만든 Obsidian 커스텀 플러그인을 로컬 vault 의 `.obsidian/plugins/` 로 배포. vault 경로를 최초 1회 탐지해 저장하고, 이후 빌드 → 복사 → 리로드 안내까지 처리 |

## 설치

별도 스크립트 없음. Claude에게 맡긴다.

> 이 repo의 스킬을 `~/.claude/skills/`에 설치해줘
