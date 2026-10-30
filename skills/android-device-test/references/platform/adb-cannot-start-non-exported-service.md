# adb 로 앱의 비공개 서비스를 시작하면 권한 거부

> 실측 출처: 개인 Android 앱 개발 중 실기기에서 겪은 것. 앱 이름은 뺐다.

## 환경
Android 16, adb 37.0.1.

## 증상
```
am start-foreground-service -n <pkg>/.MyService -a <ACTION>
Error: Requires permission not exported from uid 10898
```
앱의 알림 액션과 같은 인텐트인데 adb 로 보내면 안 먹어서, 서비스 코드의 버그로 오진했다.

## 원인
`exported="false"` 인 서비스는 shell uid 에서도 시작할 수 없다. adb 특권으로 뚫리지 않는다.

## 해결
같은 액션을 쓰는 **앱 UI 경로**로 검증한다(설정 스위치 등). 테스트 편의로 서비스를
export 하지 말 것 — 공격면을 넓히는 셈이다.

## 재발 방지
없음. 이 파일이 기억이다.
