# 서울 해설 쇼츠 제작기

대본(YAML) 하나로 AI 음성, 지도, 자막이 들어간 세로 쇼츠(1080×1920)를 만듭니다.
모든 도구가 무료입니다.

```
대본 (episodes/*.yaml)
  → AI 음성 (edge-tts, 무료)
  → 지도 (OpenStreetMap) / 카드 / 사진 그리기
  → 자막 자동 분할, 음성에 맞춰 표시
  → 영상 합치기 (FFmpeg)
  → output/<에피소드>/<에피소드>.mp4 + description.txt (설명란 문구)
```

## 윈도우에서 처음 설치하기

1. **파이썬 3.11 이상** 설치: https://www.python.org/downloads/ 에서 받아 설치할 때 "Add python.exe to PATH"를 꼭 체크합니다.
2. **FFmpeg** 설치: 명령 프롬프트(cmd)를 열고 `winget install Gyan.FFmpeg`를 입력합니다. 설치 후 cmd 창을 닫았다 다시 엽니다.
3. 이 저장소를 내려받습니다. GitHub 페이지의 초록색 Code 버튼 → Download ZIP → 압축 풀기. (git을 쓰면 `git clone`)
4. 압축을 푼 폴더에서 cmd를 열고 아래를 실행합니다.

```bat
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## 영상 만들기

```bat
.venv\Scripts\activate
python -m shorts episodes\001_gangnam.yaml
```

- 완성된 영상: `output\001_gangnam\001_gangnam.mp4`
- 설명란 문구(출처 포함): `output\001_gangnam\description.txt`
- 마지막에 "업로드 전에 꼭 확인할 사실" 목록이 나옵니다. 검수할 때 이 목록을 확인하세요.
- 음성 없이 화면만 빨리 확인하려면 `--silent`를 붙입니다.

## 새 에피소드 만들기

1. `prompts/script_prompt.md`의 내용을 Claude 대화창에 붙여 넣고 주제를 바꿉니다.
2. 나온 YAML을 `episodes\002_yeouido.yaml`처럼 저장합니다.
3. `fact_check` 목록을 보며 사실을 확인하고, 확인한 자료를 `sources`에 적습니다.
4. 영상을 만들고 확인한 뒤 유튜브 스튜디오에서 예약 업로드합니다.

주제 후보는 `docs/topics.md`에 있습니다.

## AI 캐릭터 쇼츠 만들기 (전체 화면 모드)

AI 영상 생성기로 만든 캐릭터 클립 위에 대사(AI 음성)와 자막을 얹습니다. 샘플: `episodes/101_baby_daycare.yaml`

1. `prompts/101_baby_daycare_clips.md`의 프롬프트로 Google Flow(Veo)나 Kling에서 클립을 만듭니다.
2. 클립을 `assets\clips\101\01.mp4`처럼 장면 순서대로 저장합니다.
3. `.venv\Scripts\python -m shorts episodes\101_baby_daycare.yaml`

- 대본 맨 위의 `layout: full`이 전체 화면 모드입니다.
- `characters`에 캐릭터별 목소리(`voice`), 높낮이(`pitch`), 속도(`rate`)를 정해 두고, 장면마다 `voice: 아기`처럼 캐릭터 이름을 쓰면 됩니다.
- 클립에 소리가 있으면 30% 크기로 섞습니다. 장면의 `visual`에 `clip_volume: 0`을 쓰면 끕니다.
- 실존 인물(특히 아이)의 사진·영상으로 클립을 만들지 않습니다. 업로드할 때 "변경되거나 합성된 콘텐츠"를 **예**로 표시합니다.

## 말 속도와 공백

`config.yaml`의 `rate: "+50%"`가 1.5배 속도이고, `max_gap: 0.12`가 대사 사이 공백을 0.12초까지만 남기고 잘라 냅니다.

## 저작권과 출처 규칙

- 지도는 OpenStreetMap을 쓰며, 화면과 설명란에 "© OpenStreetMap contributors"가 자동으로 들어갑니다. 받은 지도 조각은 `cache/`에 저장해 같은 지도를 다시 받지 않습니다.
- 사진(`type: image`)은 출처(`credit`)가 없으면 영상이 만들어지지 않습니다. 공공누리 1유형처럼 상업적 이용이 허락된 사진만 씁니다.
- 배경음악은 유튜브 오디오 보관함처럼 수익 창출 채널에서 써도 되는 곡만 `config.yaml`의 `bgm`에 넣습니다.
- edge-tts는 마이크로소프트의 무료 음성입니다. 수익 창출 채널에서 쓸 수 있는지 약관이 분명하지 않으므로, 수익 신청 전에 유료 음성으로 바꾸는 것을 검토합니다.

## 설정

`config.yaml`에서 목소리, 말 빠르기, 색, 배경음악을 바꿀 수 있습니다.
