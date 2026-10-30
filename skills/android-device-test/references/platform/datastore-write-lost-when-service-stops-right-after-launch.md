# lifecycleScope.launch { 저장 } 직후 stopSelf() 하면 저장이 실행되지 않는다

> 실측 출처: 개인 Android 앱 개발 중 실기기에서 겪은 것. 앱 이름은 뺐다.

## 환경
`androidx.lifecycle:lifecycle-service` 의 `LifecycleService` + DataStore Preferences.

## 증상
서비스에서 `lifecycleScope.launch { repository.update{...} }` 를 던지고 바로 `stopSelf()`.
창은 사라졌는데 설정값은 바뀌지 않아, 앱을 다시 열면 지운 것이 되살아난다.

## 원인
`stopSelf()` → `onDestroy()` 가 `lifecycleScope` 를 취소한다. 아직 시작도 못 한 코루틴이
함께 취소돼 저장이 실행되지 않는다.

## 해결
둘 중 하나.
- 저장 코루틴 **안에서**, 저장이 끝난 뒤 `stopSelf()` 를 부른다.
- 서비스 수명과 떼어 놓는다: `lifecycleScope.launch(NonCancellable) { ... }`.

## 재발 방지
서비스를 멈추는 코드 근처의 `launch` 를 볼 때 "이게 끝나기 전에 스코프가 죽나" 를 묻는다.
