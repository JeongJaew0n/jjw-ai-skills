# 재생 바에 앱 이름 대신 패키지 이름이 나온다

> 실측 출처: 개인 Android 앱 개발 중 실기기에서 겪은 것. 앱 이름은 뺐다.

## 환경
Android 11+ (targetSdk 36) · Galaxy S23+ / Android 16 · `MediaSessionManager.getActiveSessions()` 로 얻은 `MediaController`.

## 증상
재생 바 부제가 `Rick Astley · com.google.android.yo…` 처럼 앱 이름이 아니라 패키지 이름으로 나온다.
예외도 경고도 없다. 곰오디오처럼 이름이 제대로 나오는 앱도 있어 "가끔 그렇다" 로 넘기기 쉽다.

## 원인
Android 11 의 **패키지 가시성**. 매니페스트에 `<queries>` 로 선언하지 않은 앱은 `getApplicationInfo()` 가
`NameNotFoundException` 을 던진다. 코드가 그 실패를 `getOrDefault(packageName)` 으로 받아 패키지 이름을 띄웠다.
`MediaController.packageName` 은 알려 주면서 그 앱의 이름은 못 읽는 셈이다.

## 해결
1. 매니페스트에 **미디어 앱만** 보이게 하는 `<queries>` — `android.intent.action.MEDIA_BUTTON`,
   `android.media.browse.MediaBrowserService`. 모든 앱을 보는 `QUERY_ALL_PACKAGES` 는 쓰지 않는다.
2. 그래도 못 읽으면 패키지 이름을 띄우지 말고 **빼고** 보여 준다(제목·아티스트만).

유튜브는 1번으로 "YouTube" 가 나왔다.

## 재발 방지
다른 앱의 이름·정보를 읽는 코드를 쓰면 매니페스트 `<queries>` 부터 본다.
