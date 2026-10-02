---
name: obsidian-plugin-local-deployment
description: |
  직접 만든 Obsidian 커스텀 플러그인을 이 컴퓨터에 설치된 Obsidian vault 의
  플러그인 폴더로 배포한다. 첫 실행 때 vault 경로를 자동 탐지하거나 사용자에게
  받아 config.json 에 저장해 두고, 이후에는 저장된 경로로 바로 배포한다.
  사용자가 `/obsidian-plugin-local-deployment` 또는
  `$obsidian-plugin-local-deployment` 를 명시적으로 호출했을 때만 사용한다.
  Obsidian·플러그인·배포 요청이 관련 분야에 해당한다는 이유만으로 자동 사용하지 않는다.
user-invocable: true
disable-model-invocation: true
argument-hint: "[플러그인 레포 경로] [--vault <이름>] [--reconfigure] [--dry-run]"
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
  - Glob
  - AskUserQuestion
---

# /obsidian-plugin-local-deployment — 로컬 Obsidian 에 커스텀 플러그인 배포

## 활성화 조건

`/obsidian-plugin-local-deployment` 나 `$obsidian-plugin-local-deployment` 로 불렀을 때만 돌려. 이름만 나온 건 호출이 아니야 — `disable-model-invocation` 이 그 경로를 막으니까, 실행하지 말고 슬래시로 불러달라고 안내해. Obsidian 이나 플러그인 배포 얘기가 나왔다고 알아서 집어 들지 마.

## 뭐 하는 스킬이냐면

Obsidian 플러그인엔 **레지스트리도 설치 명령도 없어.** `main.js` · `manifest.json` · `styles.css` 세 파일을 `<vault>/.obsidian/plugins/<plugin-id>/` 에 갖다 놓으면 그게 설치야. 그래서 개발하다 보면 매번 같은 경로로 같은 파일을 복사하게 되는데, 이 스킬이 그 반복을 없애줘.

단계는 두 개야.

| 단계 | 하는 일 | 언제 |
|---|---|---|
| **설정** | vault 의 플러그인 폴더 경로를 찾아 `config.json` 에 저장 | 최초 1회 (또는 `--reconfigure`) |
| **배포** | 빌드 → 세 파일 복사 → 리로드 안내 | 호출할 때마다 |

## 파일 배치

```
<이 스킬 폴더>/
├── SKILL.md
├── bin/
│   ├── obsidian-vaults.sh    # vault 탐지 (obsidian.json 파싱)
│   └── obsidian-deploy.sh    # 실제 복사 (안전 가드 포함)
└── config.json               # 저장된 vault 경로 (런타임에 생성, git 추적 안 함)
```

**`config.json` 은 이 컴퓨터 전용이야.** 저장소엔 커밋하지 마 (`.gitignore` 처리돼 있어). 스킬을 재설치해서 파일이 사라지면 아래 "1. 설정" 이 다시 돌면서 새로 만들어져.

`SKILL_DIR` 은 이 `SKILL.md` 가 있는 디렉터리야. 전역 설치본이면 보통 `~/.claude/skills/obsidian-plugin-local-deployment`. 아래 명령의 `$SKILL_DIR` 은 실제 경로로 바꿔서 써.

## 실행 절차

### 1. 설정 — vault 경로 확보

`$SKILL_DIR/config.json` 이 있고 `--reconfigure` 가 없으면 **이 단계는 통째로 건너뛰어.** 단, 저장된 `pluginsDir` 이 실제로 있는지만 확인해. 없어졌으면 (vault 이동·삭제·외장 디스크 미연결) 사용자한테 알리고 재탐지로 넘어가.

없으면 탐지해.

```bash
"$SKILL_DIR/bin/obsidian-vaults.sh"
```

Obsidian 이 열어본 vault 를 기록해 두는 `obsidian.json` 을 읽어서 이렇게 출력해.

```
<vault경로>	<플러그인디렉터리>	<플러그인디렉터리 존재여부>
```

결과에 따라 갈려.

- **1개** → 그대로 써. 사용자한테 경로를 보여주고 확인만 받아.
- **2개 이상** → `AskUserQuestion` 으로 배포 대상을 고르게 해. 여러 개를 상시 대상으로 쓰고 싶다면 복수 선택을 허용하고 그중 기본값을 정해.
- **0개 또는 스크립트 실패** → **추측하지 말고 사용자한테 물어.** vault 경로나 플러그인 폴더 경로를 직접 받아. 홈 디렉터리를 뒤져서 `.obsidian` 을 찾는 식의 전수 탐색은 하지 마 — 느리고, 백업본이나 동기화 사본을 진짜 vault 로 착각해.

플러그인 디렉터리 존재여부가 `no` 면 그 vault 는 커뮤니티 플러그인을 한 번도 설치한 적이 없다는 뜻이야. 경로 자체는 유효하니까 `mkdir -p` 로 만들어도 되지만, **만들기 전에 이 vault 가 맞는지 사용자 확인을 받아.**

확정한 내용을 저장해.

```json
{
  "version": 1,
  "vaults": [
    {
      "name": "<사람이 알아볼 짧은 이름>",
      "path": "<vault 루트>",
      "pluginsDir": "<vault 루트>/.obsidian/plugins",
      "default": true
    }
  ]
}
```

`default: true` 는 정확히 하나여야 해. `name` 은 사용자가 `--vault <이름>` 으로 지목할 때 쓰는 키야.

### 2. 배포할 플러그인 레포 확정

인자로 경로가 왔으면 그걸 써. 없으면 현재 작업 디렉터리를 후보로 봐.

**Obsidian 플러그인 레포인지 확인해.** 판정 기준은 루트의 `manifest.json` 이고, 그 안에 `id` 랑 `minAppVersion` 이 있으면 확실해. 아니면 멈추고 사용자한테 경로를 물어. 엉뚱한 디렉터리를 플러그인으로 착각해서 배포하지 마.

`manifest.json` 의 `id` 가 배포될 폴더명이 돼. 이 값을 사용자한테 보여줘 — 대상 폴더가 여기서 정해지니까, 사용자가 틀린 걸 알아챌 수 있는 마지막 지점이야.

### 3. 빌드

`main.js` 는 빌드 산출물이야. **소스만 고치고 빌드 안 한 채 배포하면 이전 버전이 그대로 복사되는데, 이게 이 작업에서 제일 흔한 실패야.** 배포는 성공했다고 나오고 동작만 예전 거라서 원인 찾는 데도 오래 걸려.

그래서 빌드는 건너뛰지 마.

1. `package.json` 에 `build` 스크립트가 있는지 봐.
2. 아래 중 하나면 빌드해.
   - `main.js` 가 없다
   - `main.js` 가 `src/` · `*.ts` · `*.tsx` 등 소스 파일보다 오래됐다
3. 패키지 매니저는 락 파일로 판별해 — `pnpm-lock.yaml` → pnpm, `yarn.lock` → yarn, `bun.lockb` → bun, 그 외 `package-lock.json` → npm.
4. **빌드가 실패하면 거기서 멈춰.** 실패한 빌드의 낡은 `main.js` 를 배포하는 게 이 스킬이 저지를 수 있는 최악의 결과야. 실패 로그는 그대로 사용자한테 보여줘.

`build` 스크립트가 없고 `main.js` 만 있는 레포(빌드 없이 순수 JS로 쓴 플러그인)면 그대로 진행해.

### 4. 복사

```bash
"$SKILL_DIR/bin/obsidian-deploy.sh" \
  --src "<플러그인 레포>" \
  --plugins-dir "<config 의 pluginsDir>"
```

옵션:

| 옵션 | 용도 |
|---|---|
| `--dry-run` | 복사하지 않고 대상 경로와 파일 목록만 출력 |
| `--id <id>` | `manifest.json` 의 `id` 대신 쓸 폴더명 |
| `--hotreload` | 대상에 `.hotreload` 생성 (아래 "리로드" 참조) |

스크립트가 보장하는 것:

- **대상 폴더를 통째로 지우지 않아.** `main.js` · `manifest.json` · `styles.css` 만 덮어써.
- **`data.json` 은 안 건드려.** 그건 사용자가 플러그인 설정 화면에서 저장한 값이야. 배포할 때마다 설정이 초기화되면 아무도 안 써.
- 덮어쓰기 전에 대상에 있던 플러그인 이름·버전을 출력해.
- 대상의 이름이 다르면 경고해. 같은 `id` 를 쓰는 다른 플러그인일 수 있거든.
- `plugins` 디렉터리가 없으면 만들지 않고 멈춰. 경로가 틀렸을 때 vault 밖에 폴더를 만들어버리는 걸 막으려고.

사용자가 `--dry-run` 을 줬으면 여기서 끝내고 결과만 보고해.

### 5. 리로드 안내

**복사만으론 Obsidian 에 반영이 안 돼.** Obsidian 은 플러그인 코드를 시작할 때 한 번 읽고 캐시하거든. 배포 직후엔 꼭 아래 중 하나를 안내해.

| 방법 | 절차 |
|---|---|
| 플러그인 토글 | 설정 → 커뮤니티 플러그인 → 해당 플러그인 껐다 켜기 |
| Obsidian 재시작 | 앱 종료 후 재실행 |
| Hot-Reload 플러그인 | pjeby/obsidian-hot-reload 설치 시 `main.js` 변경을 감지해 자동 리로드 |

vault 에 hot-reload 가 설치돼 있는지는 이렇게 확인해.

```bash
ls -d "<pluginsDir>/hot-reload" 2>/dev/null
```

있으면 `--hotreload` 를 붙여서 배포하고, 자동으로 리로드된다고 안내해. 없으면 토글을 안내해. **hot-reload 를 사용자 동의 없이 설치하지 마.**

**새로 배포한 플러그인(vault 에 처음 올라간 id)이면** 토글이 아니라 다른 안내가 필요해. Obsidian 이 목록을 새로 읽어야 보이니까, 설정 → 커뮤니티 플러그인에서 새로고침한 다음 **활성화**해야 해.

### 6. 보고

이렇게 짧게 보고해.

```
My Test Plugin (my-test-plugin) v1.3.0
  빌드: npm run build (2.1s)
  배포: /Users/me/vault/.obsidian/plugins/my-test-plugin
        main.js, manifest.json, styles.css
  반영: 설정 → 커뮤니티 플러그인 → My Test Plugin 껐다 켜기
```

빌드를 건너뛰었으면 **그 사실과 이유를 꼭 적어** ("main.js 가 소스보다 최신이라 빌드 생략"). 사용자가 "고친 게 반영 안 됐다" 고 할 때 제일 먼저 의심할 지점이야.

## 동작 원칙

- **vault 를 추측하지 마.** `obsidian.json` 에 없으면 사용자한테 물어. 홈 디렉터리 전수 탐색은 동기화 사본·백업본을 진짜 vault 로 착각하고, 그 결과는 엉뚱한 폴더에 쓰는 거야.
- **`data.json` 은 보존해.** 예외 없어. 사용자가 명시적으로 초기화를 요청했을 때만 지워.
- **대상 폴더를 재귀 삭제하지 마.** 이 스킬에서 `rm -rf "$TARGET"` 은 금지야. 이름을 아는 파일만 덮어써. vault 엔 사용자 노트 전체가 들어 있고, 경로 변수가 비어 있을 때의 `rm -rf` 는 되돌릴 수 없어.
- **빌드가 실패하면 배포하지 마.** 낡은 산출물을 성공이라고 보고하느니 실패를 보고하는 게 나아.
- **`config.json` 은 갱신할 수 있어야 해.** vault 를 옮겼거나 새 vault 를 추가하면 `--reconfigure` 로 다시 잡아. 저장된 경로가 더 이상 없으면 조용히 넘어가지 말고 재설정을 제안해.
- **여러 vault 배포는 명시적으로만.** `config.json` 에 vault 가 여러 개 있어도 기본은 `default: true` 한 곳이야. 전체 배포는 사용자가 요청했을 때만 해.
- **커밋·푸시는 안 해.** 이 스킬은 로컬 배포까지야. 릴리스(태그·`versions.json`·GitHub Release)는 범위 밖이고, 사용자가 따로 시킬 때 처리해.

## 자주 나오는 상황

| 증상 | 원인 | 대응 |
|---|---|---|
| 배포했는데 동작이 그대로 | 리로드 안 함 | 5단계 안내 |
| 배포했는데 동작이 그대로 (리로드 했는데도) | 빌드 안 함 | 3단계 재확인, `main.js` 타임스탬프 확인 |
| 플러그인 목록에 안 보임 | 신규 배포 후 미활성화 | 설정에서 새로고침 후 활성화 |
| 설정이 초기화됨 | `data.json` 유실 | 이 스킬은 보존한다. 다른 경로로 지워졌는지 확인 |
| `plugins` 디렉터리 없음 | vault 경로 오류 또는 커뮤니티 플러그인 미사용 vault | 경로 재확인 후 사용자 동의하에 생성 |
