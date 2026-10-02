# checklist — skill-tone-casual

> 작업하면서 AI 가 순서대로 체크한다. `[x]` 는 끝난 항목이다.
> 새 항목이 생기면 맞는 단계에 끼워 넣는다.

## 0. 준비
- [x] 사용자에게 [미정] 범위 확정받기 — hud README 는 해요체로 포함, references 는 제외
- [x] 작업 전 `./bin/install.sh --check` 출력 저장 (scratchpad)
- [x] 비교 스크립트 준비 — HEAD 와 작업본의 frontmatter·코드 블록을 비교 (scratchpad/verify.py)

## 1. 변환 — 파일 하나 끝낼 때마다 검증하고 커밋·푸시
짧은 것부터 해서 문체 기준을 먼저 굳힌다.
- [x] claude-sessions (63)
- [x] vscode-vsix-local-deployment (88)
- [x] obsidian-plugin-troubleshooting (102)
- [x] cmux-appearance (109)
- [x] what-did-i-do-today (116)
- [x] ai-skill-integration (161)
- [x] chrome-extension-ai-guidance (191)
- [x] ai-interview-tech (192)
- [x] obsidian-plugin-local-deployment (199)
- [x] hud/skills/setup (199)
- [x] cmux-where (220)
- [x] create-another-rc-session (229)
- [x] diagnose (257)
- [x] my-app-init (296)
- [x] review-code-intent (394)
- [ ] hud/README.md (175) — 해요체

## 2. 검증 (파일마다)
- [ ] frontmatter diff 0
- [ ] 코드 블록 diff 0
- [ ] 원본과 나란히 읽어 규칙·조건·숫자 누락 없음
- [ ] 참조되는 헤더 이름 유지

## 3. 마무리
- [ ] 전체 `grep -rn` 으로 남은 `~한다/~이다` 종결 훑기 (템플릿·코드 블록 안은 정상)
- [ ] `./bin/install.sh --check` 작업 전과 비교
- [ ] AGENTS.md 에 "본문은 반말 대화체" 규칙 추가할지 사용자에게 확인
- [ ] 체크 안 된 항목이 남았으면 이유 메모
