# checklist — skill-tone-casual

> 작업하면서 AI 가 순서대로 체크한다. `[x]` 는 끝난 항목이다.
> 새 항목이 생기면 맞는 단계에 끼워 넣는다.

## 0. 준비
- [ ] 사용자에게 [미정] 범위(hud README, references) 확정받기
- [ ] 작업 전 `./bin/install.sh --check` 출력 저장 (scratchpad)
- [ ] 15개 파일의 frontmatter·코드 블록 원본 추출 (scratchpad, 비교용)

## 1. 변환 — 파일 하나 끝낼 때마다 검증하고 커밋·푸시
짧은 것부터 해서 문체 기준을 먼저 굳힌다.
- [ ] claude-sessions (63)
- [ ] vscode-vsix-local-deployment (88)
- [ ] obsidian-plugin-troubleshooting (102)
- [ ] cmux-appearance (109)
- [ ] what-did-i-do-today (116)
- [ ] ai-skill-integration (161)
- [ ] chrome-extension-ai-guidance (191)
- [ ] ai-interview-tech (192)
- [ ] obsidian-plugin-local-deployment (199)
- [ ] hud/skills/setup (199)
- [ ] cmux-where (220)
- [ ] create-another-rc-session (229)
- [ ] diagnose (257)
- [ ] my-app-init (296)
- [ ] review-code-intent (394)

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
