# Skill 작성 규칙

이 저장소의 스킬은 사용자가 명시적으로 호출했을 때만 사용되도록 작성한다.

**이 정책은 산문이 아니라 frontmatter 로 강제한다.** description 에 부탁을 적어두는 것만으로는 지켜지지 않는다는 것이 이 저장소가 이미 겪은 실패다.

## 호출 정책

- 사용자가 `/skill-name` 또는 `$skill-name` 형태로 호출한 경우에만 해당 스킬을 사용한다.
- **이름만 언급한 경우(`"skill-name 으로 해줘"`)는 호출로 보지 않는다.** 그 경로는 Skill 도구를 거쳐야 하는데, 아래 `disable-model-invocation` 이 그것을 차단한다. AI 는 스킬을 실행하지 말고 사용자에게 슬래시 호출을 안내한다.
- 사용자의 요청 내용이 스킬의 적용 분야와 유사하다는 이유만으로 AI가 스킬을 자동 호출하거나 적용하지 않게 한다.
- `SKILL.md`의 frontmatter `description`에는 명시적 호출 방식만 트리거로 적는다.
- `description`에 "반드시 사용한다", "먼저 사용한다", "이런 요청에 적용한다"처럼 일반 요청만으로 자동 활성화를 유도하는 문구를 넣지 않는다.
- `SKILL.md` 본문에도 명시적 호출 없이 스킬을 선택하도록 지시하는 규칙을 넣지 않는다.
- 스킬을 새로 만들거나 수정할 때 위 정책을 검토하고, 기존 스킬의 자동 호출 범위를 넓히지 않았는지 확인한다.

## 필수 frontmatter

모든 스킬에 다음 두 키를 넣는다.

```yaml
user-invocable: true
disable-model-invocation: true
```

| 키 | 역할 |
|---|---|
| `user-invocable: true` | 사용자가 `/skill-name` 으로 부를 수 있게 한다. 값이 없으면 기본 허용이지만 의도를 명시한다 |
| `disable-model-invocation: true` | AI 가 Skill 도구로 이 스킬을 호출하는 것을 **차단한다.** 자동 선택과 이름 언급 호출이 함께 막힌다 |

### 키 표기를 틀리지 않는다

**하이픈이다. 언더스코어가 아니다.**

```yaml
user-invocable: true       # 올바름
user_invocable: true       # 무시된다
```

Claude Code 가 인식하는 SKILL.md frontmatter 키는 다음과 같다 (2.1.251 기준).

```
allowed-tools  disallowed-tools  argument-hint  arguments
disable-model-invocation  user-invocable  effort  when_to_use  paths
```

`claude plugin validate --strict` 는 **SKILL.md frontmatter 의 알 수 없는 키를 잡아내지 않는다.** `plugin.json` 은 경고를 내지만 SKILL.md 에는 같은 검사가 없다. 즉 오타 키는 조용히 무시되므로 사람이 직접 대조해야 한다.

## 권장 description 형태

```yaml
description: <스킬이 제공하는 기능>. 사용자가 `/skill-name` 또는 `$skill-name` 을 명시적으로 호출했을 때만 사용한다. 요청 내용이 관련 분야에 해당한다는 이유만으로 자동 사용하지 않는다.
```

이름만 나열하는 형태(`` 또는 `skill-name`을 ``)는 쓰지 않는다. `disable-model-invocation` 이 그 경로를 막으므로 description 이 지킬 수 없는 약속을 하게 된다.
