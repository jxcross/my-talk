"""
MyTalk - 완전 수정 버전
주요 수정사항:
1. 스크립트 생성 페이지 완전 구현
2. 로컬 저장 기능 완전 수정
3. 연습하기 페이지 완전 수정
4. 데이터베이스 참조 통일
5. 누락된 함수들 추가
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

# LLM Providers (기본 import만)
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
# 수정된 데이터베이스 클래스 (통일된 버전)
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

# =============================================================================
# 간단한 TTS 관리자 (tts_module.py가 없을 경우 대비)
# =============================================================================

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

# =============================================================================
# 간단한 LLM 제공자
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
                    messages=[{"role": "user", "content": content}]
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
# 초기화 함수
# =============================================================================

def init_session_state():
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
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

# =============================================================================
# 임시 백업 함수들
# =============================================================================

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

# =============================================================================
# 로컬 저장 함수
# =============================================================================

def save_to_local_db_fixed(results, input_content, input_method, category):
    """수정된 로컬 저장 함수"""
    try:
        st.write("🔍 저장 시작...")
        
        # 결과 데이터 검증
        if not results:
            raise ValueError("저장할 결과가 없습니다")
        
        title = results.get('title', f"Script_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
        original_script = results.get('original_script', '')
        korean_translation = results.get('korean_translation', '')
        
        if not original_script:
            raise ValueError("원본 스크립트가 비어있습니다")
        
        st.write(f"제목: {title}")
        st.write(f"원본 길이: {len(original_script)} 문자")
        st.write(f"카테고리: {category}")
        
        # 데이터베이스 저장
        db = FixedDatabase()
        
        # 1. 메인 스크립트 저장
        st.write("1️⃣ 메인 스크립트 저장 중...")
        script_id = db.create_script_project(
            title=title,
            original_content=original_script,
            korean_translation=korean_translation,
            category=category,
            input_type=input_method.lower(),
            input_data=input_content[:1000] if input_content else ''
        )
        
        st.write(f"✅ 메인 스크립트 저장됨 (ID: {script_id})")
        
        # 2. 각 버전별 저장
        version_types = ['ted', 'podcast', 'daily']
        saved_versions = []
        
        for version_type in version_types:
            script_key = f"{version_type}_script"
            audio_key = f"{version_type}_audio"
            
            if script_key in results and results[script_key]:
                st.write(f"2️⃣ {version_type.upper()} 버전 저장 중...")
                
                try:
                    version_id = db.add_practice_version(
                        script_id=script_id,
                        version_type=version_type,
                        content=results[script_key],
                        audio_path=results.get(audio_key, '')
                    )
                    saved_versions.append(f"{version_type}(ID:{version_id})")
                    st.write(f"✅ {version_type} 버전 저장 완료")
                except Exception as ve:
                    st.warning(f"⚠️ {version_type} 저장 실패: {ve}")
                    continue
        
        # 3. 저장 확인
        st.write("3️⃣ 저장 검증 중...")
        saved_project = db.get_script_project(script_id)
        
        if saved_project['script'] and saved_project['script'][1]:
            st.success(f"🎉 저장 완료! 스크립트 ID: {script_id}")
            st.success(f"📊 저장된 내용: 메인 스크립트 + {len(saved_versions)}개 연습 버전")
            
            # 세션 상태 업데이트
            st.session_state.last_save_time = datetime.now().isoformat()
            st.session_state.last_saved_script_id = script_id
            
            return True
        else:
            raise Exception("저장 확인 실패")
        
    except Exception as e:
        st.error(f"❌ 저장 실패: {str(e)}")
        return False

# =============================================================================
# 스크립트 생성 페이지 (완전 구현)
# =============================================================================

def script_creation_page():
    """완전히 수정된 스크립트 생성 페이지"""
    st.header("✏️ 영어 스크립트 생성")

    # 임시 백업 복구 섹션
    with st.expander("📄 임시 백업 복구"):
        recent_backups = get_recent_backups_fixed()
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
                        restored_data = load_temp_backup_fixed(backup['id'])
                        if restored_data:
                            st.session_state.current_project = restored_data['results']
                            st.session_state.current_backup_id = backup['id']
                            st.success("✅ 백업 복구 완료!")
                            st.rerun()
        else:
            st.info("저장된 임시 백업이 없습니다.")
    
    # 복구된 콘텐츠가 있는 경우 표시
    if hasattr(st.session_state, 'current_project') and st.session_state.current_project:
        results = st.session_state.current_project
        st.markdown("### 📋 복구된 콘텐츠")
        display_results_fixed(results, ['original', 'ted', 'podcast', 'daily'])
        
        st.markdown("---")
        st.markdown("### 💾 복구된 콘텐츠 저장")
        
        col1, col2 = st.columns([1, 1])
        
        with col1:
            if st.button("💾 로컬 저장", type="primary", key="save_restored_local"):
                success = save_to_local_db_fixed(
                    results,
                    st.session_state.get('restored_input_content', ''),
                    st.session_state.get('restored_input_method', 'text'),
                    st.session_state.get('restored_category', 'general')
                )
                if success:
                    # 백업 정리
                    if hasattr(st.session_state, 'current_backup_id'):
                        cleanup_temp_backup_fixed(st.session_state.current_backup_id)
                        del st.session_state.current_backup_id
                        del st.session_state.current_project
                    st.balloons()
                    st.rerun()
        
        return  # 복구된 콘텐츠가 있으면 새 생성 UI는 표시하지 않음
    
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
        selected_versions = ["original"]  # 원본은 필수
        
        if st.checkbox("TED 3분 말하기", value=True):
            selected_versions.append("ted")
        if st.checkbox("팟캐스트 대화", value=True):
            selected_versions.append("podcast")
        if st.checkbox("일상 대화", value=True):
            selected_versions.append("daily")
    
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
    if st.button("🚀 스크립트 생성하기", type="primary"):
        if not st.session_state.api_key:
            st.error("먼저 설정에서 API Key를 입력해주세요!")
            return
        
        if not input_content:
            st.error("내용을 입력해주세요!")
            return
        
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
                
                # 임시 백업 저장
                backup_id = save_to_temp_backup_fixed(results, input_content, input_method, category)
                if backup_id:
                    st.info(f"💾 임시 저장 완료 (ID: {backup_id})")
                    st.session_state.current_backup_id = backup_id
                
                st.session_state.current_project = results
                
                # 결과 표시
                st.success("🎉 모든 콘텐츠 생성이 완료되었습니다!")
                display_results_fixed(results, selected_versions)
                
                # 저장 버튼
                st.markdown("---")
                st.markdown("### 💾 저장하기")
                
                col1, col2 = st.columns([1, 1])
                
                with col1:
                    if st.button("💾 로컬 저장", type="primary", key="save_local_main"):
                        success = save_to_local_db_fixed(results, input_content, input_method, category)
                        if success:
                            # 백업 정리
                            if backup_id:
                                cleanup_temp_backup_fixed(backup_id)
                                if hasattr(st.session_state, 'current_backup_id'):
                                    del st.session_state.current_backup_id
                                if hasattr(st.session_state, 'current_project'):
                                    del st.session_state.current_project
                            st.balloons()
                            st.info("💡 '연습하기' 또는 '내 스크립트' 탭에서 저장된 내용을 확인하세요!")
                            time.sleep(2)
                            st.rerun()
                
                with col2:
                    if st.session_state.google_drive_enabled:
                        if st.button("☁️ Google Drive 저장", type="secondary", key="save_gdrive_main"):
                            st.info("Google Drive 저장 기능은 현재 개발 중입니다.")
                    else:
                        st.info("Google Drive 저장을 위해서는 설정에서 연동이 필요합니다.")
            
            else:
                st.error("❌ 영어 스크립트 생성 실패")
        
        progress_container.empty()

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

# =============================================================================
# 연습하기 페이지 (완전 수정)
# =============================================================================

def practice_page_fixed():
    """완전히 수정된 연습하기 페이지"""
    st.header("🎯 연습하기")
    
    # 데이터베이스 연결
    db = FixedDatabase()
    
    # 새로고침 버튼
    col1, col2 = st.columns([3, 1])
    with col1:
        if hasattr(st.session_state, 'last_save_time'):
            st.info(f"🆕 마지막 저장: {st.session_state.last_save_time[:19]}")
    
    with col2:
        if st.button("🔄 새로고침"):
            st.rerun()
    
    try:
        # 스크립트 목록 조회
        scripts = db.get_all_scripts()
        
        st.write(f"📊 데이터베이스 연결: {'✅ 성공' if os.path.exists(db.db_path) else '❌ 실패'}")
        st.write(f"📋 조회된 스크립트 수: {len(scripts)}")
        
        if not scripts:
            st.warning("저장된 스크립트가 없습니다.")
            
            # 디버깅 정보
            with st.expander("🔍 데이터베이스 직접 확인"):
                try:
                    conn = sqlite3.connect(db.db_path)
                    c = conn.cursor()
                    
                    # 테이블 존재 확인
                    c.execute("SELECT name FROM sqlite_master WHERE type='table'")
                    tables = [row[0] for row in c.fetchall()]
                    st.write(f"존재하는 테이블: {tables}")
                    
                    # 스크립트 테이블 직접 확인
                    if 'scripts' in tables:
                        c.execute("SELECT COUNT(*) FROM scripts")
                        count = c.fetchone()[0]
                        st.write(f"scripts 테이블의 행 수: {count}")
                        
                        if count > 0:
                            c.execute("SELECT id, title, created_at FROM scripts ORDER BY created_at DESC LIMIT 5")
                            recent = c.fetchall()
                            st.write("최근 스크립트:")
                            for r in recent:
                                st.write(f"• ID {r[0]}: {r[1]} ({r[2][:16]})")
                    
                    conn.close()
                    
                except Exception as db_error:
                    st.error(f"데이터베이스 직접 확인 오류: {db_error}")
            
            return
        
        # 스크립트가 있는 경우
        st.success(f"📚 총 {len(scripts)}개의 스크립트가 저장되어 있습니다.")
        
        # 스크립트 선택
        st.markdown("### 📖 연습할 스크립트 선택")
        
        script_options = {}
        for script in scripts:
            script_id, title, content, translation, category, input_type, input_data, created_at, updated_at = script
            display_name = f"{title} ({category}) - {created_at[:10]}"
            script_options[display_name] = script_id
        
        selected_script_name = st.selectbox(
            "스크립트 선택",
            list(script_options.keys()),
            help="연습하고 싶은 스크립트를 선택하세요"
        )
        
        if selected_script_name:
            script_id = script_options[selected_script_name]
            
            # 프로젝트 데이터 조회
            project_data = db.get_script_project(script_id)
            
            if not project_data['script']:
                st.error(f"스크립트 ID {script_id}를 찾을 수 없습니다")
                return
            
            script_info = project_data['script']
            versions = project_data['versions']
            
            # 스크립트 정보 표시
            st.markdown("### 📄 스크립트 정보")
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.markdown(f"**제목**: {script_info[1]}")
            with col2:
                st.markdown(f"**카테고리**: {script_info[4]}")
            with col3:
                st.markdown(f"**생성일**: {script_info[7][:10]}")
            
            # 사용 가능한 버전들 구성
            available_versions = [('original', '원본 스크립트', script_info[2])]
            
            # 연습 버전들 추가
            version_names = {
                'ted': 'TED 3분 말하기',
                'podcast': '팟캐스트 대화', 
                'daily': '일상 대화'
            }
            
            for version in versions:
                version_id, script_id_fk, version_type, content, audio_path, created_at = version
                if version_type in version_names:
                    available_versions.append((version_type, version_names[version_type], content))
            
            st.write(f"📊 사용 가능한 버전: {len(available_versions)}개")
            
            # 탭으로 버전들 표시
            if available_versions:
                tab_names = [v[1] for v in available_versions]
                tabs = st.tabs(tab_names)
                
                for i, (version_type, version_name, content) in enumerate(available_versions):
                    with tabs[i]:
                        # 스크립트 내용 표시
                        st.markdown(f"### 📝 {version_name}")
                        
                        # 스크립트 컨테이너
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
                            ">{content}</div>
                        </div>
                        ''', unsafe_allow_html=True)
                        
                        # 오디오 및 연습 도구
                        col1, col2 = st.columns([2, 1])
                        
                        with col2:
                            st.markdown("### 🎧 음성 연습")
                            
                            # 저장된 오디오 확인
                            audio_path = None
                            if version_type != 'original':
                                for v in versions:
                                    if v[2] == version_type and v[4]:
                                        audio_path = v[4]
                                        break
                            
                            if audio_path and os.path.exists(audio_path):
                                st.audio(audio_path, format='audio/mp3')
                            else:
                                # TTS 생성 버튼
                                if st.button(f"🔊 음성 생성", key=f"tts_{version_type}_{script_id}"):
                                    with st.spinner("음성 생성 중..."):
                                        new_audio = generate_audio_with_fallback(
                                            content,
                                            st.session_state.get('tts_engine', 'auto'),
                                            st.session_state.get('tts_voice', 'en')
                                        )
                                        if new_audio and os.path.exists(new_audio):
                                            st.audio(new_audio, format='audio/mp3')
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
                                ">{script_info[3]}</div>
                            </div>
                            ''', unsafe_allow_html=True)
                
    except Exception as e:
        st.error(f"연습 페이지 로드 오류: {str(e)}")

# =============================================================================
# 내 스크립트 페이지 (수정)
# =============================================================================

def my_scripts_page_fixed():
    """수정된 내 스크립트 페이지"""
    st.header("📚 내 스크립트")
    
    db = FixedDatabase()
    
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

# =============================================================================
# 설정 페이지 (수정)
# =============================================================================

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
                    st.error("❌ 데이터베이스 테스트 실패")
                    
            except Exception as e:
                st.error(f"❌ 데이터베이스 테스트 오류: {str(e)}")
        
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

# =============================================================================
# 메인 앱
# =============================================================================

def main():
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