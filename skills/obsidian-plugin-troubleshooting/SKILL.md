---
name: obsidian-plugin-troubleshooting
description: |
  Obsidian 플러그인을 만들며 쌓인 트러블슈팅 기록의 색인. 앱이 멈추거나, 입력이
  안 되거나, 클립보드 서식이 깨지거나, CSS 폭이 안 줄어드는 증상을 만났을 때
  이미 겪은 것인지 먼저 확인한다. 새 Obsidian 플러그인 작업을 시작할 때 금지
  패턴을 훑는 용도로도 쓴다.
  사용자가 `/obsidian-plugin-troubleshooting` 또는
  `$obsidian-plugin-troubleshooting` 을 명시적으로 호출했을 때만 사용한다.
  Obsidian·플러그인 관련 요청이 관련 분야에 해당한다는 이유만으로 자동 사용하지 않는다.
user-invocable: true
disable-model-invocation: true
argument-hint: "[증상 키워드]"
allowed-tools:
  - Bash
  - Read
  - Grep
  - Glob
---

# /obsidian-plugin-troubleshooting — 이미 겪은 것인지 먼저 본다

**이 파일은 색인이야. 내용은 `references/` 에 있어.** 증상이 걸리는 항목만 열어서 읽어. 전부 읽진 마 — 합치면 4만 자가 넘어.

## 언제 쓰나

| 상황 | 하는 일 |
|---|---|
| 증상을 만났다 | 아래 색인에서 찾는다. 있으면 그 문서를 열고, 없으면 새로 조사한다 |
| 새 플러그인 작업을 시작한다 | `obsidian-plugin-freeze-rules` 를 먼저 읽는다. 앱을 멈추게 하는 패턴 모음이다 |
| 트러블슈팅을 새로 썼다 | 원본 프로젝트에 쓰고, [색인 갱신](#색인-갱신) 절차를 따른다 |

## 색인 — 재사용 기록 (`references/`)

작성자가 `reusable/` 로 분류한 것들이야. **원인이 Obsidian·브라우저·OS 에 있어서 다른 프로젝트에서도 그대로 재발해.**

| 증상 | 문서 | 크기 |
|---|---|---|
| 앱이 멈추거나 느려진다. 플러그인을 켜자마자 먹통 | `references/obsidian-plugin-freeze-rules.md` | 16K |
| 오류도 없는데 **입력이 전혀 안 된다.** 드래그 선택만 됨 | `references/automation-left-host-app-in-readonly-view.md` | 4.6K |
| 복사한 마크다운을 붙여넣으면 **서식이 사라진다** | `references/clipboard-writetext-loses-formatting.md` | 6.4K |
| 폭 속성을 풀었는데 요소가 **내용물 크기로 안 줄어든다** | `references/container-type-inline-size-blocks-width-auto.md` | 2.3K |

제일 먼저 볼 건 **`obsidian-plugin-freeze-rules`** 야. 나머지 셋은 개별 증상이고 이건 패턴·금지 사항 모음이라, 착수 전에 읽어두면 나머지는 아예 안 만나게 돼.

### 각 문서의 쓸모

- **freeze-rules** — Obsidian 플러그인이 앱을 멈추게 하는 패턴들. 레이아웃 이벤트에서 레이아웃을 바꾸는 재귀, 같은 영역을 만지는 플러그인끼리의 충돌 등
- **automation-left-host-app-in-readonly-view** — 외부 명령으로 보기 모드를 바꾸고 안 되돌린 경우. **토글 명령은 이전 상태를 알려주지 않고**, 모드는 세션을 넘어 저장돼. Obsidian 만의 문제가 아니라 편집/읽기 모드가 나뉜 앱이면 다 해당
- **clipboard-writetext-loses-formatting** — `navigator.clipboard.writeText` 는 평문만 올려
- **container-type-inline-size-blocks-width-auto** — CSS 컨테이너 쿼리를 건 요소의 폭 동작

## 색인 — 프로젝트 고유 기록 (포인터만)

작성자가 `project-specific/` 로 분류한 것들이야. **원인이 그 프로젝트 코드에 있어서** 그대로 재사용은 안 돼. 여기로 복사하지 마. 그래도 비슷한 걸 만들 땐 참고할 만해.

| 증상 | 위치 |
|---|---|
| 탭 그룹을 만들면 Obsidian 이 멈춘다 | `my-obsidian-tools/docs/troubleshootings/project-specific/tab-group-layout-infinite-loop.md` |
| 켜자마자 먹통 — 탭 바를 만지는 플러그인이 둘 | `.../two-tab-group-plugins-freeze-on-startup.md` |
| 탭을 열 때마다 그룹 라벨이 깜빡인다 | `.../tab-group-label-flickers-on-tab-open.md` |
| 라벨을 빠르게 누르면 창 크기가 바뀐다 | `.../fast-tab-group-click-resizes-obsidian-window.md` |

넷 다 **탭 바를 건드리는 플러그인**에서 나왔어. 그 영역을 만질 계획이면 `freeze-rules` 랑 같이 읽어.

## 증상으로 찾기

```bash
grep -ril "<키워드>" "$SKILL_DIR/references/"
```

`SKILL_DIR` 은 이 `SKILL.md` 가 있는 디렉터리야. 인자로 키워드가 왔으면 그걸로 먼저 훑어.

**색인에 없다고 "처음 보는 문제" 라고 단정하지 마.** 기록엔 겪은 것만 있어. 없으면 새로 조사하고, 원인을 찾았으면 아래 절차대로 기록을 남겨.

## 색인 갱신

기록은 원본 프로젝트에서 자라. 여기로 안 가져오면 이 색인은 조용히 낡아.

```bash
"$SKILL_DIR/bin/scan-sources.py"
```

`~/my/Dev` 아래에서 **Obsidian 플러그인 프로젝트만** 골라 `docs/troubleshootings/` 를 훑어. 판정 기준은 루트 `manifest.json` 의 `minAppVersion` 이야 — Chrome 확장도 `manifest.json` 을 쓰지만 그쪽은 `manifest_version` 이라 걸러져. 이 구분이 없으면 무관한 기록이 섞여.

읽기 전용이야. 알려주는 건 세 가지.

| 보고 | 뜻 |
|---|---|
| `references/ 에 없는 reusable 문서` | 새로 쓴 것. 가져올지 사람이 판단한다 |
| `원본이 바뀐 문서` | 원본이 정본이다. 여기 사본을 다시 가져온다 |
| `project-specific` | **가져오지 않는다.** 포인터 색인만 갱신한다 |

가져올 땐 파일을 `references/` 로 복사하고 **위 색인 표에 줄을 추가해.** 파일만 넣고 색인을 안 고치면 아무도 그 문서를 못 찾아.

## 동작 원칙

- **원본이 정본이야.** `references/` 는 사본이고 파일마다 머리에 출처가 적혀 있어. 내용을 고쳐야 하면 **원본 프로젝트에서 고치고 다시 가져와.** 여기서 고치면 두 벌이 갈라져.
- **새 트러블슈팅을 이 스킬에 직접 쓰지 마.** 겪은 프로젝트의 `docs/troubleshootings/` 에 먼저 써. 그래야 그 프로젝트 사람도 봐.
- **`reusable` 과 `project-specific` 경계를 지켜.** 원인이 라이브러리·런타임·OS 에 있으면 reusable, 그 프로젝트 코드에 있으면 project-specific 이야. 판단이 안 서면 원인을 한 줄로 써봐. 그러면 갈려.
- **전부 읽지 마.** 색인에서 증상이 걸리는 것만 열어. `freeze-rules` 만 예외로, 착수 전에 통독할 값어치가 있어.
- **이 스킬은 커밋 안 해.** 색인을 갱신했으면 이 저장소 규약대로 처리해.
