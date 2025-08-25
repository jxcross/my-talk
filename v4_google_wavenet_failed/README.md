# MyTalk - Google Wavenet TTS 지원 버전

## 🎯 주요 기능

### 1. 다중 TTS 엔진 지원
- **Google Cloud Wavenet TTS** (고품질 AI 음성)
- **gTTS** (Google Translate TTS)
- **pyttsx3** (로컬 TTS)
- **브라우저 TTS** (폴백)

### 2. Google Drive OAuth 2.0 동기화
- 개인 Google Drive 직접 연결
- 실시간 동기화 및 백업
- 오프라인/온라인 모드 지원

### 3. 스크립트 생성 및 관리
- AI 기반 다양한 스타일 스크립트 생성
- TED, 팟캐스트, 일상 대화 버전
- 한국어 번역 자동 생성

## 📦 설치 방법

### 1. Python 패키지 설치
```bash
pip install -r requirements.txt
```

### 2. 추가 패키지 (선택사항)
```bash
# Google Cloud TTS (Wavenet) 지원
pip install google-cloud-texttospeech

# 음성 품질 향상을 위한 추가 패키지
pip install soundfile librosa
```

## 🔧 설정 방법

### 1. LLM API 키 설정
지원하는 LLM 제공업체 중 하나의 API 키가 필요합니다:

- **OpenAI**: `https://platform.openai.com/api-keys`
- **Anthropic**: `https://console.anthropic.com/`
- **Google AI**: `https://makersuite.google.com/app/apikey`

### 2. Google Drive OAuth 2.0 설정 (선택사항)

#### 단계별 설정:
1. [Google Cloud Console](https://console.cloud.google.com/) 접속
2. 새 프로젝트 생성 또는 기존 프로젝트 선택
3. **Google Drive API** 활성화
4. **OAuth 2.0 클라이언트 ID** 생성:
   - 애플리케이션 유형: "데스크톱 애플리케이션"
   - 이름: "MyTalk OAuth Client"
5. **JSON 파일 다운로드** 후 앱에서 설정

### 3. Google Cloud TTS (Wavenet) 설정 (선택사항)

#### 고품질 AI 음성을 위한 설정:

1. [Google Cloud Console](https://console.cloud.google.com/) 접속
2. **Cloud Text-to-Speech API** 활성화
3. **서비스 계정** 생성:
   - 역할: "Cloud Text-to-Speech 클라이언트"
4. **JSON 키 파일 다운로드**
5. 앱의 설정에서 JSON 내용 입력

#### 비용 정보:
- **무료 할당량**: 월 100만 문자
- **Standard 음성**: 100만 문자당 $4.00
- **Wavenet 음성**: 100만 문자당 $16.00
- **Neural2 음성**: 100만 문자당 $16.00

## 🚀 실행 방법

```bash
streamlit run main.py
```

## 🎤 TTS 엔진 비교

| 엔진 | 품질 | 속도 | 비용 | 언어 지원 | 특징 |
|------|------|------|------|-----------|------|
| **Wavenet** | 🌟🌟🌟🌟🌟 | 🌟🌟🌟 | 💰💰💰 | 40+ | AI 기반, 자연스러운 억양 |
| **gTTS** | 🌟🌟🌟 | 🌟🌟🌟🌟 | 무료 | 100+ | 안정적, 다양한 언어 |
| **pyttsx3** | 🌟🌟 | 🌟🌟🌟🌟🌟 | 무료 | 제한적 | 완전 오프라인 |
| **브라우저 TTS** | 🌟🌟 | 🌟🌟🌟🌟🌟 | 무료 | 다양 | 설치 불필요 |

## 🎛️ Wavenet 고급 설정

### 사용 가능한 음성
- **영어**: `en-US-Wavenet-A~J` (남성/여성)
- **한국어**: `ko-KR-Wavenet-A~D`
- **일본어**: `ja-JP-Wavenet-A~D`
- **기타**: 40+ 언어 지원

### 음성 조정 옵션
- **말하기 속도**: 0.25x ~ 4.0x
- **피치 조정**: -20 ~ +20 semitones
- **음성 효과**: 강조, 휴지 등

## 🛠️ 문제 해결

### TTS 관련 문제

1. **Wavenet TTS 실패**
   ```
   Google Cloud 인증 확인 → JSON 키 재설정
   ```

2. **gTTS 연결 오류**
   ```
   인터넷 연결 확인 → VPN/방화벽 설정 확인
   ```

3. **pyttsx3 오류**
   ```bash
   # Windows
   pip install pywin32
   
   # macOS
   pip install pyobjc-core pyobjc
   
   # Linux
   sudo apt-get install espeak espeak-data libespeak-dev
   ```

### Google Drive 동기화 문제

1. **OAuth 인증 실패**
   - 브라우저에서 쿠키/캐시 삭제
   - 다른 브라우저 사용 시도

2. **API 할당량 초과**
   - Google Cloud Console에서 할당량 확인
   - 프로젝트 결제 계정 설정

### 일반적인 해결 방법

1. **패키지 재설치**
   ```bash
   pip uninstall -r requirements.txt
   pip install -r requirements.txt
   ```

2. **캐시 초기화**
   ```bash
   rm -rf ~/.streamlit/
   rm token.pickle credentials.json
   ```

## 📁 파일 구조

```
mytalk/
├── main.py                 # 메인 애플리케이션
├── tts_module.py          # TTS 통합 모듈
├── requirements.txt       # 필요 패키지 목록
├── mytalk_data/          # 로컬 데이터 폴더
│   ├── scripts/          # 생성된 스크립트
│   ├── audio/            # 음성 파일
│   └── metadata/         # 프로젝트 메타데이터
├── temp_backups/         # 임시 백업
├── credentials.json      # OAuth 클라이언트 정보
└── token.pickle          # OAuth 토큰 캐시
```

## 🔒 보안 주의사항

1. **API 키 보안**
   - API 키를 소스코드에 하드코딩하지 마세요
   - 환경변수나 설정 파일 사용 권장

2. **Google 인증 정보**
   - `credentials.json`과 `token.pickle` 파일을 안전하게 보관
   - 공유하지 말고 `.gitignore`에 추가

3. **개인정보 보호**
   - 생성된 스크립트에 개인정보 포함 주의
   - Google Drive 동기화 시 개인정보 처리방침 확인

## 🆕 업데이트 내역

### v3.2 - Wavenet TTS 지원
- Google Cloud Text-to-Speech API 통합
- Wavenet 고품질 AI 음성 지원
- 다중 TTS 엔진 자동 폴백 시스템
- 음성 파라미터 세부 조정 기능

### v3.1 - OAuth 2.0 Google Drive
- OAuth 2.0 기반 Google Drive 연동
- 실시간 동기화 및 충돌 해결
- 오프라인 모드 지원
- 자동 백업 및 복원 기능

## 📞 지원

문제가 발생하거나 기능 제안이 있으시면:

1. **GitHub Issues** 등록
2. **로그 파일** 확인 (`~/.streamlit/logs/`)
3. **시스템 정보** 수집 (`pip list`, Python 버전)

## 📜 라이선스

이 프로젝트는 MIT 라이선스 하에 배포됩니다.

---

**MyTalk v3.2** - AI 기반 영어 말하기 학습 앱
Google Wavenet TTS 지원으로 더욱 자연스러운 음성 학습 경험을 제공합니다.