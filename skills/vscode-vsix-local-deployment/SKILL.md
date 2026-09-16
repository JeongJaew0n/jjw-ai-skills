---
name: vscode-vsix-local-deployment
description: |
  로컬 VS Code 확장 저장소의 VSIX를 Visual Studio Code CLI로 설치하고 확장 ID와
  버전을 검증한다. 사용자가 `/vscode-vsix-local-deployment` 또는
  `$vscode-vsix-local-deployment` 를 명시적으로 호출했을 때만 사용한다.
  VS Code·확장·VSIX 요청이 관련 분야에 해당한다는 이유만으로 자동 사용하지 않는다.
user-invocable: true
disable-model-invocation: true
argument-hint: "[확장 레포 또는 .vsix 경로] [--build] [--cli <명령/경로>] [--dry-run]"
allowed-tools:
  - Bash
  - Read
  - Glob
  - AskUserQuestion
---

# /vscode-vsix-local-deployment — VSIX를 로컬 VS Code에 설치

## 활성화 조건

사용자가 `/vscode-vsix-local-deployment` 또는 `$vscode-vsix-local-deployment` 로 호출한
경우에만 실행한다. 이름만 언급했거나 VSIX 작업과 유사하다는 이유로 자동 선택하지 않는다.

## 결과

VSIX 하나를 VS Code CLI의 `--install-extension ... --force`로 설치한 뒤
`--list-extensions --show-versions`에서 같은 확장 ID와 버전이 확인되어야 완료다.
열려 있는 VS Code 창은 자동으로 다시 시작하거나 조작하지 않는다.

## 인자

- 첫 번째 위치 인자: 확장 저장소 또는 `.vsix` 파일. 생략하면 현재 디렉터리.
- `--build`: 저장소의 패키징 스크립트를 실행해 새 VSIX를 만든 뒤 설치.
- `--cli <명령/경로>`: 설치 대상 VS Code CLI를 명시. Insiders나 다른 배포판은 반드시
  이 옵션으로 사용자가 지정한 경우에만 대상으로 삼는다.
- `--dry-run`: CLI·VSIX·manifest·호환성만 검사하고 설치하지 않는다.

## 실행 절차

### 1. 입력 확정

명시된 `.vsix`는 그대로 사용한다. 저장소를 받았으면 루트 `package.json`의 `publisher`,
`name`, `version`, `engines.vscode`를 확인한다. 이 필드가 없으면 VS Code 확장 저장소로
추측하지 말고 중단한다.

저장소에 정확히 `artifacts/<name>-<version>.vsix`가 있으면 기본 산출물로 사용한다.
정확한 파일이 없고 VSIX가 여러 개면 임의로 최신 파일을 고르지 말고 사용자가 파일을
지정하게 한다. 서로 다른 버전이나 배포판일 수 있기 때문이다.

### 2. 필요할 때만 패키징

`--build`가 있거나 설치 가능한 VSIX가 없으면 `package.json`의 `package:vsix` 스크립트를
우선 사용한다. 없다면 임의의 `npx vsce package`를 만들지 말고 저장소가 제공하는 패키징
절차를 확인한다. 락 파일에 맞는 패키지 매니저와 저장소가 요구하는 Node 버전을 사용한다.

패키징 실패 시 즉시 중단한다. 이전 VSIX를 대신 설치해 성공처럼 보고하지 않는다.
명시적인 VSIX 파일을 받은 경우에는 소스 저장소를 다시 빌드하지 않는다.

### 3. 설치 및 검증

`SKILL_DIR`은 이 `SKILL.md`가 있는 디렉터리다. 다음 스크립트를 실행한다.

```bash
"$SKILL_DIR/bin/vsix-install.sh" \
  "<확장 레포 또는 VSIX>" \
  [--cli "<VS Code CLI>"] \
  [--dry-run]
```

스크립트는 다음을 보장한다.

- 기본 대상은 PATH의 `code`, 그다음 macOS 기본 Visual Studio Code 앱 번들의 CLI다.
- VSIX 내부 `extension/package.json`에서 ID·버전·`engines.vscode`를 직접 읽는다.
- 로컬 VS Code가 manifest의 최소 버전보다 낮으면 설치 전에 중단한다.
- 같은 ID의 기존 설치는 `--force`로 갱신하되 사용자 설정은 지우지 않는다.
- 명령 성공만 믿지 않고 설치 목록에서 정확한 `publisher.name@version`을 확인한다.

CLI가 없으면 VS Code의 **Shell Command: Install 'code' command in PATH**를 안내하거나
실제 앱 번들 경로를 `--cli`로 받는다. VS Code 버전이 낮으면 앱 업데이트가 필요하다고
보고한다. 호환성을 맞춘다는 이유로 확장의 `engines.vscode`를 자동 하향하지 않는다.

### 4. 보고

설치한 VSIX, 대상 CLI와 VS Code 버전, 검증된 확장 ID·버전을 짧게 보고한다. 열린 창에는
`Developer: Reload Window` 또는 재실행이 필요하다고 안내한다. 이 스킬은 Marketplace 게시,
GitHub Release, 태그 생성, 대상 저장소의 커밋·푸시를 하지 않는다.

