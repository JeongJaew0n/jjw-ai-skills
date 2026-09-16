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
| [obsidian-plugin-local-deployment](skills/obsidian-plugin-local-deployment/) | 직접 만든 Obsidian 커스텀 플러그인을 로컬 vault 의 `.obsidian/plugins/` 로 배포. vault 경로를 최초 1회 탐지해 저장하고, 이후 빌드 → 복사 → 리로드 안내까지 처리 |
| [vscode-vsix-local-deployment](skills/vscode-vsix-local-deployment/) | 로컬 VS Code 확장 저장소나 VSIX를 `code --install-extension`으로 설치하고 manifest 호환성과 실제 설치 ID·버전을 검증 |
| [cmux-where](skills/cmux-where/) | cmux 세션이 자기 위치(workspace·pane·surface 와 좌/우/상/하)와 형제 터미널 지도를 파악. `pane.list` 의 `pixel_frame` 으로 판정해 `cmux tree` 의 index 순서 오독을 막는다. **이 저장소에서 유일하게 자동 호출을 허용** ([근거](AGENTS.md)) |
| [ai-skill-integration](skills/ai-skill-integration/) | Claude 와 Codex 에 흩어진 스킬을 대조해 어느 쪽이 최신인지 근거와 함께 보고하고, **방향을 사용자에게 물어** 맞춘다. 저장소 관리분·다른 패키지·계보 충돌은 제외 |
| [chrome-extension-ai-guidance](skills/chrome-extension-ai-guidance/) | Chrome 팀의 "코딩 에이전트로 확장 프로그램 빌드" 가이드를 **매번 원문으로 받아** 이 프로젝트에 도입할지 축별로 판정하고 `docs/decisions/` 에 남긴다. 분석만 하고 설치하지 않는다 |
| [my-app-init](skills/my-app-init/) | 새 프로젝트 초기 세팅 — git 신원·커밋 정책·브랜치 정책을 묻고 `git config --local` 과 `CLAUDE.md` 에 고정, `docs/plans`·`docs/glossary`·`docs/troubleshootings`(project-specific·reusable) 골격 생성, 멀티 기능 제품이면 기능 묶음 단위 이름(기본 `FeatureGroup`) 확정, README·CLAUDE.md 작성 |
| [create-another-rc-session](skills/create-another-rc-session/) | Remote Control 에서 `/cd` 가 막혔을 때 대상 디렉터리에 RC 서버를 띄워 세션을 새로 만든다. 워크스페이스 신뢰 게이트 우회는 사용자 확인 필수이며 자동 로드 설정이 있는 디렉터리는 하드 거부 |
| [diagnose](skills/diagnose/) | 근본 원인을 찾고 나서 고치는 체계적 디버깅(Iron Law·5단계·3-strike 룰). gstack `investigate` 에서 프레임워크 결합을 걷어내 포팅했고, 기록 위치는 레포를 훑어 사용자에게 묻고 `CLAUDE.md` 에 고정한다 |
| [what-did-i-do-today](skills/what-did-i-do-today/) | 최근 24시간(기간 조정 가능) 사용자가 입력한 프롬프트를 모든 세션에서 모아 세션별 요약. 전사의 `origin.kind`·`promptSource` 로 직접 입력과 AI·시스템 자동 입력을 구분 |

## 설치

```bash
./bin/install.sh              # Claude Code + Codex 양쪽에 설치
./bin/install.sh --check      # 현재 상태만 점검
./bin/install.sh --dry-run    # 무엇을 할지만 출력
```

복사가 아니라 **심볼릭 링크**를 건다. 복사본은 이 저장소를 고쳐도 반영되지 않아
어느 쪽이 최신인지 알 수 없게 되는데, 실제로 그 상태가 한 번 만들어졌었다.

| 대상 | 정책이 걸리는 자리 |
|---|---|
| `~/.claude/skills/` | `SKILL.md` frontmatter 의 `disable-model-invocation` |
| `~/.codex/skills/` | `agents/openai.yaml` 의 `allow_implicit_invocation` |

Codex 는 frontmatter 를 읽지 않으므로 `agents/openai.yaml` 이 따로 필요하다.
이 파일은 `install.sh` 가 frontmatter 에서 **생성**하므로 직접 고치지 않는다.

저장소에 없는 전역 스킬은 건드리지 않고 목록만 보여준다.
