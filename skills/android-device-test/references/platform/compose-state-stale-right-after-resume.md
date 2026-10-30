# LifecycleResumeEffect 가 옛 설정값으로 동작한다

> 실측 출처: 개인 Android 앱 개발 중 실기기에서 겪은 것. 앱 이름은 뺐다.

## 환경
Compose + `collectAsStateWithLifecycle`.

## 증상
백그라운드에서 설정을 false 로 바꿨는데, Activity 로 돌아오면 `LifecycleResumeEffect` 가
true 로 동작한다(꺼 둔 기능이 되살아남). 곧이어 화면의 스위치는 false 로 그려진다.

## 원인
`collectAsStateWithLifecycle` 는 화면이 STOPPED 인 동안 수집을 멈춘다. RESUME 직후 첫
컴포지션의 상태는 **멈추기 전의 스냅샷**이고, 새 값은 한 프레임 뒤에 도착한다.

## 해결
RESUME 에서 결정할 값은 저장소에서 다시 읽는다: `repository.settings.first()`.

## 재발 방지
`LifecycleResumeEffect`/`onResume` 안에서 composition 의 상태를 읽어 부작용을 일으키지 말 것.
