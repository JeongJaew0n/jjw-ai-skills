# 생체 인증만 허용하면 전체 화면 오버레이에서 빠져나올 수 없다

> 실측 출처: 개인 Android 앱 개발 중 실기기에서 겪은 것. 앱 이름은 뺐다.

## 환경
Android `android.hardware.biometrics.BiometricPrompt` (API 28+). 화면 전체를 덮는 오버레이
(`TYPE_ACCESSIBILITY_OVERLAY` 또는 `TYPE_APPLICATION_OVERLAY`)를 해제하는 수단으로 생체 인증을
쓰는 앱. 실측: Galaxy S23+ / Android 16.

## 증상
오버레이를 띄운 뒤 지문 인식이 반복 실패하자 **화면을 되찾을 방법이 없었다.**
프롬프트의 '취소' 를 눌러도 프롬프트만 닫히고 오버레이는 그대로다. 오버레이가 상태바까지
덮으면 알림 그림자도 못 내리고 설정 앱으로도 갈 수 없다. 기기가 사실상 잠긴다.

## 원인
`setAllowedAuthenticators(BIOMETRIC_WEAK)` 처럼 **생체만 허용하고 `DEVICE_CREDENTIAL`(기기
PIN/패턴/비밀번호) 대체를 막아 둔 것.**

흔한 오해가 이 결정을 부른다 — "PIN 화면은 어차피 우리 오버레이 아래 가려져 못 쓴다."
사실이 아니다. Android 는 PIN 확인 같은 **민감 화면이 뜰 때 오버레이를 강제로 걷어낸다.**
PIN 화면은 가려지지 않는다.

## 응급 탈출 (이미 갇혔을 때)
- **전원 버튼 길게 → 다시 시작.** 부팅 후 오버레이를 자동 복원하지 않는 앱이면 이걸로 풀린다.
- adb 가 붙어 있다면 `adb shell am force-stop <pkg>` — 서비스가 죽으며 오버레이 창도 내려간다.
- 접근성 오버레이라면 `adb shell settings put secure accessibility_enabled 0` 도 된다
  (단, `enabled_accessibility_services` 에 빈 문자열은 `Bad arguments` 라 `settings delete` 를 쓴다).

## 해결
1. **`DEVICE_CREDENTIAL` 을 허용한다.**
   ```kotlin
   when {
       SDK_INT >= R -> builder.setAllowedAuthenticators(BIOMETRIC_WEAK or DEVICE_CREDENTIAL)
       SDK_INT >= Q -> builder.setDeviceCredentialAllowed(true)   // deprecated
       else -> builder.setNegativeButton(...)                      // API 28 은 대체 없음
   }
   ```
   **`DEVICE_CREDENTIAL` 과 `setNegativeButton` 은 함께 쓸 수 없다** — 프레임워크가 예외를
   던진다. 시스템이 그 자리에 'PIN 사용' 버튼을 직접 넣는다.

2. **생체 프롬프트 단계에서는 오버레이를 비켜 준다.** PIN 화면과 달리 생체 프롬프트는
   오버레이 **아래**에 그려진다. 프롬프트가 떠 있는 동안만
   - 알파를 크게 낮추고(예: 0.12) — 안 그러면 프롬프트가 안 보인다
   - `FLAG_NOT_TOUCHABLE` 을 걸어 터치를 통과시킨다 — 안 그러면 '취소'·'PIN 사용' 버튼이
     눌리지 않는다. 오버레이가 터치를 삼키기 때문이다.

   (지문 센서 자체는 창과 무관하게 하드웨어가 읽으므로, 아이콘이 가려져도 인식은 된다.
   그래서 "지문은 되는데 취소가 안 눌린다" 는 헷갈리는 증상이 나온다.)

3. **안전망**: 다시 시도해도 소용없는 오류면 오버레이를 자동 해제한다.
   `BIOMETRIC_ERROR_HW_UNAVAILABLE(1)`, `LOCKOUT_PERMANENT(9)`, `NO_BIOMETRICS(11)`,
   `HW_NOT_PRESENT(12)`. 갇히는 것보다 열리는 쪽이 낫다.
   사용자 취소(`USER_CANCELED` 10, `CANCELED` 5)는 정상 경로이므로 오버레이를 유지한다.

4. **시스템이 창을 걷어갈 수 있음을 전제로 상태를 관리한다.** PIN 확인 화면이 뜨면 오버레이가
   제거되는데, 앱이 들고 있던 창 참조가 남아 있으면 `if (view != null) return` 같은 가드에
   걸려 **그 뒤로 오버레이가 영영 다시 뜨지 않는다.**
   ```kotlin
   view.addOnAttachStateChangeListener(object : View.OnAttachStateChangeListener {
       override fun onViewAttachedToWindow(v: View) = Unit
       override fun onViewDetachedFromWindow(v: View) { if (myView === v) { myView = null; myParams = null } }
   })
   ```

## 재발 방지
**해제 수단을 새로 만들 때 "그 수단이 실패하면 어떻게 빠져나오는가" 를 먼저 답할 것.**
화면 전체를 덮는 오버레이는 시스템 UI 로 우회할 수 없어, 탈출구를 앱이 스스로 보장해야 한다.
그리고 탈출구는 **실제로 쓸 수 있어야** 한다 — 보이지 않거나 눌리지 않는 버튼은 탈출구가 아니다.
