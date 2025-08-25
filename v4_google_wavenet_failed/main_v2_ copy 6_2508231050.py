"""
MyTalk - 스크립트 생성 결과 유지 문제 해결
주요 수정사항:
1. 스크립트 생성 결과를 세션 상태에 안정적으로 저장
2. 화면 새로고침 후에도 결과 유지
3. 진행 상황 표시 개선
4. 누락된 script_creation_page() 함수 추가
5. 결과 표시 로직 개선
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
import time
import uuid
import shutil

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


class FileBasedStorage:
    """파일 기반 저장 시스템"""
    
    def __init__(self, base_dir="mytalk_data"):
        self.base_dir = Path(base_dir)
        self.scripts_dir = self.base_dir / "scripts"
        self.audio_dir = self.base_dir / "audio"
        self.metadata_dir = self.base_dir / "metadata"
        
        # 디렉토리 생성
        self.scripts_dir.mkdir(parents=True, exist_ok=True)
        self.audio_dir.mkdir(parents=True, exist_ok=True)
        self.metadata_dir.mkdir(parents=True, exist_ok=True)
    
    def save_project_to_files(self, results, input_content, input_method, category):
        """프로젝트를 파일로 저장"""
        try:
            # 프로젝트 ID 생성
            project_id = datetime.now().strftime("%Y%m%d_%H%M%S")
            title = results.get('title', f'Script_{project_id}')
            
            # 안전한 파일명 생성
            safe_title = self.sanitize_filename(title)
            project_folder = self.scripts_dir / f"{project_id}_{safe_title}"
            project_folder.mkdir(exist_ok=True)
            
            # 프로젝트 폴더 내 하위 폴더들
            audio_folder = project_folder / "audio"
            audio_folder.mkdir(exist_ok=True)
            
            saved_files = {}
            
            # 1. 메타데이터 저장
            metadata = {
                'project_id': project_id,
                'title': title,
                'category': category,
                'input_method': input_method,
                'input_content': input_content,
                'created_at': datetime.now().isoformat(),
                'versions': []
            }
            
            # 2. 원본 스크립트 저장
            if 'original_script' in results:
                original_file = project_folder / "original_script.txt"
                with open(original_file, 'w', encoding='utf-8') as f:
                    f.write(results['original_script'])
                saved_files['original_script'] = str(original_file)
                metadata['versions'].append('original')
                
                st.write(f"✅ 원본 스크립트 저장: {original_file.name}")
            
            # 3. 한국어 번역 저장
            if 'korean_translation' in results:
                translation_file = project_folder / "korean_translation.txt"
                with open(translation_file, 'w', encoding='utf-8') as f:
                    f.write(results['korean_translation'])
                saved_files['korean_translation'] = str(translation_file)
                
                st.write(f"✅ 한국어 번역 저장: {translation_file.name}")
            
            # 4. 각 버전별 스크립트 및 오디오 저장
            versions = ['ted', 'podcast', 'daily']
            
            for version in versions:
                script_key = f"{version}_script"
                audio_key = f"{version}_audio"
                
                # 스크립트 파일 저장
                if script_key in results and results[script_key]:
                    script_file = project_folder / f"{version}_script.txt"
                    with open(script_file, 'w', encoding='utf-8') as f:
                        f.write(results[script_key])
                    saved_files[script_key] = str(script_file)
                    metadata['versions'].append(version)
                    
                    st.write(f"✅ {version.upper()} 스크립트 저장: {script_file.name}")
                
                # 오디오 파일 저장
                if audio_key in results and results[audio_key]:
                    audio_src = results[audio_key]
                    if os.path.exists(audio_src):
                        # 오디오 파일을 프로젝트 폴더로 복사
                        audio_ext = Path(audio_src).suffix or '.mp3'
                        audio_dest = audio_folder / f"{version}_audio{audio_ext}"
                        shutil.copy2(audio_src, audio_dest)
                        saved_files[audio_key] = str(audio_dest)
                        
                        st.write(f"✅ {version.upper()} 오디오 저장: {audio_dest.name}")
            
            # 5. 원본 오디오 저장
            if 'original_audio' in results and results['original_audio']:
                audio_src = results['original_audio']
                if os.path.exists(audio_src):
                    audio_ext = Path(audio_src).suffix or '.mp3'
                    audio_dest = audio_folder / f"original_audio{audio_ext}"
                    shutil.copy2(audio_src, audio_dest)
                    saved_files['original_audio'] = str(audio_dest)
                    
                    st.write(f"✅ 원본 오디오 저장: {audio_dest.name}")
            
            # 6. 메타데이터 최종 저장
            metadata['saved_files'] = saved_files
            metadata_file = project_folder / "metadata.json"
            with open(metadata_file, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2)
            
            # 7. 프로젝트 인덱스 업데이트
            self.update_project_index(project_id, title, category, str(project_folder))
            
            st.success(f"🎉 파일 저장 완료! 프로젝트 폴더: {project_folder.name}")
            st.success(f"📊 저장된 파일: {len(saved_files)}개")
            
            return project_id, str(project_folder)
            
        except Exception as e:
            st.error(f"⛔ 파일 저장 실패: {str(e)}")
            return None, None
    
    def sanitize_filename(self, filename):
        """안전한 파일명 생성"""
        # 허용되지 않는 문자 제거
        safe_chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_() "
        safe_filename = ''.join(c for c in filename if c in safe_chars)
        safe_filename = ' '.join(safe_filename.split())[:50]  # 길이 제한
        return safe_filename.strip() or "Untitled"
    
    def update_project_index(self, project_id, title, category, project_path):
        """프로젝트 인덱스 업데이트"""
        try:
            index_file = self.base_dir / "project_index.json"
            
            # 기존 인덱스 로드
            if index_file.exists():
                with open(index_file, 'r', encoding='utf-8') as f:
                    index_data = json.load(f)
            else:
                index_data = {"projects": []}
            
            # 새 프로젝트 추가
            new_project = {
                'project_id': project_id,
                'title': title,
                'category': category,
                'project_path': project_path,
                'created_at': datetime.now().isoformat()
            }
            
            index_data["projects"].append(new_project)
            
            # 최신순 정렬
            index_data["projects"].sort(key=lambda x: x['created_at'], reverse=True)
            
            # 인덱스 저장
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
                
                # 프로젝트 폴더가 실제로 존재하는지 확인
                if project_path.exists():
                    # 메타데이터 로드
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
            
            # 모든 스크립트 파일 로드
            for file_type, file_path in target_project['saved_files'].items():
                if 'script' in file_type or 'translation' in file_type:
                    if os.path.exists(file_path):
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content[file_type] = f.read()
                elif 'audio' in file_type:
                    # 오디오 파일 경로만 저장
                    if os.path.exists(file_path):
                        content[file_type] = file_path
            
            # 메타데이터 포함
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
                # 프로젝트 폴더 삭제
                project_path = Path(list(target_project['saved_files'].values())[0]).parent
                if project_path.exists():
                    shutil.rmtree(project_path)
                
                # 인덱스에서 제거
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
            
            # 메인 스크립트 테이블
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
            
            # 연습 버전 테이블
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
            # 데이터 검증
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
            
            # 저장 확인
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
            
            # 메인 스크립트 정보
            c.execute('SELECT * FROM scripts WHERE id = ?', (script_id,))
            script = c.fetchone()
            
            # 연습 버전들
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


class SimpleTTSManager:
    def __init__(self):
        self.available_engines = []
        try:
            import gtts
            self.available_engines.append('gTTS')
        except ImportError:
            pass


def generate_audio_with_fallback(text, engine='auto', voice='en'):
    """간단한 TTS 생성 (폴백)"""
    try:
        from tts_module import generate_audio_with_fallback as tts_generate
        return tts_generate(text, engine, voice)
    except ImportError:
        # tts_module이 없으면 None 반환
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


def init_session_state():
    """세션 상태 초기화"""
    defaults = {
        'api_provider': 'OpenAI',
        'api_key': '',
        'model': 'gpt-4o-mini',
        'current_project': None,
        'generation_progress': {},
        'tts_engine': 'auto',
        'tts_voice': 'en',
        'google_drive_enabled': False,
        'google_credentials': None,
        'file_projects': [],
        # 스크립트 생성 결과 관련
        'script_results': None,
        'show_results': False,
        'selected_versions': None,
        'input_content': '',
        'input_method': 'text',
        'category': '일반',
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
        
        # 임시 폴더 생성
        temp_backup_dir = Path("temp_backups")
        temp_backup_dir.mkdir(exist_ok=True)
        
        # JSON 저장
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


def cleanup_temp_backup_fixed(backup_id):
    """수정된 임시 백업 정리"""
    try:
        backup_dir = Path("temp_backups")
        json_path = backup_dir / f"backup_{backup_id}.json"
        
        if json_path.exists():
            json_path.unlink()
            return True
        return False
        
    except Exception as e:
        st.warning(f"백업 정리 실패: {str(e)}")
        return False


def save_to_files_and_db(results, input_content, input_method, category):
    """파일과 데이터베이스에 동시 저장"""
    try:
        st.write("📁 통합 저장 시작...")
        
        # 1. 파일 시스템에 저장
        file_storage = FileBasedStorage()
        project_id, project_path = file_storage.save_project_to_files(
            results, input_content, input_method, category
        )
        
        if not project_id:
            raise Exception("파일 저장 실패")
        
        st.write(f"✅ 파일 저장 완료: {project_path}")
        
        # 2. 데이터베이스에도 저장 (기존 방식 유지)
        try:
            db = FixedDatabase()
            
            title = results.get('title', f'Script_{project_id}')
            original_script = results.get('original_script', '')
            korean_translation = results.get('korean_translation', '')
            
            # 메인 스크립트 저장
            script_id = db.create_script_project(
                title=title,
                original_content=original_script,
                korean_translation=korean_translation,
                category=category,
                input_type=input_method.lower(),
                input_data=f"file_project_id:{project_id}"  # 파일 프로젝트 ID 연결
            )
            
            # 각 버전별 저장
            for version_type in ['ted', 'podcast', 'daily']:
                script_key = f"{version_type}_script"
                if script_key in results and results[script_key]:
                    db.add_practice_version(
                        script_id=script_id,
                        version_type=version_type,
                        content=results[script_key],
                        audio_path=f"file_project_id:{project_id}"  # 파일 참조
                    )
            
            st.write(f"✅ 데이터베이스 저장 완료 (ID: {script_id})")
            
        except Exception as db_error:
            st.warning(f"⚠️ 데이터베이스 저장 실패: {db_error}")
            st.info("파일 저장은 성공했으므로 데이터는 보존됩니다.")
        
        # 3. 세션 상태 업데이트
        st.session_state.last_save_time = datetime.now().isoformat()
        st.session_state.last_project_id = project_id
        st.session_state.file_projects = file_storage.load_all_projects()  # 전체 목록 갱신
        
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
                
                # 음성 재생
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


def script_creation_page():
    """스크립트 생성 페이지"""
    st.header("✏️ 스크립트 작성")
    
    # 현재 결과가 있는지 확인하고 표시
    if st.session_state.show_results and st.session_state.script_results:
        st.success("🎉 생성된 스크립트가 있습니다!")
        
        # 저장 버튼을 상단에 배치
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
                    # 상태 초기화
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
            if st.button("📥 백업에서 복원", key="restore_backup"):
                backups = get_recent_backups_fixed(5)
                if backups:
                    st.session_state.show_backup_restore = True
                else:
                    st.info("복원 가능한 백업이 없습니다.")
        
        # 기존 결과 표시
        display_results_fixed(st.session_state.script_results, st.session_state.selected_versions)
        
        # 백업 복원 UI
        if st.session_state.get('show_backup_restore', False):
            st.markdown("---")
            st.markdown("### 📥 백업에서 복원")
            
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
    
    # 새로운 스크립트 생성 UI
    st.markdown("### 📝 새 스크립트 만들기")
    
    # 카테고리와 버전 선택
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
    
    # 입력 방법 선택
    input_method = st.radio(
        "입력 방법 선택",
        ["텍스트", "이미지", "파일"],
        horizontal=True
    )
    
    # 입력 내용
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
        
        # 세션 상태에 현재 설정 저장
        st.session_state.input_content = input_content
        st.session_state.input_method = input_method
        st.session_state.category = category
        st.session_state.selected_versions = selected_versions
        
        # 진행상황 표시
        progress_container = st.empty()
        
        with progress_container.container():
            st.markdown("### 📊 생성 진행상황")
            
            # LLM 제공자 초기화
            llm_provider = SimpleLLMProvider(
                st.session_state.api_provider,
                st.session_state.api_key,
                st.session_state.model
            )
            
            results = {}
            
            # 1. 원본 영어 스크립트 생성
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
                # 제목과 스크립트 분리
                title = "Generated Script"
                script_content = original_response
                
                # TITLE 추출
                lines = original_response.split('\n')
                for line in lines:
                    if line.startswith('TITLE:'):
                        title = line.replace('TITLE:', '').strip()
                        break
                
                # SCRIPT 부분 추출
                script_start = original_response.find('SCRIPT:')
                if script_start != -1:
                    script_content = original_response[script_start+7:].strip()
                
                results['title'] = title
                results['original_script'] = script_content
                st.write("✅ 영어 스크립트 생성 완료")
                
                # 2. 한국어 번역
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
                
                # 3. 원본 음성 생성
                st.write("3️⃣ 원본 음성 생성 중...")
                original_audio = generate_audio_with_fallback(
                    script_content, 
                    st.session_state.tts_engine, 
                    st.session_state.tts_voice
                )
                results['original_audio'] = original_audio
                st.write("✅ 원본 음성 생성 완료" if original_audio else "⚠️ 원본 음성 생성 실패")
                
                # 4. 각 버전별 생성
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
                            
                            # 음성 생성
                            st.write(f"🔊 {version.upper()} 음성 생성 중...")
                            version_audio = generate_audio_with_fallback(
                                version_content,
                                st.session_state.tts_engine,
                                st.session_state.tts_voice
                            )
                            results[f"{version}_audio"] = version_audio
                            st.write(f"✅ {version.upper()} 음성 생성 완료" if version_audio else f"⚠️ {version.upper()} 음성 생성 실패")
                        else:
                            st.warning(f"⚠️ {version.upper()} 스크립트 생성 실패")
                
                # 5. 결과를 세션 상태에 저장
                st.session_state.script_results = results
                st.session_state.show_results = True
                
                # 임시 백업 저장
                backup_id = save_to_temp_backup_fixed(results, input_content, input_method, category)
                if backup_id:
                    st.info(f"💾 임시 저장 완료 (ID: {backup_id})")
                
                st.success("🎉 모든 콘텐츠 생성이 완료되었습니다!")
                
                # 페이지 새로고침을 통해 결과 표시
                time.sleep(1)
                st.rerun()
                
            else:
                st.error("⛔ 영어 스크립트 생성 실패")
        
        progress_container.empty()


def practice_page_fixed():
    """파일 기반 연습하기 페이지"""
    st.header("🎯 연습하기")
    
    # 파일 저장소 초기화
    file_storage = FileBasedStorage()
    
    # 새로고침 버튼
    col1, col2 = st.columns([3, 1])
    with col1:
        if hasattr(st.session_state, 'last_save_time'):
            st.info(f"🆕 마지막 저장: {st.session_state.last_save_time[:19]}")
    
    with col2:
        if st.button("🔄 새로고침"):
            # 파일에서 프로젝트 목록 다시 로드
            st.session_state.file_projects = file_storage.load_all_projects()
            st.rerun()
    
    try:
        # 파일에서 프로젝트 로드
        if 'file_projects' not in st.session_state:
            st.session_state.file_projects = file_storage.load_all_projects()
        
        projects = st.session_state.file_projects
        
        st.write(f"📊 파일 저장소 연결: ✅ 성공")
        st.write(f"📋 로드된 프로젝트 수: {len(projects)}")
        
        if not projects:
            st.warning("저장된 프로젝트가 없습니다.")
            st.markdown("**스크립트 생성** 탭에서 새로운 스크립트를 만들어보세요! 🚀")
            return
        
        # 프로젝트 선택
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
            
            # 프로젝트 내용 로드
            project_content = file_storage.load_project_content(project_id)
            
            if not project_content:
                st.error(f"프로젝트 {project_id}를 로드할 수 없습니다")
                return
            
            metadata = project_content['metadata']
            
            # 프로젝트 정보 표시
            st.markdown("### 📄 프로젝트 정보")
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.markdown(f"**제목**: {metadata['title']}")
            with col2:
                st.markdown(f"**카테고리**: {metadata['category']}")
            with col3:
                st.markdown(f"**생성일**: {metadata['created_at'][:10]}")
            
            # 사용 가능한 버전들 구성
            available_versions = []
            
            # 원본 버전
            if 'original_script' in project_content:
                available_versions.append(('original', '원본 스크립트', project_content['original_script']))
            
            # 다른 버전들
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
            
            # 탭으로 버전들 표시
            if available_versions:
                tab_names = [v[1] for v in available_versions]
                tabs = st.tabs(tab_names)
                
                for i, (version_type, version_name, content) in enumerate(available_versions):
                    with tabs[i]:
                        # 스크립트 내용 표시
                        st.markdown(f"### 📃 {version_name}")
                        
                        # 스크립트 컨테이너
                        st.markdown(f'''
                        <div class="script-container">
                            <div class="script-text">{content}</div>
                        </div>
                        ''', unsafe_allow_html=True)
                        
                        # 오디오 및 연습 도구
                        col1, col2 = st.columns([2, 1])
                        
                        with col2:
                            st.markdown("### 🎧 음성 연습")
                            
                            # 저장된 오디오 확인
                            audio_key = f"{version_type}_audio"
                            if audio_key in project_content:
                                audio_path = project_content[audio_key]
                                if os.path.exists(audio_path):
                                    st.audio(audio_path, format='audio/mp3')
                                else:
                                    st.warning("오디오 파일을 찾을 수 없습니다.")
                                    st.markdown(get_browser_tts_script(content), unsafe_allow_html=True)
                            else:
                                # TTS 생성 버튼
                                if st.button(f"🔊 음성 생성", key=f"tts_{version_type}_{project_id}"):
                                    with st.spinner("음성 생성 중..."):
                                        new_audio = generate_audio_with_fallback(
                                            content,
                                            st.session_state.get('tts_engine', 'auto'),
                                            st.session_state.get('tts_voice', 'en')
                                        )
                                        if new_audio and os.path.exists(new_audio):
                                            # 생성된 오디오를 프로젝트 폴더로 복사
                                            try:
                                                project_path = Path(list(metadata['saved_files'].values())[0]).parent
                                                audio_folder = project_path / "audio"
                                                audio_dest = audio_folder / f"{version_type}_audio_new.mp3"
                                                shutil.copy2(new_audio, audio_dest)
                                                
                                                st.audio(str(audio_dest), format='audio/mp3')
                                                st.success("음성 생성 및 저장 완료!")
                                            except Exception as e:
                                                st.audio(new_audio, format='audio/mp3')
                                                st.warning(f"음성 생성은 끝지만 저장 실패: {e}")
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
                        if version_type == 'original' and 'korean_translation' in project_content:
                            st.markdown("### 🇰🇷 한국어 번역")
                            st.markdown(f'''
                            <div class="script-container">
                                <div class="translation-text" style="font-style: italic; color: #666;">{project_content["korean_translation"]}</div>
                            </div>
                            ''', unsafe_allow_html=True)
                
    except Exception as e:
        st.error(f"연습 페이지 로드 오류: {str(e)}")


def my_scripts_page_fixed():
    """파일 기반 내 스크립트 페이지"""
    st.header("📚 내 스크립트")
    
    file_storage = FileBasedStorage()
    
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
    
    # 프로젝트 로드
    projects = file_storage.load_all_projects()
    
    # 필터링
    if search_query:
        projects = [p for p in projects if search_query.lower() in p['title'].lower()]
    
    if category_filter != "전체":
        projects = [p for p in projects if p['category'] == category_filter]
    
    # 정렬
    if sort_order == "제목순":
        projects.sort(key=lambda x: x['title'])
    else:
        projects.sort(key=lambda x: x['created_at'], reverse=True)
    
    # 프로젝트 표시
    if projects:
        st.write(f"총 {len(projects)}개의 프로젝트")
        
        # 그리드 형태로 표시
        for i in range(0, len(projects), 2):
            cols = st.columns(2)
            
            for j, col in enumerate(cols):
                if i + j < len(projects):
                    project = projects[i + j]
                    
                    with col:
                        with st.container():
                            # 제목과 정보
                            st.markdown(f"### 📄 {project['title']}")
                            st.markdown(f"**카테고리**: {project['category']}")
                            st.markdown(f"**생성일**: {project['created_at'][:10]}")
                            st.markdown(f"**버전**: {len(project['versions'])}개")
                            
                            # 버튼들
                            button_cols = st.columns(3)
                            
                            with button_cols[0]:
                                if st.button("📖 보기", key=f"view_file_{project['project_id']}"):
                                    st.session_state[f"show_file_detail_{project['project_id']}"] = True
                            
                            with button_cols[1]:
                                if st.button("🎯 연습", key=f"practice_file_{project['project_id']}"):
                                    st.info("연습하기 탭으로 이동해서 해당 프로젝트를 선택하세요.")
                            
                            with button_cols[2]:
                                if st.button("🗑️ 삭제", key=f"delete_file_{project['project_id']}"):
                                    if st.session_state.get(f"confirm_delete_file_{project['project_id']}"):
                                        if file_storage.delete_project(project['project_id']):
                                            st.success("삭제되었습니다!")
                                            # 프로젝트 목록 갱신
                                            st.session_state.file_projects = file_storage.load_all_projects()
                                            st.rerun()
                                    else:
                                        st.session_state[f"confirm_delete_file_{project['project_id']}"] = True
                                        st.warning("한 번 더 클릭하면 삭제됩니다.")
                            
                            # 상세 보기
                            if st.session_state.get(f"show_file_detail_{project['project_id']}"):
                                with st.expander(f"📋 {project['title']} 상세보기", expanded=True):
                                    # 프로젝트 내용 로드
                                    project_content = file_storage.load_project_content(project['project_id'])
                                    
                                    if project_content:
                                        # 원본 스크립트
                                        if 'original_script' in project_content:
                                            st.markdown("#### 🇺🇸 영어 스크립트")
                                            st.markdown(project_content['original_script'])
                                        
                                        # 한국어 번역
                                        if 'korean_translation' in project_content:
                                            st.markdown("#### 🇰🇷 한국어 번역")
                                            st.markdown(project_content['korean_translation'])
                                        
                                        # 연습 버전들
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
                                    
                                    # 닫기 버튼
                                    if st.button("닫기", key=f"close_file_{project['project_id']}"):
                                        st.session_state[f"show_file_detail_{project['project_id']}"] = False
                                        st.rerun()
    else:
        st.info("저장된 프로젝트가 없습니다.")
        st.markdown("**스크립트 생성** 탭에서 새로운 프로젝트를 만들어보세요! 🚀")


def settings_page_fixed():
    """수정된 설정 페이지"""
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
        # 간단한 TTS 설정
        col1, col2 = st.columns(2)
        
        with col1:
            engine_options = ['auto (자동)', 'gTTS', 'pyttsx3']
            selected_engine = st.selectbox("TTS 엔진", engine_options)
            st.session_state.tts_engine = 'auto' if selected_engine == 'auto (자동)' else selected_engine
        
        with col2:
            voice_options = {
                '영어 (미국)': 'en',
                '영어 (영국)': 'en-uk', 
                '영어 (호주)': 'en-au',
                '한국어': 'ko'
            }
            selected_voice_name = st.selectbox("음성 언어", list(voice_options.keys()))
            st.session_state.tts_voice = voice_options[selected_voice_name]
    
    with st.expander("🔧 데이터베이스 테스트"):
        if st.button("데이터베이스 연결 테스트"):
            try:
                db = FixedDatabase()
                test_id = db.create_script_project(
                    title="테스트 스크립트",
                    original_content="This is a test script.",
                    korean_translation="이것은 테스트 스크립트입니다.",
                    category="test"
                )
                
                # 확인
                project = db.get_script_project(test_id)
                if project['script']:
                    st.success(f"✅ 데이터베이스 테스트 성공! (ID: {test_id})")
                    
                    # 테스트 데이터 삭제
                    db.delete_script_project(test_id)
                    st.info("🗑️ 테스트 데이터 정리 완료")
                else:
                    st.error("⛔ 데이터베이스 테스트 실패")
                    
            except Exception as e:
                st.error(f"⛔ 데이터베이스 테스트 오류: {str(e)}")
        
        if st.button("현재 저장된 스크립트 확인"):
            db = FixedDatabase()
            scripts = db.get_all_scripts()
            if scripts:
                st.write(f"총 {len(scripts)}개의 스크립트가 저장되어 있습니다:")
                for script in scripts[:5]:
                    st.write(f"- {script[1]} ({script[4]}) - {script[7][:10]}")
            else:
                st.write("저장된 스크립트가 없습니다.")

        if st.button("🔨 데이터베이스 강제 초기화"):
            db = FixedDatabase()
            st.success("데이터베이스 초기화 완료!")

    with st.expander("📁 파일 저장소 관리"):
        file_storage = FileBasedStorage()
        
        if st.button("파일 저장소 상태 확인"):
            projects = file_storage.load_all_projects()
            st.write(f"파일 저장소 경로: {file_storage.base_dir}")
            st.write(f"저장된 프로젝트 수: {len(projects)}")
            
            # 디렉토리 구조 표시
            if file_storage.base_dir.exists():
                st.write("**디렉토리 구조:**")
                for item in file_storage.base_dir.rglob("*"):
                    if item.is_file():
                        relative_path = item.relative_to(file_storage.base_dir)
                        st.write(f"  📄 {relative_path}")
            else:
                st.write("파일 저장소가 아직 생성되지 않았습니다.")
        
        if st.button("🧹 임시 백업 정리"):
            backup_dir = Path("temp_backups")
            if backup_dir.exists():
                backup_files = list(backup_dir.glob("backup_*.json"))
                if backup_files:
                    for backup_file in backup_files:
                        try:
                            backup_file.unlink()
                        except:
                            pass
                    st.success(f"🗑️ {len(backup_files)}개의 임시 백업 파일을 정리했습니다.")
                else:
                    st.info("정리할 임시 백업이 없습니다.")
            else:
                st.info("임시 백업 폴더가 없습니다.")


def main():
    """메인 애플리케이션"""
    # 페이지 설정
    st.set_page_config(
        page_title="MyTalk - 영어 말하기 학습",
        page_icon="🎙️",
        layout="wide",
        initial_sidebar_state="collapsed"
    )
    
    # 세션 상태 초기화
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
        @media (max-width: 768px) {
            .stApp {
                padding: 0.5rem;
            }
            .script-text {
                font-size: 1rem;
            }
        }
        
        /* 컨테이너 스타일 개선 */
        .stContainer > div {
            border: 1px solid #e0e0e0;
            border-radius: 10px;
            padding: 1rem;
            margin: 0.5rem 0;
        }
        
        /* 탭 스타일 개선 */
        .stTabs [data-baseweb="tab-list"] {
            gap: 8px;
        }
        
        .stTabs [data-baseweb="tab"] {
            background-color: #f0f2f6;
            border-radius: 8px;
            padding: 8px 16px;
        }
        
        /* 성공/오류 메시지 스타일 */
        .stSuccess {
            border-radius: 10px;
            padding: 1rem;
        }
        
        .stError {
            border-radius: 10px;
            padding: 1rem;
        }
        
        .stWarning {
            border-radius: 10px;
            padding: 1rem;
        }
        
        .stInfo {
            border-radius: 10px;
            padding: 1rem;
        }
    </style>
    """, unsafe_allow_html=True)
    
    # 모바일 친화적 헤더
    st.markdown("""
    <div style='text-align: center; padding: 1rem; background: linear-gradient(90deg, #4CAF50, #45a049); border-radius: 10px; margin-bottom: 2rem;'>
        <h1 style='color: white; margin: 0;'>🎙️ MyTalk</h1>
        <p style='color: white; margin: 0; opacity: 0.9;'>나만의 영어 말하기 학습 앱</p>
    </div>
    """, unsafe_allow_html=True)
    
    # 네비게이션 탭
    tab1, tab2, tab3, tab4 = st.tabs(["✏️ 스크립트 작성", "🎯 연습하기", "📚 내 스크립트", "⚙️ 설정"])
    
    with tab1:
        script_creation_page()
    
    with tab2:
        practice_page_fixed()
    
    with tab3:
        my_scripts_page_fixed()
    
    with tab4:
        settings_page_fixed()
    
    # 푸터
    st.markdown("---")
    st.markdown("""
    <div style='text-align: center; color: #666; font-size: 0.8rem; margin-top: 2rem;'>
        <p>MyTalk v2.0 | Personal English Learning Assistant</p>
        <p>Made with ❤️ using Streamlit | 원스톱 영어 학습 솔루션</p>
    </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()