# 리팩토링 검토 — ai-plan-memory

> 검토일: 2026-09-01 / 기준 커밋: `fdecefc` / 대상: `SKILL.md` (223줄)

근거 등급은 이 저장소의 `review-code-intent` 규약을 따른다.
`실행 확인` = 명령을 돌려 확인 / `코드 확정` = 파일·바이너리를 읽어 확정 / `미측정` = 메커니즘만 확인.

## 요약

| 심각도 | 개수 |
|---|---|
| 높음 | 2 |
| 중간 | 4 |
| 낮음 | 2 |

가장 시급한 것은 **유령 참조(P-2)** 다. 템플릿이 존재하지 않는 규약을 가리키고 있어, 이 스킬이 만든 checklist 를 따르는 다음 세션이 찾을 수 없는 문서를 찾게 된다.

---

## [높음] P-1. 명시적 호출 정책이 강제되지 않는다

> **해소** — 2026-09-01. `user-invocable: true` 를 추가했다.
> `disable-model-invocation: true` 도 추가했다 (B안 채택, [결정 기록](#보류--disable-model-invocation)).

**위치** — frontmatter 전체

`AGENTS.md` 는 "사용자가 명시적으로 호출한 경우에만 사용"을 저장소 정책으로 정해두었고, 이 스킬은 그것을 `description` 산문과 본문 `## 활성화 조건` 으로만 구현한다. 둘 다 모델에 대한 **부탁**이지 강제가 아니다.

Claude Code 에는 이를 구조적으로 강제하는 frontmatter 키가 있다.

```
disable-model-invocation: true
```

**근거** — `코드 확정`. Claude Code 2.1.251 바이너리의 frontmatter 키 목록(offset 67001012)에 `disable-model-invocation` 이 있고, 관련 문구가 다음과 같다.

```
... cannot be used with <tool> due to disable-model-invocation.
Do not replicate this skill's workflow by other means
— it is reserved for explicit user invocation.
```

`/skills` 화면에도 `State: (on/name-only locked by frontmatter disable-model-invocation)` 이 표시된다(offset 68067860).

**제안** — frontmatter 에 다음을 추가한다.

```yaml
user-invocable: true
disable-model-invocation: true
```

`user-invocable` 이 없으면 슬래시 호출 자체는 기본 허용이지만(런타임이 `userInvocable === false` 만 차단), 의도를 명시하는 편이 낫다. **반드시 하이픈이다** — [P-1 보충](#p-1-보충--키-표기) 참조.

### P-1 보충 — 키 표기

이 저장소의 `review-code-intent` 와 `hud/skills/setup` 은 `user_invocable`(언더스코어)을 쓴다. **그 표기는 인식되지 않는다.**

**근거** — `코드 확정`. 바이너리에서 `user_invocable` 은 2회만 나오고 둘 다 내부 에러 코드 문자열 `cmd_not_user_invocable` 이다. frontmatter 키 목록에 있는 것은 `user-invocable`(31회)이다.

이 스킬은 아직 어느 쪽도 쓰지 않으므로, 처음부터 하이픈으로 넣으면 된다.

---

## [높음] P-2. `commit_protocol` 은 존재하지 않는 규약이다

> **해소** — 2026-09-01. 실재하는 위치를 가리키도록 고치고, 커밋을 조건부 항목으로 바꿨다(P-3 도 함께 해소).
> 검증: `grep -rn commit_protocol skills/*/SKILL.md` → 0건.

**위치** — `SKILL.md:174`, checklist.md 템플릿

```markdown
- [ ] 커밋 (CLAUDE.md commit_protocol 따름)
```

**근거** — `실행 확인`.

```bash
$ grep -rn "commit_protocol" ~/.claude/CLAUDE.md skills/
skills/ai-plan-memory/SKILL.md:174:- [ ] 커밋 (CLAUDE.md commit_protocol 따름)
```

전역 `CLAUDE.md` 에 그런 키는 없다. Git 규약은 `## 4. Git` 절에 산문으로 있다. 즉 이 스킬이 생성하는 모든 checklist.md 가 **찾을 수 없는 문서를 가리킨다.**

**제안** — 실재하는 위치로 바꾼다.

```markdown
- [ ] 커밋 (저장소의 `.claude/commands/commit.md` 와 `CLAUDE.md` 의 Git 절을 먼저 읽고 따름)
```

---

## [중간] P-3. checklist 템플릿이 커밋을 기본 단계로 넣는다

> **해소** — 2026-09-01. P-2 수정에 포함됐다. 커밋 항목이 `(사용자가 커밋을 지시한 경우에만)` 조건부로 바뀌었다.

**위치** — `SKILL.md:174`

전역 `CLAUDE.md` 는 `"요청하지 않으면 커밋·푸시하지 않는다"` 를 규칙으로 둔다. 그런데 이 스킬이 생성하는 checklist 는 `## 3. 마무리` 에 커밋을 **기본 체크 항목**으로 넣는다. 체크리스트를 순차 소화하는 흐름에서 이는 사용자 지시 없는 커밋을 유도한다.

**근거** — `코드 확정`. 템플릿 174행과 전역 CLAUDE.md 4절.

**제안** — 항목을 조건부로 바꾼다.

```markdown
- [ ] (사용자가 커밋을 지시한 경우에만) 커밋 — 저장소 규약 확인 후
```

---

## [중간] P-4. 3단계 충돌 확인이 1단계의 루트 정규화를 쓰지 않는다

> **해소** — 2026-09-01. 1단계가 `ROOT` 변수를 잡고 3단계가 `"$ROOT/docs/plans/<slug>/"` 를 쓰도록 고쳤다.
> 이후 단계에서 `$ROOT` 를 쓰라는 규칙과 그 이유도 본문에 명시했다.

**위치** — `SKILL.md:46-52` 대 `SKILL.md:70-72`

1단계는 프로젝트 루트를 구하고 `"docs/plans/ 경로는 항상 이 루트 기준이다. 서브 디렉터리에서 호출돼도 루트로 정규화한다"` 고 못 박는다. 그런데 3단계 명령은 상대경로다.

```bash
ls docs/plans/<slug>/ 2>/dev/null      # cwd 기준
```

서브 디렉터리에서 호출하면 **충돌을 놓치고** 4단계가 루트에 이미 있는 폴더를 덮어쓸 수 있다. `## 동작 원칙` 의 `"충돌하는 plan 폴더가 이미 있으면 절대 조용히 덮어쓰지 않는다"` 가 무력화되는 경로다.

**근거** — `미측정`. 경로 처리 불일치는 코드 확정이지만, 실제 덮어쓰기까지 재현하지는 않았다.

**제안** — 1단계에서 구한 루트를 변수로 잡아 이후 전부 그것을 쓴다.

```bash
ROOT=$(git rev-parse --show-toplevel 2>/dev/null || pwd)
ls "$ROOT/docs/plans/<slug>/" 2>/dev/null
```

---

## [중간] P-5. `description` 이 저장소에서 유일하게 영어다

> **해소** — 2026-09-01. 한국어로 통일했다.
> P-1 작업 중 영어 절만 한국어로 바꿔 영/한 혼용이 되었고, 원래보다 나쁜 상태라 그대로 둘 수 없어 함께 처리했다.

**위치** — `SKILL.md:4-11`

나머지 3개 스킬은 한국어 `description` 이고, 전역 `CLAUDE.md` 는 `"문서도 한국어 Markdown 으로 쓴다"` 를 규칙으로 둔다. 이 스킬만 영어 본문에 한국어 괄호가 섞인 형태다.

`description` 은 모델이 스킬 선택에 쓰는 유일한 요약이므로, 표기가 갈리면 선택 품질도 갈릴 수 있다.

**근거** — `코드 확정`. 4개 SKILL.md frontmatter 비교.

**제안** — 한국어로 통일하고, 형제 스킬(`ai-interview-tech`)의 문형을 따른다.

---

## [중간] P-6. `version` 을 이 스킬만 갖고, 갱신 주체가 없다

> **해소** — 2026-09-01. `version` 을 제거했다(제안 1안). 이력은 git 이 갖는다.

**위치** — `SKILL.md:3`

```yaml
version: 1.2.0
```

4개 중 이 스킬만 `version` 을 갖는다. `hud` 는 `plugin.json` 에 버전이 있고(플러그인이라 의미가 있다), 나머지 둘은 없다. 이 값이 언제 올라가는지에 대한 규약이 저장소 어디에도 없어, 파일이 바뀌어도 `1.2.0` 에 머물러 있을 가능성이 높다. **틀린 버전은 없는 버전보다 나쁘다.**

**근거** — `코드 확정`. frontmatter 비교 + `AGENTS.md` 에 버전 규약 없음.

**제안** — 둘 중 하나. (1) 제거하고 git 이력에 맡긴다 — 추천. (2) 유지하려면 `AGENTS.md` 에 "SKILL.md 의 동작이 바뀌면 minor 를 올린다" 같은 규약을 명시한다.

---

## [중간] P-7. `ai-interview-tech` 와의 위임 계약이 여기 없다

> **해소** — 2026-09-01. `## 다른 스킬이 이 템플릿에 의존한다` 절을 추가해 매핑 표와 함께 명시했다.

**위치** — 이 스킬 전체 / `../../ai-interview-tech/SKILL.md:149-153`

`ai-interview-tech` 는 인터뷰 산출물을 이 스킬에 위임하며 매핑까지 못 박아 두었다.

| 인터뷰 산출물 | 위임 대상 |
|---|---|
| 확정된 결정 표 + 근거 | `spec.md` / `context.md` |
| 논의에서 생략한 축 | `context.md` |
| 리뷰 검증 체크리스트 | `checklist.md` |

그런데 **이 스킬은 그 계약을 모른다.** 세 파일의 템플릿을 바꾸면 저쪽 매핑이 조용히 어긋난다. 단방향 결합이다.

**근거** — `코드 확정`. 양쪽 파일 대조.

**제안** — 이 문서의 `## 파일 템플릿` 아래에 짧은 절을 추가한다.

```markdown
## 다른 스킬이 이 템플릿에 의존한다

`ai-interview-tech` 가 인터뷰 산출물을 이 세 파일에 위임한다(그 스킬의 `결정 스펙을 영속화한다` 절).
템플릿의 헤더 구조를 바꿀 때 그쪽 매핑도 함께 고친다.
```

---

## [낮음] P-8. 제목의 슬래시 접두가 형제 스킬과 다르다

**위치** — `SKILL.md:22`

```markdown
# /ai-plan-memory — 작업 계획을 docs/plans/ 에 영속화
```

나머지 셋은 `# AI Interview Tech`, `# review-code-intent`, `# hud:setup` 이다. 일관성만의 문제이므로 낮음.

**제안** — `# ai-plan-memory — 작업 계획을 docs/plans/ 에 영속화`

---

## 왜 이것들이 지금까지 안 걸렸나

`claude plugin validate` 는 스킬 frontmatter 의 **알 수 없는 키를 잡아내지 않는다.** 저장소 전체에 `--strict` 를 돌려도 통과한다.

```bash
$ claude plugin validate ./skills --strict
✔ Validation passed
```

`plugin.json` 은 알 수 없는 필드에 경고를 내지만(`engines`, `platforms` 등에서 확인), SKILL.md frontmatter 에는 같은 검사가 없다. 따라서 **오타 키는 조용히 무시된다.** 이 저장소에서는 사람이 직접 대조하는 수밖에 없다.

**근거** — `실행 확인`. `--strict` 통과 출력 및 `plugin.json` 미지원 키 경고 비교.

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
