"""
MyTalk - 오디오 생성 문제 해결된 버전
주요 수정사항:
1. extract_role_dialogues 함수의 대화 추출 로직 개선
2. generate_multi_voice_audio 함수의 오류 처리 강화
3. 텍스트 정리 및 검증 로직 추가
4. 디버깅 정보 향상
"""

import streamlit as st
import os
import json
import tempfile
from PIL import Image
import time
import uuid
import shutil
from pathlib import Path
from datetime import datetime
import re

# OpenAI Library
try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    st.error("OpenAI 라이브러리가 필요합니다. pip install openai로 설치해주세요.")


class SimpleStorage:
    """간소화된 로컬 파일 저장소"""
    
    def __init__(self, base_dir="mytalk_data"):
        self.base_dir = Path(base_dir)
        self.scripts_dir = self.base_dir / "scripts"
        self.audio_dir = self.base_dir / "audio"
        
        self.scripts_dir.mkdir(parents=True, exist_ok=True)
        self.audio_dir.mkdir(parents=True, exist_ok=True)
    
    def sanitize_filename(self, filename):
        """안전한 파일명 생성"""
        safe_chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_() "
        safe_filename = ''.join(c for c in filename if c in safe_chars)
        safe_filename = ' '.join(safe_filename.split())[:50]
        return safe_filename.strip() or "Untitled"
    
    def save_project(self, results, input_content, input_method, category):
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


class SimpleLLMProvider:
    def __init__(self, api_key, model):
        self.api_key = api_key
        self.model = model
        self.client = None
        self.setup_client()
    
    def setup_client(self):
        """클라이언트 초기화"""
        try:
            if OPENAI_AVAILABLE and self.api_key:
                self.client = openai.OpenAI(api_key=self.api_key)
        except Exception as e:
            st.error(f"LLM 클라이언트 초기화 실패: {str(e)}")
    
    def generate_content(self, prompt):
        """간단한 콘텐츠 생성"""
        try:
            if not self.client or not self.api_key:
                return None
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=2000,
                temperature=0.7
            )
            return response.choices[0].message.content
        
        except Exception as e:
            st.error(f"LLM 호출 실패: {str(e)}")
            return None


def generate_audio_with_openai_tts(text, api_key, voice='alloy'):
    """OpenAI TTS API를 사용한 음성 생성"""
    try:
        if not OPENAI_AVAILABLE:
            raise ImportError("OpenAI 라이브러리가 설치되지 않았습니다")
        
        if not text or not text.strip():
            st.warning(f"빈 텍스트로 인해 {voice} 음성 생성을 건너뜁니다.")
            return None
        
        # OpenAI 클라이언트 설정
        client = openai.OpenAI(api_key=api_key)
        
        # TTS 요청
        response = client.audio.speech.create(
            model="tts-1",
            voice=voice,
            input=text.strip()
        )
        
        # 임시 파일에 저장 (스트림 경고 해결)
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.mp3')
        
        # 응답 내용을 직접 쓰기
        with open(temp_file.name, 'wb') as f:
            for chunk in response.iter_bytes(chunk_size=1024):
                f.write(chunk)
        
        temp_file.close()
        
        # 파일이 생성되었는지 확인
        if os.path.exists(temp_file.name) and os.path.getsize(temp_file.name) > 0:
            return temp_file.name
        else:
            st.error(f"음성 파일 생성 실패: {voice}")
            return None
        
    except Exception as e:
        st.error(f"OpenAI TTS 생성 실패 ({voice}): {str(e)}")
        return None


def clean_text_for_tts(text):
    """TTS를 위한 텍스트 정리 - 개선된 버전"""
    try:
        if not text or not isinstance(text, str):
            return ""
        
        # [ ... ] 로 둘러싸인 부분 제거 (지침이나 메타 정보)
        text = re.sub(r'\[.*?\]', '', text)
        
        # ** ... ** 로 둘러싸인 부분 제거 (볼드 텍스트)
        text = re.sub(r'\*\*.*?\*\*', '', text)
        
        # * ... * 로 둘러싸인 부분 제거 (이탤릭)
        text = re.sub(r'\*([^*]+)\*', r'\1', text)
        
        # 마크다운 헤더 제거 (###, ##, # 등)
        text = re.sub(r'^#+\s*', '', text, flags=re.MULTILINE)
        
        # 줄바꿈을 공백으로 변경
        text = text.replace('\n', ' ')
        text = text.replace('\r', ' ')
        
        # 여러 공백을 단일 공백으로 변경
        text = re.sub(r'\s+', ' ', text)
        
        # 앞뒤 공백 제거
        text = text.strip()
        
        return text
        
    except Exception as e:
        st.warning(f"텍스트 정리 중 오류: {str(e)}")
        return text if text else ""


def extract_role_dialogues(text, version_type):
    """역할별 대화 추출 및 정리 (개선된 버전)"""
    try:
        if not text or not isinstance(text, str):
            st.error("유효하지 않은 텍스트입니다.")
            return None
            
        st.write(f"🔍 텍스트 분석 시작...")
        st.write(f"📄 원본 텍스트 길이: {len(text)} 글자")
        
        dialogue_sequence = []  # (role, content, order) 튜플의 리스트
        
        if version_type == 'podcast':
            # Host, Guest 역할 분리 (순서 보존)
            lines = text.split('\n')
            order = 0
            host_texts = []
            guest_texts = []
            
            for line in lines:
                line = line.strip()
                if not line:  # 빈 줄 건너뛰기
                    continue
                    
                # Host로 시작하는 줄 찾기
                if line.lower().startswith('host:'):
                    content = line[5:].strip()  # 'host:' 제거
                    content = clean_text_for_tts(content)
                    if content:
                        dialogue_sequence.append(('host', content, order))
                        host_texts.append(content)
                        order += 1
                        
                # Guest로 시작하는 줄 찾기
                elif line.lower().startswith('guest:'):
                    content = line[6:].strip()  # 'guest:' 제거
                    content = clean_text_for_tts(content)
                    if content:
                        dialogue_sequence.append(('guest', content, order))
                        guest_texts.append(content)
                        order += 1
                        
                # Host나 Guest가 명시되지 않은 경우도 처리
                elif ':' in line:
                    parts = line.split(':', 1)
                    role = parts[0].strip().lower()
                    content = parts[1].strip()
                    
                    if 'host' in role or 'presenter' in role or 'interviewer' in role:
                        content = clean_text_for_tts(content)
                        if content:
                            dialogue_sequence.append(('host', content, order))
                            host_texts.append(content)
                            order += 1
                    elif 'guest' in role or 'interviewee' in role or 'speaker' in role:
                        content = clean_text_for_tts(content)
                        if content:
                            dialogue_sequence.append(('guest', content, order))
                            guest_texts.append(content)
                            order += 1
            
            # 결과가 없으면 전체 텍스트를 Host로 할당
            if not host_texts and not guest_texts:
                st.warning("Host/Guest 구분을 찾을 수 없어 전체를 Host로 처리합니다.")
                cleaned_text = clean_text_for_tts(text)
                if cleaned_text:
                    host_texts = [cleaned_text]
                    dialogue_sequence = [('host', cleaned_text, 0)]
            
            # 디버깅 정보
            st.write(f"🔍 Host 대사 수: {len(host_texts)}")
            st.write(f"🔍 Guest 대사 수: {len(guest_texts)}")
            
            if host_texts:
                st.write(f"🔍 Host 첫 대사 미리보기: {host_texts[0][:100]}...")
            if guest_texts:
                st.write(f"🔍 Guest 첫 대사 미리보기: {guest_texts[0][:100]}...")
            
            # 역할별로 분리된 텍스트와 순서 정보 반환
            return {
                'host': ' '.join(host_texts),
                'guest': ' '.join(guest_texts),
                'sequence': dialogue_sequence
            }
        
        elif version_type == 'daily':
            # A, B 역할 분리 (순서 보존)
            lines = text.split('\n')
            order = 0
            a_texts = []
            b_texts = []
            
            for line in lines:
                line = line.strip()
                if not line:  # 빈 줄 건너뛰기
                    continue
                    
                # A로 시작하는 줄 찾기
                if line.lower().startswith('a:'):
                    content = line[2:].strip()  # 'a:' 제거
                    content = clean_text_for_tts(content)
                    if content:
                        dialogue_sequence.append(('a', content, order))
                        a_texts.append(content)
                        order += 1
                        
                # B로 시작하는 줄 찾기
                elif line.lower().startswith('b:'):
                    content = line[2:].strip()  # 'b:' 제거
                    content = clean_text_for_tts(content)
                    if content:
                        dialogue_sequence.append(('b', content, order))
                        b_texts.append(content)
                        order += 1
                        
                # Person A, Person B 등의 변형도 처리
                elif ':' in line:
                    parts = line.split(':', 1)
                    role = parts[0].strip().lower()
                    content = parts[1].strip()
                    
                    if 'a' in role or 'person a' in role or 'speaker a' in role:
                        content = clean_text_for_tts(content)
                        if content:
                            dialogue_sequence.append(('a', content, order))
                            a_texts.append(content)
                            order += 1
                    elif 'b' in role or 'person b' in role or 'speaker b' in role:
                        content = clean_text_for_tts(content)
                        if content:
                            dialogue_sequence.append(('b', content, order))
                            b_texts.append(content)
                            order += 1
            
            # 결과가 없으면 전체 텍스트를 A로 할당
            if not a_texts and not b_texts:
                st.warning("A/B 구분을 찾을 수 없어 전체를 Person A로 처리합니다.")
                cleaned_text = clean_text_for_tts(text)
                if cleaned_text:
                    a_texts = [cleaned_text]
                    dialogue_sequence = [('a', cleaned_text, 0)]
            
            # 디버깅 정보
            st.write(f"🔍 Person A 대사 수: {len(a_texts)}")
            st.write(f"🔍 Person B 대사 수: {len(b_texts)}")
            
            if a_texts:
                st.write(f"🔍 Person A 첫 대사 미리보기: {a_texts[0][:100]}...")
            if b_texts:
                st.write(f"🔍 Person B 첫 대사 미리보기: {b_texts[0][:100]}...")
            
            # 역할별로 분리된 텍스트와 순서 정보 반환
            return {
                'a': ' '.join(a_texts),
                'b': ' '.join(b_texts),
                'sequence': dialogue_sequence
            }
        
        return None
        
    except Exception as e:
        st.error(f"역할별 대화 추출 중 오류: {str(e)}")
        import traceback
        st.error(f"상세 오류:\n{traceback.format_exc()}")
        return None


def merge_audio_files(audio_files, dialogue_sequence, silence_duration=0.5):
    """역할별 오디오 파일들을 대화 순서에 따라 합치기"""
    try:
        from pydub import AudioSegment
        from pydub.silence import Silence
        
        # 무음 구간 생성 (밀리초 단위)
        silence = AudioSegment.silent(duration=int(silence_duration * 1000))
        
        # 최종 합칠 오디오 세그먼트 리스트
        combined_audio = AudioSegment.empty()
        
        # 각 역할의 오디오를 문장별로 분할해야 하지만, 
        # 현재는 역할별로 전체가 하나의 파일이므로 간단히 순서대로 합치기
        
        # 실제로는 문장별 타이밍이 필요하지만, 임시로 역할별 전체 파일을 순서대로 배치
        role_order = []
        current_role = None
        
        for role, content, order in dialogue_sequence:
            if current_role != role:
                role_order.append(role)
                current_role = role
        
        # 역할 순서대로 오디오 합치기 (무음 구간 추가)
        for i, role in enumerate(role_order):
            if role in audio_files and os.path.exists(audio_files[role]):
                try:
                    audio_segment = AudioSegment.from_mp3(audio_files[role])
                    
                    if i > 0:  # 첫 번째가 아니면 무음 추가
                        combined_audio += silence
                    
                    combined_audio += audio_segment
                    
                except Exception as e:
                    st.warning(f"오디오 파일 {role} 로드 실패: {e}")
                    continue
        
        if len(combined_audio) > 0:
            # 임시 파일로 저장
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.mp3')
            combined_audio.export(temp_file.name, format="mp3")
            return temp_file.name
        
        return None
        
    except ImportError:
        st.warning("pydub 라이브러리가 필요합니다. 개별 음성 파일만 제공됩니다.")
        return None
    except Exception as e:
        st.warning(f"오디오 합치기 실패: {str(e)}. 개별 음성 파일을 제공합니다.")
        return None


def simple_merge_audio_files(audio_files):
    """pydub 없이 간단한 오디오 파일 합치기 (ffmpeg 사용)"""
    try:
        import subprocess
        
        # 임시 파일 리스트 생성
        temp_list_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt')
        
        for role, audio_file in audio_files.items():
            if os.path.exists(audio_file):
                temp_list_file.write(f"file '{audio_file}'\n")
        
        temp_list_file.close()
        
        # 출력 파일
        output_file = tempfile.NamedTemporaryFile(delete=False, suffix='.mp3')
        output_file.close()
        
        # ffmpeg로 합치기
        subprocess.run([
            'ffmpeg', '-f', 'concat', '-safe', '0', 
            '-i', temp_list_file.name, 
            '-c', 'copy', output_file.name, '-y'
        ], check=True, capture_output=True)
        
        # 임시 리스트 파일 삭제
        os.unlink(temp_list_file.name)
        
        return output_file.name
        
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    except Exception as e:
        st.warning(f"간단한 오디오 합치기 실패: {str(e)}")
        return None


def generate_multi_voice_audio(text, api_key, voice1, voice2, version_type):
    """다중 음성 오디오 생성 및 합치기 - 개선된 버전"""
    try:
        st.write(f"🎵 {version_type.upper()} 음성 생성 시작...")
        
        # 입력 텍스트 검증
        if not text or not text.strip():
            st.error(f"❌ 빈 텍스트로 인해 {version_type} 음성 생성을 건너뜁니다.")
            return None
        
        # 2인 대화인 경우 역할별 처리
        if version_type in ['podcast', 'daily']:
            st.write(f"🎭 {version_type.upper()} 대화 분석 중...")
            
            # 원본 텍스트 미리보기
            st.write(f"📄 원본 텍스트 미리보기:\n{text[:300]}...")
            
            role_dialogues = extract_role_dialogues(text, version_type)
            
            if not role_dialogues:
                st.error(f"❌ {version_type} 대화에서 역할을 찾을 수 없습니다.")
                # 대화 분석 실패 시 전체 텍스트를 첫 번째 음성으로 처리
                st.write("🔄 전체 텍스트를 단일 음성으로 처리합니다.")
                cleaned_text = clean_text_for_tts(text)
                if cleaned_text:
                    return generate_audio_with_openai_tts(cleaned_text, api_key, voice1)
                return None
                
            if 'sequence' not in role_dialogues:
                st.error(f"❌ {version_type} 대화 순서 정보가 없습니다.")
                # 순서 정보 없으면 전체 텍스트를 첫 번째 음성으로 처리
                cleaned_text = clean_text_for_tts(text)
                if cleaned_text:
                    return generate_audio_with_openai_tts(cleaned_text, api_key, voice1)
                return None
            
            audio_files = {}
            
            # 첫 번째 역할 (Host/A)
            role1_key = 'host' if version_type == 'podcast' else 'a'
            role1_text = role_dialogues.get(role1_key, '').strip()
            
            if role1_text:
                st.write(f"🎙️ {role1_key.upper()} 음성 생성 중... (길이: {len(role1_text)} 글자)")
                st.write(f"🔍 {role1_key.upper()} 텍스트 미리보기: {role1_text[:150]}...")
                
                # 텍스트가 너무 짧은지 확인
                if len(role1_text.strip()) < 10:
                    st.warning(f"⚠️ {role1_key.upper()} 텍스트가 너무 짧습니다: '{role1_text}'")
                
                audio1 = generate_audio_with_openai_tts(role1_text, api_key, voice1)
                if audio1:
                    audio_files[role1_key] = audio1
                    st.write(f"✅ {role1_key.upper()} 음성 생성 완료")
                    st.write(f"📁 {role1_key.upper()} 오디오 파일: {os.path.getsize(audio1)} bytes")
                else:
                    st.error(f"❌ {role1_key.upper()} 음성 생성 실패")
            else:
                st.warning(f"⚠️ {role1_key.upper()} 대사가 비어있습니다.")
            
            # 두 번째 역할 (Guest/B)  
            role2_key = 'guest' if version_type == 'podcast' else 'b'
            role2_text = role_dialogues.get(role2_key, '').strip()
            
            if role2_text:
                st.write(f"🎤 {role2_key.upper()} 음성 생성 중... (길이: {len(role2_text)} 글자)")
                st.write(f"🔍 {role2_key.upper()} 텍스트 미리보기: {role2_text[:150]}...")
                
                # 텍스트가 너무 짧은지 확인
                if len(role2_text.strip()) < 10:
                    st.warning(f"⚠️ {role2_key.upper()} 텍스트가 너무 짧습니다: '{role2_text}'")
                
                audio2 = generate_audio_with_openai_tts(role2_text, api_key, voice2)
                if audio2:
                    audio_files[role2_key] = audio2
                    st.write(f"✅ {role2_key.upper()} 음성 생성 완료")
                    st.write(f"📁 {role2_key.upper()} 오디오 파일: {os.path.getsize(audio2)} bytes")
                else:
                    st.error(f"❌ {role2_key.upper()} 음성 생성 실패")
            else:
                st.warning(f"⚠️ {role2_key.upper()} 대사가 비어있습니다.")
            
            # 생성된 음성 파일 확인
            st.write(f"🎵 생성된 음성 파일 수: {len(audio_files)}")
            
            # 음성 파일이 하나도 없으면 전체 텍스트로 단일 음성 생성 시도
            if len(audio_files) == 0:
                st.warning("⚠️ 모든 역할의 음성 생성에 실패했습니다. 전체 텍스트로 단일 음성을 생성합니다.")
                cleaned_text = clean_text_for_tts(text)
                if cleaned_text:
                    return generate_audio_with_openai_tts(cleaned_text, api_key, voice1)
                return None
            
            # 개별 음성 파일이 있으면 합치기 시도
            if len(audio_files) >= 1:
                if len(audio_files) >= 2:
                    st.write("🔄 개별 음성을 하나로 합치는 중...")
                    
                    # pydub을 사용한 합치기 시도
                    merged_audio = merge_audio_files(audio_files, role_dialogues['sequence'])
                    
                    if not merged_audio:
                        # pydub 실패시 ffmpeg으로 간단히 합치기 시도
                        merged_audio = simple_merge_audio_files(audio_files)
                    
                    if merged_audio:
                        st.write("✅ 통합 음성 생성 완료")
                        # 개별 파일과 통합 파일 모두 반환
                        audio_files['merged'] = merged_audio
                    else:
                        st.write("⚠️ 음성 합치기 실패 - 개별 음성 파일 제공")
                else:
                    st.write("ℹ️ 단일 음성 파일만 있습니다.")
                
                return audio_files
            else:
                st.error(f"❌ {version_type} 음성 생성 완전 실패")
                return None
        
        # 단일 음성 (원본, TED)
        st.write(f"🎯 {version_type.upper()} 단일 음성 생성 중...")
        cleaned_text = clean_text_for_tts(text)
        
        if not cleaned_text:
            st.error(f"❌ 텍스트 정리 후 내용이 없습니다.")
            return None
            
        voice = voice2 if version_type == 'ted' else voice1  # TED는 음성언어-2 사용
        
        st.write(f"📄 정리된 텍스트 길이: {len(cleaned_text)} 글자")
        st.write(f"🎤 사용할 음성: {voice}")
        
        return generate_audio_with_openai_tts(cleaned_text, api_key, voice)
        
    except Exception as e:
        st.error(f"음성 생성 중 예외 발생: {str(e)}")
        import traceback
        st.error(f"상세 오류:\n{traceback.format_exc()}")
        return None


# 나머지 함수들은 원본과 동일하므로 생략...
# (init_session_state, display_results, script_creation_page, practice_page, my_scripts_page, settings_page, main 함수들)

def init_session_state():
    """세션 상태 초기화"""
    defaults = {
        'api_key': '',
        'model': 'gpt-4o-mini',
        'voice1': 'alloy',
        'voice2': 'nova',
        'script_results': None,
        'show_results': False,
        'selected_versions': None,
        'input_content': '',
        'input_method': 'text',
        'category': '일반',
        'image_description': '',
        'storage': SimpleStorage()
    }
    
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def display_results(results, selected_versions):
    """결과 표시 함수 (Multi-Audio 지원)"""
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
                        # 통합된 오디오 파일이 있으면 먼저 표시
                        if 'merged' in audio_data and os.path.exists(audio_data['merged']):
                            st.markdown("**🎵 통합 대화 음성**")
                            st.audio(audio_data['merged'], format='audio/mp3')
                            st.markdown("---")
                        
                        # 개별 음성들도 표시
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
    """스크립트 생성 페이지 (간소화된 버전)"""
    st.header("✏️ 스크립트 작성")
    
    if st.session_state.show_results and st.session_state.script_results:
        st.success("🎉 생성된 스크립트가 있습니다!")
        
        col1, col2 = st.columns([1, 1])
        
        with col1:
            if st.button("💾 저장", type="primary", key="save_existing_results"):
                storage = st.session_state.storage
                project_id, project_path = storage.save_project(
                    st.session_state.script_results, 
                    st.session_state.input_content, 
                    st.session_state.input_method, 
                    st.session_state.category
                )
                if project_id:
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
        
        display_results(st.session_state.script_results, st.session_state.selected_versions)
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
    image_description = ""
    
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
        
        image_description = st.text_area(
            "이미지 설명 추가",
            height=80,
            placeholder="이미지에 대한 추가 설명이나 생성하고 싶은 스크립트의 방향을 입력하세요 (선택사항)"
        )
        
        if uploaded_image:
            image = Image.open(uploaded_image)
            st.image(image, caption="업로드된 이미지", use_column_width=True)
            input_content = f"이 이미지를 설명하고 관련된 영어 학습 스크립트를 만들어주세요. 추가 설명: {image_description}" if image_description else "이 이미지를 설명하고 관련된 영어 학습 스크립트를 만들어주세요."
    
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
        st.session_state.image_description = image_description
        
        # 진행 상황 표시
        progress_container = st.empty()
        
        try:
            with progress_container.container():
                st.markdown("### 📊 생성 진행상황")
                
                # LLM 프로바이더 초기화
                llm_provider = SimpleLLMProvider(
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
                1. Create natural, conversational American English suitable for speaking practice
                2. Use everyday vocabulary and expressions that Americans commonly use
                3. Length: 200-300 words
                4. Include engaging expressions and practical vocabulary
                5. Make it suitable for intermediate English learners
                6. Structure with clear introduction, main content, and conclusion
                7. Include both English and Korean titles
                8. Use casual, friendly tone like Americans speak in daily life
                
                Format your response as:
                ENGLISH TITLE: [Create a clear, descriptive English title]
                KOREAN TITLE: [Create a clear, descriptive Korean title]
                
                SCRIPT:
                [Your natural American English script here]
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
                        Use conversational Korean that sounds natural.
                        
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
                        original_audio = generate_multi_voice_audio(
                            script_content,
                            st.session_state.api_key,
                            st.session_state.voice1,
                            st.session_state.voice2,
                            'original'
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
                        5. Use natural American English with TED-style language and pacing
                        6. Keep it around 400-450 words (3 minutes speaking)
                        7. Add [Opening Hook], [Main Point 1], etc. markers for structure
                        8. Use conversational, engaging tone like popular TED speakers
                        """,
                        
                        'podcast': f"""
                        Transform the following script into a natural 2-person podcast dialogue using everyday American English.
                        
                        Original Script:
                        {script_content}
                        
                        Requirements:
                        1. Create natural conversation between Host and Guest
                        2. Include follow-up questions and responses
                        3. Add conversational fillers and natural expressions that Americans use
                        4. Make it informative but casual and friendly
                        5. Around 400 words total
                        6. Format as "Host: [dialogue]" and "Guest: [dialogue]"
                        7. Add [Intro Music Fades Out], [Background ambiance] etc. for atmosphere
                        8. Use everyday vocabulary and expressions
                        """,
                        
                        'daily': f"""
                        Transform the following script into a practical daily conversation using natural American English.
                        
                        Original Script:
                        {script_content}
                        
                        Requirements:
                        1. Create realistic daily situation dialogue between two people
                        2. Use common, practical expressions that Americans use in daily life
                        3. Include polite phrases and natural responses
                        4. Make it useful for real-life situations
                        5. Around 300 words
                        6. Format as "A: [dialogue]" and "B: [dialogue]"
                        7. Add "Setting: [location/situation]" at the beginning
                        8. Use casual, friendly American conversational style
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
                                st.write(f"🌐 {version.upper()} 한국어 번역 생성 중...")
                                translation_prompt = f"""
                                Translate the following {version.upper()} script to natural, fluent Korean.
                                Maintain the dialogue format and structure.
                                Keep stage directions like [Opening Hook], Host:, Guest:, A:, B:, Setting: in their original form.
                                Use conversational Korean.
                                
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
                                version_audio = generate_multi_voice_audio(
                                    version_content,
                                    st.session_state.api_key,
                                    st.session_state.voice1,
                                    st.session_state.voice2,
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
                    
                    st.success("🎉 모든 콘텐츠 생성이 완료되었습니다!")
                    
                    # 페이지 새로고침
                    time.sleep(1)
                    st.rerun()
                    
                else:
                    st.error("❌ 영어 스크립트 생성 실패")
        
        except Exception as e:
            st.error(f"❌ 스크립트 생성 중 오류 발생: {str(e)}")
            st.error("다시 시도해주세요.")
        
        finally:
            progress_container.empty()


def practice_page():
    """연습하기 페이지 (간소화된 버전)"""
    st.header("🎯 연습하기")
    
    storage = st.session_state.storage
    
    col1, col2 = st.columns([3, 1])
    
    with col2:
        if st.button("🔄 새로고침"):
            st.rerun()
    
    try:
        projects = storage.load_all_projects()
        
        st.write(f"📊 로드된 프로젝트 수: {len(projects)}")
        
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
            info_col1, info_col2, info_col3 = st.columns(3)
            
            with info_col1:
                st.markdown(f"**제목**: {metadata['title']}")
            with info_col2:
                st.markdown(f"**카테고리**: {metadata['category']}")
            with info_col3:
                st.markdown(f"**생성일**: {metadata['created_at'][:10]}")
            
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
                                    # 통합된 오디오 파일이 있으면 먼저 표시
                                    if 'merged' in audio_data and os.path.exists(audio_data['merged']):
                                        st.markdown("**🎵 통합 대화 음성**")
                                        st.audio(audio_data['merged'], format='audio/mp3')
                                        st.markdown("---")
                                    
                                    # 개별 음성들도 표시
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


def my_scripts_page():
    """내 스크립트 페이지 (간소화된 버전)"""
    st.header("📚 내 스크립트")
    
    storage = st.session_state.storage
    
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
                            
                            button_cols = st.columns(3)
                            
                            with button_cols[0]:
                                if st.button("📖 보기", key=f"view_{project['project_id']}"):
                                    st.session_state[f"show_detail_{project['project_id']}"] = True
                            
                            with button_cols[1]:
                                if st.button("🎯 연습", key=f"practice_{project['project_id']}"):
                                    st.info("연습하기 탭으로 이동해서 해당 프로젝트를 선택하세요.")
                            
                            with button_cols[2]:
                                if st.button("🗑️ 삭제", key=f"delete_{project['project_id']}"):
                                    if st.session_state.get(f"confirm_delete_{project['project_id']}"):
                                        if storage.delete_project(project['project_id']):
                                            st.success("삭제되었습니다!")
                                            st.rerun()
                                    else:
                                        st.session_state[f"confirm_delete_{project['project_id']}"] = True
                                        st.warning("한 번 더 클릭하면 삭제됩니다.")
                            
                            if st.session_state.get(f"show_detail_{project['project_id']}"):
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
                                    
                                    if st.button("닫기", key=f"close_{project['project_id']}"):
                                        st.session_state[f"show_detail_{project['project_id']}"] = False
                                        st.rerun()
    else:
        st.info("저장된 프로젝트가 없습니다.")
        st.markdown("**스크립트 생성** 탭에서 새로운 프로젝트를 만들어보세요! 🚀")


def settings_page():
    """설정 페이지 (간소화된 버전)"""
    st.header("⚙️ 환경 설정")
    
    # LLM 설정
    with st.expander("🤖 LLM 설정", expanded=True):
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**OpenAI 설정**")
            st.info("현재는 OpenAI만 지원됩니다")
        
        with col2:
            models = ['gpt-4o-mini', 'gpt-4o', 'gpt-4-turbo', 'gpt-3.5-turbo']
            model = st.selectbox("Model 선택", models, index=models.index(st.session_state.model))
            st.session_state.model = model
        
        api_key = st.text_input(
            "OpenAI API Key",
            value=st.session_state.api_key,
            type="password",
            help="OpenAI API 키를 입력하세요"
        )
        st.session_state.api_key = api_key
    
    # Multi-Voice TTS 설정
    with st.expander("🎤 Multi-Voice TTS 설정", expanded=True):
        st.markdown("### 🎵 OpenAI TTS 음성 설정")
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
            
            # 현재 음성언어-1 설정 확인 및 기본값 처리
            current_voice1 = st.session_state.voice1
            if current_voice1 not in voice_options.values():
                current_voice1 = 'alloy'
                st.session_state.voice1 = 'alloy'
            
            try:
                current_index1 = list(voice_options.values()).index(current_voice1)
            except ValueError:
                current_index1 = 0
                st.session_state.voice1 = 'alloy'
            
            selected_voice1_name = st.selectbox(
                "음성언어-1 선택", 
                list(voice_options.keys()),
                index=current_index1,
                key="voice1_select"
            )
            st.session_state.voice1 = voice_options[selected_voice1_name]
        
        with col2:
            st.markdown("#### 🎤 음성언어-2")
            st.markdown("*TED 말하기, Guest, Person B*")
            
            # 현재 음성언어-2 설정 확인 및 기본값 처리
            current_voice2 = st.session_state.voice2
            if current_voice2 not in voice_options.values():
                current_voice2 = 'nova'
                st.session_state.voice2 = 'nova'
            
            try:
                current_index2 = list(voice_options.values()).index(current_voice2)
            except ValueError:
                current_index2 = 4  # nova가 다섯 번째
                st.session_state.voice2 = 'nova'
            
            selected_voice2_name = st.selectbox(
                "음성언어-2 선택", 
                list(voice_options.keys()),
                index=current_index2,
                key="voice2_select"
            )
            st.session_state.voice2 = voice_options[selected_voice2_name]

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
        
        # TTS 테스트
        st.markdown("### 🎵 TTS 테스트")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("🎙️ 음성언어-1 테스트"):
                test_text = "Hello, this is voice one testing. I am the host or person A."
                
                if not st.session_state.api_key:
                    st.error("OpenAI API Key가 필요합니다!")
                else:
                    with st.spinner("음성언어-1 테스트 중..."):
                        test_audio = generate_audio_with_openai_tts(
                            test_text,
                            st.session_state.api_key,
                            st.session_state.voice1
                        )
                        if test_audio:
                            st.audio(test_audio, format='audio/mp3')
                            st.success("음성언어-1 테스트 완료!")
                        else:
                            st.error("음성언어-1 테스트 실패")
        
        with col2:
            if st.button("🎤 음성언어-2 테스트"):
                test_text = "Hello, this is voice two testing. I am the guest or person B."
                
                if not st.session_state.api_key:
                    st.error("OpenAI API Key가 필요합니다!")
                else:
                    with st.spinner("음성언어-2 테스트 중..."):
                        test_audio = generate_audio_with_openai_tts(
                            test_text,
                            st.session_state.api_key,
                            st.session_state.voice2
                        )
                        if test_audio:
                            st.audio(test_audio, format='audio/mp3')
                            st.success("음성언어-2 테스트 완료!")
                        else:
                            st.error("음성언어-2 테스트 실패")
    
    # 시스템 정보
    with st.expander("📊 시스템 정보"):
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**현재 설정**")
            st.info(f"**모델**: {st.session_state.model}")
            st.info(f"**음성언어-1**: {st.session_state.voice1.title()}")
            st.info(f"**음성언어-2**: {st.session_state.voice2.title()}")
        
        with col2:
            st.markdown("**저장소 정보**")
            storage = st.session_state.storage
            projects = storage.load_all_projects()
            st.info(f"**저장된 프로젝트**: {len(projects)}개")
            st.info(f"**저장 위치**: {storage.base_dir}")
        
        # 시스템 테스트
        st.markdown("**시스템 테스트**")
        if st.button("🔧 전체 시스템 테스트"):
            with st.spinner("시스템 테스트 중..."):
                # API 키 테스트
                if st.session_state.api_key:
                    try:
                        llm_provider = SimpleLLMProvider(
                            st.session_state.api_key,
                            st.session_state.model
                        )
                        if llm_provider.client:
                            st.success("✅ OpenAI API 연결 성공")
                        else:
                            st.error("❌ OpenAI API 연결 실패")
                    except Exception as e:
                        st.error(f"❌ API 테스트 실패: {str(e)}")
                else:
                    st.warning("⚠️ API 키가 설정되지 않았습니다")
                
                # 저장소 테스트
                try:
                    test_projects = storage.load_all_projects()
                    st.success(f"✅ 저장소 접근 성공 ({len(test_projects)}개 프로젝트)")
                except Exception as e:
                    st.error(f"❌ 저장소 접근 실패: {str(e)}")


def main():
    """메인 애플리케이션 (간소화된 Multi-Voice TTS 버전)"""
    st.set_page_config(
        page_title="MyTalk - Simplified Multi-Voice TTS",
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
        .voice-info {
            background: linear-gradient(135deg, #e3f2fd, #f1f8e9);
            padding: 1rem;
            border-radius: 10px;
            margin: 0.5rem 0;
            border-left: 4px solid #2196F3;
        }
        .system-info {
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
        <p style='color: white; margin: 0; opacity: 0.9;'>Simplified Multi-Voice TTS with OpenAI</p>
    </div>
    """, unsafe_allow_html=True)
    
    # TTS 엔진 상태 표시
    if st.session_state.api_key:
        st.markdown(f"""
        <div class="voice-info">
            🎵 <strong>Multi-Voice TTS 활성화</strong><br>
            🎙️ <strong>음성언어-1</strong>: {st.session_state.voice1.title()} (원본, Host, A)<br>
            🎤 <strong>음성언어-2</strong>: {st.session_state.voice2.title()} (TED, Guest, B)
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div class="system-info">
            ⚠️ <strong>API Key 필요</strong> | 설정에서 OpenAI API Key를 입력해주세요
        </div>
        """, unsafe_allow_html=True)
    
    # 네비게이션 탭
    tab1, tab2, tab3, tab4 = st.tabs(["✏️ 스크립트 작성", "🎯 연습하기", "📚 내 스크립트", "⚙️ 설정"])
    
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
    tts_status = f"🎵 Multi-Voice TTS ({st.session_state.voice1}/{st.session_state.voice2})"
    
    st.markdown(f"""
    <div style='text-align: center; color: #666; font-size: 0.8rem; margin-top: 2rem;'>
        <p>MyTalk v2.0 - Simplified with OpenAI Multi-Voice TTS</p>
        <p>📱 Local Storage | {tts_status}</p>
        <p>Made with ❤️ using Streamlit | 원스톱 영어 학습 솔루션</p>
    </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    if not OPENAI_AVAILABLE:
        st.error("OpenAI 라이브러리가 필요합니다.")
        st.code("pip install openai", language="bash")
        st.markdown("### 추가 의존성")
        st.markdown("음성 합치기 기능을 위해 다음 중 하나를 설치하세요:")
        st.code("pip install pydub", language="bash")  
        st.markdown("또는 시스템에 ffmpeg를 설치하세요")
        st.stop()
    
    main()
    