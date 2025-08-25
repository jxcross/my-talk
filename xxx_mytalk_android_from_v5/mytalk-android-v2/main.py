"""
MyTalk - 성능 최적화된 Kivy Android App
메모리 사용량 최적화 및 백그라운드 처리 개선 버전
"""

import os
import json
import tempfile
import time
import gc
from datetime import datetime
from pathlib import Path
import shutil
import uuid
import re
import threading
from concurrent.futures import ThreadPoolExecutor

# Kivy imports
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.spinner import Spinner
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.uix.tabbedpanel import TabbedPanel, TabbedPanelItem
from kivy.uix.checkbox import CheckBox
from kivy.uix.progressbar import ProgressBar
from kivy.uix.accordion import Accordion, AccordionItem
from kivy.clock import Clock, mainthread
from kivy.properties import StringProperty, BooleanProperty, ListProperty
from kivy.storage.jsonstore import JsonStore
from kivy.utils import platform
from kivy.core.audio import SoundLoader
from kivy.logger import Logger

# Android utilities
from android_utils import (
    get_storage_path, request_android_permissions,
    show_toast, initialize_android_app, lifecycle_manager,
    keep_screen_on, vibrate
)

# OpenAI
try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    Logger.error("OpenAI library not available")


class AsyncTaskManager:
    """비동기 작업 관리자"""
    
    def __init__(self, max_workers=2):
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.active_tasks = set()
    
    def submit_task(self, func, *args, callback=None, **kwargs):
        """백그라운드 작업 제출"""
        future = self.executor.submit(func, *args, **kwargs)
        self.active_tasks.add(future)
        
        def done_callback(fut):
            self.active_tasks.discard(fut)
            if callback:
                try:
                    result = fut.result()
                    Clock.schedule_once(lambda dt: callback(result), 0)
                except Exception as e:
                    Logger.error(f"Task error: {e}")
                    Clock.schedule_once(lambda dt: callback(None), 0)
        
        future.add_done_callback(done_callback)
        return future
    
    def cancel_all(self):
        """모든 작업 취소"""
        for task in list(self.active_tasks):
            task.cancel()
        self.active_tasks.clear()
    
    def shutdown(self):
        """작업 관리자 종료"""
        self.cancel_all()
        self.executor.shutdown(wait=False)


class OptimizedStorage:
    """메모리 효율적인 저장소 관리"""
    
    def __init__(self):
        self.base_dir = get_storage_path()
        self.scripts_dir = self.base_dir / "scripts"
        self.audio_dir = self.base_dir / "audio"
        self.temp_dir = self.base_dir / "temp"
        
        # 디렉토리 생성
        for directory in [self.scripts_dir, self.audio_dir, self.temp_dir]:
            directory.mkdir(parents=True, exist_ok=True)
        
        # 메타데이터 저장소
        self.store = JsonStore(str(self.base_dir / "projects.json"))
        
        # 임시 파일 정리
        self._cleanup_temp_files()
    
    def _cleanup_temp_files(self):
        """임시 파일 정리"""
        try:
            if self.temp_dir.exists():
                for file in self.temp_dir.iterdir():
                    if file.is_file():
                        # 1일 이상 된 임시 파일 삭제
                        if time.time() - file.stat().st_mtime > 86400:
                            file.unlink()
        except Exception as e:
            Logger.error(f"Temp cleanup error: {e}")
    
    def get_temp_file(self, suffix='.tmp'):
        """임시 파일 경로 생성"""
        return self.temp_dir / f"{uuid.uuid4()}{suffix}"
    
    def save_project_async(self, results, input_content, input_method, category, callback=None):
        """비동기 프로젝트 저장"""
        def _save():
            try:
                project_id = datetime.now().strftime("%Y%m%d_%H%M%S")
                title = results.get('title', f'Script_{project_id}')
                
                safe_title = self._sanitize_filename(title)
                project_folder = self.scripts_dir / f"{project_id}_{safe_title}"
                project_folder.mkdir(exist_ok=True)
                
                audio_folder = project_folder / "audio"
                audio_folder.mkdir(exist_ok=True)
                
                saved_files = {}
                
                # 텍스트 파일들 저장 (청크 단위로)
                for key, content in results.items():
                    if isinstance(content, str) and ('script' in key or 'translation' in key):
                        file_path = project_folder / f"{key}.txt"
                        with open(file_path, 'w', encoding='utf-8', buffering=8192) as f:
                            f.write(content)
                        saved_files[key] = str(file_path)
                
                # 오디오 파일들 이동 (복사 대신 이동으로 메모리 절약)
                for key, audio_data in results.items():
                    if 'audio' in key and audio_data:
                        if isinstance(audio_data, str) and os.path.exists(audio_data):
                            audio_dest = audio_folder / f"{key}{Path(audio_data).suffix}"
                            shutil.move(audio_data, audio_dest)
                            saved_files[key] = str(audio_dest)
                        elif isinstance(audio_data, dict):
                            audio_paths = {}
                            for role, audio_file in audio_data.items():
                                if isinstance(audio_file, str) and os.path.exists(audio_file):
                                    audio_dest = audio_folder / f"{key}_{role}{Path(audio_file).suffix}"
                                    shutil.move(audio_file, audio_dest)
                                    audio_paths[role] = str(audio_dest)
                            if audio_paths:
                                saved_files[key] = audio_paths
                
                # 메타데이터 저장
                metadata = {
                    'project_id': project_id,
                    'title': title,
                    'category': category,
                    'input_method': input_method,
                    'created_at': datetime.now().isoformat(),
                    'saved_files': saved_files,
                    'file_count': len(saved_files)
                }
                
                self.store.put(project_id, **metadata)
                
                # 메모리 정리
                del results
                gc.collect()
                
                return project_id, str(project_folder)
                
            except Exception as e:
                Logger.error(f"Save project error: {e}")
                return None, None
        
        if callback:
            # 백그라운드에서 실행
            threading.Thread(
                target=lambda: callback(_save()),
                daemon=True
            ).start()
        else:
            return _save()
    
    def load_projects_paginated(self, page=0, page_size=10):
        """페이지네이션된 프로젝트 로드"""
        try:
            all_keys = list(self.store.keys())
            all_keys.sort(reverse=True)  # 최신 순
            
            start_idx = page * page_size
            end_idx = start_idx + page_size
            page_keys = all_keys[start_idx:end_idx]
            
            projects = []
            for key in page_keys:
                try:
                    project = self.store.get(key)
                    # 메모리 절약을 위해 필요한 필드만 로드
                    projects.append({
                        'project_id': project.get('project_id'),
                        'title': project.get('title', 'Untitled'),
                        'category': project.get('category', '일반'),
                        'created_at': project.get('created_at', ''),
                        'file_count': project.get('file_count', 0)
                    })
                except Exception as e:
                    Logger.error(f"Load project {key} error: {e}")
                    continue
            
            return projects, len(all_keys)
            
        except Exception as e:
            Logger.error(f"Load projects error: {e}")
            return [], 0
    
    def load_project_content_lazy(self, project_id):
        """지연 로딩으로 프로젝트 내용 로드"""
        try:
            if not self.store.exists(project_id):
                return None
            
            project = self.store.get(project_id)
            saved_files = project.get('saved_files', {})
            
            # 텍스트 파일만 먼저 로드 (오디오는 필요할 때)
            content = {
                'metadata': project,
                'scripts': {},
                'audio_paths': {}
            }
            
            for file_type, file_path in saved_files.items():
                if 'script' in file_type or 'translation' in file_type:
                    if isinstance(file_path, str) and os.path.exists(file_path):
                        try:
                            with open(file_path, 'r', encoding='utf-8') as f:
                                # 큰 파일은 일부만 미리보기
                                file_content = f.read(2000)  # 2KB만 먼저 로드
                                if len(file_content) == 2000:
                                    file_content += "..."
                                content['scripts'][file_type] = file_content
                        except Exception as e:
                            Logger.error(f"Load script {file_type} error: {e}")
                            content['scripts'][file_type] = "로드 실패"
                elif 'audio' in file_type:
                    content['audio_paths'][file_type] = file_path
            
            return content
            
        except Exception as e:
            Logger.error(f"Load project content error: {e}")
            return None
    
    def _sanitize_filename(self, filename):
        """안전한 파일명 생성"""
        safe_chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_() "
        return ''.join(c for c in filename if c in safe_chars).strip()[:50] or "Untitled"


class LightweightLLMProvider:
    """경량화된 LLM 프로바이더"""
    
    def __init__(self, api_key, model):
        self.api_key = api_key
        self.model = model
        self.client = None
        self.request_timeout = 30  # 타임아웃 설정
        
        if OPENAI_AVAILABLE and api_key:
            try:
                self.client = openai.OpenAI(
                    api_key=api_key,
                    timeout=self.request_timeout
                )
            except Exception as e:
                Logger.error(f"OpenAI client init error: {e}")
    
    def generate_content_async(self, prompt, callback):
        """비동기 콘텐츠 생성"""
        def _generate():
            try:
                if not self.client:
                    return None
                
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=1500,  # 토큰 수 제한으로 비용 절약
                    temperature=0.7,
                    stream=False
                )
                
                content = response.choices[0].message.content
                
                # 메모리 정리
                del response
                gc.collect()
                
                return content
                
            except Exception as e:
                Logger.error(f"LLM generation error: {e}")
                return None
        
        # 백그라운드 실행
        threading.Thread(
            target=lambda: Clock.schedule_once(lambda dt: callback(_generate()), 0),
            daemon=True
        ).start()


class OptimizedTTSGenerator:
    """최적화된 TTS 생성기"""
    
    def __init__(self, api_key):
        self.api_key = api_key
        self.temp_files = set()  # 임시 파일 추적
    
    def generate_audio_async(self, text, voice, callback, temp_storage=None):
        """비동기 오디오 생성"""
        def _generate():
            try:
                if not OPENAI_AVAILABLE or not text or not text.strip():
                    return None
                
                # 텍스트 정리 및 길이 제한
                cleaned_text = self._clean_text_for_tts(text)[:1000]  # 1000자 제한
                
                if not cleaned_text:
                    return None
                
                client = openai.OpenAI(api_key=self.api_key)
                
                response = client.audio.speech.create(
                    model="tts-1",  # 빠른 모델 사용
                    voice=voice,
                    input=cleaned_text,
                    response_format="mp3",
                    speed=1.0
                )
                
                # 임시 파일 저장
                if temp_storage:
                    temp_file = temp_storage.get_temp_file('.mp3')
                else:
                    temp_file = Path(tempfile.mktemp(suffix='.mp3'))
                
                with open(temp_file, 'wb') as f:
                    for chunk in response.iter_bytes(chunk_size=8192):
                        f.write(chunk)
                
                # 임시 파일 추적
                self.temp_files.add(str(temp_file))
                
                # 메모리 정리
                del response
                gc.collect()
                
                if temp_file.exists() and temp_file.stat().st_size > 0:
                    return str(temp_file)
                return None
                
            except Exception as e:
                Logger.error(f"TTS generation error: {e}")
                return None
        
        # 백그라운드 실행
        threading.Thread(
            target=lambda: Clock.schedule_once(lambda dt: callback(_generate()), 0),
            daemon=True
        ).start()
    
    def _clean_text_for_tts(self, text):
        """TTS용 텍스트 정리"""
        if not text or not isinstance(text, str):
            return ""
        
        # 마크다운 및 불필요한 문자 제거
        text = re.sub(r'\[.*?\]', '', text)
        text = re.sub(r'\*\*.*?\*\*', '', text)
        text = re.sub(r'\*([^*]+)\*', r'\1', text)
        text = re.sub(r'^#+\s*', '', text, flags=re.MULTILINE)
        text = text.replace('\n', ' ').replace('\r', ' ')
        text = re.sub(r'\s+', ' ', text)
        
        return text.strip()
    
    def cleanup_temp_files(self):
        """임시 파일 정리"""
        for file_path in list(self.temp_files):
            try:
                if os.path.exists(file_path):
                    os.unlink(file_path)
                self.temp_files.discard(file_path)
            except Exception as e:
                Logger.error(f"Cleanup temp file error: {e}")


class SmartProgressPopup(Popup):
    """스마트 진행률 팝업"""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.title = "생성 중..."
        self.size_hint = (0.8, 0.4)
        self.auto_dismiss = False
        
        layout = BoxLayout(orientation='vertical', padding=20, spacing=15)
        
        self.progress_bar = ProgressBar(max=100, value=0)
        self.status_label = Label(
            text="초기화 중...",
            size_hint_y=0.3,
            text_size=(None, None)
        )
        self.detail_label = Label(
            text="",
            size_hint_y=0.3,
            text_size=(None, None),
            font_size='12sp'
        )
        
        # 취소 버튼
        self.cancel_button = Button(
            text="취소",
            size_hint=(1, 0.2),
            background_color=(1, 0.3, 0.3, 1)
        )
        self.cancel_button.bind(on_press=self.on_cancel)
        
        layout.add_widget(self.progress_bar)
        layout.add_widget(self.status_label)
        layout.add_widget(self.detail_label)
        layout.add_widget(self.cancel_button)
        
        self.content = layout
        self.cancelled = False
    
    def update_progress(self, value, status, detail=""):
        """진행률 업데이트"""
        if not self.cancelled:
            self.progress_bar.value = min(value, 100)
            self.status_label.text = status
            self.detail_label.text = detail
    
    def on_cancel(self, instance):
        """취소 처리"""
        self.cancelled = True
        self.dismiss()


class OptimizedScriptCreationTab(TabbedPanelItem):
    """최적화된 스크립트 생성 탭"""
    
    def __init__(self, app_instance, **kwargs):
        super().__init__(**kwargs)
        self.text = "📝 스크립트 생성"
        self.app_instance = app_instance
        self.current_task = None
        
        # UI 생성 (기본 구조는 동일)
        self._build_ui()
    
    def _build_ui(self):
        """UI 구축"""
        main_layout = BoxLayout(orientation='vertical', padding=10, spacing=10)
        scroll = ScrollView()
        content_layout = BoxLayout(orientation='vertical', size_hint_y=None, spacing=15)
        content_layout.bind(minimum_height=content_layout.setter('height'))
        
        # 제목
        title = Label(
            text="📝 스마트 스크립트 생성",
            font_size='20sp',
            size_hint_y=None,
            height='40dp'
        )
        content_layout.add_widget(title)
        
        # 카테고리 선택
        category_layout = BoxLayout(orientation='horizontal', size_hint_y=None, height='40dp')
        category_layout.add_widget(Label(text="카테고리:", size_hint_x=0.3))
        self.category_spinner = Spinner(
            text='일반',
            values=['일반', '비즈니스', '여행', '교육', '건강', '기술', '문화', '스포츠'],
            size_hint_x=0.7
        )
        category_layout.add_widget(self.category_spinner)
        content_layout.add_widget(category_layout)
        
        # 버전 선택 (체크박스)
        version_label = Label(
            text="생성할 버전 (추천: 2개 이하로 메모리 절약):",
            size_hint_y=None,
            height='30dp'
        )
        content_layout.add_widget(version_label)
        
        self.version_checkboxes = {}
        versions = [
            ('original', '원본 스크립트'),
            ('ted', 'TED 3분 말하기'),
            ('podcast', '팟캐스트 대화'),
            ('daily', '일상 대화')
        ]
        
        for version_id, version_name in versions:
            version_layout = BoxLayout(orientation='horizontal', size_hint_y=None, height='30dp')
            checkbox = CheckBox(
                active=(version_id in ['original', 'ted']),  # 기본 2개만 선택
                size_hint_x=0.2
            )
            label = Label(text=version_name, size_hint_x=0.8)
            version_layout.add_widget(checkbox)
            version_layout.add_widget(label)
            content_layout.add_widget(version_layout)
            self.version_checkboxes[version_id] = checkbox
        
        # 텍스트 입력
        input_label = Label(
            text="내용 입력 (간단할수록 빠름):",
            size_hint_y=None,
            height='30dp'
        )
        content_layout.add_widget(input_label)
        
        self.content_input = TextInput(
            hint_text="예: 환경보호의 중요성",
            multiline=True,
            size_hint_y=None,
            height='150dp'
        )
        content_layout.add_widget(self.content_input)
        
        # 고급 설정
        advanced_layout = BoxLayout(orientation='horizontal', size_hint_y=None, height='40dp')
        self.audio_checkbox = CheckBox(active=True, size_hint_x=0.2)
        audio_label = Label(text="음성도 생성 (시간 오래 걸림)", size_hint_x=0.8)
        advanced_layout.add_widget(self.audio_checkbox)
        advanced_layout.add_widget(audio_label)
        content_layout.add_widget(advanced_layout)
        
        # 생성 버튼
        generate_button = Button(
            text="🚀 스마트 생성하기",
            size_hint_y=None,
            height='50dp',
            background_color=(0.2, 0.8, 0.2, 1)
        )
        generate_button.bind(on_press=self.start_generation)
        content_layout.add_widget(generate_button)
        
        # 팁
        tip_label = Label(
            text="💡 팁: 네트워크 상태가 좋을 때 사용하세요",
            size_hint_y=None,
            height='30dp',
            font_size='12sp'
        )
        content_layout.add_widget(tip_label)
        
        scroll.add_widget(content_layout)
        main_layout.add_widget(scroll)
        self.add_widget(main_layout)
    
    def start_generation(self, instance):
        """생성 시작"""
        # 입력 검증
        if not self.app_instance.api_key:
            show_toast("설정에서 API Key를 입력해주세요!")
            return
        
        content = self.content_input.text.strip()
        if not content:
            show_toast("내용을 입력해주세요!")
            return
        
        selected_versions = [
            version for version, checkbox in self.version_checkboxes.items()
            if checkbox.active
        ]
        
        if not selected_versions:
            show_toast("생성할 버전을 선택해주세요!")
            return
        
        # 진행률 팝업 표시
        self.progress_popup = SmartProgressPopup()
        self.progress_popup.open()
        
        # 화면 켜짐 유지
        keep_screen_on(True)
        
        # 백그라운드 생성 시작
        self._generate_in_background(content, selected_versions)
    
    def _generate_in_background(self, content, selected_versions):
        """백그라운드에서 생성"""
        try:
            self.progress_popup.update_progress(10, "초기화 중...", "LLM 연결")
            
            # LLM 프로바이더 생성
            llm = LightweightLLMProvider(
                self.app_instance.api_key,
                self.app_instance.model
            )
            
            if not llm.client:
                self._show_error("API 연결 실패")
                return
            
            results = {}
            progress = 20
            
            # 원본 스크립트 생성
            self.progress_popup.update_progress(progress, "스크립트 생성 중...", "기본 내용")
            
            original_prompt = self._create_optimized_prompt(content, self.category_spinner.text)
            
            def on_script_generated(script_content):
                if self.progress_popup.cancelled:
                    return
                
                if script_content:
                    # 제목과 스크립트 분리
                    title, script = self._parse_script_response(script_content)
                    results['title'] = title
                    results['original_script'] = script
                    
                    self.progress_popup.update_progress(40, "버전별 생성 중...", f"{len(selected_versions)}개 버전")
                    
                    # 버전별 생성 계속
                    self._generate_versions(results, script, selected_versions, llm)
                else:
                    self._show_error("스크립트 생성 실패")
            
            llm.generate_content_async(original_prompt, on_script_generated)
            
        except Exception as e:
            self._show_error(f"생성 오류: {str(e)}")
    
    def _generate_versions(self, results, base_script, selected_versions, llm):
        """버전별 생성"""
        remaining_versions = [v for v in selected_versions if v != 'original']
        
        if not remaining_versions:
            # 원본만 있으면 오디오 생성으로
            if self.audio_checkbox.active:
                self._generate_audio(results, selected_versions)
            else:
                self._finish_generation(results)
            return
        
        version_prompts = {
            'ted': f"Transform into TED-style presentation: {base_script[:500]}",
            'podcast': f"Transform into podcast dialogue: {base_script[:500]}",
            'daily': f"Transform into daily conversation: {base_script[:500]}"
        }
        
        current_idx = 0
        
        def process_next_version():
            nonlocal current_idx
            
            if self.progress_popup.cancelled or current_idx >= len(remaining_versions):
                # 모든 버전 완료
                if self.audio_checkbox.active:
                    self._generate_audio(results, selected_versions)
                else:
                    self._finish_generation(results)
                return
            
            version = remaining_versions[current_idx]
            progress = 50 + (current_idx * 20)
            
            self.progress_popup.update_progress(
                progress, 
                f"{version.upper()} 생성 중...", 
                f"{current_idx + 1}/{len(remaining_versions)}"
            )
            
            def on_version_generated(version_content):
                if version_content and not self.progress_popup.cancelled:
                    results[f"{version}_script"] = version_content
                
                current_idx += 1
                Clock.schedule_once(lambda dt: process_next_version(), 0.5)
            
            if version in version_prompts:
                llm.generate_content_async(version_prompts[version], on_version_generated)
            else:
                current_idx += 1
                Clock.schedule_once(lambda dt: process_next_version(), 0.1)
        
        process_next_version()
    
    def _generate_audio(self, results, selected_versions):
        """오디오 생성"""
        self.progress_popup.update_progress(80, "음성 생성 중...", "TTS 처리")
        
        tts = OptimizedTTSGenerator(self.app_instance.api_key)
        
        # 원본만 음성 생성 (메모리 절약)
        if 'original_script' in results:
            def on_audio_generated(audio_file):
                if audio_file and not self.progress_popup.cancelled:
                    results['original_audio'] = audio_file
                
                # 정리 및 완료
                tts.cleanup_temp_files()
                self._finish_generation(results)
            
            tts.generate_audio_async(
                results['original_script'],
                self.app_instance.voice1,
                on_audio_generated,
                self.app_instance.storage
            )
        else:
            self._finish_generation(results)
    
    def _finish_generation(self, results):
        """생성 완료"""
        self.progress_popup.update_progress(95, "저장 중...", "파일 저장")
        
        def on_save_complete(result):
            self.progress_popup.dismiss()
            keep_screen_on(False)
            
            project_id, project_path = result if result else (None, None)
            
            if project_id:
                show_toast("생성 완료! 🎉")
                vibrate(200)
                
                # 메모리 정리
                del results
                gc.collect()
                
                # 연습 탭으로 전환 제안
                Clock.schedule_once(lambda dt: self._suggest_practice(), 2)
            else:
                show_toast("저장 실패 😔")
        
        self.app_instance.storage.save_project_async(
            results,
            self.content_input.text,
            "text",
            self.category_spinner.text,
            on_save_complete
        )
    
    def _suggest_practice(self):
        """연습 제안"""
        content_layout = BoxLayout(orientation='vertical', padding=20, spacing=20)
        
        message = Label(
            text="스크립트 생성이 완료되었습니다!\n연습하기 탭에서 확인하시겠습니까?",
            halign='center'
        )
        content_layout.add_widget(message)
        
        button_layout = BoxLayout(orientation='horizontal', spacing=20)
        
        later_button = Button(text="나중에", size_hint_x=0.5)
        practice_button = Button(
            text="연습하러 가기",
            size_hint_x=0.5,
            background_color=(0.2, 0.8, 0.2, 1)
        )
        
        button_layout.add_widget(later_button)
        button_layout.add_widget(practice_button)
        content_layout.add_widget(button_layout)
        
        popup = Popup(
            title="생성 완료!",
            content=content_layout,
            size_hint=(0.8, 0.4)
        )
        
        later_button.bind(on_press=popup.dismiss)
        practice_button.bind(on_press=lambda x: self._switch_to_practice(popup))
        popup.open()
    
    def _switch_to_practice(self, popup):
        """연습 탭으로 전환"""
        popup.dismiss()
        # 부모 TabbedPanel의 연습 탭으로 전환
        parent = self.parent
        if parent and hasattr(parent, 'switch_to'):
            for tab in parent.tab_list:
                if "연습" in tab.text:
                    parent.switch_to(tab)
                    break
    
    def _create_optimized_prompt(self, content, category):
        """최적화된 프롬프트 생성"""
        return f"""Create a concise English learning script.

Category: {category}
Topic: {content}

Requirements:
1. Natural American English
2. 150-200 words only
3. Simple vocabulary
4. Clear structure

Format:
TITLE: [English title]

[Script content here]"""
    
    def _parse_script_response(self, response):
        """스크립트 응답 파싱"""
        lines = response.split('\n')
        title = "Generated Script"
        script = response
        
        for line in lines:
            if line.startswith('TITLE:'):
                title = line.replace('TITLE:', '').strip()
                break
        
        # 제목 부분 제거하고 스크립트만 추출
        if 'TITLE:' in response:
            script_start = response.find('\n', response.find('TITLE:'))
            if script_start != -1:
                script = response[script_start:].strip()
        
        return title, script
    
    def _show_error(self, message):
        """에러 표시"""
        if hasattr(self, 'progress_popup'):
            self.progress_popup.dismiss()
        keep_screen_on(False)
        show_toast(f"오류: {message}")


class EfficientPracticeTab(TabbedPanelItem):
    """효율적인 연습하기 탭"""
    
    def __init__(self, app_instance, **kwargs):
        super().__init__(**kwargs)
        self.text = "🎯 연습하기"
        self.app_instance = app_instance
        self.current_sound = None
        self.current_page = 0
        self.page_size = 5  # 한 페이지에 5개씩
        
        self._build_ui()
        self.load_projects_page(0)
    
    def _build_ui(self):
        """UI 구축"""
        main_layout = BoxLayout(orientation='vertical', padding=10, spacing=10)
        
        # 제목
        title = Label(
            text="🎯 스마트 연습하기",
            font_size='20sp',
            size_hint_y=None,
            height='40dp'
        )
        main_layout.add_widget(title)
        
        # 페이지네이션 컨트롤
        page_layout = BoxLayout(orientation='horizontal', size_hint_y=None, height='40dp')
        
        self.prev_button = Button(text="◀ 이전", size_hint_x=0.3)
        self.prev_button.bind(on_press=self.prev_page)
        
        self.page_label = Label(text="페이지 1", size_hint_x=0.4)
        
        self.next_button = Button(text="다음 ▶", size_hint_x=0.3)
        self.next_button.bind(on_press=self.next_page)
        
        page_layout.add_widget(self.prev_button)
        page_layout.add_widget(self.page_label)
        page_layout.add_widget(self.next_button)
        main_layout.add_widget(page_layout)
        
        # 프로젝트 목록
        scroll = ScrollView()
        self.projects_layout = BoxLayout(
            orientation='vertical',
            size_hint_y=None,
            spacing=10
        )
        self.projects_layout.bind(minimum_height=self.projects_layout.setter('height'))
        scroll.add_widget(self.projects_layout)
        main_layout.add_widget(scroll)
        
        self.add_widget(main_layout)
    
    def load_projects_page(self, page):
        """페이지별 프로젝트 로드"""
        projects, total_count = self.app_instance.storage.load_projects_paginated(
            page, self.page_size
        )
        
        self.projects_layout.clear_widgets()
        
        if not projects:
            no_projects = Label(
                text="저장된 프로젝트가 없습니다.\n스크립트 생성 탭에서 만들어보세요! 📝",
                size_hint_y=None,
                height='100dp',
                halign='center'
            )
            self.projects_layout.add_widget(no_projects)
        else:
            for project in projects:
                self.create_project_card(project)
        
        # 페이지네이션 업데이트
        total_pages = (total_count + self.page_size - 1) // self.page_size
        self.current_page = page
        
        self.page_label.text = f"페이지 {page + 1}/{total_pages}"
        self.prev_button.disabled = (page == 0)
        self.next_button.disabled = (page >= total_pages - 1)
    
    def create_project_card(self, project):
        """프로젝트 카드 생성"""
        card = BoxLayout(
            orientation='vertical',
            size_hint_y=None,
            height='100dp',
            padding=10,
            spacing=5
        )
        
        # 제목
        title_label = Label(
            text=f"📄 {project['title']}",
            font_size='16sp',
            size_hint_y=None,
            height='30dp',
            halign='left'
        )
        title_label.text_size = (title_label.width, None)
        card.add_widget(title_label)
        
        # 정보
        info_label = Label(
            text=f"{project['category']} | {project['created_at'][:10]} | {project.get('file_count', 0)}개 파일",
            font_size='12sp',
            size_hint_y=None,
            height='20dp',
            halign='left'
        )
        info_label.text_size = (info_label.width, None)
        card.add_widget(info_label)
        
        # 버튼들
        button_layout = BoxLayout(
            orientation='horizontal',
            size_hint_y=None,
            height='40dp',
            spacing=10
        )
        
        practice_button = Button(
            text="🎯 연습하기",
            size_hint_x=0.5
        )
        practice_button.bind(on_press=lambda x, p=project: self.start_practice(p))
        
        preview_button = Button(
            text="👁️ 미리보기",
            size_hint_x=0.5
        )
        preview_button.bind(on_press=lambda x, p=project: self.show_preview(p))
        
        button_layout.add_widget(practice_button)
        button_layout.add_widget(preview_button)
        card.add_widget(button_layout)
        
        self.projects_layout.add_widget(card)
    
    def prev_page(self, instance):
        """이전 페이지"""
        if self.current_page > 0:
            self.load_projects_page(self.current_page - 1)
    
    def next_page(self, instance):
        """다음 페이지"""
        self.load_projects_page(self.current_page + 1)
    
    def start_practice(self, project):
        """연습 시작"""
        show_toast("연습 모드를 로드하고 있습니다...")
        
        # 백그라운드에서 프로젝트 내용 로드
        def load_content():
            content = self.app_instance.storage.load_project_content_lazy(project['project_id'])
            Clock.schedule_once(lambda dt: self.show_practice_mode(content), 0)
        
        threading.Thread(target=load_content, daemon=True).start()
    
    def show_practice_mode(self, content):
        """연습 모드 표시"""
        if not content:
            show_toast("프로젝트를 로드할 수 없습니다")
            return
        
        # 연습 모드 팝업 생성
        practice_layout = BoxLayout(orientation='vertical', padding=10, spacing=10)
        
        # 제목
        title_label = Label(
            text=f"🎯 {content['metadata']['title']}",
            font_size='18sp',
            size_hint_y=None,
            height='40dp'
        )
        practice_layout.add_widget(title_label)
        
        # 탭된 패널로 스크립트 표시
        script_tabs = TabbedPanel(do_default_tab=False, size_hint_y=0.7)
        
        for script_type, script_content in content['scripts'].items():
            if script_content:
                tab = TabbedPanelItem(text=script_type.replace('_', ' ').title())
                
                tab_layout = BoxLayout(orientation='vertical', spacing=10)
                
                # 스크립트 텍스트
                script_scroll = ScrollView()
                script_label = Label(
                    text=script_content,
                    text_size=(None, None),
                    halign='left',
                    valign='top'
                )
                script_label.bind(texture_size=script_label.setter('size'))
                script_scroll.add_widget(script_label)
                tab_layout.add_widget(script_scroll)
                
                # 오디오 컨트롤
                audio_key = script_type.replace('script', 'audio')
                if audio_key in content['audio_paths']:
                    audio_layout = BoxLayout(
                        orientation='horizontal',
                        size_hint_y=None,
                        height='50dp'
                    )
                    
                    play_button = Button(text="▶️ 재생", size_hint_x=0.5)
                    play_button.bind(on_press=lambda x, path=content['audio_paths'][audio_key]: self.play_audio(path))
                    
                    stop_button = Button(text="⏹️ 정지", size_hint_x=0.5)
                    stop_button.bind(on_press=self.stop_audio)
                    
                    audio_layout.add_widget(play_button)
                    audio_layout.add_widget(stop_button)
                    tab_layout.add_widget(audio_layout)
                
                tab.add_widget(tab_layout)
                script_tabs.add_widget(tab)
        
        practice_layout.add_widget(script_tabs)
        
        # 닫기 버튼
        close_button = Button(
            text="닫기",
            size_hint=(1, 0.1),
            background_color=(0.8, 0.8, 0.8, 1)
        )
        practice_layout.add_widget(close_button)
        
        popup = Popup(
            title="연습 모드",
            content=practice_layout,
            size_hint=(0.95, 0.9)
        )
        close_button.bind(on_press=popup.dismiss)
        popup.open()
    
    def show_preview(self, project):
        """미리보기 표시"""
        show_toast("미리보기를 로드하고 있습니다...")
        
        def load_preview():
            content = self.app_instance.storage.load_project_content_lazy(project['project_id'])
            Clock.schedule_once(lambda dt: self._show_preview_popup(content), 0)
        
        threading.Thread(target=load_preview, daemon=True).start()
    
    def _show_preview_popup(self, content):
        """미리보기 팝업"""
        if not content:
            show_toast("미리보기를 로드할 수 없습니다")
            return
        
        preview_layout = BoxLayout(orientation='vertical', padding=15, spacing=10)
        
        # 제목
        title_label = Label(
            text=f"👁️ {content['metadata']['title']}",
            font_size='16sp',
            size_hint_y=None,
            height='30dp'
        )
        preview_layout.add_widget(title_label)
        
        # 스크롤 영역
        scroll = ScrollView(size_hint_y=0.8)
        content_layout = BoxLayout(orientation='vertical', size_hint_y=None, spacing=10)
        content_layout.bind(minimum_height=content_layout.setter('height'))
        
        # 각 스크립트 미리보기
        for script_type, script_content in content['scripts'].items():
            if script_content:
                type_label = Label(
                    text=f"📝 {script_type.replace('_', ' ').title()}:",
                    font_size='14sp',
                    size_hint_y=None,
                    height='25dp',
                    halign='left'
                )
                type_label.text_size = (type_label.width, None)
                content_layout.add_widget(type_label)
                
                preview_text = script_content[:200] + "..." if len(script_content) > 200 else script_content
                content_label = Label(
                    text=preview_text,
                    text_size=(None, None),
                    size_hint_y=None,
                    halign='left',
                    valign='top',
                    font_size='12sp'
                )
                content_label.bind(texture_size=content_label.setter('size'))
                content_layout.add_widget(content_label)
        
        scroll.add_widget(content_layout)
        preview_layout.add_widget(scroll)
        
        # 닫기 버튼
        close_button = Button(
            text="닫기",
            size_hint=(1, 0.1)
        )
        preview_layout.add_widget(close_button)
        
        popup = Popup(
            title="미리보기",
            content=preview_layout,
            size_hint=(0.8, 0.7)
        )
        close_button.bind(on_press=popup.dismiss)
        popup.open()
    
    def play_audio(self, audio_path):
        """오디오 재생"""
        try:
            if self.current_sound:
                self.current_sound.stop()
            
            if isinstance(audio_path, str) and os.path.exists(audio_path):
                self.current_sound = SoundLoader.load(audio_path)
                if self.current_sound:
                    self.current_sound.play()
                    show_toast("재생 시작")
            elif isinstance(audio_path, dict):
                # 첫 번째 오디오 파일 재생
                for path in audio_path.values():
                    if isinstance(path, str) and os.path.exists(path):
                        self.current_sound = SoundLoader.load(path)
                        if self.current_sound:
                            self.current_sound.play()
                            show_toast("재생 시작")
                        break
        except Exception as e:
            Logger.error(f"Audio play error: {e}")
            show_toast("재생 실패")
    
    def stop_audio(self, instance):
        """오디오 정지"""
        if self.current_sound:
            self.current_sound.stop()
            show_toast("재생 정지")


class CompactMyScriptsTab(TabbedPanelItem):
    """간소화된 내 스크립트 탭"""
    
    def __init__(self, app_instance, **kwargs):
        super().__init__(**kwargs)
        self.text = "📚 내 스크립트"
        self.app_instance = app_instance
        
        self._build_ui()
        self.refresh_scripts()
    
    def _build_ui(self):
        """UI 구축"""
        main_layout = BoxLayout(orientation='vertical', padding=10, spacing=10)
        
        # 제목과 컨트롤
        header_layout = BoxLayout(orientation='horizontal', size_hint_y=None, height='40dp')
        
        title = Label(
            text="📚 내 스크립트",
            font_size='20sp',
            size_hint_x=0.7
        )
        header_layout.add_widget(title)
        
        refresh_button = Button(
            text="🔄",
            size_hint_x=0.15
        )
        refresh_button.bind(on_press=self.refresh_scripts)
        header_layout.add_widget(refresh_button)
        
        cleanup_button = Button(
            text="🧹",
            size_hint_x=0.15
        )
        cleanup_button.bind(on_press=self.cleanup_old_files)
        header_layout.add_widget(cleanup_button)
        
        main_layout.add_widget(header_layout)
        
        # 스크립트 목록
        scroll = ScrollView()
        self.scripts_layout = BoxLayout(
            orientation='vertical',
            size_hint_y=None,
            spacing=8
        )
        self.scripts_layout.bind(minimum_height=self.scripts_layout.setter('height'))
        scroll.add_widget(self.scripts_layout)
        main_layout.add_widget(scroll)
        
        self.add_widget(main_layout)
    
    def refresh_scripts(self, instance=None):
        """스크립트 목록 새로고침"""
        show_toast("목록을 새로고침하고 있습니다...")
        
        def load_scripts():
            projects, _ = self.app_instance.storage.load_projects_paginated(0, 20)  # 최신 20개
            Clock.schedule_once(lambda dt: self._update_scripts_list(projects), 0)
        
        threading.Thread(target=load_scripts, daemon=True).start()
    
    def _update_scripts_list(self, projects):
        """스크립트 목록 업데이트"""
        self.scripts_layout.clear_widgets()
        
        if not projects:
            no_scripts = Label(
                text="저장된 스크립트가 없습니다.\n📝 스크립트 생성 탭에서 만들어보세요!",
                size_hint_y=None,
                height='80dp',
                halign='center'
            )
            self.scripts_layout.add_widget(no_scripts)
            return
        
        for project in projects:
            self.create_compact_card(project)
        
        show_toast(f"{len(projects)}개 스크립트 로드됨")
    
    def create_compact_card(self, project):
        """간소화된 프로젝트 카드"""
        card = BoxLayout(
            orientation='horizontal',
            size_hint_y=None,
            height='60dp',
            padding=8,
            spacing=10
        )
        
        # 정보 영역
        info_layout = BoxLayout(orientation='vertical', size_hint_x=0.6)
        
        title_label = Label(
            text=f"📄 {project['title']}",
            font_size='14sp',
            size_hint_y=0.6,
            halign='left'
        )
        title_label.text_size = (title_label.width, None)
        
        detail_label = Label(
            text=f"{project['category']} • {project['created_at'][:10]}",
            font_size='11sp',
            size_hint_y=0.4,
            halign='left',
            color=(0.6, 0.6, 0.6, 1)
        )
        detail_label.text_size = (detail_label.width, None)
        
        info_layout.add_widget(title_label)
        info_layout.add_widget(detail_label)
        card.add_widget(info_layout)
        
        # 버튼 영역
        button_layout = BoxLayout(orientation='horizontal', size_hint_x=0.4, spacing=5)
        
        view_button = Button(
            text="👁️",
            size_hint_x=0.33
        )
        view_button.bind(on_press=lambda x, p=project: self.quick_view(p))
        
        share_button = Button(
            text="📤",
            size_hint_x=0.33
        )
        share_button.bind(on_press=lambda x, p=project: self.share_script(p))
        
        delete_button = Button(
            text="🗑️",
            size_hint_x=0.33,
            background_color=(1, 0.4, 0.4, 1)
        )
        delete_button.bind(on_press=lambda x, p=project: self.quick_delete(p))
        
        button_layout.add_widget(view_button)
        button_layout.add_widget(share_button)
        button_layout.add_widget(delete_button)
        card.add_widget(button_layout)
        
        self.scripts_layout.add_widget(card)
    
    def quick_view(self, project):
        """빠른 보기"""
        show_toast("로드 중...")
        
        def load_and_show():
            content = self.app_instance.storage.load_project_content_lazy(project['project_id'])
            Clock.schedule_once(lambda dt: self._show_quick_view(project, content), 0)
        
        threading.Thread(target=load_and_show, daemon=True).start()
    
    def _show_quick_view(self, project, content):
        """빠른 보기 표시"""
        if not content:
            show_toast("로드 실패")
            return
        
        view_layout = BoxLayout(orientation='vertical', padding=10, spacing=10)
        
        # 제목
        title_label = Label(
            text=project['title'],
            font_size='16sp',
            size_hint_y=None,
            height='30dp'
        )
        view_layout.add_widget(title_label)
        
        # 내용 (첫 번째 스크립트만)
        scroll = ScrollView(size_hint_y=0.8)
        first_script = next(iter(content['scripts'].values()), "내용 없음")
        content_label = Label(
            text=first_script[:500] + ("..." if len(first_script) > 500 else ""),
            text_size=(None, None),
            halign='left',
            valign='top'
        )
        content_label.bind(texture_size=content_label.setter('size'))
        scroll.add_widget(content_label)
        view_layout.add_widget(scroll)
        
        # 닫기 버튼
        close_button = Button(
            text="닫기",
            size_hint=(1, 0.1)
        )
        view_layout.add_widget(close_button)
        
        popup = Popup(
            title="빠른 보기",
            content=view_layout,
            size_hint=(0.9, 0.8)
        )
        close_button.bind(on_press=popup.dismiss)
        popup.open()
    
    def share_script(self, project):
        """스크립트 공유"""
        def load_and_share():
            content = self.app_instance.storage.load_project_content_lazy(project['project_id'])
            if content and content['scripts']:
                first_script = next(iter(content['scripts'].values()))
                share_text = f"{project['title']}\n\n{first_script[:1000]}"
                
                # Android utils의 share_text 사용
                from android_utils import share_text
                if share_text(share_text, f"MyTalk - {project['title']}"):
                    Clock.schedule_once(lambda dt: show_toast("공유됨"), 0)
                else:
                    Clock.schedule_once(lambda dt: show_toast("공유 실패"), 0)
        
        threading.Thread(target=load_and_share, daemon=True).start()
        show_toast("공유 준비 중...")
    
    def quick_delete(self, project):
        """빠른 삭제"""
        # 간단한 확인 팝업
        confirm_layout = BoxLayout(orientation='vertical', padding=20, spacing=15)
        
        message = Label(
            text=f"'{project['title']}'\n정말 삭제하시겠습니까?",
            halign='center'
        )
        confirm_layout.add_widget(message)
        
        button_layout = BoxLayout(orientation='horizontal', spacing=15)
        
        cancel_button = Button(text="취소", size_hint_x=0.5)
        delete_button = Button(
            text="삭제",
            size_hint_x=0.5,
            background_color=(1, 0.3, 0.3, 1)
        )
        
        button_layout.add_widget(cancel_button)
        button_layout.add_widget(delete_button)
        confirm_layout.add_widget(button_layout)
        
        popup = Popup(
            title="삭제 확인",
            content=confirm_layout,
            size_hint=(0.7, 0.3)
        )
        
        def do_delete(instance):
            popup.dismiss()
            if self.app_instance.storage.delete_project(project['project_id']):
                show_toast("삭제됨")
                vibrate(100)
                self.refresh_scripts()
            else:
                show_toast("삭제 실패")
        
        cancel_button.bind(on_press=popup.dismiss)
        delete_button.bind(on_press=do_delete)
        popup.open()
    
    def cleanup_old_files(self, instance):
        """오래된 파일 정리"""
        show_toast("파일 정리 중...")
        
        def cleanup():
            try:
                # 임시 파일 정리
                temp_dir = self.app_instance.storage.temp_dir
                cleaned_count = 0
                
                if temp_dir.exists():
                    for file in temp_dir.iterdir():
                        if file.is_file():
                            try:
                                file.unlink()
                                cleaned_count += 1
                            except:
                                continue
                
                Clock.schedule_once(
                    lambda dt: show_toast(f"임시 파일 {cleaned_count}개 정리됨"), 0
                )
                
                # 메모리 정리
                gc.collect()
                
            except Exception as e:
                Logger.error(f"Cleanup error: {e}")
                Clock.schedule_once(lambda dt: show_toast("정리 실패"), 0)
        
        threading.Thread(target=cleanup, daemon=True).start()


class SmartSettingsTab(TabbedPanelItem):
    """스마트 설정 탭"""
    
    def __init__(self, app_instance, **kwargs):
        super().__init__(**kwargs)
        self.text = "⚙️ 설정"
        self.app_instance = app_instance
        
        self._build_ui()
        self._load_device_info()
    
    def _build_ui(self):
        """UI 구축"""
        main_layout = BoxLayout(orientation='vertical', padding=10, spacing=15)
        scroll = ScrollView()
        content_layout = BoxLayout(orientation='vertical', size_hint_y=None, spacing=20)
        content_layout.bind(minimum_height=content_layout.setter('height'))
        
        # 제목
        title = Label(
            text="⚙️ 스마트 설정",
            font_size='20sp',
            size_hint_y=None,
            height='40dp'
        )
        content_layout.add_widget(title)
        
        # API 설정
        api_section = self._create_api_section()
        content_layout.add_widget(api_section)
        
        # TTS 설정
        tts_section = self._create_tts_section()
        content_layout.add_widget(tts_section)
        
        # 앱 설정
        app_section = self._create_app_section()
        content_layout.add_widget(app_section)
        
        # 시스템 정보
        system_section = self._create_system_section()
        content_layout.add_widget(system_section)
        
        scroll.add_widget(content_layout)
        main_layout.add_widget(scroll)
        self.add_widget(main_layout)
    
    def _create_api_section(self):
        """API 설정 섹션"""
        section = BoxLayout(orientation='vertical', size_hint_y=None, spacing=10)
        section.bind(minimum_height=section.setter('height'))
        
        # 섹션 제목
        title = Label(
            text="🤖 OpenAI API 설정",
            font_size='16sp',
            size_hint_y=None,
            height='30dp',
            halign='left'
        )
        section.add_widget(title)
        
        # API Key
        api_layout = BoxLayout(orientation='vertical', size_hint_y=None, spacing=5)
        api_layout.bind(minimum_height=api_layout.setter('height'))
        
        api_label = Label(
            text="API Key (안전하게 저장됩니다):",
            size_hint_y=None,
            height='25dp',
            halign='left'
        )
        api_layout.add_widget(api_label)
        
        api_input_layout = BoxLayout(orientation='horizontal', size_hint_y=None, height='40dp')
        
        self.api_input = TextInput(
            text=self.app_instance.api_key,
            password=True,
            multiline=False,
            size_hint_x=0.8
        )
        self.api_input.bind(text=self.on_api_key_change)
        
        test_api_button = Button(
            text="테스트",
            size_hint_x=0.2
        )
        test_api_button.bind(on_press=self.test_api_connection)
        
        api_input_layout.add_widget(self.api_input)
        api_input_layout.add_widget(test_api_button)
        api_layout.add_widget(api_input_layout)
        
        section.add_widget(api_layout)
        
        # Model 선택
        model_layout = BoxLayout(orientation='horizontal', size_hint_y=None, height='40dp')
        model_layout.add_widget(Label(text="모델:", size_hint_x=0.3))
        
        self.model_spinner = Spinner(
            text=self.app_instance.model,
            values=['gpt-4o-mini', 'gpt-4o', 'gpt-3.5-turbo'],
            size_hint_x=0.7
        )
        self.model_spinner.bind(text=self.on_model_change)
        model_layout.add_widget(self.model_spinner)
        section.add_widget(model_layout)
        
        return section
    
    def _create_tts_section(self):
        """TTS 설정 섹션"""
        section = BoxLayout(orientation='vertical', size_hint_y=None, spacing=10)
        section.bind(minimum_height=section.setter('height'))
        
        title = Label(
            text="🎤 음성 설정",
            font_size='16sp',
            size_hint_y=None,
            height='30dp',
            halign='left'
        )
        section.add_widget(title)
        
        voices = ['alloy', 'echo', 'fable', 'onyx', 'nova', 'shimmer']
        
        # 음성언어-1
        voice1_layout = BoxLayout(orientation='horizontal', size_hint_y=None, height='40dp')
        voice1_layout.add_widget(Label(text="음성 1 (기본):", size_hint_x=0.4))
        
        self.voice1_spinner = Spinner(
            text=self.app_instance.voice1,
            values=voices,
            size_hint_x=0.4
        )
        self.voice1_spinner.bind(text=self.on_voice1_change)
        
        test1_button = Button(text="🎵", size_hint_x=0.2)
        test1_button.bind(on_press=self.test_voice1)
        
        voice1_layout.add_widget(self.voice1_spinner)
        voice1_layout.add_widget(test1_button)
        section.add_widget(voice1_layout)
        
        # 음성언어-2
        voice2_layout = BoxLayout(orientation='horizontal', size_hint_y=None, height='40dp')
        voice2_layout.add_widget(Label(text="음성 2 (대화):", size_hint_x=0.4))
        
        self.voice2_spinner = Spinner(
            text=self.app_instance.voice2,
            values=voices,
            size_hint_x=0.4
        )
        self.voice2_spinner.bind(text=self.on_voice2_change)
        
        test2_button = Button(text="🎵", size_hint_x=0.2)
        test2_button.bind(on_press=self.test_voice2)
        
        voice2_layout.add_widget(self.voice2_spinner)
        voice2_layout.add_widget(test2_button)
        section.add_widget(voice2_layout)
        
        return section
    
    def _create_app_section(self):
        """앱 설정 섹션"""
        section = BoxLayout(orientation='vertical', size_hint_y=None, spacing=10)
        section.bind(minimum_height=section.setter('height'))
        
        title = Label(
            text="📱 앱 설정",
            font_size='16sp',
            size_hint_y=None,
            height='30dp',
            halign='left'
        )
        section.add_widget(title)
        
        # 화면 켜짐 유지
        screen_layout = BoxLayout(orientation='horizontal', size_hint_y=None, height='40dp')
        screen_checkbox = CheckBox(active=False, size_hint_x=0.2)
        screen_checkbox.bind(active=self.on_keep_screen_on)
        
        screen_label = Label(text="생성 중 화면 켜짐 유지", size_hint_x=0.8)
        
        screen_layout.add_widget(screen_checkbox)
        screen_layout.add_widget(screen_label)
        section.add_widget(screen_layout)
        
        # 진동 피드백
        vibrate_layout = BoxLayout(orientation='horizontal', size_hint_y=None, height='40dp')
        vibrate_checkbox = CheckBox(active=True, size_hint_x=0.2)
        vibrate_checkbox.bind(active=self.on_vibrate_feedback)
        
        vibrate_label = Label(text="진동 피드백 활성화", size_hint_x=0.8)
        
        vibrate_layout.add_widget(vibrate_checkbox)
        vibrate_layout.add_widget(vibrate_label)
        section.add_widget(vibrate_layout)
        
        return section
    
    def _create_system_section(self):
        """시스템 정보 섹션"""
        section = BoxLayout(orientation='vertical', size_hint_y=None, spacing=10)
        section.bind(minimum_height=section.setter('height'))
        
        title = Label(
            text="📊 시스템 정보",
            font_size='16sp',
            size_hint_y=None,
            height='30dp',
            halign='left'
        )
        section.add_widget(title)
        
        self.system_info_label = Label(
            text="시스템 정보를 로드하고 있습니다...",
            size_hint_y=None,
            halign='left',
            font_size='12sp'
        )
        self.system_info_label.bind(texture_size=self.system_info_label.setter('size'))
        section.add_widget(self.system_info_label)
        
        # 유틸리티 버튼들
        utils_layout = BoxLayout(orientation='horizontal', size_hint_y=None, height='50dp', spacing=10)
        
        cleanup_button = Button(text="🧹 정리")
        cleanup_button.bind(on_press=self.cleanup_storage)
        
        backup_button = Button(text="💾 백업")
        backup_button.bind(on_press=self.backup_settings)
        
        about_button = Button(text="ℹ️ 정보")
        about_button.bind(on_press=self.show_about)
        
        utils_layout.add_widget(cleanup_button)
        utils_layout.add_widget(backup_button)
        utils_layout.add_widget(about_button)
        section.add_widget(utils_layout)
        
        return section
    
    def _load_device_info(self):
        """기기 정보 로드"""
        def load_info():
            from android_utils import get_device_info, check_network_connection
            
            device_info = get_device_info()
            projects_count = len(self.app_instance.storage.store.keys())
            network_status = "연결됨" if check_network_connection() else "연결 안됨"
            
            info_text = f"""플랫폼: {device_info.get('platform', 'Unknown')}
네트워크: {network_status}
저장된 프로젝트: {projects_count}개
저장 위치: {device_info.get('storage_path', 'Unknown')}
앱 버전: 1.0 (최적화됨)"""
            
            if platform == 'android':
                info_text += f"""
기기: {device_info.get('model', 'Unknown')}
안드로이드: {device_info.get('version', 'Unknown')}"""
            
            Clock.schedule_once(lambda dt: setattr(self.system_info_label, 'text', info_text), 0)
        
        threading.Thread(target=load_info, daemon=True).start()
    
    # 이벤트 핸들러들
    def on_api_key_change(self, instance, value):
        self.app_instance.api_key = value
        self.app_instance.save_settings()
    
    def on_model_change(self, spinner, text):
        self.app_instance.model = text
        self.app_instance.save_settings()
    
    def on_voice1_change(self, spinner, text):
        self.app_instance.voice1 = text
        self.app_instance.save_settings()
    
    def on_voice2_change(self, spinner, text):
        self.app_instance.voice2 = text
        self.app_instance.save_settings()
    
    def on_keep_screen_on(self, checkbox, active):
        keep_screen_on(active)
        show_toast("화면 설정 변경됨")
    
    def on_vibrate_feedback(self, checkbox, active):
        if active:
            vibrate(100)
        show_toast("진동 설정 변경됨")
    
    def test_api_connection(self, instance):
        """API 연결 테스트"""
        if not self.app_instance.api_key:
            show_toast("API Key를 입력하세요")
            return
        
        show_toast("API 테스트 중...")
        
        def test():
            try:
                llm = LightweightLLMProvider(
                    self.app_instance.api_key,
                    self.app_instance.model
                )
                
                if llm.client:
                    Clock.schedule_once(lambda dt: show_toast("API 연결 성공! ✅"), 0)
                else:
                    Clock.schedule_once(lambda dt: show_toast("API 연결 실패 ❌"), 0)
            except Exception as e:
                Clock.schedule_once(lambda dt: show_toast(f"연결 오류: {str(e)[:30]}"), 0)
        
        threading.Thread(target=test, daemon=True).start()
    
    def test_voice1(self, instance):
        """음성 1 테스트"""
        self._test_voice("Hello, this is voice one testing.", self.app_instance.voice1)
    
    def test_voice2(self, instance):
        """음성 2 테스트"""
        self._test_voice("Hello, this is voice two testing.", self.app_instance.voice2)
    
    def _test_voice(self, text, voice):
        """음성 테스트 실행"""
        if not self.app_instance.api_key:
            show_toast("API Key가 필요합니다")
            return
        
        show_toast(f"{voice} 음성 테스트 중...")
        
        def test():
            tts = OptimizedTTSGenerator(self.app_instance.api_key)
            
            def on_generated(audio_file):
                if audio_file:
                    try:
                        sound = SoundLoader.load(audio_file)
                        if sound:
                            sound.play()
                            show_toast("테스트 완료! 🎵")
                            vibrate(100)
                        else:
                            show_toast("재생 실패")
                    except:
                        show_toast("재생 오류")
                else:
                    show_toast("음성 생성 실패")
            
            tts.generate_audio_async(
                text, voice, on_generated, self.app_instance.storage
            )
        
        threading.Thread(target=test, daemon=True).start()
    
    def cleanup_storage(self, instance):
        """저장소 정리"""
        show_toast("저장소 정리 중...")
        
        def cleanup():
            try:
                # 임시 파일 정리
                self.app_instance.storage._cleanup_temp_files()
                
                # 메모리 정리
                gc.collect()
                
                Clock.schedule_once(lambda dt: show_toast("정리 완료! 🧹"), 0)
            except Exception as e:
                Clock.schedule_once(lambda dt: show_toast("정리 실패"), 0)
        
        threading.Thread(target=cleanup, daemon=True).start()
    
    def backup_settings(self, instance):
        """설정 백업"""
        try:
            settings = {
                'api_key': self.app_instance.api_key,
                'model': self.app_instance.model,
                'voice1': self.app_instance.voice1,
                'voice2': self.app_instance.voice2,
                'backup_date': datetime.now().isoformat()
            }
            
            backup_file = self.app_instance.storage.base_dir / "settings_backup.json"
            with open(backup_file, 'w') as f:
                json.dump(settings, f)
            
            show_toast("설정 백업 완료! 💾")
        except Exception as e:
            show_toast("백업 실패")
    
    def show_about(self, instance):
        """앱 정보 표시"""
        about_layout = BoxLayout(orientation='vertical', padding=20, spacing=15)
        
        title = Label(
            text="🎙️ MyTalk",
            font_size='24sp',
            size_hint_y=None,
            height='40dp'
        )
        about_layout.add_widget(title)
        
        info_text = """영어 학습을 위한 스마트 스크립트 생성 앱

🎯 주요 기능:
• AI 기반 스크립트 생성
• 다양한 형식 (TED, 팟캐스트, 일상)
• 고품질 음성 합성
• 오프라인 연습 지원

🔧 기술 스택:
• Python + Kivy
• OpenAI GPT & TTS
• Android Native

📱 버전: 1.0 (최적화)
👨‍💻 개발: MyTalk Team"""
        
        info_label = Label(
            text=info_text,
            halign='center',
            font_size='12sp'
        )
        about_layout.add_widget(info_label)
        
        close_button = Button(
            text="닫기",
            size_hint=(1, None),
            height='40dp'
        )
        about_layout.add_widget(close_button)
        
        popup = Popup(
            title="앱 정보",
            content=about_layout,
            size_hint=(0.8, 0.7)
        )
        close_button.bind(on_press=popup.dismiss)
        popup.open()


class MyTalkOptimizedApp(App):
    """최적화된 메인 애플리케이션"""
    
    # 앱 속성들
    api_key = StringProperty('')
    model = StringProperty('gpt-4o-mini')
    voice1 = StringProperty('alloy')
    voice2 = StringProperty('nova')
    
    def build(self):
        """앱 빌드"""
        self.title = "MyTalk - Smart English Learning"
        
        # Android 초기화
        if platform == 'android':
            initialize_android_app()
        
        # 저장소 및 작업 관리자 초기화
        self.storage = OptimizedStorage()
        self.task_manager = AsyncTaskManager(max_workers=2)
        
        # 설정 로드
        self.load_settings()
        
        # 생명주기 콜백 등록
        lifecycle_manager.register_callback('on_pause', self.on_app_pause)
        lifecycle_manager.register_callback('on_resume', self.on_app_resume)
        lifecycle_manager.register_callback('on_destroy', self.on_app_destroy)
        
        # 메인 UI
        root = TabbedPanel(do_default_tab=False)
        
        # 탭들 추가
        root.add_widget(OptimizedScriptCreationTab(self))
        root.add_widget(EfficientPracticeTab(self))
        root.add_widget(CompactMyScriptsTab(self))
        root.add_widget(SmartSettingsTab(self))
        
        return root
    
    def load_settings(self):
        """설정 로드"""
        settings_file = self.storage.base_dir / "settings.json"
        try:
            if settings_file.exists():
                with open(settings_file, 'r', encoding='utf-8') as f:
                    settings = json.load(f)
                
                self.api_key = settings.get('api_key', '')
                self.model = settings.get('model', 'gpt-4o-mini')
                self.voice1 = settings.get('voice1', 'alloy')
                self.voice2 = settings.get('voice2', 'nova')
        except Exception as e:
            Logger.error(f"Settings load error: {e}")
    
    def save_settings(self):
        """설정 저장"""
        settings = {
            'api_key': self.api_key,
            'model': self.model,
            'voice1': self.voice1,
            'voice2': self.voice2,
            'last_updated': datetime.now().isoformat()
        }
        
        settings_file = self.storage.base_dir / "settings.json"
        try:
            with open(settings_file, 'w', encoding='utf-8') as f:
                json.dump(settings, f, ensure_ascii=False, indent=2)
        except Exception as e:
            Logger.error(f"Settings save error: {e}")
    
    def on_app_pause(self):
        """앱 일시정지 시 (Android 생명주기)"""
        Logger.info("App pausing - cleaning up resources")
        
        # 진행 중인 작업들 일시정지
        self.task_manager.cancel_all()
        
        # 설정 저장
        self.save_settings()
        
        # 메모리 정리
        gc.collect()
        
        return True
    
    def on_app_resume(self):
        """앱 재개 시"""
        Logger.info("App resuming")
        
        # 네트워크 상태 확인
        from android_utils import check_network_connection
        if not check_network_connection():
            Clock.schedule_once(
                lambda dt: show_toast("네트워크 연결을 확인해주세요"), 0.5
            )
    
    def on_app_destroy(self):
        """앱 종료 시"""
        Logger.info("App destroying - final cleanup")
        
        # 모든 작업 정리
        if hasattr(self, 'task_manager'):
            self.task_manager.shutdown()
        
        # 임시 파일 정리
        if hasattr(self, 'storage'):
            self.storage._cleanup_temp_files()
        
        # 설정 저장
        self.save_settings()
    
    def on_pause(self):
        """Kivy 앱 일시정지"""
        lifecycle_manager.trigger_callbacks('on_pause')
        return True
    
    def on_resume(self):
        """Kivy 앱 재개"""
        lifecycle_manager.trigger_callbacks('on_resume')
    
    def on_stop(self):
        """Kivy 앱 정지"""
        lifecycle_manager.trigger_callbacks('on_destroy')


if __name__ == '__main__':
    # 앱 실행
    MyTalkOptimizedApp().run()