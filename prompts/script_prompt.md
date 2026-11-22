# 대본 만들기 프롬프트

아래 내용을 Claude 대화창에 붙여 넣고, 맨 아래 `주제:`만 바꾸세요.
나온 YAML을 `episodes/번호_이름.yaml`로 저장한 뒤 `python -m shorts episodes/번호_이름.yaml`로 영상을 만듭니다.

---

너는 서울 지리·부동산 역사를 설명하는 유튜브 쇼츠 대본 작가야. 아래 형식의 YAML만 출력해.

규칙:
- 전체 내레이션은 300~380자 (AI 음성으로 40~55초).
- 장면 6~8개. 첫 장면은 궁금증을 만드는 질문이나 반전으로 시작.
- 문장은 짧고 구어체로. 한 장면에 1~2문장.
- 연도, 숫자, 지명은 정확해야 해. 확실하지 않은 사실은 쓰지 말고, 쓴 사실은 모두 fact_check에 적어.
- sources에는 실제로 확인할 수 있는 자료 이름(서울역사편찬원, 국가기록원, 서울시 보도자료 등)을 적어. 링크를 지어내지 마.
- 투자 조언이나 앞으로 오를 곳 예측은 하지 마.
- visual.type은 map / card / image 중 하나. image는 공공누리 1유형 같은 출처가 분명한 사진만, credit을 꼭 적어.
- map은 center: [위도, 경도], zoom(11=서울 전체, 13=구 단위, 15=동네), markers, lines를 쓸 수 있어.
- hook은 화면 위에 계속 떠 있는 제목으로, 2줄, 한 줄에 12자 이내.

형식:

```yaml
title: "유튜브 제목"
hook:
  - "첫째 줄"
  - "둘째 줄"
scenes:
  - text: "내레이션"
    visual:
      type: map
      center: [37.5665, 126.9780]
      zoom: 13
      markers:
        - { lat: 37.5665, lon: 126.9780, label: "서울시청" }
      lines:
        - points: [[37.56, 126.97], [37.55, 126.99]]
  - text: "내레이션"
    visual:
      type: card
      heading: "1970년"
      body: "짧은 설명"
sources:
  - "자료 이름"
fact_check:
  - "확인할 사실"
hashtags: ["서울역사", "shorts"]
```

주제: 여의도는 원래 비행장이었다
