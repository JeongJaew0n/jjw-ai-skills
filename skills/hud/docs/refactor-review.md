# 리팩토링 검토 — hud

> 검토일: 2026-09-01 / 기준 커밋: `fdecefc` / 플러그인 버전 `0.2.0`
> 대상: `bin/hud.mjs` (225줄), `bin/hud` (28줄), `skills/setup/SKILL.md` (187줄), `README.md` (145줄)

근거 등급은 이 저장소의 `review-code-intent` 규약을 따른다. `실행 확인` / `코드 확정` / `미측정`.

## 요약

| 심각도 | 개수 |
|---|---|
| 높음 | 1 |
| 중간 | 3 |
| 낮음 | 2 |

4개 스킬 중 **유일하게 실행 가능한 검증을 갖춘 것**이 이 스킬이다(픽스처 + 3종 회귀). 나머지 셋은 지시문뿐이라 스스로를 검사할 방법이 없다. 이 강점은 유지해야 한다.

약점은 **아직 오지 않은 배포 경로를 위해 만든 분기**와 **같은 설명이 두 파일에 사는 것**이다.

---

## [높음] H-1. `user_invocable` 은 인식되지 않는 키다

> **해소** — 2026-09-01. `user-invocable` (하이픈)으로 고쳤다.
> `disable-model-invocation: true` 도 추가했다 (B안 채택, [결정 기록](#보류--disable-model-invocation)).

**위치** — `skills/setup/SKILL.md:4`

```yaml
user_invocable: true
```

**근거** — `코드 확정`. Claude Code 2.1.251 바이너리 frontmatter 키 목록(offset 67001012)에 있는 것은 `user-invocable`(하이픈)이다. 언더스코어 표기는 바이너리에 2회 나오지만 둘 다 내부 에러 코드 문자열 `cmd_not_user_invocable` 이며 frontmatter 키가 아니다. 런타임 검사는 `if (r.userInvocable === false)` 다.

현재 영향은 무해하다(기본값이 허용). 다만 선언이 아무 일도 하지 않고, `false` 로 뒤집으려 할 때 조용히 실패한다.

**제안**

```yaml
user-invocable: true
disable-model-invocation: true
```

`disable-model-invocation` 은 이 스킬에 특히 잘 맞는다. `settings.json` 을 편집하는 스킬이라 모델이 임의로 선택하면 안 되는데, 지금은 `description` 산문으로만 막고 있다.

같은 오타가 `review-code-intent/SKILL.md:4` 에도 있다.

---

## [중간] H-2. "사본 모드"는 아직 존재하지 않는 배포 경로를 위한 분기다

**위치** — `skills/setup/SKILL.md` 의 `## 두 가지 설치 모드`, `## Phase 1 — 실행 경로 확정`

setup 은 설치 경로에 버전 해시가 있는지로 두 모드를 가른다.

| 모드 | 조건 | 현재 |
|---|---|---|
| 직접 참조 | 경로에 해시 없음 | **실제로 쓰이는 경로** |
| 사본 | `/plugins/cache/` 아래 | 도달 불가 |

사본 모드는 마켓플레이스 설치를 전제하는데, `.claude-plugin/marketplace.json` 이 없어 그 설치 경로가 **존재하지 않는다.** `README.md` 의 `## 아직 안 된 것` 이 이 사실을 이미 기록하고 있다.

즉 Phase 1 의 절반, `VERSION` 파일, `~/.claude/hud/` 사본 관리, 제거 절차 4번이 전부 **한 번도 실행되지 않는 코드 경로**다.

**근거** — `실행 확인`. `claude plugin list` 에 `hud` 없음(마켓플레이스 미등록), 실제 설치는 심볼릭 링크.

```
~/.claude/skills/hud -> /Users/jjw/my/Dev/jjw-ai-skills/skills/hud
```

**제안** — 지우지 말고 **표시**한다. 마켓플레이스 배포는 실제 계획이므로 미리 쓴 것이 낭비는 아니지만, 검증되지 않았다는 사실은 남아야 한다.

```markdown
> **사본 모드는 아직 실행된 적이 없다.** 마켓플레이스 배포가 없어 도달 불가능한 경로다.
> 첫 마켓플레이스 설치 때 이 절을 실제로 검증한다.
```

이 스킬 자신의 규율(`설치했다고 주장하기 전에 실제로 실행해 출력을 확인한다`)을 문서 자신에게도 적용하는 것이다.

---

## [중간] H-3. 같은 설명이 두 파일에 산다

**위치** — `README.md:53` 과 `skills/setup/SKILL.md` 의 `## 왜 setup 이 필요한가`

거의 동일한 문단이 두 곳에 있다.

```
README.md:53
**플러그인은 `statusLine` 을 등록할 수 없다.** Claude Code 에서 플러그인이 제공할 수 있는
컴포넌트는 `commands / agents / skills / hooks / mcpServers / lspServers` 뿐이고 ...

setup/SKILL.md
**플러그인은 `statusLine` 을 등록할 수 없다.** 플러그인이 제공할 수 있는 컴포넌트는
`commands / agents / skills / hooks / mcpServers / lspServers` 뿐이고 ...
```

**근거** — `실행 확인`. 두 파일 모두에서 컴포넌트 목록 문장이 1회씩 검출.

Claude Code 가 컴포넌트 목록에 무언가를 추가하면(예: 언젠가 statusLine 을 허용하면) **두 곳을 다 고쳐야 하고, 한 곳만 고치면 다른 곳이 거짓이 된다.**

**제안** — 독자가 다르므로 완전 통합은 맞지 않다. README 는 사람이, SKILL.md 는 실행 주체가 읽는다. 대신 **사실의 정본을 한쪽에 두고 다른 쪽은 가리킨다.**

- 정본: `README.md` (제품 설명이 사는 곳)
- `setup/SKILL.md`: `"플러그인이 statusLine 을 등록할 수 없는 이유는 README 의 '왜 setup 을 따로 실행해야 하나' 참조. 그래서 이 스킬이 settings.json 을 편집한다."` 로 축약

---

## [중간] H-4. `@skills-dir` 자동 로드가 심볼릭 링크에서 검증되지 않았다

**위치** — `README.md:25` (`## 설치`)

```
이 저장소가 `~/.claude/skills/` 에 설치되면 `hud` 는 `hud@skills-dir` 로 자동 로드된다.
```

현재 설치는 심볼릭 링크이고, **이 문장은 아직 확인되지 않았다.**

알려진 사실은 여기까지다.

| 사실 | 근거 |
|---|---|
| 세션은 `~/.claude/skills` 의 심볼릭 링크를 따라 **컴포넌트(스킬)** 를 읽는다 | `실행 확인` — `claude plugin validate ~/.claude/skills` 경고문: `"A session loading this directory does follow them"`. 실제로 `ai-interview-tech` 가 링크를 통해 로드됨 |
| **플러그인** 스캐너가 링크를 따라가는지 | `미측정` — 확인 안 됨 |

컴포넌트 로딩과 플러그인 로딩은 다른 경로이므로 앞의 사실이 뒤를 보장하지 않는다.

**제안** — 다음 세션에서 `/hud:setup` 이 뜨는지 확인하고 결과를 `README.md` 에 기록한다. 안 뜨면 링크를 복사로 바꾼다. 그 경우 `README.md` 의 `## 업데이트`(`git pull` 만으로 끝)도 함께 틀려지므로 같이 고쳐야 한다.

---

## [낮음] H-5. 픽스처의 절대 epoch 가 노후한다

**위치** — `docs/payload-example.json` 의 `rate_limits.*.resets_at`

```json
"five_hour":  { "resets_at": 1788170000 },
"seven_day":  { "resets_at": 1788400000 }
```

`hud.mjs` 의 `untilReset()` 은 `epoch*1000 - Date.now()` 가 양수일 때만 `(3h50m)` 접미를 붙인다. 이 값들이 과거가 되면 픽스처 렌더 결과가 조용히 달라진다.

`README.md` 가 이 사실을 이미 기록하고 있어(`"resets_at 이 절대 epoch 초라서 ... 픽스처의 렌더 결과는 실행 시점에 따라 달라진다"`) 함정은 아니다. 다만 회귀 테스트의 기대값이 시간에 따라 변한다는 뜻이다.

**근거** — `코드 확정`. `bin/hud.mjs` 의 `untilReset` 구현.

**제안** — 급하지 않다. 손댄다면 픽스처를 상대 시각으로 생성하는 한 줄짜리 헬퍼가 낫다.

```sh
jq --argjson now "$(date +%s)" '.rate_limits.five_hour.resets_at = $now + 14000
  | .rate_limits.seven_day.resets_at = $now + 240000' docs/payload-example.json
```

---

## [낮음] H-6. 스킬 이름 `setup` 이 일반적이다

**위치** — `skills/setup/SKILL.md:2`

플러그인 안에서는 `hud:setup` 으로 네임스페이스가 붙어 충돌하지 않는다. 다만 파일 경로(`skills/setup/`)만 보면 무엇의 setup 인지 알 수 없고, 저장소 최상위의 다른 스킬들은 전부 자기 이름을 갖는다.

심각도가 낮은 이유는 **네임스페이스가 실제 충돌을 막고 있고**, 이름을 바꾸면 사용자 호출 문자열(`/hud:setup`)이 바뀌기 때문이다. 이득보다 비용이 크다.

**제안** — 그대로 둔다. 기록만 남긴다.

---

## 기록된 결정 — setup 스킬의 크기

`skills/setup/SKILL.md` 187줄이 실제로 만드는 것은 `settings.json` 의 4줄 병합이다. 비용 대비 이득이 약하다는 지적이 2026-08-31 세션에서 나왔고, **그대로 두기로 결정됐다.**

이 검토는 그 결정을 다시 꺼내지 않는다. 다만 재검토가 필요해질 조건을 남긴다.

- 마켓플레이스 배포를 접기로 하면 → 사본 모드(H-2)가 영구히 죽은 코드가 되므로 축약 재검토
- 다른 사람에게 배포하게 되면 → 백업·충돌 확인 가드레일의 값어치가 올라가므로 현행 유지가 더 맞아짐

---

## 손대지 않기를 권하는 것

- **`bin/hud` 런처의 존재 자체** — `env -u NODE_OPTIONS` 와 node 부재 가드는 실제 장애에서 나온 대응이고, 회귀 테스트로 검증돼 있다.
- **`bin/hud.mjs` 의 실패 정책** — "필드가 없으면 그 항목만 빠지고, 예외가 나면 아무것도 출력하지 않는다". 상태줄이라는 맥락에 정확한 선택이다.
- **`spawn 0` 원칙** (`.git/HEAD` 직접 읽기) — 렌더마다 실행되는 코드에서 이건 성능이 아니라 설계다.
- **3종 회귀 절차** — 정상 / 깨진 `NODE_OPTIONS` / node 부재. 이 저장소에서 유일하게 실행 가능한 검증이며, 다른 스킬들이 배울 지점이다.

---

## 보류 — disable-model-invocation

> **결정됨 (B안)** — 2026-09-01. `disable-model-invocation: true` 를 넣기로 했다. 아래는 그 결정에 이르기까지의 판단 근거이며, 기록으로 남긴다.

이 키는 자동 선택만 막는 게 아니라 **Skill 도구 호출을 전면 차단**한다. 그래서 정책 변경을 수반했다.

이 키는 자동 선택만 막는 게 아니라 **Skill 도구 호출을 전면 차단**한다.

```
Ask the user to run /<name> themselves
— it cannot be invoked via the <tool> tool in this session,
  by the coordinator or by workers
<X> cannot be used with <Y> tool due to disable-model-invocation.
```

`근거` — `코드 확정`. Claude Code 2.1.251 바이너리 offset 71210541.

그런데 `AGENTS.md` 는 이름 직접 언급을 허용한다.

> 사용자가 스킬 이름을 **직접 언급하거나** `/skill-name`, `$skill-name` 형태로 호출한 경우에만 해당 스킬을 사용한다.

이름 직접 언급(`"review-code-intent 로 봐줘"`)은 Skill 도구를 거쳐야 하므로, 이 키를 넣으면 **정책이 허용한 경로가 죽는다.** 즉 이 키는 저장소 정책보다 엄격하다.

선택은 둘이다.

| 안 | 내용 | 대가 |
|---|---|---|
| A (기각) | 넣지 않는다. 정책은 `description` 산문으로 유지 | 강제력이 프롬프트 수준에 머문다 |
| **B (채택)** | 넣는다. 슬래시 전용으로 좁힌다 | 이름 언급 경로 상실. `AGENTS.md` 와 4개 `description` 을 함께 고쳤다 |

채택 근거 — 이 정책이 생긴 원인이 "산문으로 부탁했는데 지켜지지 않은 것"이고 A 는 같은 층위에 머문다. 그리고 로컬 스킬 29개 중 유일하게 이 키를 쓰던 것이 `xi-implementation`(가장 자주 쓰고 오발동 위험이 큰 스킬)이었다 — 이미 같은 선택을 한 전례다.

함께 고친 것 (2026-09-01) — `AGENTS.md` 의 "직접 언급하거나" 삭제, `## 필수 frontmatter` 절 추가, 권장 description 형태에서 bare-name 제거, 4개 스킬의 `description` 과 본문 활성화 조건에서 bare-name 제거.
