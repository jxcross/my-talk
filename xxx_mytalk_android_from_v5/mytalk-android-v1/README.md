# 🎙️ MyTalk - Android English Learning App

> **Streamlit을 Kivy + Buildozer로 변환한 안드로이드 네이티브 영어 학습 앱**

## 📱 앱 개요

MyTalk는 AI 기반 영어 학습 스크립트 생성 및 TTS(Text-to-Speech) 기능을 제공하는 안드로이드 앱입니다. 기존 Streamlit 웹 애플리케이션을 Kivy 프레임워크로 완전히 재구성하여 모바일 네이티브 경험을 제공합니다.

### ✨ 주요 기능

- 🤖 **AI 스크립트 생성**: OpenAI GPT를 활용한 다양한 형식의 영어 스크립트 생성
- 🎵 **Multi-Voice TTS**: OpenAI TTS로 역할별 음성 생성 (Host/Guest, A/B)
- 📚 **4가지 학습 형식**: 원본, TED 스타일, 팟캐스트 대화, 일상 대화
- 💾 **로컬 저장**: 오프라인 접근 가능한 프로젝트 관리
- 🎯 **스마트 연습**: 페이지네이션과 미리보기 지원
- ⚡ **성능 최적화**: 메모리 효율적인 백그라운드 처리

### 🆚 기존 Streamlit 버전 대비 개선사항

| 기능 | Streamlit 버전 | Android 앱 버전 |
|------|---------------|----------------|
| **플랫폼** | 웹 브라우저 | 안드로이드 네이티브 |
| **오프라인 사용** | ❌ 불가능 | ✅ 콘텐츠 저장 후 가능 |
| **모바일 최적화** | ⚠️ 제한적 | ✅ 완전 최적화 |
| **메모리 관리** | ⚠️ 브라우저 의존 | ✅ 효율적 관리 |
| **사용자 경험** | 🌐 웹앱 | 📱 네이티브 앱 |
| **저장 방식** | 🗄️ 서버/세션 | 💾 로컬 저장 |
| **백그라운드 처리** | ⚠️ 제한적 | ✅ 멀티스레딩 |

## 🏗️ 프로젝트 구조

```
mytalk-android/
├── main.py                    # 기본 Kivy 앱 (단순 버전)
├── main_optimized.py          # 성능 최적화 버전 ⭐ 추천
├── android_utils.py           # 안드로이드 전용 유틸리티
├── buildozer.spec            # 빌드 설정
├── requirements.txt          # Python 의존성
├── build.sh                  # 자동 빌드 스크립트
├── setup_guide.md           # 상세 설정 가이드
├── README.md                # 이 파일
├── assets/                  # 앱 리소스 (생성 필요)
│   ├── icon.png             # 앱 아이콘 (512x512)
│   └── presplash.png        # 스플래시 화면
└── .buildozer/              # 빌드 캐시 (자동 생성)
```

## 🚀 빠른 시작

### 1. 환경 준비

```bash
# Ubuntu/Linux 권장
sudo apt update
sudo apt install -y python3-pip python3-venv git zip unzip
sudo apt install -y build-essential libssl-dev libffi-dev python3-dev
sudo apt install -y openjdk-11-jdk

# Android SDK 설치 (Android Studio 또는 CLI 도구)
# 환경변수 설정
export ANDROID_HOME=$HOME/android-sdk
export PATH=$PATH:$ANDROID_HOME/cmdline-tools/latest/bin
```

### 2. 프로젝트 설정

```bash
# 프로젝트 클론 (또는 파일 다운로드)
mkdir mytalk-android && cd mytalk-android

# 제공된 파일들을 프로젝트 디렉토리에 저장:
# - main_optimized.py (메인 앱 파일)
# - android_utils.py (안드로이드 유틸리티)
# - buildozer.spec (빌드 설정)
# - requirements.txt (의존성)
# - build.sh (빌드 스크립트)

# 빌드 스크립트 실행 권한 부여
chmod +x build.sh
```

### 3. 자동 빌드

```bash
# 초기 설정 및 디버그 빌드
./build.sh debug

# 또는 단계별 실행
./build.sh setup    # 초기 설정
./build.sh debug    # 디버그 빌드
./build.sh install  # 기기에 설치
./build.sh logs     # 로그 확인
```

### 4. 수동 빌드 (고급 사용자)

```bash
# 가상환경 생성
python3 -m venv venv
source venv/bin/activate

# 의존성 설치
pip install buildozer cython kivy[base]==2.1.0 kivymd openai

# 빌드 실행
buildozer android debug

# APK 설치 (USB 디버깅 활성화된 기기)
adb install bin/mytalk-*-debug.apk
```

## 🎯 사용법

### 앱 실행 후

1. **⚙️ 설정 탭**: OpenAI API Key 입력 및 음성 설정
2. **📝 스크립트 생성**: 주제 입력 후 원하는 버전 선택
3. **🎯 연습하기**: 생성된 스크립트로 학습
4. **📚 내 스크립트**: 저장된 프로젝트 관리

### OpenAI API 설정

1. [OpenAI API 키 발급](https://platform.openai.com/api-keys)
2. 앱의 설정 탭에서 API 키 입력
3. 모델 선택 (`gpt-4o-mini` 권장 - 비용 효율적)
4. 음성 설정 (voice1: 기본, voice2: 대화용)

## 🔧 커스터마이징

### 앱 아이콘 변경

```bash
# assets/icon.png (512x512 픽셀, PNG 형식)
# buildozer.spec에서 경로 설정:
# icon.filename = %(source.dir)s/assets/icon.png
```

### 스플래시 화면

```bash
# assets/presplash.png 생성
# buildozer.spec에서 경로 설정:
# presplash.filename = %(source.dir)s/assets/presplash.png
```

### 앱 정보 수정

`buildozer.spec` 파일에서:
```ini
title = MyTalk
package.name = mytalk
package.domain = com.mytalk.app
```

## 📊 성능 최적화 특징

### 메모리 관리
- **비동기 작업**: ThreadPoolExecutor로 백그라운드 처리
- **지연 로딩**: 필요할 때만 콘텐츠 로드
- **가비지 컬렉션**: 자동 메모리 정리
- **페이지네이션**: 대량 데이터 효율적 처리

### 저장소 최적화
- **로컬 저장**: JsonStore + 파일 시스템
- **임시 파일 관리**: 자동 정리 시스템
- **청크 단위 I/O**: 대용량 파일 효율적 처리

### 네트워크 최적화
- **연결 상태 감지**: 네트워크 확인 후 API 호출
- **타임아웃 설정**: 30초 제한으로 응답성 보장
- **에러 복구**: 재시도 로직

## 🐛 문제 해결

### 빌드 오류

**Java 버전 문제**
```bash
export JAVA_HOME=/usr/lib/jvm/java-11-openjdk-amd64
java -version  # Java 11 확인
```

**NDK 경로 오류**
```bash
# buildozer.spec에서 NDK 경로 명시
android.ndk = 23b
```

**권한 오류**
```bash
sudo chown -R $USER:$USER ~/.buildozer
```

### 런타임 오류

**API 연결 실패**
- OpenAI API 키 확인
- 네트워크 연결 상태 확인
- API 사용량 및 결제 상태 확인

**오디오 재생 실패**
- 기기 볼륨 확인
- 헤드폰/스피커 연결 확인
- 오디오 권한 허용

**저장소 접근 실패**
- 저장소 권한 허용
- 저장 공간 충분한지 확인

## 🚀 배포

### Google Play Store

1. **릴리즈 빌드**
```bash
./build.sh release
```

2. **Play Console 업로드**
- AAB 형식 권장
- 앱 서명 Google Play에서 관리

### 직접 배포 (APK)

1. **서명된 APK 생성**
2. **웹사이트/클라우드에 업로드**
3. **사용자 안내**: "알 수 없는 소스" 허용 필요

## 🔄 업데이트 및 유지보수

### 의존성 업데이트

```bash
# Kivy 업데이트
pip install --upgrade kivy

# OpenAI 라이브러리 업데이트
pip install --upgrade openai

# 빌드 도구 업데이트
pip install --upgrade buildozer
```

### 기능 추가

1. **새 탭 추가**: `TabbedPanelItem` 상속
2. **새 기능**: 기존 탭 클래스 확장
3. **UI 개선**: KivyMD 위젯 활용

## 🤝 기여하기

### 개발 환경 설정

```bash
git clone <repository>
cd mytalk-android
python3 -m venv dev-env
source dev-env/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt  # 개발용 의존성
```

### 코드 스타일

- **PEP 8** 준수
- **Type hints** 사용
- **Docstring** 작성 (Google 스타일)
- **Error handling** 필수

### 테스트

```bash
# 유닛 테스트
python -m pytest tests/

# 통합 테스트
./build.sh debug
./build.sh install
```

## 📄 라이선스

이 프로젝트는 MIT 라이선스를 따릅니다.

## 🙏 감사의 말

- **Kivy**: 크로스플랫폼 UI 프레임워크
- **OpenAI**: GPT 및 TTS API 제공
- **Buildozer**: 안드로이드 빌드 도구
- **Python Community**: 풍부한 생태계

## 📞 지원

- **이슈 리포트**: GitHub Issues
- **기능 요청**: GitHub Discussions
- **문서 개선**: Pull Requests 환영

---

**🎉 MyTalk로 스마트한 영어 학습을 시작하세요!**

> **개발 팁**: `main_optimized.py`를 메인 파일로 사용하면 최고의 성능을 얻을 수 있습니다. 메모리 사용량이 최적화되어 있고 백그라운드 처리가 효율적입니다.


---
||||||||||||||||

---
# JDK 17 설치 에러 발생시
---

문제를 확인했습니다. Java 17이 설치되었지만 여전히 Java 8이 사용되고 있습니다. JAVA_HOME 경로가 잘못 설정되어 있네요. 수정하겠습니다.추가로 Android SDK 구성 요소 설치 함수도 수정하겠습니다:이제 문제를 해결하기 위해 다음 단계를 따라해보세요:

## 🔧 즉시 해결 방법

### 1. 현재 Java 상황 점검
```bash
# 설치된 Java 버전들 확인
/usr/libexec/java_home -V

# 현재 JAVA_HOME 확인
echo $JAVA_HOME

# 현재 사용 중인 Java 확인
java -version
which java
```

### 2. Java 17 수동 설치 및 설정
```bash
# 기존 temurin@17 제거 후 재설치
brew uninstall --cask temurin@17 2>/dev/null || true
brew install --cask temurin@17

# Java 17이 올바르게 설치되었는지 확인
/usr/libexec/java_home -v 17

# 환경변수 설정
export JAVA_HOME=$(/usr/libexec/java_home -v 17)
export PATH="$JAVA_HOME/bin:$PATH"

# 확인
java -version
```

### 3. 수정된 스크립트 재실행
```bash
# 새로운 터미널 세션에서 실행
./build_macos_fixed.sh setup
```

### 4. 만약 여전히 문제가 있다면 Oracle JDK 17 설치

```bash
# Homebrew로 Oracle JDK 설치
brew install --cask oracle-jdk

# 또는 수동 다운로드
# https://www.oracle.com/java/technologies/javase/jdk17-archive-downloads.html
```

### 5. 문제 해결 후 확인

```bash
# Java 17이 올바르게 작동하는지 확인
export JAVA_HOME=$(/usr/libexec/java_home -v 17)
"$JAVA_HOME/bin/java" -version

# Android SDK Manager가 작동하는지 테스트
export ANDROID_HOME="$HOME/android-sdk"
"$ANDROID_HOME/cmdline-tools/latest/bin/sdkmanager" --version
```

## 🚨 만약 위 방법이 안 된다면

Java Browser Plugin이 간섭하고 있을 수 있습니다. 다음을 시도해보세요:

```bash
# 브라우저 플러그인 비활성화 후 재시도
sudo rm -rf "/Library/Internet Plug-Ins/JavaAppletPlugin.plugin"

# 환경변수 완전 재설정
unset JAVA_HOME
export JAVA_HOME=$(/usr/libexec/java_home -v 17)
export PATH="$JAVA_HOME/bin:$PATH"

# 확인
echo "JAVA_HOME: $JAVA_HOME"
java -version
```

