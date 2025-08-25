"""
MyTalk - Personal English Speaking App (Redesigned)
개인용 영어 말하기 학습 앱 - 개선된 버전
"""

import streamlit as st
import os
import json
import sqlite3
from datetime import datetime
import base64
from pathlib import Path
import tempfile
from PIL import Image
import io
import asyncio
import time
import pickle
import uuid

# LLM Providers
import openai
from anthropic import Anthropic
import google.generativeai as genai

# Google Drive
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload

# TTS Module
from tts_module import TTSManager, generate_audio_with_fallback, get_browser_tts_script

# 페이지 설정
st.set_page_config(
    page_title="MyTalk - 영어 말하기",
    page_icon="🎙️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# CSS for mobile optimization and better UI
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
    .primary-button > button {
        background: linear-gradient(90deg, #4CAF50, #45a049);
        color: white;
        border: none;
    }
    .audio-player {
        width: 100%;
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
        margin-top: 0.5rem;
        font-style: italic;
    }
    .progress-container {
        background-color: #f8f9fa;
        padding: 1rem;
        border-radius: 10px;
        margin: 1rem 0;
    }
    .status-badge {
        display: inline-block;
        padding: 0.3rem 0.8rem;
        border-radius: 20px;
        font-size: 0.8rem;
        font-weight: bold;
        margin: 0.2rem;
    }
    .status-success {
        background-color: #d4edda;
        color: #155724;
    }
    .status-processing {
        background-color: #fff3cd;
        color: #856404;
    }
    .status-error {
        background-color: #f8d7da;
        color: #721c24;
    }
    .version-card {
        border: 2px solid #e9ecef;
        border-radius: 10px;
        padding: 1rem;
        margin: 0.5rem 0;
        transition: all 0.3s ease;
    }
    .version-card:hover {
        border-color: #4CAF50;
        box-shadow: 0 2px 8px rgba(76,175,80,0.2);
    }
    @media (max-width: 768px) {
        .stApp {
            padding: 0.5rem;
        }
        .script-text {
            font-size: 1rem;
        }
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
def init_session_state():
    defaults = {
        'api_provider': 'OpenAI',
        'api_key': '',
        'model': 'gpt-4o-mini',
        'db_path': 'mytalk.db',
        'google_drive_enabled': False,
        'google_credentials': None,
        'current_project': None,
        'generation_progress': {},
        'tts_engine': 'auto',
        'tts_voice': 'en',
        'selected_versions': [],
        # 복구 관련 상태들
        'restored_input_content': '',
        'restored_input_method': 'text',
        'restored_category': 'general',
        'current_backup_id': None,  # 현재 복구된 백업의 ID
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

# Enhanced Database with multi-table structure
class EnhancedDatabase:
    def __init__(self, db_path='mytalk.db'):
        self.db_path = db_path
        self.init_db()
    
    def init_db(self):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # 메인 스크립트 테이블
        c.execute('''
            CREATE TABLE IF NOT EXISTS scripts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                original_content TEXT NOT NULL,
                korean_translation TEXT,
                category TEXT DEFAULT 'general',
                input_type TEXT DEFAULT 'text',
                input_data TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 연습 버전 테이블
        c.execute('''
            CREATE TABLE IF NOT EXISTS practice_versions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                script_id INTEGER,
                version_type TEXT NOT NULL,
                content TEXT NOT NULL,
                audio_path TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (script_id) REFERENCES scripts (id)
            )
        ''')
        
        # 파일 저장 테이블
        c.execute('''
            CREATE TABLE IF NOT EXISTS stored_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                script_id INTEGER,
                file_type TEXT NOT NULL,
                file_name TEXT NOT NULL,
                local_path TEXT,
                gdrive_path TEXT,
                gdrive_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (script_id) REFERENCES scripts (id)
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def create_script_project(self, title, original_content, korean_translation, category, input_type, input_data):
        """새 스크립트 프로젝트 생성 (디버깅 개선)"""
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            
            # 데이터 검증
            if not title or not original_content:
                raise ValueError(f"필수 데이터 누락: title='{title}', content='{original_content[:50] if original_content else None}'")
            
            c.execute('''
                INSERT INTO scripts (title, original_content, korean_translation, category, input_type, input_data)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (title, original_content, korean_translation or '', category, input_type, input_data or ''))
            
            script_id = c.lastrowid
            conn.commit()
            
            # 저장 확인
            c.execute('SELECT COUNT(*) FROM scripts WHERE id = ?', (script_id,))
            if c.fetchone()[0] == 0:
                raise Exception(f"스크립트 저장 실패 확인: ID {script_id}")
                
            conn.close()
            return script_id
            
        except Exception as e:
            if 'conn' in locals():
                conn.rollback()
                conn.close()
            raise Exception(f"데이터베이스 저장 오류: {str(e)}")
    
    def add_practice_version(self, script_id, version_type, content, audio_path=None):
        """연습 버전 추가"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('''
            INSERT INTO practice_versions (script_id, version_type, content, audio_path)
            VALUES (?, ?, ?, ?)
        ''', (script_id, version_type, content, audio_path))
        version_id = c.lastrowid
        conn.commit()
        conn.close()
        return version_id
    
    def add_stored_file(self, script_id, file_type, file_name, local_path=None, gdrive_path=None, gdrive_id=None):
        """저장된 파일 정보 추가"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('''
            INSERT INTO stored_files (script_id, file_type, file_name, local_path, gdrive_path, gdrive_id)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (script_id, file_type, file_name, local_path, gdrive_path, gdrive_id))
        file_id = c.lastrowid
        conn.commit()
        conn.close()
        return file_id
    
    def get_script_project(self, script_id):
        """스크립트 프로젝트 전체 정보 조회"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # 메인 스크립트 정보
        c.execute('SELECT * FROM scripts WHERE id = ?', (script_id,))
        script = c.fetchone()
        
        # 연습 버전들
        c.execute('SELECT * FROM practice_versions WHERE script_id = ?', (script_id,))
        versions = c.fetchall()
        
        # 파일들
        c.execute('SELECT * FROM stored_files WHERE script_id = ?', (script_id,))
        files = c.fetchall()
        
        conn.close()
        
        return {
            'script': script,
            'versions': versions,
            'files': files
        }
    
    def get_all_scripts(self):
        """모든 스크립트 목록 조회"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('SELECT * FROM scripts ORDER BY created_at DESC')
        scripts = c.fetchall()
        conn.close()
        return scripts
    
    def search_scripts(self, query):
        """스크립트 검색"""
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
    
    def delete_script_project(self, script_id):
        """스크립트 프로젝트 전체 삭제"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('DELETE FROM stored_files WHERE script_id = ?', (script_id,))
        c.execute('DELETE FROM practice_versions WHERE script_id = ?', (script_id,))
        c.execute('DELETE FROM scripts WHERE id = ?', (script_id,))
        conn.commit()
        conn.close()

# Enhanced Google Drive Manager
class EnhancedGoogleDriveManager:
    def __init__(self, credentials_path=None):
        self.credentials = None
        self.service = None
        self.base_folder_id = None
        
        if credentials_path and os.path.exists(credentials_path):
            self.initialize_service(credentials_path)
    
    def initialize_service(self, credentials_path):
        """Google Drive 서비스 초기화"""
        try:
            self.credentials = service_account.Credentials.from_service_account_file(
                credentials_path,
                scopes=['https://www.googleapis.com/auth/drive.file']
            )
            self.service = build('drive', 'v3', credentials=self.credentials)
            self.base_folder_id = self.ensure_base_folder()
            return True
        except Exception as e:
            st.error(f"Google Drive 초기화 실패: {str(e)}")
            return False
    
    def ensure_base_folder(self):
        """기본 폴더 구조 생성"""
        try:
            # GDRIVE_API 폴더 찾기/생성
            api_folder_id = self.create_folder_if_not_exists("GDRIVE_API")
            # MyTalk 폴더 찾기/생성
            mytalk_folder_id = self.create_folder_if_not_exists("MyTalk", api_folder_id)
            return mytalk_folder_id
        except Exception as e:
            st.error(f"기본 폴더 생성 실패: {str(e)}")
            return None
    
    def create_folder_if_not_exists(self, folder_name, parent_id=None):
        """폴더가 없으면 생성, 있으면 ID 반환"""
        try:
            # 폴더 검색
            query = f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder'"
            if parent_id:
                query += f" and '{parent_id}' in parents"
            
            results = self.service.files().list(q=query, fields="files(id, name)").execute()
            items = results.get('files', [])
            
            if items:
                return items[0]['id']
            
            # 새 폴더 생성
            file_metadata = {
                'name': folder_name,
                'mimeType': 'application/vnd.google-apps.folder'
            }
            if parent_id:
                file_metadata['parents'] = [parent_id]
            
            folder = self.service.files().create(body=file_metadata, fields='id').execute()
            return folder.get('id')
        except Exception as e:
            st.error(f"폴더 생성 실패: {str(e)}")
            return None
    
    def create_project_folder(self, project_title):
        """프로젝트별 폴더 생성"""
        if not self.base_folder_id:
            return None
        
        # 날짜별 폴더 구조: 2025/01/
        now = datetime.now()
        year_folder = self.create_folder_if_not_exists(str(now.year), self.base_folder_id)
        month_folder = self.create_folder_if_not_exists(f"{now.month:02d}", year_folder)
        
        # 프로젝트 폴더: 20250122_프로젝트명
        date_prefix = now.strftime("%Y%m%d")
        safe_title = "".join(c for c in project_title if c.isalnum() or c in (' ', '_')).strip()
        project_folder_name = f"{date_prefix}_{safe_title}"
        
        project_folder_id = self.create_folder_if_not_exists(project_folder_name, month_folder)
        return project_folder_id
    
    def upload_file(self, file_path, file_name, folder_id):
        """파일 업로드"""
        try:
            file_metadata = {
                'name': file_name,
                'parents': [folder_id]
            }
            
            media = MediaFileUpload(file_path, resumable=True)
            file = self.service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id'
            ).execute()
            
            return file.get('id')
        except Exception as e:
            st.error(f"파일 업로드 실패: {str(e)}")
            return None
    
    def save_project_files(self, script_id, project_title, files_data):
        """프로젝트의 모든 파일을 구조적으로 저장"""
        project_folder_id = self.create_project_folder(project_title)
        if not project_folder_id:
            return False
        
        db = EnhancedDatabase()
        
        for file_data in files_data:
            file_type = file_data['type']
            file_path = file_data['path']
            file_name = file_data['name']
            
            # Google Drive에 업로드
            gdrive_id = self.upload_file(file_path, file_name, project_folder_id)
            
            if gdrive_id:
                # 데이터베이스에 기록
                gdrive_path = f"MyTalk/{datetime.now().year}/{datetime.now().month:02d}/{project_title}/{file_name}"
                db.add_stored_file(
                    script_id=script_id,
                    file_type=file_type,
                    file_name=file_name,
                    local_path=file_path,
                    gdrive_path=gdrive_path,
                    gdrive_id=gdrive_id
                )
        
        return True

# Enhanced LLM Provider with better prompts
class EnhancedLLMProvider:
    def __init__(self, provider, api_key, model):
        self.provider = provider
        self.api_key = api_key
        self.model = model
        self.setup_client()
    
    def setup_client(self):
        """클라이언트 초기화"""
        try:
            if self.provider == 'OpenAI':
                openai.api_key = self.api_key
                self.client = openai
            elif self.provider == 'Anthropic':
                self.client = Anthropic(api_key=self.api_key)
            elif self.provider == 'Google':
                genai.configure(api_key=self.api_key)
                self.client = genai
        except Exception as e:
            st.error(f"LLM 클라이언트 초기화 실패: {str(e)}")
            self.client = None
    
    def generate_original_script(self, input_content, input_type="text", category="general", image=None):
        """원본 영어 스크립트 생성"""
        prompt = f"""
        Create a natural, engaging English script based on the following input.
        
        Input Type: {input_type}
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
        
        KEY_PHRASES: [List 5 important phrases from the script]
        """
        
        return self._make_llm_call(prompt, image)
    
    def translate_to_korean(self, english_text):
        """한국어 번역 생성"""
        prompt = f"""
        Translate the following English text to natural, fluent Korean.
        Focus on meaning rather than literal translation.
        
        English Text:
        {english_text}
        
        Provide only the Korean translation:
        """
        
        return self._make_llm_call(prompt)
    
    def create_ted_version(self, original_script, title):
        """TED 3분 말하기 버전 생성"""
        prompt = f"""
        Transform the following script into a TED-style 3-minute presentation format.
        
        Original Script:
        {original_script}
        
        Requirements:
        1. Add a powerful hook opening
        2. Include personal stories or examples
        3. Create 2-3 main points with clear transitions
        4. End with an inspiring call to action
        5. Use TED-style language and pacing
        6. Keep it around 400-450 words (3 minutes speaking)
        
        Format:
        [Hook opening]
        
        [Personal story/example]
        
        [Main Point 1]
        [Transition]
        [Main Point 2]
        [Transition]
        [Main Point 3]
        
        [Inspiring conclusion and call to action]
        """
        
        return self._make_llm_call(prompt)
    
    def create_podcast_version(self, original_script, title):
        """PODCAST 2인 대화 버전 생성"""
        prompt = f"""
        Transform the following script into a natural 2-person podcast dialogue.
        
        Original Script:
        {original_script}
        
        Requirements:
        1. Create natural conversation between Host and Guest
        2. Include follow-up questions and responses
        3. Add conversational fillers and natural expressions
        4. Make it informative but casual
        5. Around 400 words total
        
        Format:
        Host: [Introduction and first question]
        Guest: [Detailed response with examples]
        Host: [Follow-up question]
        Guest: [Further explanation]
        [Continue natural dialogue...]
        Host: [Closing remarks]
        """
        
        return self._make_llm_call(prompt)
    
    def create_daily_conversation_version(self, original_script, title):
        """일상 2인 대화 버전 생성"""
        prompt = f"""
        Transform the following script into a practical daily conversation.
        
        Original Script:
        {original_script}
        
        Requirements:
        1. Create realistic daily situation dialogue
        2. Use common, practical expressions
        3. Include polite phrases and natural responses
        4. Make it useful for real-life situations
        5. Around 300 words
        
        Format:
        Person A: [Natural opening]
        Person B: [Appropriate response]
        Person A: [Follow-up]
        Person B: [Natural continuation]
        [Continue realistic conversation...]
        """
        
        return self._make_llm_call(prompt)
    
    def _make_llm_call(self, prompt, image=None):
        """LLM API 호출"""
        try:
            if not self.client:
                return None
            
            if self.provider == 'OpenAI':
                messages = [{"role": "user", "content": prompt}]
                
                if image:
                    buffered = io.BytesIO()
                    image.save(buffered, format="PNG")
                    img_str = base64.b64encode(buffered.getvalue()).decode()
                    messages[0]["content"] = [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_str}"}}
                    ]
                
                response = self.client.ChatCompletion.create(
                    model=self.model,
                    messages=messages,
                    max_tokens=1200,
                    temperature=0.7
                )
                return response.choices[0].message.content
            
            elif self.provider == 'Anthropic':
                content = prompt
                if image:
                    # Anthropic의 이미지 처리 로직 (필요시 구현)
                    pass
                
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=1200,
                    messages=[{"role": "user", "content": content}]
                )
                return response.content[0].text
            
            elif self.provider == 'Google':
                model = genai.GenerativeModel(self.model)
                if image:
                    response = model.generate_content([prompt, image])
                else:
                    response = model.generate_content(prompt)
                return response.text
        
        except Exception as e:
            st.error(f"LLM 호출 실패: {str(e)}")
            return None

# Content Generation Pipeline
class ContentGenerationPipeline:
    def __init__(self, llm_provider, tts_manager, gdrive_manager=None):
        self.llm = llm_provider
        self.tts = tts_manager
        self.gdrive = gdrive_manager
        self.progress_callback = None
    
    def set_progress_callback(self, callback):
        """진행상황 콜백 설정"""
        self.progress_callback = callback
    
    def update_progress(self, step, status, message=""):
        """진행상황 업데이트"""
        if self.progress_callback:
            self.progress_callback(step, status, message)
    
    def generate_all_content(self, input_content, input_type, category, image=None, selected_versions=None):
        """모든 콘텐츠 생성 파이프라인"""
        if not selected_versions:
            selected_versions = ['original', 'ted', 'podcast', 'daily']
        
        results = {}
        
        # 1. 원본 영어 스크립트 생성
        self.update_progress("original", "processing", "영어 스크립트 생성 중...")
        
        original_response = self.llm.generate_original_script(input_content, input_type, category, image)
        if not original_response:
            self.update_progress("original", "error", "영어 스크립트 생성 실패")
            return None
        
        # 제목과 스크립트 분리
        lines = original_response.split('\n')
        title = "Generated Script"
        script_content = original_response
        
        for line in lines:
            if line.startswith('TITLE:'):
                title = line.replace('TITLE:', '').strip()
                break
        
        # SCRIPT: 부분 추출
        script_start = original_response.find('SCRIPT:')
        if script_start != -1:
            script_end = original_response.find('KEY_PHRASES:')
            if script_end != -1:
                script_content = original_response[script_start+7:script_end].strip()
            else:
                script_content = original_response[script_start+7:].strip()
        
        results['title'] = title
        results['original_script'] = script_content
        self.update_progress("original", "success", "영어 스크립트 생성 완료")
        
        # 2. 한국어 번역 생성
        self.update_progress("translation", "processing", "한국어 번역 생성 중...")
        translation = self.llm.translate_to_korean(script_content)
        results['korean_translation'] = translation or "번역 생성 실패"
        self.update_progress("translation", "success" if translation else "error", 
                           "한국어 번역 생성 완료" if translation else "한국어 번역 생성 실패")
        
        # 3. 원본 음성 생성
        self.update_progress("original_audio", "processing", "원본 음성 생성 중...")
        original_audio = generate_audio_with_fallback(
            script_content, 
            st.session_state.tts_engine, 
            st.session_state.tts_voice
        )
        results['original_audio'] = original_audio
        self.update_progress("original_audio", "success" if original_audio else "error",
                           "원본 음성 생성 완료" if original_audio else "원본 음성 생성 실패")
        
        # 4. 각 버전별 생성
        version_methods = {
            'ted': self.llm.create_ted_version,
            'podcast': self.llm.create_podcast_version,
            'daily': self.llm.create_daily_conversation_version
        }
        
        for version in selected_versions:
            if version == 'original':
                continue
            
            if version in version_methods:
                self.update_progress(version, "processing", f"{version.upper()} 버전 생성 중...")
                
                version_content = version_methods[version](script_content, title)
                if version_content:
                    results[f"{version}_script"] = version_content
                    self.update_progress(version, "success", f"{version.upper()} 스크립트 생성 완료")
                    
                    # 음성 생성
                    self.update_progress(f"{version}_audio", "processing", f"{version.upper()} 음성 생성 중...")
                    version_audio = generate_audio_with_fallback(
                        version_content,
                        st.session_state.tts_engine,
                        st.session_state.tts_voice
                    )
                    results[f"{version}_audio"] = version_audio
                    self.update_progress(f"{version}_audio", "success" if version_audio else "error",
                                       f"{version.upper()} 음성 생성 완료" if version_audio else f"{version.upper()} 음성 생성 실패")
                else:
                    self.update_progress(version, "error", f"{version.upper()} 스크립트 생성 실패")
        
        return results
    
def test_database_connection():
    """데이터베이스 연결 테스트"""
    try:
        db = EnhancedDatabase()
        
        # 테스트 데이터 삽입
        test_id = db.create_script_project(
            title="테스트 스크립트",
            original_content="This is a test script.",
            korean_translation="이것은 테스트 스크립트입니다.",
            category="test",
            input_type="text", 
            input_data="test input"
        )
        
        # 확인
        project = db.get_script_project(test_id)
        if project['script']:
            st.success(f"✅ 데이터베이스 테스트 성공! (ID: {test_id})")
            
            # 테스트 데이터 삭제
            db.delete_script_project(test_id)
            st.info("🗑️ 테스트 데이터 정리 완료")
            return True
        else:
            st.error("❌ 데이터베이스 테스트 실패")
            return False
            
    except Exception as e:
        st.error(f"❌ 데이터베이스 테스트 오류: {str(e)}")
        return False

# Main App Functions
def settings_page():
    st.header("⚙️ 환경 설정")
    
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
    
    with st.expander("🔊 TTS 설정"):
        tts_manager = TTSManager()
        
        if not tts_manager.available_engines:
            st.error("❌ TTS 엔진이 설치되지 않았습니다.")
            st.code("pip install gtts pyttsx3", language="bash")
        else:
            st.success(f"✅ 사용 가능: {', '.join(tts_manager.available_engines)}")
            
            col1, col2 = st.columns(2)
            
            with col1:
                engine_options = ['auto (자동)'] + tts_manager.available_engines
                selected_engine = st.selectbox("TTS 엔진", engine_options)
                st.session_state.tts_engine = 'auto' if selected_engine == 'auto (자동)' else selected_engine
            
            with col2:
                if st.session_state.tts_engine in ['auto', 'gTTS']:
                    voice_options = {
                        '영어 (미국)': 'en',
                        '영어 (영국)': 'en-uk', 
                        '영어 (호주)': 'en-au',
                        '한국어': 'ko'
                    }
                    selected_voice_name = st.selectbox("음성 언어", list(voice_options.keys()))
                    st.session_state.tts_voice = voice_options[selected_voice_name]
                else:
                    st.info("시스템 기본 음성을 사용합니다")
                    st.session_state.tts_voice = None
    
    with st.expander("☁️ Google Drive 설정"):
        st.info("Google Drive에 자동 백업하려면 서비스 계정 JSON 파일이 필요합니다.")
        
        uploaded_file = st.file_uploader(
            "Service Account JSON 파일 업로드",
            type=['json'],
            help="Google Cloud Console에서 생성한 서비스 계정 키 파일"
        )
        
        if uploaded_file:
            # 임시 파일로 저장
            with tempfile.NamedTemporaryFile(mode='w+b', suffix='.json', delete=False) as tmp_file:
                tmp_file.write(uploaded_file.getvalue())
                tmp_file_path = tmp_file.name
            
            # Google Drive Manager 초기화 테스트
            gdrive_manager = EnhancedGoogleDriveManager(tmp_file_path)
            if gdrive_manager.service:
                st.success("✅ Google Drive 연동 성공!")
                st.session_state.google_drive_enabled = True
                st.session_state.google_credentials = tmp_file_path
                
                # 폴더 구조 표시
                st.info("저장 위치: My Drive > GDRIVE_API > MyTalk")
            else:
                st.error("❌ Google Drive 연동 실패")
                if os.path.exists(tmp_file_path):
                    os.unlink(tmp_file_path)
    with st.expander("🔧 데이터베이스 테스트"):
        if st.button("데이터베이스 연결 테스트"):
            test_database_connection()
        
        if st.button("현재 저장된 스크립트 확인"):
            db = EnhancedDatabase()
            scripts = db.get_all_scripts()
            if scripts:
                st.write(f"총 {len(scripts)}개의 스크립트가 저장되어 있습니다:")
                for script in scripts[:5]:  # 최근 5개만 표시
                    st.write(f"- {script[1]} ({script[4]}) - {script[7][:10]}")
            else:
                st.write("저장된 스크립트가 없습니다.")


def script_creation_page():
    st.header("✍️ 영어 스크립트 생성")

    # 임시 백업 복구 섹션 추가
    with st.expander("🔄 임시 백업 복구"):
        recent_backups = get_recent_backups()
        if recent_backups:
            st.write("최근 임시 저장된 작업:")
            for backup in recent_backups:
                col1, col2, col3 = st.columns([2, 2, 1])
                with col1:
                    st.write(f"**{backup['title']}**")
                with col2:
                    st.write(f"{backup['timestamp'][:19]}")
                with col3:
                    if st.button("복구", key=f"restore_{backup['id']}"):
                        # 복구 액션을 세션 상태에 저장
                        st.session_state.restore_action = backup['id']

        # 복구 액션 처리 (버튼 클릭 후 실행)
        if hasattr(st.session_state, 'restore_action') and st.session_state.restore_action:
            restored_data = load_temp_backup(st.session_state.restore_action)
            if restored_data:
                # 복구된 데이터를 세션 상태에 저장
                st.session_state.current_project = restored_data['results']
                st.session_state.restored_input_content = restored_data.get('input_content', '')
                st.session_state.restored_input_method = restored_data.get('input_method', 'text')
                st.session_state.restored_category = restored_data.get('category', 'general')
                st.session_state.current_backup_id = st.session_state.restore_action  # 백업 ID 저장
                
                st.success("✅ 백업 복구 완료!")
                
                # 복구 액션 초기화
                del st.session_state.restore_action
                
                # 복구된 내용 즉시 표시
                results = st.session_state.current_project
                if results:
                    st.markdown("### 📋 복구된 콘텐츠")
                    display_results(results, ['original', 'ted', 'podcast', 'daily'])
                    
                    # 복구된 콘텐츠에 대한 저장 버튼 추가
                    st.markdown("---")
                    st.markdown("### 💾 복구된 콘텐츠 저장")
                    
                    col1, col2 = st.columns([1, 1])
                    
                    with col1:
                        if st.button("💾 로컬 저장", type="secondary", key="save_restored_local"):
                            st.session_state.save_action = "restored_local"
                            
                    with col2:
                        if st.session_state.google_drive_enabled and st.button("☁️ Google Drive 저장", type="primary", key="save_restored_gdrive"):
                            st.session_state.save_action = "restored_gdrive"
            else:
                st.error("❌ 백업 복구 실패")
                del st.session_state.restore_action

        # 복구된 콘텐츠가 이미 있는 경우 저장 버튼 표시
        elif hasattr(st.session_state, 'current_project') and st.session_state.current_project and hasattr(st.session_state, 'current_backup_id'):
            results = st.session_state.current_project
            st.markdown("### 📋 복구된 콘텐츠")
            display_results(results, ['original', 'ted', 'podcast', 'daily'])
            
            st.markdown("---")
            st.markdown("### 💾 복구된 콘텐츠 저장")
            
            col1, col2 = st.columns([1, 1])
            
            with col1:
                if st.button("💾 로컬 저장", type="secondary", key="save_restored_local"):
                    st.session_state.save_action = "restored_local"
                    
            with col2:
                if st.session_state.google_drive_enabled and st.button("☁️ Google Drive 저장", type="primary", key="save_restored_gdrive"):
                    st.session_state.save_action = "restored_gdrive"
        else:
            st.info("저장된 임시 백업이 없습니다.")
    
    # 입력 방법 선택
    col1, col2, col3 = st.columns(3)
    with col1:
        input_method = st.radio(
            "입력 방법",
            ["텍스트", "이미지", "파일"],
            help="원하는 입력 방법을 선택하세요"
        )
    
    with col2:
        category = st.selectbox(
            "카테고리",
            ["일반", "비즈니스", "여행", "교육", "건강", "기술", "문화", "스포츠"]
        )
    
    with col3:
        st.markdown("### 생성할 버전 선택")
        versions = {
            "원본 스크립트": "original",
            "TED 3분 말하기": "ted", 
            "팟캐스트 대화": "podcast",
            "일상 대화": "daily"
        }
        
        selected_versions = []
        selected_versions.append("original")  # 원본은 필수
        
        for display_name, version_key in list(versions.items())[1:]:  # 원본 제외
            if st.checkbox(display_name, value=True):
                selected_versions.append(version_key)
    
    # 입력 인터페이스
    input_content = None
    image = None
    
    if input_method == "텍스트":
        input_content = st.text_area(
            "내용을 입력하세요",
            placeholder="예: 'AI의 미래', '커피 주문하기', 'Yesterday I went to the park...'",
            height=150
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
    
    else:  # 파일
        uploaded_file = st.file_uploader(
            "텍스트 파일 업로드",
            type=['txt', 'md'],
            help="텍스트 파일의 내용을 기반으로 스크립트를 생성합니다"
        )
        if uploaded_file:
            input_content = uploaded_file.read().decode('utf-8')
            st.text_area("파일 내용 미리보기", input_content[:500] + "...", height=100, disabled=True)
    
    # 생성 버튼
    if st.button("🚀 스크립트 생성하기", type="primary", key="generate_script"):
        if not st.session_state.api_key:
            st.error("먼저 설정에서 API Key를 입력해주세요!")
            return
        
        if not input_content:
            st.error("내용을 입력해주세요!")
            return
        
        # 진행상황 표시 컨테이너
        progress_container = st.empty()
        
        # 진행상황 업데이트 콜백
        def update_progress_ui(step, status, message):
            st.session_state.generation_progress[step] = {'status': status, 'message': message}
            
            with progress_container.container():
                st.markdown("### 📊 생성 진행상황")
                
                progress_steps = [
                    ("original", "영어 스크립트"),
                    ("translation", "한국어 번역"),
                    ("original_audio", "원본 음성"),
                ]
                
                # 선택된 버전들에 대한 단계 추가
                for version in selected_versions:
                    if version != 'original':
                        progress_steps.extend([
                            (version, f"{version.upper()} 스크립트"),
                            (f"{version}_audio", f"{version.upper()} 음성")
                        ])
                
                cols = st.columns(len(progress_steps))
                
                for i, (step_key, step_name) in enumerate(progress_steps):
                    with cols[i % len(cols)]:
                        if i >= len(cols):
                            st.write("")  # 다음 줄로
                        
                        progress_info = st.session_state.generation_progress.get(step_key, {'status': 'waiting', 'message': ''})
                        
                        if progress_info['status'] == 'success':
                            st.markdown(f'<div class="status-badge status-success">✅ {step_name}</div>', unsafe_allow_html=True)
                        elif progress_info['status'] == 'processing':
                            st.markdown(f'<div class="status-badge status-processing">⏳ {step_name}</div>', unsafe_allow_html=True)
                        elif progress_info['status'] == 'error':
                            st.markdown(f'<div class="status-badge status-error">❌ {step_name}</div>', unsafe_allow_html=True)
                        else:
                            st.markdown(f'<div class="status-badge">⏸️ {step_name}</div>', unsafe_allow_html=True)
        
        # 초기화
        st.session_state.generation_progress = {}
        
        # 생성 파이프라인 실행
        llm_provider = EnhancedLLMProvider(
            st.session_state.api_provider,
            st.session_state.api_key,
            st.session_state.model
        )
        
        tts_manager = TTSManager()
        
        gdrive_manager = None
        if st.session_state.google_drive_enabled and st.session_state.google_credentials:
            gdrive_manager = EnhancedGoogleDriveManager(st.session_state.google_credentials)
        
        pipeline = ContentGenerationPipeline(llm_provider, tts_manager, gdrive_manager)
        pipeline.set_progress_callback(update_progress_ui)
        
        # 생성 실행
        results = pipeline.generate_all_content(
            input_content=input_content,
            input_type=input_method.lower(),
            category=category,
            image=image,
            selected_versions=selected_versions
        )
        
        if results:
            # 즉시 임시 저장
            backup_id = save_to_temp_backup(results, input_content, input_method, category)
            if backup_id:
                st.info(f"💾 임시 저장 완료 (ID: {backup_id})")
            
            st.session_state.current_project = results
            
            # 결과 표시
            st.success("🎉 모든 콘텐츠 생성이 완료되었습니다!")
            display_results(results, selected_versions)
            
            # 저장 버튼 (key 추가로 중복 방지)
            col1, col2 = st.columns([1, 1])

            if results:
        # 즉시 임시 저장
        backup_id = save_to_temp_backup(results, input_content, input_method, category)
        if backup_id:
            st.info(f"💾 임시 저장 완료 (ID: {backup_id})")
        
        st.session_state.current_project = results
        
        # 결과 표시
        st.success("🎉 모든 콘텐츠 생성이 완료되었습니다!")
        display_results(results, selected_versions)
        
        # 즉시 실행 방식 저장 버튼
        col1, col2 = st.columns([1, 1])
        
        with col1:
            if st.button("💾 로컬 저장", type="secondary", key="save_local_immediate"):
                # 즉시 실행 - 별도 함수 호출 없음
                save_success = False
                try:
                    with st.spinner("로컬 저장 중..."):
                        # 직접 데이터베이스에 저장
                        db = EnhancedDatabase()
                        
                        # 1. 메인 스크립트 저장
                        script_id = db.create_script_project(
                            title=results.get('title', f"Script_{datetime.now().strftime('%Y%m%d_%H%M%S')}"),
                            original_content=results.get('original_script', ''),
                            korean_translation=results.get('korean_translation', ''),
                            category=category,
                            input_type=input_method,
                            input_data=input_content
                        )
                        
                        st.write(f"✅ 스크립트 ID {script_id} 생성됨")
                        
                        # 2. 각 버전별 저장
                        version_count = 0
                        for version_type in ['ted', 'podcast', 'daily']:
                            script_key = f"{version_type}_script"
                            audio_key = f"{version_type}_audio"
                            
                            if script_key in results and results[script_key]:
                                version_id = db.add_practice_version(
                                    script_id=script_id,
                                    version_type=version_type,
                                    content=results[script_key],
                                    audio_path=results.get(audio_key, '')
                                )
                                version_count += 1
                                st.write(f"✅ {version_type} 버전 저장됨 (ID: {version_id})")
                        
                        # 3. 저장 확인
                        verification = db.get_script_project(script_id)
                        if verification['script'] and verification['script'][1]:  # title 확인
                            save_success = True
                            st.success(f"🎉 저장 완료! 메인 스크립트 + {version_count}개 버전")
                            st.balloons()
                            
                            # 백업 정리
                            if backup_id:
                                cleanup_temp_backup(backup_id)
                                st.info("🗑️ 임시 백업 정리됨")
                            
                            # 다른 탭 갱신을 위한 트리거
                            st.session_state.refresh_tabs = datetime.now().isoformat()
                            
                        else:
                            raise Exception("저장 확인 실패")
                            
                except Exception as e:
                    st.error(f"❌ 저장 실패: {str(e)}")
                    st.code(f"오류 상세: {str(e)}")
                    save_success = False
                
                if save_success:
                    st.rerun()  # 성공시에만 리런

            with col2:
                if st.session_state.google_drive_enabled and st.button("☁️ Google Drive 저장", type="primary", key="save_gdrive_main"):
                    st.session_state.save_action = "gdrive"
                    st.session_state.save_data = {
                        'results': results,
                        'gdrive_manager': EnhancedGoogleDriveManager(st.session_state.google_credentials) if st.session_state.google_credentials else None
                    }

            # 저장 액션 처리 (버튼 클릭 후 실행)
            if hasattr(st.session_state, 'save_action') and st.session_state.save_action:
                if st.session_state.save_action == "local":
                    with st.spinner("로컬 저장 중..."):
                        data = st.session_state.save_data
                        success = save_to_local_db_safe(
                            data['results'], 
                            data['input_content'], 
                            data['input_method'], 
                            data['category']
                        )
                        if success:
                            st.success("✅ 로컬 저장 완료!")
                            st.balloons()  # 시각적 피드백
                            
                            # 저장 후 다른 탭들이 새로고침되도록 트리거
                            st.session_state.last_save_time = datetime.now().isoformat()
                            
                            if backup_id:
                                cleanup_temp_backup(backup_id)
                                
                            # 저장 완료 메시지와 함께 안내
                            st.info("💡 '연습하기' 또는 '내 스크립트' 탭에서 저장된 내용을 확인하세요!")
                            
                        else:
                            st.error("❌ 로컬 저장 실패 - 임시 백업은 유지됩니다.")
                
                elif st.session_state.save_action == "gdrive":
                    with st.spinner("Google Drive 저장 중..."):
                        data = st.session_state.save_data
                        success = save_to_google_drive_safe(data['results'], data['gdrive_manager'])
                        if success and backup_id:
                            cleanup_temp_backup(backup_id)
                
                # 복구된 콘텐츠 저장 처리 추가
                elif st.session_state.save_action == "restored_local":
                    if hasattr(st.session_state, 'current_project') and st.session_state.current_project:
                        with st.spinner("복구된 콘텐츠 로컬 저장 중..."):
                            success = save_to_local_db_safe(
                                st.session_state.current_project,
                                st.session_state.get('restored_input_content', ''),
                                st.session_state.get('restored_input_method', 'text'),
                                st.session_state.get('restored_category', 'general')
                            )
                            if success:
                                st.success("✅ 복구된 콘텐츠 로컬 저장 완료!")
                                # 저장 성공 시 백업 정리
                                if hasattr(st.session_state, 'current_backup_id'):
                                    cleanup_temp_backup(st.session_state.current_backup_id)
                                    del st.session_state.current_backup_id
                                    del st.session_state.current_project
                                    del st.session_state.restored_input_content
                                    del st.session_state.restored_input_method  
                                    del st.session_state.restored_category
                                    st.info("🗑️ 임시 백업이 정리되었습니다.")
                            else:
                                st.error("❌ 복구된 콘텐츠 로컬 저장 실패")
                
                elif st.session_state.save_action == "restored_gdrive":
                    if hasattr(st.session_state, 'current_project') and st.session_state.current_project:
                        with st.spinner("복구된 콘텐츠 Google Drive 저장 중..."):
                            gdrive_manager = None
                            if st.session_state.google_credentials:
                                gdrive_manager = EnhancedGoogleDriveManager(st.session_state.google_credentials)
                            
                            success = save_to_google_drive_safe(st.session_state.current_project, gdrive_manager)
                            if success:
                                st.success("✅ 복구된 콘텐츠 Google Drive 저장 완료!")
                                # 저장 성공 시 백업 정리
                                if hasattr(st.session_state, 'current_backup_id'):
                                    cleanup_temp_backup(st.session_state.current_backup_id)
                                    del st.session_state.current_backup_id
                                    del st.session_state.current_project
                                    del st.session_state.restored_input_content
                                    del st.session_state.restored_input_method
                                    del st.session_state.restored_category
                                    st.info("🗑️ 임시 백업이 정리되었습니다.")
                            else:
                                st.error("❌ 복구된 콘텐츠 Google Drive 저장 실패")
                
                # 저장 액션 초기화
                if 'save_action' in st.session_state:
                    del st.session_state.save_action
                if 'save_data' in st.session_state:
                    del st.session_state.save_data

        else:
            st.error("❌ 콘텐츠 생성에 실패했습니다.")


def display_results(results, selected_versions):
    """생성 결과 표시 (세션 상태 기반)"""
    if not results:
        return
        
    st.markdown("---")
    st.markdown("## 📋 생성 결과")
    
    # 결과를 세션 상태에 보존
    st.session_state.current_project = results
    
    # 탭으로 각 버전 표시
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
                # 영어 스크립트
                st.markdown("### 🇺🇸 English Script")
                st.markdown(f'<div class="script-container"><div class="script-text">{results[script_key]}</div></div>', 
                          unsafe_allow_html=True)
                
                # 음성 재생 (세션 상태 기반으로 유지)
                if audio_key in results and results[audio_key]:
                    audio_path = results[audio_key]
                    if os.path.exists(audio_path):
                        st.audio(audio_path, format='audio/mp3')
                    else:
                        st.warning("오디오 파일을 찾을 수 없습니다.")
                        st.markdown(get_browser_tts_script(results[script_key]), unsafe_allow_html=True)
                else:
                    # 브라우저 TTS 폴백
                    st.markdown(get_browser_tts_script(results[script_key]), unsafe_allow_html=True)
                
                # 한국어 번역 (원본에만 표시)
                if version == 'original' and 'korean_translation' in results:
                    st.markdown("### 🇰🇷 한국어 번역")
                    st.markdown(f'<div class="script-container"><div class="translation-text">{results["korean_translation"]}</div></div>', 
                              unsafe_allow_html=True)


                    
def save_to_local_db_safe(results, input_content, input_method, category):
    """안전한 로컬 저장 (디버깅 정보 포함)"""
    try:
        st.write("🔍 저장 시작...")
        st.write(f"제목: {results.get('title', 'N/A')}")
        st.write(f"카테고리: {category}")
        
        db = EnhancedDatabase()
        
        # 메인 스크립트 저장
        script_id = db.create_script_project(
            title=results.get('title', 'Untitled'),
            original_content=results.get('original_script', ''),
            korean_translation=results.get('korean_translation', ''),
            category=category,
            input_type=input_method,
            input_data=input_content
        )
        
        st.write(f"✅ 메인 스크립트 저장됨 (ID: {script_id})")
        
        # 각 버전별 저장
        version_types = ['ted', 'podcast', 'daily']
        saved_versions = []
        
        for version_type in version_types:
            script_key = f"{version_type}_script"
            audio_key = f"{version_type}_audio"
            
            if script_key in results and results[script_key]:
                version_id = db.add_practice_version(
                    script_id=script_id,
                    version_type=version_type,
                    content=results[script_key],
                    audio_path=results.get(audio_key)
                )
                saved_versions.append(f"{version_type}(ID:{version_id})")
        
        if saved_versions:
            st.write(f"✅ 연습 버전 저장됨: {', '.join(saved_versions)}")
        
        # 저장 확인
        saved_script = db.get_script_project(script_id)
        if saved_script['script']:
            st.write(f"✅ 저장 확인 완료: {saved_script['script'][1]}")
            return True
        else:
            st.error("❌ 저장 확인 실패")
            return False
        
    except Exception as e:
        st.error(f"❌ 로컬 저장 실패: {str(e)}")
        import traceback
        st.code(traceback.format_exc())
        return False

def save_to_google_drive_safe(results, gdrive_manager):
    """안전한 Google Drive 저장"""
    if not gdrive_manager or not gdrive_manager.service:
        st.error("Google Drive가 설정되지 않았습니다.")
        return False
    
    try:
        success = gdrive_manager.save_project_to_drive(results)
        if success:
            st.success("✅ Google Drive 저장 완료!")
        else:
            st.error("❌ Google Drive 저장 실패")
        return success
        
    except Exception as e:
        st.error(f"Google Drive 저장 실패: {str(e)}")
        return False

def cleanup_temp_backup(backup_id):
    """임시 백업 정리 (개선된 버전)"""
    try:
        json_path = Path(f"temp_backups/backup_{backup_id}.json")
        pickle_path = Path(f"temp_backups/backup_{backup_id}.pkl")
        
        deleted_files = []
        
        if json_path.exists():
            json_path.unlink()
            deleted_files.append("JSON")
            
        if pickle_path.exists():
            pickle_path.unlink()
            deleted_files.append("PKL")
        
        if deleted_files:
            st.info(f"🗑️ 백업 파일 정리 완료: {', '.join(deleted_files)}")
        
        return True
        
    except Exception as e:
        st.warning(f"백업 정리 실패: {str(e)}")
        return False

def practice_page():
    st.header("🎯 연습하기")
    
    # 저장 시간 기반 갱신 체크
    if hasattr(st.session_state, 'last_save_time'):
        st.success(f"🆕 최근 저장: {st.session_state.last_save_time[:19]}")
    
    db = EnhancedDatabase()
    scripts = db.get_all_scripts()
    
    if not scripts:
        st.info("저장된 스크립트가 없습니다. 먼저 스크립트를 생성해주세요.")
        
        # 디버깅: 데이터베이스 상태 확인
        with st.expander("🔍 데이터베이스 디버깅"):
            try:
                conn = sqlite3.connect(db.db_path)
                c = conn.cursor()
                c.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = c.fetchall()
                st.write(f"테이블 목록: {[t[0] for t in tables]}")
                
                c.execute("SELECT COUNT(*) FROM scripts")
                script_count = c.fetchone()[0]
                st.write(f"스크립트 개수: {script_count}")
                
                if script_count > 0:
                    c.execute("SELECT id, title, category, created_at FROM scripts LIMIT 5")
                    recent_scripts = c.fetchall()
                    st.write("최근 스크립트:")
                    for script in recent_scripts:
                        st.write(f"- ID:{script[0]}, 제목:{script[1]}, 카테고리:{script[2]}, 생성:{script[3]}")
                
                conn.close()
            except Exception as e:
                st.error(f"데이터베이스 확인 오류: {e}")
        
        return
    
    # 스크립트 선택
    st.markdown("### 📖 연습할 스크립트 선택")
    
    script_options = {f"{script[1]} ({script[4]}) - {script[7][:10]}": script[0] 
                     for script in scripts}
    
    selected_script_name = st.selectbox(
        "스크립트 선택",
        list(script_options.keys()),
        help="연습하고 싶은 스크립트를 선택하세요"
    )
    
    if selected_script_name:
        script_id = script_options[selected_script_name]
        project_data = db.get_script_project(script_id)
        
        if project_data['script']:
            script_info = project_data['script']
            versions = project_data['versions']
            
            # 스크립트 정보 표시
            st.markdown(f"**제목**: {script_info[1]}")
            st.markdown(f"**카테고리**: {script_info[4]}")
            st.markdown(f"**생성일**: {script_info[7][:10]}")
            
            # 원본 + 연습 버전들 탭으로 표시
            available_versions = [('original', '원본 스크립트', script_info[2])]
            
            # 연습 버전들 추가
            version_names = {
                'ted': 'TED 3분 말하기',
                'podcast': '팟캐스트 대화', 
                'daily': '일상 대화'
            }
            
            for version in versions:
                version_type = version[2]
                if version_type in version_names:
                    available_versions.append((version_type, version_names[version_type], version[3]))
            
            # 탭 생성
            tab_names = [v[1] for v in available_versions]
            tabs = st.tabs(tab_names)
            
            for i, (version_type, version_name, content) in enumerate(available_versions):
                with tabs[i]:
                    col1, col2 = st.columns([2, 1])
                    
                    with col1:
                        st.markdown(f"### 🇺🇸 {version_name}")
                        st.markdown(f'<div class="script-container"><div class="script-text">{content}</div></div>', 
                                  unsafe_allow_html=True)
                    
                    with col2:
                        st.markdown("### 🎧 음성 연습")
                        
                        # 음성 파일 찾기
                        audio_path = None
                        if version_type == 'original':
                            # 파일 테이블에서 찾기
                            for file_info in project_data['files']:
                                if file_info[2] == 'original_audio':
                                    audio_path = file_info[4]  # local_path
                                    break
                        else:
                            # practice_versions에서 찾기
                            for version in versions:
                                if version[2] == version_type:
                                    audio_path = version[4]  # audio_path
                                    break
                        
                        if audio_path and os.path.exists(audio_path):
                            st.audio(audio_path, format='audio/mp3')
                        else:
                            # TTS 생성 버튼
                            if st.button(f"🔊 음성 생성", key=f"tts_{version_type}_{script_id}"):
                                with st.spinner("음성 생성 중..."):
                                    new_audio = generate_audio_with_fallback(
                                        content,
                                        st.session_state.tts_engine,
                                        st.session_state.tts_voice
                                    )
                                    if new_audio:
                                        st.audio(new_audio)
                                        st.success("음성 생성 완료!")
                                    else:
                                        st.error("음성 생성 실패")
                            
                            # 브라우저 TTS 폴백
                            st.markdown("**또는 브라우저 TTS 사용:**")
                            st.markdown(get_browser_tts_script(content), unsafe_allow_html=True)
                        
                        # 연습 팁
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
                            else:  # original
                                st.markdown("""
                                - 명확한 발음 연습
                                - 문장별로 나누어 연습
                                - 녹음해서 비교하기
                                - 반복 학습으로 유창성 향상
                                """)
                    
                    # 한국어 번역 (원본에만 표시)
                    if version_type == 'original' and script_info[3]:
                        st.markdown("### 🇰🇷 한국어 번역")
                        st.markdown(f'<div class="script-container"><div class="translation-text">{script_info[3]}</div></div>', 
                                  unsafe_allow_html=True)

def my_scripts_page():
    st.header("📚 내 스크립트")
    
    db = EnhancedDatabase()
    
    # 검색 및 필터
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        search_query = st.text_input("🔍 검색", placeholder="제목 또는 내용 검색...")
    
    with col2:
        category_filter = st.selectbox(
            "카테고리",
            ["전체", "일반", "비즈니스", "여행", "교육", "건강", "기술", "문화", "스포츠"]
        )
    
    with col3:
        sort_order = st.selectbox("정렬", ["최신순", "제목순"])
    
    # 스크립트 조회
    if search_query:
        scripts = db.search_scripts(search_query)
    else:
        scripts = db.get_all_scripts()
    
    # 필터링
    if category_filter != "전체":
        scripts = [s for s in scripts if s[4] == category_filter]
    
    # 정렬
    if sort_order == "제목순":
        scripts.sort(key=lambda x: x[1])
    
    # 스크립트 표시
    if scripts:
        st.write(f"총 {len(scripts)}개의 스크립트")
        
        # 그리드 형태로 표시
        for i in range(0, len(scripts), 2):
            cols = st.columns(2)
            
            for j, col in enumerate(cols):
                if i + j < len(scripts):
                    script = scripts[i + j]
                    script_id, title, content, translation, category, input_type, input_data, created_at, _ = script
                    
                    with col:
                        with st.container():
                            st.markdown(f'<div class="version-card">', unsafe_allow_html=True)
                            
                            # 제목과 정보
                            st.markdown(f"### 📄 {title}")
                            st.markdown(f"**카테고리**: {category}")
                            st.markdown(f"**생성일**: {created_at[:10]}")
                            st.markdown(f"**입력방식**: {input_type}")
                            
                            # 내용 미리보기
                            preview = content[:100] + "..." if len(content) > 100 else content
                            st.markdown(f"**내용**: {preview}")
                            
                            # 버튼들
                            button_cols = st.columns(3)
                            
                            with button_cols[0]:
                                if st.button("📖 보기", key=f"view_{script_id}"):
                                    st.session_state[f"show_detail_{script_id}"] = True
                            
                            with button_cols[1]:
                                if st.button("🎯 연습", key=f"practice_{script_id}"):
                                    # 연습 페이지로 이동 (실제로는 상태 변경)
                                    st.info("연습하기 탭으로 이동해서 해당 스크립트를 선택하세요.")
                            
                            with button_cols[2]:
                                if st.button("🗑️ 삭제", key=f"delete_{script_id}"):
                                    if st.session_state.get(f"confirm_delete_{script_id}"):
                                        db.delete_script_project(script_id)
                                        st.success("삭제되었습니다!")
                                        st.rerun()
                                    else:
                                        st.session_state[f"confirm_delete_{script_id}"] = True
                                        st.warning("한 번 더 클릭하면 삭제됩니다.")
                            
                            st.markdown('</div>', unsafe_allow_html=True)
                            
                            # 상세 보기
                            if st.session_state.get(f"show_detail_{script_id}"):
                                with st.expander(f"📋 {title} 상세보기", expanded=True):
                                    project_data = db.get_script_project(script_id)
                                    
                                    # 원본 스크립트
                                    st.markdown("#### 🇺🇸 영어 스크립트")
                                    st.markdown(content)
                                    
                                    # 한국어 번역
                                    if translation:
                                        st.markdown("#### 🇰🇷 한국어 번역")
                                        st.markdown(translation)
                                    
                                    # 연습 버전들
                                    versions = project_data['versions']
                                    if versions:
                                        st.markdown("#### 📝 연습 버전들")
                                        
                                        version_names = {
                                            'ted': 'TED 3분 말하기',
                                            'podcast': '팟캐스트 대화',
                                            'daily': '일상 대화'
                                        }
                                        
                                        for version in versions:
                                            version_type = version[2]
                                            version_content = version[3]
                                            
                                            if version_type in version_names:
                                                st.markdown(f"**{version_names[version_type]}**")
                                                st.markdown(version_content[:200] + "..." if len(version_content) > 200 else version_content)
                                                st.markdown("---")
                                    
                                    # 닫기 버튼
                                    if st.button("닫기", key=f"close_{script_id}"):
                                        st.session_state[f"show_detail_{script_id}"] = False
                                        st.rerun()
    else:
        st.info("저장된 스크립트가 없습니다.")
        st.markdown("**스크립트 생성** 탭에서 새로운 스크립트를 만들어보세요! 🚀")


import pickle
import uuid

def save_to_temp_backup(results, input_content, input_method, category):
    """임시 백업 저장 (LLM 비용 절약용)"""
    try:
        backup_id = str(uuid.uuid4())[:8]
        backup_data = {
            'timestamp': datetime.now().isoformat(),
            'backup_id': backup_id,
            'results': results,
            'input_content': input_content,
            'input_method': input_method,
            'category': category
        }
        
        # 임시 폴더 생성
        temp_backup_dir = Path("temp_backups")
        temp_backup_dir.mkdir(exist_ok=True)
        
        # JSON과 pickle 두 형태로 저장 (안전성)
        json_path = temp_backup_dir / f"backup_{backup_id}.json"
        pickle_path = temp_backup_dir / f"backup_{backup_id}.pkl"
        
        # JSON 저장 (사람이 읽을 수 있음)
        with open(json_path, 'w', encoding='utf-8') as f:
            json_backup = backup_data.copy()
            # 오디오 파일 경로만 저장 (바이너리 데이터 제외)
            json.dump(json_backup, f, ensure_ascii=False, indent=2)
        
        # Pickle 저장 (완전한 객체)
        with open(pickle_path, 'wb') as f:
            pickle.dump(backup_data, f)
        
        return backup_id
    except Exception as e:
        st.error(f"임시 저장 실패: {str(e)}")
        return None

def load_temp_backup(backup_id):
    """임시 백업 로드 (개선된 버전)"""
    backup_data = None
    
    # Pickle 파일 시도 (완전한 데이터)
    try:
        pickle_path = Path(f"temp_backups/backup_{backup_id}.pkl")
        if pickle_path.exists():
            with open(pickle_path, 'rb') as f:
                backup_data = pickle.load(f)
                # 로드 후 유효성 검사
                if 'results' in backup_data and backup_data['results']:
                    return backup_data
    except Exception as e:
        st.warning(f"Pickle 로드 실패: {str(e)}")
    
    # JSON 파일 시도 (텍스트 데이터)
    try:
        json_path = Path(f"temp_backups/backup_{backup_id}.json")
        if json_path.exists():
            with open(json_path, 'r', encoding='utf-8') as f:
                backup_data = json.load(f)
                if 'results' in backup_data and backup_data['results']:
                    return backup_data
    except Exception as e:
        st.warning(f"JSON 로드 실패: {str(e)}")
    
    return None

def get_recent_backups(limit=5):
    """최근 백업 목록"""
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
                    'title': data.get('results', {}).get('title', 'Unknown')
                })
        except:
            continue
    
    # 시간순 정렬
    backups.sort(key=lambda x: x['timestamp'], reverse=True)
    return backups[:limit]





# Main App
def main():
    init_session_state()
    
    # 모바일 친화적 헤더
    st.markdown("""
    <div style='text-align: center; padding: 1rem; background: linear-gradient(90deg, #4CAF50, #45a049); border-radius: 10px; margin-bottom: 2rem;'>
        <h1 style='color: white; margin: 0;'>🎙️ MyTalk</h1>
        <p style='color: white; margin: 0; opacity: 0.9;'>나만의 영어 말하기 학습 앱</p>
    </div>
    """, unsafe_allow_html=True)
    
    # 네비게이션 탭
    tab1, tab2, tab3, tab4 = st.tabs(["✍️ 스크립트 작성", "🎯 연습하기", "📚 내 스크립트", "⚙️ 설정"])
    
    with tab1:
        script_creation_page()
    
    with tab2:
        practice_page()
    
    with tab3:
        my_scripts_page()
    
    with tab4:
        settings_page()
    
    # 푸터
    st.markdown("---")
    st.markdown("""
    <div style='text-align: center; color: #666; font-size: 0.8rem; margin-top: 2rem;'>
        <p>MyTalk v2.0 | Personal English Learning Assistant</p>
        <p>Copyright © 2025 Sunggeun Han (mysomang@gmail.com)</p>
        <p>Made with ❤️ using Streamlit | 원스톱 영어 학습 솔루션</p>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()