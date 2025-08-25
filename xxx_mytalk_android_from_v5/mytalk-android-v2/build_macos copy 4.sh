#!/bin/bash

# MyTalk Android App - Enhanced macOS Build Script
# Fixed for Kivy compilation issues and optimized for Python 3.11

set -e

echo "🎙️ MyTalk Android App - Enhanced Build Script"
echo "=============================================="

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Logging functions
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
    PLATFORM="Apple Silicon"
    HOMEBREW_PREFIX="/opt/homebrew"
else
    PLATFORM="Intel"
    HOMEBREW_PREFIX="/usr/local"
fi

log_info "Platform: $PLATFORM ($ARCH)"

# Enhanced Python 3.11 setup
setup_python311_environment() {
    log_info "Setting up Python 3.11 environment..."
    
    # Deactivate any conda environments
    if command -v conda &> /dev/null; then
        log_info "Deactivating conda environments..."
        conda deactivate 2>/dev/null || true
        # Remove conda from PATH temporarily
        export PATH=$(echo $PATH | sed -e 's|[^:]*conda[^:]*:||g')
    fi
    
    # Set Homebrew-first PATH
    export PATH="${HOMEBREW_PREFIX}/bin:${HOMEBREW_PREFIX}/sbin:/usr/bin:/bin:/usr/sbin:/sbin"
    
    # Install Python 3.11 if not present
    PYTHON311_PATH="${HOMEBREW_PREFIX}/bin/python3.11"
    
    if [[ ! -f "$PYTHON311_PATH" ]]; then
        log_info "Installing Python 3.11..."
        brew install python@3.11
    fi
    
    # Verify Python 3.11
    if [[ -f "$PYTHON311_PATH" ]]; then
        py311_version=$("$PYTHON311_PATH" --version)
        log_success "Python 3.11 confirmed: $py311_version"
        export PYTHON_CMD="$PYTHON311_PATH"
    else
        log_error "Python 3.11 not found at $PYTHON311_PATH"
        exit 1
    fi
    
    # Install pip if needed
    "$PYTHON_CMD" -m ensurepip --upgrade 2>/dev/null || true
}

# Create virtual environment with Python 3.11
create_venv_python311() {
    log_info "Creating Python 3.11 virtual environment..."
    
    # Remove existing venv
    if [[ -d "venv" ]]; then
        log_info "Removing existing virtual environment..."
        rm -rf venv
    fi
    
    # Create new venv with Python 3.11
    if "$PYTHON_CMD" -m venv venv; then
        log_success "Virtual environment created successfully"
    else
        log_error "Failed to create virtual environment"
        exit 1
    fi
    
    # Activate venv
    source venv/bin/activate
    
    # Verify venv Python version
    venv_python_version=$(python --version)
    venv_python_path=$(which python)
    log_info "Venv Python: $venv_python_version at $venv_python_path"
    
    if [[ "$venv_python_version" =~ "3.11" ]]; then
        log_success "✅ Python 3.11 virtual environment ready"
    else
        log_error "❌ Virtual environment not using Python 3.11: $venv_python_version"
        exit 1
    fi
}

# Enhanced Kivy installation for macOS
install_kivy_python311() {
    log_info "Installing Kivy and dependencies for Python 3.11 on macOS..."
    
    # Upgrade pip and essential tools
    pip install --upgrade pip wheel setuptools
    
    # Install Cython with specific version for Python 3.11 compatibility
    log_info "Installing Cython..."
    pip install "Cython>=0.29.33,<3.0" --no-cache-dir
    
    # Install numpy (Kivy dependency)
    log_info "Installing numpy..."
    pip install "numpy>=1.21.0,<2.0" --no-cache-dir
    
    # Set macOS build environment variables
    export LDFLAGS="-L${HOMEBREW_PREFIX}/lib"
    export CPPFLAGS="-I${HOMEBREW_PREFIX}/include"
    export PKG_CONFIG_PATH="${HOMEBREW_PREFIX}/lib/pkgconfig"
    
    # Set architecture-specific flags
    if [[ "$ARCH" == "arm64" ]]; then
        export ARCHFLAGS="-arch arm64"
        export CFLAGS="-arch arm64"
    else
        export ARCHFLAGS="-arch x86_64"
        export CFLAGS="-arch x86_64"
    fi
    
    # Install SDL2 dependencies via Homebrew
    log_info "Installing SDL2 dependencies..."
    local sdl_deps=("sdl2" "sdl2_image" "sdl2_ttf" "sdl2_mixer" "pkg-config")
    
    for dep in "${sdl_deps[@]}"; do
        if ! brew list "$dep" &>/dev/null; then
            log_info "Installing $dep..."
            brew install "$dep"
        else
            log_info "$dep already installed"
        fi
    done
    
    # Additional macOS-specific dependencies
    local extra_deps=("freetype" "harfbuzz" "fribidi" "glib" "gettext")
    for dep in "${extra_deps[@]}"; do
        if ! brew list "$dep" &>/dev/null; then
            log_info "Installing $dep..."
            brew install "$dep" 2>/dev/null || log_warning "Could not install $dep"
        fi
    done
    
    # Set additional environment variables for macOS compilation
    export KIVY_DEPS_ROOT="${HOMEBREW_PREFIX}"
    export USE_OSX_FRAMEWORKS=0
    export KIVY_SDL_GL_ALPHA_SIZE=8
    
    # Try binary installation first
    log_info "Attempting binary Kivy installation..."
    if pip install "kivy[base]==2.1.0" --only-binary=kivy --no-cache-dir; then
        log_success "✅ Kivy binary installation successful"
    else
        log_warning "Binary installation failed, trying source build..."
        
        # Additional source build environment
        export CC=clang
        export CXX=clang++
        
        # Install from source with verbose output
        if pip install "kivy[base]==2.1.0" --no-binary=kivy --verbose --no-cache-dir; then
            log_success "✅ Kivy source installation successful"
        else
            log_error "❌ Kivy installation failed"
            log_error "Try running: brew install sdl2 sdl2_image sdl2_ttf sdl2_mixer"
            exit 1
        fi
    fi
    
    # Install other dependencies
    log_info "Installing additional Python packages..."
    pip install kivymd buildozer
    
    # Install OpenAI and networking dependencies
    pip install "openai>=1.0.0" requests certifi urllib3 charset-normalizer idna
    
    # Verify Kivy installation
    if python -c "import kivy; print(f'Kivy {kivy.__version__} installed successfully')" 2>/dev/null; then
        log_success "✅ Kivy verification passed"
    else
        log_error "❌ Kivy verification failed"
        exit 1
    fi
}

# Java 17 setup
setup_java17() {
    log_info "Setting up Java 17..."
    
    # Check if Java 17 is already installed
    if java -version 2>&1 | grep -q "17\."; then
        log_success "Java 17 already available"
    else
        if ! brew list --cask temurin@17 &>/dev/null; then
            log_info "Installing Java 17..."
            brew install --cask temurin@17
        fi
    fi
    
    # Set JAVA_HOME
    export JAVA_HOME=$(/usr/libexec/java_home -v 17 2>/dev/null || echo "/Library/Java/JavaVirtualMachines/temurin-17.jdk/Contents/Home")
    export PATH="$JAVA_HOME/bin:$PATH"
    
    if [[ -d "$JAVA_HOME" ]]; then
        java_version=$(java -version 2>&1 | head -n1)
        log_success "✅ Java 17 configured: $java_version"
        log_info "JAVA_HOME: $JAVA_HOME"
    else
        log_error "❌ Java 17 setup failed"
        exit 1
    fi
}

# Android SDK setup with better error handling
setup_android_sdk() {
    log_info "Setting up Android SDK..."
    
    export ANDROID_HOME="$HOME/android-sdk"
    export ANDROID_SDK_ROOT="$ANDROID_HOME"
    
    # Create SDK directory
    mkdir -p "$ANDROID_HOME/cmdline-tools"
    
    # Download and install command line tools if not present
    if [[ ! -d "$ANDROID_HOME/cmdline-tools/latest" ]]; then
        log_info "Downloading Android command line tools..."
        cd "$ANDROID_HOME/cmdline-tools"
        
        # Use the latest command line tools
        CMDLINE_TOOLS_URL="https://dl.google.com/android/repository/commandlinetools-mac-11076708_latest.zip"
        
        if command -v curl &> /dev/null; then
            curl -o cmdline-tools.zip -L "$CMDLINE_TOOLS_URL"
        elif command -v wget &> /dev/null; then
            wget -O cmdline-tools.zip "$CMDLINE_TOOLS_URL"
        else
            log_error "Neither curl nor wget available for download"
            exit 1
        fi
        
        unzip -q cmdline-tools.zip
        mv cmdline-tools latest
        rm cmdline-tools.zip
        
        cd - > /dev/null
        log_success "Android command line tools installed"
    fi
    
    # Set PATH for Android tools
    export PATH="$PATH:$ANDROID_HOME/cmdline-tools/latest/bin:$ANDROID_HOME/platform-tools"
    
    # Accept licenses and install components
    log_info "Installing Android SDK components..."
    yes | "$ANDROID_HOME/cmdline-tools/latest/bin/sdkmanager" --licenses &>/dev/null || true
    
    # Install required components
    local components=(
        "platform-tools"
        "platforms;android-34"
        "build-tools;34.0.0"
        "ndk;26.1.10909125"
        "extras;android;m2repository"
        "extras;google;m2repository"
    )
    
    for component in "${components[@]}"; do
        log_info "Installing $component..."
        "$ANDROID_HOME/cmdline-tools/latest/bin/sdkmanager" "$component" &>/dev/null || log_warning "Failed to install $component"
    done
    
    log_success "✅ Android SDK setup complete"
}

# Enhanced buildozer.spec creation
create_buildozer_spec() {
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

# Enhanced requirements for better compatibility
requirements = python3,kivy==2.1.0,kivymd,openai,requests,certifi,urllib3,charset-normalizer,idna,Cython

# Android settings
orientation = portrait
fullscreen = 0

# Enhanced permissions
android.permissions = INTERNET,WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE,RECORD_AUDIO,ACCESS_NETWORK_STATE,WAKE_LOCK

# Architecture settings
android.archs = arm64-v8a, armeabi-v7a

# API levels
android.api = 34
android.minapi = 21
android.ndk = 26b
android.sdk = 34

# Backup settings
android.allow_backup = True

# Buildozer settings
[buildozer]
log_level = 2
warn_on_root = 1

# P4A settings for better compatibility
p4a.fork = kivy
p4a.branch = develop
p4a.bootstrap = sdl2
EOF

    log_success "✅ Enhanced buildozer.spec created"
}

# Build function with better error handling
build_debug() {
    log_info "Starting debug build..."
    
    # Ensure all environment variables are set
    export ANDROID_HOME="$HOME/android-sdk"
    export ANDROID_SDK_ROOT="$ANDROID_HOME"
    export PATH="$JAVA_HOME/bin:$PATH:$ANDROID_HOME/cmdline-tools/latest/bin:$ANDROID_HOME/platform-tools"
    
    # Set build environment variables
    export LDFLAGS="-L${HOMEBREW_PREFIX}/lib"
    export CPPFLAGS="-I${HOMEBREW_PREFIX}/include"
    export PKG_CONFIG_PATH="${HOMEBREW_PREFIX}/lib/pkgconfig"
    
    if [[ "$ARCH" == "arm64" ]]; then
        export ARCHFLAGS="-arch arm64"
    fi
    
    # Display build environment info
    log_info "Build environment:"
    echo "  - Python: $(python --version) ($(which python))"
    echo "  - Java: $(java -version 2>&1 | head -n1)"
    echo "  - ANDROID_HOME: $ANDROID_HOME"
    echo "  - JAVA_HOME: $JAVA_HOME"
    echo "  - Architecture: $ARCH"
    
    # Clean previous builds if requested
    if [[ "$1" == "--clean" ]]; then
        log_info "Cleaning previous builds..."
        rm -rf .buildozer bin
    fi
    
    # Run buildozer with error handling
    log_info "Running buildozer android debug..."
    
    if buildozer android debug; then
        log_success "🎉 Build completed successfully!"
        
        # Check for APK file
        if ls bin/*.apk &>/dev/null; then
            apk_file=$(ls bin/*.apk | head -1)
            apk_size=$(du -h "$apk_file" | cut -f1)
            log_success "📱 APK created: $apk_file ($apk_size)"
            
            # Show installation instructions
            echo ""
            echo "📋 Installation Instructions:"
            echo "  1. Enable 'Unknown Sources' on your Android device"
            echo "  2. Transfer the APK file to your device"
            echo "  3. Install the APK file"
            echo ""
            echo "Or use ADB: adb install \"$apk_file\""
        fi
        
        return 0
    else
        log_error "❌ Build failed"
        log_error "Check the build log above for detailed error information"
        return 1
    fi
}

# Missing file creation function
create_missing_files() {
    log_info "Creating missing Android utility files..."
    
    # Create android_utils.py if missing
    if [[ ! -f "android_utils.py" ]]; then
        log_info "Creating android_utils.py..."
        cat > android_utils.py << 'EOF'
"""
Android utility functions for MyTalk app
Handles Android-specific functionality with fallbacks for desktop
"""

import os
import json
import tempfile
from pathlib import Path
from kivy.utils import platform
from kivy.logger import Logger


def get_storage_path():
    """Get appropriate storage path for the platform"""
    if platform == 'android':
        try:
            from jnius import autoclass, cast
            from android.permissions import request_permissions, Permission
            
            # Request storage permissions
            request_permissions([
                Permission.WRITE_EXTERNAL_STORAGE,
                Permission.READ_EXTERNAL_STORAGE
            ])
            
            # Get external storage directory
            Environment = autoclass('android.os.Environment')
            context = autoclass('org.kivy.android.PythonActivity').mActivity
            
            external_path = context.getExternalFilesDir(None)
            if external_path:
                return Path(str(external_path.toString())) / "MyTalk"
            else:
                # Fallback to internal storage
                internal_path = context.getFilesDir()
                return Path(str(internal_path.toString())) / "MyTalk"
        except Exception as e:
            Logger.error(f"Android storage error: {e}")
            return Path.home() / "MyTalk"
    else:
        return Path.home() / "MyTalk"


def request_android_permissions():
    """Request necessary Android permissions"""
    if platform == 'android':
        try:
            from android.permissions import request_permissions, Permission
            request_permissions([
                Permission.WRITE_EXTERNAL_STORAGE,
                Permission.READ_EXTERNAL_STORAGE,
                Permission.RECORD_AUDIO,
                Permission.INTERNET,
                Permission.ACCESS_NETWORK_STATE
            ])
            return True
        except Exception as e:
            Logger.error(f"Permission request error: {e}")
            return False
    return True


def show_toast(message, duration=2000):
    """Show toast message on Android, print on desktop"""
    if platform == 'android':
        try:
            from jnius import autoclass
            Toast = autoclass('android.widget.Toast')
            context = autoclass('org.kivy.android.PythonActivity').mActivity
            String = autoclass('java.lang.String')
            
            toast = Toast.makeText(context, String(message), Toast.LENGTH_SHORT)
            toast.show()
        except Exception as e:
            Logger.error(f"Toast error: {e}")
            print(f"Toast: {message}")
    else:
        print(f"Info: {message}")


def initialize_android_app():
    """Initialize Android-specific app components"""
    if platform == 'android':
        request_android_permissions()
        return True
    return False


def keep_screen_on(keep_on=True):
    """Keep screen on during operations"""
    if platform == 'android':
        try:
            from jnius import autoclass
            PythonActivity = autoclass('org.kivy.android.PythonActivity')
            activity = PythonActivity.mActivity
            
            if keep_on:
                activity.getWindow().addFlags(0x00000080)  # FLAG_KEEP_SCREEN_ON
            else:
                activity.getWindow().clearFlags(0x00000080)
        except Exception as e:
            Logger.error(f"Keep screen on error: {e}")


def vibrate(duration=100):
    """Vibrate device"""
    if platform == 'android':
        try:
            from jnius import autoclass
            PythonActivity = autoclass('org.kivy.android.PythonActivity')
            activity = PythonActivity.mActivity
            vibrator = activity.getSystemService('vibrator')
            vibrator.vibrate(duration)
        except Exception as e:
            Logger.error(f"Vibrate error: {e}")


def share_text(text, title="Share"):
    """Share text content"""
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
        except Exception as e:
            Logger.error(f"Share error: {e}")
            return False
    else:
        print(f"Share: {text}")
        return False


def get_device_info():
    """Get device information"""
    info = {
        'platform': platform,
        'storage_path': str(get_storage_path())
    }
    
    if platform == 'android':
        try:
            from jnius import autoclass
            Build = autoclass('android.os.Build')
            info.update({
                'model': Build.MODEL,
                'manufacturer': Build.MANUFACTURER,
                'version': Build.VERSION.RELEASE,
                'sdk': Build.VERSION.SDK_INT
            })
        except Exception as e:
            Logger.error(f"Device info error: {e}")
    
    return info


def check_network_connection():
    """Check if network connection is available"""
    if platform == 'android':
        try:
            from jnius import autoclass
            PythonActivity = autoclass('org.kivy.android.PythonActivity')
            activity = PythonActivity.mActivity
            
            connectivity_manager = activity.getSystemService('connectivity')
            network_info = connectivity_manager.getActiveNetworkInfo()
            
            return network_info is not None and network_info.isConnected()
        except Exception as e:
            Logger.error(f"Network check error: {e}")
            return True  # Assume connected on error
    else:
        # Simple network check for desktop
        try:
            import urllib.request
            urllib.request.urlopen('https://www.google.com', timeout=3)
            return True
        except:
            return False


class LifecycleManager:
    """Manage app lifecycle callbacks"""
    
    def __init__(self):
        self.callbacks = {}
    
    def register_callback(self, event, callback):
        """Register callback for lifecycle event"""
        if event not in self.callbacks:
            self.callbacks[event] = []
        self.callbacks[event].append(callback)
    
    def trigger_callbacks(self, event):
        """Trigger callbacks for event"""
        if event in self.callbacks:
            for callback in self.callbacks[event]:
                try:
                    callback()
                except Exception as e:
                    Logger.error(f"Lifecycle callback error: {e}")


# Global lifecycle manager
lifecycle_manager = LifecycleManager()
EOF
        log_success "✅ android_utils.py created"
    fi
}

# Main execution function
main() {
    case ${1:-help} in
        "setup")
            log_info "🔧 Setting up complete Python 3.11 development environment"
            setup_python311_environment
            create_venv_python311
            install_kivy_python311
            setup_java17
            setup_android_sdk
            create_missing_files
            create_buildozer_spec
            log_success "✅ Development environment setup complete!"
            echo ""
            echo "Next steps:"
            echo "  1. Run: $0 debug"
            echo "  2. Or run: $0 debug --clean (for clean build)"
            ;;
            
        "debug")
            log_info "🛠️ Building debug APK"
            setup_python311_environment
            source venv/bin/activate
            setup_java17
            build_debug "$2"
            ;;
            
        "clean")
            log_info "🧹 Cleaning build artifacts"
            rm -rf venv .buildozer bin __pycache__ build
            find . -name "*.pyc" -delete
            find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
            log_success "✅ Cleanup complete"
            ;;
            
        "test")
            log_info "🧪 Testing Python environment"
            setup_python311_environment
            source venv/bin/activate
            python -c "
import sys
print(f'Python: {sys.version}')
try:
    import kivy
    print(f'Kivy: {kivy.__version__}')
except ImportError as e:
    print(f'Kivy not available: {e}')
try:
    import openai
    print('OpenAI: Available')
except ImportError:
    print('OpenAI: Not available')
"
            ;;
            
        *)
            echo "MyTalk Android App - Enhanced Build Script"
            echo ""
            echo "Usage: $0 {setup|debug|clean|test}"
            echo ""
            echo "Commands:"
            echo "  setup        - Complete development environment setup"
            echo "  debug        - Build debug APK"
            echo "  debug --clean - Clean build debug APK"
            echo "  clean        - Clean all build artifacts"
            echo "  test         - Test Python environment"
            echo ""
            echo "Prerequisites:"
            echo "  - macOS with Homebrew installed"
            echo "  - Xcode Command Line Tools"
            echo "  - Internet connection"
            ;;
    esac
}

# Execute main function
main "$@"