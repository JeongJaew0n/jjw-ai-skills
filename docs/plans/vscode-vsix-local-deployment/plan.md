# VSIX 로컬 배포 스킬 계획

## 목표

로컬 VS Code 확장 저장소 또는 VSIX 파일을 받아 Visual Studio Code CLI로 설치하고,
실제로 설치된 확장 ID와 버전을 검증하는 명시 호출형 스킬을 만든다.

## 범위

- `vscode-vsix-local-deployment` 스킬과 결정적 설치 스크립트 추가
- `code`가 PATH에 없을 때 macOS 기본 앱 번들의 CLI 탐지
- VSIX manifest와 로컬 VS Code 버전 호환성 사전 검사
- 기존 설치를 `--force`로 갱신하고 `--list-extensions --show-versions`로 결과 검증
- Claude Code와 Codex에 심볼릭 링크로 설치

## 완료 조건

- [x] 명시 호출 정책과 인자 계약을 문서화한다.
- [x] 실제 VSIX로 dry-run을 검증한다.
- [x] 오래된 VS Code 버전을 설치 전에 차단한다.
- [x] 저장소 README의 스킬 목록을 갱신한다.
- [x] 스킬 validator와 설치 상태 점검을 통과한다.

