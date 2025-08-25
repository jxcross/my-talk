# 🎙️ MyTalk - 나만의 영어 말하기 학습 앱

개인용 영어 말하기 학습을 위한 올인원 솔루션입니다. AI가 생성한 영어 스크립트를 다양한 형태로 연습할 수 있으며, 음성 합성과 번역 기능을 제공합니다.

## ✨ 주요 기능

### 🔥 핵심 기능
- **원스톱 생성**: 텍스트/이미지/파일 입력 → 영어 스크립트 + 음성 + 번역 자동 생성
- **다양한 연습 형태**: TED 3분 말하기, 팟캐스트 대화, 일상 대화
- **멀티 TTS 엔진**: gTTS, pyttsx3, edge-tts, 브라우저 TTS 지원
- **Google Drive 백업**: 자동 클라우드 저장 및 관리
- **학습 진도 추적**: 통계, 배지 시스템, 목표 설정

### 🤖 지원 AI 모델
- **OpenAI**: GPT-4o, GPT-4o-mini, GPT-4-turbo
- **Anthropic**: Claude-3 (Haiku, Sonnet, Opus)  
- **Google**: Gemini-Pro, Gemini-Pro-Vision

### 📱 모바일 친화적
- 반응형 디자인
- PWA 지원 (웹앱으로 설치 가능)
- 터치 최적화 인터페이스

## 🚀 빠른 시작

### 1. 설치

```bash
# 저장소 클론
git clone https://github.com/yourusername/mytalk.git
cd mytalk

# 가상환경 생성 (권장)
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 의존성 설치
pip install -r requirements.txt
```

### 2. 환경 설정

#### 필수: API 키 준비
다음 중 하나 이상의 API 키가 필요합니다:

- **OpenAI API**: [platform.openai.com](https://platform.openai.com)
- **Anthropic API**: [console.anthropic.com](https://console.anthropic.com) 
- **Google AI API**: [makersuite.google.com](https://makersuite.google.com)

#### 선택사항: Google Drive 연동
Google Drive 자동 백업을 원한다면:

1. [Google Cloud Console](https://console.cloud.google.com) 접속
2. 새 프로젝트 생성
3. Google Drive API 활성화
4. 서비스 계정 생성 → JSON 키 다운로드
5. JSON 파일을 앱에 업로드

### 3. 실행

```bash
streamlit run main.py
```

브라우저에서 `http://localhost:8501` 접속

## 📖 사용 방법

### 1단계: 초기 설정
1. **설정** 탭에서 API 키 입력
2. TTS 엔진 선택 (auto 권장)
3. Google Drive 연동 (선택사항)

### 2단계: 스크립트 생성
1. **스크립트 작성** 탭 접속
2. 입력 방법 선택:
   - 텍스트 직접 입력
   - 이미지 업로드 (AI가 설명)
   - 파일 업로드 (.txt, .md)
3. 생성할 버전 선택:
   - ✅ 원본 스크립트 (필수)
   - ☑️ TED 3분 말하기
   - ☑️ 팟캐스트 대화  
   - ☑️ 일상 대화
4. **스크립트 생성하기** 버튼 클릭
5. 결과 확인 후 저장

### 3단계: 연습하기
1. **연습하기** 탭에서 저장된 스크립트 선택
2. 원하는 버전 탭 클릭
3. 오디오 재생하며 따라 읽기
4. 반복 학습으로 유창성 향상

### 4단계: 진도 관리
1. **내 스크립트** 탭에서 학습 이력 확인
2. 통계 및 배지 획득 상황 점검
3. 목표 설정 및 달성 확인

## 🛠️ 고급 설정

### TTS 엔진별 특징

| 엔진 | 장점 | 단점 | 권장 상황 |
|------|------|------|-----------|
| **gTTS** | 고품질, 안정적 | 인터넷 필요 | 일반적 사용 |
| **pyttsx3** | 오프라인 | 음질 제한적 | 인터넷 불안정시 |
| **edge-tts** | 매우 고품질 | 가끔 불안정 | 최고 음질 원할 때 |
| **브라우저 TTS** | 설치 불필요 | 브라우저 의존적 | 백업용 |

### 모바일에서 사용하기

1. **모바일 브라우저에서 접속**
   ```
   http://your-server-ip:8501
   ```

2. **PWA로 설치** (Chrome, Safari)
   - 브라우저 메뉴 → "홈 화면에 추가"
   - 네이티브 앱처럼 사용 가능

3. **최적화 팁**
   - 세로 모드 권장
   - WiFi 환경에서 사용
   - 브라우저 TTS 활용

### Google Drive 폴더 구조

```
My Drive/
└── GDRIVE_API/
    └── MyTalk/
        ├── 2025/
        │   ├── 01/
        │   │   ├── 20250122_1630_AI의미래/
        │   │   │   ├── metadata.json
        │   │   │   ├── original_script.txt
        │   │   │   ├── original_audio.mp3
        │   │   │   ├── korean_translation.txt
        │   │   │   ├── ted_script.txt
        │   │   │   ├── ted_audio.mp3
        │   │   │   ├── podcast_script.txt
        │   │   │   ├── podcast_audio.mp3
        │   │   │   ├── daily_script.txt
        │   │   │   ├── daily_audio.mp3
        │   │   │   └── README.md
        │   │   └── ...
        │   └── ...
        └── ...
```

## 🔧 문제 해결

### 일반적인 문제

**Q: TTS가 작동하지 않습니다**
```bash
# TTS 패키지 재설치
pip uninstall gtts pyttsx3 edge-tts
pip install gtts pyttsx3 edge-tts

# 또는 브라우저 TTS 사용
```

**Q: API 키 오류가 발생합니다**
- API 키가 올바른지 확인
- API 사용량/크레딧 확인
- 네트워크 연결 상태 확인

**Q: Google Drive 연동이 안됩니다**
- JSON 파일이 올바른 서비스 계정 키인지 확인
- Google Drive API가 활성화되어 있는지 확인
- 권한 설정 확인

**Q: 모바일에서 느려요**
- TTS 엔진을 'auto'로 설정
- 브라우저 TTS 사용
- 캐시 정리

### 성능 최적화

```python
# 캐시 크기 조정 (기본: 500MB)
cache_manager = SmartCacheManager(max_size_mb=200)

# TTS 엔진 우선순위 변경
tts_manager.engine_priorities = ['pyttsx3', 'gTTS', 'edge-tts']
```

## 📊 데이터 관리

### 백업 및 내보내기

1. **자동 Google Drive 백업**: 설정에서 활성화
2. **수동 내보내기**: 모든 데이터를 ZIP으로 내보내기
3. **선택적 백업**: 원하는 스크립트만 백업

### 가져오기

1. **ZIP 파일에서 복원**: 전체 데이터 복원
2. **개별 스크립트 가져오기**: 특정 스크립트만 가져오기

## 🎯 활용 팁

### 효과적인 학습 방법

1. **단계적 접근**
   - 원본 스크립트로 기초 다지기
   - TED 버전으로 프레젠테이션 연습
   - 대화 버전으로 실전 준비

2. **반복 학습**
   - 하루 15-30분 꾸준히
   - 같은 스크립트 3-5번 반복
   - 녹음해서 비교하기

3. **다양한 주제**
   - 관심사 관련 주제로 시작
   - 점진적으로 난이도 높이기
   - 시사, 문화, 기술 등 다양하게

### 맞춤형 설정

```python
# 개인 선호에 맞는 설정
user_preferences = {
    'tts_speed': 'normal',  # slow, normal, fast
    'script_length': 'medium',  # short, medium, long
    'difficulty': 'intermediate',  # beginner, intermediate, advanced
    'focus_area': 'pronunciation'  # vocabulary, grammar, pronunciation
}
```

## 🔒 보안 및 개인정보

- **로컬 우선**: 모든 데이터는 우선 로컬에 저장
- **API 키 보호**: 브라우저에만 저장, 서버 전송 안함
- **선택적 클라우드**: Google Drive는 선택사항
- **데이터 소유권**: 모든 생성 데이터는 사용자 소유

## 🛣️ 로드맵

### v2.1 (예정)
- [ ] 실시간 발음 평가
- [ ] 그룹 스터디 기능
- [ ] 더 많은 언어 지원
- [ ] 모바일 앱 (React Native)

### v3.0 (계획)
- [ ] AI 튜터 모드
- [ ] 실시간 대화 연습
- [ ] 커뮤니티 기능
- [ ] 더 많은 AI 모델 지원

## 🤝 기여하기

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)  
5. Open a Pull Request

## 📄 라이선스

이 프로젝트는 MIT 라이선스 하에 배포됩니다. 자세한 내용은 `LICENSE` 파일을 참조하세요.

## 👨‍💻 개발자

**Sunggeun Han**
- 이메일: mysomang@gmail.com
- GitHub: [@sunggeunhan](https://github.com/sunggeunhan)

## 🙏 감사의 말

- OpenAI, Anthropic, Google의 훌륭한 AI 모델들
- Streamlit 커뮤니티의 지속적인 지원
- 모든 테스터와 피드백 제공자들

---

**MyTalk v2.0 - 당신의 영어 실력을 한 단계 높여보세요! 🚀**

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://python.org)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.31+-red.svg)](https://streamlit.io)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)