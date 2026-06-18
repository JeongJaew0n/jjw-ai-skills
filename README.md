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

## 설치

별도 스크립트 없음. Claude에게 맡긴다.

> 이 repo의 스킬을 `~/.claude/skills/`에 설치해줘
