#!/bin/bash
# run.sh - Linux/Mac 실행 스크립트

echo "🎙️ MyTalk 시작 중..."

# 가상환경 확인
if [ ! -d "mytalk_env" ]; then
    echo "📦 가상환경 생성 중..."
    python3 -m venv mytalk_env
fi

# 가상환경 활성화
source mytalk_env/bin/activate

# 패키지 설치 확인
if [ ! -f ".installed" ]; then
    echo "📚 필요한 패키지 설치 중..."
    pip install -r requirements.txt
    touch .installed
fi

# Streamlit 설정 폴더 생성
if [ ! -d ".streamlit" ]; then
    mkdir .streamlit
fi

# 캐시 폴더 생성
if [ ! -d "cache" ]; then
    mkdir cache
fi

# 앱 실행
echo "🚀 앱을 시작합니다..."
echo "📱 브라우저가 자동으로 열립니다."
echo "📱 모바일 접속: 같은 WiFi에서 http://[YOUR_IP]:8501"
echo ""
echo "종료하려면 Ctrl+C를 누르세요."

streamlit run main.py --server.address 0.0.0.0
