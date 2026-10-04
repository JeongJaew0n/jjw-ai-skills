# hud

Claude Code 상태줄 HUD예요.

```
repo:some-repo  branch:main  ~/Dev/some-repo/src/panel
Opus 5 high | ctx:43% | 5h:18%(3h1m) wk:63%(9/8(화) 23:10) | $8.25 | 3h32m | +231/-47
```

## 설계 원칙

이 네 가지가 이 제품의 전부예요.

| 원칙 | 이유 |
| --- | --- |
| **의존성 0** | Node 내장 모듈(`node:fs`, `node:path`)만 쓴다. `npm install` 이 없다 |
| **spawn 0** | 브랜치를 `git` 호출 대신 `.git/HEAD` 를 직접 읽어 얻는다. 상태줄은 렌더마다 실행되므로 프로세스 생성 비용이 누적된다 |
| **MCP 0** | MCP 서버가 없다. 죽을 프로세스가 없다 |
| **자격증명 접근 0** | rate limit·비용은 Claude Code 가 stdin 으로 그대로 준다. 어디에도 로그인하지 않는다 |

여기에 실패 정책이 하나 더 붙어요. **어떤 필드가 없어도 그 항목만 빠지고 나머지는 그려요. 예외가 나면 아무것도 출력하지 않아요.** 깨진 상태줄보다 없는 상태줄이 나으니까요.

## 요구사항

| 항목 | 요구 | 확인 |
| --- | --- | --- |
| Node | **14 이상** | `bin/hud.mjs` 가 optional chaining(`?.`)과 nullish(`??`)를 쓴다 |
| 셸 | POSIX `sh` | 런처가 `#!/bin/sh` + `env -u` |
| 플랫폼 | **macOS / Linux / WSL** | native Windows 는 `/bin/sh` 가 없어 동작하지 않는다 |

**`node` 는 따로 설치돼 있어야 해요.** Claude Code 는 단일 실행 바이너리라서, Claude Code 가 돌아간다고 `node` 가 있다는 보장은 없어요.

`node` 가 없으면 런처는 **조용히 물러나요** — 상태줄 항목만 사라지고 에러는 드러나지 않아요. 확인하려면:

```sh
command -v node || echo "node 없음 — HUD 는 아무것도 그리지 않는다"
```

`plugin.json` 에는 이 제약을 적을 표준 필드가 없어요 (`engines` / `platforms` / `os` 는 Claude Code 가 인식하지 않아서 `claude plugin validate --strict` 에서 경고가 나요). 그래서 여기와 런처 헤더에 적어 뒀어요.

## 설치

이 저장소가 `~/.claude/skills/` 에 설치되면 `hud` 는 `hud@skills-dir` 로 자동 로드돼요. 따로 설치 명령은 없어요.

**심볼릭 링크로도 동작해요** (2026-09-01 확인).

```
$ ls -la ~/.claude/skills/hud
hud -> /path/to/jjw-ai-skills/skills/hud

$ claude plugin list
Skills-directory plugins (.claude/skills/*):
  ❯ hud@skills-dir   Version: 0.4.1   Status: ✔ loaded
```

링크로 설치하면 `git pull` 이 바로 반영돼요. 자동 로드는 **다음 세션부터** 걸려요.

상태줄을 켜려면 **한 번만** 실행하세요.

```
/hud:setup
```

### 왜 setup 을 따로 실행해야 하나

**플러그인은 `statusLine` 을 등록할 수 없어요.** Claude Code 에서 플러그인이 제공할 수 있는 컴포넌트는 `commands / agents / skills / hooks / mcpServers / lspServers` 뿐이고, `statusLine` 은 settings 전용 키예요. 공식 `/statusline` 커맨드조차 `~/.claude/settings.json` 을 직접 고치는 방식으로 동작해요.

그래서 `/hud:setup` 이 `settings.json` 의 `statusLine` 을 런처 경로로 병합해요. 여러 번 돌려도 결과가 같고, 고치기 전에 백업하며, 다른 `statusLine` 이 이미 설정돼 있으면 확인 없이 덮어쓰지 않아요.

## 업데이트

```
git pull
```

이게 끝이에요. `~/.claude/skills/hud/` 는 버전 해시가 없는 안정 경로라서 `settings.json` 이 그 경로를 **직접** 가리켜요. 파일이 갱신되면 다음 렌더부터 새 코드가 돌아요.

마켓플레이스로 설치했다면 캐시 경로에 버전 해시가 박히기 때문에(`.../hud/<해시>/`) `setup` 이 `~/.claude/hud/` 에 사본을 만들고 그쪽을 가리켜요. 이 경우에만 업데이트 후 `/hud:setup` 을 다시 실행해야 해요. 자세한 판정 기준은 `skills/setup/SKILL.md` 의 `두 가지 설치 모드` 에 있어요.

## 제거

```
/hud:setup 제거
```

`statusLine` 키만 지우고 다른 설정은 건드리지 않아요. 플러그인 파일 자체는 저장소가 관리하니까 지우지 않아요.

## 구조

```
.claude-plugin/plugin.json   매니페스트
bin/hud                      런처 (settings 가 가리키는 것)
bin/hud.mjs                  렌더러
skills/setup/SKILL.md        설치·갱신·제거
docs/payload-example.json    stdin 페이로드 예시 / 테스트 픽스처
```

### 런처가 따로 있는 이유

`settings.json` 의 `statusLine.command` 는 셸을 거쳐 실행되고, 그 셸은 부모의 `NODE_OPTIONS` 를 물려받아요. `NODE_OPTIONS=--require=<사라진 파일>` 같은 상태면 **node 가 스크립트를 읽기도 전에 `MODULE_NOT_FOUND` 로 죽고 상태줄은 빈 줄이 돼요.** 터미널 래퍼가 tmp 디렉터리에 `--require` 대상을 두는 경우, OS 가 임시파일을 청소하면서 실제로 이런 일이 생겨요.

`hud.mjs` 는 내장 모듈만 쓰니까 `NODE_OPTIONS` 로 얻을 게 없어요. 그래서 런처는 이것만 해요.

```sh
exec env -u NODE_OPTIONS node "$dir/hud.mjs"
```

## 표시 항목

왼쪽부터 순서대로, **해당 필드가 페이로드에 있을 때만** 나타나요.

| 항목 | 소스 | 임계값 |
| --- | --- | --- |
| `repo:` | `workspace.repo.name` | 경로의 마지막 조각과 같으면 **생략** |
| `branch:` | `.git/HEAD` 직접 읽기 | — |
| 실행 경로 | `workspace.current_dir` 또는 `cwd` | — |
| 모델명 | `model.display_name` | — |
| 추론 노력 | `effort.level` | 모델명 바로 뒤. `low` `medium` `high` `xhigh` `max` |
| `ctx:` | `context_window.used_percentage` | 70% 노랑 / 85% 빨강 |
| `5h:` `wk:` | `rate_limits.*.used_percentage` | 60% 노랑 / 85% 빨강 |
| 비용 | `cost.total_cost_usd` | $20 노랑 / $50 빨강 |
| 경과 시간 | `cost.total_duration_ms` | — |
| `+N/-N` | `cost.total_lines_*` | 둘 다 0이면 숨김 |

`repo:` 는 실행 경로의 마지막 조각과 이름이 같으면 그리지 않아요. 보통 레포 루트에서 돌기 때문에 그대로 두면 한 줄에 같은 이름이 두 번 나오거든요. 하위 디렉터리·워크트리처럼 마지막 조각이 다르면 레포 이름이 정보가 되니까 남겨요.

임계값은 `bin/hud.mjs` 상단 `CONFIG` 에서 조정해요.

추론 노력(`high` 같은 것)은 모델명 바로 뒤에 붙어요. Claude Code 가 **effort 를 지원하는 모델일 때만** 이 값을 보내기 때문에, 지원하지 않는 모델에서는 모델명만 보여요. `/effort` 로 바꾸면 다음 렌더에 바로 반영돼요.

실행 경로는 홈 아래면 `~` 로 줄여요(`$HOME` 이 없으면 절대 경로 그대로). **파일시스템을 확인하지 않는 순수 문자열 변환이라서, 경로가 실제로 없어도 그려져요** — `branch:` 와 갈리는 지점이에요. 상태줄이 알려주려는 건 "어디서 돌고 있다고 보고받았는가" 이지, 그 경로가 지금 존재하는지가 아니에요.

`5h:` 뒤의 괄호는 **리셋까지 남은 시간**(`3h1m`), `wk:` 뒤의 괄호는 **리셋되는 절대 시각**이에요. 5시간 창은 몇 시간 뒤라 남은 시간이 직관적이고, 7일 창은 며칠 뒤라 시각이 직관적이어서 표기를 다르게 뒀어요. `wk:` 는 오늘 안이면 `23:10`, 다른 날이면 `9/8(화) 23:10` 처럼 날짜와 요일을 붙여요.

`resets_at` 이 절대 epoch 초라서, **이미 지난 시각이면 이 괄호만 빠져요.** `docs/payload-example.json` 의 값도 시간이 지나면 과거가 되기 때문에, 픽스처의 렌더 결과는 실행 시점에 따라 달라져요.

## 색상

`NO_COLOR` 규약을 따라요. 이 환경변수가 설정돼 있으면 ANSI 코드 없이 평문만 출력해요.

## 직접 실행

상태줄은 stdin 으로 JSON 을 받아 stdout 으로 텍스트를 내는 계약이에요. 그래서 셸에서 그대로 돌려볼 수 있어요.

```sh
jq -c . docs/payload-example.json | ./bin/hud | cat -v
```

픽스처의 `cwd` 는 실제로 없는 경로라서 `branch:` 항목은 빠져요. 이게 정상 동작이에요 — 필드를 얻을 수 없으면 그 항목만 사라져요. **실행 경로는 같은 조건에서도 그려져요** — 파일시스템을 보지 않으니까요. 픽스처의 홈이 실행 환경의 `$HOME` 과 다르기 때문에 `~` 축약 없이 절대 경로로 나와요.

깨진 `NODE_OPTIONS` 아래에서도 같은 출력이 나와야 해요.

```sh
jq -c . docs/payload-example.json | NODE_OPTIONS="--require=/nonexistent.cjs" ./bin/hud
```

`node` 가 없는 환경에서는 stdout·stderr 가 모두 비어 있고 종료 코드가 0이어야 해요.

```sh
jq -c . docs/payload-example.json | env PATH=/usr/bin:/bin ./bin/hud; echo "rc=$?"
```

리셋 표기(`5h:` `wk:` 뒤의 괄호)까지 확인하려면 `resets_at` 을 미래 시각으로 바꿔 넣으세요.

```sh
jq -c --argjson now "$(date +%s)" \
  '.rate_limits.five_hour.resets_at=($now+13800) | .rate_limits.seven_day.resets_at=($now+241200)' \
  docs/payload-example.json | ./bin/hud | cat -v
```

**픽스처의 `resets_at` 은 일부러 절대 epoch 로 남겨 뒀어요.** Claude Code 가 실제로 보내는 형태가 그거라서, 계약 문서로서는 절대값이 정확해요. 대신 시간이 지나면 그 값이 과거가 돼서 리셋 표기 분기를 지나지 않으니까, **렌더 회귀를 볼 때는 위 갱신 원라이너를 쓰세요.** 픽스처를 동적 생성으로 바꾸지 않은 건, 정적 파일이 실행물이 되면서 "의존성 0" 원칙과 어긋나기 때문이에요.

## 아직 안 된 것

- **사본 모드 미검증** — `skills/setup/SKILL.md` 의 사본 모드는 마켓플레이스 설치를 전제하는데, 그 경로가 아직 없어서 한 번도 실행된 적이 없어요
- **마켓플레이스 배포** — `.claude-plugin/marketplace.json` 이 없어요. 지금 배포 경로는 이 저장소뿐이에요
- **LICENSE** — 미정
- **설정 외부화** — 임계값이 `bin/hud.mjs` 소스에 있어요. `~/.claude/hud/config.json` 으로 뺄지 미정
