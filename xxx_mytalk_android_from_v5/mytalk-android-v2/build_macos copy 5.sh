#!/bin/bash

# MyTalk Android App - Python 3.10 Build Script (More Stable)
# Alternative approach using Python 3.10 for better Kivy compatibility

set -e

echo "🎙️ MyTalk Android App - Python 3.10 Build Script"
echo "================================================"

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

# Setup Python 3.10 environment (more stable for Kivy)
setup_python310_environment() {
    log_info "Setting up Python 3.10 environment (better Kivy compatibility)..."
    
    # Deactivate conda environments
    if command -v conda &> /dev/null; then
        conda deactivate 2>/dev/null || true
        export PATH=$(echo $PATH | sed -e 's|[^:]*conda[^:]*:||g')
    fi
    
    export PATH="${HOMEBREW_PREFIX}/bin:${HOMEBREW_PREFIX}/sbin:/usr/bin:/bin:/usr/sbin:/sbin"
    
    # Install Python 3.10
    PYTHON310_PATH="${HOMEBREW_PREFIX}/bin/python3.10"
    
    if [[ ! -f "$PYTHON310_PATH" ]]; then
        log_info "Installing Python 3.10..."
        brew install python@3.10
    fi
    
    if [[ -f "$PYTHON310_PATH" ]]; then
        py310_version=$("$PYTHON310_PATH" --version)
        log_success "Python 3.10 confirmed: $py310_version"
        export PYTHON_CMD="$PYTHON310_PATH"
    else
        log_error "Python 3.10 not found"
        exit 1
    fi
}

# Create Python 3.10 virtual environment
create_venv_python310() {
    log_info "Creating Python 3.10 virtual environment..."
    
    if [[ -d "venv" ]]; then
        rm -rf venv
    fi
    
    "$PYTHON_CMD" -m venv venv
    source venv/bin/activate
    
    venv_python_version=$(python --version)
    log_info "Venv Python: $venv_python_version"
    
    if [[ "$venv_python_version" =~ "3.10" ]]; then
        log_success "✅ Python 3.10 virtual environment ready"
    else
        log_error "❌ Wrong Python version in venv"
        exit 1
    fi
}

# Install Kivy with Python 3.10 (more stable)
install_kivy_python310() {
    log_info "Installing Kivy with Python 3.10..."
    
    # Update pip and tools
    pip install --upgrade pip wheel setuptools
    
    # Install Cython
    pip install "Cython>=0.29.28,<3.0"
    
    # Install numpy
    pip install "numpy>=1.21.0,<2.0"
    
    # Install SDL2 dependencies
    local deps=("sdl2" "sdl2_image" "sdl2_ttf" "sdl2_mixer" "pkg-config")
    for dep in "${deps[@]}"; do
        if ! brew list "$dep" &>/dev/null; then
            brew install "$dep"
        fi
    done
    
    # Set environment variables
    export LDFLAGS="-L${HOMEBREW_PREFIX}/lib"
    export CPPFLAGS="-I${HOMEBREW_PREFIX}/include"
    export PKG_CONFIG_PATH="${HOMEBREW_PREFIX}/lib/pkgconfig"
    
    if [[ "$ARCH" == "arm64" ]]; then
        export ARCHFLAGS="-arch arm64"
    fi
    
    # Try binary installation first
    if pip install "kivy[base]==2.1.0" --no-cache-dir; then
        log_success "✅ Kivy installation successful"
    else
        log_error "❌ Kivy installation failed"
        exit 1
    fi
    
    # Install other dependencies
    pip install kivymd buildozer
    pip install "openai>=1.0.0" requests certifi urllib3 charset-normalizer idna
    
    # Test installation
    python -c "import kivy; print(f'Kivy {kivy.__version__} ready!')"
}

# Java and Android SDK setup (same as before)
setup_java_android() {
    log_info "Setting up Java and Android SDK..."
    
    # Java 17
    if ! brew list --cask temurin@17 &>/dev/null; then
        brew install --cask temurin@17
    fi
    
    export JAVA_HOME=$(/usr/libexec/java_home -v 17)
    export PATH="$JAVA_HOME/bin:$PATH"
    
    # Android SDK
    export ANDROID_HOME="$HOME/android-sdk"
    mkdir -p "$ANDROID_HOME/cmdline-tools"
    
    if [[ ! -d "$ANDROID_HOME/cmdline-tools/latest" ]]; then
        cd "$ANDROID_HOME/cmdline-tools"
        curl -o cmdline-tools.zip -L "https://dl.google.com/android/repository/commandlinetools-mac-11076708_latest.zip"
        unzip -q cmdline-tools.zip
        mv cmdline-tools latest
        rm cmdline-tools.zip
        cd - > /dev/null
    fi
    
    export PATH="$PATH:$ANDROID_HOME/cmdline-tools/latest/bin:$ANDROID_HOME/platform-tools"
    
    # Install SDK components
    yes | "$ANDROID_HOME/cmdline-tools/latest/bin/sdkmanager" --licenses &>/dev/null || true
    "$ANDROID_HOME/cmdline-tools/latest/bin/sdkmanager" "platform-tools" "platforms;android-34" "build-tools;34.0.0" "ndk;26.1.10909125" &>/dev/null
    
    log_success "✅ Java and Android SDK ready"
}

# Create optimized buildozer.spec for Python 3.10
create_buildozer_spec_310() {
    cat > buildozer.spec << 'EOF'
[app]
title = MyTalk
package.name = mytalk
package.domain = com.mytalk.app
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,json,txt,mp3
source.exclude_dirs = tests,bin,venv,.git,__pycache__,build,.buildozer
version = 1.0

# Python 3.10 optimized requirements
requirements = python3,kivy==2.1.0,kivymd,openai,requests,certifi,urllib3,charset-normalizer,idna,Cython

orientation = portrait
fullscreen = 0

android.permissions = INTERNET,WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE,RECORD_AUDIO,ACCESS_NETWORK_STATE,WAKE_LOCK,VIBRATE
android.archs = arm64-v8a, armeabi-v7a
android.api = 34
android.minapi = 21
android.ndk = 26b
android.sdk = 34
android.allow_backup = True

[buildozer]
log_level = 2
warn_on_root = 1

# Python-for-Android settings
p4a.fork = kivy
p4a.branch = develop
p4a.bootstrap = sdl2
EOF
    log_success "✅ buildozer.spec created for Python 3.10"
}

# Create android_utils.py
create_android_utils() {
    if [[ ! -f "android_utils.py" ]]; then
        cat > android_utils.py << 'EOF'
"""Android utility functions for MyTalk app"""

import os
import json
from pathlib import Path
from kivy.utils import platform
from kivy.logger import Logger

def get_storage_path():
    """Get storage path"""
    if platform == 'android':
        try:
            from jnius import autoclass
            Environment = autoclass('android.os.Environment')
            context = autoclass('org.kivy.android.PythonActivity').mActivity
            external_path = context.getExternalFilesDir(None)
            if external_path:
                return Path(str(external_path.toString())) / "MyTalk"
        except:
            pass
    return Path.home() / "MyTalk"

def request_android_permissions():
    """Request permissions"""
    if platform == 'android':
        try:
            from android.permissions import request_permissions, Permission
            request_permissions([
                Permission.WRITE_EXTERNAL_STORAGE,
                Permission.READ_EXTERNAL_STORAGE,
                Permission.RECORD_AUDIO,
                Permission.INTERNET
            ])
            return True
        except:
            pass
    return True

def show_toast(message, duration=2000):
    """Show toast message"""
    if platform == 'android':
        try:
            from jnius import autoclass
            Toast = autoclass('android.widget.Toast')
            context = autoclass('org.kivy.android.PythonActivity').mActivity
            String = autoclass('java.lang.String')
            toast = Toast.makeText(context, String(message), Toast.LENGTH_SHORT)
            toast.show()
        except:
            print(f"Toast: {message}")
    else:
        print(f"Info: {message}")

def initialize_android_app():
    """Initialize Android app"""
    if platform == 'android':
        request_android_permissions()
        return True
    return False

def keep_screen_on(keep_on=True):
    """Keep screen on"""
    if platform == 'android':
        try:
            from jnius import autoclass
            PythonActivity = autoclass('org.kivy.android.PythonActivity')
            activity = PythonActivity.mActivity
            if keep_on:
                activity.getWindow().addFlags(0x00000080)
            else:
                activity.getWindow().clearFlags(0x00000080)
        except:
            pass

def vibrate(duration=100):
    """Vibrate device"""
    if platform == 'android':
        try:
            from jnius import autoclass
            PythonActivity = autoclass('org.kivy.android.PythonActivity')
            activity = PythonActivity.mActivity
            vibrator = activity.getSystemService('vibrator')
            vibrator.vibrate(duration)
        except:
            pass

def share_text(text, title="Share"):
    """Share text"""
    if platform == 'android':
        try:
            from jnius import autoclass
            PythonActivity = autoclass('org.kivy.android.PythonActivity')
            Intent = autoclass('android.content.Intent')
            String = autoclass('java.lang.String')
            
            intent = Intent()
            intent.setAction(Intent.ACTION_SEND)
            intent.setType('text/plain')
            intent.putExtra(Intent.EXTRA_TEXT, String(text))
            intent.putExtra(Intent.EXTRA_SUBJECT, String(title))
            
            chooser = Intent.createChooser(intent, String(title))
            PythonActivity.mActivity.startActivity(chooser)
            return True
        except:
            pass
    print(f"Share: {text}")
    return False

def get_device_info():
    """Get device info"""
    info = {'platform': platform, 'storage_path': str(get_storage_path())}
    if platform == 'android':
        try:
            from jnius import autoclass
            Build = autoclass('android.os.Build')
            info.update({
                'model': Build.MODEL,
                'manufacturer': Build.MANUFACTURER,
                'version': Build.VERSION.RELEASE
            })
        except:
            pass
    return info

def check_network_connection():
    """Check network"""
    if platform == 'android':
        try:
            from jnius import autoclass
            PythonActivity = autoclass('org.kivy.android.PythonActivity')
            activity = PythonActivity.mActivity
            connectivity_manager = activity.getSystemService('connectivity')
            network_info = connectivity_manager.getActiveNetworkInfo()
            return network_info is not None and network_info.isConnected()
        except:
            pass
    try:
        import urllib.request
        urllib.request.urlopen('https://www.google.com', timeout=3)
        return True
    except:
        return False

class LifecycleManager:
    """App lifecycle manager"""
    def __init__(self):
        self.callbacks = {}
    
    def register_callback(self, event, callback):
        if event not in self.callbacks:
            self.callbacks[event] = []
        self.callbacks[event].append(callback)
    
    def trigger_callbacks(self, event):
        if event in self.callbacks:
            for callback in self.callbacks[event]:
                try:
                    callback()
                except Exception as e:
                    Logger.error(f"Lifecycle callback error: {e}")

lifecycle_manager = LifecycleManager()
EOF
        log_success "✅ android_utils.py created"
    fi
}

# Build function
build_debug() {
    log_info "Building APK with Python 3.10..."
    
    export ANDROID_HOME="$HOME/android-sdk"
    export PATH="$JAVA_HOME/bin:$PATH:$ANDROID_HOME/cmdline-tools/latest/bin:$ANDROID_HOME/platform-tools"
    
    if [[ "$1" == "--clean" ]]; then
        rm -rf .buildozer bin
    fi
    
    log_info "Build environment:"
    echo "  - Python: $(python --version) ($(which python))"
    echo "  - Java: $(java -version 2>&1 | head -n1)"
    echo "  - ANDROID_HOME: $ANDROID_HOME"
    
    if buildozer android debug; then
        log_success "🎉 Build successful with Python 3.10!"
        if ls bin/*.apk &>/dev/null; then
            apk_file=$(ls bin/*.apk | head -1)
            log_success "📱 APK created: $apk_file"
        fi
        return 0
    else
        log_error "❌ Build failed"
        return 1
    fi
}

# Main function
main() {
    case ${1:-help} in
        "setup")
            log_info "🔧 Setting up Python 3.10 environment for better Kivy compatibility"
            setup_python310_environment
            create_venv_python310
            install_kivy_python310
            setup_java_android
            create_android_utils
            create_buildozer_spec_310
            log_success "✅ Python 3.10 environment ready!"
            ;;
            
        "debug")
            log_info "🛠️ Building with Python 3.10"
            setup_python310_environment
            source venv/bin/activate
            setup_java_android
            build_debug "$2"
            ;;
            
        "clean")
            log_info "🧹 Cleaning build artifacts"
            rm -rf venv .buildozer bin __pycache__ build
            log_success "✅ Cleanup complete"
            ;;
            
        "test")
            log_info "🧪 Testing Python 3.10 environment"
            if [[ -f "venv/bin/activate" ]]; then
                source venv/bin/activate
                python -c "
import sys
print(f'Python: {sys.version}')
import kivy
print(f'Kivy: {kivy.__version__}')
print('✅ Environment test passed')
"
            else
                log_error "Virtual environment not found. Run setup first."
            fi
            ;;
            
        *)
            echo "MyTalk Android App - Python 3.10 Build Script"
            echo ""
            echo "Usage: $0 {setup|debug|clean|test}"
            echo ""
            echo "Commands:"
            echo "  setup          - Complete Python 3.10 environment setup"
            echo "  debug          - Build debug APK"
            echo "  debug --clean  - Clean build debug APK"
            echo "  clean          - Clean all build artifacts"
            echo "  test           - Test environment"
            echo ""
            echo "This script uses Python 3.10 for better Kivy compatibility!"
            ;;
    esac
}

main "$@"