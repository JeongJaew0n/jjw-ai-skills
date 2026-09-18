> 출처: `my-obsidian-tools/docs/troubleshootings/reusable/obsidian-plugin-freeze-rules.md` (2026-09-18 복사)
> 원본이 정본이다. 여기서 고치지 말고 원본을 고친 뒤 다시 가져온다.

# Obsidian 플러그인이 앱을 멈추게 하는 패턴과 금지 사항

- 작성: 2026-09-18
- 대상: 쓰고 있는 자작 Obsidian 플러그인 (`my-obsidian-tools` · `playmaker` · `inno-daily-log`)
  — `dooray-daily-log`는 2026-09-18 사용 중단으로 대상에서 뺐다
- 목적: 실제로 Obsidian을 멈추거나 느리게 만든 사건들에서 규칙만 뽑아 한곳에 둔다.
  새 기능을 설계할 때 이 목록을 먼저 읽는다.

## 근거로 삼은 사건

추측이 아니라 실제 발생 기록에서만 뽑았다.

| 사건 | 결과 | 원인 위치 |
| --- | --- | --- |
| [탭 그룹을 만들면 Obsidian이 멈춘다](../project-specific/tab-group-layout-infinite-loop.md) | **완전 프리즈** | 우리 코드 (배치 계산 불일치 + 감시자 가드 무효) |
| [켜자마자 먹통 — 탭 바를 만지는 플러그인이 둘](../project-specific/two-tab-group-plugins-freeze-on-startup.md) | **시작 즉시 프리즈** | 플러그인 구성 (상호 루프) |
| [탭을 열 때마다 그룹 라벨이 깜빡인다](../project-specific/tab-group-label-flickers-on-tab-open.md) | 깜빡임 + 낭비되는 재삽입 | 호스트 앱이 우리 요소를 제거 |
| [라벨을 빠르게 누르면 창이 줄어든다](../project-specific/fast-tab-group-click-resizes-obsidian-window.md) | 창 크기 오동작 | DOM 재생성 중 클릭 대상 교체 |
| [자동화가 호스트 앱을 읽기 전용으로 남김](https://github.com/JeongJaew0n/obsidian-plugin-for-inno) (`inno-daily-log` 저장소) | **멈춘 것처럼 보임** (실제로는 정상) | **조사용 자동화** — 플러그인 코드가 아니다 |

범위 밖으로 둔 것: `clipboard.writeText` 서식 손실은 성능·정지와 무관해 제외했다.

## 1. DOM을 감시하면서 DOM을 고칠 때

프리즈 사건 두 건이 전부 여기서 났다. 가장 위험한 영역이다.

- **멱등성은 정확성의 일부다.** 같은 입력으로 두 번째 배치를 돌리면 DOM 변경이 **0건**이어야 한다.
  1건이라도 남으면 감시자가 다시 깨어나고, 그 사이클은 스스로 멈추지 않는다.
  → 테스트로 고정한다. `tests/arrange.test.ts`의 "두 번째 배치는 DOM을 건드리지 않는다"가 그 역할이다.
- **`MutationObserver` 콜백은 마이크로태스크로 비동기 실행된다.** 동기 플래그(`if (this.applying) return`)로
  자기 변경을 거르려는 시도는 **한 번도 걸리지 않는다.** 콜백이 돌 때는 이미 플래그가 내려가 있다.
  → 작업이 끝난 자리에서 `observer.takeRecords()`로 자기 변경 기록을 버린다.
- **같은 영역을 두 계산이 각자 배치하면 서로를 되돌린다.** 정렬이 라벨의 존재를 모르면
  정렬은 라벨을 밀어내고 라벨 배치는 되돌린다. 영원히 반복된다.
  → 한 목표 순서를 **한 번에** 계산해 한 패스로 배치한다.
- 감시 범위를 최소로 잡는다. `{ childList: true }`만 필요하면 속성·서브트리를 켜지 않는다.
  속성 변경(class·style)은 childList 감시자를 깨우지 않으므로, 표시용 클래스 토글은 안전하다.

## 2. 호스트 앱이 소유한 컨테이너에 우리 요소를 넣지 않는다

- **호스트 앱은 자기가 만들지 않은 자식을 정리 대상으로 본다.** Obsidian의 `updateTabDisplay()`는
  탭 바에서 등록되지 않은 자식을 "방금 닫힌 탭"으로 보고 복제본으로 바꿔치기한 뒤 200ms 페이드아웃으로 없앤다.
  우리가 다시 꽂으면 깜빡임이 반복되고, 그동안 계속 일한다.
- **붙일 자리를 고를 때 "이 요소의 부모를 누가 다시 그리는가"를 먼저 본다.**
  호스트가 한 번 만들고 재사용하는 요소(`leaf.tabHeaderEl`)의 **안쪽**이 상대적으로 안전하다.
  비우는 코드가 없다는 것을 소스에서 확인하고 고른다.
- **요소를 전부 지웠다 다시 만드는 방식을 쓰지 않는다.** 재생성 도중 클릭 대상과 히트테스트 영역이
  교체되어 엉뚱한 네이티브 동작(창 크기 변경)이 튄다. 재사용하고 위치만 옮긴다.

## 3. 같은 영역을 노리는 다른 플러그인

- **우리 코드의 멱등성은 자기 변경만 막는다.** 남이 계속 DOM을 바꾸면 우리 감시자는 정당하게 깨어나고,
  우리가 되돌리면 상대가 깨어난다. 양쪽 다 정상 동작인데 앱이 멈춘다.
- **문서에 "하나만 켜라"라고 적는 것으로는 아무것도 막지 못한다.** 실제로 같은 사고가 그대로 재발했다.
  → 코드로 막는다. `app.plugins.enabledPlugins`와 컨테이너 안의 외부 노드를 보고, 충돌이면
  화면 계층을 **켜지 않고** `Notice`만 띄운다 (`src/tab-groups/guard.ts`).
- **판정은 `onLayoutReady` 직후 한 번에 끝낸다.** 루프에 빠진 뒤에는 그 안내조차 표시할 수 없다.
- **시험용으로 설치한 남의 플러그인은 검증이 끝나면 지운다.** 기능을 이식한 시점이 곧 제거 시점이다.
  꺼두는 것만으로는 다음에 누가 켠다.

## 4. 멈췄을 때 밖에서 진단하는 법

UI가 죽으면 DevTools를 열 수 없다. 터미널에서 순서대로 본다.

```sh
# 1) 렌더러가 100%면 메인 스레드가 물린 것이다
ps aux | grep "[O]bsidian Helper" | sort -k3 -rn | head -3

# 2) 3초 표본으로 무엇을 하는지 본다
sample <pid> 3 -file /tmp/obsidian-sample.txt

# 3) 저장까지 도는 루프인지 — data.json 의 mtime 을 본다
stat -f "%Sm %N" .obsidian/plugins/*/data.json
```

읽는 법:

- `%CPU`는 프로세스 수명 평균이다. `99%`에 `ELAPSED`가 짧으면 **켜진 뒤 한 번도 쉬지 않았다**는 뜻이다.
- 스택이 `v8::MicrotasksScope::PerformCheckpoint` 아래 JIT 프레임에만 있고 Blink 레이아웃 프레임이
  없으면 CSS 레이아웃 진동이 아니라 **마이크로태스크로 스스로를 깨우는 JS 루프**다.
  `MutationObserver` 콜백이 정확히 그 부류다.
- `data.json`이 멈춘 동안 한 번도 안 쓰였으면 저장 경로가 아니라 **DOM만 도는 루프**다.

## 5. 멈춘 게 아닌데 멈춘 것처럼 보이는 경우

`inno-daily-log`에서 겪었다. 앱은 멀쩡한데 입력이 전혀 안 됐다. 자동화가 보기 모드를
읽기 전용으로 바꿔놓고 되돌리지 않은 것이었다. 읽기 모드는 설계상 입력을 받지 않는다.

- **토글 명령으로 상태를 바꾸지 않는다.** 토글은 현재 상태를 뒤집을 뿐이라 되돌릴 수 없다.
  원하는 상태를 직접 지정하는 API를 쓰고, 토글밖에 없으면 호출 전 상태를 먼저 읽어 기록한다.
- **복원은 `finally`에 둔다.** 중간에 예외가 나면 복원이 건너뛰어진다.
- **사용자의 실제 문서를 대상으로 상태를 바꾸지 않는다.** 검증은 임시 문서에서 한다.
- 모드는 워크스페이스에 저장되어 **재시작해도 남는다.** "재시작했는데도 안 된다"가 되어
  원인 추적이 늦어진다.

## 6. 배포 뒤 5초 점검

새 빌드를 vault에 배포하고 Obsidian을 재시작한 뒤, 위 1번 명령 한 줄로 렌더러 CPU를 본다.
프리즈는 켜자마자 시작되므로 이 한 번이 대부분을 잡는다.

## 7. "문제가 보고된 적 없다"를 안전으로 읽지 않는다

playmaker 조사에서 얻은 규칙이다.

- 사건 기록이 없는 것은 **안전의 증거가 아니라 표본이 없다는 뜻**일 수 있다.
  실제로 playmaker는 비활성 상태였고 기능을 켠 채 쓴 적이 없었다.
- 위험을 판정할 때는 **무증상**과 **미사용**을 구분한다. 문서에 적을 때도 나눠 적는다.
- 정적 분석으로 확정한 것과 런타임으로 확인한 것을 섞어 쓰지 않는다. 이 문서의 프리즈 2건은
  실제 발생이고, playmaker 판정은 코드만 읽은 것이다. 근거의 종류가 다르다.

"확인할 가치가 있다"고 적은 추정을 **조사해서 사실로 바꾸거나 지운다.** 추정이 문서에 남아 있으면
다음 사람이 그걸 사실로 읽는다. 이 문서의 playmaker 항목이 이틀 만에 그렇게 될 뻔했다.

## 우리 플러그인에서 이 규칙이 걸리는 자리

| 플러그인 | 패턴 | 곳 | 판정 |
| --- | --- | --- | --- |
| `my-obsidian-tools` | `MutationObserver` | 5 | **사건 발생 이력 있음.** 위 규칙 1~3이 전부 여기서 나왔다 |
| `my-obsidian-tools` | `iterateAllLeaves` · `iterateRootLeaves` | 5 | **위험 없음** (2026-09-18 조사) |
| `my-obsidian-tools` | `layout-change` 구독 | 1 | **위험 없음** (2026-09-18 조사) |
| `playmaker` | `requestAnimationFrame` | 1 | **위험 없음** (2026-09-18 조사) |
| `playmaker` | `layout-change` 구독 | 1 | **위험 없음** (2026-09-18 조사) |
| `inno-daily-log` | 상주 타이머·감시자·구독 | **0** | **위험 없음** (2026-09-18 조사) — 전부 명령 기반 |
| `inno-daily-log` | `MarkdownRenderer.render` 부모 컴포넌트 | 1 | 프리즈 아님. 느린 누수 가능성, **런타임 미확인** |
| `inno-daily-log` | `getMarkdownFiles()` 전수 순회 + 순차 read | 1 | 프리즈 아님. 명령 시 1회, **소요 시간 미측정** |

### my-obsidian-tools 순회·구독 조사 결과 (2026-09-18)

`iterateAllLeaves`·`iterateRootLeaves` 는 5곳이고, 그중 **핫패스는 하나뿐**이다.

| 호출 | 부르는 곳 | 빈도 |
| --- | --- | --- |
| `mainWindowLeaves` (`iterateRootLeaves`) | `apply()` 의 `orderedLeaves()` | **refresh 마다** — layout-change · 탭 바 DOM 변경 |
| `leafFromHeader` (`iterateAllLeaves`) | `onDragStart`, 탭 헤더 우클릭 | 드래그 시작·우클릭 1회 |
| `leafById` 폴백 (`iterateAllLeaves`) | 공개 `getLeafById` 가 없을 때만 | 사실상 0 |
| `aliveLeafIds` (`iterateAllLeaves`) | `start()` | 플러그인 로드 1회 |
| `sequentialDirection` (`iterateRootLeaves`) | 접힌 그룹 탭이 활성화될 때 | 드물다 |

핫패스인 `apply()` 는 열린 탭 수 N 에 대해 O(N) 이고 N 은 보통 수십 이하다.
`arrange()` 가 멱등이라 안정 상태에서는 DOM 쓰기가 0건이다(테스트로 고정).
중첩 순회나 순회 안에서의 레이아웃 읽기는 없다. `layout-change` 콜백도 `refresh()` 한 줄이다.

**여기에 폭주 차단이 붙어 있다.** `RunawayGuard`(`src/tab-groups/guard.ts`)가 1초에 배치 20회를
넘으면 화면 계층을 끄고 안내한다(`view.ts:95`). 규칙 3이 말하는 "루프에 빠지기 전에 끊는다"가
코드로 구현된 상태다. 정상 사용의 연속 호출은 이 임계를 넘지 않는다.

`[미측정]` 실제 프레임 비용은 재지 않았다. 탭을 드래그하는 동안 Obsidian 이 탭 바를 반복
변경하면 그만큼 `refresh()` 가 도는데, 각 회차가 가볍고 멱등이라 문제로 보이지 않지만
측정한 값은 없다.

### playmaker 조사 결과 (2026-09-18)

처음에 "rAF 루프가 종료 조건 없이 도는지 확인할 가치가 있다"고 적었는데 **사실이 아니었다.
루프 자체가 없다.** 직접 확인한 내용이다.

```ts
// src/skin-controller.ts:43
scheduleReapply(): void {
  if (this.rafHandle !== null) return;        // 예약은 항상 최대 1건
  this.rafHandle = window.requestAnimationFrame(() => {
    this.rafHandle = null;
    this.reapplyAll();                        // 자신을 재예약하지 않는다
  });
}
```

- 이벤트 1회 → 프레임 1회 → 끝. 지속 루프가 아니라 **같은 프레임에 몰린 이벤트를 1회로 합치는(coalescing) 패턴**이다.
  구독 4개(`active-leaf-change`·`layout-change`·`file-open`·`css-change`)가 동시에 터져도 재적용은 한 번이다.
- `destroy()`가 `cancelAnimationFrame` 후 클래스·`<style>`을 걷어낸다. 백그라운드에서는 콜백이 지연되지만 가드 때문에 예약이 누적되지 않는다.
- **레이아웃 읽기가 저장소 전체에 0건이다.** `getBoundingClientRect`·`offsetWidth`·`getComputedStyle` 등 전수 확인.
  읽기가 없으니 규칙 1의 "읽기·쓰기가 섞여 강제 동기 레이아웃" 경로가 성립하지 않는다.
- `setInterval`·`setTimeout`·`MutationObserver`·`ResizeObserver`·`addEventListener` **전부 0건.**
  모든 구독이 `registerEvent()`를 거쳐 unload 시 자동 해제된다.
- 호스트 DOM에 노드를 넣는 곳은 `document.head`의 `<style>` 하나뿐이다. 뷰에는 **클래스 하나만 토글**하고
  스캔라인·인광은 CSS `::after`와 상속으로 그린다. 규칙 2의 침범이 없다.

**그러나 이것을 "안전하다"의 근거로 삼으면 안 된다.** playmaker는 현재 **비활성**이고
(`community-plugins.json`에 없음), `data.json`의 `skinnedPaths`가 비어 있어 **스킨을 켠 채 쓴 흔적이 없다.**
위 판정은 전부 정적 분석이며 런타임 프로파일링(실제 프레임 비용·페인트 시간)은 하지 않았다.

참고로 남기는 경로 하나 — `src/main.ts:54` `saveSettings()`가 디스크 쓰기 + `<style>` 전체 교체 +
재적용을 한 번에 하는데, vault의 rename·delete 이벤트에서 디바운스 없이 불린다.
`skinnedPaths`에 매치되는 파일이 많은 상태에서 상위 폴더를 옮기면 그만큼 연달아 돈다.
`<style>` 교체는 문서 전체 스타일 재계산을 부른다. 측정한 적 없고 증상도 없다.

### inno-daily-log 조사 결과 (2026-09-18)

**규칙 1~4에 걸리는 코드가 한 줄도 없다.** 직접 확인했다.

```
setInterval · setTimeout · MutationObserver · ResizeObserver
requestAnimationFrame · addEventListener · registerEvent          →  전 파일 0건
getBoundingClientRect · offsetWidth · getComputedStyle            →  전 파일 0건
```

**전부 명령 기반**이다. 사용자가 명령을 실행할 때만 돌고 상주하는 루프·구독·감시자가 없다.
프리즈 2건이 났던 "DOM을 감시하며 DOM을 고치는" 구조가 성립할 수 없다. 등록은 `addCommand` 4개와
`addSettingTab` 1개뿐이고 둘 다 Obsidian이 자동 해제한다.

밖에서 보였던 `innerHTML` 1곳(`main.ts:186`)은 안전하다. **자기가 만든 `div`** 를 화면 밖에 붙여
렌더한 뒤 `innerHTML` 을 **읽기만** 하고, `finally` 에서 반드시 걷는다. 호스트 소유 컨테이너가 아니라
규칙 2에 해당하지 않는다.

관찰 2건 — 위험이 아니라 사실만 적는다. 고치지 않았다.

- `MarkdownRenderer.render` 에 부모 컴포넌트로 **플러그인 자신**을 넘긴다(`main.ts:191`). 공개 타입의
  계약상 렌더러가 만든 자식 컴포넌트의 수명이 플러그인 언로드까지가 된다. 복사를 반복하면 누적될 수
  있다. 프리즈 경로는 아니고 **런타임으로 세어보지 않았다.**
- 전일 노트 탐색이 `getMarkdownFiles()` 전수 순회(오늘 기준 md 1,157개, 메모리 인덱스라 디스크 I/O 없음)
  뒤 후보를 최신순으로 순차 `await vault.read` 한다. 보통 1회, 최악은 탐색 루트 아래 데일리 노트 수
  (`Work/Daily` 194개)가 상한이다. 전부 `await` 라 메인 스레드를 동기 점유하지 않는다 —
  **느릴 수는 있어도 멈추지 않는다.** 소요 시간은 재지 않았다.

### 무증상과 미사용은 한 플러그인 안에서도 갈린다

규칙 7을 적용해 보니 셋이 서로 달랐다.

| 플러그인 | 상태 | 판정의 성격 |
| --- | --- | --- |
| `my-obsidian-tools` | 활성·실사용, 사건 4건 발생 | **실제 발생 이력** |
| `inno-daily-log` | 활성·실사용(데일리 노트 3곳에 마커 사용 중) | **무증상** — 쓰는데 증상이 없다 |
| `inno-daily-log` 의 설정 탭 | `data.json` 자체가 없음 | **미사용** — 같은 플러그인 안에서도 경로마다 다르다 |
| `playmaker` | 비활성, `skinnedPaths` 비어 있음 | **미사용** — 무증상이 아니다 |

**한 플러그인을 통째로 "무증상"이라고 적지 않는다.** 실행된 적 없는 경로는 그 안에서도 표본이 없다.

## 한 줄 요약

> **호스트 앱의 DOM은 빌려 쓰는 것이다.** 감시하며 고칠 거면 멱등하게, 남의 컨테이너에는 넣지 말고,
> 같은 자리를 노리는 상대가 있으면 코드로 물러선다.
