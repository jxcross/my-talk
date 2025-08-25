#!/bin/bash

# Buildozer Android Build Fix Script
# Addresses harfbuzz, NDK, and p4a compilation issues on macOS

set -e

echo "🔧 Buildozer Android Build Fix Script"
echo "====================================="

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

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

# System detection
ARCH=$(uname -m)
if [[ "$ARCH" == "arm64" ]]; then
    HOMEBREW_PREFIX="/opt/homebrew"
else
    HOMEBREW_PREFIX="/usr/local"
fi

# Clean buildozer cache and rebuild
clean_buildozer_cache() {
    log_info "Cleaning buildozer cache and build directories..."
    
    # Remove buildozer directories
    rm -rf .buildozer
    rm -rf bin
    rm -rf build
    
    # Remove global buildozer cache
    rm -rf ~/.buildozer
    
    # Clean pip cache
    pip cache purge 2>/dev/null || true
    
    log_success "✅ Buildozer cache cleaned"
}

# Fix buildozer.spec for better compatibility
create_optimized_buildozer_spec() {
    log_info "Creating optimized buildozer.spec..."
    
    cat > buildozer.spec << 'EOF'
[app]
title = MyTalk
package.name = mytalk
package.domain = com.mytalk.app
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,json,txt,mp3
source.exclude_dirs = tests,bin,venv,.git,__pycache__,build,.buildozer
version = 1.0

# Simplified requirements to avoid compilation issues
requirements = python3,kivy,kivymd,openai,requests,certifi,urllib3,charset-normalizer,idna

orientation = portrait
fullscreen = 0

# Essential permissions only
android.permissions = INTERNET,WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE,RECORD_AUDIO

# Single architecture for easier build (choose one)
android.archs = arm64-v8a

# API levels
android.api = 33
android.minapi = 21
android.ndk = 25b
android.sdk = 33

android.allow_backup = True

[buildozer]
log_level = 2
warn_on_root = 1

# P4A settings optimized for macOS
p4a.fork = kivy
p4a.branch = master
p4a.bootstrap = sdl2

# Skip problematic recipes
p4a.local_recipes = 
EOF

    log_success "✅ Optimized buildozer.spec created"
}

# Setup environment variables for successful build
setup_build_environment() {
    log_info "Setting up build environment..."
    
    # Java setup
    export JAVA_HOME=$(/usr/libexec/java_home -v 17 2>/dev/null)
    if [[ -z "$JAVA_HOME" ]]; then
        log_error "Java 17 not found. Installing..."
        brew install --cask temurin@17
        export JAVA_HOME=$(/usr/libexec/java_home -v 17)
    fi
    
    # Android setup
    export ANDROID_HOME="$HOME/android-sdk"
    export ANDROID_SDK_ROOT="$ANDROID_HOME"
    
    # NDK setup - use specific compatible version
    export ANDROIDNDK="$HOME/.buildozer/android/platform/android-ndk-r25b"
    export ANDROID_NDK_ROOT="$ANDROIDNDK"
    
    # Build environment
    export PATH="$JAVA_HOME/bin:$PATH:$ANDROID_HOME/cmdline-tools/latest/bin:$ANDROID_HOME/platform-tools"
    
    # macOS specific build flags
    export CFLAGS="-I${HOMEBREW_PREFIX}/include"
    export LDFLAGS="-L${HOMEBREW_PREFIX}/lib"
    export CPPFLAGS="-I${HOMEBREW_PREFIX}/include"
    export PKG_CONFIG_PATH="${HOMEBREW_PREFIX}/lib/pkgconfig"
    
    # Architecture specific flags
    if [[ "$ARCH" == "arm64" ]]; then
        export ARCHFLAGS="-arch arm64"
        export CC_FOR_BUILD="clang -arch arm64"
        export CXX_FOR_BUILD="clang++ -arch arm64"
    else
        export ARCHFLAGS="-arch x86_64"
    fi
    
    # P4A specific environment
    export P4A_BOOTSTRAP="sdl2"
    export P4A_ARCH="arm64-v8a"
    
    # Avoid harfbuzz issues
    export KIVY_SPLIT_EXAMPLES=1
    export USE_X11=0
    export USE_GSTREAMER=0
    
    log_info "Environment configured:"
    echo "  - Java: $JAVA_HOME"
    echo "  - Android SDK: $ANDROID_HOME"
    echo "  - Architecture: $ARCH"
}

# Install buildozer and dependencies
install_buildozer_dependencies() {
    log_info "Installing buildozer and dependencies..."
    
    # Ensure we're in venv
    if [[ -z "$VIRTUAL_ENV" ]]; then
        log_error "Please activate your virtual environment first!"
        exit 1
    fi
    
    # Update pip and tools
    pip install --upgrade pip wheel setuptools
    
    # Install specific buildozer version that works better
    pip install --upgrade "buildozer==1.5.0"
    
    # Install Cython with specific version
    pip install --upgrade "Cython>=0.29.33,<3.0"
    
    # System dependencies via Homebrew
    local brew_deps=(
        "autoconf"
        "automake"
        "libtool"
        "cmake"
        "pkg-config"
        "zlib"
        "libffi"
        "openssl"
    )
    
    for dep in "${brew_deps[@]}"; do
        if ! brew list "$dep" &>/dev/null; then
            log_info "Installing $dep..."
            brew install "$dep" 2>/dev/null || log_warning "Failed to install $dep"
        fi
    done
    
    log_success "✅ Dependencies installed"
}

# Download and setup compatible Android NDK
setup_compatible_ndk() {
    log_info "Setting up compatible Android NDK..."
    
    local ndk_dir="$HOME/.buildozer/android/platform"
    local ndk_version="android-ndk-r25b"
    local ndk_path="$ndk_dir/$ndk_version"
    
    if [[ ! -d "$ndk_path" ]]; then
        log_info "Downloading Android NDK r25b (more stable for builds)..."
        
        mkdir -p "$ndk_dir"
        cd "$ndk_dir"
        
        # Download NDK r25b (more compatible)
        local ndk_url="https://dl.google.com/android/repository/android-ndk-r25b-darwin.zip"
        
        if command -v curl &> /dev/null; then
            curl -L -o "$ndk_version.zip" "$ndk_url"
        elif command -v wget &> /dev/null; then
            wget -O "$ndk_version.zip" "$ndk_url"
        else
            log_error "Neither curl nor wget available"
            exit 1
        fi
        
        log_info "Extracting NDK..."
        unzip -q "$ndk_version.zip"
        rm "$ndk_version.zip"
        
        cd - > /dev/null
        log_success "✅ NDK r25b installed"
    else
        log_success "✅ NDK r25b already available"
    fi
    
    export ANDROIDNDK="$ndk_path"
    export ANDROID_NDK_ROOT="$ndk_path"
}

# Build with optimized settings
build_apk() {
    log_info "Starting optimized APK build..."
    
    # Display build information
    log_info "Build environment:"
    echo "  - Python: $(python --version) ($(which python))"
    echo "  - Java: $(java -version 2>&1 | head -n1)"
    echo "  - Buildozer: $(buildozer version 2>/dev/null || echo 'Unknown')"
    echo "  - ANDROID_HOME: $ANDROID_HOME"
    echo "  - ANDROIDNDK: $ANDROIDNDK"
    
    # Build with verbose output
    log_info "Running buildozer android debug..."
    
    # Use single architecture and simplified build
    if buildozer android debug --verbose; then
        log_success "🎉 Build completed successfully!"
        
        # Check for APK
        if ls bin/*.apk &>/dev/null; then
            apk_file=$(ls bin/*.apk | head -1)
            apk_size=$(du -h "$apk_file" | cut -f1)
            log_success "📱 APK created: $apk_file ($apk_size)"
            
            # Show next steps
            echo ""
            echo "🚀 Next Steps:"
            echo "1. Install APK: adb install \"$apk_file\""
            echo "2. Or transfer to device and install manually"
            echo "3. Enable 'Unknown Sources' if needed"
        fi
        
        return 0
    else
        log_error "❌ Build failed"
        
        echo ""
        echo "🔍 Troubleshooting Steps:"
        echo "1. Check the full log above for specific errors"
        echo "2. Try: $0 clean && $0 build"
        echo "3. Check Java/NDK versions"
        echo "4. Try single architecture build"
        
        return 1
    fi
}

# Alternative: Use p4a directly (bypass buildozer)
build_with_p4a_directly() {
    log_warning "Trying alternative build with p4a directly..."
    
    # Install python-for-android
    pip install --upgrade python-for-android
    
    # Build distribution
    log_info "Creating p4a distribution..."
    
    p4a create --dist_name mytalk \
        --bootstrap sdl2 \
        --requirements python3,kivy,kivymd,openai,requests,certifi,urllib3,charset-normalizer,idna \
        --arch arm64-v8a \
        --ndk-api 21
    
    if [[ $? -eq 0 ]]; then
        log_info "Building APK with p4a..."
        
        p4a apk --dist_name mytalk \
            --name MyTalk \
            --package com.mytalk.app \
            --version 1.0 \
            --bootstrap sdl2 \
            --arch arm64-v8a \
            --permission INTERNET \
            --permission WRITE_EXTERNAL_STORAGE \
            --permission READ_EXTERNAL_STORAGE \
            --permission RECORD_AUDIO
        
        if [[ $? -eq 0 ]]; then
            log_success "✅ P4A build successful!"
            return 0
        fi
    fi
    
    log_error "❌ P4A build also failed"
    return 1
}

# Main execution function
main() {
    case ${1:-help} in
        "clean")
            log_info "🧹 Cleaning build environment"
            clean_buildozer_cache
            ;;
            
        "setup")
            log_info "🔧 Setting up optimized build environment"
            clean_buildozer_cache
            create_optimized_buildozer_spec
            install_buildozer_dependencies
            setup_build_environment
            setup_compatible_ndk
            log_success "✅ Setup complete!"
            ;;
            
        "build")
            log_info "🛠️ Building APK with optimizations"
            setup_build_environment
            setup_compatible_ndk
            
            if ! build_apk; then
                log_warning "Buildozer failed, trying p4a directly..."
                build_with_p4a_directly
            fi
            ;;
            
        "p4a")
            log_info "🔧 Building directly with python-for-android"
            setup_build_environment
            build_with_p4a_directly
            ;;
            
        "debug")
            log_info "🔍 Debug build environment"
            setup_build_environment
            
            echo "Environment Variables:"
            echo "  JAVA_HOME: $JAVA_HOME"
            echo "  ANDROID_HOME: $ANDROID_HOME"
            echo "  ANDROIDNDK: $ANDROIDNDK"
            echo "  PATH: $PATH"
            echo ""
            echo "Java version:"
            java -version
            echo ""
            echo "Python environment:"
            python --version
            pip list | grep -E "(kivy|buildozer|Cython)"
            ;;
            
        *)
            echo "Buildozer Android Build Fix Script"
            echo ""
            echo "Usage: $0 {clean|setup|build|p4a|debug}"
            echo ""
            echo "Commands:"
            echo "  clean  - Clean all build caches and directories"
            echo "  setup  - Complete optimized build environment setup"
            echo "  build  - Build APK with optimizations"
            echo "  p4a    - Build directly with python-for-android"
            echo "  debug  - Show debug information"
            echo ""
            echo "Recommended workflow:"
            echo "  1. $0 clean"
            echo "  2. $0 setup"
            echo "  3. $0 build"
            ;;
    esac
}

main "$@"