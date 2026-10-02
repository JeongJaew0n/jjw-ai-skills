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

`/vscode-vsix-local-deployment` 나 `$vscode-vsix-local-deployment` 로 불렀을 때만 돌려.
이름만 나왔거나 VSIX 작업이랑 비슷해 보인다고 알아서 집어 들지 마.

## 결과

VSIX 하나를 VS Code CLI의 `--install-extension ... --force`로 설치하고,
`--list-extensions --show-versions`에서 같은 확장 ID와 버전이 보여야 완료야.
열려 있는 VS Code 창은 알아서 재시작하거나 건드리지 마.

## 인자

- 첫 번째 위치 인자: 확장 저장소 또는 `.vsix` 파일. 생략하면 현재 디렉터리.
- `--build`: 저장소의 패키징 스크립트로 새 VSIX를 만든 뒤 설치.
- `--cli <명령/경로>`: 설치 대상 VS Code CLI를 직접 지정. Insiders나 다른 배포판은
  사용자가 꼭 이 옵션으로 지정했을 때만 대상으로 삼아.
- `--dry-run`: CLI·VSIX·manifest·호환성만 검사하고 설치는 안 함.

## 실행 절차

### 1. 입력 확정

`.vsix`를 직접 받았으면 그대로 써. 저장소를 받았으면 루트 `package.json`의 `publisher`,
`name`, `version`, `engines.vscode`부터 확인해. 이 필드가 없으면 VS Code 확장 저장소라고
추측하지 말고 멈춰.

저장소에 정확히 `artifacts/<name>-<version>.vsix`가 있으면 그게 기본 산출물이야.
그 파일이 없는데 VSIX가 여러 개 있으면 최신 걸 마음대로 고르지 말고 사용자한테 파일을
지정해달라고 해. 버전이나 배포판이 서로 다를 수 있거든.

### 2. 필요할 때만 패키징

`--build`가 있거나 설치할 VSIX가 없으면 `package.json`의 `package:vsix` 스크립트를
먼저 써. 그게 없다고 `npx vsce package`를 즉석에서 만들지 말고, 저장소가 제공하는
패키징 절차를 확인해. 패키지 매니저는 락 파일에 맞는 걸, Node는 저장소가 요구하는 버전을 써.

패키징이 실패하면 바로 멈춰. 예전 VSIX를 대신 설치해놓고 성공한 것처럼 보고하지 마.
VSIX 파일을 직접 받은 경우엔 소스 저장소를 다시 빌드하지 마.

### 3. 설치 및 검증

`SKILL_DIR`은 이 `SKILL.md`가 있는 디렉터리야. 아래 스크립트를 돌려.

```bash
"$SKILL_DIR/bin/vsix-install.sh" \
  "<확장 레포 또는 VSIX>" \
  [--cli "<VS Code CLI>"] \
  [--dry-run]
```

스크립트가 보장하는 건 이거야.

- 기본 대상은 PATH의 `code`, 없으면 macOS 기본 Visual Studio Code 앱 번들의 CLI.
- VSIX 안의 `extension/package.json`에서 ID·버전·`engines.vscode`를 직접 읽어.
- 로컬 VS Code가 manifest의 최소 버전보다 낮으면 설치 전에 멈춰.
- 같은 ID가 이미 설치돼 있으면 `--force`로 갱신하되, 사용자 설정은 안 지워.
- 명령이 성공했다는 것만 믿지 않고, 설치 목록에서 정확히 `publisher.name@version`을 확인해.

CLI가 없으면 VS Code의 **Shell Command: Install 'code' command in PATH**를 안내하거나,
실제 앱 번들 경로를 `--cli`로 받아. VS Code 버전이 낮으면 앱 업데이트가 필요하다고
보고해. 호환성 맞추겠다고 확장의 `engines.vscode`를 알아서 낮추지 마.

### 4. 보고

설치한 VSIX, 대상 CLI와 VS Code 버전, 검증된 확장 ID·버전을 짧게 보고해. 열린 창에는
`Developer: Reload Window`나 재실행이 필요하다고 알려줘. 이 스킬은 Marketplace 게시,
GitHub Release, 태그 생성, 대상 저장소 커밋·푸시는 안 해.
