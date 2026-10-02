---
name: cmux-where
description: |
  cmux 창 안에서 이 세션이 어디에 있는지(window·workspace·pane·surface 와 좌/우/상/하),
  같은 창의 다른 터미널이 각각 어디에 있고 어느 것이 Claude 세션인지 알아낸다.
  좌표(pane.list 의 pixel_frame)로 판정하므로 cmux tree 의 index 순서를 화면 순서로
  오독하는 실수를 막는다.
  다음 상황에서 사용한다 — 사용자가 화면 위치로 터미널·세션을 지목할 때
  ("좌측 세션에 물어봐", "옆 터미널", "아래쪽 창"); 이 세션의 위치를 물을 때
  ("너 지금 어디야", "몇 번 pane 이야"); 지금 떠 있는 세션 목록을 물을 때;
  다른 cmux 터미널에 무언가 보내려면 대상 surface 를 특정해야 할 때.
  cmux 안에서 돌고 있지 않으면(CMUX_SURFACE_ID 없음) 사용하지 않는다.
  cmux 설정 변경, Ghostty 설정, 일반 tmux·터미널 질문에는 사용하지 않는다.
user-invocable: true
disable-model-invocation: false
argument-hint: "[--all] [--json]"
allowed-tools:
  - Bash
  - Read
  - AskUserQuestion
---

# /cmux-where — 이 세션이 cmux 안에서 어디에 있는지 파악한다

## 활성화 조건

**이 스킬은 이 저장소에서 유일하게 자동 호출을 허용해.** 사용자가 직접 불러도(`/cmux-where`) 되고, 아래 상황에선 AI 가 알아서 써도 돼. 예외를 둔 이유는 `AGENTS.md` 의 "자동 호출 예외" 절에 있어.

알아서 쓰는 경우:

- 사용자가 **화면 위치로** 터미널이나 세션을 지목할 때 — "좌측 세션에 물어봐", "옆 터미널", "아래쪽 창에서"
- 사용자가 **이 세션의 위치**를 물을 때 — "너 지금 어디야", "몇 번 pane 이야"
- 사용자가 **지금 떠 있는 세션들**을 물을 때
- 다른 cmux 터미널에 뭔가 보내야 해서 **대상 surface 를 특정해야 할 때**

알아서 쓰지 않는 경우:

- **cmux 안에서 돌고 있지 않을 때.** `$CMUX_SURFACE_ID` 가 비어 있으면 이 스킬은 아무 답도 못 줘. 먼저 확인하고, 없으면 조용히 물러나.
- cmux 설정·Ghostty 설정 변경, 일반 tmux 질문, 터미널 에뮬레이터 일반론
- 위치랑 상관없는데 "터미널", "세션", "창" 같은 단어만 나온 경우

자동 호출은 **위치를 알아내는 데까지**야. 알아낸 다음 다른 터미널에 실제로 입력을 보내는 건 별개고, 아래 "동작 원칙" 의 확인 규칙을 그대로 따라.

## 뭐 하는 스킬이냐면

cmux 는 터미널 여러 개를 한 창에 격자로 띄우고, 각 터미널에서 에이전트 세션이 돌아. 그런데 **세션 안에선 자기가 화면 어디에 있는지 기본적으로 알 방법이 없어.** 사용자가 "좌측 세션에 물어봐" 라고 해도 어느 쪽이 좌측인지 몰라.

이 스킬은 세 가지를 줘.

1. **내 위치** — `window:1 > workspace:3 > pane:14 > surface:16`, 그리고 "좌우 2분할 중 우측"
2. **형제 터미널 지도** — 같은 창의 다른 터미널이 각각 어디 있는지, 어느 게 Claude 세션인지
3. **위치로 지목하는 방법** — "좌측" 을 `--surface surface:8` 로 바꿔주니까 그대로 명령을 보낼 수 있어

## 실행 절차

```bash
"$SKILL_DIR/bin/cmux-where.py"          # 내 위치 + 같은 workspace 의 형제
"$SKILL_DIR/bin/cmux-where.py" --all    # 모든 workspace 의 터미널 지도
"$SKILL_DIR/bin/cmux-where.py" --json   # 구조화 출력
```

`SKILL_DIR` 은 이 `SKILL.md` 가 있는 디렉터리야. 전역 설치본이면 보통 `~/.claude/skills/cmux-where`.

사용자가 다른 workspace 의 세션을 언급했거나 "지금 떠 있는 세션들" 처럼 전체를 물으면 `--all` 을 써. 그 외엔 기본 출력이 짧고 충분해.

출력을 그대로 붙여넣지 말고 **사용자가 물은 것만 골라서 답해.** "내가 어디야?" 엔 두 줄이면 돼.

## cmux 의 계층 모델

이걸 모르면 어떤 명령이든 엉뚱한 데로 가. 네 단계야.

```
window     창 하나 (window:1)
└─ workspace   좌측 사이드바의 항목 하나. 보통 프로젝트 단위 (workspace:3 "plugin | ai skills")
   └─ pane        화면을 실제로 나눠 가진 영역. 좌/우/상/하가 있는 단위 (pane:14)
      └─ surface     pane 안의 탭. 터미널 하나 = 세션 하나 (surface:16)
```

| 개념 | 정체 | 위치가 있나 |
|---|---|---|
| `workspace` | 사이드바 항목. **한 번에 하나만 화면에 보인다** | 없음 (겹쳐 있음) |
| `pane` | 분할 영역. 여기에 좌/우/상/하가 있다 | **있음** |
| `surface` | pane 안의 탭. 같은 pane 의 탭들은 위치가 같다 | pane 을 따라간다 |

**한 pane 에 surface 가 여러 개면 그건 탭이야.** 그중 하나만 보이고 나머진 배경이야. 스크립트는 이걸 `[배경 탭]` 으로 표시해. 배경 탭에 명령을 보내도 동작은 하지만, 사용자는 그걸 보고 있지 않아.

환경변수는 이렇게 대응해.

| 환경변수 | 가리키는 것 |
|---|---|
| `$CMUX_WORKSPACE_ID` | 내 workspace UUID |
| `$CMUX_SURFACE_ID` | 내 surface UUID (`$CMUX_PANEL_ID` 와 같은 값) |
| `$CLAUDE_CODE_SESSION_ID` | 이 Claude 세션. surface 의 `resume_binding.checkpoint_id` 와 같다 |

마지막 항목이 **Claude 세션이랑 터미널을 잇는 고리**야. 어떤 surface 가 어떤 Claude 대화인지 이걸로 알아.

## 반드시 알아야 할 함정 네 개

이 스킬이 있는 이유의 절반이 아래 함정들이야. 앞의 세 개는 **에러 없이 조용히 틀린 답을 주는** 종류고, 네 번째는 에러로 드러나긴 하는데 원인을 오해하기 쉬운 종류야.

### 1. `cmux tree` 의 나열 순서는 화면 순서가 아니다

`cmux tree` 랑 `cmux list-panes` 는 pane 을 **index 순서**로 찍어. 그 순서가 열 우선이라서 2행 2열 격자에선 이렇게 돌아.

```
실제 화면              tree 나열 순서
┌────────┬────────┐    pane:8   ← index 0
│ pane:8 │ pane:10│    pane:9   ← index 1   (화면에서는 좌하단!)
├────────┼────────┤    pane:10  ← index 2
│ pane:9 │ pane:11│    pane:11  ← index 3
└────────┴────────┘
```

**목록의 두 번째를 "우측" 으로 읽으면 실제론 좌하단을 가리켜.** 좌우 2분할일 때만 우연히 맞아. `cmux tree` 로 위치를 추론하지 마.

### 2. 좌/우/상/하를 아는 유일한 경로는 `pixel_frame` 이다

기하 정보는 raw RPC 에만 있어. CLI 의 정리된 출력은 이걸 버려.

```bash
cmux rpc pane.list "{\"workspace_id\":\"$CMUX_WORKSPACE_ID\"}"
```

pane 마다 `pixel_frame` 이 `{x, y, width, height}` 를 줘. `x` 를 비교하면 좌우, `y` 를 비교하면 상하야. 분할 축이 뭐든 이 비교는 성립하니까 **index 말고 좌표를 써.**

값이 `460.5` 처럼 소수로 나와서, 같은 행·열로 묶을 땐 허용 오차가 필요해 (스크립트는 4px 를 써).

`pixel_frame.x` 는 창 기준 절대 좌표라서 사이드바 폭(예: 216)이 이미 더해져 있어. `container_frame` 은 사이드바를 뺀 콘텐츠 영역 크기고. **둘은 기준이 다르니까 섞어서 계산하지 마.** 어차피 필요한 건 상대 순서뿐이야.

### 3. `rpc` 의 파라미터 이름을 틀리면 조용히 남의 workspace 를 준다

`cmux rpc pane.list` 의 workspace 파라미터는 **`workspace_id` (snake_case) 고 값은 UUID** 야.

| 넘긴 키 | 결과 |
|---|---|
| `workspace_id` + UUID | **올바름** |
| `workspace`, `workspaceId`, `workspace_ref` | 무시된다. 에러 없이 **focused workspace** 를 돌려준다 |
| `workspace_id` + `"workspace:3"` 같은 ref | 무시된다 (UUID 여야 한다) |

에러 대신 그럴듯한 다른 답이 오니까, 검증 없이 쓰면 남의 workspace 를 자기 걸로 착각해. **CLI 서브커맨드(`cmux list-panes` 등)는 `$CMUX_WORKSPACE_ID` 를 기본값으로 잘 쓰지만, `cmux rpc` 는 안 그래.**

### 4. `--workspace` 를 생략하면 남의 workspace 의 surface 를 못 찾는다

`cmux send` / `send-key` / `read-screen` 의 `--workspace` **기본값은 `$CMUX_WORKSPACE_ID`, 즉 내 workspace** 야.

```
$ cmux send --help
  --workspace <id|ref|index>   Target workspace (default: $CMUX_WORKSPACE_ID)
```

그래서 다른 workspace 의 surface ref 를 `--surface` 로만 넘기면, cmux 는 그 ref 를 **내 workspace 안에서** 찾다가 실패해 (`Surface is not a terminal` 류). `--all` 로 얻은 대상은 대개 다른 workspace 라서 이 함정에 그대로 걸려.

앞의 세 개와 달리 이건 **에러로 드러나.** 조용히 틀리진 않지만, 원인이 `--surface` 값이 아니라 생략한 `--workspace` 라서 엉뚱한 데를 고치기 쉬워.

스크립트는 대상이 내 workspace 가 아니면 전송 예시에 `--workspace <ref>` 를 자동으로 붙여서 출력해. **출력된 명령을 그대로 쓰면 이 함정은 안 만나.**

## caller 와 focused 는 다르다

`cmux identify` 는 블록 두 개를 줘.

| 블록 | 뜻 |
|---|---|
| `caller` | **이 명령을 실행한 터미널** = 나 |
| `focused` | **지금 사용자 화면에 보이는 터미널** |

백그라운드 workspace 에서 도는 세션은 이 둘이 달라. 그리고 **`--workspace` / `--surface` 를 생략한 cmux 명령 중 일부는 `focused` 쪽으로 가.** 사용자가 다른 프로젝트를 보고 있는 동안 그쪽 터미널에 명령을 쏘는 사고가 이렇게 나.

그래서 **다른 터미널을 조작할 땐 항상 `--surface <ref>` 를 명시해.** 스크립트는 caller 와 focused 가 다르면 경고를 띄워.

## 위치로 지목해 명령 보내기

스크립트가 터미널마다 전송 명령을 **그대로 복사해 쓸 수 있는 형태로** 출력해. 텍스트 전송이랑 Enter 는 별개야.

```bash
# 내 workspace 안의 터미널
cmux send --surface surface:8 "<text>" && cmux send-key --surface surface:8 enter

# 다른 workspace 의 터미널 — --workspace 를 반드시 붙인다 (아래 함정 4)
cmux send --workspace workspace:2 --surface surface:5 "<text>" \
  && cmux send-key --workspace workspace:2 --surface surface:5 enter

cmux read-screen --surface surface:8 --lines 40   # 결과 확인
```

사용자가 "좌측 세션에 ~ 물어봐" 처럼 **위치로** 지목하면 스크립트 출력에서 그 위치의 `surface_ref` 를 찾아서 써. 위치 표현을 추측해서 `surface:1` 같은 걸 찍지 마.

### 보낸 텍스트가 어떻게 처리되나

대상 surface 가 뭘 돌리고 있느냐에 따라 달라. 스크립트 출력의 `claude=` 표시로 구분해.

| 대상 | 결과 |
|---|---|
| Claude Code 가 돌고 있는 surface (`claude=` 있음) | 그 Claude 에게 **프롬프트로 입력**된다 |
| 일반 셸 surface (`claude=` 없음) | **셸 명령으로 실행**된다 |

같은 문장이 한쪽에선 질문이고 다른 쪽에선 명령이야. 보내기 전에 어느 쪽인지 확인해.

## 동작 원칙

- **위치는 좌표로 판정해.** `index`, `tree` 나열 순서, ref 번호 크기로 좌우를 추론하지 마. `surface:16` 이 `surface:8` 보다 오른쪽에 있다는 보장은 없어.
- **다른 터미널을 건드릴 때 `--surface` 를 생략하지 마.** 생략하면 사용자가 보고 있는 남의 터미널로 갈 수 있어.
- **다른 세션에 명령을 보내기 전엔 사용자 확인을 받아.** 그쪽 입장에선 사람이 개입 안 한 입력이 갑자기 실행되는 거고, 그 세션이 뭘 하던 중인지 이쪽은 몰라. 사용자가 이미 "좌측에 보내" 라고 지시했으면 그게 확인이야.
- **`send-key ... enter` 는 실행 버튼이야.** `send` 만 하면 입력창에 글자만 남아. 보낼 생각이면 둘을 같이, 아니면 `send` 만 써.
- **선택 안 된 workspace 의 절대 픽셀값은 낡았을 수 있어.** 그 workspace 가 마지막으로 화면에 있었을 때 값이거든 (그 뒤에 창 크기가 바뀌었으면 어긋나). 상대 순서는 유지되니까 좌/우 판정엔 문제없지만, 픽셀값 자체를 사용자한테 보고하진 마.
- **레이아웃을 마음대로 바꾸지 마.** `new-split`, `close-surface`, `move-surface`, `swap-pane`, `focus-workspace` 는 사용자 화면을 실제로 흔들어. 사용자가 요청했을 때만 써. 위치 파악은 전부 읽기 전용으로 끝나.
- **제목의 글리프(`✳`, `◐`, `◑`)를 상태로 단정하지 마.** cmux 가 붙이는 표시고, 이 스킬은 그 의미를 확인한 적이 없어. 세션 상태가 중요하면 `cmux read-screen` 으로 실제 화면을 봐.

## 참고: 조사해서 확인한 명령

이 스킬이 실제로 검증한 것만 적었어.

| 명령 | 주는 것 |
|---|---|
| `cmux identify` | caller / focused 의 window·workspace·pane·surface·tab ref |
| `cmux rpc pane.list '{"workspace_id":"<uuid>"}'` | **pane 별 `pixel_frame`** — 좌우/상하의 유일한 근거 |
| `cmux rpc surface.list '{"workspace_id":"<uuid>"}'` | surface 별 `pane_ref`·`title`·`selected_in_pane`·`resume_binding.checkpoint_id` |
| `cmux rpc workspace.list` | workspace 의 `ref`·`title`·`selected`·`current_directory` |
| `cmux tree` | 전체 구조 개요. `◀ here` 로 caller 표시. **위치 판정에는 쓰지 않는다** |
| `cmux read-screen --surface <ref> --lines <n>` | 그 터미널의 실제 화면 |
| `cmux send` / `send-key --surface <ref>` | 텍스트 전송 / 키 전송 |
