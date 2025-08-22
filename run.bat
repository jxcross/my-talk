@echo off
echo 🎙️ MyTalk 시작 중...

REM 가상환경 확인
if not exist "mytalk_env" (
    echo 📦 가상환경 생성 중...
    python -m venv mytalk_env
)

REM 가상환경 활성화
call mytalk_env\Scripts\activate

REM 패키지 설치 확인
if not exist ".installed" (
    echo 📚 필요한 패키지 설치 중...
    pip install -r requirements.txt
    echo. > .installed
)

REM Streamlit 설정 폴더 생성
if not exist ".streamlit" mkdir .streamlit

REM 캐시 폴더 생성
if not exist "cache" mkdir cache

REM 앱 실행
echo 🚀 앱을 시작합니다...
echo 📱 브라우저가 자동으로 열립니다.
echo 📱 모바일 접속: 같은 WiFi에서 http://[YOUR_IP]:8501
echo.
echo 종료하려면 Ctrl+C를 누르세요.

streamlit run main.py --server.address 0.0.0.0