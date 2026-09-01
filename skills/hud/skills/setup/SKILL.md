---
name: setup
description: claude-hud 상태줄을 설치하거나 갱신한다. settings.json 의 statusLine 이 HUD 런처를 가리키게 병합하고, 필요하면 안정 경로로 사본을 만든다. 사용자가 `/hud:setup` 또는 `$hud:setup` 을 명시적으로 호출했을 때만 사용한다. 상태줄·HUD·설정 관련 요청이 관련 분야에 해당한다는 이유만으로 자동 사용하지 않는다.
user-invocable: true
disable-model-invocation: true
argument-hint: "[제거]"
---

# hud:setup

상태줄 HUD 를 설치·갱신·제거한다.

## 왜 setup 이 필요한가

**플러그인은 `statusLine` 을 등록할 수 없다.** 플러그인이 제공할 수 있는 컴포넌트는 `commands / agents / skills / hooks / mcpServers / lspServers` 뿐이고, `statusLine` 은 settings 전용 키다. 공식 `/statusline` 커맨드조차 `~/.claude/settings.json` 을 직접 편집한다.

그래서 켜는 동작은 **settings.json 편집 한 번**이 반드시 필요하다. 이 스킬이 그걸 한다.

## 두 가지 설치 모드

`statusLine.command` 는 **버전이 바뀌어도 유효한 경로**를 가리켜야 한다. 그래서 플러그인이 어디에 설치됐는지에 따라 갈린다.

| 모드 | 조건 | settings 가 가리키는 곳 | 업데이트 |
| --- | --- | --- | --- |
| **직접 참조** (기본) | 루트 경로에 버전 해시가 없다 — `~/.claude/skills/hud/` 같은 경우 | `<루트>/bin/hud` 를 그대로 | `git pull` 만으로 즉시 반영. setup 재실행 불필요 |
| **사본** | 루트 경로가 `/plugins/cache/` 아래다 (`.../hud/<해시>/`) | `~/.claude/hud/hud` | 플러그인 업데이트 후 **setup 재실행 필요** |

사본 모드가 필요한 이유는 마켓플레이스 설치 경로에 버전 해시가 박히기 때문이다. 그 경로를 settings 에 직접 쓰면 업데이트마다 상태줄이 깨진다.

**직접 참조 모드를 우선한다.** 사본이 없으면 동기화 문제 자체가 없다.

## 타협 불가 가드레일

- **`/hud:setup` 또는 `$hud:setup` 호출에만 반응한다.** 이름만 언급한 경우는 호출이 아니다.
- settings.json 을 고치기 전에 **반드시 읽고 백업한다.** 백업 경로를 사용자에게 알린다.
- **다른 키를 덮어쓰지 않는다.** `statusLine` 만 병합한다. `hooks`, `permissions` 등은 그대로 둔다.
- 이미 **다른** `statusLine.command` 가 있으면 조용히 바꾸지 않는다. 기존 값을 보여주고 확인을 받는다. 우리가 설치한 값이면 확인 없이 갱신한다.
- 편집 후 **JSON 유효성을 검사한다.** 깨진 settings.json 은 그 파일의 모든 설정을 조용히 무력화한다.
- 설치했다고 주장하기 전에 **실제로 실행해 출력을 확인한다.** [검증](#검증) 은 생략하지 않는다.

## 인자

| 입력 | 동작 |
| --- | --- |
| (없음) | 설치 또는 갱신 |
| `제거`, `uninstall`, `remove` | [제거](#제거) 절차 |

## Phase 0 — 플러그인 루트 확정

**추측하지 않는다.** 순서대로 시도하고 처음 성공한 것을 쓴다.

1. `$CLAUDE_PLUGIN_ROOT` 가 설정돼 있고 그 안에 `bin/hud.mjs` 가 있으면 그것.
2. 없으면 찾는다.

   ```bash
   ls -d ~/.claude/skills/hud/ ~/.claude/plugins/cache/*/hud/*/ 2>/dev/null
   ```

3. 후보가 여럿이면 **`bin/hud` 와 `bin/hud.mjs` 가 둘 다 있는 것만** 남긴다. 그래도 여럿이면 `.claude-plugin/plugin.json` 의 `version` 이 가장 높은 것. 판단이 안 서면 사용자에게 묻는다.
4. 하나도 없으면 멈추고 알린다. 플러그인이 설치되지 않은 상태다.

루트를 정한 뒤 **모드를 판정한다.**

```bash
case "$ROOT" in
  */plugins/cache/*) MODE=copy ;;
  *)                 MODE=direct ;;
esac
```

## Phase 1 — 실행 경로 확정

### 직접 참조 모드

복사하지 않는다. 실행 권한만 보장한다.

```bash
chmod +x "$ROOT/bin/hud" "$ROOT/bin/hud.mjs"
TARGET="$ROOT/bin/hud"
```

### 사본 모드

```bash
mkdir -p ~/.claude/hud
cp "$ROOT/bin/hud" "$ROOT/bin/hud.mjs" ~/.claude/hud/
chmod +x ~/.claude/hud/hud ~/.claude/hud/hud.mjs
jq -r '.version' "$ROOT/.claude-plugin/plugin.json" > ~/.claude/hud/VERSION
TARGET="$HOME/.claude/hud/hud"
```

기존 `VERSION` 이 있었다면 **이전 → 이후** 를 보고한다. 같으면 "변경 없음".

두 모드 모두 `TARGET` 이 실제 실행 가능한지 확인한다.

```bash
test -x "$TARGET" || echo "실행 권한 없음: $TARGET"
```

## Phase 2 — settings.json

1. 읽는다. `~/.claude/settings.json` 이 없으면 `{}` 로 시작한다.

2. 기존 `statusLine` 을 확인한다.

   ```bash
   jq '.statusLine' ~/.claude/settings.json 2>/dev/null
   ```

   | 기존 값 | 처리 |
   | --- | --- |
   | 없음 (`null`) | 그대로 설치 |
   | `command` 가 `hud/bin/hud` 또는 `.claude/hud/hud` 로 끝남 | 우리 것 — 확인 없이 갱신 |
   | `command` 가 `hud.mjs` 를 직접 부름 | 런처 이전의 우리 설정 — 갱신하고 **런처를 거치게 바뀌었음을 보고한다** |
   | 그 외 | **멈추고 기존 값을 보여준 뒤 교체 여부를 확인받는다** |

3. 백업한다. 경로를 사용자에게 알린다.

   ```bash
   cp -p ~/.claude/settings.json ~/.claude/settings.json.bak-hud-$(date +%Y%m%d%H%M%S)
   ```

4. `statusLine` 만 병합한다.

   ```json
   {
     "statusLine": {
       "type": "command",
       "command": "<TARGET 의 절대경로>"
     }
   }
   ```

   **`~` 를 쓰지 않는다.** 셸 확장에 의존하지 않도록 절대 경로를 쓴다 (`echo $HOME` 으로 실제 값을 확인해 채운다).

5. JSON 유효성과 다른 키 보존을 확인한다.

   ```bash
   jq -e '.statusLine.command' ~/.claude/settings.json
   jq -e 'keys' ~/.claude/settings.json
   ```

## 검증

**여기를 건너뛰고 완료라고 하지 않는다.** settings 에 적힌 커맨드를 그대로 읽어와 실제 페이로드로 실행한다.

```bash
CMD=$(jq -r '.statusLine.command' ~/.claude/settings.json)
jq -c . "$ROOT/docs/payload-example.json" | sh -c "$CMD" | cat -v
```

기대 결과 — ANSI 코드가 섞인 두 줄. 픽스처의 `cwd` 는 실재하지 않는 경로라서 `branch:` 항목은 빠지는 것이 정상이다.

```
^[[2mrepo:^[[0m^[[36msome-repo^[[0m
^[[1mOpus 5^[[0m^[[2m | ^[[0m^[[2mctx:^[[0m^[[32m43%^[[0m ...
```

깨진 `NODE_OPTIONS` 아래에서도 같은 출력이 나오는지 함께 확인한다. 런처의 존재 이유가 이것이다.

```bash
jq -c . "$ROOT/docs/payload-example.json" | env NODE_OPTIONS="--require=/nonexistent.cjs" sh -c "$CMD" | cat -v
```

출력이 비어 있으면 설치 실패다. 완료라고 쓰지 말고 원인을 찾는다.

| 증상 | 확인할 것 |
| --- | --- |
| 출력 없음, stderr 도 없음 | `node` 가 PATH 에 있는가 (`command -v node`) |
| `MODULE_NOT_FOUND` | 런처를 거치지 않고 `node` 를 직접 부르고 있다 — `command` 값을 다시 확인 |
| `Permission denied` | `chmod +x "$TARGET"` |
| 1행만 나옴 | 정상일 수 있다. 페이로드에 지표 필드가 없으면 그 항목만 빠진다 |

## 마무리 보고

- **어느 모드로 설치했는지**와 그 의미 (직접 참조면 업데이트 자동 반영, 사본이면 setup 재실행 필요)
- settings 백업 경로
- 검증 출력 (실제 바이트)
- **실행 중인 세션에 즉시 반영되는지는 확인하지 않았다고 명시한다.** 상태줄이 그대로면 재시작이 필요하다.

## 제거

1. `~/.claude/settings.json` 을 백업한다.
2. `statusLine` 값이 우리 것인지 확인한다. 아니면 건드리지 않고 그 사실을 알린다.
3. 우리 것이면 `statusLine` 키를 **삭제**한다 (`jq 'del(.statusLine)'`). 다른 키는 그대로 둔다.
4. 사본 모드로 설치했었다면 (`~/.claude/hud/` 가 존재) 지울지 **묻는다.** 사용자가 직접 고친 임계값이 들어 있을 수 있다. 지우기 전에 디렉터리 내용을 보여준다.
5. 플러그인 자체(`~/.claude/skills/hud/`)는 **지우지 않는다.** 그건 저장소가 관리한다.
6. JSON 유효성을 확인하고 보고한다.
