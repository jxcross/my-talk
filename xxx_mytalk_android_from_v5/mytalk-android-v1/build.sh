#!/bin/bash

# MyTalk Android App 자동 빌드 스크립트
# Ubuntu/Linux 환경용

set -e  # 에러 발생 시 스크립트 종료

echo "🎙️ MyTalk Android App 빌드 스크립트"
echo "=================================="

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

# 환경 변수 확인
check_environment() {
    log_info "환경 변수 확인 중..."
    
    if [ -z "$ANDROID_HOME" ]; then
        log_error "ANDROID_HOME 환경 변수가 설정되지 않았습니다."
        echo "다음 명령으로 설정하세요:"
        echo "export ANDROID_HOME=\$HOME/android-sdk"
        exit 1
    fi
    
    if [ -z "$JAVA_HOME" ]; then
        log_warning "JAVA_HOME이 설정되지 않았습니다. 자동 감지를 시도합니다..."
        export JAVA_HOME=$(readlink -f /usr/bin/java | sed "s:bin/java::")
    fi
    
    log_success "환경 변수 확인 완료"
}

# 의존성 확인
check_dependencies() {
    log_info "의존성 확인 중..."
    
    # Python 확인
    if ! command -v python3 &> /dev/null; then
        log_error "Python 3가 설치되지 않았습니다."
        exit 1
    fi
    
    # Git 확인
    if ! command -v git &> /dev/null; then
        log_error "Git이 설치되지 않았습니다."
        exit 1
    fi
    
    # Java 확인
    if ! command -v java &> /dev/null; then
        log_error "Java가 설치되지 않았습니다."
        exit 1
    fi
    
    log_success "의존성 확인 완료"
}

# 가상환경 설정
setup_virtualenv() {
    log_info "Python 가상환경 설정 중..."
    
    if [ ! -d "venv" ]; then
        python3 -m venv venv
        log_success "가상환경 생성 완료"
    fi
    
    source venv/bin/activate
    log_info "가상환경 활성화됨"
    
    # pip 업그레이드
    pip install --upgrade pip
    
    # 기본 의존성 설치
    pip install buildozer cython
    pip install kivy[base]==2.1.0
    pip install kivymd
    pip install openai requests
    
    log_success "Python 의존성 설치 완료"
}

# 프로젝트 파일 확인
check_project_files() {
    log_info "프로젝트 파일 확인 중..."
    
    required_files=("main.py" "buildozer.spec" "requirements.txt")
    
    for file in "${required_files[@]}"; do
        if [ ! -f "$file" ]; then
            log_error "필수 파일이 없습니다: $file"
            exit 1
        fi
    done
    
    log_success "프로젝트 파일 확인 완료"
}

# buildozer 초기화
init_buildozer() {
    log_info "Buildozer 초기화 중..."
    
    if [ ! -d ".buildozer" ]; then
        log_info "최초 빌드 - Android 요구사항 설치 중..."
        buildozer android_new debug
        log_success "Android 요구사항 설치 완료"
    else
        log_info "기존 빌드 환경 감지됨"
    fi
}

# 디버그 빌드
build_debug() {
    log_info "디버그 APK 빌드 중..."
    log_warning "이 과정은 시간이 오래 걸릴 수 있습니다..."
    
    # 빌드 시작 시간
    start_time=$(date +%s)
    
    # buildozer로 디버그 빌드
    buildozer android debug
    
    # 빌드 종료 시간
    end_time=$(date +%s)
    build_time=$((end_time - start_time))
    
    log_success "디버그 빌드 완료! (소요시간: ${build_time}초)"
    
    # APK 파일 확인
    if [ -f "bin/"*.apk ]; then
        apk_file=$(ls bin/*.apk | head -1)
        log_success "APK 생성됨: $apk_file"
        
        # APK 파일 크기 표시
        size=$(du -h "$apk_file" | cut -f1)
        log_info "APK 크기: $size"
        
        return 0
    else
        log_error "APK 파일을 찾을 수 없습니다"
        return 1
    fi
}

# 릴리즈 빌드
build_release() {
    log_info "릴리즈 APK 빌드 중..."
    
    # 키스토어 파일 확인
    if [ ! -f "my-release-key.keystore" ]; then
        log_warning "키스토어 파일이 없습니다. 새로 생성합니다..."
        
        read -p "키스토어 비밀번호를 입력하세요: " -s keystore_password
        echo
        read -p "키 별칭을 입력하세요 (예: mytalk-key): " key_alias
        
        keytool -genkey -v -keystore my-release-key.keystore \
                -alias "$key_alias" -keyalg RSA -keysize 2048 \
                -validity 10000 \
                -storepass "$keystore_password"
        
        log_success "키스토어 생성 완료"
    fi
    
    # 릴리즈 빌드
    buildozer android release
    
    if [ -f "bin/"*-release*.apk ]; then
        apk_file=$(ls bin/*-release*.apk | head -1)
        log_success "릴리즈 APK 생성됨: $apk_file"
        return 0
    else
        log_error "릴리즈 APK 파일을 찾을 수 없습니다"
        return 1
    fi
}

# APK 설치
install_apk() {
    log_info "기기에 APK 설치 중..."
    
    # ADB 연결 확인
    if ! command -v adb &> /dev/null; then
        log_error "ADB를 찾을 수 없습니다. Android SDK가 PATH에 있는지 확인하세요."
        return 1
    fi
    
    # 연결된 기기 확인
    devices=$(adb devices | grep -v "List of devices" | grep "device$" | wc -l)
    
    if [ "$devices" -eq 0 ]; then
        log_error "연결된 Android 기기가 없습니다."
        log_info "USB 디버깅이 활성화된 기기를 연결하세요."
        return 1
    fi
    
    # APK 파일 찾기
    apk_file=$(ls bin/*.apk | head -1)
    
    if [ ! -f "$apk_file" ]; then
        log_error "설치할 APK 파일을 찾을 수 없습니다."
        return 1
    fi
    
    # APK 설치
    adb install -r "$apk_file"
    
    if [ $? -eq 0 ]; then
        log_success "APK 설치 완료!"
        
        # 앱 실행
        read -p "앱을 실행하시겠습니까? (y/N): " run_app
        if [[ $run_app =~ ^[Yy]$ ]]; then
            adb shell am start -n com.mytalk.app/org.kivy.android.PythonActivity
            log_success "앱이 실행되었습니다"
        fi
    else
        log_error "APK 설치 실패"
        return 1
    fi
}

# 로그 보기
show_logs() {
    log_info "Android 로그 확인 중... (Ctrl+C로 종료)"
    adb logcat | grep -E "(python|kivy|mytalk)"
}

# 정리 작업
clean_build() {
    log_info "빌드 캐시 정리 중..."
    
    if [ -d ".buildozer" ]; then
        rm -rf .buildozer
        log_success "Buildozer 캐시 정리 완료"
    fi
    
    if [ -d "bin" ]; then
        rm -rf bin
        log_success "빌드 출력 디렉토리 정리 완료"
    fi
    
    # Python 캐시도 정리
    find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
    find . -name "*.pyc" -delete 2>/dev/null || true
    
    log_success "정리 작업 완료"
}

# 도움말
show_help() {
    echo "MyTalk Android App 빌드 스크립트"
    echo ""
    echo "사용법: ./build.sh [명령]"
    echo ""
    echo "명령:"
    echo "  debug      디버그 APK 빌드 (기본값)"
    echo "  release    릴리즈 APK 빌드"
    echo "  install    APK를 연결된 기기에 설치"
    echo "  logs       Android 로그 보기"
    echo "  clean      빌드 캐시 정리"
    echo "  help       이 도움말 표시"
    echo ""
    echo "예시:"
    echo "  ./build.sh debug    # 디버그 빌드"
    echo "  ./build.sh release  # 릴리즈 빌드"
    echo "  ./build.sh install  # APK 설치"
}

# 메인 함수
main() {
    local command=${1:-debug}  # 기본값은 debug
    
    case $command in
        "debug")
            log_info "디버그 빌드 모드"
            check_environment
            check_dependencies
            setup_virtualenv
            check_project_files
            init_buildozer
            build_debug
            
            if [ $? -eq 0 ]; then
                echo ""
                log_success "🎉 빌드 성공!"
                echo ""
                echo "다음 단계:"
                echo "1. ./build.sh install  # 기기에 설치"
                echo "2. ./build.sh logs     # 로그 확인"
                echo ""
            else
                log_error "빌드 실패"
                exit 1
            fi
            ;;
            
        "release")
            log_info "릴리즈 빌드 모드"
            check_environment
            check_dependencies
            setup_virtualenv
            check_project_files
            init_buildozer
            build_release
            
            if [ $? -eq 0 ]; then
                log_success "🎉 릴리즈 빌드 성공!"
                log_info "Google Play Store 또는 직접 배포용 APK가 준비되었습니다."
            else
                log_error "릴리즈 빌드 실패"
                exit 1
            fi
            ;;
            
        "install")
            log_info "APK 설치 모드"
            install_apk
            ;;
            
        "logs")
            log_info "로그 보기 모드"
            show_logs
            ;;
            
        "clean")
            log_info "정리 모드"
            read -p "빌드 캐시를 정리하시겠습니까? (y/N): " confirm
            if [[ $confirm =~ ^[Yy]$ ]]; then
                clean_build
            else
                log_info "정리 작업이 취소되었습니다."
            fi
            ;;
            
        "setup")
            log_info "초기 설정 모드"
            check_environment
            check_dependencies
            setup_virtualenv
            check_project_files
            log_success "초기 설정 완료!"
            ;;
            
        "help"|"-h"|"--help")
            show_help
            ;;
            
        *)
            log_error "알 수 없는 명령: $command"
            show_help
            exit 1
            ;;
    esac
}

# 트랩 설정 (Ctrl+C 처리)
trap 'echo -e "\n${YELLOW}빌드가 중단되었습니다.${NC}"; exit 130' INT

# 스크립트 실행
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi