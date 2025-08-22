# MyTalk - 개인용 영어 말하기 학습 앱

## 🚀 빠른 시작

### 1. 설치

```bash
# 가상환경 생성 (권장)
python -m venv mytalk_env
source mytalk_env/bin/activate  # Windows: mytalk_env\Scripts\activate

# 패키지 설치
pip install -r requirements.txt
```

### 2. 실행

```bash
streamlit run main.py
```

브라우저가 자동으로 열리며 `http://localhost:8501`에서 앱이 실행됩니다.

## 📱 모바일에서 사용하기

### 같은 WiFi 네트워크에서:
1. PC에서 앱 실행 후 나타나는 Network URL 확인 (예: `http://192.168.0.10:8501`)
2. 모바일 브라우저에서 해당 주소 입력
3. 브라우저 메뉴 → "홈 화면에 추가"로 앱처럼 사용

### 외부에서 접속 (Ngrok 사용):
```bash
# ngrok 설치
pip install pyngrok

# 터널 생성
ngrok http 8501
```

## ⚙️ 초기 설정

### 1. API Key 설정
- 앱 실행 → 설정 탭 → LLM 설정
- Provider 선택 (OpenAI 권장)
- API Key 입력

### 2. API Key 발급 방법

#### OpenAI (권장)
1. https://platform.openai.com 접속
2. API Keys 메뉴에서 새 키 생성
3. 월 $5~10 예상 비용

#### Anthropic
1. https://console.anthropic.com 접속
2. API Keys에서 키 생성

#### Google
1. https://makersuite.google.com/app/apikey 접속
2. API Key 생성

## 💰 예상 비용

| 항목 | 월 비용 |
|------|---------|
| OpenAI API (GPT-4o-mini) | $5~10 |
| TTS (Edge TTS) | 무료 |
| 호스팅 (로컬) | 무료 |
| **총 비용** | **$5~10** |

## 🎯 주요 기능

### 📝 스크립트 생성
- 텍스트, 이미지, 파일 입력 지원
- 다양한 카테고리 (일상, 비즈니스, 여행 등)
- 자동 음성 생성 (TTS)

### 🎯 영어 연습
- TED Talk 스타일 (3분 스피치)
- Podcast 대화 형식
- 일상 대화 연습
- 영어/한국어 동시 제공

### 📚 스크립트 관리
- 저장/검색/삭제
- 카테고리별 분류
- 날짜별 자동 정렬

### 🔊 음성 기능
- 7가지 원어민 음성 선택
- 무제한 재생
- 오프라인 재생 (저장 후)

## 🛠️ 문제 해결

### "API Key가 유효하지 않습니다"
- API Key 재확인
- 결제 카드 등록 확인 (OpenAI)
- API 사용량 한도 확인

### 음성이 재생되지 않음
- 인터넷 연결 확인
- 다른 음성(Voice) 선택 시도
- 브라우저 오디오 권한 확인

### 모바일에서 레이아웃 깨짐
- 브라우저 새로고침
- 데스크톱 모드 해제
- Chrome/Safari 최신 버전 사용

## 📈 사용 팁

### 효과적인 학습 방법
1. **매일 1개 스크립트**: 꾸준한 학습이 중요
2. **쉐도잉 연습**: 음성 따라 말하기
3. **카테고리 집중**: 한 주제를 깊게 학습
4. **복습 활용**: 저장된 스크립트 반복 학습

### 프롬프트 작성 팁
- 구체적인 상황 설명: "카페에서 커피 주문하기"
- 레벨 명시: "초급자용", "비즈니스 영어"
- 길이 지정: "5문장", "2분 대화"

## 🔒 데이터 보안

- 모든 데이터는 로컬 저장 (mytalk.db)
- API Key는 세션에만 저장 (재시작시 재입력 필요)
- Google Drive 연동은 선택사항

## 🆕 업데이트 예정

- [ ] 음성 녹음 및 비교 기능
- [ ] 발음 평가 기능
- [ ] 학습 통계 대시보드
- [ ] 단어장 기능
- [ ] PDF 내보내기

## 📞 지원

문제가 있거나 기능 제안이 있으시면 이슈를 남겨주세요.

---

**Version**: 1.0.0  
**License**: MIT  
**Made with**: ❤️ and Streamlit