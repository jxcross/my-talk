#!/bin/bash

# MyTalk Android App - 맥OS 빌드 스크립트
# macOS 환경용 (Intel & Apple Silicon 지원)

set -e  # 에러 발생 시 스크립트 종료

echo "🎙️ MyTalk Android App - macOS 빌드 스크립트"
echo "============================================="

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 시스템 정보 감지
ARCH=$(uname -m)
if [[ "$ARCH" == "arm64" ]]; then
    PLATFORM="Apple Silicon (M1/M2/M3)"
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

# Java 설치 확인 및 설치
install_java() {
    log_info "Java 설치를 확인합니다..."
    
    if command -v java &> /dev/null; then
        java_version=$(java -version 2>&1 | head -n1 | cut -d'"' -f2)
        log_info "Java가 이미 설치되어 있습니다: $java_version"
        
        # JAVA_HOME 설정
        if [[ -z "$JAVA_HOME" ]]; then
            if [[ "$ARCH" == "arm64" ]]; then
                export JAVA_HOME=$(/usr/libexec/java_home -v 11 2>/dev/null || /usr/libexec/java_home)
            else
                export JAVA_HOME=$(/usr/libexec/java_home -v 11 2>/dev/null || /usr/libexec/java_home)
            fi
            echo "export JAVA_HOME=$JAVA_HOME" >> ~/.zprofile
        fi
    else
        log_info "Java를 설치합니다..."
        
        # OpenJDK 11 설치 (Android 빌드에 권장)
        if [[ "$ARCH" == "arm64" ]]; then
            # Apple Silicon용
            brew install --cask temurin11
        else
            # Intel용
            brew install --cask adoptopenjdk11
        fi
        
        # JAVA_HOME 설정
        export JAVA_HOME=$(/usr/libexec/java_home -v 11)
        echo "export JAVA_HOME=$JAVA_HOME" >> ~/.zprofile
        
        log_success "Java 설치 완료"
    fi
}

# Android SDK 설치 (Command Line Tools)
install_android_sdk() {
    log_info "Android SDK 설치를 확인합니다..."
    
    ANDROID_HOME="$HOME/android-sdk"
    
    if [[ ! -d "$ANDROID_HOME" ]]; then
        log_info "Android SDK를 설치합니다..."
        
        mkdir -p "$ANDROID_HOME/cmdline-tools"
        cd "$ANDROID_HOME/cmdline-tools"
        
        # 최신 Command Line Tools 다운로드
        if [[ "$ARCH" == "arm64" ]]; then
            # Apple Silicon - x86_64 버전 사용 (Rosetta로 실행)
            wget -q https://dl.google.com/android/repository/commandlinetools-mac-9477386_latest.zip
        else
            # Intel Mac
            wget -q https://dl.google.com/android/repository/commandlinetools-mac-9477386_latest.zip
        fi
        
        unzip -q commandlinetools-mac-*_latest.zip
        mv cmdline-tools latest
        rm commandlinetools-mac-*_latest.zip
        
        # 환경변수 설정
        export ANDROID_HOME="$HOME/android-sdk"
        export PATH="$PATH:$ANDROID_HOME/cmdline-tools/latest/bin"
        export PATH="$PATH:$ANDROID_HOME/platform-tools"
        
        # 프로필에 추가
        {
            echo "# Android SDK"
            echo "export ANDROID_HOME=\"$HOME/android-sdk\""
            echo "export PATH=\"\$PATH:\$ANDROID_HOME/cmdline-tools/latest/bin\""
            echo "export PATH=\"\$PATH:\$ANDROID_HOME/platform-tools\""
        } >> ~/.zprofile
        
        log_success "Android SDK Command Line Tools 설치 완료"
    else
        log_info "Android SDK가 이미 설치되어 있습니다"
        export ANDROID_HOME="$HOME/android-sdk"
        export PATH="$PATH:$ANDROID_HOME/cmdline-tools/latest/bin"
        export PATH="$PATH:$ANDROID_HOME/platform-tools"
    fi
}

# Android SDK 구성 요소 설치
install_android_components() {
    log_info "Android SDK 구성 요소를 설치합니다..."
    
    # 필수 구성 요소들
    components=(
        "platform-tools"
        "platforms;android-33"
        "build-tools;33.0.0"
        "ndk;25.1.8937393"
    )
    
    for component in "${components[@]}"; do
        log_info "$component 설치 중..."
        yes | sdkmanager "$component" || true
    done
    
    log_success "Android SDK 구성 요소 설치 완료"
}

# Python 가상환경 설정
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
    
    # macOS용 특별 설정
    export LDFLAGS="-L$(brew --prefix)/lib"
    export CPPFLAGS="-I$(brew --prefix)/include"
    export PKG_CONFIG_PATH="$(brew --prefix)/lib/pkgconfig"
    
    # Apple Silicon 특별 설정
    if [[ "$ARCH" == "arm64" ]]; then
        export ARCHFLAGS="-arch arm64"
        # Cython 사전 컴파일
        pip install Cython==0.29.33
    fi
    
    # Kivy 의존성 설치 (macOS 최적화)
    log_info "Kivy 의존성을 설치합니다..."
    pip install --upgrade wheel setuptools
    
    # Kivy 설치
    pip install kivy[base]==2.1.0
    pip install kivymd
    
    # Buildozer 설치
    pip install buildozer
    
    # 기타 의존성
    pip install openai requests certifi
    
    log_success "Python 환경 설정 완료"
}

# Xcode Command Line Tools 확인
check_xcode() {
    log_info "Xcode Command Line Tools를 확인합니다..."
    
    if ! xcode-select -p &> /dev/null; then
        log_info "Xcode Command Line Tools를 설치합니다..."
        xcode-select --install
        
        log_warning "Xcode Command Line Tools 설치가 시작되었습니다."
        log_warning "설치 완료 후 이 스크립트를 다시 실행해주세요."
        exit 1
    else
        log_success "Xcode Command Line Tools가 설치되어 있습니다"
    fi
}

# 프로젝트 파일 확인
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

# macOS용 buildozer.spec 수정
fix_buildozer_spec() {
    log_info "macOS용 buildozer.spec을 수정합니다..."
    
    # buildozer.spec 백업
    cp buildozer.spec buildozer.spec.backup
    
    # macOS 특정 설정 추가/수정
    if [[ "$ARCH" == "arm64" ]]; then
        # Apple Silicon용 설정
        cat >> buildozer.spec << 'EOF'

# macOS Apple Silicon 특별 설정
[buildozer]
log_level = 2
warn_on_root = 1

# p4a fork for Apple Silicon compatibility
p4a.fork = kivy
p4a.branch = develop
EOF
    fi
    
    log_success "buildozer.spec 수정 완료"
}

# 빌드 실행
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
    export JAVA_HOME=$(/usr/libexec/java_home -v 11 2>/dev/null || /usr/libexec/java_home)
    
    # Apple Silicon 특별 설정
    if [[ "$ARCH" == "arm64" ]]; then
        export ARCHFLAGS="-arch arm64"
        # x86_64 에뮬레이션이 필요한 경우
        # arch -x86_64 buildozer android debug
    fi
    
    # 빌드 시작 시간
    start_time=$(date +%s)
    
    # Buildozer 실행
    if [[ "$ARCH" == "arm64" ]]; then
        log_info "Apple Silicon에서 빌드 중... (Rosetta 사용 가능)"
        buildozer android debug
    else
        buildozer android debug
    fi
    
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
        log_info "먼저 빌드를 실행하세요: ./build_macos.sh debug"
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

# 로그 보기
show_logs() {
    log_info "Android 디바이스 로그를 확인합니다... (Ctrl+C로 종료)"
    
    ADB_PATH="$HOME/android-sdk/platform-tools/adb"
    
    if [[ -f "$ADB_PATH" ]]; then
        $ADB_PATH logcat | grep -E "(python|kivy|mytalk|MyTalk)" --color=always
    else
        log_error "ADB를 찾을 수 없습니다."
    fi
}

# 정리 작업
clean_build() {
    log_info "빌드 캐시를 정리합니다..."
    
    directories_to_clean=(".buildozer" "bin" "__pycache__")
    
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
    echo "2. ./build_macos.sh debug  # 디버그 빌드"
    echo "3. ./build_macos.sh install  # 기기에 설치"
    echo ""
}

# 도움말
show_help() {
    echo "MyTalk Android App - macOS 빌드 스크립트"
    echo ""
    echo "사용법: ./build_macos.sh [명령]"
    echo ""
    echo "명령:"
    echo "  setup      전체 개발 환경 설정 (최초 1회)"
    echo "  debug      디버그 APK 빌드"
    echo "  release    릴리즈 APK 빌드"
    echo "  install    APK를 연결된 기기에 설치"
    echo "  logs       Android 로그 보기"
    echo "  clean      빌드 캐시 정리"
    echo "  help       이 도움말 표시"
    echo ""
    echo "예시:"
    echo "  ./build_macos.sh setup    # 최초 환경 설정"
    echo "  ./build_macos.sh debug    # 디버그 빌드"
    echo "  ./build_macos.sh install  # APK 설치"
    echo ""
    echo "시스템 요구사항:"
    echo "  - macOS 10.15+ (Intel 또는 Apple Silicon)"
    echo "  - Xcode Command Line Tools"
    echo "  - 여유 저장 공간 5GB 이상"
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
                echo "1. ./build_macos.sh install  # 기기에 설치"
                echo "2. ./build_macos.sh logs     # 로그 확인"
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
            
        "logs")
            log_info "📋 로그 보기 모드"
            show_logs
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