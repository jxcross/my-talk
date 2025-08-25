# MyTalk Android App - 설치 및 빌드 가이드

## 📱 개요

MyTalk는 Kivy + Buildozer를 사용하여 기존 Streamlit 기반 영어 학습 애플리케이션을 안드로이드 네이티브 앱으로 변환한 버전입니다.

## 🛠️ 개발 환경 설정

### 1. 시스템 요구사항

**Ubuntu/Linux (권장):**
```bash
sudo apt update
sudo apt install -y python3-pip python3-venv git zip unzip
sudo apt install -y build-essential libssl-dev libffi-dev python3-dev
sudo apt install -y openjdk-11-jdk
```

**macOS:**
```bash
# Homebrew 설치 후
brew install python git
brew install --cask adoptopenjdk11
```

### 2. Android 개발 도구 설치

**Android SDK 설치:**
```bash
# Android Studio 다운로드 및 설치
# 또는 커맨드라인 도구만 설치
wget https://dl.google.com/android/repository/commandlinetools-linux-latest.zip
unzip commandlinetools-linux-latest.zip
mkdir -p ~/android-sdk/cmdline-tools/latest
mv cmdline-tools/* ~/android-sdk/cmdline-tools/latest/

# 환경변수 설정 (~/.bashrc 또는 ~/.zshrc에 추가)
export ANDROID_HOME=$HOME/android-sdk
export PATH=$PATH:$ANDROID_HOME/cmdline-tools/latest/bin
export PATH=$PATH:$ANDROID_HOME/platform-tools
```

**Android NDK 설치:**
```bash
# SDK Manager로 설치
sdkmanager "ndk;21.4.7075529"
sdkmanager "platforms;android-30"
sdkmanager "build-tools;30.0.3"
```

### 3. Python 가상환경 설정

```bash
# 프로젝트 디렉토리 생성
mkdir mytalk-android
cd mytalk-android

# 가상환경 생성 및 활성화
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate  # Windows

# 의존성 설치
pip install --upgrade pip
pip install buildozer cython
pip install kivy[base]==2.1.0
pip install kivymd
pip install openai requests
```

## 📁 프로젝트 구조

```
mytalk-android/
├── main.py              # 메인 앱 파일
├── buildozer.spec       # 빌드 설정
├── requirements.txt     # Python 의존성
├── assets/             # 앱 에셋 (아이콘, 이미지 등)
│   ├── icon.png
│   └── presplash.png
├── data/               # 데이터 파일
└── .buildozer/         # 빌드 캐시 (자동생성)
```

## 🔧 빌드 과정

### 1. 파일 준비

1. **main.py**: 제공된 Kivy 앱 코드 저장
2. **buildozer.spec**: 빌드 설정 파일 저장
3. **requirements.txt**: 의존성 목록 저장

### 2. 초기 빌드 설정

```bash
# buildozer 초기화 (이미 spec 파일이 있으면 생략)
buildozer init

# Android 요구사항 설치 (최초 1회)
buildozer android_new debug
```

### 3. 앱 빌드

**디버그 빌드:**
```bash
buildozer android debug
```

**릴리즈 빌드:**
```bash
# 키스토어 생성 (최초 1회)
keytool -genkey -v -keystore my-release-key.keystore -alias alias_name -keyalg RSA -keysize 2048 -validity 10000

# 릴리즈 빌드
buildozer android release
```

### 4. APK 설치 및 테스트

```bash
# USB 디버깅이 활성화된 안드로이드 기기에 설치
adb install bin/mytalk-1.0-arm64-v8a-debug.apk

# 또는 로그 확인하며 실행
adb logcat | grep python
```

## 🎨 UI 커스터마이징

### 1. 앱 아이콘 교체

```bash
# assets/icon.png (512x512 권장)
# buildozer.spec에서 설정:
# icon.filename = %(source.dir)s/assets/icon.png
```

### 2. 스플래시 화면

```bash
# assets/presplash.png 추가
# buildozer.spec에서 설정:
# presplash.filename = %(source.dir)s/assets/presplash.png
```

### 3. 색상 및 테마

```python
# main.py에서 Kivy 테마 설정
from kivymd.app import MDApp

class MyTalkApp(MDApp):
    def build(self):
        self.theme_cls.theme_style = "Light"  # "Dark"
        self.theme_cls.primary_palette = "Blue"
        # ... 기존 코드
```

## 🐛 트러블슈팅

### 1. 빌드 오류 해결

**Java 버전 오류:**
```bash
# Java 11 사용 확인
java -version
export JAVA_HOME=/usr/lib/jvm/java-11-openjdk-amd64
```

**NDK 경로 오류:**
```bash
# buildozer.spec에서 NDK 경로 지정
[buildozer]
android.ndk_path = /path/to/android-ndk-r21e
```

**의존성 빌드 실패:**
```bash
# 특정 패키지 제외 후 재빌드
# requirements에서 문제 패키지 제거
buildozer android clean
buildozer android debug
```

### 2. 런타임 오류 해결

**권한 오류:**
```python
# main.py에서 권한 요청
if platform == 'android':
    from android.permissions import request_permissions, Permission
    request_permissions([
        Permission.WRITE_EXTERNAL_STORAGE,
        Permission.READ_EXTERNAL_STORAGE,
        Permission.INTERNET
    ])
```

**파일 경로 오류:**
```python
# Android 저장소 경로 사용
if platform == 'android':
    from android.storage import primary_external_storage_path
    storage_path = primary_external_storage_path()
else:
    storage_path = os.path.expanduser('~')
```

### 3. 성능 최적화

**메모리 사용량 줄이기:**
```python
# 큰 파일은 스트리밍으로 처리
# 사용하지 않는 객체는 즉시 해제
# 백그라운드 작업은 Clock.schedule_* 사용
```

## 🚀 배포

### 1. Google Play Store 준비

1. **릴리즈 APK 생성**
2. **앱 서명 확인**
3. **권한 설명 준비**
4. **스크린샷 및 설명 준비**

### 2. 직접 배포 (APK)

```bash
# 서명된 APK를 웹사이트나 파일 호스팅에 업로드
# 사용자는 "알 수 없는 소스" 설치 허용 후 다운로드
```

## 📋 주요 기능 상태

✅ **구현 완료:**
- 스크립트 생성 (OpenAI GPT)
- TTS 음성 생성 (OpenAI TTS)
- 로컬 파일 저장
- 프로젝트 관리
- 설정 관리

⚠️ **제한사항:**
- 이미지 입력 기능 제외 (Kivy 파일선택기로 대체 가능)
- 오디오 합성 기능 간소화 (pydub 없이)
- 일부 고급 UI 효과 단순화

🔮 **향후 개선:**
- KivyMD를 활용한 Material Design
- 오프라인 TTS 엔진 통합
- 음성 녹음 및 비교 기능
- 클라우드 동기화

## 💡 개발 팁

1. **테스트는 자주**: 빌드 시간이 길므로 자주 테스트
2. **로그 활용**: `adb logcat`으로 에러 추적
3. **단계적 개발**: 기능을 하나씩 추가하며 테스트
4. **권한 관리**: Android 권한을 정확히 설정
5. **파일 경로**: Android와 데스크톱의 경로 차이 고려

이제 `buildozer android debug` 명령으로 APK를 빌드할 수 있습니다! 🎉