# TYPE_APPLICATION_OVERLAY 창이 상태바·내비게이션 바를 덮지 못한다

> 실측 출처: 개인 Android 앱 개발 중 실기기에서 겪은 것. 앱 이름은 뺐다.

## 환경
Android 8(O) 이상 전부. 실측: Galaxy S23+ / Android 16.

## 증상
`SYSTEM_ALERT_WINDOW` 로 만든 `TYPE_APPLICATION_OVERLAY` 창을 `MATCH_PARENT` + `FLAG_LAYOUT_NO_LIMITS`
로 띄워도 프레임이 `[0,94][1080,2214]` 로 잘리고 z-order 상 두 바가 오버레이 위에 남는다.
어떤 플래그 조합으로도 안 된다.

## 원인
Android 8 부터 의도적으로 금지됐다. 오버레이가 시스템 UI 를 가리는 것(탭재킹)을 막는 플랫폼 정책.

## 해결
**창 종류를 바꾼다.** `TYPE_ACCESSIBILITY_OVERLAY` 는 상태바·내비바·시스템 다이얼로그 위까지
덮는다. 접근성 서비스로 등록하는 것 자체가 권한이라 `SYSTEM_ALERT_WINDOW` 도 필요 없다.
실측: 상태바 영역 밝은 픽셀 0개, 아래 앱은 RESUMED 그대로.

## 재발 방지
"오버레이는 상태바를 못 덮는다" 를 **창 종류 없이** 일반화하지 말 것. 이 일반화 때문에
"완전히 덮으려면 Activity 로 전환해야 한다" 는 잘못된 전제가 생겨 반대 방향으로 한참 갔다.
