# 리팩토링 검토 — ai-interview-tech

> 검토일: 2026-09-01 / 기준 커밋: `fdecefc` / 대상: `SKILL.md` (164줄), `references/decision-axes.md` (69줄)

근거 등급은 이 저장소의 `review-code-intent` 규약을 따른다.
`실행 확인` / `코드 확정` / `미측정`.

## 요약

| 심각도 | 개수 |
|---|---|
| 높음 | 2 |
| 중간 | 2 |
| 낮음 | 2 |

내용 품질은 4개 스킬 중 가장 높다. 결정 축 카탈로그를 `references/` 로 분리해 필요할 때만 읽게 한 구조가 특히 좋다. 문제는 **본문이 선언한 것을 frontmatter 가 뒷받침하지 않는다는 것**과, **다른 두 스킬과의 산출물 경계가 정해지지 않은 것**이다.

---

## [높음] I-1. `## 활성화 조건` 이 frontmatter 로 강제되지 않는다

> **해소** — 2026-09-01. `user-invocable: true` 를 추가했다.
> `disable-model-invocation: true` 도 추가했다 (B안 채택, [결정 기록](#보류--disable-model-invocation)).

**위치** — frontmatter (2-4행) 대 본문 8-10행

본문은 이렇게 못 박는다.

```
사용자가 `/ai-interview-tech`, `$ai-interview-tech` 또는 `ai-interview-tech`를 직접
언급해 호출한 경우에만 이 스킬을 실행한다.
```

그런데 frontmatter 는 `name` 과 `description` 뿐이다. 4개 스킬 중 가장 최소이며, 슬래시 호출을 위한 `user-invocable` 도, 자동 선택을 막는 `disable-model-invocation` 도 없다. 즉 **선언은 산문이고 강제는 없다.**

Claude Code 는 이를 위한 키를 갖고 있다.

**근거** — `코드 확정`. Claude Code 2.1.251 바이너리 frontmatter 키 목록(offset 67001012)에 `disable-model-invocation`, `user-invocable`, `argument-hint`, `allowed-tools`, `when_to_use` 등이 존재한다. `disable-model-invocation` 의 안내 문구는 다음과 같다.

```
Do not replicate this skill's workflow by other means
— it is reserved for explicit user invocation.
```

**제안**

```yaml
---
name: ai-interview-tech
description: ...
user-invocable: true
disable-model-invocation: true
---
```

이 키를 넣으면 본문 `## 활성화 조건` 절은 보조 설명으로 남고, 실제 차단은 하네스가 한다. **`user_invocable`(언더스코어)로 쓰지 않는다** — 그 표기는 인식되지 않는다(형제 스킬 2개가 그 오타를 갖고 있다).

---

## [높음] I-2. 폴백 저장 경로가 `ai-plan-memory` 폴더와 충돌한다

> **해소** — 2026-09-01. 폴백 경로를 `docs/decisions/<slug>.md` 로 분리하고, `docs/plans/` 에 쓰지 않는 이유를 본문에 명시했다(제안 1안).

**위치** — `SKILL.md:155`

```
`ai-plan-memory` 스킬이 없으면 ... `docs/plans/<slug>/decision-spec.md` 에 ...
```

`ai-plan-memory` 는 같은 `docs/plans/<slug>/` 에 `spec.md`, `context.md`, `checklist.md` 세 파일을 만든다. 폴백이 **같은 디렉터리에 네 번째 파일**을 놓는다.

문제는 두 경로가 배타적이지 않다는 점이다. 인터뷰를 폴백으로 저장한 뒤 나중에 `ai-plan-memory` 를 돌리면, 같은 폴더에 `decision-spec.md` 와 `spec.md` 가 **겹치는 내용으로 공존**한다. 다음 세션이 어느 쪽을 정본으로 읽어야 하는지 알 수 없다.

**근거** — `코드 확정`. 두 스킬이 모두 `docs/plans` 를 쓴다.

```bash
$ grep -rln "docs/plans" skills/
skills/ai-interview-tech/SKILL.md
skills/ai-plan-memory/SKILL.md
```

**제안** — 둘 중 하나.

1. **폴백 경로를 분리한다** — `docs/decisions/<slug>.md`. 겹칠 일이 없어진다. 추천.
2. **폴백을 없앤다** — `ai-plan-memory` 는 이 저장소에 항상 함께 있으므로 "없으면" 조건이 사실상 발생하지 않는다. 발생한다면 그때 사용자에게 묻는 편이 낫다.

어느 쪽이든 `decision-spec.md` 가 `spec.md` 옆에 놓이는 상황은 막아야 한다.

---

## [중간] I-3. `review-code-intent` 와 같은 것을 다른 형식으로 만든다

**위치** — `SKILL.md:127-132` 대 `../../review-code-intent/SKILL.md` 의 `# 3. Intent Implementation Review`

이 스킬은 인터뷰 끝에 **리뷰 검증 체크리스트**를 만든다.

```markdown
## 리뷰 검증 체크리스트
- [ ] 스펙에서 확정한 트랜잭션 경계가 코드에 반영됐는가
- [ ] 중복 방지 키가 합의한 기준대로 사용됐는가
```

`review-code-intent` 의 세 번째 축은 **의도 항목별 측정**을 한다. 그리고 그 스킬은 의도 항목의 `출처 등급` 을 요구하며, `추론`(코드에서 유추) 항목으로는 미충족을 단정하지 못하게 막는다.

두 스킬이 서로를 모른다. 그래서 인터뷰를 거친 PR 조차 리뷰 때 의도 항목을 **코드에서 다시 역산**하게 되고, 그건 `review-code-intent` 가 스스로 "순환"이라고 부르며 금지한 상황이다.

**근거** — `코드 확정`. 양쪽 파일 대조. 두 스킬 어디에도 상대 이름이 없다.

**제안** — 이 스킬의 `## 인터뷰가 끝난 뒤` 에 한 줄, `review-code-intent` 의 `의도 항목 확정` 에 한 줄을 추가해 연결한다.

```markdown
인터뷰로 확정한 결정 스펙이 있으면, 리뷰 시 `review-code-intent` 의 의도 항목 출처를
`명시` 로 쓸 수 있다. 코드에서 역산하지 않아도 된다.
```

이 연결 하나가 `review-code-intent` 가 경계하는 역산 문제를 구조적으로 없앤다. **이번 검토에서 가장 값어치 있는 항목이다.**

---

## [중간] I-4. 자체 점검 절이 없다

**위치** — 문서 말미

`review-code-intent` 는 `# 완료 전 자체 점검` 으로 9개 항목을 두어 산출물 품질을 스스로 검사한다. 이 스킬에는 대응물이 없다. 인터뷰는 "언제 끝났는지" 가 특히 모호한 작업이라 종료 조건이 더 필요하다.

**근거** — `코드 확정`. 두 파일 구조 비교.

**제안** — 다음 정도면 충분하다.

```markdown
# 완료 전 자체 점검

- [ ] 선별한 축마다 확정 또는 명시적 보류가 있는가
- [ ] 생략한 축에 생략 이유가 붙어 있는가
- [ ] 각 질문에 추천안을 함께 냈는가 (넓게 떠넘긴 질문이 없는가)
- [ ] 확정되지 않은 것을 스펙에 적지 않았는가
- [ ] 영속화 기준(축 2개 이상 + 여러 세션)에 따라 저장 여부를 판단했는가
- [ ] 저장했다면 경로를 사용자에게 알렸는가
```

---

## [낮음] I-5. 결정 스펙에 기준 시점이 없다

**위치** — `SKILL.md:109-132` 템플릿

`review-code-intent` 는 모든 산출 문서에 `기준 커밋: {head SHA}` 와 `최종 갱신` 을 넣는다. 이 스킬의 결정 스펙에는 없다. 코드베이스를 읽고 내린 결정인데 **언제의 코드베이스인지** 가 남지 않는다. 나중에 "이 결정이 지금도 유효한가"를 판단할 기준이 사라진다.

**제안** — 템플릿 상단에 두 줄 추가.

```markdown
> 기준 커밋: `<SHA>` / 작성일: <YYYY-MM-DD>
```

---

## [낮음] I-6. 예시가 Kotlin/Spring 하나뿐이다

**위치** — `SKILL.md:77-99`

`@Transactional`, `orderRepo`, `outboxRepo` 예시가 유일하다. 스킬 자체는 언어 중립이고 결정 축도 그렇지만, 예시가 하나뿐이면 다른 스택에서 "이건 우리 얘기가 아니다"로 읽힐 수 있다.

심각도가 낮은 이유는 **예시의 목적이 형식(코드로 선택지 보여주기)을 전달하는 것**이지 특정 스택을 규정하는 게 아니기 때문이다. 지금도 목적은 달성한다.

**제안** — 급하지 않다. 손댄다면 예시를 늘리기보다 한 줄을 덧붙이는 편이 싸다.

```markdown
예시는 Kotlin/Spring 이지만 형식만 빌리면 된다 — 핵심은 선택지를 그 코드베이스의 실제
코드로 보여주는 것이다.
```

---

## 손대지 않기를 권하는 것

- **`references/decision-axes.md` 분리 구조** — 2단계에서 "판단이 서지 않을 때만" 읽게 한 설계가 정확하다. 본문에 합치면 매번 읽는 비용이 생긴다.
- **`## 전략과 전술의 구분` 절** — 이 스킬이 왜 잡담으로 흐르지 않는지를 설명하는 핵심이다. 짧고 값어치가 있다.
- **10개 결정 축의 개수** — 더 늘리면 선별 자체가 부담이 된다. `## 선별 가이드` 의 5개 자문 질문이 개수를 감당 가능하게 만들고 있다.

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
