# hud

Claude Code 상태줄 HUD.

```
repo:some-repo  branch:main
Opus 5 | ctx:43% | 5h:18%(3h1m) wk:63%(9/8(화) 23:10) | $8.25 | 3h32m | +231/-47
```

## 설계 원칙

이 네 가지가 이 제품의 전부다.

| 원칙 | 이유 |
| --- | --- |
| **의존성 0** | Node 내장 모듈(`node:fs`, `node:path`)만 쓴다. `npm install` 이 없다 |
| **spawn 0** | 브랜치를 `git` 호출 대신 `.git/HEAD` 를 직접 읽어 얻는다. 상태줄은 렌더마다 실행되므로 프로세스 생성 비용이 누적된다 |
| **MCP 0** | MCP 서버가 없다. 죽을 프로세스가 없다 |
| **자격증명 접근 0** | rate limit·비용은 Claude Code 가 stdin 으로 그대로 준다. 어디에도 로그인하지 않는다 |

여기에 실패 정책이 하나 더 붙는다. **어떤 필드가 없어도 그 항목만 빠지고 나머지는 그린다. 예외가 나면 아무것도 출력하지 않는다.** 깨진 상태줄보다 없는 상태줄이 낫다.

## 요구사항

| 항목 | 요구 | 확인 |
| --- | --- | --- |
| Node | **14 이상** | `bin/hud.mjs` 가 optional chaining(`?.`)과 nullish(`??`)를 쓴다 |
| 셸 | POSIX `sh` | 런처가 `#!/bin/sh` + `env -u` |
| 플랫폼 | **macOS / Linux / WSL** | native Windows 는 `/bin/sh` 가 없어 동작하지 않는다 |

**`node` 는 별도로 설치돼 있어야 한다.** Claude Code 는 단일 실행 바이너리라서, Claude Code 가 돌아간다는 사실이 `node` 의 존재를 보장하지 않는다.

`node` 가 없으면 런처는 **조용히 물러난다** — 상태줄 항목만 사라지고 에러는 표면화되지 않는다. 확인하려면:

```sh
command -v node || echo "node 없음 — HUD 는 아무것도 그리지 않는다"
```

`plugin.json` 에는 이 제약을 적을 표준 필드가 없다 (`engines` / `platforms` / `os` 는 Claude Code 가 인식하지 않아 `claude plugin validate --strict` 에서 경고가 된다). 그래서 여기와 런처 헤더에 적어 둔다.

## 설치

이 저장소가 `~/.claude/skills/` 에 설치되면 `hud` 는 `hud@skills-dir` 로 자동 로드된다. 별도 설치 명령이 없다.

**심볼릭 링크도 동작한다** (2026-09-01 확인).

```
$ ls -la ~/.claude/skills/hud
hud -> /path/to/jjw-ai-skills/skills/hud

$ claude plugin list
Skills-directory plugins (.claude/skills/*):
  ❯ hud@skills-dir   Version: 0.2.0   Status: ✔ loaded
```

링크로 설치하면 `git pull` 이 곧바로 반영된다. 자동 로드는 **다음 세션부터** 걸린다.

상태줄을 켜려면 **한 번** 실행한다.

```
/hud:setup
```

### 왜 setup 을 따로 실행해야 하나

**플러그인은 `statusLine` 을 등록할 수 없다.** Claude Code 에서 플러그인이 제공할 수 있는 컴포넌트는 `commands / agents / skills / hooks / mcpServers / lspServers` 뿐이고, `statusLine` 은 settings 전용 키다. 공식 `/statusline` 커맨드조차 `~/.claude/settings.json` 을 직접 편집하는 방식으로 동작한다.

그래서 `/hud:setup` 이 `settings.json` 의 `statusLine` 을 런처 경로로 병합한다. 멱등하고, 편집 전 백업하며, 남이 설정한 `statusLine` 이 이미 있으면 확인 없이 덮어쓰지 않는다.

## 업데이트

```
git pull
```

끝이다. `~/.claude/skills/hud/` 는 버전 해시가 없는 안정 경로이므로 `settings.json` 이 그 경로를 **직접** 가리킨다. 파일이 갱신되면 다음 렌더부터 새 코드가 돈다.

마켓플레이스로 설치한 경우에는 캐시 경로에 버전 해시가 박히므로(`.../hud/<해시>/`) `setup` 이 `~/.claude/hud/` 로 사본을 만들고 그쪽을 가리킨다. 그 경우에만 업데이트 후 `/hud:setup` 재실행이 필요하다. 자세한 판정 기준은 `skills/setup/SKILL.md` 의 `두 가지 설치 모드`.

## 제거

```
/hud:setup 제거
```

`statusLine` 키만 삭제하고 다른 설정은 건드리지 않는다. 플러그인 파일 자체는 저장소가 관리하므로 지우지 않는다.

## 구조

```
.claude-plugin/plugin.json   매니페스트
bin/hud                      런처 (settings 가 가리키는 것)
bin/hud.mjs                  렌더러
skills/setup/SKILL.md        설치·갱신·제거
docs/payload-example.json    stdin 페이로드 예시 / 테스트 픽스처
```

### 런처가 따로 있는 이유

`settings.json` 의 `statusLine.command` 는 셸을 거쳐 실행되고, 그 셸은 부모의 `NODE_OPTIONS` 를 물려받는다. `NODE_OPTIONS=--require=<사라진 파일>` 같은 상태면 **node 는 스크립트를 읽기도 전에 `MODULE_NOT_FOUND` 로 죽고 상태줄은 빈 줄이 된다.** 터미널 래퍼가 tmp 디렉터리에 `--require` 대상을 두는 경우 OS 의 임시파일 청소로 실제 발생한다.

`hud.mjs` 는 내장 모듈만 쓰므로 `NODE_OPTIONS` 가 줄 이득이 없다. 런처는 그래서 이렇게만 한다.

```sh
exec env -u NODE_OPTIONS node "$dir/hud.mjs"
```

## 표시 항목

왼쪽부터, **해당 필드가 페이로드에 있을 때만** 나타난다.

| 항목 | 소스 | 임계값 |
| --- | --- | --- |
| `repo:` | `workspace.repo.name` | — |
| `branch:` | `.git/HEAD` 직접 읽기 | — |
| 모델명 | `model.display_name` | — |
| `ctx:` | `context_window.used_percentage` | 70% 노랑 / 85% 빨강 |
| `5h:` `wk:` | `rate_limits.*.used_percentage` | 60% 노랑 / 85% 빨강 |
| 비용 | `cost.total_cost_usd` | $20 노랑 / $50 빨강 |
| 경과 시간 | `cost.total_duration_ms` | — |
| `+N/-N` | `cost.total_lines_*` | 둘 다 0이면 숨김 |

임계값은 `bin/hud.mjs` 상단 `CONFIG` 에서 조정한다.

`5h:` 뒤의 괄호는 **리셋까지 남은 시간**(`3h1m`), `wk:` 뒤의 괄호는 **리셋되는 절대 시각**이다. 5시간 창은 몇 시간 뒤라 남은 시간이 직관적이고, 7일 창은 며칠 뒤라 시각이 직관적이라서 표기를 다르게 뒀다. `wk:` 는 오늘 안이면 `23:10`, 다른 날이면 `9/8(화) 23:10` 처럼 날짜와 요일을 붙인다.

`resets_at` 이 절대 epoch 초라서, **이미 지난 시각이면 이 괄호만 빠진다.** `docs/payload-example.json` 의 값도 시간이 지나면 과거가 되므로 픽스처의 렌더 결과는 실행 시점에 따라 달라진다.

## 색상

`NO_COLOR` 규약을 따른다. 이 환경변수가 설정돼 있으면 ANSI 코드 없이 평문만 출력한다.

## 직접 실행

상태줄은 stdin 으로 JSON 을 받아 stdout 으로 텍스트를 내는 계약이다. 그래서 셸에서 그대로 돌려볼 수 있다.

```sh
jq -c . docs/payload-example.json | ./bin/hud | cat -v
```

픽스처의 `cwd` 는 실재하지 않는 경로라서 `branch:` 항목은 빠진다. 이것이 정상 동작이다 — 필드를 얻을 수 없으면 그 항목만 사라진다.

깨진 `NODE_OPTIONS` 아래에서도 같은 출력이 나와야 한다.

```sh
jq -c . docs/payload-example.json | NODE_OPTIONS="--require=/nonexistent.cjs" ./bin/hud
```

`node` 가 없는 환경에서는 stdout·stderr 모두 비고 종료 코드가 0이어야 한다.

```sh
jq -c . docs/payload-example.json | env PATH=/usr/bin:/bin ./bin/hud; echo "rc=$?"
```

## 아직 안 된 것

- **사본 모드 미검증** — `skills/setup/SKILL.md` 의 사본 모드는 마켓플레이스 설치를 전제하는데 그 경로가 아직 없어 한 번도 실행된 적이 없다
- **마켓플레이스 배포** — `.claude-plugin/marketplace.json` 이 없다. 지금 배포 경로는 이 저장소뿐이다
- **LICENSE** — 미정
- **설정 외부화** — 임계값이 `bin/hud.mjs` 소스에 있다. `~/.claude/hud/config.json` 으로 뺄지 미정
