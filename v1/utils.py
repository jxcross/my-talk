"""
Utility functions for MyTalk app
유틸리티 함수 모음
"""

import os
import json
import hashlib
import shutil
from datetime import datetime, timedelta
from typing import Optional, Dict, List
import sqlite3
import streamlit as st

# Google Drive utilities
class GoogleDriveManager:
    """Google Drive 백업 관리"""
    
    def __init__(self, credentials_path: str = None):
        self.credentials_path = credentials_path
        self.service = None
        
        if credentials_path and os.path.exists(credentials_path):
            self.initialize_service()
    
    def initialize_service(self):
        """Google Drive 서비스 초기화"""
        try:
            from google.oauth2 import service_account
            from googleapiclient.discovery import build
            
            credentials = service_account.Credentials.from_service_account_file(
                self.credentials_path,
                scopes=['https://www.googleapis.com/auth/drive.file']
            )
            self.service = build('drive', 'v3', credentials=credentials)
            return True
        except Exception as e:
            print(f"Google Drive 초기화 실패: {e}")
            return False
    
    def create_folder(self, folder_name: str = "MyTalk_Backup"):
        """백업 폴더 생성"""
        if not self.service:
            return None
        
        try:
            # 폴더 존재 확인
            results = self.service.files().list(
                q=f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder'",
                fields="files(id, name)"
            ).execute()
            
            items = results.get('files', [])
            if items:
                return items[0]['id']
            
            # 새 폴더 생성
            file_metadata = {
                'name': folder_name,
                'mimeType': 'application/vnd.google-apps.folder'
            }
            folder = self.service.files().create(
                body=file_metadata,
                fields='id'
            ).execute()
            return folder.get('id')
        except Exception as e:
            print(f"폴더 생성 실패: {e}")
            return None
    
    def backup_database(self, db_path: str):
        """데이터베이스 백업"""
        if not self.service or not os.path.exists(db_path):
            return False
        
        try:
            folder_id = self.create_folder()
            if not folder_id:
                return False
            
            # 백업 파일명 (날짜 포함)
            backup_name = f"mytalk_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
            
            from googleapiclient.http import MediaFileUpload
            
            file_metadata = {
                'name': backup_name,
                'parents': [folder_id]
            }
            media = MediaFileUpload(db_path, mimetype='application/x-sqlite3')
            
            file = self.service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id'
            ).execute()
            
            return file.get('id') is not None
        except Exception as e:
            print(f"백업 실패: {e}")
            return False
    
    def restore_database(self, backup_id: str, restore_path: str):
        """데이터베이스 복원"""
        if not self.service:
            return False
        
        try:
            from googleapiclient.http import MediaIoBaseDownload
            import io
            
            request = self.service.files().get_media(fileId=backup_id)
            fh = io.BytesIO()
            downloader = MediaIoBaseDownload(fh, request)
            
            done = False
            while not done:
                status, done = downloader.next_chunk()
            
            # 파일 저장
            with open(restore_path, 'wb') as f:
                f.write(fh.getvalue())
            
            return True
        except Exception as e:
            print(f"복원 실패: {e}")
            return False
    
    def list_backups(self):
        """백업 목록 조회"""
        if not self.service:
            return []
        
        try:
            folder_id = self.create_folder()
            if not folder_id:
                return []
            
            results = self.service.files().list(
                q=f"'{folder_id}' in parents",
                orderBy="createdTime desc",
                fields="files(id, name, createdTime, size)"
            ).execute()
            
            return results.get('files', [])
        except Exception as e:
            print(f"백업 목록 조회 실패: {e}")
            return []

# Cache management
class CacheManager:
    """캐시 관리"""
    
    def __init__(self, cache_dir: str = "cache"):
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)
    
    def get_cache_key(self, text: str, voice: str) -> str:
        """캐시 키 생성"""
        content = f"{text}_{voice}"
        return hashlib.md5(content.encode()).hexdigest()
    
    def get_cached_audio(self, text: str, voice: str) -> Optional[str]:
        """캐시된 오디오 파일 경로 반환"""
        cache_key = self.get_cache_key(text, voice)
        cache_path = os.path.join(self.cache_dir, f"{cache_key}.mp3")
        
        if os.path.exists(cache_path):
            # 캐시 파일이 30일 이상 오래되었으면 삭제
            file_age = datetime.now() - datetime.fromtimestamp(os.path.getmtime(cache_path))
            if file_age.days > 30:
                os.remove(cache_path)
                return None
            return cache_path
        return None
    
    def save_to_cache(self, text: str, voice: str, audio_path: str) -> str:
        """오디오 파일을 캐시에 저장"""
        cache_key = self.get_cache_key(text, voice)
        cache_path = os.path.join(self.cache_dir, f"{cache_key}.mp3")
        
        if os.path.exists(audio_path):
            shutil.copy2(audio_path, cache_path)
            return cache_path
        return None
    
    def clear_cache(self, older_than_days: int = 7):
        """오래된 캐시 파일 삭제"""
        current_time = datetime.now()
        cleared_count = 0
        
        for filename in os.listdir(self.cache_dir):
            file_path = os.path.join(self.cache_dir, filename)
            file_age = current_time - datetime.fromtimestamp(os.path.getmtime(file_path))
            
            if file_age.days > older_than_days:
                os.remove(file_path)
                cleared_count += 1
        
        return cleared_count
    
    def get_cache_size(self) -> float:
        """캐시 폴더 크기 (MB)"""
        total_size = 0
        for filename in os.listdir(self.cache_dir):
            file_path = os.path.join(self.cache_dir, filename)
            total_size += os.path.getsize(file_path)
        return total_size / (1024 * 1024)  # Convert to MB

# Study statistics
class StudyStats:
    """학습 통계 관리"""
    
    def __init__(self, db_path: str = 'mytalk.db'):
        self.db_path = db_path
        self.init_stats_table()
    
    def init_stats_table(self):
        """통계 테이블 초기화"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS study_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date DATE NOT NULL,
                scripts_created INTEGER DEFAULT 0,
                scripts_practiced INTEGER DEFAULT 0,
                study_minutes INTEGER DEFAULT 0,
                UNIQUE(date)
            )
        ''')
        conn.commit()
        conn.close()
    
    def update_stat(self, stat_type: str, value: int = 1):
        """통계 업데이트"""
        today = datetime.now().date()
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # 오늘 날짜 레코드 확인
        c.execute('SELECT * FROM study_stats WHERE date = ?', (today,))
        record = c.fetchone()
        
        if record:
            # 기존 레코드 업데이트
            if stat_type == 'scripts_created':
                c.execute('UPDATE study_stats SET scripts_created = scripts_created + ? WHERE date = ?', 
                         (value, today))
            elif stat_type == 'scripts_practiced':
                c.execute('UPDATE study_stats SET scripts_practiced = scripts_practiced + ? WHERE date = ?', 
                         (value, today))
            elif stat_type == 'study_minutes':
                c.execute('UPDATE study_stats SET study_minutes = study_minutes + ? WHERE date = ?', 
                         (value, today))
        else:
            # 새 레코드 생성
            if stat_type == 'scripts_created':
                c.execute('INSERT INTO study_stats (date, scripts_created) VALUES (?, ?)', 
                         (today, value))
            elif stat_type == 'scripts_practiced':
                c.execute('INSERT INTO study_stats (date, scripts_practiced) VALUES (?, ?)', 
                         (today, value))
            elif stat_type == 'study_minutes':
                c.execute('INSERT INTO study_stats (date, study_minutes) VALUES (?, ?)', 
                         (today, value))
        
        conn.commit()
        conn.close()
    
    def get_weekly_stats(self) -> Dict:
        """주간 통계 조회"""
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=7)
        
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('''
            SELECT 
                SUM(scripts_created) as total_created,
                SUM(scripts_practiced) as total_practiced,
                SUM(study_minutes) as total_minutes
            FROM study_stats
            WHERE date BETWEEN ? AND ?
        ''', (start_date, end_date))
        
        result = c.fetchone()
        conn.close()
        
        return {
            'total_created': result[0] or 0,
            'total_practiced': result[1] or 0,
            'total_minutes': result[2] or 0,
            'daily_average': (result[2] or 0) / 7
        }
    
    def get_monthly_stats(self) -> Dict:
        """월간 통계 조회"""
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=30)
        
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('''
            SELECT 
                SUM(scripts_created) as total_created,
                SUM(scripts_practiced) as total_practiced,
                SUM(study_minutes) as total_minutes,
                COUNT(DISTINCT date) as study_days
            FROM study_stats
            WHERE date BETWEEN ? AND ?
        ''', (start_date, end_date))
        
        result = c.fetchone()
        conn.close()
        
        return {
            'total_created': result[0] or 0,
            'total_practiced': result[1] or 0,
            'total_minutes': result[2] or 0,
            'study_days': result[3] or 0
        }

# Export functions
class ExportManager:
    """내보내기 관리"""
    
    @staticmethod
    def export_to_pdf(scripts: List, output_path: str = "mytalk_scripts.pdf"):
        """스크립트를 PDF로 내보내기"""
        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.lib.styles import getSampleStyleSheet
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
            from reportlab.lib.units import inch
            
            doc = SimpleDocTemplate(output_path, pagesize=letter)
            styles = getSampleStyleSheet()
            story = []
            
            for script in scripts:
                # Title
                story.append(Paragraph(script[1], styles['Title']))
                story.append(Spacer(1, 0.2*inch))
                
                # Content
                story.append(Paragraph(script[2], styles['BodyText']))
                story.append(Spacer(1, 0.2*inch))
                
                # Translation
                if script[3]:
                    story.append(Paragraph("Translation:", styles['Heading2']))
                    story.append(Paragraph(script[3], styles['BodyText']))
                
                story.append(PageBreak())
            
            doc.build(story)
            return True
        except ImportError:
            st.error("PDF 내보내기를 위해 reportlab 패키지를 설치해주세요: pip install reportlab")
            return False
        except Exception as e:
            st.error(f"PDF 내보내기 실패: {e}")
            return False
    
    @staticmethod
    def export_to_json(scripts: List, output_path: str = "mytalk_scripts.json"):
        """스크립트를 JSON으로 내보내기"""
        try:
            export_data = []
            for script in scripts:
                export_data.append({
                    'id': script[0],
                    'title': script[1],
                    'content': script[2],
                    'translation': script[3],
                    'category': script[4],
                    'created_at': script[6]
                })
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, ensure_ascii=False, indent=2)
            
            return True
        except Exception as e:
            st.error(f"JSON 내보내기 실패: {e}")
            return False

# Prompt templates for better results
class PromptTemplates:
    """향상된 프롬프트 템플릿"""
    
    @staticmethod
    def business_english(topic: str, level: str = "intermediate") -> str:
        return f"""
        Create a business English script about: {topic}
        
        Requirements:
        - Level: {level}
        - Include professional vocabulary and phrases
        - Add common business idioms
        - Structure: Introduction, Main Points (2-3), Conclusion
        - Length: 250-300 words
        
        Format:
        Title: [Professional title]
        
        Script:
        [Natural business conversation or presentation]
        
        Key Business Phrases:
        • [5 essential phrases with explanations]
        
        Vocabulary Notes:
        • [5 important business terms with definitions]
        """
    
    @staticmethod
    def travel_english(situation: str) -> str:
        return f"""
        Create a practical travel English dialogue for: {situation}
        
        Requirements:
        - Real-world travel scenario
        - Include polite expressions
        - Add cultural tips if relevant
        - Natural conversation flow
        
        Format:
        Title: {situation}
        
        Dialogue:
        Traveler: [Natural opening]
        Local/Staff: [Helpful response]
        [Continue realistic exchange]
        
        Useful Phrases:
        • [5 must-know phrases for this situation]
        
        Cultural Tip:
        [Brief relevant cultural note]
        """
    
    @staticmethod
    def academic_english(topic: str, purpose: str = "presentation") -> str:
        return f"""
        Create an academic English script about: {topic}
        Purpose: {purpose}
        
        Requirements:
        - Formal academic language
        - Clear thesis statement
        - Evidence-based arguments
        - Academic vocabulary
        - Proper transitions
        
        Structure:
        1. Introduction with thesis
        2. Main arguments with supporting evidence
        3. Counter-arguments (if applicable)
        4. Conclusion with implications
        
        Length: 350-400 words
        
        Include:
        - Academic phrases for {purpose}
        - Field-specific terminology
        - Citation language examples
        """

# Mobile optimization helpers
def mobile_friendly_layout():
    """모바일 친화적 레이아웃 설정"""
    st.markdown("""
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        /* PWA 설정 */
        @media (max-width: 768px) {
            .stApp {
                padding: 0.5rem;
            }
            .stButton > button {
                min-height: 44px;
                font-size: 16px;
            }
            .stTextInput > div > div > input {
                font-size: 16px;
            }
            .stTextArea > div > div > textarea {
                font-size: 16px;
            }
        }
        
        /* iOS 안전 영역 */
        @supports (padding: max(0px)) {
            .stApp {
                padding-left: max(0.5rem, env(safe-area-inset-left));
                padding-right: max(0.5rem, env(safe-area-inset-right));
                padding-bottom: max(0.5rem, env(safe-area-inset-bottom));
            }
        }
        
        /* 다크 모드 지원 */
        @media (prefers-color-scheme: dark) {
            .stApp {
                background-color: #1E1E1E;
            }
        }
    </style>
    """, unsafe_allow_html=True)

# Session management
def save_session_state():
    """세션 상태 저장"""
    session_data = {
        'api_provider': st.session_state.get('api_provider', ''),
        'api_key': st.session_state.get('api_key', ''),
        'model': st.session_state.get('model', ''),
        'tts_voice': st.session_state.get('tts_voice', ''),
        'timestamp': datetime.now().isoformat()
    }
    
    # 민감한 정보는 암호화 (선택사항)
    with open('.session_cache', 'w') as f:
        json.dump(session_data, f)

def load_session_state():
    """세션 상태 복원"""
    if os.path.exists('.session_cache'):
        try:
            with open('.session_cache', 'r') as f:
                session_data = json.load(f)
            
            # 24시간 이내 세션만 복원
            saved_time = datetime.fromisoformat(session_data['timestamp'])
            if datetime.now() - saved_time < timedelta(hours=24):
                for key, value in session_data.items():
                    if key != 'timestamp':
                        st.session_state[key] = value
                return True
        except:
            pass
    return False