---
name: setup
description: claude-hud 상태줄을 설치하거나 갱신한다. settings.json 의 statusLine 이 HUD 런처를 가리키게 병합하고, 필요하면 안정 경로로 사본을 만든다. 사용자가 `/hud:setup` 또는 `$hud:setup` 을 명시적으로 호출했을 때만 사용한다. 상태줄·HUD·설정 관련 요청이 관련 분야에 해당한다는 이유만으로 자동 사용하지 않는다.
user-invocable: true
disable-model-invocation: true
argument-hint: "[제거]"
---

# hud:setup

상태줄 HUD 를 설치·갱신·제거하는 스킬이야.

## 왜 setup 이 필요한가

**플러그인은 `statusLine` 을 등록할 수 없어.** 그래서 켜려면 **settings.json 을 한 번은 꼭 고쳐야** 하고, 이 스킬이 그걸 해.

이유의 정본은 `../../README.md` 의 `왜 setup 을 따로 실행해야 하나` 절이야. 컴포넌트 목록 같은 사실을 여기에 복사해두면, Claude Code 가 그 목록을 바꿀 때 두 곳이 갈라져.

## 두 가지 설치 모드

`statusLine.command` 는 **버전이 바뀌어도 유효한 경로**를 가리켜야 해. 그래서 플러그인이 어디에 설치됐는지에 따라 갈려.

| 모드 | 조건 | settings 가 가리키는 곳 | 업데이트 |
| --- | --- | --- | --- |
| **직접 참조** (기본) | 루트 경로에 버전 해시가 없다 — `~/.claude/skills/hud/` 같은 경우 | `<루트>/bin/hud` 를 그대로 | `git pull` 만으로 즉시 반영. setup 재실행 불필요 |
| **사본** | 루트 경로가 `/plugins/cache/` 아래다 (`.../hud/<해시>/`) | `~/.claude/hud/hud` | 플러그인 업데이트 후 **setup 재실행 필요** |

사본 모드가 필요한 건 마켓플레이스 설치 경로에 버전 해시가 박히기 때문이야. 그 경로를 settings 에 바로 쓰면 업데이트할 때마다 상태줄이 깨져.

**직접 참조 모드가 우선이야.** 사본이 없으면 동기화 문제 자체가 안 생겨.

> **사본 모드는 아직 한 번도 실행된 적이 없어.** 마켓플레이스 배포(`marketplace.json`)가 없어서 도달할 수 없는 경로야.
> 첫 마켓플레이스 설치 때 이 절이랑 제거 절차 4번을 실제로 검증해. 그때까지는 미검증으로 취급해.

## 타협 불가 가드레일

- **`/hud:setup` 이나 `$hud:setup` 호출에만 반응해.** 이름만 나온 건 호출이 아니야.
- settings.json 을 고치기 전에 **꼭 읽고 백업해.** 백업 경로는 사용자한테 알려줘.
- **다른 키를 덮어쓰지 마.** `statusLine` 만 병합해. `hooks`, `permissions` 등은 그대로 둬.
- 이미 **다른** `statusLine.command` 가 있으면 조용히 바꾸지 마. 기존 값을 보여주고 확인받아. 우리가 설치한 값이면 확인 없이 갱신해.
- 고친 다음엔 **JSON 유효성을 검사해.** settings.json 이 깨지면 그 파일의 설정 전부가 조용히 무력화돼.
- 설치했다고 말하기 전에 **실제로 실행해서 출력을 확인해.** [검증](#검증) 은 생략하지 마.

## 인자

| 입력 | 동작 |
| --- | --- |
| (없음) | 설치 또는 갱신 |
| `제거`, `uninstall`, `remove` | [제거](#제거) 절차 |

## Phase 0 — 플러그인 루트 확정

**추측하지 마.** 순서대로 시도하고 처음 성공한 걸 써.

1. `$CLAUDE_PLUGIN_ROOT` 가 설정돼 있고 그 안에 `bin/hud.mjs` 가 있으면 그거.
2. 없으면 찾아.

   ```bash
   ls -d ~/.claude/skills/hud/ ~/.claude/plugins/cache/*/hud/*/ 2>/dev/null
   ```

3. 후보가 여러 개면 **`bin/hud` 랑 `bin/hud.mjs` 가 둘 다 있는 것만** 남겨. 그래도 여러 개면 `.claude-plugin/plugin.json` 의 `version` 이 제일 높은 거. 판단이 안 서면 사용자한테 물어.
4. 하나도 없으면 멈추고 알려. 플러그인이 설치 안 된 상태야.

루트를 정했으면 **모드를 판정해.**

```bash
case "$ROOT" in
  */plugins/cache/*) MODE=copy ;;
  *)                 MODE=direct ;;
esac
```

## Phase 1 — 실행 경로 확정

### 직접 참조 모드

복사하지 마. 실행 권한만 보장해.

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

기존 `VERSION` 이 있었으면 **이전 → 이후** 를 보고해. 같으면 "변경 없음".

두 모드 다 `TARGET` 이 실제로 실행 가능한지 확인해.

```bash
test -x "$TARGET" || echo "실행 권한 없음: $TARGET"
```

## Phase 2 — settings.json

1. 읽어. `~/.claude/settings.json` 이 없으면 `{}` 로 시작해.

2. 기존 `statusLine` 을 확인해.

   ```bash
   jq '.statusLine' ~/.claude/settings.json 2>/dev/null
   ```

   | 기존 값 | 처리 |
   | --- | --- |
   | 없음 (`null`) | 그대로 설치 |
   | `command` 가 `hud/bin/hud` 또는 `.claude/hud/hud` 로 끝남 | 우리 것 — 확인 없이 갱신 |
   | `command` 가 `hud.mjs` 를 직접 부름 | 런처 이전의 우리 설정 — 갱신하고 **런처를 거치게 바뀌었음을 보고한다** |
   | 그 외 | **멈추고 기존 값을 보여준 뒤 교체 여부를 확인받는다** |

3. 백업해. 경로는 사용자한테 알려줘.

   ```bash
   cp -p ~/.claude/settings.json ~/.claude/settings.json.bak-hud-$(date +%Y%m%d%H%M%S)
   ```

4. `statusLine` 만 병합해.

   ```json
   {
     "statusLine": {
       "type": "command",
       "command": "<TARGET 의 절대경로>"
     }
   }
   ```

   **`~` 는 쓰지 마.** 셸 확장에 기대지 않게 절대 경로로 써 (`echo $HOME` 으로 실제 값을 확인해서 채워).

5. JSON 유효성이랑 다른 키가 보존됐는지 확인해.

   ```bash
   jq -e '.statusLine.command' ~/.claude/settings.json
   jq -e 'keys' ~/.claude/settings.json
   ```

## 검증

**여길 건너뛰고 완료라고 하지 마.** settings 에 적힌 커맨드를 그대로 읽어와서 실제 페이로드로 실행해.

```bash
CMD=$(jq -r '.statusLine.command' ~/.claude/settings.json)
jq -c . "$ROOT/docs/payload-example.json" | sh -c "$CMD" | cat -v
```

기대 결과는 ANSI 코드가 섞인 두 줄이야. 픽스처의 마지막 경로 조각이 레포 이름이랑 같아서 `repo:` 는 생략돼(중복 억제). 픽스처의 `cwd` 는 실재하지 않는 경로라서 `branch:` 항목이 빠지는 게 정상이야. **실행 경로는 그 조건에서도 나와** — 파일시스템을 안 보기 때문이고, 픽스처의 홈이 실행 환경의 `$HOME` 이랑 달라서 `~` 축약 없이 절대 경로로 그려져.

```
^[[2m/Users/me/Dev/some-repo^[[0m
^[[1mOpus 5^[[0m ^[[36mhigh^[[0m^[[2m | ^[[0m^[[2mctx:^[[0m^[[32m43%^[[0m ...
```

깨진 `NODE_OPTIONS` 아래에서도 같은 출력이 나오는지 같이 확인해. 런처가 있는 이유가 이거야.

```bash
jq -c . "$ROOT/docs/payload-example.json" | env NODE_OPTIONS="--require=/nonexistent.cjs" sh -c "$CMD" | cat -v
```

리셋 표기까지 확인하려면 `resets_at` 을 미래로 갱신해서 넣어. 픽스처 값은 절대 epoch 라서 시간이 지나면 과거가 되고, 그러면 양쪽 버전이 똑같이 괄호를 생략해서 **버전 차이가 안 보여.**

```bash
jq -c --argjson now "$(date +%s)" \
  '.rate_limits.five_hour.resets_at=($now+13800) | .rate_limits.seven_day.resets_at=($now+241200)' \
  "$ROOT/docs/payload-example.json" | sh -c "$CMD" | cat -v
```

출력이 비어 있으면 설치 실패야. 완료라고 쓰지 말고 원인을 찾아.

| 증상 | 확인할 것 |
| --- | --- |
| 출력 없음, stderr 도 없음 | `node` 가 PATH 에 있는가 (`command -v node`) |
| `MODULE_NOT_FOUND` | 런처를 거치지 않고 `node` 를 직접 부르고 있다 — `command` 값을 다시 확인 |
| `Permission denied` | `chmod +x "$TARGET"` |
| 1행만 나옴 | 정상일 수 있다. 페이로드에 지표 필드가 없으면 그 항목만 빠진다 |

## 마무리 보고

- **어느 모드로 설치했는지**랑 그 의미 (직접 참조면 업데이트 자동 반영, 사본이면 setup 재실행 필요)
- settings 백업 경로
- 검증 출력 (실제 바이트)
- **실행 중인 세션에 바로 반영되는지는 확인 안 했다고 분명히 적어.** 상태줄이 그대로면 재시작이 필요해.

## 제거

1. `~/.claude/settings.json` 을 백업해.
2. `statusLine` 값이 우리 건지 확인해. 아니면 건드리지 말고 그렇다고 알려.
3. 우리 거면 `statusLine` 키를 **삭제**해 (`jq 'del(.statusLine)'`). 다른 키는 그대로 둬.
4. 사본 모드로 설치했었으면 (`~/.claude/hud/` 가 있으면) 지울지 **물어봐.** 사용자가 직접 고친 임계값이 들어 있을 수 있어. 지우기 전에 디렉터리 내용을 보여줘.
5. 플러그인 자체(`~/.claude/skills/hud/`)는 **지우지 마.** 그건 저장소가 관리해.
6. JSON 유효성을 확인하고 보고해.
