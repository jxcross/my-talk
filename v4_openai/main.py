"""
MyTalk - OAuth 2.0 Google Drive 동기화 통합 버전 with Enhanced OpenAI TTS (Multi-Voice)
주요 기능:
1. 기존 로컬 파일 시스템과 Google Drive 이중 저장
2. OAuth 2.0 방식으로 개인 Google Drive 접근
3. 토큰 자동 저장 및 갱신
4. 실시간 동기화 및 충돌 해결
5. 오프라인 모드 지원
6. 자동 백업 및 복원
7. Enhanced OpenAI TTS API 통합 (Multi-Voice: 음성언어-1, 음성언어-2)
8. 2인 대화 형식 지원 (Host/Guest, A/B 역할별 음성 배정)
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
import re

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
    st.warning("Google Drive API 라이브러리가 없습니다. 로컬 모드로만 작동합니다.")

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
                
                st.info("🔍 OAuth 2.0 브라우저 인증이 필요합니다.")
                
                try:
                    flow = InstalledAppFlow.from_client_secrets_file(
                        self.credentials_file, self.scopes)
                    
                    # 인증 URL 생성
                    auth_url, _ = flow.authorization_url(prompt='consent')
                    
                    st.markdown(f"""
                    ### 🔍 Google OAuth 2.0 인증이 필요합니다
                    
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
                        st.error("⛔ 제공된 ID는 폴더가 아닙니다.")
                        return False
                except Exception as e:
                    st.error(f"⛔ 폴더에 접근할 수 없습니다: {str(e)}")
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
    
    def extract_folder_id_from_url(self, url):
        """Google Drive URL에서 폴더 ID 추출"""
        import re
        
        patterns = [
            r'/folders/([a-zA-Z0-9-_]+)',
            r'id=([a-zA-Z0-9-_]+)',
            r'/d/([a-zA-Z0-9-_]+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        
        if len(url.strip()) > 20 and not url.startswith('http'):
            return url.strip()
        
        return None
    
    def set_custom_folder(self, folder_id_or_path_or_url):
        """사용자 지정 폴더 설정"""
        if folder_id_or_path_or_url.strip():
            input_value = folder_id_or_path_or_url.strip()
            
            if input_value.startswith('http'):
                folder_id = self.extract_folder_id_from_url(input_value)
                if folder_id:
                    self.custom_folder_id = folder_id
                    self.folder_path = None
                    return True
                else:
                    return False
            
            elif len(input_value.replace('-', '').replace('_', '')) > 20:
                self.custom_folder_id = input_value
                self.folder_path = None
                return True
            else:
                self.custom_folder_id = None
                self.folder_path = input_value
                return True
        return False
    
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
    
    def list_drive_folders(self, parent_id='root', max_results=20):
        """Google Drive의 폴더 목록 조회"""
        try:
            query = f"parents in '{parent_id}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
            results = self.service.files().list(
                q=query,
                pageSize=max_results,
                fields="files(id, name, parents)"
            ).execute()
            return results.get('files', [])
        except Exception as e:
            st.error(f"폴더 목록 조회 실패: {str(e)}")
            return []
    
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
                translation_key = f"{version}_korean_translation"
                
                if script_key in results and results[script_key]:
                    script_file = project_folder / f"{version}_script.txt"
                    with open(script_file, 'w', encoding='utf-8') as f:
                        f.write(results[script_key])
                    saved_files[script_key] = str(script_file)
                    metadata['versions'].append(version)
                    st.write(f"✅ {version.upper()} 스크립트 저장: {script_file.name}")
                
                # 한국어 번역 저장
                if translation_key in results and results[translation_key]:
                    translation_file = project_folder / f"{version}_korean_translation.txt"
                    with open(translation_file, 'w', encoding='utf-8') as f:
                        f.write(results[translation_key])
                    saved_files[translation_key] = str(translation_file)
                    st.write(f"✅ {version.upper()} 한국어 번역 저장: {translation_file.name}")
                
                # 오디오 파일들 저장 (단일 또는 다중)
                if audio_key in results and results[audio_key]:
                    audio_data = results[audio_key]
                    
                    # 단일 오디오 파일인 경우
                    if isinstance(audio_data, str) and os.path.exists(audio_data):
                        audio_ext = Path(audio_data).suffix or '.mp3'
                        audio_dest = audio_folder / f"{version}_audio{audio_ext}"
                        shutil.copy2(audio_data, audio_dest)
                        saved_files[audio_key] = str(audio_dest)
                        st.write(f"✅ {version.upper()} 오디오 저장: {audio_dest.name}")
                    
                    # 다중 오디오 파일인 경우 (딕셔너리)
                    elif isinstance(audio_data, dict):
                        audio_paths = {}
                        for role, audio_path in audio_data.items():
                            if os.path.exists(audio_path):
                                audio_ext = Path(audio_path).suffix or '.mp3'
                                audio_dest = audio_folder / f"{version}_audio_{role}{audio_ext}"
                                shutil.copy2(audio_path, audio_dest)
                                audio_paths[role] = str(audio_dest)
                                st.write(f"✅ {version.upper()} {role.upper()} 오디오 저장: {audio_dest.name}")
                        saved_files[audio_key] = audio_paths
            
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
                    # 단일 파일인 경우
                    if isinstance(file_path, str) and os.path.exists(file_path):
                        content[file_type] = file_path
                    # 다중 파일인 경우 (딕셔너리)
                    elif isinstance(file_path, dict):
                        audio_files = {}
                        for role, path in file_path.items():
                            if os.path.exists(path):
                                audio_files[role] = path
                        if audio_files:
                            content[file_type] = audio_files
            
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
            if self.provider == 'OpenAI' and openai and self.api_key:
                # OpenAI v1.0+ 방식
                self.client = openai.OpenAI(api_key=self.api_key)
            elif self.provider == 'Anthropic' and Anthropic and self.api_key:
                self.client = Anthropic(api_key=self.api_key)
            elif self.provider == 'Google' and genai and self.api_key:
                genai.configure(api_key=self.api_key)
                self.client = genai
        except Exception as e:
            st.error(f"LLM 클라이언트 초기화 실패: {str(e)}")
    
    def generate_content(self, prompt):
        """간단한 콘텐츠 생성"""
        try:
            if not self.client or not self.api_key:
                return None
            
            if self.provider == 'OpenAI':
                # OpenAI v1.0+ 방식
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=2000,
                    temperature=0.7
                )
                return response.choices[0].message.content
            
            elif self.provider == 'Anthropic':
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=2000,
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


def generate_audio_with_openai_tts(text, api_key, voice='alloy'):
    """OpenAI TTS API를 사용한 음성 생성"""
    try:
        if not openai:
            raise ImportError("OpenAI 라이브러리가 설치되지 않았습니다")
        
        # OpenAI 클라이언트 설정
        client = openai.OpenAI(api_key=api_key)
        
        # TTS 요청
        response = client.audio.speech.create(
            model="tts-1",  # tts-1 또는 tts-1-hd 사용 가능
            voice=voice,
            input=text
        )
        
        # 임시 파일에 저장
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.mp3')
        response.stream_to_file(temp_file.name)
        
        return temp_file.name
        
    except Exception as e:
        st.error(f"OpenAI TTS 생성 실패: {str(e)}")
        return None


def extract_dialogue_content(text, version_type):
    """스크립트에서 실제 대화 부분만 추출 (메타 정보 제거)"""
    try:
        # 버전별 처리
        if version_type == 'ted':
            # [Opening Hook] 같은 부분 제거
            lines = text.split('\n')
            cleaned_lines = []
            for line in lines:
                # [] 로 둘러싸인 부분 제거
                if re.match(r'^\[.*\]', line.strip()):
                    continue
                # [] 부분이 포함된 라인에서 해당 부분만 제거
                cleaned_line = re.sub(r'\[.*?\]', '', line).strip()
                if cleaned_line:
                    cleaned_lines.append(cleaned_line)
            return '\n'.join(cleaned_lines)
        
        elif version_type == 'podcast':
            # Host:, Guest: 와 [Intro Music Fades Out] 같은 부분 제거
            lines = text.split('\n')
            cleaned_lines = []
            current_speaker = None
            
            for line in lines:
                line = line.strip()
                # [] 로 둘러싸인 부분 건너뛰기
                if re.match(r'^\[.*\]', line):
                    continue
                # Host:, Guest: 처리
                if line.startswith('Host:'):
                    current_speaker = 'Host'
                    content = line.replace('Host:', '').strip()
                    if content:
                        cleaned_lines.append(content)
                elif line.startswith('Guest:'):
                    current_speaker = 'Guest'
                    content = line.replace('Guest:', '').strip()
                    if content:
                        cleaned_lines.append(content)
                elif line and not re.match(r'^\[.*\]', line):
                    # [] 부분 제거
                    cleaned_line = re.sub(r'\[.*?\]', '', line).strip()
                    if cleaned_line:
                        cleaned_lines.append(cleaned_line)
            
            return '\n'.join(cleaned_lines)
        
        elif version_type == 'daily':
            # A:, B: 와 Setting: 같은 부분 제거
            lines = text.split('\n')
            cleaned_lines = []
            
            for line in lines:
                line = line.strip()
                # Setting: 으로 시작하는 라인 건너뛰기
                if line.startswith('Setting:'):
                    continue
                # [] 로 둘러싸인 부분 건너뛰기
                if re.match(r'^\[.*\]', line):
                    continue
                # A:, B: 처리
                if line.startswith('A:'):
                    content = line.replace('A:', '').strip()
                    if content:
                        cleaned_lines.append(content)
                elif line.startswith('B:'):
                    content = line.replace('B:', '').strip()
                    if content:
                        cleaned_lines.append(content)
                elif line and not re.match(r'^\[.*\]', line):
                    # [] 부분 제거
                    cleaned_line = re.sub(r'\[.*?\]', '', line).strip()
                    if cleaned_line:
                        cleaned_lines.append(cleaned_line)
            
            return '\n'.join(cleaned_lines)
        
        else:
            # 원본은 그대로 반환
            return text
            
    except Exception as e:
        st.warning(f"대화 내용 추출 중 오류: {str(e)}")
        return text


def extract_role_dialogues(text, version_type):
    """역할별 대화 추출 (2인 대화용)"""
    try:
        dialogues = {'role1': [], 'role2': []}
        
        if version_type == 'podcast':
            # Host, Guest 역할 분리
            lines = text.split('\n')
            for line in lines:
                line = line.strip()
                if line.startswith('Host:'):
                    content = line.replace('Host:', '').strip()
                    # [] 부분 제거
                    content = re.sub(r'\[.*?\]', '', content).strip()
                    if content:
                        dialogues['role1'].append(content)
                elif line.startswith('Guest:'):
                    content = line.replace('Guest:', '').strip()
                    # [] 부분 제거
                    content = re.sub(r'\[.*?\]', '', content).strip()
                    if content:
                        dialogues['role2'].append(content)
            
            return {
                'host': '\n'.join(dialogues['role1']),
                'guest': '\n'.join(dialogues['role2'])
            }
        
        elif version_type == 'daily':
            # A, B 역할 분리
            lines = text.split('\n')
            for line in lines:
                line = line.strip()
                if line.startswith('A:'):
                    content = line.replace('A:', '').strip()
                    # [] 부분 제거
                    content = re.sub(r'\[.*?\]', '', content).strip()
                    if content:
                        dialogues['role1'].append(content)
                elif line.startswith('B:'):
                    content = line.replace('B:', '').strip()
                    # [] 부분 제거
                    content = re.sub(r'\[.*?\]', '', content).strip()
                    if content:
                        dialogues['role2'].append(content)
            
            return {
                'a': '\n'.join(dialogues['role1']),
                'b': '\n'.join(dialogues['role2'])
            }
        
        return None
        
    except Exception as e:
        st.warning(f"역할별 대화 추출 중 오류: {str(e)}")
        return None


def generate_audio_with_fallback(text, engine='auto', voice='en', openai_api_key=None, openai_voice=None, version_type=None):
    """개선된 TTS 생성 (Multi-Voice 지원)"""
    try:
        # OpenAI TTS 사용
        if engine == 'openai' and openai_api_key and openai_voice:
            # 2인 대화인 경우 역할별 처리
            if version_type in ['podcast', 'daily']:
                role_dialogues = extract_role_dialogues(text, version_type)
                if role_dialogues:
                    audio_files = {}
                    voice1 = st.session_state.get('tts_voice1', 'alloy')
                    voice2 = st.session_state.get('tts_voice2', 'nova')
                    
                    # 첫 번째 역할 (Host/A)
                    role1_key = 'host' if version_type == 'podcast' else 'a'
                    if role_dialogues[role1_key]:
                        audio1 = generate_audio_with_openai_tts(
                            role_dialogues[role1_key], openai_api_key, voice1
                        )
                        if audio1:
                            audio_files[role1_key] = audio1
                    
                    # 두 번째 역할 (Guest/B)
                    role2_key = 'guest' if version_type == 'podcast' else 'b'
                    if role_dialogues[role2_key]:
                        audio2 = generate_audio_with_openai_tts(
                            role_dialogues[role2_key], openai_api_key, voice2
                        )
                        if audio2:
                            audio_files[role2_key] = audio2
                    
                    return audio_files if audio_files else None
            
            # 단일 음성 (원본, TED)
            cleaned_text = extract_dialogue_content(text, version_type)
            return generate_audio_with_openai_tts(cleaned_text, openai_api_key, openai_voice)
        
        # 기존 TTS 엔진들 (fallback)
        try:
            from tts_module import generate_audio_with_fallback as tts_generate
            cleaned_text = extract_dialogue_content(text, version_type)
            return tts_generate(cleaned_text, engine, voice)
        except ImportError:
            pass
        
        # 간단한 gTTS fallback
        try:
            from gtts import gTTS
            cleaned_text = extract_dialogue_content(text, version_type)
            tts = gTTS(text=cleaned_text, lang='en' if voice.startswith('en') else voice)
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.mp3')
            tts.save(temp_file.name)
            return temp_file.name
        except:
            pass
        
        return None
        
    except Exception as e:
        st.error(f"음성 생성 실패: {str(e)}")
        return None


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
        'tts_voice1': 'alloy',  # 기본값을 OpenAI 호환으로 변경
        'tts_voice2': 'nova',   # 기본값을 OpenAI 호환으로 변경
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
        st.write("📝 통합 저장 시작...")
        
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
    """수정된 결과 표시 함수 (Multi-Audio 지원)"""
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
            translation_key = f"{version}_korean_translation"
            
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
                
                # 오디오 재생
                if audio_key in results and results[audio_key]:
                    st.markdown("### 🎧 Audio")
                    audio_data = results[audio_key]
                    
                    # 단일 오디오 파일인 경우
                    if isinstance(audio_data, str) and os.path.exists(audio_data):
                        st.audio(audio_data, format='audio/mp3')
                    
                    # 다중 오디오 파일인 경우 (딕셔너리)
                    elif isinstance(audio_data, dict):
                        if version == 'podcast':
                            col1, col2 = st.columns(2)
                            with col1:
                                if 'host' in audio_data and os.path.exists(audio_data['host']):
                                    st.markdown("**🎤 Host (음성언어-1)**")
                                    st.audio(audio_data['host'], format='audio/mp3')
                            with col2:
                                if 'guest' in audio_data and os.path.exists(audio_data['guest']):
                                    st.markdown("**🎙️ Guest (음성언어-2)**")
                                    st.audio(audio_data['guest'], format='audio/mp3')
                        
                        elif version == 'daily':
                            col1, col2 = st.columns(2)
                            with col1:
                                if 'a' in audio_data and os.path.exists(audio_data['a']):
                                    st.markdown("**👤 Person A (음성언어-1)**")
                                    st.audio(audio_data['a'], format='audio/mp3')
                            with col2:
                                if 'b' in audio_data and os.path.exists(audio_data['b']):
                                    st.markdown("**👥 Person B (음성언어-2)**")
                                    st.audio(audio_data['b'], format='audio/mp3')
                    else:
                        st.warning("오디오 파일을 찾을 수 없습니다.")
                        st.markdown(get_browser_tts_script(results[script_key]), unsafe_allow_html=True)
                else:
                    st.markdown(get_browser_tts_script(results[script_key]), unsafe_allow_html=True)
                
                # 한국어 번역 표시 (원본 + 모든 버전)
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
                
                # TED, 팟캐스트, 일상대화의 한국어 번역
                elif translation_key in results and results[translation_key]:
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
                        ">{results[translation_key]}</div>
                    </div>
                    ''', unsafe_allow_html=True)


def script_creation_page():
    """스크립트 생성 페이지 (Enhanced Multi-Voice)"""
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
    
    # 생성 버튼
    if st.button("🚀 스크립트 생성하기", type="primary", key="generate_script_main"):
        # API 키 확인
        if not st.session_state.api_key:
            st.error("먼저 설정에서 API Key를 입력해주세요!")
            return
        
        # 입력 내용 확인
        if not input_content.strip():
            st.error("내용을 입력해주세요!")
            return
        
        # 버전 선택 확인
        if not selected_versions:
            st.error("생성할 버전을 선택해주세요!")
            return
        
        # 세션 상태 업데이트
        st.session_state.input_content = input_content
        st.session_state.input_method = input_method
        st.session_state.category = category
        st.session_state.selected_versions = selected_versions
        
        # 진행 상황 표시
        progress_container = st.empty()
        
        try:
            with progress_container.container():
                st.markdown("### 📊 생성 진행상황")
                
                # LLM 프로바이더 초기화
                llm_provider = SimpleLLMProvider(
                    st.session_state.api_provider,
                    st.session_state.api_key,
                    st.session_state.model
                )
                
                if not llm_provider.client:
                    st.error("LLM 클라이언트 초기화 실패. API 키와 설정을 확인해주세요.")
                    return
                
                results = {}
                
                st.write("1️⃣ 영어 스크립트 생성 중...")
                
                # 원본 스크립트 생성 프롬프트 (제목 포함)
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
                6. Include both English and Korean titles
                
                Format your response as:
                ENGLISH TITLE: [Create a clear, descriptive English title]
                KOREAN TITLE: [Create a clear, descriptive Korean title]
                
                SCRIPT:
                [Your natural English script here]
                """
                
                original_response = llm_provider.generate_content(original_prompt)
                
                if original_response:
                    # 제목과 스크립트 분리
                    english_title = "Generated Script"
                    korean_title = "생성된 스크립트"
                    script_content = original_response
                    
                    lines = original_response.split('\n')
                    for line in lines:
                        if line.startswith('ENGLISH TITLE:'):
                            english_title = line.replace('ENGLISH TITLE:', '').strip()
                        elif line.startswith('KOREAN TITLE:'):
                            korean_title = line.replace('KOREAN TITLE:', '').strip()
                    
                    script_start = original_response.find('SCRIPT:')
                    if script_start != -1:
                        script_content = original_response[script_start+7:].strip()
                    
                    results['title'] = english_title
                    results['korean_title'] = korean_title
                    results['original_script'] = script_content
                    st.write("✅ 영어 스크립트 생성 완료")
                    
                    # 한국어 번역 생성
                    if 'original' in selected_versions:
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
                    
                    # 원본 음성 생성
                    if 'original' in selected_versions:
                        st.write("3️⃣ 원본 음성 생성 중...")
                        
                        if st.session_state.tts_engine == 'openai':
                            original_audio = generate_audio_with_fallback(
                                script_content, 
                                'openai',
                                None,
                                st.session_state.api_key,
                                st.session_state.tts_voice1,  # 음성언어-1 사용
                                'original'
                            )
                        else:
                            original_audio = generate_audio_with_fallback(
                                script_content, 
                                st.session_state.tts_engine, 
                                st.session_state.tts_voice1
                            )
                        
                        results['original_audio'] = original_audio
                        st.write("✅ 원본 음성 생성 완료" if original_audio else "⚠️ 원본 음성 생성 실패")
                    
                    # 버전별 스크립트 생성
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
                        7. Add [Opening Hook], [Main Point 1], etc. markers for structure
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
                        6. Format as "Host: [dialogue]" and "Guest: [dialogue]"
                        7. Add [Intro Music Fades Out], [Background ambiance] etc. for atmosphere
                        """,
                        
                        'daily': f"""
                        Transform the following script into a practical daily conversation.
                        
                        Original Script:
                        {script_content}
                        
                        Requirements:
                        1. Create realistic daily situation dialogue between two people
                        2. Use common, practical expressions
                        3. Include polite phrases and natural responses
                        4. Make it useful for real-life situations
                        5. Around 300 words
                        6. Format as "A: [dialogue]" and "B: [dialogue]"
                        7. Add "Setting: [location/situation]" at the beginning
                        """
                    }
                    
                    # 각 버전별 생성
                    step_counter = 4
                    for version in selected_versions:
                        if version == 'original':
                            continue
                        
                        if version in version_prompts:
                            st.write(f"{step_counter}️⃣ {version.upper()} 버전 생성 중...")
                            
                            version_content = llm_provider.generate_content(version_prompts[version])
                            if version_content:
                                results[f"{version}_script"] = version_content
                                st.write(f"✅ {version.upper()} 스크립트 생성 완료")
                                
                                # 한국어 번역 생성
                                st.write(f"🌏 {version.upper()} 한국어 번역 생성 중...")
                                translation_prompt = f"""
                                Translate the following {version.upper()} script to natural, fluent Korean.
                                Maintain the dialogue format and structure.
                                Keep stage directions like [Opening Hook], Host:, Guest:, A:, B:, Setting: in their original form.
                                
                                English Text:
                                {version_content}
                                
                                Provide the Korean translation:
                                """
                                
                                korean_translation = llm_provider.generate_content(translation_prompt)
                                if korean_translation:
                                    results[f"{version}_korean_translation"] = korean_translation
                                    st.write(f"✅ {version.upper()} 한국어 번역 완료")
                                
                                # 버전별 음성 생성
                                st.write(f"🔊 {version.upper()} 음성 생성 중...")
                                
                                if st.session_state.tts_engine == 'openai':
                                    if version == 'ted':
                                        # TED는 음성언어-2 사용
                                        version_audio = generate_audio_with_fallback(
                                            version_content,
                                            'openai',
                                            None,
                                            st.session_state.api_key,
                                            st.session_state.tts_voice2,  # 음성언어-2
                                            version
                                        )
                                    else:
                                        # 팟캐스트, 일상대화는 2인 음성
                                        version_audio = generate_audio_with_fallback(
                                            version_content,
                                            'openai',
                                            None,
                                            st.session_state.api_key,
                                            None,  # 다중 음성이므로 None
                                            version
                                        )
                                else:
                                    version_audio = generate_audio_with_fallback(
                                        version_content,
                                        st.session_state.tts_engine,
                                        st.session_state.tts_voice1,
                                        None,
                                        None,
                                        version
                                    )
                                
                                results[f"{version}_audio"] = version_audio
                                
                                if version_audio:
                                    if isinstance(version_audio, dict):
                                        st.write(f"✅ {version.upper()} 다중 음성 생성 완료")
                                    else:
                                        st.write(f"✅ {version.upper()} 음성 생성 완료")
                                else:
                                    st.write(f"⚠️ {version.upper()} 음성 생성 실패")
                            else:
                                st.warning(f"⚠️ {version.upper()} 스크립트 생성 실패")
                        
                        step_counter += 1
                    
                    # 결과 저장
                    st.session_state.script_results = results
                    st.session_state.show_results = True
                    
                    # 백업 저장
                    backup_id = save_to_temp_backup_fixed(results, input_content, input_method, category)
                    if backup_id:
                        st.info(f"💾 임시 저장 완료 (ID: {backup_id})")
                    
                    st.success("🎉 모든 콘텐츠 생성이 완료되었습니다!")
                    
                    # 페이지 새로고침
                    time.sleep(1)
                    st.rerun()
                    
                else:
                    st.error("⌫ 영어 스크립트 생성 실패")
        
        except Exception as e:
            st.error(f"⌫ 스크립트 생성 중 오류 발생: {str(e)}")
            st.error("다시 시도해주세요.")
        
        finally:
            progress_container.empty()


def practice_page_with_sync():
    """동기화 기능이 포함된 연습하기 페이지 (Multi-Audio 지원)"""
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
                st.error("⛔ 동기화 오류")
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
        
        st.write(f"📊 연결 상태: ✅ 성공")
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
                                audio_data = project_content[audio_key]
                                
                                # 단일 오디오 파일인 경우
                                if isinstance(audio_data, str) and os.path.exists(audio_data):
                                    st.audio(audio_data, format='audio/mp3')
                                
                                # 다중 오디오 파일인 경우
                                elif isinstance(audio_data, dict):
                                    if version_type == 'podcast':
                                        if 'host' in audio_data and os.path.exists(audio_data['host']):
                                            st.markdown("**🎤 Host (음성언어-1)**")
                                            st.audio(audio_data['host'], format='audio/mp3')
                                        if 'guest' in audio_data and os.path.exists(audio_data['guest']):
                                            st.markdown("**🎙️ Guest (음성언어-2)**")
                                            st.audio(audio_data['guest'], format='audio/mp3')
                                    
                                    elif version_type == 'daily':
                                        if 'a' in audio_data and os.path.exists(audio_data['a']):
                                            st.markdown("**👤 Person A (음성언어-1)**")
                                            st.audio(audio_data['a'], format='audio/mp3')
                                        if 'b' in audio_data and os.path.exists(audio_data['b']):
                                            st.markdown("**👥 Person B (음성언어-2)**")
                                            st.audio(audio_data['b'], format='audio/mp3')
                                else:
                                    st.warning("오디오 파일을 찾을 수 없습니다.")
                                    st.markdown(get_browser_tts_script(content), unsafe_allow_html=True)
                            else:
                                # 음성 생성 옵션 제공
                                st.markdown("#### 🔊 새 음성 생성")
                                
                                # TTS 엔진 선택
                                tts_col1, tts_col2 = st.columns(2)
                                with tts_col1:
                                    tts_engine = st.selectbox(
                                        "TTS 엔진",
                                        ['OpenAI TTS', 'gTTS', 'Browser TTS'],
                                        key=f"tts_engine_{version_type}_{project_id}"
                                    )
                                
                                with tts_col2:
                                    if tts_engine == 'OpenAI TTS':
                                        voice_options = {
                                            'Alloy (남성, 중성)': 'alloy',
                                            'Echo (남성)': 'echo', 
                                            'Fable (남성, 영국식)': 'fable',
                                            'Onyx (남성, 깊은 목소리)': 'onyx',
                                            'Nova (여성)': 'nova',
                                            'Shimmer (여성)': 'shimmer'
                                        }
                                        selected_voice_name = st.selectbox(
                                            "목소리 선택", 
                                            list(voice_options.keys()),
                                            key=f"voice_{version_type}_{project_id}"
                                        )
                                        selected_voice = voice_options[selected_voice_name]
                                    else:
                                        selected_voice = 'en'
                                
                                if st.button(f"🔊 음성 생성", key=f"generate_tts_{version_type}_{project_id}"):
                                    if not st.session_state.api_key and tts_engine == 'OpenAI TTS':
                                        st.error("OpenAI API Key가 필요합니다!")
                                    else:
                                        with st.spinner("음성 생성 중..."):
                                            if tts_engine == 'OpenAI TTS':
                                                new_audio = generate_audio_with_fallback(
                                                    content,
                                                    'openai',
                                                    None,
                                                    st.session_state.api_key,
                                                    selected_voice,
                                                    version_type
                                                )
                                            else:
                                                new_audio = generate_audio_with_fallback(
                                                    content,
                                                    'auto',
                                                    'en',
                                                    None,
                                                    None,
                                                    version_type
                                                )
                                            
                                            if new_audio:
                                                try:
                                                    project_path = Path(list(metadata['saved_files'].values())[0]).parent
                                                    audio_folder = project_path / "audio"
                                                    
                                                    # 단일 오디오인 경우
                                                    if isinstance(new_audio, str) and os.path.exists(new_audio):
                                                        audio_dest = audio_folder / f"{version_type}_audio_new.mp3"
                                                        shutil.copy2(new_audio, audio_dest)
                                                        st.audio(str(audio_dest), format='audio/mp3')
                                                        st.success("음성 생성 및 저장 완료!")
                                                    
                                                    # 다중 오디오인 경우
                                                    elif isinstance(new_audio, dict):
                                                        for role, audio_path in new_audio.items():
                                                            if os.path.exists(audio_path):
                                                                audio_dest = audio_folder / f"{version_type}_audio_{role}_new.mp3"
                                                                shutil.copy2(audio_path, audio_dest)
                                                                st.markdown(f"**{role.upper()}**")
                                                                st.audio(str(audio_dest), format='audio/mp3')
                                                        st.success("다중 음성 생성 및 저장 완료!")
                                                    
                                                except Exception as e:
                                                    # 저장 실패해도 재생은 가능
                                                    if isinstance(new_audio, str):
                                                        st.audio(new_audio, format='audio/mp3')
                                                    elif isinstance(new_audio, dict):
                                                        for role, audio_path in new_audio.items():
                                                            st.markdown(f"**{role.upper()}**")
                                                            st.audio(audio_path, format='audio/mp3')
                                                    st.warning(f"음성 생성은 끝났지만 저장 실패: {e}")
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
                        
                        # 한국어 번역 표시
                        translation_key = f"{version_type}_korean_translation"
                        if version_type == 'original' and 'korean_translation' in project_content:
                            st.markdown("### 🇰🇷 한국어 번역")
                            st.markdown(f'''
                            <div class="script-container">
                                <div class="translation-text" style="font-style: italic; color: #666;">{project_content["korean_translation"]}</div>
                            </div>
                            ''', unsafe_allow_html=True)
                        elif translation_key in project_content:
                            st.markdown("### 🇰🇷 한국어 번역")
                            st.markdown(f'''
                            <div class="script-container">
                                <div class="translation-text" style="font-style: italic; color: #666;">{project_content[translation_key]}</div>
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
                                            translation_key = f"{version_type}_korean_translation"
                                            
                                            if script_key in project_content:
                                                st.markdown(f"**{version_name}**")
                                                content = project_content[script_key]
                                                preview = content[:200] + "..." if len(content) > 200 else content
                                                st.markdown(preview)
                                                
                                                if translation_key in project_content:
                                                    st.markdown("*한국어 번역:*")
                                                    translation = project_content[translation_key]
                                                    translation_preview = translation[:200] + "..." if len(translation) > 200 else translation
                                                    st.markdown(f"*{translation_preview}*")
                                                
                                                st.markdown("---")
                                    
                                    if st.button("닫기", key=f"close_file_{project['project_id']}"):
                                        st.session_state[f"show_file_detail_{project['project_id']}"] = False
                                        st.rerun()
    else:
        st.info("저장된 프로젝트가 없습니다.")
        st.markdown("**스크립트 생성** 탭에서 새로운 프로젝트를 만들어보세요! 🚀")


def settings_page_with_oauth_drive():
    """OAuth 2.0 Google Drive 설정이 포함된 설정 페이지 (Enhanced Multi-Voice TTS)"""
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
                
                st.markdown("#### 📝 OAuth 2.0 클라이언트 JSON 입력")
                
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
                                    st.error("⛔ Google Drive 연결 실패")
                                    
                            except Exception as e:
                                st.error(f"⛔ 연결 오류: {str(e)}")
                                
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
                                    st.error("⛔ 재인증 실패")
                                    
                            except Exception as e:
                                st.error(f"⛔ 재인증 오류: {str(e)}")
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
            st.error("⛔ Google Drive API 라이브러리가 설치되지 않았습니다.")
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
    
    # Enhanced Multi-Voice TTS 설정
    with st.expander("🔊 Enhanced Multi-Voice TTS 설정", expanded=True):
        st.markdown("### 🎵 음성 엔진 선택")
        
        engine_options = ['auto (자동)', 'OpenAI TTS', 'gTTS', 'pyttsx3']
        selected_engine = st.selectbox("TTS 엔진", engine_options)
        
        if selected_engine == 'OpenAI TTS':
            st.session_state.tts_engine = 'openai'
        else:
            st.session_state.tts_engine = 'auto' if selected_engine == 'auto (자동)' else selected_engine
        
        # if selected_engine == 'OpenAI TTS':
        #     st.markdown("### 🎤 Multi-Voice 설정")
        #     st.info("**음성언어-1**: 원본 스크립트, Host/A 역할\n**음성언어-2**: TED 말하기, Guest/B 역할")
            
        #     voice_options = {
        #         'Alloy (중성, 균형잡힌)': 'alloy',
        #         'Echo (남성, 명확한)': 'echo', 
        #         'Fable (남성, 영국 억양)': 'fable',
        #         'Onyx (남성, 깊고 강한)': 'onyx',
        #         'Nova (여성, 부드러운)': 'nova',
        #         'Shimmer (여성, 따뜻한)': 'shimmer'
        #     }
            
        #     col1, col2 = st.columns(2)
            
        #     with col1:
        #         st.markdown("#### 🎙️ 음성언어-1")
        #         st.markdown("*원본 스크립트, Host, Person A*")
        #         selected_voice1_name = st.selectbox(
        #             "음성언어-1 선택", 
        #             list(voice_options.keys()),
        #             index=list(voice_options.values()).index(st.session_state.tts_voice1),
        #             key="voice1_select"
        #         )
        #         st.session_state.tts_voice1 = voice_options[selected_voice1_name]
            
        #     with col2:
        #         st.markdown("#### 🎤 음성언어-2")
        #         st.markdown("*TED 말하기, Guest, Person B*")
        #         selected_voice2_name = st.selectbox(
        #             "음성언어-2 선택", 
        #             list(voice_options.keys()),
        #             index=list(voice_options.values()).index(st.session_state.tts_voice2),
        #             key="voice2_select"
        #         )
        #         st.session_state.tts_voice2 = voice_options[selected_voice2_name]

        if selected_engine == 'OpenAI TTS':
            st.markdown("### 🎤 Multi-Voice 설정")
            st.info("**음성언어-1**: 원본 스크립트, Host/A 역할\n**음성언어-2**: TED 말하기, Guest/B 역할")
            
            voice_options = {
                'Alloy (중성, 균형잡힌)': 'alloy',
                'Echo (남성, 명확한)': 'echo', 
                'Fable (남성, 영국 억양)': 'fable',
                'Onyx (남성, 깊고 강한)': 'onyx',
                'Nova (여성, 부드러운)': 'nova',
                'Shimmer (여성, 따뜻한)': 'shimmer'
            }
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("#### 🎙️ 음성언어-1")
                st.markdown("*원본 스크립트, Host, Person A*")
                
                # 기본값 처리 - 현재 값이 voice_options에 없으면 'alloy'로 설정
                current_voice1 = st.session_state.tts_voice1
                if current_voice1 not in voice_options.values():
                    current_voice1 = 'alloy'
                    st.session_state.tts_voice1 = 'alloy'
                
                # index 찾기 - 안전한 방식으로
                try:
                    current_index1 = list(voice_options.values()).index(current_voice1)
                except ValueError:
                    current_index1 = 0  # alloy가 첫 번째
                    st.session_state.tts_voice1 = 'alloy'
                
                selected_voice1_name = st.selectbox(
                    "음성언어-1 선택", 
                    list(voice_options.keys()),
                    index=current_index1,
                    key="voice1_select"
                )
                st.session_state.tts_voice1 = voice_options[selected_voice1_name]
            
            with col2:
                st.markdown("#### 🎤 음성언어-2")
                st.markdown("*TED 말하기, Guest, Person B*")
                
                # 기본값 처리 - 현재 값이 voice_options에 없으면 'nova'로 설정
                current_voice2 = st.session_state.tts_voice2
                if current_voice2 not in voice_options.values():
                    current_voice2 = 'nova'
                    st.session_state.tts_voice2 = 'nova'
                
                # index 찾기 - 안전한 방식으로
                try:
                    current_index2 = list(voice_options.values()).index(current_voice2)
                except ValueError:
                    current_index2 = 4  # nova가 다섯 번째
                    st.session_state.tts_voice2 = 'nova'
                
                selected_voice2_name = st.selectbox(
                    "음성언어-2 선택", 
                    list(voice_options.keys()),
                    index=current_index2,
                    key="voice2_select"
                )
                st.session_state.tts_voice2 = voice_options[selected_voice2_name]

            # 음성 적용 규칙 설명
            st.markdown("### 📋 음성 적용 규칙")
            st.markdown("""
            | 스크립트 유형 | 음성 배정 | 설명 |
            |--------------|-----------|------|
            | **원본 스크립트** | 음성언어-1 | 단일 화자 |
            | **TED 3분 말하기** | 음성언어-2 | 단일 화자 (프레젠테이션) |
            | **팟캐스트 대화** | Host: 음성언어-1<br>Guest: 음성언어-2 | 2인 대화 |
            | **일상 대화** | Person A: 음성언어-1<br>Person B: 음성언어-2 | 2인 대화 |
            """)
            
        else:
            # 기존 TTS 음성 옵션
            st.markdown("### 🌐 기본 TTS 언어 설정")
            voice_options = {
                '영어 (미국)': 'en',
                '영어 (영국)': 'en-uk', 
                '영어 (호주)': 'en-au',
                '한국어': 'ko'
            }
            selected_voice_name = st.selectbox("음성 언어", list(voice_options.keys()))
            st.session_state.tts_voice1 = voice_options[selected_voice_name]
            st.session_state.tts_voice2 = voice_options[selected_voice_name]
        
        # TTS 테스트
        st.markdown("### 🎵 TTS 테스트")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("🎙️ 음성언어-1 테스트"):
                test_text = "Hello, this is voice one testing. I am the host or person A."
                
                if st.session_state.tts_engine == 'openai':
                    if not st.session_state.api_key:
                        st.error("OpenAI API Key가 필요합니다!")
                    else:
                        with st.spinner("음성언어-1 테스트 중..."):
                            test_audio = generate_audio_with_openai_tts(
                                test_text,
                                st.session_state.api_key,
                                st.session_state.tts_voice1
                            )
                            if test_audio:
                                st.audio(test_audio, format='audio/mp3')
                                st.success("음성언어-1 테스트 완료!")
                            else:
                                st.error("음성언어-1 테스트 실패")
                else:
                    with st.spinner("음성 생성 중..."):
                        test_audio = generate_audio_with_fallback(
                            test_text,
                            st.session_state.tts_engine,
                            st.session_state.tts_voice1
                        )
                        if test_audio:
                            st.audio(test_audio, format='audio/mp3')
                            st.success("음성언어-1 테스트 완료!")
                        else:
                            st.error("음성언어-1 테스트 실패")
        
        with col2:
            if st.button("🎤 음성언어-2 테스트"):
                test_text = "Hello, this is voice two testing. I am the guest or person B."
                
                if st.session_state.tts_engine == 'openai':
                    if not st.session_state.api_key:
                        st.error("OpenAI API Key가 필요합니다!")
                    else:
                        with st.spinner("음성언어-2 테스트 중..."):
                            test_audio = generate_audio_with_openai_tts(
                                test_text,
                                st.session_state.api_key,
                                st.session_state.tts_voice2
                            )
                            if test_audio:
                                st.audio(test_audio, format='audio/mp3')
                                st.success("음성언어-2 테스트 완료!")
                            else:
                                st.error("음성언어-2 테스트 실패")
                else:
                    with st.spinner("음성 생성 중..."):
                        test_audio = generate_audio_with_fallback(
                            test_text,
                            st.session_state.tts_engine,
                            st.session_state.tts_voice2
                        )
                        if test_audio:
                            st.audio(test_audio, format='audio/mp3')
                            st.success("음성언어-2 테스트 완료!")
                        else:
                            st.error("음성언어-2 테스트 실패")
    
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
                            st.error(f"⛔ Drive API 테스트 실패: {test_message}")
                        
                    except Exception as e:
                        st.error(f"⛔ Drive 테스트 오류: {str(e)}")
                else:
                    st.warning("⚠️ Google Drive가 연결되지 않았습니다.")


def main():
    """메인 애플리케이션 (Enhanced Multi-Voice TTS 버전)"""
    st.set_page_config(
        page_title="MyTalk - Enhanced Multi-Voice TTS",
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
        .tts-info {
            background: linear-gradient(135deg, #e3f2fd, #f1f8e9);
            padding: 1rem;
            border-radius: 10px;
            margin: 0.5rem 0;
            border-left: 4px solid #2196F3;
        }
        .voice-assignment {
            background: linear-gradient(135deg, #fff3e0, #e8f5e8);
            padding: 0.8rem;
            border-radius: 8px;
            margin: 0.3rem 0;
            border-left: 3px solid #ff9800;
        }
    </style>
    """, unsafe_allow_html=True)
    
    # 헤더
    st.markdown("""
    <div style='text-align: center; padding: 1rem; background: linear-gradient(90deg, #4CAF50, #45a049); border-radius: 10px; margin-bottom: 2rem;'>
        <h1 style='color: white; margin: 0;'>🎙️ MyTalk</h1>
        <p style='color: white; margin: 0; opacity: 0.9;'>Enhanced Multi-Voice TTS with OAuth 2.0 Google Drive</p>
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
                ⛔ Google Drive 동기화 오류 발생 | 설정을 확인해주세요
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
    
    # Multi-Voice TTS 엔진 상태 표시
    if st.session_state.tts_engine == 'openai':
        if st.session_state.api_key:
            st.markdown(f"""
            <div class="voice-assignment">
                🎵 <strong>Enhanced Multi-Voice TTS 활성화</strong><br>
                🎙️ <strong>음성언어-1</strong>: {st.session_state.tts_voice1.title()} (원본, Host, A)<br>
                🎤 <strong>음성언어-2</strong>: {st.session_state.tts_voice2.title()} (TED, Guest, B)
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown("""
            <div class="sync-status sync-error">
                ⚠️ Enhanced Multi-Voice TTS 선택됨 | API Key 필요 (설정에서 입력)
            </div>
            """, unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div class="tts-info">
            🔊 <strong>TTS 엔진:</strong> {st.session_state.tts_engine.title()} | <strong>언어:</strong> {st.session_state.tts_voice1.upper()}
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
    drive_status_text = "☁️ OAuth 2.0 Google Drive" if sync_status['drive_enabled'] else "📱 Local Mode"
    
    if st.session_state.tts_engine == 'openai':
        tts_status_text = f"🎵 Multi-Voice TTS ({st.session_state.tts_voice1}/{st.session_state.tts_voice2})"
    else:
        tts_status_text = f"🔊 {st.session_state.tts_engine.title()}"
    
    st.markdown(f"""
    <div style='text-align: center; color: #666; font-size: 0.8rem; margin-top: 2rem;'>
        <p>MyTalk v5.0 with Enhanced Multi-Voice TTS + OAuth 2.0 Google Drive</p>
        <p>{drive_status_text} | {tts_status_text}</p>
        <p>Made with ❤️ using Streamlit | 원스톱 영어 학습 솔루션</p>
    </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()