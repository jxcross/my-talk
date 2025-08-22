#!/usr/bin/env python3
"""
MyTalk 자동 설치 스크립트
"""

import os
import sys
import subprocess
import platform

def run_command(command):
    """명령 실행"""
    try:
        subprocess.run(command, shell=True, check=True)
        return True
    except subprocess.CalledProcessError:
        return False

def main():
    print("="*50)
    print("🎙️ MyTalk 설치 프로그램")
    print("="*50)
    
    # Python 버전 확인
    if sys.version_info < (3, 8):
        print("❌ Python 3.8 이상이 필요합니다.")
        sys.exit(1)
    
    print(f"✅ Python {sys.version} 감지됨")
    
    # 가상환경 생성
    print("\n📦 가상환경 생성 중...")
    if not os.path.exists("mytalk_env"):
        if not run_command(f"{sys.executable} -m venv mytalk_env"):
            print("❌ 가상환경 생성 실패")
            sys.exit(1)
    
    # 가상환경 활성화 경로
    if platform.system() == "Windows":
        pip_path = os.path.join("mytalk_env", "Scripts", "pip")
        python_path = os.path.join("mytalk_env", "Scripts", "python")
    else:
        pip_path = os.path.join("mytalk_env", "bin", "pip")
        python_path = os.path.join("mytalk_env", "bin", "python")
    
    # 패키지 설치
    print("\n📚 필요한 패키지 설치 중...")
    packages = [
        "streamlit==1.31.0",
        "openai==0.28.1",
        "anthropic==0.18.1",
        "google-generativeai==0.3.2",
        "edge-tts==6.1.9",
        "Pillow==10.2.0",
        "google-auth==2.27.0",
        "google-api-python-client==2.116.0"
    ]
    
    for package in packages:
        print(f"  - {package} 설치 중...")
        if not run_command(f"{pip_path} install {package}"):
            print(f"  ⚠️ {package} 설치 실패 (계속 진행)")
    
    # 필요한 폴더 생성
    print("\n📁 필요한 폴더 생성 중...")
    folders = [".streamlit", "cache", "exports", "backups"]
    for folder in folders:
        if not os.path.exists(folder):
            os.makedirs(folder)
            print(f"  ✅ {folder} 폴더 생성됨")
    
    # 설정 파일 생성
    if not os.path.exists(".streamlit/config.toml"):
        print("\n⚙️ 설정 파일 생성 중...")
        config_content = """[theme]
base = "light"
primaryColor = "#4CAF50"

[server]
address = "0.0.0.0"
port = 8501
maxUploadSize = 10

[browser]
gatherUsageStats = false
"""
        with open(".streamlit/config.toml", "w") as f:
            f.write(config_content)
        print("  ✅ 설정 파일 생성됨")
    
    # 완료
    print("\n" + "="*50)
    print("✅ 설치 완료!")
    print("="*50)
    print("\n🚀 앱 실행 방법:")
    
    if platform.system() == "Windows":
        print("  1. run.bat 실행")
        print("  또는")
        print("  2. mytalk_env\\Scripts\\activate")
        print("     streamlit run main.py")
    else:
        print("  1. ./run.sh 실행")
        print("  또는")
        print("  2. source mytalk_env/bin/activate")
        print("     streamlit run main.py")
    
    print("\n📱 모바일 접속:")
    print("  같은 WiFi 네트워크에서 http://[PC_IP]:8501")
    
    print("\n📖 자세한 사용법은 README.md를 참조하세요.")

if __name__ == "__main__":
    main()