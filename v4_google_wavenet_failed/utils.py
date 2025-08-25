"""
Enhanced Utility functions for MyTalk app
유틸리티 함수 모음 - 개선된 버전
"""

import os
import json
import hashlib
import shutil
import tempfile
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple, Any
import sqlite3
import streamlit as st
import zipfile
from pathlib import Path

# Google Drive utilities
class EnhancedGoogleDriveManager:
    """향상된 Google Drive 백업 관리"""
    
    def __init__(self, credentials_path: Optional[str] = None):
        self.credentials_path = credentials_path
        self.service = None
        self.base_folder_id = None
        self.folder_cache = {}  # 폴더 ID 캐시
        
        if credentials_path and os.path.exists(credentials_path):
            self.initialize_service()
    
    def initialize_service(self) -> bool:
        """Google Drive 서비스 초기화"""
        try:
            from google.oauth2 import service_account
            from googleapiclient.discovery import build
            
            credentials = service_account.Credentials.from_service_account_file(
                self.credentials_path,
                scopes=[
                    'https://www.googleapis.com/auth/drive.file',
                    'https://www.googleapis.com/auth/drive.metadata'
                ]
            )
            self.service = build('drive', 'v3', credentials=credentials)
            
            # 기본 폴더 구조 확인
            self.base_folder_id = self.ensure_folder_structure()
            
            return True
        except Exception as e:
            st.error(f"Google Drive 초기화 실패: {e}")
            return False
    
    def ensure_folder_structure(self) -> Optional[str]:
        """MyTalk 폴더 구조 생성 및 확인"""
        try:
            # GDRIVE_API 폴더
            gdrive_api_id = self.get_or_create_folder("GDRIVE_API")
            if not gdrive_api_id:
                return None
            
            # MyTalk 폴더
            mytalk_id = self.get_or_create_folder("MyTalk", gdrive_api_id)
            return mytalk_id
            
        except Exception as e:
            st.error(f"폴더 구조 생성 실패: {e}")
            return None
    
    def get_or_create_folder(self, folder_name: str, parent_id: Optional[str] = None) -> Optional[str]:
        """폴더 조회 또는 생성"""
        try:
            # 캐시 확인
            cache_key = f"{folder_name}_{parent_id or 'root'}"
            if cache_key in self.folder_cache:
                return self.folder_cache[cache_key]
            
            # 기존 폴더 검색
            query = f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
            if parent_id:
                query += f" and '{parent_id}' in parents"
            
            results = self.service.files().list(
                q=query,
                fields="files(id, name)",
                pageSize=10
            ).execute()
            
            items = results.get('files', [])
            if items:
                folder_id = items[0]['id']
                self.folder_cache[cache_key] = folder_id
                return folder_id
            
            # 새 폴더 생성
            file_metadata = {
                'name': folder_name,
                'mimeType': 'application/vnd.google-apps.folder'
            }
            if parent_id:
                file_metadata['parents'] = [parent_id]
            
            folder = self.service.files().create(
                body=file_metadata,
                fields='id'
            ).execute()
            
            folder_id = folder.get('id')
            self.folder_cache[cache_key] = folder_id
            return folder_id
            
        except Exception as e:
            st.error(f"폴더 생성/조회 실패: {e}")
            return None
    
    def create_project_folder(self, project_title: str) -> Optional[str]:
        """프로젝트별 폴더 생성"""
        if not self.base_folder_id:
            return None
        
        try:
            now = datetime.now()
            
            # 연도 폴더
            year_folder_id = self.get_or_create_folder(str(now.year), self.base_folder_id)
            if not year_folder_id:
                return None
            
            # 월 폴더
            month_folder_id = self.get_or_create_folder(f"{now.month:02d}", year_folder_id)
            if not month_folder_id:
                return None
            
            # 프로젝트 폴더
            date_prefix = now.strftime("%Y%m%d_%H%M")
            safe_title = self.sanitize_filename(project_title)
            project_folder_name = f"{date_prefix}_{safe_title}"
            
            project_folder_id = self.get_or_create_folder(project_folder_name, month_folder_id)
            return project_folder_id
            
        except Exception as e:
            st.error(f"프로젝트 폴더 생성 실패: {e}")
            return None
    
    def sanitize_filename(self, filename: str, max_length: int = 50) -> str:
        """파일명 정리"""
        # 허용되지 않는 문자 제거
        safe_chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_() "
        safe_filename = ''.join(c for c in filename if c in safe_chars)
        
        # 연속 공백 제거 및 길이 제한
        safe_filename = ' '.join(safe_filename.split())[:max_length]
        
        return safe_filename.strip() or "Untitled"
    
    def upload_file(self, file_path: str, file_name: str, folder_id: str, description: str = "") -> Optional[str]:
        """파일 업로드"""
        try:
            from googleapiclient.http import MediaFileUpload
            
            file_metadata = {
                'name': file_name,
                'parents': [folder_id]
            }
            
            if description:
                file_metadata['description'] = description
            
            media = MediaFileUpload(file_path, resumable=True)
            
            file = self.service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id,name,size,createdTime'
            ).execute()
            
            return file.get('id')
            
        except Exception as e:
            st.error(f"파일 업로드 실패 ({file_name}): {e}")
            return None
    
    def create_project_package(self, project_data: Dict, temp_dir: str) -> Dict[str, str]:
        """프로젝트 파일 패키지 생성"""
        files_created = {}
        
        try:
            # 메타데이터 JSON
            metadata = {
                'title': project_data.get('title', 'Untitled'),
                'created_at': datetime.now().isoformat(),
                'category': project_data.get('category', 'general'),
                'input_type': project_data.get('input_type', 'text'),
                'versions': []
            }
            
            # 원본 영어 스크립트
            if 'original_script' in project_data:
                original_path = os.path.join(temp_dir, 'original_script.txt')
                with open(original_path, 'w', encoding='utf-8') as f:
                    f.write(project_data['original_script'])
                files_created['original_script.txt'] = original_path
                metadata['versions'].append('original')
            
            # 한국어 번역
            if 'korean_translation' in project_data:
                translation_path = os.path.join(temp_dir, 'korean_translation.txt')
                with open(translation_path, 'w', encoding='utf-8') as f:
                    f.write(project_data['korean_translation'])
                files_created['korean_translation.txt'] = translation_path
            
            # 각 버전별 스크립트 및 오디오
            versions = ['ted', 'podcast', 'daily']
            for version in versions:
                script_key = f"{version}_script"
                audio_key = f"{version}_audio"
                
                # 스크립트 파일
                if script_key in project_data:
                    script_path = os.path.join(temp_dir, f'{version}_script.txt')
                    with open(script_path, 'w', encoding='utf-8') as f:
                        f.write(project_data[script_key])
                    files_created[f'{version}_script.txt'] = script_path
                    metadata['versions'].append(version)
                
                # 오디오 파일
                if audio_key in project_data and project_data[audio_key]:
                    audio_src = project_data[audio_key]
                    if os.path.exists(audio_src):
                        audio_ext = os.path.splitext(audio_src)[1] or '.mp3'
                        audio_dest = os.path.join(temp_dir, f'{version}_audio{audio_ext}')
                        shutil.copy2(audio_src, audio_dest)
                        files_created[f'{version}_audio{audio_ext}'] = audio_dest
            
            # 원본 오디오
            if 'original_audio' in project_data and project_data['original_audio']:
                audio_src = project_data['original_audio']
                if os.path.exists(audio_src):
                    audio_ext = os.path.splitext(audio_src)[1] or '.mp3'
                    audio_dest = os.path.join(temp_dir, f'original_audio{audio_ext}')
                    shutil.copy2(audio_src, audio_dest)
                    files_created[f'original_audio{audio_ext}'] = audio_dest
            
            # 메타데이터 저장
            metadata_path = os.path.join(temp_dir, 'metadata.json')
            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2)
            files_created['metadata.json'] = metadata_path
            
            # README 생성
            readme_content = f"""# {metadata['title']}

## 프로젝트 정보
- 제목: {metadata['title']}
- 카테고리: {metadata.get('category', 'N/A')}
- 생성일: {metadata['created_at'][:10]}
- 입력 방식: {metadata.get('input_type', 'N/A')}

## 포함된 버전
{chr(10).join(f"- {version}" for version in metadata['versions'])}

## 파일 구조
"""
            for filename in files_created.keys():
                readme_content += f"- {filename}\n"
            
            readme_content += """
## 사용 방법
1. 각 스크립트 파일을 열어 내용 확인
2. 오디오 파일로 발음 연습
3. MyTalk 앱에서 다시 불러오기 가능

Generated by MyTalk v2.0
"""
            
            readme_path = os.path.join(temp_dir, 'README.md')
            with open(readme_path, 'w', encoding='utf-8') as f:
                f.write(readme_content)
            files_created['README.md'] = readme_path
            
            return files_created
            
        except Exception as e:
            st.error(f"프로젝트 패키지 생성 실패: {e}")
            return {}
    
    def save_project_to_drive(self, project_data: Dict) -> bool:
        """프로젝트를 Google Drive에 저장"""
        if not self.service or not self.base_folder_id:
            return False
        
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                # 프로젝트 폴더 생성
                project_folder_id = self.create_project_folder(project_data.get('title', 'Untitled'))
                if not project_folder_id:
                    return False
                
                # 파일 패키지 생성
                files_created = self.create_project_package(project_data, temp_dir)
                if not files_created:
                    return False
                
                # 각 파일 업로드
                upload_success = 0
                total_files = len(files_created)
                
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                for i, (filename, filepath) in enumerate(files_created.items()):
                    status_text.text(f"업로드 중: {filename}")
                    
                    file_id = self.upload_file(
                        filepath, 
                        filename, 
                        project_folder_id,
                        f"MyTalk 프로젝트 파일 - {project_data.get('title', 'Untitled')}"
                    )
                    
                    if file_id:
                        upload_success += 1
                    
                    progress_bar.progress((i + 1) / total_files)
                
                progress_bar.empty()
                status_text.empty()
                
                return upload_success == total_files
                
        except Exception as e:
            st.error(f"Google Drive 저장 실패: {e}")
            return False
    
    def list_projects(self, limit: int = 50) -> List[Dict]:
        """저장된 프로젝트 목록 조회"""
        if not self.service or not self.base_folder_id:
            return []
        
        try:
            # MyTalk 폴더 하위의 모든 폴더 검색
            query = f"'{self.base_folder_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
            
            all_projects = []
            page_token = None
            
            while len(all_projects) < limit:
                results = self.service.files().list(
                    q=query,
                    fields="nextPageToken, files(id, name, createdTime, modifiedTime)",
                    pageSize=min(limit - len(all_projects), 100),
                    orderBy="createdTime desc",
                    pageToken=page_token
                ).execute()
                
                items = results.get('files', [])
                all_projects.extend(items)
                
                page_token = results.get('nextPageToken')
                if not page_token:
                    break
            
            # 프로젝트 정보 구조화
            projects = []
            for item in all_projects[:limit]:
                project_info = {
                    'id': item['id'],
                    'name': item['name'],
                    'created': item.get('createdTime', ''),
                    'modified': item.get('modifiedTime', ''),
                    'folder_id': item['id']
                }
                projects.append(project_info)
            
            return projects
            
        except Exception as e:
            st.error(f"프로젝트 목록 조회 실패: {e}")
            return []
    
    def download_project(self, folder_id: str, download_path: str) -> bool:
        """프로젝트 다운로드"""
        try:
            from googleapiclient.http import MediaIoBaseDownload
            
            # 폴더 내 파일 목록 조회
            query = f"'{folder_id}' in parents and trashed=false"
            results = self.service.files().list(
                q=query,
                fields="files(id, name)"
            ).execute()
            
            files = results.get('files', [])
            if not files:
                return False
            
            # 다운로드 폴더 생성
            os.makedirs(download_path, exist_ok=True)
            
            # 각 파일 다운로드
            for file_info in files:
                file_id = file_info['id']
                file_name = file_info['name']
                
                request = self.service.files().get_media(fileId=file_id)
                
                file_path = os.path.join(download_path, file_name)
                with open(file_path, 'wb') as fh:
                    downloader = MediaIoBaseDownload(fh, request)
                    done = False
                    while not done:
                        status, done = downloader.next_chunk()
            
            return True
            
        except Exception as e:
            st.error(f"프로젝트 다운로드 실패: {e}")
            return False

# Advanced Cache Management
class SmartCacheManager:
    """스마트 캐시 관리자"""
    
    def __init__(self, cache_dir: str = "cache", max_size_mb: int = 500):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        self.max_size_bytes = max_size_mb * 1024 * 1024
        self.index_file = self.cache_dir / "cache_index.json"
        self.load_index()
    
    def load_index(self):
        """캐시 인덱스 로드"""
        try:
            if self.index_file.exists():
                with open(self.index_file, 'r', encoding='utf-8') as f:
                    self.index = json.load(f)
            else:
                self.index = {}
        except Exception:
            self.index = {}
    
    def save_index(self):
        """캐시 인덱스 저장"""
        try:
            with open(self.index_file, 'w', encoding='utf-8') as f:
                json.dump(self.index, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
    
    def get_cache_key(self, content: str, content_type: str, params: Dict = None) -> str:
        """캐시 키 생성"""
        key_data = f"{content}_{content_type}"
        if params:
            key_data += "_" + "_".join(f"{k}:{v}" for k, v in sorted(params.items()))
        
        return hashlib.sha256(key_data.encode()).hexdigest()[:16]
    
    def get_cached_file(self, cache_key: str) -> Optional[str]:
        """캐시된 파일 경로 반환"""
        if cache_key in self.index:
            cache_info = self.index[cache_key]
            cache_path = self.cache_dir / cache_info['filename']
            
            if cache_path.exists():
                # 접근 시간 업데이트
                cache_info['last_accessed'] = datetime.now().isoformat()
                cache_info['access_count'] = cache_info.get('access_count', 0) + 1
                self.save_index()
                
                return str(cache_path)
        
        return None
    
    def cache_file(self, cache_key: str, source_path: str, content_type: str, metadata: Dict = None) -> bool:
        """파일을 캐시에 저장"""
        try:
            if not os.path.exists(source_path):
                return False
            
            # 파일 확장자 결정
            if content_type == 'audio':
                ext = '.mp3'
            elif content_type == 'text':
                ext = '.txt'
            else:
                ext = os.path.splitext(source_path)[1] or '.dat'
            
            cache_filename = f"{cache_key}{ext}"
            cache_path = self.cache_dir / cache_filename
            
            # 파일 복사
            shutil.copy2(source_path, cache_path)
            
            # 인덱스 업데이트
            self.index[cache_key] = {
                'filename': cache_filename,
                'content_type': content_type,
                'created': datetime.now().isoformat(),
                'last_accessed': datetime.now().isoformat(),
                'access_count': 1,
                'size': cache_path.stat().st_size,
                'metadata': metadata or {}
            }
            
            self.save_index()
            self.cleanup_if_needed()
            
            return True
            
        except Exception as e:
            return False
    
    def get_cache_size(self) -> int:
        """현재 캐시 크기 (바이트)"""
        total_size = 0
        for cache_info in self.index.values():
            cache_path = self.cache_dir / cache_info['filename']
            if cache_path.exists():
                total_size += cache_path.stat().st_size
            else:
                # 존재하지 않는 파일은 인덱스에서 제거
                self.remove_from_index(cache_info['filename'])
        
        return total_size
    
    def cleanup_if_needed(self):
        """필요시 캐시 정리"""
        current_size = self.get_cache_size()
        
        if current_size > self.max_size_bytes:
            # LRU 정책으로 정리
            items = list(self.index.items())
            items.sort(key=lambda x: x[1].get('last_accessed', ''))
            
            while current_size > self.max_size_bytes * 0.8 and items:
                cache_key, cache_info = items.pop(0)
                self.remove_cached_file(cache_key)
                current_size = self.get_cache_size()
    
    def remove_cached_file(self, cache_key: str):
        """특정 캐시 파일 제거"""
        if cache_key in self.index:
            cache_info = self.index[cache_key]
            cache_path = self.cache_dir / cache_info['filename']
            
            try:
                if cache_path.exists():
                    cache_path.unlink()
            except Exception:
                pass
            
            del self.index[cache_key]
            self.save_index()
    
    def remove_from_index(self, filename: str):
        """인덱스에서 파일 정보 제거"""
        keys_to_remove = []
        for key, info in self.index.items():
            if info.get('filename') == filename:
                keys_to_remove.append(key)
        
        for key in keys_to_remove:
            del self.index[key]
        
        if keys_to_remove:
            self.save_index()
    
    def clear_cache(self) -> int:
        """전체 캐시 정리"""
        removed_count = 0
        
        for cache_info in list(self.index.values()):
            cache_path = self.cache_dir / cache_info['filename']
            try:
                if cache_path.exists():
                    cache_path.unlink()
                    removed_count += 1
            except Exception:
                pass
        
        self.index.clear()
        self.save_index()
        
        return removed_count
    
    def get_cache_stats(self) -> Dict:
        """캐시 통계"""
        total_size = self.get_cache_size()
        file_count = len(self.index)
        
        type_stats = {}
        for cache_info in self.index.values():
            content_type = cache_info.get('content_type', 'unknown')
            if content_type not in type_stats:
                type_stats[content_type] = {'count': 0, 'size': 0}
            
            type_stats[content_type]['count'] += 1
            type_stats[content_type]['size'] += cache_info.get('size', 0)
        
        return {
            'total_size_mb': total_size / (1024 * 1024),
            'file_count': file_count,
            'max_size_mb': self.max_size_bytes / (1024 * 1024),
            'usage_percent': (total_size / self.max_size_bytes) * 100,
            'type_stats': type_stats
        }

# Study Progress Tracking
class StudyProgressTracker:
    """학습 진행 상황 추적"""
    
    def __init__(self, db_path: str = 'mytalk.db'):
        self.db_path = db_path
        self.init_tables()
    
    def init_tables(self):
        """테이블 초기화"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # 학습 세션 테이블
        c.execute('''
            CREATE TABLE IF NOT EXISTS study_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_date DATE NOT NULL,
                script_id INTEGER,
                version_type TEXT,
                study_duration_minutes INTEGER,
                activity_type TEXT,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (script_id) REFERENCES scripts (id)
            )
        ''')
        
        # 학습 목표 테이블
        c.execute('''
            CREATE TABLE IF NOT EXISTS study_goals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                goal_type TEXT NOT NULL,
                target_value INTEGER,
                current_value INTEGER DEFAULT 0,
                start_date DATE,
                target_date DATE,
                status TEXT DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 성취 배지 테이블
        c.execute('''
            CREATE TABLE IF NOT EXISTS achievements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                badge_name TEXT NOT NULL,
                badge_description TEXT,
                earned_date DATE,
                criteria_met TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def log_study_session(self, script_id: Optional[int], version_type: str, 
                         duration_minutes: int, activity_type: str, notes: str = ""):
        """학습 세션 기록"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute('''
            INSERT INTO study_sessions 
            (session_date, script_id, version_type, study_duration_minutes, activity_type, notes)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (datetime.now().date(), script_id, version_type, duration_minutes, activity_type, notes))
        
        conn.commit()
        conn.close()
        
        # 목표 진행도 업데이트
        self.update_goal_progress()
        
        # 배지 확인
        self.check_achievements()
    
    def update_goal_progress(self):
        """목표 진행도 업데이트"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # 활성 목표들 조회
        c.execute("SELECT * FROM study_goals WHERE status = 'active'")
        goals = c.fetchall()
        
        for goal in goals:
            goal_id, goal_type, target_value, current_value, start_date, target_date, status, created_at = goal
            
            new_value = self.calculate_goal_progress(goal_type, start_date)
            
            # 진행도 업데이트
            c.execute("UPDATE study_goals SET current_value = ? WHERE id = ?", (new_value, goal_id))
            
            # 목표 달성 확인
            if new_value >= target_value:
                c.execute("UPDATE study_goals SET status = 'completed' WHERE id = ?", (goal_id,))
        
        conn.commit()
        conn.close()
    
    def calculate_goal_progress(self, goal_type: str, start_date: str) -> int:
        """목표 유형별 진행도 계산"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        if goal_type == 'daily_minutes':
            c.execute('''
                SELECT COALESCE(SUM(study_duration_minutes), 0) 
                FROM study_sessions 
                WHERE session_date = ?
            ''', (datetime.now().date(),))
            
        elif goal_type == 'weekly_sessions':
            week_ago = datetime.now().date() - timedelta(days=7)
            c.execute('''
                SELECT COUNT(*) 
                FROM study_sessions 
                WHERE session_date >= ?
            ''', (week_ago,))
            
        elif goal_type == 'scripts_completed':
            c.execute('''
                SELECT COUNT(DISTINCT script_id) 
                FROM study_sessions 
                WHERE session_date >= ?
            ''', (start_date,))
            
        elif goal_type == 'total_minutes':
            c.execute('''
                SELECT COALESCE(SUM(study_duration_minutes), 0) 
                FROM study_sessions 
                WHERE session_date >= ?
            ''', (start_date,))
        
        else:
            return 0
        
        result = c.fetchone()
        conn.close()
        
        return result[0] if result else 0
    
    def check_achievements(self):
        """배지 획득 확인"""
        achievements_to_check = [
            ('first_script', '첫 스크립트 완성', self.check_first_script),
            ('week_warrior', '일주일 연속 학습', self.check_week_streak),
            ('hour_master', '누적 60분 학습', self.check_total_hours),
            ('variety_learner', '모든 버전 경험', self.check_all_versions),
            ('daily_dedication', '하루 30분 학습', self.check_daily_goal)
        ]
        
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        for badge_name, description, check_func in achievements_to_check:
            # 이미 획득한 배지인지 확인
            c.execute("SELECT id FROM achievements WHERE badge_name = ?", (badge_name,))
            if c.fetchone():
                continue  # 이미 획득
            
            # 배지 조건 확인
            if check_func():
                c.execute('''
                    INSERT INTO achievements (badge_name, badge_description, earned_date, criteria_met)
                    VALUES (?, ?, ?, ?)
                ''', (badge_name, description, datetime.now().date(), "자동 달성"))
        
        conn.commit()
        conn.close()
    
    def check_first_script(self) -> bool:
        """첫 스크립트 완성 확인"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM scripts")
        count = c.fetchone()[0]
        conn.close()
        return count >= 1
    
    def check_week_streak(self) -> bool:
        """일주일 연속 학습 확인"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # 최근 7일간 학습한 날짜 확인
        seven_days_ago = datetime.now().date() - timedelta(days=7)
        c.execute('''
            SELECT DISTINCT session_date 
            FROM study_sessions 
            WHERE session_date >= ? 
            ORDER BY session_date
        ''', (seven_days_ago,))
        
        dates = [row[0] for row in c.fetchall()]
        conn.close()
        
        if len(dates) < 7:
            return False
        
        # 연속성 확인
        for i in range(6):
            current_date = datetime.strptime(dates[i], '%Y-%m-%d').date()
            next_date = datetime.strptime(dates[i + 1], '%Y-%m-%d').date()
            if (next_date - current_date).days != 1:
                return False
        
        return True
    
    def check_total_hours(self) -> bool:
        """누적 60분 학습 확인"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("SELECT COALESCE(SUM(study_duration_minutes), 0) FROM study_sessions")
        total_minutes = c.fetchone()[0]
        conn.close()
        return total_minutes >= 60
    
    def check_all_versions(self) -> bool:
        """모든 버전 경험 확인"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("SELECT DISTINCT version_type FROM study_sessions")
        versions = set(row[0] for row in c.fetchall())
        conn.close()
        required_versions = {'original', 'ted', 'podcast', 'daily'}
        return required_versions.issubset(versions)
    
    def check_daily_goal(self) -> bool:
        """하루 30분 학습 확인"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('''
            SELECT COALESCE(SUM(study_duration_minutes), 0) 
            FROM study_sessions 
            WHERE session_date = ?
        ''', (datetime.now().date(),))
        daily_minutes = c.fetchone()[0]
        conn.close()
        return daily_minutes >= 30
    
    def get_study_stats(self, days: int = 30) -> Dict:
        """학습 통계 조회"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        start_date = datetime.now().date() - timedelta(days=days)
        
        # 기본 통계
        c.execute('''
            SELECT 
                COUNT(*) as session_count,
                COALESCE(SUM(study_duration_minutes), 0) as total_minutes,
                COUNT(DISTINCT session_date) as study_days,
                COUNT(DISTINCT script_id) as unique_scripts
            FROM study_sessions 
            WHERE session_date >= ?
        ''', (start_date,))
        
        basic_stats = c.fetchone()
        
        # 버전별 통계
        c.execute('''
            SELECT version_type, COUNT(*), COALESCE(SUM(study_duration_minutes), 0)
            FROM study_sessions 
            WHERE session_date >= ?
            GROUP BY version_type
        ''', (start_date,))
        
        version_stats = {row[0]: {'sessions': row[1], 'minutes': row[2]} for row in c.fetchall()}
        
        # 활동별 통계
        c.execute('''
            SELECT activity_type, COUNT(*), COALESCE(SUM(study_duration_minutes), 0)
            FROM study_sessions 
            WHERE session_date >= ?
            GROUP BY activity_type
        ''', (start_date,))
        
        activity_stats = {row[0]: {'sessions': row[1], 'minutes': row[2]} for row in c.fetchall()}
        
        # 일별 학습 시간
        c.execute('''
            SELECT session_date, COALESCE(SUM(study_duration_minutes), 0)
            FROM study_sessions 
            WHERE session_date >= ?
            GROUP BY session_date
            ORDER BY session_date
        ''', (start_date,))
        
        daily_minutes = {row[0]: row[1] for row in c.fetchall()}
        
        conn.close()
        
        return {
            'period_days': days,
            'session_count': basic_stats[0],
            'total_minutes': basic_stats[1],
            'study_days': basic_stats[2],
            'unique_scripts': basic_stats[3],
            'average_session_minutes': basic_stats[1] / max(basic_stats[0], 1),
            'version_stats': version_stats,
            'activity_stats': activity_stats,
            'daily_minutes': daily_minutes
        }
    
    def get_achievements(self) -> List[Dict]:
        """획득한 배지 목록"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute('''
            SELECT badge_name, badge_description, earned_date 
            FROM achievements 
            ORDER BY earned_date DESC
        ''')
        
        achievements = []
        for row in c.fetchall():
            achievements.append({
                'name': row[0],
                'description': row[1],
                'earned_date': row[2]
            })
        
        conn.close()
        return achievements

# Export and Import utilities
class DataPortabilityManager:
    """데이터 이동성 관리 (내보내기/가져오기)"""
    
    def __init__(self, db_path: str = 'mytalk.db'):
        self.db_path = db_path
    
    def export_to_zip(self, output_path: str, include_audio: bool = True) -> bool:
        """전체 데이터를 ZIP으로 내보내기"""
        try:
            with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                # 데이터베이스 내보내기
                db_data = self.export_database_to_json()
                zipf.writestr('database.json', json.dumps(db_data, ensure_ascii=False, indent=2))
                
                # 오디오 파일들 포함
                if include_audio:
                    audio_files = self.collect_audio_files()
                    for audio_path, archive_name in audio_files:
                        if os.path.exists(audio_path):
                            zipf.write(audio_path, f'audio/{archive_name}')
                
                # 메타데이터 추가
                metadata = {
                    'export_date': datetime.now().isoformat(),
                    'version': 'MyTalk v2.0',
                    'include_audio': include_audio,
                    'file_count': len(zipf.namelist())
                }
                zipf.writestr('export_info.json', json.dumps(metadata, indent=2))
            
            return True
            
        except Exception as e:
            st.error(f"ZIP 내보내기 실패: {e}")
            return False
    
    def export_database_to_json(self) -> Dict:
        """데이터베이스를 JSON으로 내보내기"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # 딕셔너리 형태로 결과 반환
        
        data = {}
        
        # 각 테이블 데이터 수집
        tables = ['scripts', 'practice_versions', 'stored_files', 'study_sessions', 'study_goals', 'achievements']
        
        for table in tables:
            try:
                cursor = conn.execute(f"SELECT * FROM {table}")
                data[table] = [dict(row) for row in cursor.fetchall()]
            except sqlite3.OperationalError:
                # 테이블이 존재하지 않으면 빈 리스트
                data[table] = []
        
        conn.close()
        return data
    
    def collect_audio_files(self) -> List[Tuple[str, str]]:
        """오디오 파일 수집"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        audio_files = []
        
        # practice_versions 테이블에서 오디오 파일
        c.execute("SELECT id, audio_path FROM practice_versions WHERE audio_path IS NOT NULL")
        for row in c.fetchall():
            version_id, audio_path = row
            if audio_path and os.path.exists(audio_path):
                filename = f"version_{version_id}_{os.path.basename(audio_path)}"
                audio_files.append((audio_path, filename))
        
        # stored_files 테이블에서 오디오 파일
        c.execute("SELECT id, local_path, file_name FROM stored_files WHERE file_type LIKE '%audio%' AND local_path IS NOT NULL")
        for row in c.fetchall():
            file_id, local_path, file_name = row
            if local_path and os.path.exists(local_path):
                filename = f"stored_{file_id}_{file_name}"
                audio_files.append((local_path, filename))
        
        conn.close()
        return audio_files
    
    def import_from_zip(self, zip_path: str) -> bool:
        """ZIP에서 데이터 가져오기"""
        try:
            with zipfile.ZipFile(zip_path, 'r') as zipf:
                # 내보내기 정보 확인
                if 'export_info.json' in zipf.namelist():
                    export_info = json.loads(zipf.read('export_info.json').decode('utf-8'))
                    st.info(f"가져오기: {export_info.get('version', 'Unknown')} ({export_info.get('export_date', 'Unknown')})")
                
                # 데이터베이스 가져오기
                if 'database.json' in zipf.namelist():
                    db_data = json.loads(zipf.read('database.json').decode('utf-8'))
                    self.import_database_from_json(db_data)
                
                # 오디오 파일 가져오기
                audio_files = [f for f in zipf.namelist() if f.startswith('audio/')]
                if audio_files:
                    audio_dir = 'imported_audio'
                    os.makedirs(audio_dir, exist_ok=True)
                    
                    for audio_file in audio_files:
                        zipf.extract(audio_file, '.')
                        # 파일 경로 업데이트 (필요시)
                        self.update_audio_paths(audio_file, os.path.join(audio_dir, os.path.basename(audio_file)))
            
            return True
            
        except Exception as e:
            st.error(f"ZIP 가져오기 실패: {e}")
            return False
    
    def import_database_from_json(self, data: Dict):
        """JSON에서 데이터베이스로 가져오기"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        try:
            # 외래 키 제약 조건 일시 비활성화
            c.execute("PRAGMA foreign_keys = OFF")
            
            # 각 테이블 데이터 삽입
            table_order = ['scripts', 'practice_versions', 'stored_files', 'study_sessions', 'study_goals', 'achievements']
            
            for table in table_order:
                if table in data and data[table]:
                    # 테이블 구조 확인
                    c.execute(f"PRAGMA table_info({table})")
                    columns = [col[1] for col in c.fetchall()]
                    
                    for row_data in data[table]:
                        # 존재하는 컬럼만 사용
                        valid_data = {k: v for k, v in row_data.items() if k in columns}
                        
                        if valid_data:
                            placeholders = ', '.join(['?' for _ in valid_data])
                            column_names = ', '.join(valid_data.keys())
                            
                            c.execute(f'''
                                INSERT OR REPLACE INTO {table} ({column_names}) 
                                VALUES ({placeholders})
                            ''', list(valid_data.values()))
            
            # 외래 키 제약 조건 재활성화
            c.execute("PRAGMA foreign_keys = ON")
            
            conn.commit()
            
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
    
    def update_audio_paths(self, old_path: str, new_path: str):
        """오디오 파일 경로 업데이트"""
        if os.path.exists(old_path):
            shutil.move(old_path, new_path)
        
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # practice_versions 테이블 업데이트
        c.execute("UPDATE practice_versions SET audio_path = ? WHERE audio_path LIKE ?", 
                 (new_path, f"%{os.path.basename(old_path)}%"))
        
        # stored_files 테이블 업데이트
        c.execute("UPDATE stored_files SET local_path = ? WHERE local_path LIKE ?",
                 (new_path, f"%{os.path.basename(old_path)}%"))
        
        conn.commit()
        conn.close()

# UI Helper functions
def create_progress_indicator(current: int, total: int, label: str = "") -> str:
    """진행률 표시기 HTML 생성"""
    percentage = (current / max(total, 1)) * 100
    
    return f"""
    <div style="margin: 10px 0;">
        {f'<div style="font-size: 14px; margin-bottom: 5px;">{label}</div>' if label else ''}
        <div style="background-color: #e0e0e0; border-radius: 10px; overflow: hidden;">
            <div style="
                background: linear-gradient(90deg, #4CAF50, #45a049);
                height: 20px;
                width: {percentage:.1f}%;
                transition: width 0.3s ease;
                border-radius: 10px;
                position: relative;
            ">
                <div style="
                    position: absolute;
                    right: 5px;
                    top: 50%;
                    transform: translateY(-50%);
                    color: white;
                    font-size: 12px;
                    font-weight: bold;
                ">
                    {current}/{total}
                </div>
            </div>
        </div>
        <div style="text-align: center; font-size: 12px; margin-top: 2px; color: #666;">
            {percentage:.1f}% 완료
        </div>
    </div>
    """

def create_stats_card(title: str, value: str, subtitle: str = "", icon: str = "📊") -> str:
    """통계 카드 HTML 생성"""
    return f"""
    <div style="
        background: linear-gradient(135deg, #f8f9fa, #e9ecef);
        padding: 20px;
        border-radius: 15px;
        text-align: center;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        margin: 10px;
        transition: transform 0.2s ease;
    " onmouseover="this.style.transform='translateY(-2px)'" onmouseout="this.style.transform='translateY(0)'">
        <div style="font-size: 2rem; margin-bottom: 10px;">{icon}</div>
        <div style="font-size: 2rem; font-weight: bold; color: #2c3e50; margin-bottom: 5px;">{value}</div>
        <div style="font-size: 1.1rem; color: #495057; font-weight: 500;">{title}</div>
        {f'<div style="font-size: 0.9rem; color: #6c757d; margin-top: 5px;">{subtitle}</div>' if subtitle else ''}
    </div>
    """

def create_achievement_badge(name: str, description: str, earned: bool = False, date: str = "") -> str:
    """성취 배지 HTML 생성"""
    if earned:
        badge_style = """
            background: linear-gradient(45deg, #FFD700, #FFA500);
            color: #333;
            border: 3px solid #FFD700;
            box-shadow: 0 0 20px rgba(255, 215, 0, 0.5);
        """
        status_icon = "🏆"
        status_text = f"달성일: {date}" if date else "달성"
    else:
        badge_style = """
            background: #f8f9fa;
            color: #6c757d;
            border: 3px solid #dee2e6;
        """
        status_icon = "🔒"
        status_text = "미달성"
    
    return f"""
    <div style="
        {badge_style}
        padding: 15px;
        border-radius: 15px;
        text-align: center;
        margin: 10px;
        transition: all 0.3s ease;
        min-height: 120px;
        display: flex;
        flex-direction: column;
        justify-content: center;
    " {'onmouseover="this.style.transform=\'scale(1.05)\'" onmouseout="this.style.transform=\'scale(1)\'"' if earned else ''}>
        <div style="font-size: 2rem; margin-bottom: 8px;">{status_icon}</div>
        <div style="font-weight: bold; margin-bottom: 5px;">{name}</div>
        <div style="font-size: 0.9rem; margin-bottom: 5px;">{description}</div>
        <div style="font-size: 0.8rem; font-style: italic;">{status_text}</div>
    </div>
    """

def format_duration(minutes: int) -> str:
    """시간 형식 변환"""
    if minutes < 60:
        return f"{minutes}분"
    else:
        hours = minutes // 60
        mins = minutes % 60
        if mins == 0:
            return f"{hours}시간"
        else:
            return f"{hours}시간 {mins}분"

def safe_divide(a: float, b: float, default: float = 0.0) -> float:
    """안전한 나눗셈"""
    return a / b if b != 0 else default

# Mobile optimization
def get_mobile_css() -> str:
    """모바일 최적화 CSS"""
    return """
    <style>
    @media (max-width: 768px) {
        .stApp {
            padding: 0.5rem !important;
        }
        
        .stButton > button {
            width: 100% !important;
            min-height: 44px !important;
            font-size: 16px !important;
            touch-action: manipulation;
        }
        
        .stSelectbox > div > div {
            font-size: 16px !important;
        }
        
        .stTextInput > div > div > input,
        .stTextArea > div > div > textarea {
            font-size: 16px !important;
            -webkit-appearance: none;
        }
        
        .stTabs [data-baseweb="tab-list"] {
            gap: 2px;
        }
        
        .stTabs [data-baseweb="tab"] {
            padding: 8px 12px;
            font-size: 14px;
        }
        
        /* 스크롤 성능 개선 */
        .main > div {
            -webkit-overflow-scrolling: touch;
        }
        
        /* 터치 반응성 개선 */
        button, a, [role="button"] {
            touch-action: manipulation;
            -webkit-tap-highlight-color: rgba(0,0,0,0.1);
        }
    }
    
    /* iOS Safari 특별 처리 */
    @supports (-webkit-touch-callout: none) {
        .stTextInput > div > div > input {
            font-size: 16px !important; /* 줌 방지 */
        }
    }
    
    /* PWA 지원 */
    @media (display-mode: standalone) {
        .stApp {
            padding-top: max(1rem, env(safe-area-inset-top));
            padding-bottom: max(1rem, env(safe-area-inset-bottom));
        }
    }
    </style>
    """

# Session management for better UX
def init_session_persistence():
    """세션 지속성 초기화"""
    if 'session_id' not in st.session_state:
        st.session_state.session_id = hashlib.md5(f"{datetime.now().isoformat()}".encode()).hexdigest()[:12]
    
    # 자동 저장 설정
    if 'auto_save_enabled' not in st.session_state:
        st.session_state.auto_save_enabled = True

def save_session_data():
    """세션 데이터 저장"""
    if not st.session_state.get('auto_save_enabled'):
        return
    
    session_file = f"session_{st.session_state.session_id}.json"
    
    try:
        session_data = {
            'api_provider': st.session_state.get('api_provider', ''),
            'model': st.session_state.get('model', ''),
            'tts_engine': st.session_state.get('tts_engine', 'auto'),
            'tts_voice': st.session_state.get('tts_voice', 'en'),
            'last_update': datetime.now().isoformat()
        }
        
        with open(session_file, 'w', encoding='utf-8') as f:
            json.dump(session_data, f, ensure_ascii=False, indent=2)
            
    except Exception:
        pass  # 세션 저장 실패는 치명적이지 않음

def load_session_data():
    """세션 데이터 로드"""
    if 'session_id' not in st.session_state:
        return
    
    session_file = f"session_{st.session_state.session_id}.json"
    
    try:
        if os.path.exists(session_file):
            with open(session_file, 'r', encoding='utf-8') as f:
                session_data = json.load(f)
            
            # 24시간 이내 데이터만 복원
            last_update = datetime.fromisoformat(session_data.get('last_update', ''))
            if datetime.now() - last_update < timedelta(hours=24):
                for key, value in session_data.items():
                    if key != 'last_update' and key not in st.session_state:
                        st.session_state[key] = value
    except Exception:
        pass

# 정리 함수들
def cleanup_temp_files(max_age_hours: int = 24):
    """오래된 임시 파일 정리"""
    temp_patterns = ['session_*.json', 'temp_*.mp3', 'temp_*.wav', 'temp_*.txt']
    current_time = datetime.now()
    
    for pattern in temp_patterns:
        for filepath in Path('.').glob(pattern):
            try:
                file_age = current_time - datetime.fromtimestamp(filepath.stat().st_mtime)
                if file_age.total_seconds() > max_age_hours * 3600:
                    filepath.unlink()
            except Exception:
                pass

# 앱 시작시 초기화
def initialize_app():
    """앱 초기화"""
    init_session_persistence()
    load_session_data()
    cleanup_temp_files()

# 앱 종료시 정리
import atexit

def cleanup_on_exit():
    """앱 종료시 정리"""
    save_session_data()
    cleanup_temp_files(max_age_hours=1)  # 1시간 이상 된 파일만

atexit.register(cleanup_on_exit)