# 로케일 시계 패턴: 앞자리 0 이 사라지고 java.time 이 예외를 낸다

> 실측 출처: 개인 Android 앱 개발 중 실기기에서 겪은 것. 앱 이름은 뺐다.

## 환경
`android.text.format.DateFormat.getBestDateTimePattern` / `java.time.DateTimeFormatter` /
`android.icu.text.DateTimePatternGenerator`. Android 16.

## 증상
1. 한국어에서 스켈레톤 `HHmm` 을 넘겨도 `H:mm` 이 나와 `09:05` 가 `9:05` 로 바뀐다.
2. 일부 로케일의 12시간제 패턴에 `B`(유연한 시간대)가 들어오면 `DateTimeFormatter.ofPattern` 이 예외.

## 원인
1. `getBestDateTimePattern` 은 시간 필드 폭을 로케일 기본값에 맞추고, 폭을 강제하는 옵션을 노출하지 않는다.
2. Android 의 `java.time` 은 CLDR 의 `B` 패턴 문자를 모른다.

## 해결
ICU 로 만들고 ICU 로 서식한다.
```kotlin
val pattern = DateTimePatternGenerator.getInstance(locale)
    .getBestPattern("HHmm", DateTimePatternGenerator.MATCH_HOUR_FIELD_LENGTH)
android.icu.text.SimpleDateFormat(pattern, locale).format(Date())
```

## 재발 방지
ICU 가 만든 패턴은 ICU 로만 서식한다. 실측: ko `09:05`/`오전 9:05`, en `09:05`/`9:05 AM`, ja `午後1:05`.
