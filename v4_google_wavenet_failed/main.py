"""
MyTalk - 통합 버전 (Google Wavenet TTS + OAuth 2.0 Google Drive)
모든 기능이 하나의 파일에 통합된 영어 말하기 학습 앱

주요 기능:
1. AI 기반 다양한 스타일의 영어 스크립트 생성 (TED, 팟캐스트, 일상 대화)
2. Google Wavenet TTS를 포함한 다중 TTS 엔진 지원
3. OAuth 2.0 방식 Google Drive 동기화
4. 로컬 파일 시스템과 클라우드 이중 저장
5. 실시간 동기화 및 충돌 해결
6. 오프라인 모드 지원
7. 자동 백업 및 복원
"""

import streamlit as st
import os
import json
import sqlite3
from datetime import datetime, timedelta
import base64
from pathlib import Path
import tempfile
from PIL import Image
import io
import time
import uuid
import shutil
import threading
import hashlib
import pickle
from typing import Optional, Dict, List, Tuple
import queue

# Google Drive API 라이브러리 (OAuth 2.0)
try:
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload, MediaIoBaseUpload
    from googleapiclient.errors import HttpError
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    GOOGLE_DRIVE_AVAILABLE = True
except ImportError:
    GOOGLE_DRIVE_AVAILABLE = False

# Google Cloud TTS (Wavenet)
try:
    from google.cloud import texttospeech
    GOOGLE_TTS_AVAILABLE = True
except ImportError:
    GOOGLE_TTS_AVAILABLE = False

# 기본 TTS 엔진들
try:
    from gtts import gTTS
    GTTS_AVAILABLE = True
except ImportError:
    GTTS_AVAILABLE = False

try:
    import pyttsx3
    PYTTSX3_AVAILABLE = True
except ImportError:
    PYTTSX3_AVAILABLE = False

# LLM Providers
try:
    import openai
except ImportError:
    openai = None

try:
    from anthropic import Anthropic
except ImportError:
    Anthropic = None

try:
    import google.generativeai as genai
except ImportError:
    genai = None


# =============================================================================
# TTS 모듈 (Google Wavenet 포함)
# =============================================================================

class GoogleWavenetTTS:
    """Google Cloud Text-to-Speech (Wavenet) 클래스"""
    
    def __init__(self):
        self.client = None
        self.credentials_file = None
        self.setup_client()
    
    def setup_client(self):
        """클라이언트 초기화"""
        try:
            # 환경변수에서 인증 정보 확인
            credentials_path = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')
            
            if credentials_path and os.path.exists(credentials_path):
                self.client = texttospeech.TextToSpeechClient()
                self.credentials_file = credentials_path
                return True
            else:
                return False
                
        except Exception as e:
            return False
    
    def set_credentials_from_json(self, credentials_json):
        """JSON 문자열에서 인증 정보 설정"""
        try:
            from google.oauth2 import service_account
            
            # JSON 파싱
            credentials_info = json.loads(credentials_json)
            
            # 서비스 계정 인증 정보 생성
            credentials = service_account.Credentials.from_service_account_info(credentials_info)
            
            # 클라이언트 생성
            self.client = texttospeech.TextToSpeechClient(credentials=credentials)
            
            # 임시 파일에 저장 (선택사항)
            temp_credentials = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False)
            json.dump(credentials_info, temp_credentials, indent=2)
            temp_credentials.close()
            
            self.credentials_file = temp_credentials.name
            os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = self.credentials_file
            
            return True
            
        except Exception as e:
            st.error(f"Google Cloud 인증 설정 실패: {e}")
            return False
    
    def get_available_voices(self, language_code='en-US'):
        """사용 가능한 음성 목록 조회"""
        if not self.client:
            return []
        
        try:
            voices_request = texttospeech.ListVoicesRequest(language_code=language_code)
            voices_response = self.client.list_voices(request=voices_request)
            
            wavenet_voices = []
            for voice in voices_response.voices:
                if 'Wavenet' in voice.name or 'Neural2' in voice.name:
                    wavenet_voices.append({
                        'name': voice.name,
                        'language': voice.language_codes[0],
                        'gender': voice.ssml_gender.name
                    })
            
            return wavenet_voices
            
        except Exception as e:
            return []
    
    def generate_speech(self, text, voice_name='en-US-Wavenet-D', speaking_rate=1.0, pitch=0.0):
        """Wavenet TTS로 음성 생성"""
        if not self.client:
            raise Exception("Google Cloud TTS 클라이언트가 초기화되지 않았습니다.")
        
        try:
            # 텍스트 입력 설정
            synthesis_input = texttospeech.SynthesisInput(text=text)
            
            # 음성 설정
            voice = texttospeech.VoiceSelectionParams(
                name=voice_name,
                language_code=voice_name[:5]  # 'en-US', 'ko-KR' 등
            )
            
            # 오디오 설정
            audio_config = texttospeech.AudioConfig(
                audio_encoding=texttospeech.AudioEncoding.MP3,
                speaking_rate=speaking_rate,
                pitch=pitch
            )
            
            # TTS 요청
            response = self.client.synthesize_speech(
                input=synthesis_input,
                voice=voice,
                audio_config=audio_config
            )
            
            # 임시 파일에 저장
            temp_file = tempfile.NamedTemporaryFile(suffix='.mp3', delete=False)
            temp_file.write(response.audio_content)
            temp_file.close()
            
            return temp_file.name
            
        except Exception as e:
            raise Exception(f"Wavenet TTS 생성 실패: {e}")


class SimpleTTS:
    """간단한 TTS 클래스 (gTTS, pyttsx3)"""
    
    @staticmethod
    def gtts_generate(text, lang='en', slow=False):
        """gTTS로 음성 생성"""
        try:
            tts = gTTS(text=text, lang=lang, slow=slow)
            temp_file = tempfile.NamedTemporaryFile(suffix='.mp3', delete=False)
            tts.save(temp_file.name)
            return temp_file.name
        except Exception as e:
            raise Exception(f"gTTS 생성 실패: {e}")
    
    @staticmethod
    def pyttsx3_generate(text, rate=200, volume=0.9):
        """pyttsx3로 음성 생성"""
        try:
            engine = pyttsx3.init()
            engine.setProperty('rate', rate)
            engine.setProperty('volume', volume)
            
            temp_file = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
            engine.save_to_file(text, temp_file.name)
            engine.runAndWait()
            
            return temp_file.name
        except Exception as e:
            raise Exception(f"pyttsx3 생성 실패: {e}")


def get_wavenet_voice_name(voice_code):
    """음성 코드를 Wavenet 음성 이름으로 변환"""
    voice_mapping = {
        'en': 'en-US-Wavenet-D',
        'en-us': 'en-US-Wavenet-D',
        'en-uk': 'en-GB-Wavenet-B',
        'en-au': 'en-AU-Wavenet-B',
        'ko': 'ko-KR-Wavenet-A',
        'ko-kr': 'ko-KR-Wavenet-A',
        'ja': 'ja-JP-Wavenet-A',
        'zh': 'cmn-CN-Wavenet-A',
        'es': 'es-ES-Wavenet-A',
        'fr': 'fr-FR-Wavenet-A',
        'de': 'de-DE-Wavenet-A',
        'it': 'it-IT-Wavenet-A'
    }
    
    return voice_mapping.get(voice_code.lower(), 'en-US-Wavenet-D')


def get_gtts_lang_code(voice_code):
    """음성 코드를 gTTS 언어 코드로 변환"""
    lang_mapping = {
        'en': 'en',
        'en-us': 'en',
        'en-uk': 'en',
        'en-au': 'en',
        'ko': 'ko',
        'ko-kr': 'ko',
        'ja': 'ja',
        'zh': 'zh',
        'es': 'es',
        'fr': 'fr',
        'de': 'de',
        'it': 'it'
    }
    
    return lang_mapping.get(voice_code.lower(), 'en')


def generate_audio_with_fallback(text, engine='auto', voice='en-us', **kwargs):
    """폴백을 지원하는 TTS 생성 함수"""
    
    if not text or not text.strip():
        return None
    
    text = text.strip()
    
    # Wavenet 사용 시도
    if engine == 'wavenet' or engine == 'auto':
        if GOOGLE_TTS_AVAILABLE:
            try:
                wavenet = GoogleWavenetTTS()
                
                if wavenet.client:
                    voice_name = get_wavenet_voice_name(voice)
                    speaking_rate = kwargs.get('speaking_rate', 1.0)
                    pitch = kwargs.get('pitch', 0.0)
                    
                    audio_file = wavenet.generate_speech(
                        text=text,
                        voice_name=voice_name,
                        speaking_rate=speaking_rate,
                        pitch=pitch
                    )
                    
                    if audio_file and os.path.exists(audio_file):
                        st.info("🔊 Google Wavenet TTS로 음성 생성됨")
                        return audio_file
                else:
                    if engine == 'wavenet':
                        st.warning("Google Cloud TTS 인증이 설정되지 않았습니다. gTTS로 대체합니다.")
                        
            except Exception as e:
                if engine == 'wavenet':
                    st.error(f"Wavenet TTS 실패: {e}")
                    return None
    
    # gTTS 사용 시도
    if engine == 'gtts' or engine == 'auto':
        if GTTS_AVAILABLE:
            try:
                lang = get_gtts_lang_code(voice)
                slow = kwargs.get('slow', False)
                
                audio_file = SimpleTTS.gtts_generate(
                    text=text,
                    lang=lang,
                    slow=slow
                )
                
                if audio_file and os.path.exists(audio_file):
                    st.info("🔊 gTTS로 음성 생성됨")
                    return audio_file
                    
            except Exception as e:
                if engine == 'gtts':
                    st.error(f"gTTS 실패: {e}")
                    return None
    
    # pyttsx3 사용 시도
    if engine == 'pyttsx3' or engine == 'auto':
        if PYTTSX3_AVAILABLE:
            try:
                rate = kwargs.get('rate', 200)
                volume = kwargs.get('volume', 0.9)
                
                audio_file = SimpleTTS.pyttsx3_generate(
                    text=text,
                    rate=rate,
                    volume=volume
                )
                
                if audio_file and os.path.exists(audio_file):
                    st.info("🔊 pyttsx3로 음성 생성됨")
                    return audio_file
                    
            except Exception as e:
                if engine == 'pyttsx3':
                    st.error(f"pyttsx3 실패: {e}")
                    return None
    
    # 모든 엔진 실패
    st.warning("🔇 모든 TTS 엔진 사용 불가능")
    return None


def get_available_engines():
    """사용 가능한 TTS 엔진 목록 반환"""
    engines = ['auto (자동)']
    
    if GOOGLE_TTS_AVAILABLE:
        engines.append('wavenet (Google Cloud)')
    
    if GTTS_AVAILABLE:
        engines.append('gtts (Google Translate)')
    
    if PYTTSX3_AVAILABLE:
        engines.append('pyttsx3 (로컬)')
    
    return engines


def get_voice_options():
    """사용 가능한 음성 옵션 반환"""
    return {
        '영어 (미국)': 'en-us',
        '영어 (영국)': 'en-uk', 
        '영어 (호주)': 'en-au',
        '한국어': 'ko-kr',
        '일본어': 'ja',
        '중국어': 'zh',
        '스페인어': 'es',
        '프랑스어': 'fr',
        '독일어': 'de',
        '이탈리아어': 'it'
    }


def setup_google_tts_credentials():
    """Google Cloud TTS 인증 설정 UI"""
    st.markdown("#### 🔐 Google Cloud TTS 인증 설정")
    
    # 현재 상태 확인
    wavenet = GoogleWavenetTTS()
    
    if wavenet.client:
        st.success("✅ Google Cloud TTS가 설정되었습니다!")
        
        # 사용 가능한 음성 목록 표시
        show_voices = st.checkbox("🎤 사용 가능한 Wavenet 음성 보기")
        if show_voices:
            for lang in ['en-US', 'ko-KR', 'ja-JP']:
                voices = wavenet.get_available_voices(lang)
                if voices:
                    st.write(f"**{lang}:**")
                    for voice in voices[:3]:  # 상위 3개만 표시
                        st.write(f"- {voice['name']} ({voice['gender']})")
        
        return True
    
    else:
        st.warning("Google Cloud TTS가 설정되지 않았습니다.")
        
        show_guide = st.checkbox("📋 설정 가이드 보기")
        
        if show_guide:
            st.markdown("""
            ### Google Cloud Text-to-Speech API 설정 방법
            
            1. **Google Cloud Console 접속**
               - [Google Cloud Console](https://console.cloud.google.com/) 방문
            
            2. **프로젝트 생성 또는 선택**
               - 새 프로젝트 생성 또는 기존 프로젝트 선택
            
            3. **Text-to-Speech API 활성화**
               - API 및 서비스 > 라이브러리
               - "Cloud Text-to-Speech API" 검색 후 활성화
            
            4. **서비스 계정 생성**
               - IAM 및 관리자 > 서비스 계정
               - "서비스 계정 만들기" 클릭
               - 역할: "Cloud Text-to-Speech 클라이언트" 선택
            
            5. **JSON 키 파일 다운로드**
               - 생성된 서비스 계정 클릭
               - "키" 탭 > "키 추가" > "JSON"
               - 다운로드된 JSON 파일 내용을 아래에 입력
            
            ### 💰 비용 정보
            - 월 100만 문자까지 무료
            - 이후 100만 문자당 $4.00
            - Wavenet 음성: 100만 문자당 $16.00
            """)
        
        # JSON 인증 정보 입력
        credentials_json = st.text_area(
            "서비스 계정 JSON 키",
            height=200,
            placeholder="""{
  "type": "service_account",
  "project_id": "your-project-id",
  "private_key_id": "...",
  "private_key": "-----BEGIN PRIVATE KEY-----\\n...\\n-----END PRIVATE KEY-----\\n",
  "client_email": "your-service-account@your-project.iam.gserviceaccount.com",
  "client_id": "...",
  ...
}""",
            help="Google Cloud Console에서 다운로드한 서비스 계정 JSON 키를 붙여넣으세요"
        )
        
        if st.button("🔑 인증 설정"):
            if credentials_json.strip():
                wavenet = GoogleWavenetTTS()
                if wavenet.set_credentials_from_json(credentials_json):
                    st.success("✅ Google Cloud TTS 인증이 설정되었습니다!")
                    st.balloons()
                    st.rerun()
                else:
                    st.error("❌ 인증 설정에 실패했습니다.")
            else:
                st.error("JSON 키를 입력해주세요.")
        
        return False


def test_tts_engines():
    """TTS 엔진 테스트"""
    st.markdown("#### 🧪 TTS 엔진 테스트")
    
    test_text = st.text_input(
        "테스트 텍스트", 
        value="Hello, this is a test of the Text-to-Speech system.",
        help="음성 생성을 테스트할 텍스트를 입력하세요"
    )
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("🤖 Wavenet 테스트"):
            if GOOGLE_TTS_AVAILABLE:
                with st.spinner("Wavenet TTS 생성 중..."):
                    audio_file = generate_audio_with_fallback(
                        test_text, 
                        engine='wavenet', 
                        voice='en-us'
                    )
                    if audio_file:
                        st.audio(audio_file, format='audio/mp3')
                    else:
                        st.error("Wavenet TTS 테스트 실패")
            else:
                st.error("Google Cloud TTS가 설치되지 않았습니다.")
    
    with col2:
        if st.button("🌐 gTTS 테스트"):
            if GTTS_AVAILABLE:
                with st.spinner("gTTS 생성 중..."):
                    audio_file = generate_audio_with_fallback(
                        test_text, 
                        engine='gtts', 
                        voice='en'
                    )
                    if audio_file:
                        st.audio(audio_file, format='audio/mp3')
                    else:
                        st.error("gTTS 테스트 실패")
            else:
                st.error("gTTS가 설치되지 않았습니다.")
    
    with col3:
        if st.button("🖥️ pyttsx3 테스트"):
            if PYTTSX3_AVAILABLE:
                with st.spinner("pyttsx3 생성 중..."):
                    audio_file = generate_audio_with_fallback(
                        test_text, 
                        engine='pyttsx3', 
                        voice='en'
                    )
                    if audio_file:
                        st.audio(audio_file, format='audio/wav')
                    else:
                        st.error("pyttsx3 테스트 실패")
            else:
                st.error("pyttsx3가 설치되지 않았습니다.")
    
    # 자동 선택 테스트
    if st.button("🔄 자동 선택 테스트"):
        with st.spinner("최적의 TTS 엔진으로 생성 중..."):
            audio_file = generate_audio_with_fallback(
                test_text, 
                engine='auto', 
                voice='en-us'
            )
            if audio_file:
                st.audio(audio_file, format='audio/mp3')
            else:
                st.error("모든 TTS 엔진 사용 불가")


# =============================================================================
# Google Drive 관리 클래스 (OAuth 2.0)
# =============================================================================

class GoogleDriveManagerOAuth:
    """Google Drive API 관리 클래스 (OAuth 2.0 방식)"""
    
    def __init__(self):
        self.service = None
        self.credentials = None
        self.root_folder_id = None
        self.custom_folder_id = None
        self.folder_path = "MyTalk_Data"
        self.scopes = ['https://www.googleapis.com/auth/drive.file']
        self.credentials_file = 'credentials.json'
        self.token_file = 'token.pickle'
        
    def authenticate(self, credentials_json=None, force_reauth=False):
        """OAuth 2.0을 사용한 Google Drive 인증"""
        try:
            # OAuth 2.0 클라이언트 자격증명 저장
            if credentials_json:
                try:
                    credentials_info = json.loads(credentials_json)
                    required_fields = ['client_id', 'client_secret', 'auth_uri', 'token_uri']
                    for field in required_fields:
                        if field not in credentials_info.get('installed', {}):
                            raise ValueError(f"OAuth 2.0 클라이언트 JSON에 '{field}' 필드가 없습니다.")
                    
                    with open(self.credentials_file, 'w') as f:
                        json.dump(credentials_info, f, indent=2)
                    
                    st.success("OAuth 2.0 클라이언트 자격증명이 저장되었습니다.")
                    
                except json.JSONDecodeError:
                    raise ValueError("올바른 JSON 형식이 아닙니다.")
                except Exception as e:
                    raise Exception(f"OAuth 2.0 클라이언트 JSON 처리 오류: {str(e)}")
            
            # 기존 토큰 파일 확인 및 로드
            creds = None
            if os.path.exists(self.token_file) and not force_reauth:
                try:
                    with open(self.token_file, 'rb') as token:
                        creds = pickle.load(token)
                    st.info("🔒 기존 인증 토큰을 발견했습니다.")
                except Exception as e:
                    st.warning(f"토큰 파일 로드 실패: {e}")
                    st.info("🔄 새로운 인증을 진행합니다.")
            
            # 토큰 유효성 검사 및 갱신
            if creds:
                if creds.valid:
                    st.success("✅ 기존 토큰이 유효합니다. 자동 로그인 완료!")
                elif creds.expired and creds.refresh_token:
                    try:
                        st.info("🔄 만료된 토큰을 갱신 중...")
                        creds.refresh(Request())
                        st.success("✅ 토큰 갱신 완료!")
                        
                        with open(self.token_file, 'wb') as token:
                            pickle.dump(creds, token)
                            
                    except Exception as e:
                        st.warning(f"토큰 갱신 실패: {e}")
                        st.info("🔄 재인증이 필요합니다.")
                        creds = None
                else:
                    st.warning("토큰이 만료되었고 갱신할 수 없습니다.")
                    creds = None
            
            # 새로운 인증 진행
            if not creds or not creds.valid:
                if not os.path.exists(self.credentials_file):
                    if not credentials_json:
                        st.warning("OAuth 2.0 클라이언트 자격증명 파일이 필요합니다.")
                        return False
                    else:
                        return self.authenticate()
                
                st.info("🔐 OAuth 2.0 브라우저 인증이 필요합니다.")
                
                try:
                    flow = InstalledAppFlow.from_client_secrets_file(
                        self.credentials_file, self.scopes)
                    
                    # 인증 URL 생성
                    auth_url, _ = flow.authorization_url(prompt='consent')
                    
                    st.markdown(f"""
                    ### 🔐 Google OAuth 2.0 인증이 필요합니다
                    
                    1. 아래 링크를 클릭하여 Google 계정으로 로그인하세요:
                    
                    [Google 로그인 하기]({auth_url})
                    
                    2. 권한을 승인한 후 받은 인증 코드를 아래 입력창에 붙여넣으세요:
                    """)
                    
                    # Streamlit에서 인증 코드 입력받기
                    auth_code = st.text_input(
                        "인증 코드 입력",
                        placeholder="Google에서 받은 인증 코드를 여기에 붙여넣으세요",
                        help="브라우저에서 Google 로그인 후 받은 코드를 입력하세요"
                    )
                    
                    if auth_code:
                        try:
                            flow.fetch_token(code=auth_code)
                            creds = flow.credentials
                            st.success("✅ 수동 인증 완료!")
                        except Exception as auth_error:
                            st.error(f"인증 코드 처리 실패: {str(auth_error)}")
                            return False
                    else:
                        return False
                    
                    # 인증 토큰 저장
                    with open(self.token_file, 'wb') as token:
                        pickle.dump(creds, token)
                        st.info(f"💾 인증 토큰이 '{self.token_file}'에 저장되었습니다.")
                        st.success("🎉 다음번 실행부터는 자동으로 로그인됩니다!")
                    
                except Exception as e:
                    st.error(f"OAuth 2.0 인증 실패: {str(e)}")
                    return False
            
            # API 서비스 생성
            try:
                self.service = build('drive', 'v3', credentials=creds)
                self.credentials = creds
                
                # 루트 폴더 설정
                self.setup_root_folder()
                
                st.success("✅ Google Drive OAuth 2.0 인증 성공!")
                return True
                
            except Exception as e:
                st.error(f"API 서비스 생성 실패: {str(e)}")
                return False
                
        except Exception as e:
            st.error(f"Google Drive 인증 실패: {str(e)}")
            return False
    
    def is_authenticated(self):
        """인증 상태 확인"""
        return self.service is not None and self.credentials is not None
    
    def get_oauth_info(self):
        """OAuth 2.0 클라이언트 정보 조회"""
        if os.path.exists(self.credentials_file):
            try:
                with open(self.credentials_file, 'r') as f:
                    credentials_info = json.load(f)
                client_info = credentials_info.get('installed', {})
                return {
                    'client_id': client_info.get('client_id', 'Unknown')[:20] + '...',
                    'project_id': client_info.get('project_id', 'Unknown'),
                    'auth_uri': client_info.get('auth_uri', 'Unknown')
                }
            except:
                return None
        return None
    
    def get_current_folder_info(self):
        """현재 설정된 폴더 정보 반환"""
        if self.root_folder_id:
            try:
                folder = self.service.files().get(fileId=self.root_folder_id).execute()
                return {
                    'id': self.root_folder_id,
                    'name': folder.get('name', 'Unknown'),
                    'path': self.folder_path or 'Custom Folder'
                }
            except:
                pass
        return None
    
    def setup_root_folder(self, custom_folder_path=None):
        """MyTalk 루트 폴더 생성 또는 찾기"""
        try:
            if custom_folder_path:
                self.folder_path = custom_folder_path
            
            # 사용자가 폴더 ID를 직접 제공한 경우
            if self.custom_folder_id:
                try:
                    folder = self.service.files().get(fileId=self.custom_folder_id).execute()
                    if folder.get('mimeType') == 'application/vnd.google-apps.folder':
                        self.root_folder_id = self.custom_folder_id
                        st.success(f"✅ 사용자 지정 폴더 연결: {folder.get('name')}")
                        self._ensure_subfolders()
                        return True
                    else:
                        st.error("⚠ 제공된 ID는 폴더가 아닙니다.")
                        return False
                except Exception as e:
                    st.error(f"⚠ 폴더에 접근할 수 없습니다: {str(e)}")
                    return False
            
            # 폴더 이름으로 검색 또는 생성
            folder_name = self.folder_path
            
            # 기존 폴더 검색
            results = self.service.files().list(
                q=f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false",
                fields="files(id, name)"
            ).execute()
            
            folders = results.get('files', [])
            
            if folders:
                # 기존 폴더 사용
                self.root_folder_id = folders[0]['id']
                st.success(f"✅ 기존 폴더 발견: {folder_name}")
            else:
                # 새 폴더 생성
                folder_metadata = {
                    'name': folder_name,
                    'mimeType': 'application/vnd.google-apps.folder'
                }
                
                folder = self.service.files().create(body=folder_metadata).execute()
                self.root_folder_id = folder.get('id')
                st.success(f"✅ 새 폴더 생성: {folder_name}")
            
            # 필수 하위 폴더들 확인 및 생성
            self._ensure_subfolders()
            return True
            
        except Exception as e:
            st.error(f"폴더 설정 실패: {str(e)}")
            return False
    
    def _ensure_subfolders(self):
        """필수 하위 폴더들 확인 및 생성"""
        subfolders = ['projects', 'index', 'temp']
        for subfolder in subfolders:
            self.create_subfolder(subfolder)
    
    def create_subfolder(self, folder_name):
        """하위 폴더 생성"""
        try:
            results = self.service.files().list(
                q=f"name='{folder_name}' and parents in '{self.root_folder_id}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
            ).execute()
            
            if not results.get('files', []):
                folder_metadata = {
                    'name': folder_name,
                    'mimeType': 'application/vnd.google-apps.folder',
                    'parents': [self.root_folder_id]
                }
                self.service.files().create(body=folder_metadata).execute()
                
        except Exception as e:
            st.warning(f"하위 폴더 {folder_name} 생성 실패: {str(e)}")
    
    def upload_file(self, local_path, drive_path, parent_folder_id=None):
        """파일을 Google Drive에 업로드"""
        try:
            if not parent_folder_id:
                parent_folder_id = self.root_folder_id
            
            if not parent_folder_id:
                raise Exception("업로드할 대상 폴더가 설정되지 않았습니다.")
            
            file_metadata = {
                'name': os.path.basename(drive_path),
                'parents': [parent_folder_id]
            }
            
            media = MediaFileUpload(local_path, resumable=True)
            
            existing_files = self.service.files().list(
                q=f"name='{os.path.basename(drive_path)}' and parents in '{parent_folder_id}' and trashed=false"
            ).execute().get('files', [])
            
            if existing_files:
                file_id = existing_files[0]['id']
                updated_file = self.service.files().update(
                    fileId=file_id,
                    body=file_metadata,
                    media_body=media
                ).execute()
                return updated_file.get('id')
            else:
                file = self.service.files().create(
                    body=file_metadata,
                    media_body=media
                ).execute()
                return file.get('id')
                
        except Exception as e:
            raise Exception(f"파일 업로드 실패: {str(e)}")
    
    def upload_text_content(self, content, filename, parent_folder_id=None):
        """텍스트 내용을 파일로 Google Drive에 업로드"""
        try:
            if not parent_folder_id:
                parent_folder_id = self.root_folder_id
            
            if not parent_folder_id:
                raise Exception("업로드할 대상 폴더가 설정되지 않았습니다.")
            
            file_content = io.BytesIO(content.encode('utf-8'))
            
            file_metadata = {
                'name': filename,
                'parents': [parent_folder_id]
            }
            
            media = MediaIoBaseUpload(
                file_content, 
                mimetype='text/plain',
                resumable=True
            )
            
            existing_files = self.service.files().list(
                q=f"name='{filename}' and parents in '{parent_folder_id}' and trashed=false"
            ).execute().get('files', [])
            
            if existing_files:
                file_id = existing_files[0]['id']
                updated_file = self.service.files().update(
                    fileId=file_id,
                    body=file_metadata,
                    media_body=media
                ).execute()
                return updated_file.get('id')
            else:
                file = self.service.files().create(
                    body=file_metadata,
                    media_body=media
                ).execute()
                return file.get('id')
                
        except Exception as e:
            raise Exception(f"텍스트 파일 업로드 실패: {str(e)}")
    
    def test_upload_permission(self):
        """업로드 권한 테스트"""
        try:
            if not self.root_folder_id:
                return False, "루트 폴더가 설정되지 않았습니다."
            
            test_content = f"MyTalk OAuth 2.0 Test - {datetime.now().isoformat()}"
            filename = f"test_permissions_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            
            file_id = self.upload_text_content(test_content, filename, self.root_folder_id)
            
            if file_id:
                self.delete_file(file_id)
                return True, "권한 테스트 성공"
            else:
                return False, "업로드 실패"
                
        except Exception as e:
            return False, str(e)
    
    def download_file(self, file_id, local_path):
        """Google Drive에서 파일 다운로드"""
        try:
            request = self.service.files().get_media(fileId=file_id)
            
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            
            with open(local_path, 'wb') as fh:
                downloader = MediaIoBaseDownload(fh, request)
                done = False
                while done is False:
                    status, done = downloader.next_chunk()
            
            return True
            
        except Exception as e:
            st.error(f"파일 다운로드 실패: {str(e)}")
            return False
    
    def list_files(self, folder_id=None, query=""):
        """폴더 내 파일 목록 조회"""
        try:
            if not folder_id:
                folder_id = self.root_folder_id
            
            base_query = f"parents in '{folder_id}' and trashed=false"
            if query:
                base_query += f" and {query}"
            
            results = self.service.files().list(
                q=base_query,
                fields="files(id, name, mimeType, modifiedTime, size)"
            ).execute()
            
            return results.get('files', [])
            
        except Exception as e:
            st.error(f"파일 목록 조회 실패: {str(e)}")
            return []
    
    def delete_file(self, file_id):
        """파일 삭제"""
        try:
            self.service.files().delete(fileId=file_id).execute()
            return True
        except Exception as e:
            st.error(f"파일 삭제 실패: {str(e)}")
            return False
    
    def get_folder_id(self, folder_name, parent_id=None):
        """폴더 ID 조회"""
        try:
            if not parent_id:
                parent_id = self.root_folder_id
            
            results = self.service.files().list(
                q=f"name='{folder_name}' and parents in '{parent_id}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
            ).execute()
            
            files = results.get('files', [])
            return files[0]['id'] if files else None
            
        except Exception as e:
            st.error(f"폴더 ID 조회 실패: {str(e)}")
            return None
    
    def create_project_folder(self, project_name):
        """프로젝트 폴더 생성"""
        try:
            projects_folder_id = self.get_folder_id('projects')
            if not projects_folder_id:
                return None
            
            folder_metadata = {
                'name': project_name,
                'mimeType': 'application/vnd.google-apps.folder',
                'parents': [projects_folder_id]
            }
            
            folder = self.service.files().create(body=folder_metadata).execute()
            project_folder_id = folder.get('id')
            
            audio_metadata = {
                'name': 'audio',
                'mimeType': 'application/vnd.google-apps.folder',
                'parents': [project_folder_id]
            }
            self.service.files().create(body=audio_metadata).execute()
            
            return project_folder_id
            
        except Exception as e:
            st.error(f"프로젝트 폴더 생성 실패: {str(e)}")
            return None
    
    def reset_authentication(self):
        """인증 토큰 삭제 및 재인증 강제"""
        try:
            if os.path.exists(self.token_file):
                os.remove(self.token_file)
                st.success(f"🗑️ 기존 토큰 파일 '{self.token_file}' 삭제됨")
            
            self.service = None
            self.credentials = None
            self.root_folder_id = None
            
            st.info("🔄 다음 실행 시 재인증이 필요합니다.")
            return True
        except Exception as e:
            st.error(f"토큰 삭제 실패: {str(e)}")
            return False


# =============================================================================
# 동기화 관리 클래스
# =============================================================================

class SyncManager:
    """로컬과 Google Drive 간 동기화 관리"""
    
    def __init__(self, local_storage, drive_manager):
        self.local_storage = local_storage
        self.drive_manager = drive_manager
        self.sync_queue = queue.Queue()
        self.is_syncing = False
        self.sync_status = "idle"
        self.last_sync_time = None
        self.sync_metadata_file = "sync_metadata.json"
        
    def calculate_file_hash(self, file_path):
        """파일 해시 계산"""
        try:
            hash_md5 = hashlib.md5()
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except:
            return None
    
    def load_sync_metadata(self):
        """동기화 메타데이터 로드"""
        try:
            if os.path.exists(self.sync_metadata_file):
                with open(self.sync_metadata_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return {}
        except:
            return {}
    
    def save_sync_metadata(self, metadata):
        """동기화 메타데이터 저장"""
        try:
            with open(self.sync_metadata_file, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2)
        except Exception as e:
            st.warning(f"동기화 메타데이터 저장 실패: {e}")
    
    def sync_project_to_drive(self, project_id, project_data):
        """프로젝트를 Google Drive에 동기화"""
        try:
            if not self.drive_manager.service:
                return False
            
            self.sync_status = "syncing"
            
            title = project_data.get('title', f'Script_{project_id}')
            safe_title = self.local_storage.sanitize_filename(title)
            project_folder_name = f"{project_id}_{safe_title}"
            
            drive_folder_id = self.drive_manager.create_project_folder(project_folder_name)
            if not drive_folder_id:
                self.sync_status = "error"
                return False
            
            local_project_path = None
            for file_path in project_data.get('saved_files', {}).values():
                if os.path.exists(file_path):
                    local_project_path = Path(file_path).parent
                    break
            
            if not local_project_path:
                self.sync_status = "error"
                return False
            
            uploaded_files = []
            
            # 메타데이터 파일 업로드
            metadata_file = local_project_path / "metadata.json"
            if metadata_file.exists():
                file_id = self.drive_manager.upload_file(
                    str(metadata_file), 
                    "metadata.json", 
                    drive_folder_id
                )
                if file_id:
                    uploaded_files.append(("metadata.json", file_id))
            
            # 스크립트 파일들 업로드
            for file_name in local_project_path.glob("*_script.txt"):
                file_id = self.drive_manager.upload_file(
                    str(file_name), 
                    file_name.name, 
                    drive_folder_id
                )
                if file_id:
                    uploaded_files.append((file_name.name, file_id))
            
            # 번역 파일 업로드
            for file_name in local_project_path.glob("*_translation.txt"):
                file_id = self.drive_manager.upload_file(
                    str(file_name), 
                    file_name.name, 
                    drive_folder_id
                )
                if file_id:
                    uploaded_files.append((file_name.name, file_id))
            
            # 오디오 파일들 업로드
            audio_folder = local_project_path / "audio"
            if audio_folder.exists():
                audio_folder_id = self.drive_manager.get_folder_id("audio", drive_folder_id)
                
                for audio_file in audio_folder.glob("*"):
                    if audio_file.is_file():
                        file_id = self.drive_manager.upload_file(
                            str(audio_file), 
                            audio_file.name, 
                            audio_folder_id
                        )
                        if file_id:
                            uploaded_files.append((f"audio/{audio_file.name}", file_id))
            
            # 동기화 메타데이터 업데이트
            sync_metadata = self.load_sync_metadata()
            sync_metadata[project_id] = {
                'drive_folder_id': drive_folder_id,
                'uploaded_files': uploaded_files,
                'last_sync': datetime.now().isoformat(),
                'local_hash': {}
            }
            
            # 파일 해시 저장
            for file_path in project_data.get('saved_files', {}).values():
                if os.path.exists(file_path):
                    file_hash = self.calculate_file_hash(file_path)
                    if file_hash:
                        relative_path = str(Path(file_path).relative_to(local_project_path))
                        sync_metadata[project_id]['local_hash'][relative_path] = file_hash
            
            self.save_sync_metadata(sync_metadata)
            self.sync_status = "completed"
            self.last_sync_time = datetime.now()
            
            return True
            
        except Exception as e:
            st.error(f"Google Drive 동기화 실패: {str(e)}")
            self.sync_status = "error"
            return False
    
    def sync_from_drive(self, project_id):
        """Google Drive에서 프로젝트 다운로드"""
        try:
            if not self.drive_manager.service:
                return False
            
            sync_metadata = self.load_sync_metadata()
            project_sync_data = sync_metadata.get(project_id)
            
            if not project_sync_data or 'drive_folder_id' not in project_sync_data:
                return False
            
            drive_folder_id = project_sync_data['drive_folder_id']
            
            local_base_path = self.local_storage.scripts_dir / project_id
            local_base_path.mkdir(exist_ok=True)
            
            audio_path = local_base_path / "audio"
            audio_path.mkdir(exist_ok=True)
            
            drive_files = self.drive_manager.list_files(drive_folder_id)
            
            downloaded_files = {}
            
            for drive_file in drive_files:
                file_name = drive_file['name']
                file_id = drive_file['id']
                
                if drive_file['mimeType'] == 'application/vnd.google-apps.folder':
                    continue
                
                local_file_path = local_base_path / file_name
                
                if self.drive_manager.download_file(file_id, str(local_file_path)):
                    downloaded_files[file_name] = str(local_file_path)
            
            # 오디오 폴더 파일들
            audio_folder_id = self.drive_manager.get_folder_id("audio", drive_folder_id)
            if audio_folder_id:
                audio_files = self.drive_manager.list_files(audio_folder_id)
                
                for audio_file in audio_files:
                    file_name = audio_file['name']
                    file_id = audio_file['id']
                    
                    local_audio_path = audio_path / file_name
                    
                    if self.drive_manager.download_file(file_id, str(local_audio_path)):
                        downloaded_files[f"audio/{file_name}"] = str(local_audio_path)
            
            return downloaded_files
            
        except Exception as e:
            st.error(f"Google Drive에서 다운로드 실패: {str(e)}")
            return {}
    
    def auto_sync_project(self, project_id, project_data):
        """프로젝트 자동 동기화 (동기식으로 변경)"""
        try:
            return self.sync_project_to_drive(project_id, project_data)
        except Exception as e:
            print(f"자동 동기화 실패: {str(e)}")
            return False


# =============================================================================
# 하이브리드 저장소 클래스
# =============================================================================

class HybridStorage:
    """로컬과 Google Drive 이중 저장소 (OAuth 2.0 버전)"""
    
    def __init__(self):
        self.local_storage = FileBasedStorage()
        self.drive_manager = GoogleDriveManagerOAuth() if GOOGLE_DRIVE_AVAILABLE else None
        self.sync_manager = None
        self.drive_enabled = False
        
        if self.drive_manager:
            self.sync_manager = SyncManager(self.local_storage, self.drive_manager)
    
    def enable_drive_sync(self, credentials_json=None, force_reauth=False):
        """Google Drive 동기화 활성화 (OAuth 2.0 방식)"""
        if not self.drive_manager:
            return False
        
        result = self.drive_manager.authenticate(credentials_json, force_reauth)
        if result == True:
            self.drive_enabled = True
            return True
        
        return False
    
    def disconnect_drive(self):
        """Google Drive 연결 해제"""
        try:
            if self.drive_manager:
                success = self.drive_manager.reset_authentication()
                if success:
                    self.drive_enabled = False
                    return True
            return False
        except Exception as e:
            st.error(f"연결 해제 실패: {str(e)}")
            return False
    
    def save_project(self, results, input_content, input_method, category, auto_sync=True):
        """프로젝트 저장 (로컬 + 선택적 Drive 동기화)"""
        try:
            project_id, project_path = self.local_storage.save_project_to_files(
                results, input_content, input_method, category
            )
            
            if not project_id:
                return None, None
            
            if self.drive_enabled and auto_sync and self.sync_manager:
                project_data = {
                    'title': results.get('title', f'Script_{project_id}'),
                    'category': category,
                    'saved_files': self._get_project_files(project_path),
                    'created_at': datetime.now().isoformat()
                }
                
                # 동기식으로 변경하여 오류 방지
                try:
                    st.info("🔄 Google Drive 동기화 중...")
                    sync_success = self.sync_manager.auto_sync_project(project_id, project_data)
                    if sync_success:
                        st.success("✅ Google Drive 동기화 완료!")
                    else:
                        st.warning("⚠️ Google Drive 동기화 실패 (로컬 저장은 완료)")
                except Exception as sync_error:
                    st.warning(f"⚠️ Google Drive 동기화 오류: {str(sync_error)} (로컬 저장은 완료)")
            
            return project_id, project_path
            
        except Exception as e:
            st.error(f"프로젝트 저장 실패: {str(e)}")
            return None, None
    
    def _get_project_files(self, project_path):
        """프로젝트 폴더의 파일 목록 조회"""
        files = {}
        project_dir = Path(project_path)
        
        if project_dir.exists():
            for file_path in project_dir.rglob("*"):
                if file_path.is_file():
                    relative_path = file_path.relative_to(project_dir)
                    files[str(relative_path)] = str(file_path)
        
        return files
    
    def load_all_projects(self):
        """모든 프로젝트 로드 (로컬 우선)"""
        return self.local_storage.load_all_projects()
    
    def load_project_content(self, project_id):
        """프로젝트 내용 로드"""
        content = self.local_storage.load_project_content(project_id)
        
        if not content and self.drive_enabled and self.sync_manager:
            downloaded_files = self.sync_manager.sync_from_drive(project_id)
            if downloaded_files:
                content = self.local_storage.load_project_content(project_id)
        
        return content
    
    def manual_sync_project(self, project_id):
        """프로젝트 수동 동기화"""
        if not self.drive_enabled or not self.sync_manager:
            return False
        
        projects = self.load_all_projects()
        target_project = None
        
        for project in projects:
            if project['project_id'] == project_id:
                target_project = project
                break
        
        if target_project:
            return self.sync_manager.sync_project_to_drive(project_id, target_project)
        
        return False
    
    def get_sync_status(self):
        """동기화 상태 조회"""
        if not self.sync_manager:
            return {"status": "disabled", "message": "Google Drive 동기화가 비활성화됨"}
        
        return {
            "status": self.sync_manager.sync_status,
            "last_sync": self.sync_manager.last_sync_time.isoformat() if self.sync_manager.last_sync_time else None,
            "drive_enabled": self.drive_enabled
        }


# =============================================================================
# 파일 기반 저장소 클래스
# =============================================================================

class FileBasedStorage:
    """기존 파일 기반 저장소"""
    
    def __init__(self, base_dir="mytalk_data"):
        self.base_dir = Path(base_dir)
        self.scripts_dir = self.base_dir / "scripts"
        self.audio_dir = self.base_dir / "audio"
        self.metadata_dir = self.base_dir / "metadata"
        
        self.scripts_dir.mkdir(parents=True, exist_ok=True)
        self.audio_dir.mkdir(parents=True, exist_ok=True)
        self.metadata_dir.mkdir(parents=True, exist_ok=True)
    
    def save_project_to_files(self, results, input_content, input_method, category):
        """프로젝트를 파일로 저장"""
        try:
            project_id = datetime.now().strftime("%Y%m%d_%H%M%S")
            title = results.get('title', f'Script_{project_id}')
            
            safe_title = self.sanitize_filename(title)
            project_folder = self.scripts_dir / f"{project_id}_{safe_title}"
            project_folder.mkdir(exist_ok=True)
            
            audio_folder = project_folder / "audio"
            audio_folder.mkdir(exist_ok=True)
            
            saved_files = {}
            
            metadata = {
                'project_id': project_id,
                'title': title,
                'category': category,
                'input_method': input_method,
                'input_content': input_content,
                'created_at': datetime.now().isoformat(),
                'versions': []
            }
            
            # 원본 스크립트 저장
            if 'original_script' in results:
                original_file = project_folder / "original_script.txt"
                with open(original_file, 'w', encoding='utf-8') as f:
                    f.write(results['original_script'])
                saved_files['original_script'] = str(original_file)
                metadata['versions'].append('original')
                st.write(f"✅ 원본 스크립트 저장: {original_file.name}")
            
            # 한국어 번역 저장
            if 'korean_translation' in results:
                translation_file = project_folder / "korean_translation.txt"
                with open(translation_file, 'w', encoding='utf-8') as f:
                    f.write(results['korean_translation'])
                saved_files['korean_translation'] = str(translation_file)
                st.write(f"✅ 한국어 번역 저장: {translation_file.name}")
            
            # 각 버전별 스크립트 및 오디오 저장
            versions = ['ted', 'podcast', 'daily']
            
            for version in versions:
                script_key = f"{version}_script"
                audio_key = f"{version}_audio"
                
                if script_key in results and results[script_key]:
                    script_file = project_folder / f"{version}_script.txt"
                    with open(script_file, 'w', encoding='utf-8') as f:
                        f.write(results[script_key])
                    saved_files[script_key] = str(script_file)
                    metadata['versions'].append(version)
                    st.write(f"✅ {version.upper()} 스크립트 저장: {script_file.name}")
                
                if audio_key in results and results[audio_key]:
                    audio_src = results[audio_key]
                    if os.path.exists(audio_src):
                        audio_ext = Path(audio_src).suffix or '.mp3'
                        audio_dest = audio_folder / f"{version}_audio{audio_ext}"
                        shutil.copy2(audio_src, audio_dest)
                        saved_files[audio_key] = str(audio_dest)
                        st.write(f"✅ {version.upper()} 오디오 저장: {audio_dest.name}")
            
            # 원본 오디오 저장
            if 'original_audio' in results and results['original_audio']:
                audio_src = results['original_audio']
                if os.path.exists(audio_src):
                    audio_ext = Path(audio_src).suffix or '.mp3'
                    audio_dest = audio_folder / f"original_audio{audio_ext}"
                    shutil.copy2(audio_src, audio_dest)
                    saved_files['original_audio'] = str(audio_dest)
                    st.write(f"✅ 원본 오디오 저장: {audio_dest.name}")
            
            # 메타데이터 최종 저장
            metadata['saved_files'] = saved_files
            metadata_file = project_folder / "metadata.json"
            with open(metadata_file, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2)
            
            # 프로젝트 인덱스 업데이트
            self.update_project_index(project_id, title, category, str(project_folder))
            
            st.success(f"🎉 파일 저장 완료! 프로젝트 폴더: {project_folder.name}")
            st.success(f"📊 저장된 파일: {len(saved_files)}개")
            
            return project_id, str(project_folder)
            
        except Exception as e:
            st.error(f"⛔ 파일 저장 실패: {str(e)}")
            return None, None
    
    def sanitize_filename(self, filename):
        """안전한 파일명 생성"""
        safe_chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_() "
        safe_filename = ''.join(c for c in filename if c in safe_chars)
        safe_filename = ' '.join(safe_filename.split())[:50]
        return safe_filename.strip() or "Untitled"
    
    def update_project_index(self, project_id, title, category, project_path):
        """프로젝트 인덱스 업데이트"""
        try:
            index_file = self.base_dir / "project_index.json"
            
            if index_file.exists():
                with open(index_file, 'r', encoding='utf-8') as f:
                    index_data = json.load(f)
            else:
                index_data = {"projects": []}
            
            new_project = {
                'project_id': project_id,
                'title': title,
                'category': category,
                'project_path': project_path,
                'created_at': datetime.now().isoformat()
            }
            
            index_data["projects"].append(new_project)
            index_data["projects"].sort(key=lambda x: x['created_at'], reverse=True)
            
            with open(index_file, 'w', encoding='utf-8') as f:
                json.dump(index_data, f, ensure_ascii=False, indent=2)
            
            return True
            
        except Exception as e:
            st.error(f"인덱스 업데이트 실패: {str(e)}")
            return False
    
    def load_all_projects(self):
        """모든 프로젝트 로드"""
        try:
            index_file = self.base_dir / "project_index.json"
            
            if not index_file.exists():
                return []
            
            with open(index_file, 'r', encoding='utf-8') as f:
                index_data = json.load(f)
            
            projects = []
            for project_info in index_data.get("projects", []):
                project_path = Path(project_info['project_path'])
                
                if project_path.exists():
                    metadata_file = project_path / "metadata.json"
                    if metadata_file.exists():
                        with open(metadata_file, 'r', encoding='utf-8') as f:
                            metadata = json.load(f)
                        projects.append(metadata)
            
            return projects
            
        except Exception as e:
            st.error(f"프로젝트 로드 실패: {str(e)}")
            return []
    
    def load_project_content(self, project_id):
        """특정 프로젝트의 모든 내용 로드"""
        try:
            projects = self.load_all_projects()
            target_project = None
            
            for project in projects:
                if project['project_id'] == project_id:
                    target_project = project
                    break
            
            if not target_project:
                return None
            
            project_path = Path(list(target_project['saved_files'].values())[0]).parent
            content = {}
            
            for file_type, file_path in target_project['saved_files'].items():
                if 'script' in file_type or 'translation' in file_type:
                    if os.path.exists(file_path):
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content[file_type] = f.read()
                elif 'audio' in file_type:
                    if os.path.exists(file_path):
                        content[file_type] = file_path
            
            content['metadata'] = target_project
            
            return content
            
        except Exception as e:
            st.error(f"프로젝트 내용 로드 실패: {str(e)}")
            return None
    
    def delete_project(self, project_id):
        """프로젝트 완전 삭제"""
        try:
            projects = self.load_all_projects()
            target_project = None
            
            for project in projects:
                if project['project_id'] == project_id:
                    target_project = project
                    break
            
            if target_project:
                project_path = Path(list(target_project['saved_files'].values())[0]).parent
                if project_path.exists():
                    shutil.rmtree(project_path)
                
                index_file = self.base_dir / "project_index.json"
                if index_file.exists():
                    with open(index_file, 'r', encoding='utf-8') as f:
                        index_data = json.load(f)
                    
                    index_data["projects"] = [p for p in index_data["projects"] if p['project_id'] != project_id]
                    
                    with open(index_file, 'w', encoding='utf-8') as f:
                        json.dump(index_data, f, ensure_ascii=False, indent=2)
                
                return True
            
            return False
            
        except Exception as e:
            st.error(f"프로젝트 삭제 실패: {str(e)}")
            return False


# =============================================================================
# 데이터베이스 클래스
# =============================================================================

class FixedDatabase:
    def __init__(self, db_path='mytalk.db'):
        self.db_path = db_path
        self.init_db()
    
    def init_db(self):
        """데이터베이스 초기화"""
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            
            c.execute('''
                CREATE TABLE IF NOT EXISTS scripts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    original_content TEXT NOT NULL,
                    korean_translation TEXT DEFAULT '',
                    category TEXT DEFAULT 'general',
                    input_type TEXT DEFAULT 'text',
                    input_data TEXT DEFAULT '',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            c.execute('''
                CREATE TABLE IF NOT EXISTS practice_versions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    script_id INTEGER NOT NULL,
                    version_type TEXT NOT NULL,
                    content TEXT NOT NULL,
                    audio_path TEXT DEFAULT '',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (script_id) REFERENCES scripts (id) ON DELETE CASCADE
                )
            ''')
            
            conn.commit()
            conn.close()
            return True
            
        except Exception as e:
            st.error(f"데이터베이스 초기화 실패: {e}")
            return False
    
    def create_script_project(self, title, original_content, korean_translation='', 
                            category='general', input_type='text', input_data=''):
        """스크립트 프로젝트 생성"""
        try:
            title = title.strip() if title else f"Script_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            original_content = original_content.strip()
            
            if not original_content:
                raise ValueError("스크립트 내용이 비어있습니다")
            
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            
            c.execute('''
                INSERT INTO scripts (title, original_content, korean_translation, category, input_type, input_data)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (title, original_content, korean_translation, category, input_type, input_data))
            
            script_id = c.lastrowid
            conn.commit()
            
            c.execute('SELECT COUNT(*) FROM scripts WHERE id = ?', (script_id,))
            if c.fetchone()[0] == 1:
                conn.close()
                return script_id
            else:
                conn.rollback()
                conn.close()
                raise Exception(f"저장 후 확인 실패")
                
        except Exception as e:
            if 'conn' in locals():
                try:
                    conn.rollback()
                    conn.close()
                except:
                    pass
            raise Exception(f"스크립트 저장 실패: {str(e)}")
    
    def add_practice_version(self, script_id, version_type, content, audio_path=''):
        """연습 버전 추가"""
        try:
            if not content.strip():
                raise ValueError(f"{version_type} 내용이 비어있습니다")
            
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            
            c.execute('''
                INSERT INTO practice_versions (script_id, version_type, content, audio_path)
                VALUES (?, ?, ?, ?)
            ''', (script_id, version_type, content.strip(), audio_path or ''))
            
            version_id = c.lastrowid
            conn.commit()
            conn.close()
            
            return version_id
            
        except Exception as e:
            if 'conn' in locals():
                try:
                    conn.rollback()
                    conn.close()
                except:
                    pass
            raise Exception(f"{version_type} 버전 저장 실패: {str(e)}")
    
    def get_all_scripts(self):
        """모든 스크립트 목록 조회"""
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            c.execute('SELECT * FROM scripts ORDER BY created_at DESC')
            scripts = c.fetchall()
            conn.close()
            return scripts
        except Exception as e:
            st.error(f"스크립트 조회 오류: {e}")
            return []
    
    def get_script_project(self, script_id):
        """스크립트 프로젝트 전체 정보 조회"""
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            
            c.execute('SELECT * FROM scripts WHERE id = ?', (script_id,))
            script = c.fetchone()
            
            c.execute('SELECT * FROM practice_versions WHERE script_id = ?', (script_id,))
            versions = c.fetchall()
            
            conn.close()
            
            return {
                'script': script,
                'versions': versions,
                'files': []
            }
        except Exception as e:
            st.error(f"프로젝트 조회 오류: {e}")
            return {'script': None, 'versions': [], 'files': []}
    
    def search_scripts(self, query):
        """스크립트 검색"""
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            c.execute('''
                SELECT * FROM scripts 
                WHERE title LIKE ? OR original_content LIKE ? 
                ORDER BY created_at DESC
            ''', (f'%{query}%', f'%{query}%'))
            scripts = c.fetchall()
            conn.close()
            return scripts
        except Exception as e:
            st.error(f"검색 오류: {e}")
            return []
    
    def delete_script_project(self, script_id):
        """스크립트 프로젝트 전체 삭제"""
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            c.execute('DELETE FROM practice_versions WHERE script_id = ?', (script_id,))
            c.execute('DELETE FROM scripts WHERE id = ?', (script_id,))
            conn.commit()
            conn.close()
        except Exception as e:
            st.error(f"삭제 오류: {e}")


# =============================================================================
# LLM Provider 클래스
# =============================================================================

class SimpleLLMProvider:
    def __init__(self, provider, api_key, model):
        self.provider = provider
        self.api_key = api_key
        self.model = model
        self.client = None
        self.setup_client()
    
    def setup_client(self):
        """클라이언트 초기화"""
        try:
            if self.provider == 'OpenAI' and openai:
                openai.api_key = self.api_key
                self.client = openai
            elif self.provider == 'Anthropic' and Anthropic:
                self.client = Anthropic(api_key=self.api_key)
            elif self.provider == 'Google' and genai:
                genai.configure(api_key=self.api_key)
                self.client = genai
        except Exception as e:
            st.error(f"LLM 클라이언트 초기화 실패: {str(e)}")
    
    def generate_content(self, prompt):
        """간단한 콘텐츠 생성"""
        try:
            if not self.client:
                return None
            
            if self.provider == 'OpenAI':
                response = self.client.ChatCompletion.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=1000,
                    temperature=0.7
                )
                return response.choices[0].message.content
            
            elif self.provider == 'Anthropic':
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=1000,
                    messages=[{"role": "user", "content": prompt}]
                )
                return response.content[0].text
            
            elif self.provider == 'Google':
                model = genai.GenerativeModel(self.model)
                response = model.generate_content(prompt)
                return response.text
        
        except Exception as e:
            st.error(f"LLM 호출 실패: {str(e)}")
            return None


# =============================================================================
# 유틸리티 함수들
# =============================================================================

def get_browser_tts_script(text, lang='en-US'):
    """브라우저 TTS 스크립트 생성"""
    clean_text = text.replace("'", "\\'").replace('"', '\\"').replace('\n', '\\n')
    button_id = f"btn_{hash(text) % 10000}"
    
    return f"""
    <div style="margin: 10px 0; padding: 10px; background-color: #f8f9fa; border-radius: 8px;">
        <button 
            id="{button_id}" 
            onclick="
                if ('speechSynthesis' in window) {{
                    window.speechSynthesis.cancel();
                    const utterance = new SpeechSynthesisUtterance('{clean_text}');
                    utterance.lang = '{lang}';
                    utterance.rate = 1.0;
                    window.speechSynthesis.speak(utterance);
                }} else {{
                    alert('브라우저가 음성 합성을 지원하지 않습니다.');
                }}
            " 
            style="
                background: linear-gradient(45deg, #FF6B6B, #4ECDC4);
                color: white;
                border: none;
                padding: 10px 15px;
                border-radius: 20px;
                cursor: pointer;
                font-size: 14px;
            "
        >
            🔊 브라우저 TTS 재생
        </button>
    </div>
    """


def init_session_state():
    """세션 상태 초기화"""
    defaults = {
        'api_provider': 'OpenAI',
        'api_key': '',
        'model': 'gpt-4o-mini',
        'current_project': None,
        'generation_progress': {},
        'tts_engine': 'auto',
        'tts_voice': 'en-us',
        'tts_speaking_rate': 1.0,
        'tts_pitch': 0.0,
        'google_drive_enabled': False,
        'google_credentials': None,
        'file_projects': [],
        'script_results': None,
        'show_results': False,
        'selected_versions': None,
        'input_content': '',
        'input_method': 'text',
        'category': '일반',
        'drive_oauth_info': None,
        'sync_status': {},
    }
    
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def save_to_temp_backup_fixed(results, input_content, input_method, category):
    """수정된 임시 백업 저장"""
    try:
        backup_id = str(uuid.uuid4())[:8]
        backup_data = {
            'backup_id': backup_id,
            'timestamp': datetime.now().isoformat(),
            'title': results.get('title', 'Untitled'),
            'results': results,
            'input_content': input_content,
            'input_method': input_method,
            'category': category
        }
        
        temp_backup_dir = Path("temp_backups")
        temp_backup_dir.mkdir(exist_ok=True)
        
        json_path = temp_backup_dir / f"backup_{backup_id}.json"
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(backup_data, f, ensure_ascii=False, indent=2)
        
        return backup_id
        
    except Exception as e:
        st.error(f"임시 백업 저장 실패: {e}")
        return None


def load_temp_backup_fixed(backup_id):
    """수정된 임시 백업 로드"""
    try:
        json_path = Path(f"temp_backups/backup_{backup_id}.json")
        
        if json_path.exists():
            with open(json_path, 'r', encoding='utf-8') as f:
                backup_data = json.load(f)
                if 'results' in backup_data and backup_data['results']:
                    return backup_data
        
        return None
        
    except Exception as e:
        st.error(f"임시 백업 로드 실패: {e}")
        return None


def get_recent_backups_fixed(limit=5):
    """수정된 최근 백업 목록"""
    backup_dir = Path("temp_backups")
    if not backup_dir.exists():
        return []
    
    backups = []
    for file_path in backup_dir.glob("backup_*.json"):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                backups.append({
                    'id': data.get('backup_id'),
                    'timestamp': data.get('timestamp'),
                    'title': data.get('title', 'Unknown'),
                    'category': data.get('category', ''),
                    'input_method': data.get('input_method', '')
                })
        except:
            continue
    
    backups.sort(key=lambda x: x['timestamp'], reverse=True)
    return backups[:limit]


def save_to_files_and_db(results, input_content, input_method, category):
    """하이브리드 저장소에 저장 (동기화 오류 처리 개선)"""
    try:
        st.write("📁 통합 저장 시작...")
        
        storage = st.session_state.get('storage')
        if not storage:
            storage = HybridStorage()
            st.session_state.storage = storage
        
        # 프로젝트 저장 (동기화 포함)
        project_id, project_path = storage.save_project(
            results, input_content, input_method, category
        )
        
        if not project_id:
            raise Exception("프로젝트 저장 실패")
        
        st.write(f"✅ 프로젝트 저장 완료: {os.path.basename(project_path)}")
        
        # 기존 DB 저장도 유지 (호환성을 위해)
        try:
            db = FixedDatabase()
            
            title = results.get('title', f'Script_{project_id}')
            original_script = results.get('original_script', '')
            korean_translation = results.get('korean_translation', '')
            
            script_id = db.create_script_project(
                title=title,
                original_content=original_script,
                korean_translation=korean_translation,
                category=category,
                input_type=input_method.lower(),
                input_data=f"hybrid_project_id:{project_id}"
            )
            
            for version_type in ['ted', 'podcast', 'daily']:
                script_key = f"{version_type}_script"
                if script_key in results and results[script_key]:
                    db.add_practice_version(
                        script_id=script_id,
                        version_type=version_type,
                        content=results[script_key],
                        audio_path=f"hybrid_project_id:{project_id}"
                    )
            
            st.write(f"✅ 데이터베이스 저장 완료 (ID: {script_id})")
            
        except Exception as db_error:
            st.warning(f"⚠️ 데이터베이스 저장 실패: {db_error}")
            st.info("파일 저장은 성공했으므로 데이터는 보존됩니다.")
        
        # 세션 상태 업데이트
        st.session_state.last_save_time = datetime.now().isoformat()
        st.session_state.last_project_id = project_id
        st.session_state.file_projects = storage.load_all_projects()
        
        return True
        
    except Exception as e:
        st.error(f"⛔ 통합 저장 실패: {str(e)}")
        return False


def display_results_fixed(results, selected_versions):
    """수정된 결과 표시 함수"""
    if not results:
        return
        
    st.markdown("---")
    st.markdown("## 📋 생성 결과")
    
    version_names = {
        'original': '원본 스크립트',
        'ted': 'TED 3분 말하기', 
        'podcast': '팟캐스트 대화',
        'daily': '일상 대화'
    }
    
    tab_names = [version_names[v] for v in selected_versions if v in version_names]
    if not tab_names:
        return
        
    tabs = st.tabs(tab_names)
    
    for i, version in enumerate(selected_versions):
        if version not in version_names:
            continue
            
        with tabs[i]:
            script_key = f"{version}_script" if version != 'original' else 'original_script'
            audio_key = f"{version}_audio" if version != 'original' else 'original_audio'
            
            if script_key in results:
                st.markdown("### 🇺🇸 English Script")
                st.markdown(f'''
                <div style="
                    background: linear-gradient(135deg, #f0f2f6, #e8eaf0);
                    padding: 1.5rem;
                    border-radius: 15px;
                    margin: 1rem 0;
                    box-shadow: 0 4px 6px rgba(0,0,0,0.1);
                ">
                    <div style="
                        font-size: 1.1rem;
                        line-height: 1.8;
                        color: #1f1f1f;
                        font-family: 'Georgia', serif;
                    ">{results[script_key]}</div>
                </div>
                ''', unsafe_allow_html=True)
                
                if audio_key in results and results[audio_key]:
                    audio_path = results[audio_key]
                    if os.path.exists(audio_path):
                        st.audio(audio_path, format='audio/mp3')
                    else:
                        st.warning("오디오 파일을 찾을 수 없습니다.")
                        st.markdown(get_browser_tts_script(results[script_key]), unsafe_allow_html=True)
                else:
                    st.markdown(get_browser_tts_script(results[script_key]), unsafe_allow_html=True)
                
                if version == 'original' and 'korean_translation' in results:
                    st.markdown("### 🇰🇷 한국어 번역")
                    st.markdown(f'''
                    <div style="
                        background: linear-gradient(135deg, #f0f2f6, #e8eaf0);
                        padding: 1rem;
                        border-radius: 10px;
                        margin: 1rem 0;
                    ">
                        <div style="
                            font-size: 0.95rem;
                            color: #666;
                            font-style: italic;
                            line-height: 1.6;
                        ">{results["korean_translation"]}</div>
                    </div>
                    ''', unsafe_allow_html=True)


# =============================================================================
# 페이지 함수들
# =============================================================================

def script_creation_page():
    """스크립트 생성 페이지"""
    st.header("✏️ 스크립트 작성")
    
    if st.session_state.show_results and st.session_state.script_results:
        st.success("🎉 생성된 스크립트가 있습니다!")
        
        col1, col2, col3 = st.columns([1, 1, 1])
        
        with col1:
            if st.button("💾 로컬 저장", type="primary", key="save_existing_results"):
                success = save_to_files_and_db(
                    st.session_state.script_results, 
                    st.session_state.input_content, 
                    st.session_state.input_method, 
                    st.session_state.category
                )
                if success:
                    st.balloons()
                    st.success("저장 완료! 연습하기 탭에서 확인하세요.")
                    st.session_state.show_results = False
                    st.session_state.script_results = None
                    time.sleep(2)
                    st.rerun()
        
        with col2:
            if st.button("🔄 새로 만들기", key="create_new_script"):
                st.session_state.show_results = False
                st.session_state.script_results = None
                st.rerun()
        
        with col3:
            if st.button("🔥 백업에서 복원", key="restore_backup"):
                backups = get_recent_backups_fixed(5)
                if backups:
                    st.session_state.show_backup_restore = True
                else:
                    st.info("복원 가능한 백업이 없습니다.")
        
        display_results_fixed(st.session_state.script_results, st.session_state.selected_versions)
        
        if st.session_state.get('show_backup_restore', False):
            st.markdown("---")
            st.markdown("### 🔥 백업에서 복원")
            
            backups = get_recent_backups_fixed(5)
            if backups:
                backup_options = {}
                for backup in backups:
                    display_name = f"{backup['title']} ({backup['category']}) - {backup['timestamp'][:16]}"
                    backup_options[display_name] = backup['id']
                
                selected_backup = st.selectbox("복원할 백업 선택", list(backup_options.keys()))
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("복원하기"):
                        backup_id = backup_options[selected_backup]
                        backup_data = load_temp_backup_fixed(backup_id)
                        
                        if backup_data:
                            st.session_state.script_results = backup_data['results']
                            st.session_state.input_content = backup_data['input_content']
                            st.session_state.input_method = backup_data['input_method']
                            st.session_state.category = backup_data['category']
                            st.session_state.show_results = True
                            st.session_state.show_backup_restore = False
                            st.success("백업 복원 완료!")
                            st.rerun()
                        else:
                            st.error("백업 복원 실패")
                
                with col2:
                    if st.button("취소"):
                        st.session_state.show_backup_restore = False
                        st.rerun()
        
        return
    
    st.markdown("### 📝 새 스크립트 만들기")
    
    col1, col2 = st.columns(2)
    
    with col1:
        category = st.selectbox(
            "카테고리 선택",
            ["일반", "비즈니스", "여행", "교육", "건강", "기술", "문화", "스포츠"],
            help="스크립트의 주제를 선택하세요"
        )
    
    with col2:
        version_options = {
            '원본 스크립트': 'original',
            'TED 3분 말하기': 'ted',
            '팟캐스트 대화': 'podcast',
            '일상 대화': 'daily'
        }
        
        selected_version_names = st.multiselect(
            "생성할 버전 선택",
            list(version_options.keys()),
            default=['원본 스크립트', 'TED 3분 말하기', '팟캐스트 대화', '일상 대화'],
            help="생성하고 싶은 스크립트 버전들을 선택하세요"
        )
        
        selected_versions = [version_options[name] for name in selected_version_names]
    
    input_method = st.radio(
        "입력 방법 선택",
        ["텍스트", "이미지", "파일"],
        horizontal=True
    )
    
    input_content = ""
    
    if input_method == "텍스트":
        input_content = st.text_area(
            "주제 또는 내용 입력",
            height=100,
            placeholder="예: 환경 보호의 중요성에 대해 설명하는 스크립트를 만들어주세요."
        )
    
    elif input_method == "이미지":
        uploaded_image = st.file_uploader(
            "이미지 업로드",
            type=['png', 'jpg', 'jpeg'],
            help="이미지를 기반으로 영어 스크립트를 생성합니다"
        )
        if uploaded_image:
            image = Image.open(uploaded_image)
            st.image(image, caption="업로드된 이미지", use_column_width=True)
            input_content = "이 이미지를 설명하고 관련된 영어 학습 스크립트를 만들어주세요."
    
    else:
        uploaded_file = st.file_uploader(
            "텍스트 파일 업로드",
            type=['txt', 'md'],
            help="텍스트 파일의 내용을 기반으로 스크립트를 생성합니다"
        )
        if uploaded_file:
            input_content = uploaded_file.read().decode('utf-8')
            st.text_area("파일 내용 미리보기", input_content[:500] + "...", height=100, disabled=True)
    
    if st.button("🚀 스크립트 생성하기", type="primary"):
        if not st.session_state.api_key:
            st.error("먼저 설정에서 API Key를 입력해주세요!")
            return
        
        if not input_content:
            st.error("내용을 입력해주세요!")
            return
        
        if not selected_versions:
            st.error("생성할 버전을 선택해주세요!")
            return
        
        st.session_state.input_content = input_content
        st.session_state.input_method = input_method
        st.session_state.category = category
        st.session_state.selected_versions = selected_versions
        
        progress_container = st.empty()
        
        with progress_container.container():
            st.markdown("### 📊 생성 진행상황")
            
            llm_provider = SimpleLLMProvider(
                st.session_state.api_provider,
                st.session_state.api_key,
                st.session_state.model
            )
            
            results = {}
            
            st.write("1️⃣ 영어 스크립트 생성 중...")
            
            original_prompt = f"""
            Create a natural, engaging English script based on the following input.
            
            Input Type: {input_method.lower()}
            Category: {category}
            Content: {input_content}
            
            Requirements:
            1. Create natural, conversational English suitable for speaking practice
            2. Length: 200-300 words
            3. Include engaging expressions and vocabulary
            4. Make it suitable for intermediate English learners
            5. Structure with clear introduction, main content, and conclusion
            
            Format your response as:
            TITLE: [Create a clear, descriptive title]
            
            SCRIPT:
            [Your natural English script here]
            """
            
            original_response = llm_provider.generate_content(original_prompt)
            
            if original_response:
                title = "Generated Script"
                script_content = original_response
                
                lines = original_response.split('\n')
                for line in lines:
                    if line.startswith('TITLE:'):
                        title = line.replace('TITLE:', '').strip()
                        break
                
                script_start = original_response.find('SCRIPT:')
                if script_start != -1:
                    script_content = original_response[script_start+7:].strip()
                
                results['title'] = title
                results['original_script'] = script_content
                st.write("✅ 영어 스크립트 생성 완료")
                
                st.write("2️⃣ 한국어 번역 생성 중...")
                translation_prompt = f"""
                Translate the following English text to natural, fluent Korean.
                Focus on meaning rather than literal translation.
                
                English Text:
                {script_content}
                
                Provide only the Korean translation:
                """
                
                translation = llm_provider.generate_content(translation_prompt)
                results['korean_translation'] = translation or "번역 생성 실패"
                st.write("✅ 한국어 번역 완료")
                
                st.write("3️⃣ 원본 음성 생성 중...")
                tts_kwargs = {
                    'speaking_rate': st.session_state.get('tts_speaking_rate', 1.0),
                    'pitch': st.session_state.get('tts_pitch', 0.0)
                }
                original_audio = generate_audio_with_fallback(
                    script_content, 
                    st.session_state.tts_engine, 
                    st.session_state.tts_voice,
                    **tts_kwargs
                )
                results['original_audio'] = original_audio
                st.write("✅ 원본 음성 생성 완료" if original_audio else "⚠️ 원본 음성 생성 실패")
                
                version_prompts = {
                    'ted': f"""
                    Transform the following script into a TED-style 3-minute presentation format.
                    
                    Original Script:
                    {script_content}
                    
                    Requirements:
                    1. Add a powerful hook opening
                    2. Include personal stories or examples
                    3. Create 2-3 main points with clear transitions
                    4. End with an inspiring call to action
                    5. Use TED-style language and pacing
                    6. Keep it around 400-450 words (3 minutes speaking)
                    """,
                    
                    'podcast': f"""
                    Transform the following script into a natural 2-person podcast dialogue.
                    
                    Original Script:
                    {script_content}
                    
                    Requirements:
                    1. Create natural conversation between Host and Guest
                    2. Include follow-up questions and responses
                    3. Add conversational fillers and natural expressions
                    4. Make it informative but casual
                    5. Around 400 words total
                    """,
                    
                    'daily': f"""
                    Transform the following script into a practical daily conversation.
                    
                    Original Script:
                    {script_content}
                    
                    Requirements:
                    1. Create realistic daily situation dialogue
                    2. Use common, practical expressions
                    3. Include polite phrases and natural responses
                    4. Make it useful for real-life situations
                    5. Around 300 words
                    """
                }
                
                for version in selected_versions:
                    if version == 'original':
                        continue
                    
                    if version in version_prompts:
                        st.write(f"4️⃣ {version.upper()} 버전 생성 중...")
                        
                        version_content = llm_provider.generate_content(version_prompts[version])
                        if version_content:
                            results[f"{version}_script"] = version_content
                            st.write(f"✅ {version.upper()} 스크립트 생성 완료")
                            
                            st.write(f"🔊 {version.upper()} 음성 생성 중...")
                            tts_kwargs = {
                                'speaking_rate': st.session_state.get('tts_speaking_rate', 1.0),
                                'pitch': st.session_state.get('tts_pitch', 0.0)
                            }
                            version_audio = generate_audio_with_fallback(
                                version_content,
                                st.session_state.tts_engine,
                                st.session_state.tts_voice,
                                **tts_kwargs
                            )
                            results[f"{version}_audio"] = version_audio
                            st.write(f"✅ {version.upper()} 음성 생성 완료" if version_audio else f"⚠️ {version.upper()} 음성 생성 실패")
                        else:
                            st.warning(f"⚠️ {version.upper()} 스크립트 생성 실패")
                
                st.session_state.script_results = results
                st.session_state.show_results = True
                
                backup_id = save_to_temp_backup_fixed(results, input_content, input_method, category)
                if backup_id:
                    st.info(f"💾 임시 저장 완료 (ID: {backup_id})")
                
                st.success("🎉 모든 콘텐츠 생성이 완료되었습니다!")
                
                time.sleep(1)
                st.rerun()
                
            else:
                st.error("⛔ 영어 스크립트 생성 실패")
        
        progress_container.empty()


def practice_page_with_sync():
    """동기화 기능이 포함된 연습하기 페이지"""
    st.header("🎯 연습하기")
    
    if 'storage' not in st.session_state:
        st.session_state.storage = HybridStorage()
    
    storage = st.session_state.storage
    
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        if hasattr(st.session_state, 'last_save_time'):
            st.info(f"🆕 마지막 저장: {st.session_state.last_save_time[:19]}")
    
    with col2:
        sync_status = storage.get_sync_status()
        if sync_status['drive_enabled']:
            if sync_status['status'] == 'syncing':
                st.info("🔄 동기화 중...")
            elif sync_status['status'] == 'completed':
                st.success("☁️ 동기화됨")
            elif sync_status['status'] == 'error':
                st.error("⚠ 동기화 오류")
            else:
                st.info("☁️ Drive 연결됨")
        else:
            st.warning("📱 로컬만")
    
    with col3:
        if st.button("🔄 새로고침"):
            st.session_state.file_projects = storage.load_all_projects()
            st.rerun()
    
    try:
        if 'file_projects' not in st.session_state:
            st.session_state.file_projects = storage.load_all_projects()
        
        projects = st.session_state.file_projects
        
        st.write(f"🔊 연결 상태: ✅ 성공")
        st.write(f"📋 로드된 프로젝트 수: {len(projects)}")
        
        if not projects:
            st.warning("저장된 프로젝트가 없습니다.")
            st.markdown("**스크립트 생성** 탭에서 새로운 스크립트를 만들어보세요! 🚀")
            return
        
        st.success(f"📚 총 {len(projects)}개의 프로젝트가 저장되어 있습니다.")
        st.markdown("### 📖 연습할 스크립트 선택")
        
        project_options = {}
        for project in projects:
            display_name = f"{project['title']} ({project['category']}) - {project['created_at'][:10]}"
            project_options[display_name] = project['project_id']
        
        selected_project_name = st.selectbox(
            "프로젝트 선택",
            list(project_options.keys()),
            help="연습하고 싶은 프로젝트를 선택하세요"
        )
        
        if selected_project_name:
            project_id = project_options[selected_project_name]
            
            project_content = storage.load_project_content(project_id)
            
            if not project_content:
                st.error(f"프로젝트 {project_id}를 로드할 수 없습니다")
                return
            
            metadata = project_content['metadata']
            
            st.markdown("### 📄 프로젝트 정보")
            info_col1, info_col2, info_col3, info_col4 = st.columns(4)
            
            with info_col1:
                st.markdown(f"**제목**: {metadata['title']}")
            with info_col2:
                st.markdown(f"**카테고리**: {metadata['category']}")
            with info_col3:
                st.markdown(f"**생성일**: {metadata['created_at'][:10]}")
            with info_col4:
                if storage.drive_enabled:
                    if st.button("☁️ 동기화", key=f"sync_{project_id}"):
                        with st.spinner("Google Drive에 동기화 중..."):
                            success = storage.manual_sync_project(project_id)
                            if success:
                                st.success("동기화 완료!")
                            else:
                                st.error("동기화 실패")
            
            available_versions = []
            
            if 'original_script' in project_content:
                available_versions.append(('original', '원본 스크립트', project_content['original_script']))
            
            version_names = {
                'ted': 'TED 3분 말하기',
                'podcast': '팟캐스트 대화', 
                'daily': '일상 대화'
            }
            
            for version_type, version_name in version_names.items():
                script_key = f"{version_type}_script"
                if script_key in project_content:
                    available_versions.append((version_type, version_name, project_content[script_key]))
            
            st.write(f"📊 사용 가능한 버전: {len(available_versions)}개")
            
            if available_versions:
                tab_names = [v[1] for v in available_versions]
                tabs = st.tabs(tab_names)
                
                for i, (version_type, version_name, content) in enumerate(available_versions):
                    with tabs[i]:
                        st.markdown(f"### 📃 {version_name}")
                        
                        st.markdown(f'''
                        <div class="script-container">
                            <div class="script-text">{content}</div>
                        </div>
                        ''', unsafe_allow_html=True)
                        
                        practice_col1, practice_col2 = st.columns([2, 1])
                        
                        with practice_col2:
                            st.markdown("### 🎧 음성 연습")
                            
                            audio_key = f"{version_type}_audio"
                            if audio_key in project_content:
                                audio_path = project_content[audio_key]
                                if os.path.exists(audio_path):
                                    st.audio(audio_path, format='audio/mp3')
                                else:
                                    st.warning("오디오 파일을 찾을 수 없습니다.")
                                    st.markdown(get_browser_tts_script(content), unsafe_allow_html=True)
                            else:
                                if st.button(f"🔊 음성 생성", key=f"tts_{version_type}_{project_id}"):
                                    with st.spinner("음성 생성 중..."):
                                        tts_kwargs = {
                                            'speaking_rate': st.session_state.get('tts_speaking_rate', 1.0),
                                            'pitch': st.session_state.get('tts_pitch', 0.0)
                                        }
                                        new_audio = generate_audio_with_fallback(
                                            content,
                                            st.session_state.get('tts_engine', 'auto'),
                                            st.session_state.get('tts_voice', 'en-us'),
                                            **tts_kwargs
                                        )
                                        if new_audio and os.path.exists(new_audio):
                                            try:
                                                project_path = Path(list(metadata['saved_files'].values())[0]).parent
                                                audio_folder = project_path / "audio"
                                                audio_dest = audio_folder / f"{version_type}_audio_new.mp3"
                                                shutil.copy2(new_audio, audio_dest)
                                                
                                                st.audio(str(audio_dest), format='audio/mp3')
                                                st.success("음성 생성 및 저장 완료!")
                                            except Exception as e:
                                                st.audio(new_audio, format='audio/mp3')
                                                st.warning(f"음성 생성은 됐지만 저장 실패: {e}")
                                        else:
                                            st.error("음성 생성 실패")
                                
                                st.markdown("**또는 브라우저 TTS 사용:**")
                                st.markdown(get_browser_tts_script(content), unsafe_allow_html=True)
                            
                            with st.expander("💡 연습 팁"):
                                if version_type == 'ted':
                                    st.markdown("""
                                    - 자신감 있게 말하기
                                    - 감정을 담아서 표현
                                    - 청중과 아이컨택 상상
                                    - 핵심 메시지에 강조
                                    """)
                                elif version_type == 'podcast':
                                    st.markdown("""
                                    - 자연스럽고 편안한 톤
                                    - 대화하듯 말하기
                                    - 질문과 답변 구분
                                    - 적절한 속도 유지
                                    """)
                                elif version_type == 'daily':
                                    st.markdown("""
                                    - 일상적이고 친근한 톤
                                    - 상황에 맞는 감정 표현
                                    - 실제 대화처럼 자연스럽게
                                    - 예의 바른 표현 연습
                                    """)
                                else:
                                    st.markdown("""
                                    - 명확한 발음 연습
                                    - 문장별로 나누어 연습
                                    - 녹음해서 비교하기
                                    - 반복 학습으로 유창성 향상
                                    """)
                        
                        if version_type == 'original' and 'korean_translation' in project_content:
                            st.markdown("### 🇰🇷 한국어 번역")
                            st.markdown(f'''
                            <div class="script-container">
                                <div class="translation-text" style="font-style: italic; color: #666;">{project_content["korean_translation"]}</div>
                            </div>
                            ''', unsafe_allow_html=True)
                
    except Exception as e:
        st.error(f"연습 페이지 로드 오류: {str(e)}")


def my_scripts_page_with_sync():
    """동기화 기능이 포함된 내 스크립트 페이지"""
    st.header("📚 내 스크립트")
    
    if 'storage' not in st.session_state:
        st.session_state.storage = HybridStorage()
    
    storage = st.session_state.storage
    
    col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
    
    with col1:
        search_query = st.text_input("🔍 검색", placeholder="제목 또는 내용 검색...")
    
    with col2:
        category_filter = st.selectbox(
            "카테고리",
            ["전체", "일반", "비즈니스", "여행", "교육", "건강", "기술", "문화", "스포츠"]
        )
    
    with col3:
        sort_order = st.selectbox("정렬", ["최신순", "제목순"])
    
    with col4:
        sync_status = storage.get_sync_status()
        if sync_status['drive_enabled']:
            if st.button("☁️ 전체 동기화"):
                st.info("전체 프로젝트 동기화를 시작합니다...")
        else:
            st.info("📱 로컬 모드")
    
    projects = storage.load_all_projects()
    
    if search_query:
        projects = [p for p in projects if search_query.lower() in p['title'].lower()]
    
    if category_filter != "전체":
        projects = [p for p in projects if p['category'] == category_filter]
    
    if sort_order == "제목순":
        projects.sort(key=lambda x: x['title'])
    else:
        projects.sort(key=lambda x: x['created_at'], reverse=True)
    
    if projects:
        st.write(f"총 {len(projects)}개의 프로젝트")
        
        for i in range(0, len(projects), 2):
            cols = st.columns(2)
            
            for j, col in enumerate(cols):
                if i + j < len(projects):
                    project = projects[i + j]
                    
                    with col:
                        with st.container():
                            st.markdown(f"### 📄 {project['title']}")
                            st.markdown(f"**카테고리**: {project['category']}")
                            st.markdown(f"**생성일**: {project['created_at'][:10]}")
                            st.markdown(f"**버전**: {len(project['versions'])}개")
                            
                            if storage.drive_enabled:
                                sync_metadata = storage.sync_manager.load_sync_metadata() if storage.sync_manager else {}
                                if project['project_id'] in sync_metadata:
                                    st.markdown("☁️ **동기화됨**")
                                else:
                                    st.markdown("📱 **로컬만**")
                            
                            button_cols = st.columns(4)
                            
                            with button_cols[0]:
                                if st.button("📖 보기", key=f"view_file_{project['project_id']}"):
                                    st.session_state[f"show_file_detail_{project['project_id']}"] = True
                            
                            with button_cols[1]:
                                if st.button("🎯 연습", key=f"practice_file_{project['project_id']}"):
                                    st.info("연습하기 탭으로 이동해서 해당 프로젝트를 선택하세요.")
                            
                            with button_cols[2]:
                                if storage.drive_enabled:
                                    if st.button("☁️ 동기화", key=f"sync_file_{project['project_id']}"):
                                        with st.spinner("동기화 중..."):
                                            success = storage.manual_sync_project(project['project_id'])
                                            if success:
                                                st.success("동기화 완료!")
                                            else:
                                                st.error("동기화 실패")
                                else:
                                    st.write("☁️")
                            
                            with button_cols[3]:
                                if st.button("🗑️ 삭제", key=f"delete_file_{project['project_id']}"):
                                    if st.session_state.get(f"confirm_delete_file_{project['project_id']}"):
                                        if storage.local_storage.delete_project(project['project_id']):
                                            st.success("삭제되었습니다!")
                                            st.session_state.file_projects = storage.load_all_projects()
                                            st.rerun()
                                    else:
                                        st.session_state[f"confirm_delete_file_{project['project_id']}"] = True
                                        st.warning("한 번 더 클릭하면 삭제됩니다.")
                            
                            if st.session_state.get(f"show_file_detail_{project['project_id']}"):
                                with st.expander(f"📋 {project['title']} 상세보기", expanded=True):
                                    project_content = storage.load_project_content(project['project_id'])
                                    
                                    if project_content:
                                        if 'original_script' in project_content:
                                            st.markdown("#### 🇺🇸 영어 스크립트")
                                            st.markdown(project_content['original_script'])
                                        
                                        if 'korean_translation' in project_content:
                                            st.markdown("#### 🇰🇷 한국어 번역")
                                            st.markdown(project_content['korean_translation'])
                                        
                                        st.markdown("#### 📝 연습 버전들")
                                        
                                        version_names = {
                                            'ted': 'TED 3분 말하기',
                                            'podcast': '팟캐스트 대화',
                                            'daily': '일상 대화'
                                        }
                                        
                                        for version_type, version_name in version_names.items():
                                            script_key = f"{version_type}_script"
                                            if script_key in project_content:
                                                st.markdown(f"**{version_name}**")
                                                content = project_content[script_key]
                                                preview = content[:200] + "..." if len(content) > 200 else content
                                                st.markdown(preview)
                                                st.markdown("---")
                                    
                                    if st.button("닫기", key=f"close_file_{project['project_id']}"):
                                        st.session_state[f"show_file_detail_{project['project_id']}"] = False
                                        st.rerun()
    else:
        st.info("저장된 프로젝트가 없습니다.")
        st.markdown("**스크립트 생성** 탭에서 새로운 프로젝트를 만들어보세요! 🚀")


def settings_page_with_oauth_drive():
    """OAuth 2.0 Google Drive 설정이 포함된 설정 페이지"""
    st.header("⚙️ 환경 설정")
    
    if 'storage' not in st.session_state:
        st.session_state.storage = HybridStorage()
    
    storage = st.session_state.storage
    
    # Google Drive 설정 (OAuth 2.0)
    with st.expander("☁️ Google Drive 동기화 (OAuth 2.0)", expanded=True):
        if GOOGLE_DRIVE_AVAILABLE:
            st.markdown("### Google Drive OAuth 2.0 연동")
            
            drive_status = storage.get_sync_status()
            
            if drive_status['drive_enabled']:
                st.success("✅ Google Drive OAuth 2.0이 연결되었습니다!")
                
                oauth_info = storage.drive_manager.get_oauth_info()
                folder_info = storage.drive_manager.get_current_folder_info()
                
                if oauth_info:
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.info(f"**프로젝트 ID**: {oauth_info['project_id']}")
                        st.info(f"**클라이언트 ID**: {oauth_info['client_id']}")
                    
                    with col2:
                        if folder_info:
                            st.info(f"**저장 폴더**: {folder_info['name']}")
                            st.info(f"**폴더 경로**: {folder_info['path']}")
                        st.info(f"📅 마지막 동기화: {drive_status.get('last_sync', '없음')}")
                
                # 연결 해제 버튼
                st.markdown("---")
                if st.button("🔌 연결 해제"):
                    if storage.disconnect_drive():
                        st.success("Google Drive 연결이 해제되었습니다.")
                        st.rerun()
                    else:
                        st.error("연결 해제 실패")
            
            else:
                st.warning("Google Drive OAuth 2.0이 연결되지 않았습니다.")
                
                show_guide = st.checkbox("📋 상세 설정 가이드 보기")
                
                if show_guide:
                    st.markdown("""
                    ### 1. Google Cloud Console에서 프로젝트 생성
                    - [Google Cloud Console](https://console.cloud.google.com/) 접속
                    - 새 프로젝트 생성 또는 기존 프로젝트 선택
                    
                    ### 2. Google Drive API 활성화
                    - API 및 서비스 > 라이브러리로 이동
                    - "Google Drive API" 검색 후 활성화
                    
                    ### 3. OAuth 2.0 클라이언트 ID 생성
                    - API 및 서비스 > 사용자 인증 정보로 이동
                    - "사용자 인증 정보 만들기" > "OAuth 클라이언트 ID" 선택
                    - 애플리케이션 유형: "데스크톱 애플리케이션" 선택
                    - 이름 입력 후 생성
                    
                    ### 4. JSON 파일 다운로드
                    - 생성된 OAuth 2.0 클라이언트 ID 클릭
                    - "JSON 다운로드" 버튼 클릭
                    - 다운로드된 JSON 파일 내용을 아래에 붙여넣기
                    
                    ### 5. 테스트 사용자 추가 (필요시)
                    - OAuth 동의 화면에서 "테스트 사용자" 추가
                    - 본인의 Gmail 주소를 테스트 사용자로 등록
                    
                    ### ⚠️ 주의사항
                    - OAuth 2.0 클라이언트 JSON은 안전하게 보관하세요
                    - 처음 인증 시 브라우저에서 Google 로그인이 필요합니다
                    - 인증 후 토큰이 자동으로 저장되어 다음번부터는 자동 로그인됩니다
                    """)
                
                st.markdown("#### 🔐 OAuth 2.0 클라이언트 JSON 입력")
                
                oauth_credentials_json = st.text_area(
                    "OAuth 2.0 클라이언트 자격증명 JSON",
                    height=250,
                    placeholder='''{
  "installed": {
    "client_id": "your-client-id.apps.googleusercontent.com",
    "project_id": "your-project-id",
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token",
    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
    "client_secret": "your-client-secret",
    "redirect_uris": ["http://localhost"]
  }
}''',
                    help="Google Cloud Console에서 다운로드한 OAuth 2.0 클라이언트 JSON 내용을 붙여넣으세요"
                )
                
                col1, col2, col3 = st.columns([1, 1, 1])
                
                with col1:
                    if st.button("🔗 Google Drive 연결", type="primary"):
                        if oauth_credentials_json.strip():
                            try:
                                success = storage.enable_drive_sync(oauth_credentials_json)
                                
                                if success:
                                    st.success("✅ Google Drive OAuth 2.0 연결 성공!")
                                    st.balloons()
                                    time.sleep(1)
                                    st.rerun()
                                else:
                                    st.error("⚠ Google Drive 연결 실패")
                                    
                            except Exception as e:
                                st.error(f"⚠ 연결 오류: {str(e)}")
                                
                        else:
                            st.error("OAuth 2.0 클라이언트 JSON을 입력해주세요.")
                
                with col2:
                    if st.button("🔄 재인증"):
                        if oauth_credentials_json.strip():
                            try:
                                success = storage.enable_drive_sync(oauth_credentials_json, force_reauth=True)
                                
                                if success:
                                    st.success("✅ 재인증 성공!")
                                    st.balloons()
                                    time.sleep(1)
                                    st.rerun()
                                else:
                                    st.error("⚠ 재인증 실패")
                                    
                            except Exception as e:
                                st.error(f"⚠ 재인증 오류: {str(e)}")
                        else:
                            st.error("OAuth 2.0 클라이언트 JSON을 입력해주세요.")
                
                with col3:
                    st.info("""
                    **OAuth 2.0 방식의 장점:**
                    - 개인 Google Drive 직접 접근
                    - 브라우저 인증 후 자동 로그인
                    - 토큰 자동 갱신으로 지속 사용
                    - 복잡한 권한 설정 불필요
                    """)
        
        else:
            st.error("⚠ Google Drive API 라이브러리가 설치되지 않았습니다.")
            st.markdown("""
            다음 명령어로 필요한 라이브러리를 설치하세요:
            ```bash
            pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib
            ```
            """)
    
    # LLM 설정
    with st.expander("🤖 LLM 설정", expanded=True):
        col1, col2 = st.columns(2)
        
        with col1:
            provider = st.selectbox(
                "Provider 선택",
                ['OpenAI', 'Anthropic', 'Google'],
                index=['OpenAI', 'Anthropic', 'Google'].index(st.session_state.api_provider)
            )
            st.session_state.api_provider = provider
        
        with col2:
            if provider == 'OpenAI':
                models = ['gpt-4o-mini', 'gpt-4o', 'gpt-4-turbo', 'gpt-3.5-turbo']
            elif provider == 'Anthropic':
                models = ['claude-3-haiku-20240307', 'claude-3-sonnet-20240229', 'claude-3-opus-20240229']
            else:
                models = ['gemini-pro', 'gemini-pro-vision']
            
            model = st.selectbox("Model 선택", models)
            st.session_state.model = model
        
        api_key = st.text_input(
            "API Key",
            value=st.session_state.api_key,
            type="password",
            help="LLM API 키를 입력하세요"
        )
        st.session_state.api_key = api_key
    
    # TTS 설정
    with st.expander("🔊 TTS 설정"):
        # Google Cloud TTS 설정
        setup_google_tts_credentials()
        
        st.markdown("---")
        
        col1, col2 = st.columns(2)
        
        with col1:
            engine_options = get_available_engines()
            selected_engine = st.selectbox("TTS 엔진", engine_options)
            
            if 'wavenet' in selected_engine.lower():
                st.session_state.tts_engine = 'wavenet'
            elif 'gtts' in selected_engine.lower():
                st.session_state.tts_engine = 'gtts'
            elif 'pyttsx3' in selected_engine.lower():
                st.session_state.tts_engine = 'pyttsx3'
            else:
                st.session_state.tts_engine = 'auto'
        
        with col2:
            voice_options = get_voice_options()
            selected_voice_name = st.selectbox("음성 언어", list(voice_options.keys()))
            st.session_state.tts_voice = voice_options[selected_voice_name]
        
        # Wavenet 고급 설정
        if st.session_state.tts_engine == 'wavenet':
            st.markdown("#### 🎛️ Wavenet 고급 설정")
            
            col1, col2 = st.columns(2)
            with col1:
                speaking_rate = st.slider(
                    "말하기 속도", 
                    min_value=0.25, 
                    max_value=4.0, 
                    value=1.0, 
                    step=0.25,
                    help="1.0이 기본 속도입니다"
                )
                st.session_state.tts_speaking_rate = speaking_rate
            
            with col2:
                pitch = st.slider(
                    "음성 피치", 
                    min_value=-20.0, 
                    max_value=20.0, 
                    value=0.0, 
                    step=1.0,
                    help="0.0이 기본 피치입니다"
                )
                st.session_state.tts_pitch = pitch
        
        # TTS 엔진 테스트
        st.markdown("---")
        test_tts_engines()
    
    # 시스템 테스트
    with st.expander("🔧 시스템 테스트"):
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**데이터베이스 테스트**")
            if st.button("DB 연결 테스트"):
                try:
                    db = FixedDatabase()
                    test_id = db.create_script_project(
                        title="테스트 스크립트",
                        original_content="This is a test script.",
                        korean_translation="이것은 테스트 스크립트입니다.",
                        category="test"
                    )
                    
                    project = db.get_script_project(test_id)
                    if project['script']:
                        st.success(f"✅ DB 테스트 성공! (ID: {test_id})")
                        
                        db.delete_script_project(test_id)
                        st.info("🗑️ 테스트 데이터 정리 완료")
                    else:
                        st.error("⛔ DB 테스트 실패")
                        
                except Exception as e:
                    st.error(f"⛔ DB 테스트 오류: {str(e)}")
        
        with col2:
            st.markdown("**Google Drive 테스트**")
            if st.button("Drive API 테스트"):
                if storage.drive_enabled and storage.drive_manager.is_authenticated():
                    try:
                        test_success, test_message = storage.drive_manager.test_upload_permission()
                        
                        if test_success:
                            st.success("✅ Drive API 테스트 성공!")
                            st.info("업로드 권한이 정상적으로 작동합니다.")
                        else:
                            st.error(f"⚠ Drive API 테스트 실패: {test_message}")
                        
                    except Exception as e:
                        st.error(f"⚠ Drive 테스트 오류: {str(e)}")
                else:
                    st.warning("⚠️ Google Drive가 연결되지 않았습니다.")


def main():
    """메인 애플리케이션 (통합 버전)"""
    st.set_page_config(
        page_title="MyTalk - 통합 버전 (Wavenet TTS + OAuth 2.0 Drive)",
        page_icon="🎙️",
        layout="wide",
        initial_sidebar_state="collapsed"
    )
    
    init_session_state()
    
    # CSS 스타일
    st.markdown("""
    <style>
        .stApp {
            max-width: 100%;
            padding: 1rem;
        }
        .stButton > button {
            width: 100%;
            height: 3rem;
            font-size: 1.1rem;
            margin: 0.5rem 0;
            border-radius: 10px;
        }
        .script-container {
            background: linear-gradient(135deg, #f0f2f6, #e8eaf0);
            padding: 1.5rem;
            border-radius: 15px;
            margin: 1rem 0;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        .script-text {
            font-size: 1.1rem;
            line-height: 1.8;
            color: #1f1f1f;
            font-family: 'Georgia', serif;
        }
        .translation-text {
            font-size: 0.95rem;
            color: #666;
            font-style: italic;
            line-height: 1.6;
        }
        .sync-status {
            padding: 0.5rem;
            border-radius: 5px;
            margin: 0.25rem 0;
            font-size: 0.9rem;
        }
        .sync-connected {
            background-color: #d4edda;
            color: #155724;
            border: 1px solid #c3e6cb;
        }
        .sync-syncing {
            background-color: #fff3cd;
            color: #856404;
            border: 1px solid #ffeaa7;
        }
        .sync-error {
            background-color: #f8d7da;
            color: #721c24;
            border: 1px solid #f5c6cb;
        }
        .sync-local {
            background-color: #e2e3e5;
            color: #383d41;
            border: 1px solid #d6d8db;
        }
    </style>
    """, unsafe_allow_html=True)
    
    # 헤더
    st.markdown("""
    <div style='text-align: center; padding: 1rem; background: linear-gradient(90deg, #4CAF50, #45a049); border-radius: 10px; margin-bottom: 2rem;'>
        <h1 style='color: white; margin: 0;'>🎙️ MyTalk</h1>
        <p style='color: white; margin: 0; opacity: 0.9;'>나만의 영어 말하기 학습 앱 with Google Wavenet TTS + OAuth 2.0 Drive</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Google Drive 연결 상태 표시
    if 'storage' not in st.session_state:
        st.session_state.storage = HybridStorage()
    
    storage = st.session_state.storage
    sync_status = storage.get_sync_status()
    
    # 상단 동기화 상태 바
    if sync_status['drive_enabled']:
        if sync_status['status'] == 'syncing':
            st.markdown("""
            <div class="sync-status sync-syncing">
                🔄 Google Drive 동기화 진행 중...
            </div>
            """, unsafe_allow_html=True)
        elif sync_status['status'] == 'completed':
            last_sync = sync_status.get('last_sync', 'Unknown')
            st.markdown(f"""
            <div class="sync-status sync-connected">
                ☁️ Google Drive 연결됨 | 마지막 동기화: {last_sync[:19] if last_sync != 'Unknown' else 'Unknown'}
            </div>
            """, unsafe_allow_html=True)
        elif sync_status['status'] == 'error':
            st.markdown("""
            <div class="sync-status sync-error">
                ⚠ Google Drive 동기화 오류 발생 | 설정을 확인해주세요
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown("""
            <div class="sync-status sync-connected">
                ☁️ Google Drive 연결됨 | 동기화 대기 중
            </div>
            """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div class="sync-status sync-local">
            📱 로컬 모드 | Google Drive 미연결 (설정에서 연결 가능)
        </div>
        """, unsafe_allow_html=True)
    
    # TTS 엔진 상태 표시
    tts_info = []
    if GOOGLE_TTS_AVAILABLE:
        tts_info.append("🤖 Wavenet")
    if GTTS_AVAILABLE:
        tts_info.append("🌐 gTTS")
    if PYTTSX3_AVAILABLE:
        tts_info.append("🖥️ pyttsx3")
    
    if tts_info:
        st.markdown(f"""
        <div class="sync-status sync-connected">
            🔊 TTS 엔진: {' | '.join(tts_info)} | 현재 설정: {st.session_state.get('tts_engine', 'auto')}
        </div>
        """, unsafe_allow_html=True)
    
    # 네비게이션 탭
    tab1, tab2, tab3, tab4 = st.tabs(["✏️ 스크립트 작성", "🎯 연습하기", "📚 내 스크립트", "⚙️ 설정"])
    
    with tab1:
        script_creation_page()
    
    with tab2:
        practice_page_with_sync()
    
    with tab3:
        my_scripts_page_with_sync()
    
    with tab4:
        settings_page_with_oauth_drive()
    
    # 푸터
    st.markdown("---")
    
    # 시스템 정보
    system_info_col1, system_info_col2, system_info_col3 = st.columns(3)
    
    with system_info_col1:
        drive_status_text = "☁️ OAuth 2.0 Google Drive" if sync_status['drive_enabled'] else "📱 Local Mode"
        st.markdown(f"**저장소**: {drive_status_text}")
    
    with system_info_col2:
        tts_engine_text = st.session_state.get('tts_engine', 'auto')
        available_engines = len([e for e in [GOOGLE_TTS_AVAILABLE, GTTS_AVAILABLE, PYTTSX3_AVAILABLE] if e])
        st.markdown(f"**TTS**: {tts_engine_text} ({available_engines}개 엔진)")
    
    with system_info_col3:
        llm_provider = st.session_state.get('api_provider', 'None')
        st.markdown(f"**LLM**: {llm_provider}")
    
    st.markdown(f"""
    <div style='text-align: center; color: #666; font-size: 0.8rem; margin-top: 2rem;'>
        <p>MyTalk v4.0 - 통합 버전 (Google Wavenet TTS + OAuth 2.0 Google Drive)</p>
        <p>Made with ❤️ using Streamlit | 원스톱 영어 학습 솔루션</p>
        <p>📦 설치된 패키지: {'✅' if GOOGLE_DRIVE_AVAILABLE else '❌'} Drive API | {'✅' if GOOGLE_TTS_AVAILABLE else '❌'} Wavenet TTS | {'✅' if GTTS_AVAILABLE else '❌'} gTTS | {'✅' if PYTTSX3_AVAILABLE else '❌'} pyttsx3</p>
    </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()