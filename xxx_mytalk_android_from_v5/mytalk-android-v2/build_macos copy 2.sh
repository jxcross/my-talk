#!/bin/bash

# MyTalk Android App - 수정된 macOS 빌드 스크립트
# Java 버전 호환성 및 최신 의존성 문제 해결

set -e  # 에러 발생 시 스크립트 종료

echo "🎙️ MyTalk Android App - macOS 빌드 스크립트 (수정됨)"
echo "======================================================="

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 시스템 정보 감지
ARCH=$(uname -m)
if [[ "$ARCH" == "arm64" ]]; then
    PLATFORM="Apple Silicon (M1/M2/M3/M4)"
else
    PLATFORM="Intel"
fi

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

# macOS 시스템 정보 출력
show_system_info() {
    log_info "시스템 정보:"
    echo "  - macOS 버전: $(sw_vers -productVersion)"
    echo "  - 아키텍처: $PLATFORM"
    echo "  - Python: $(python3 --version 2>/dev/null || echo '설치 필요')"
    echo "  - Xcode: $(xcode-select -v 2>/dev/null || echo '설치 필요')"
}

# Homebrew 확인 및 설치
install_homebrew() {
    if ! command -v brew &> /dev/null; then
        log_info "Homebrew를 설치합니다..."
        /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
        
        # Apple Silicon의 경우 PATH 추가
        if [[ "$ARCH" == "arm64" ]]; then
            echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile
            eval "$(/opt/homebrew/bin/brew shellenv)"
        fi
        
        log_success "Homebrew 설치 완료"
    else
        log_info "Homebrew가 이미 설치되어 있습니다"
        # Homebrew 업데이트
        brew update
    fi
}

# 기본 의존성 설치
install_dependencies() {
    log_info "기본 의존성을 설치합니다..."
    
    # Homebrew로 필수 패키지 설치
    brew_packages=(
        "python@3.11"
        "git"
        "wget"
        "cmake"
        "autoconf"
        "automake"
        "libtool"
        "pkg-config"
        "ninja"
        "ccache"
    )
    
    for package in "${brew_packages[@]}"; do
        if brew list "$package" &>/dev/null; then
            log_info "$package는 이미 설치되어 있습니다"
        else
            log_info "$package를 설치합니다..."
            brew install "$package"
        fi
    done
    
    # Python 심볼릭 링크 확인
    if ! command -v python3 &> /dev/null; then
        log_warning "python3 명령을 찾을 수 없습니다. Homebrew Python 경로를 확인합니다..."
        if [[ "$ARCH" == "arm64" ]]; then
            export PATH="/opt/homebrew/bin:$PATH"
        else
            export PATH="/usr/local/bin:$PATH"
        fi
    fi
    
    log_success "기본 의존성 설치 완료"
}

# Java 17 설치 (Android SDK와 호환)
install_java() {
    log_info "Java 17 설치를 확인합니다..."
    
    # 기존 Java 확인
    if command -v java &> /dev/null; then
        java_version=$(java -version 2>&1 | head -n1 | cut -d'"' -f2)
        log_info "현재 Java 버전: $java_version"
    fi
    
    # Java 17이 이미 설치되어 있는지 확인
    if /usr/libexec/java_home -v 17 &>/dev/null; then
        log_info "Java 17이 이미 설치되어 있습니다"
    else
        # OpenJDK 17 설치 (정확한 cask 이름 사용)
        log_info "OpenJDK 17을 설치합니다..."
        if ! brew list --cask temurin@17 &>/dev/null; then
            brew install --cask temurin@17
        fi
    fi
    
    # JAVA_HOME 설정 (JDK 17 사용) - 올바른 경로 찾기
    log_info "Java 17 경로를 찾는 중..."
    
    # 먼저 /usr/libexec/java_home으로 시도
    if /usr/libexec/java_home -v 17 &>/dev/null; then
        FOUND_JAVA_HOME=$(/usr/libexec/java_home -v 17)
        log_info "java_home으로 찾은 경로: $FOUND_JAVA_HOME"
    else
        # 수동으로 경로 찾기
        log_info "수동으로 Java 17 경로를 찾는 중..."
        
        possible_paths=(
            "/Library/Java/JavaVirtualMachines/temurin-17.jdk/Contents/Home"
            "/Library/Java/JavaVirtualMachines/adoptopenjdk-17.jdk/Contents/Home"
            "/Library/Java/JavaVirtualMachines/eclipse-temurin-17.jdk/Contents/Home"
        )
        
        if [[ "$ARCH" == "arm64" ]]; then
            possible_paths+=(
                "/opt/homebrew/Cellar/temurin@17/*/Contents/Home"
                "/opt/homebrew/opt/temurin@17/libexec/openjdk.jdk/Contents/Home"
            )
        else
            possible_paths+=(
                "/usr/local/Cellar/temurin@17/*/Contents/Home"
                "/usr/local/opt/temurin@17/libexec/openjdk.jdk/Contents/Home"
            )
        fi
        
        FOUND_JAVA_HOME=""
        for path in "${possible_paths[@]}"; do
            # 와일드카드 확장
            expanded_paths=($path)
            for expanded_path in "${expanded_paths[@]}"; do
                if [[ -d "$expanded_path" ]] && [[ -f "$expanded_path/bin/java" ]]; then
                    FOUND_JAVA_HOME="$expanded_path"
                    log_info "찾은 Java 17 경로: $FOUND_JAVA_HOME"
                    break 2
                fi
            done
        done
    fi
    
    # 유효한 Java 17 경로인지 검증
    if [[ -n "$FOUND_JAVA_HOME" ]] && [[ -f "$FOUND_JAVA_HOME/bin/java" ]]; then
        export JAVA_HOME="$FOUND_JAVA_HOME"
        
        # Java 버전 검증 (17인지 확인)
        java_version_check=$("$JAVA_HOME/bin/java" -version 2>&1 | head -n1)
        if [[ "$java_version_check" =~ "17\." ]] || [[ "$java_version_check" =~ "openjdk version \"17" ]]; then
            log_success "올바른 Java 17을 찾았습니다: $JAVA_HOME"
        else
            log_warning "찾은 Java가 17 버전이 아닙니다: $java_version_check"
        fi
    else
        log_error "Java 17을 찾을 수 없습니다. 수동으로 재설치해주세요."
        echo ""
        echo "다음 명령으로 재설치 시도:"
        echo "  brew uninstall --cask temurin@17"
        echo "  brew install --cask temurin@17"
        echo ""
        echo "또는 Oracle JDK 17 다운로드:"
        echo "  https://www.oracle.com/java/technologies/javase/jdk17-archive-downloads.html"
        exit 1
    fi
    
    # 환경변수를 프로필에 추가
    if ! grep -q "JAVA_HOME.*temurin-17\|JAVA_HOME.*openjdk@17" ~/.zprofile 2>/dev/null; then
        echo "" >> ~/.zprofile
        echo "# Java 17 for Android development" >> ~/.zprofile
        echo "export JAVA_HOME=\"$JAVA_HOME\"" >> ~/.zprofile
        echo "export PATH=\"\$JAVA_HOME/bin:\$PATH\"" >> ~/.zprofile
    fi
    
    # Java 17 설치 확인
    if [[ -d "$JAVA_HOME" ]]; then
        log_success "Java 17 설치 완료: $JAVA_HOME"
        # Java 버전 확인
        if "$JAVA_HOME/bin/java" -version &>/dev/null; then
            java_17_version=$("$JAVA_HOME/bin/java" -version 2>&1 | head -n1)
            log_info "Java 17 버전: $java_17_version"
        fi
    else
        log_error "Java 17 설치에 실패했습니다. 수동으로 설치해주세요:"
        echo "  brew install --cask temurin@17"
        exit 1
    fi
}

# Android SDK 설치 (최신 Command Line Tools)
install_android_sdk() {
    log_info "Android SDK 설치를 확인합니다..."
    
    ANDROID_HOME="$HOME/android-sdk"
    
    if [[ ! -d "$ANDROID_HOME" ]]; then
        log_info "Android SDK를 설치합니다..."
        
        mkdir -p "$ANDROID_HOME/cmdline-tools"
        cd "$ANDROID_HOME/cmdline-tools"
        
        # 최신 Command Line Tools 다운로드 (2024년 최신)
        log_info "최신 Android Command Line Tools 다운로드 중..."
        wget -q https://dl.google.com/android/repository/commandlinetools-mac-11076708_latest.zip
        
        unzip -q commandlinetools-mac-*_latest.zip
        mv cmdline-tools latest
        rm commandlinetools-mac-*_latest.zip
        
        log_success "Android SDK Command Line Tools 설치 완료"
    else
        log_info "Android SDK가 이미 설치되어 있습니다"
    fi
    
    # 환경변수 설정
    export ANDROID_HOME="$HOME/android-sdk"
    export PATH="$PATH:$ANDROID_HOME/cmdline-tools/latest/bin"
    export PATH="$PATH:$ANDROID_HOME/platform-tools"
    
    # 프로필에 추가
    if ! grep -q "ANDROID_HOME" ~/.zprofile 2>/dev/null; then
        {
            echo ""
            echo "# Android SDK"
            echo "export ANDROID_HOME=\"$HOME/android-sdk\""
            echo "export PATH=\"\$PATH:\$ANDROID_HOME/cmdline-tools/latest/bin\""
            echo "export PATH=\"\$PATH:\$ANDROID_HOME/platform-tools\""
        } >> ~/.zprofile
    fi
}

# Android SDK 구성 요소 설치 (최신 버전)
install_android_components() {
    log_info "Android SDK 구성 요소를 설치합니다..."
    
    # Java 17 확실히 사용하도록 설정
    if [[ -n "$JAVA_HOME" ]] && [[ -f "$JAVA_HOME/bin/java" ]]; then
        export PATH="$JAVA_HOME/bin:$PATH"
        log_info "Android SDK 설치에 Java 17 사용: $JAVA_HOME"
        
        # Java 버전 재확인
        current_java=$("$JAVA_HOME/bin/java" -version 2>&1 | head -n1)
        log_info "현재 Java 버전: $current_java"
        
        if [[ ! "$current_java" =~ "17\." ]] && [[ ! "$current_java" =~ "openjdk version \"17" ]]; then
            log_error "Java 17이 올바르게 설정되지 않았습니다."
            log_info "수동으로 Java 17을 확인해주세요:"
            echo "  /usr/libexec/java_home -V  # 설치된 Java 버전 확인"
            return 1
        fi
    else
        log_error "JAVA_HOME이 올바르게 설정되지 않았습니다: $JAVA_HOME"
        return 1
    fi
    
    # 환경변수 확인
    export ANDROID_HOME="$HOME/android-sdk"
    sdkmanager_path="$ANDROID_HOME/cmdline-tools/latest/bin/sdkmanager"
    
    if [[ ! -f "$sdkmanager_path" ]]; then
        log_error "sdkmanager를 찾을 수 없습니다: $sdkmanager_path"
        return 1
    fi
    
    # SDK Manager 라이선스 허용
    log_info "Android SDK 라이선스에 동의하는 중..."
    yes | "$sdkmanager_path" --licenses &>/dev/null || {
        log_warning "라이선스 동의 실패 - 계속 진행"
    }
    
    # 필수 구성 요소들 (최신 버전)
    components=(
        "platform-tools"
        "platforms;android-34"
        "build-tools;34.0.0"
        "ndk;26.1.10909125"
        "cmake;3.22.1"
    )
    
    for component in "${components[@]}"; do
        log_info "$component 설치 중..."
        if "$sdkmanager_path" "$component" 2>/dev/null; then
            log_success "$component 설치 성공"
        else
            log_warning "$component 설치 실패 - 계속 진행"
        fi
    done
    
    log_success "Android SDK 구성 요소 설치 완료"
}

# Python 가상환경 설정 (수정된 버전)
setup_python_env() {
    log_info "Python 가상환경을 설정합니다..."
    
    # Python 가상환경 생성
    if [[ ! -d "venv" ]]; then
        python3 -m venv venv
        log_success "가상환경 생성 완료"
    fi
    
    # 가상환경 활성화
    source venv/bin/activate
    log_info "가상환경 활성화됨"
    
    # pip 업그레이드
    pip install --upgrade pip
    
    # Cython 사전 설치 (Kivy 빌드에 필요)
    log_info "Cython 설치 중..."
    pip install "Cython>=0.29.33,<1.0"
    
    # 빌드 도구들 설치
    pip install wheel setuptools
    
    # macOS 특별 환경변수 설정
    export LDFLAGS="-L$(brew --prefix)/lib"
    export CPPFLAGS="-I$(brew --prefix)/include"
    export PKG_CONFIG_PATH="$(brew --prefix)/lib/pkgconfig"
    
    # Apple Silicon 특별 설정
    if [[ "$ARCH" == "arm64" ]]; then
        export ARCHFLAGS="-arch arm64"
        # Kivy를 위한 추가 설정
        export CC="clang"
        export CXX="clang++"
    fi
    
    # Kivy 의존성 설치 (호환 버전)
    log_info "Kivy 의존성을 설치합니다..."
    
    # 먼저 필요한 시스템 라이브러리 설치
    brew_kivy_deps=(
        "sdl2"
        "sdl2_image" 
        "sdl2_ttf"
        "sdl2_mixer"
        "gstreamer"
        "gst-plugins-base"
        "gst-plugins-good"
    )
    
    for dep in "${brew_kivy_deps[@]}"; do
        if ! brew list "$dep" &>/dev/null; then
            log_info "$dep 설치 중..."
            brew install "$dep" || log_warning "$dep 설치 실패 - 계속 진행"
        fi
    done
    
    # Kivy 설치 (최신 호환 버전)
    log_info "Kivy 설치 중..."
    pip install --no-binary=kivy kivy[base]==2.2.1 || {
        log_warning "소스에서 Kivy 빌드 실패, 바이너리 버전 시도..."
        pip install kivy[base]==2.2.1
    }
    
    # KivyMD 및 기타 의존성
    pip install kivymd
    pip install buildozer
    
    # 앱 의존성들
    pip install openai requests certifi
    
    log_success "Python 환경 설정 완료"
}

# Xcode Command Line Tools 확인 (개선된 버전)
check_xcode() {
    log_info "Xcode Command Line Tools를 확인합니다..."
    
    if ! xcode-select -p &> /dev/null; then
        log_info "Xcode Command Line Tools를 설치합니다..."
        xcode-select --install
        
        log_warning "Xcode Command Line Tools 설치가 시작되었습니다."
        log_warning "설치 완료 후 이 스크립트를 다시 실행해주세요."
        exit 1
    else
        # 라이선스 동의 확인
        if ! sudo xcodebuild -license check &> /dev/null; then
            log_warning "Xcode 라이선스에 동의해야 합니다."
            echo "다음 명령을 실행하세요: sudo xcodebuild -license accept"
        fi
        log_success "Xcode Command Line Tools가 설치되어 있습니다"
    fi
}

# 프로젝트 파일 확인 및 수정
check_project_files() {
    log_info "프로젝트 파일을 확인합니다..."
    
    # 메인 파일 확인 및 생성
    if [[ -f "main_optimized.py" ]] && [[ ! -f "main.py" ]]; then
        log_info "main_optimized.py를 main.py로 복사합니다..."
        cp main_optimized.py main.py
    fi
    
    required_files=("main.py" "buildozer.spec" "android_utils.py")
    
    for file in "${required_files[@]}"; do
        if [[ ! -f "$file" ]]; then
            log_error "필수 파일이 없습니다: $file"
            echo ""
            echo "다음 파일들이 필요합니다:"
            echo "  - main.py (또는 main_optimized.py)"
            echo "  - buildozer.spec"
            echo "  - android_utils.py"
            echo "  - requirements.txt"
            echo ""
            exit 1
        fi
    done
    
    log_success "프로젝트 파일 확인 완료"
}

# buildozer.spec 수정 (최신 버전 호환)
fix_buildozer_spec() {
    log_info "최신 버전용 buildozer.spec을 수정합니다..."
    
    # buildozer.spec 백업
    cp buildozer.spec buildozer.spec.backup
    
    # buildozer.spec 수정
    cat > buildozer.spec.new << 'EOF'
[app]
title = MyTalk
package.name = mytalk
package.domain = com.mytalk.app
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,json,txt,mp3
source.exclude_dirs = tests,bin,venv,.git,__pycache__,build
version = 1.0
requirements = python3,kivy==2.2.1,kivymd,openai,requests,certifi,urllib3,charset-normalizer,idna
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

# p4a 최신 설정
p4a.fork = kivy
p4a.branch = develop
p4a.bootstrap = sdl2
EOF

    mv buildozer.spec.new buildozer.spec
    log_success "buildozer.spec 수정 완료"
}

# 빌드 실행 (개선된 버전)
build_debug() {
    log_info "디버그 APK 빌드를 시작합니다..."
    log_warning "최초 빌드는 1-2시간이 걸릴 수 있습니다..."
    
    # 가상환경 확인
    if [[ -z "$VIRTUAL_ENV" ]]; then
        source venv/bin/activate
    fi
    
    # 환경변수 설정
    export ANDROID_HOME="$HOME/android-sdk"
    export PATH="$PATH:$ANDROID_HOME/cmdline-tools/latest/bin"
    export PATH="$PATH:$ANDROID_HOME/platform-tools"
    
    # Java 17 JAVA_HOME 설정
    if /usr/libexec/java_home -v 17 &>/dev/null; then
        export JAVA_HOME=$(/usr/libexec/java_home -v 17)
    else
        # 설치된 Java 17 경로 찾기
        if [[ "$ARCH" == "arm64" ]]; then
            possible_paths=(
                "/opt/homebrew/Cellar/temurin@17/*/libexec/openjdk.jdk/Contents/Home"
                "/Library/Java/JavaVirtualMachines/temurin-17.jdk/Contents/Home"
            )
        else
            possible_paths=(
                "/usr/local/Cellar/temurin@17/*/libexec/openjdk.jdk/Contents/Home"
                "/Library/Java/JavaVirtualMachines/temurin-17.jdk/Contents/Home"
            )
        fi
        
        for path in "${possible_paths[@]}"; do
            expanded_paths=($path)
            for expanded_path in "${expanded_paths[@]}"; do
                if [[ -d "$expanded_path" ]]; then
                    export JAVA_HOME="$expanded_path"
                    break 2
                fi
            done
        done
    fi
    
    export PATH="$JAVA_HOME/bin:$PATH"
    
    # Java 버전 확인
    log_info "사용 중인 Java 버전: $("$JAVA_HOME/bin/java" -version 2>&1 | head -n1)"
    
    # macOS 특별 설정
    export LDFLAGS="-L$(brew --prefix)/lib"
    export CPPFLAGS="-I$(brew --prefix)/include"
    export PKG_CONFIG_PATH="$(brew --prefix)/lib/pkgconfig"
    
    # Apple Silicon 특별 설정
    if [[ "$ARCH" == "arm64" ]]; then
        export ARCHFLAGS="-arch arm64"
        export CC="clang"
        export CXX="clang++"
    fi
    
    # 빌드 시작 시간
    start_time=$(date +%s)
    
    # 빌드 로그 파일
    BUILD_LOG="buildozer_build.log"
    
    log_info "빌드 시작... 로그는 $BUILD_LOG에서 확인할 수 있습니다"
    
    # Buildozer 실행
    if buildozer android debug 2>&1 | tee "$BUILD_LOG"; then
        # 빌드 종료 시간
        end_time=$(date +%s)
        build_time=$((end_time - start_time))
        minutes=$((build_time / 60))
        seconds=$((build_time % 60))
        
        # 결과 확인
        if ls bin/*.apk 1> /dev/null 2>&1; then
            apk_file=$(ls bin/*.apk | head -1)
            apk_size=$(du -h "$apk_file" | cut -f1)
            
            log_success "🎉 빌드 성공!"
            echo ""
            echo "📱 APK 정보:"
            echo "  - 파일: $apk_file"
            echo "  - 크기: $apk_size"
            echo "  - 빌드 시간: ${minutes}분 ${seconds}초"
            echo ""
            
            return 0
        else
            log_error "APK 파일을 찾을 수 없습니다"
            return 1
        fi
    else
        log_error "빌드 실패. 로그를 확인하세요: $BUILD_LOG"
        return 1
    fi
}

# APK 설치 (ADB 사용)
install_apk() {
    log_info "Android 기기에 APK를 설치합니다..."
    
    # ADB 경로 확인
    ADB_PATH="$HOME/android-sdk/platform-tools/adb"
    if [[ ! -f "$ADB_PATH" ]]; then
        log_error "ADB를 찾을 수 없습니다."
        log_info "Android SDK가 올바르게 설치되었는지 확인하세요."
        return 1
    fi
    
    # 연결된 기기 확인
    devices=$($ADB_PATH devices | grep -v "List of devices" | grep "device$" | wc -l)
    
    if [[ "$devices" -eq 0 ]]; then
        log_error "연결된 Android 기기가 없습니다."
        echo ""
        echo "다음을 확인하세요:"
        echo "1. USB 케이블로 기기 연결"
        echo "2. 기기에서 USB 디버깅 활성화"
        echo "3. 컴퓨터 신뢰 허용"
        echo ""
        return 1
    fi
    
    # APK 파일 찾기
    apk_file=$(ls bin/*.apk 2>/dev/null | head -1)
    
    if [[ ! -f "$apk_file" ]]; then
        log_error "설치할 APK 파일을 찾을 수 없습니다."
        log_info "먼저 빌드를 실행하세요: ./build_macos_fixed.sh debug"
        return 1
    fi
    
    # APK 설치
    log_info "APK 설치 중: $apk_file"
    $ADB_PATH install -r "$apk_file"
    
    if [[ $? -eq 0 ]]; then
        log_success "📱 APK 설치 완료!"
        
        # 앱 실행 여부 확인
        read -p "앱을 실행하시겠습니까? (y/N): " run_app
        if [[ $run_app =~ ^[Yy]$ ]]; then
            $ADB_PATH shell am start -n com.mytalk.app/org.kivy.android.PythonActivity
            log_success "앱이 실행되었습니다"
        fi
        
        return 0
    else
        log_error "APK 설치 실패"
        return 1
    fi
}

# 전체 환경 설정
setup_environment() {
    log_info "macOS 환경을 설정합니다..."
    
    show_system_info
    echo ""
    
    install_homebrew
    install_dependencies
    check_xcode
    install_java
    install_android_sdk
    install_android_components
    setup_python_env
    
    log_success "✅ 환경 설정이 완료되었습니다!"
    echo ""
    echo "다음 단계:"
    echo "1. 프로젝트 파일들을 현재 디렉토리에 배치"
    echo "2. ./build_macos_fixed.sh debug  # 디버그 빌드"
    echo "3. ./build_macos_fixed.sh install  # 기기에 설치"
    echo ""
    echo "중요: 터미널을 재시작하거나 다음 명령을 실행하세요:"
    echo "source ~/.zprofile"
    echo ""
}

# 정리 작업
clean_build() {
    log_info "빌드 캐시를 정리합니다..."
    
    directories_to_clean=(".buildozer" "bin" "__pycache__" "build")
    
    for dir in "${directories_to_clean[@]}"; do
        if [[ -d "$dir" ]]; then
            rm -rf "$dir"
            log_success "$dir 정리 완료"
        fi
    done
    
    # Python 캐시 파일 정리
    find . -name "*.pyc" -delete 2>/dev/null || true
    find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
    
    log_success "정리 작업 완료"
}

# 도움말
show_help() {
    echo "MyTalk Android App - 수정된 macOS 빌드 스크립트"
    echo ""
    echo "사용법: ./build_macos_fixed.sh [명령]"
    echo ""
    echo "명령:"
    echo "  setup      전체 개발 환경 설정 (최초 1회)"
    echo "  debug      디버그 APK 빌드"
    echo "  release    릴리즈 APK 빌드"
    echo "  install    APK를 연결된 기기에 설치"
    echo "  clean      빌드 캐시 정리"
    echo "  help       이 도움말 표시"
    echo ""
    echo "예시:"
    echo "  ./build_macos_fixed.sh setup    # 최초 환경 설정"
    echo "  ./build_macos_fixed.sh debug    # 디버그 빌드"
    echo "  ./build_macos_fixed.sh install  # APK 설치"
    echo ""
    echo "시스템 요구사항:"
    echo "  - macOS 10.15+ (Intel 또는 Apple Silicon)"
    echo "  - Xcode Command Line Tools"
    echo "  - Java 17+ (자동 설치됨)"
    echo "  - 여유 저장 공간 8GB 이상"
    echo ""
}

# 메인 함수
main() {
    local command=${1:-help}
    
    case $command in
        "setup")
            log_info "🔧 전체 환경 설정 모드"
            setup_environment
            ;;
            
        "debug")
            log_info "🛠️ 디버그 빌드 모드"
            check_project_files
            fix_buildozer_spec
            build_debug
            
            if [[ $? -eq 0 ]]; then
                echo ""
                log_success "🎉 빌드 완료!"
                echo ""
                echo "다음 단계:"
                echo "1. ./build_macos_fixed.sh install  # 기기에 설치"
                echo ""
            fi
            ;;
            
        "release")
            log_info "📦 릴리즈 빌드 모드"
            check_project_files
            fix_buildozer_spec
            
            # 릴리즈 빌드는 키스토어 필요
            log_warning "릴리즈 빌드는 키스토어가 필요합니다."
            read -p "계속하시겠습니까? (y/N): " continue_release
            
            if [[ $continue_release =~ ^[Yy]$ ]]; then
                source venv/bin/activate 2>/dev/null || true
                buildozer android release
                log_success "릴리즈 빌드 완료"
            fi
            ;;
            
        "install")
            log_info "📱 APK 설치 모드"
            install_apk
            ;;
            
        "clean")
            log_info "🧹 정리 모드"
            read -p "빌드 캐시를 정리하시겠습니까? (y/N): " confirm
            if [[ $confirm =~ ^[Yy]$ ]]; then
                clean_build
            else
                log_info "정리 작업이 취소되었습니다."
            fi
            ;;
            
        "help"|"-h"|"--help"|*)
            show_help
            ;;
    esac
}

# 트랩 설정 (Ctrl+C 처리)
trap 'echo -e "\n${YELLOW}작업이 중단되었습니다.${NC}"; exit 130' INT

# 스크립트 실행
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi