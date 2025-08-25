#!/bin/bash

# MyTalk Android App - Python 3.11 강제 사용 버전
# miniconda/conda 환경을 우회하여 Homebrew Python 3.11 사용

set -e

echo "🎙️ MyTalk Android App - Python 3.11 전용 빌드 스크립트"
echo "========================================================="

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 로그 함수
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 시스템 정보
ARCH=$(uname -m)
if [[ "$ARCH" == "arm64" ]]; then
    PLATFORM="Apple Silicon"
    HOMEBREW_PREFIX="/opt/homebrew"
else
    PLATFORM="Intel"
    HOMEBREW_PREFIX="/usr/local"
fi

# Python 3.11 경로 설정
setup_python311_environment() {
    log_info "Python 3.11 환경을 설정합니다..."
    
    # conda 환경 비활성화
    if command -v conda &> /dev/null; then
        log_info "conda 환경을 비활성화합니다..."
        conda deactivate 2>/dev/null || true
        
        # conda base 환경도 비활성화
        if [[ -n "$CONDA_DEFAULT_ENV" ]]; then
            unset CONDA_DEFAULT_ENV
        fi
    fi
    
    # PATH를 Homebrew 우선으로 설정
    export PATH="${HOMEBREW_PREFIX}/bin:${HOMEBREW_PREFIX}/sbin:/usr/bin:/bin:/usr/sbin:/sbin"
    log_info "PATH 설정: $PATH"
    
    # Python 3.11 설치 확인
    PYTHON311_PATH="${HOMEBREW_PREFIX}/bin/python3.11"
    
    if [[ ! -f "$PYTHON311_PATH" ]]; then
        log_info "Python 3.11을 설치합니다..."
        brew install python@3.11
    fi
    
    # Python 3.11 버전 확인
    if [[ -f "$PYTHON311_PATH" ]]; then
        py311_version=$("$PYTHON311_PATH" --version)
        log_success "Python 3.11 확인: $py311_version"
        export PYTHON_CMD="$PYTHON311_PATH"
    else
        log_error "Python 3.11을 찾을 수 없습니다"
        exit 1
    fi
}

# 가상환경 생성 (Python 3.11 전용)
create_venv_python311() {
    log_info "Python 3.11 가상환경을 생성합니다..."
    
    # 기존 가상환경 삭제
    if [[ -d "venv" ]]; then
        log_info "기존 가상환경을 삭제합니다..."
        rm -rf venv
    fi
    
    # Python 3.11로 가상환경 생성
    if "$PYTHON_CMD" -m venv venv; then
        log_success "Python 3.11 가상환경 생성 완료"
    else
        log_error "가상환경 생성 실패"
        exit 1
    fi
    
    # 가상환경 활성화
    source venv/bin/activate
    
    # 가상환경 내 Python 버전 확인
    venv_python_version=$(python --version)
    venv_python_path=$(which python)
    log_info "가상환경 Python: $venv_python_version"
    log_info "가상환경 Python 경로: $venv_python_path"
    
    # Python 3.11인지 확인
    if [[ "$venv_python_version" =~ "3.11" ]]; then
        log_success "✅ Python 3.11 가상환경 설정 완료"
    else
        log_error "❌ 가상환경이 Python 3.11을 사용하지 않습니다: $venv_python_version"
        exit 1
    fi
}

# Kivy 설치 (Python 3.11 호환)
install_kivy_python311() {
    log_info "Python 3.11용 Kivy를 설치합니다..."
    
    # pip 업그레이드
    pip install --upgrade pip wheel setuptools
    
    # Cython 설치 (Python 3.11 호환 버전)
    pip install "Cython>=0.29.33,<3.0"
    
    # numpy 설치 (Kivy 의존성)
    pip install "numpy>=1.21.0,<2.0"
    
    # macOS 빌드 환경변수
    export LDFLAGS="-L${HOMEBREW_PREFIX}/lib"
    export CPPFLAGS="-I${HOMEBREW_PREFIX}/include"
    export PKG_CONFIG_PATH="${HOMEBREW_PREFIX}/lib/pkgconfig"
    
    if [[ "$ARCH" == "arm64" ]]; then
        export ARCHFLAGS="-arch arm64"
    fi
    
    # 시스템 의존성 설치
    deps=("sdl2" "sdl2_image" "sdl2_ttf" "sdl2_mixer")
    for dep in "${deps[@]}"; do
        if ! brew list "$dep" &>/dev/null; then
            log_info "$dep 설치 중..."
            brew install "$dep"
        fi
    done
    
    # Kivy 설치 (Python 3.11 호환 버전)
    log_info "Kivy 2.1.0 설치 중..."
    if pip install "kivy[base]==2.1.0" --no-cache-dir; then
        log_success "Kivy 설치 성공"
    else
        log_warning "바이너리 설치 실패, 소스 빌드 시도..."
        pip install --no-binary=kivy "kivy[base]==2.1.0" --no-cache-dir
    fi
    
    # 기타 의존성
    pip install kivymd buildozer
    pip install "openai>=1.0.0" requests certifi urllib3 charset-normalizer idna
}

# Java 17 설정
setup_java17() {
    log_info "Java 17 설정..."
    
    if ! brew list --cask temurin@17 &>/dev/null; then
        log_info "Java 17 설치 중..."
        brew install --cask temurin@17
    fi
    
    export JAVA_HOME=$(/usr/libexec/java_home -v 17 2>/dev/null || echo "/Library/Java/JavaVirtualMachines/temurin-17.jdk/Contents/Home")
    export PATH="$JAVA_HOME/bin:$PATH"
    
    log_success "Java 17 설정 완료: $JAVA_HOME"
}

# Android SDK 설정
setup_android_sdk() {
    log_info "Android SDK 설정..."
    
    export ANDROID_HOME="$HOME/android-sdk"
    
    if [[ ! -d "$ANDROID_HOME/cmdline-tools/latest" ]]; then
        log_info "Android SDK 설치 중..."
        mkdir -p "$ANDROID_HOME/cmdline-tools"
        cd "$ANDROID_HOME/cmdline-tools"
        
        wget -q https://dl.google.com/android/repository/commandlinetools-mac-11076708_latest.zip
        unzip -q commandlinetools-mac-*_latest.zip
        mv cmdline-tools latest
        rm commandlinetools-mac-*_latest.zip
        
        cd - > /dev/null
    fi
    
    export PATH="$PATH:$ANDROID_HOME/cmdline-tools/latest/bin:$ANDROID_HOME/platform-tools"
    
    # Android 구성 요소 설치
    log_info "Android 구성 요소 설치 중..."
    yes | "$ANDROID_HOME/cmdline-tools/latest/bin/sdkmanager" --licenses &>/dev/null || true
    
    components=("platform-tools" "platforms;android-34" "build-tools;34.0.0" "ndk;26.1.10909125")
    for component in "${components[@]}"; do
        "$ANDROID_HOME/cmdline-tools/latest/bin/sdkmanager" "$component" &>/dev/null || log_warning "$component 설치 실패"
    done
    
    log_success "Android SDK 설정 완료"
}

# buildozer.spec 생성
create_buildozer_spec() {
    log_info "buildozer.spec 생성..."
    
    cat > buildozer.spec << 'EOF'
[app]
title = MyTalk
package.name = mytalk
package.domain = com.mytalk.app
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,json,txt,mp3
source.exclude_dirs = tests,bin,venv,.git,__pycache__,build
version = 1.0
requirements = python3,kivy==2.1.0,kivymd,openai,requests,certifi,urllib3,charset-normalizer,idna,Cython
orientation = portrait
fullscreen = 0
android.permissions = INTERNET,WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE,RECORD_AUDIO,ACCESS_NETWORK_STATE
android.archs = arm64-v8a, armeabi-v7a
android.allow_backup = True
android.api = 34
android.minapi = 21
android.ndk = 26b
android.sdk = 34

[buildozer]
log_level = 2
warn_on_root = 1

p4a.fork = kivy
p4a.branch = develop
p4a.bootstrap = sdl2
EOF

    log_success "buildozer.spec 생성 완료"
}

# 빌드 실행
build_debug() {
    log_info "디버그 빌드 시작..."
    
    # 환경변수 재설정
    export ANDROID_HOME="$HOME/android-sdk"
    export PATH="$JAVA_HOME/bin:$PATH:$ANDROID_HOME/cmdline-tools/latest/bin:$ANDROID_HOME/platform-tools"
    
    # macOS 빌드 환경변수
    export LDFLAGS="-L${HOMEBREW_PREFIX}/lib"
    export CPPFLAGS="-I${HOMEBREW_PREFIX}/include"
    export PKG_CONFIG_PATH="${HOMEBREW_PREFIX}/lib/pkgconfig"
    
    if [[ "$ARCH" == "arm64" ]]; then
        export ARCHFLAGS="-arch arm64"
    fi
    
    log_info "빌드 환경:"
    echo "  - Python: $(python --version) ($(which python))"
    echo "  - Java: $(java -version 2>&1 | head -n1)"
    echo "  - ANDROID_HOME: $ANDROID_HOME"
    
    # 빌드 실행
    if buildozer android debug; then
        log_success "🎉 빌드 성공!"
        
        if ls bin/*.apk &>/dev/null; then
            apk_file=$(ls bin/*.apk | head -1)
            log_success "APK 생성됨: $apk_file"
        fi
        
        return 0
    else
        log_error "빌드 실패"
        return 1
    fi
}

# 메인 실행 함수
main() {
    case ${1:-help} in
        "setup")
            log_info "🔧 Python 3.11 환경 설정"
            setup_python311_environment
            create_venv_python311
            install_kivy_python311
            setup_java17
            setup_android_sdk
            create_buildozer_spec
            log_success "✅ 환경 설정 완료!"
            ;;
            
        "debug")
            log_info "🛠️ 디버그 빌드"
            setup_python311_environment
            source venv/bin/activate
            setup_java17
            build_debug
            ;;
            
        "clean")
            log_info "🧹 정리"
            rm -rf venv .buildozer bin __pycache__
            log_success "정리 완료"
            ;;
            
        *)
            echo "사용법: $0 {setup|debug|clean}"
            echo ""
            echo "  setup  - Python 3.11 환경 설정"
            echo "  debug  - 디버그 빌드"
            echo "  clean  - 정리"
            ;;
    esac
}

main "$@"