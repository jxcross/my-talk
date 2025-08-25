"""
MyTalk - Kivy Android App Version
영어 학습용 스크립트 생성 및 TTS 애플리케이션
"""

import os
import json
import tempfile
import time
from datetime import datetime
from pathlib import Path
import shutil
import uuid
import re

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
from kivy.uix.filechooser import FileChooserListView
from kivy.uix.progressbar import ProgressBar
from kivy.uix.accordion import Accordion, AccordionItem
from kivy.clock import Clock
from kivy.properties import StringProperty, BooleanProperty, ListProperty
from kivy.storage.jsonstore import JsonStore
from kivy.utils import platform

# Audio
from kivy.core.audio import SoundLoader

# OpenAI
try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

# Android storage
if platform == 'android':
    from android.permissions import request_permissions, Permission
    from android.storage import primary_external_storage_path
    request_permissions([
        Permission.WRITE_EXTERNAL_STORAGE,
        Permission.READ_EXTERNAL_STORAGE,
        Permission.INTERNET,
        Permission.RECORD_AUDIO
    ])


class SimpleStorage:
    """로컬 저장소 관리 클래스"""
    
    def __init__(self):
        if platform == 'android':
            self.base_dir = Path(primary_external_storage_path()) / "MyTalk"
        else:
            self.base_dir = Path.home() / "MyTalk"
        
        self.scripts_dir = self.base_dir / "scripts"
        self.audio_dir = self.base_dir / "audio"
        
        # 디렉토리 생성
        self.scripts_dir.mkdir(parents=True, exist_ok=True)
        self.audio_dir.mkdir(parents=True, exist_ok=True)
        
        # JsonStore for metadata
        self.store = JsonStore(str(self.base_dir / "projects.json"))
    
    def sanitize_filename(self, filename):
        """안전한 파일명 생성"""
        safe_chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_() "
        safe_filename = ''.join(c for c in filename if c in safe_chars)
        return safe_filename.strip()[:50] or "Untitled"
    
    def save_project(self, results, input_content, input_method, category):
        """프로젝트 저장"""
        try:
            project_id = datetime.now().strftime("%Y%m%d_%H%M%S")
            title = results.get('title', f'Script_{project_id}')
            
            safe_title = self.sanitize_filename(title)
            project_folder = self.scripts_dir / f"{project_id}_{safe_title}"
            project_folder.mkdir(exist_ok=True)
            
            audio_folder = project_folder / "audio"
            audio_folder.mkdir(exist_ok=True)
            
            saved_files = {}
            
            # 텍스트 파일들 저장
            if 'original_script' in results:
                script_file = project_folder / "original_script.txt"
                with open(script_file, 'w', encoding='utf-8') as f:
                    f.write(results['original_script'])
                saved_files['original_script'] = str(script_file)
            
            # 각 버전별 저장
            for version in ['ted', 'podcast', 'daily']:
                script_key = f"{version}_script"
                if script_key in results:
                    script_file = project_folder / f"{version}_script.txt"
                    with open(script_file, 'w', encoding='utf-8') as f:
                        f.write(results[script_key])
                    saved_files[script_key] = str(script_file)
                
                # 오디오 파일 저장
                audio_key = f"{version}_audio"
                if audio_key in results and results[audio_key]:
                    audio_data = results[audio_key]
                    if isinstance(audio_data, str) and os.path.exists(audio_data):
                        audio_ext = Path(audio_data).suffix or '.mp3'
                        audio_dest = audio_folder / f"{version}_audio{audio_ext}"
                        shutil.copy2(audio_data, audio_dest)
                        saved_files[audio_key] = str(audio_dest)
                    elif isinstance(audio_data, dict):
                        audio_paths = {}
                        for role, audio_file in audio_data.items():
                            if isinstance(audio_file, str) and os.path.exists(audio_file):
                                audio_ext = Path(audio_file).suffix or '.mp3'
                                audio_dest = audio_folder / f"{version}_audio_{role}{audio_ext}"
                                shutil.copy2(audio_file, audio_dest)
                                audio_paths[role] = str(audio_dest)
                        if audio_paths:
                            saved_files[audio_key] = audio_paths
            
            # 메타데이터 저장
            metadata = {
                'project_id': project_id,
                'title': title,
                'category': category,
                'input_method': input_method,
                'created_at': datetime.now().isoformat(),
                'saved_files': saved_files
            }
            
            self.store.put(project_id, **metadata)
            return project_id, str(project_folder)
            
        except Exception as e:
            print(f"저장 실패: {e}")
            return None, None
    
    def load_all_projects(self):
        """모든 프로젝트 로드"""
        projects = []
        for key in self.store.keys():
            projects.append(self.store.get(key))
        return sorted(projects, key=lambda x: x.get('created_at', ''), reverse=True)
    
    def delete_project(self, project_id):
        """프로젝트 삭제"""
        try:
            if self.store.exists(project_id):
                project = self.store.get(project_id)
                # 파일들 삭제
                saved_files = project.get('saved_files', {})
                for file_path in saved_files.values():
                    if isinstance(file_path, str) and os.path.exists(file_path):
                        project_dir = Path(file_path).parent.parent
                        if project_dir.exists():
                            shutil.rmtree(project_dir)
                        break
                
                # 메타데이터 삭제
                self.store.delete(project_id)
                return True
        except Exception as e:
            print(f"삭제 실패: {e}")
        return False


class SimpleLLMProvider:
    """OpenAI API 클라이언트"""
    
    def __init__(self, api_key, model):
        self.api_key = api_key
        self.model = model
        self.client = None
        if OPENAI_AVAILABLE and api_key:
            self.client = openai.OpenAI(api_key=api_key)
    
    def generate_content(self, prompt):
        """텍스트 생성"""
        try:
            if not self.client:
                return None
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=2000,
                temperature=0.7
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"LLM 호출 실패: {e}")
            return None


def generate_audio_with_openai_tts(text, api_key, voice='alloy'):
    """OpenAI TTS 음성 생성"""
    try:
        if not OPENAI_AVAILABLE or not text or not text.strip():
            return None
        
        client = openai.OpenAI(api_key=api_key)
        
        response = client.audio.speech.create(
            model="tts-1",
            voice=voice,
            input=text.strip()
        )
        
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.mp3')
        
        with open(temp_file.name, 'wb') as f:
            for chunk in response.iter_bytes(chunk_size=1024):
                f.write(chunk)
        
        temp_file.close()
        
        if os.path.exists(temp_file.name) and os.path.getsize(temp_file.name) > 0:
            return temp_file.name
        return None
        
    except Exception as e:
        print(f"TTS 생성 실패: {e}")
        return None


def clean_text_for_tts(text):
    """TTS용 텍스트 정리"""
    if not text or not isinstance(text, str):
        return ""
    
    # 마크다운 제거
    text = re.sub(r'\[.*?\]', '', text)
    text = re.sub(r'\*\*.*?\*\*', '', text)
    text = re.sub(r'\*([^*]+)\*', r'\1', text)
    text = re.sub(r'^#+\s*', '', text, flags=re.MULTILINE)
    
    # 줄바꿈을 공백으로
    text = text.replace('\n', ' ').replace('\r', ' ')
    text = re.sub(r'\s+', ' ', text)
    
    return text.strip()


class LoadingPopup(Popup):
    """로딩 팝업"""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.title = "생성 중..."
        self.size_hint = (0.8, 0.3)
        self.auto_dismiss = False
        
        layout = BoxLayout(orientation='vertical', padding=20, spacing=10)
        
        self.progress_bar = ProgressBar(max=100)
        self.status_label = Label(text="초기화 중...", size_hint_y=0.3)
        
        layout.add_widget(self.progress_bar)
        layout.add_widget(self.status_label)
        
        self.content = layout
    
    def update_progress(self, value, status):
        """진행률 업데이트"""
        self.progress_bar.value = value
        self.status_label.text = status


class ScriptCreationTab(TabbedPanelItem):
    """스크립트 생성 탭"""
    
    def __init__(self, app_instance, **kwargs):
        super().__init__(**kwargs)
        self.text = "📝 스크립트 생성"
        self.app_instance = app_instance
        
        # 메인 레이아웃
        main_layout = BoxLayout(orientation='vertical', padding=10, spacing=10)
        scroll = ScrollView()
        content_layout = BoxLayout(orientation='vertical', size_hint_y=None, spacing=15)
        content_layout.bind(minimum_height=content_layout.setter('height'))
        
        # 제목
        title = Label(
            text="📝 새 스크립트 만들기",
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
        
        # 버전 선택
        version_label = Label(
            text="생성할 버전 선택:",
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
            checkbox = CheckBox(active=True, size_hint_x=0.2)
            label = Label(text=version_name, size_hint_x=0.8, text_size=(None, None))
            version_layout.add_widget(checkbox)
            version_layout.add_widget(label)
            content_layout.add_widget(version_layout)
            self.version_checkboxes[version_id] = checkbox
        
        # 입력 방법
        input_label = Label(
            text="입력 방법:",
            size_hint_y=None,
            height='30dp'
        )
        content_layout.add_widget(input_label)
        
        input_layout = BoxLayout(orientation='horizontal', size_hint_y=None, height='40dp')
        input_layout.add_widget(Label(text="방법:", size_hint_x=0.3))
        self.input_method_spinner = Spinner(
            text='텍스트',
            values=['텍스트', '파일'],
            size_hint_x=0.7
        )
        input_layout.add_widget(self.input_method_spinner)
        content_layout.add_widget(input_layout)
        
        # 텍스트 입력
        self.content_input = TextInput(
            hint_text="주제나 내용을 입력하세요...",
            multiline=True,
            size_hint_y=None,
            height='200dp'
        )
        content_layout.add_widget(self.content_input)
        
        # 생성 버튼
        generate_button = Button(
            text="🚀 스크립트 생성하기",
            size_hint_y=None,
            height='50dp',
            background_color=(0.2, 0.8, 0.2, 1)
        )
        generate_button.bind(on_press=self.generate_script)
        content_layout.add_widget(generate_button)
        
        scroll.add_widget(content_layout)
        main_layout.add_widget(scroll)
        self.add_widget(main_layout)
    
    def generate_script(self, instance):
        """스크립트 생성"""
        # API 키 확인
        if not self.app_instance.api_key:
            popup = Popup(
                title="오류",
                content=Label(text="설정에서 API Key를 입력해주세요!"),
                size_hint=(0.8, 0.3)
            )
            popup.open()
            return
        
        # 입력 확인
        content = self.content_input.text.strip()
        if not content:
            popup = Popup(
                title="오류",
                content=Label(text="내용을 입력해주세요!"),
                size_hint=(0.8, 0.3)
            )
            popup.open()
            return
        
        # 선택된 버전 확인
        selected_versions = [
            version for version, checkbox in self.version_checkboxes.items()
            if checkbox.active
        ]
        
        if not selected_versions:
            popup = Popup(
                title="오류",
                content=Label(text="생성할 버전을 선택해주세요!"),
                size_hint=(0.8, 0.3)
            )
            popup.open()
            return
        
        # 로딩 팝업 표시
        self.loading_popup = LoadingPopup()
        self.loading_popup.open()
        
        # 백그라운드에서 생성 시작
        Clock.schedule_once(lambda dt: self._generate_script_background(
            content, selected_versions, self.category_spinner.text
        ), 0.1)
    
    def _generate_script_background(self, content, selected_versions, category):
        """백그라운드에서 스크립트 생성"""
        try:
            self.loading_popup.update_progress(10, "LLM 초기화 중...")
            
            llm_provider = SimpleLLMProvider(
                self.app_instance.api_key,
                self.app_instance.model
            )
            
            if not llm_provider.client:
                self.loading_popup.dismiss()
                Clock.schedule_once(lambda dt: self._show_error("API 연결 실패"), 0.1)
                return
            
            results = {}
            
            # 원본 스크립트 생성
            self.loading_popup.update_progress(20, "영어 스크립트 생성 중...")
            
            original_prompt = f"""
            Create a natural, engaging English script based on the following input.
            
            Category: {category}
            Content: {content}
            
            Requirements:
            1. Natural conversational American English
            2. 200-300 words
            3. Clear structure with introduction, main content, conclusion
            4. Include both English and Korean titles
            
            Format:
            ENGLISH TITLE: [title]
            KOREAN TITLE: [title]
            
            SCRIPT:
            [script content]
            """
            
            original_response = llm_provider.generate_content(original_prompt)
            
            if not original_response:
                self.loading_popup.dismiss()
                Clock.schedule_once(lambda dt: self._show_error("스크립트 생성 실패"), 0.1)
                return
            
            # 제목과 스크립트 분리
            title = "Generated Script"
            script_content = original_response
            
            lines = original_response.split('\n')
            for line in lines:
                if line.startswith('ENGLISH TITLE:'):
                    title = line.replace('ENGLISH TITLE:', '').strip()
            
            script_start = original_response.find('SCRIPT:')
            if script_start != -1:
                script_content = original_response[script_start+7:].strip()
            
            results['title'] = title
            results['original_script'] = script_content
            
            # 각 버전별 생성
            version_prompts = {
                'ted': f"""Transform into TED-style 3-minute presentation:
                Original: {script_content}
                Add powerful opening, personal examples, clear structure, inspiring ending.""",
                
                'podcast': f"""Transform into 2-person podcast dialogue:
                Original: {script_content}
                Format as "Host: [dialogue]" and "Guest: [dialogue]"
                Natural conversation style.""",
                
                'daily': f"""Transform into daily conversation:
                Original: {script_content}
                Format as "A: [dialogue]" and "B: [dialogue]"
                Casual, practical expressions."""
            }
            
            progress = 30
            for version in selected_versions:
                if version == 'original':
                    continue
                
                self.loading_popup.update_progress(progress, f"{version.upper()} 생성 중...")
                
                if version in version_prompts:
                    version_content = llm_provider.generate_content(version_prompts[version])
                    if version_content:
                        results[f"{version}_script"] = version_content
                
                progress += 20
            
            # 음성 생성
            if self.app_instance.voice1 and self.app_instance.voice2:
                self.loading_popup.update_progress(80, "음성 생성 중...")
                
                # 원본 음성
                if 'original' in selected_versions:
                    original_audio = generate_audio_with_openai_tts(
                        clean_text_for_tts(script_content),
                        self.app_instance.api_key,
                        self.app_instance.voice1
                    )
                    if original_audio:
                        results['original_audio'] = original_audio
                
                # TED 음성
                if 'ted' in selected_versions and 'ted_script' in results:
                    ted_audio = generate_audio_with_openai_tts(
                        clean_text_for_tts(results['ted_script']),
                        self.app_instance.api_key,
                        self.app_instance.voice2
                    )
                    if ted_audio:
                        results['ted_audio'] = ted_audio
            
            self.loading_popup.update_progress(100, "완료!")
            
            # 저장
            project_id, project_path = self.app_instance.storage.save_project(
                results, content, "text", category
            )
            
            self.loading_popup.dismiss()
            
            if project_id:
                Clock.schedule_once(lambda dt: self._show_success("생성 완료!"), 0.1)
            else:
                Clock.schedule_once(lambda dt: self._show_error("저장 실패"), 0.1)
            
        except Exception as e:
            self.loading_popup.dismiss()
            Clock.schedule_once(lambda dt: self._show_error(f"오류: {str(e)}"), 0.1)
    
    def _show_error(self, message):
        """에러 팝업"""
        popup = Popup(
            title="오류",
            content=Label(text=message),
            size_hint=(0.8, 0.3)
        )
        popup.open()
    
    def _show_success(self, message):
        """성공 팝업"""
        popup = Popup(
            title="성공",
            content=Label(text=message),
            size_hint=(0.8, 0.3)
        )
        popup.open()


class PracticeTab(TabbedPanelItem):
    """연습하기 탭"""
    
    def __init__(self, app_instance, **kwargs):
        super().__init__(**kwargs)
        self.text = "🎯 연습하기"
        self.app_instance = app_instance
        self.current_sound = None
        
        main_layout = BoxLayout(orientation='vertical', padding=10, spacing=10)
        
        # 제목
        title = Label(
            text="🎯 연습하기",
            font_size='20sp',
            size_hint_y=None,
            height='40dp'
        )
        main_layout.add_widget(title)
        
        # 프로젝트 선택
        project_layout = BoxLayout(orientation='horizontal', size_hint_y=None, height='40dp')
        project_layout.add_widget(Label(text="프로젝트:", size_hint_x=0.3))
        self.project_spinner = Spinner(
            text='프로젝트를 선택하세요',
            values=[],
            size_hint_x=0.7
        )
        self.project_spinner.bind(text=self.on_project_selected)
        project_layout.add_widget(self.project_spinner)
        main_layout.add_widget(project_layout)
        
        # 새로고침 버튼
        refresh_button = Button(
            text="🔄 새로고침",
            size_hint_y=None,
            height='40dp'
        )
        refresh_button.bind(on_press=self.refresh_projects)
        main_layout.add_widget(refresh_button)
        
        # 스크롤 영역
        scroll = ScrollView()
        self.content_layout = BoxLayout(
            orientation='vertical',
            size_hint_y=None,
            spacing=10
        )
        self.content_layout.bind(minimum_height=self.content_layout.setter('height'))
        scroll.add_widget(self.content_layout)
        main_layout.add_widget(scroll)
        
        self.add_widget(main_layout)
        
        # 프로젝트 로드
        self.refresh_projects()
    
    def refresh_projects(self, instance=None):
        """프로젝트 목록 새로고침"""
        projects = self.app_instance.storage.load_all_projects()
        project_names = [f"{p['title']} ({p['created_at'][:10]})" for p in projects]
        
        self.project_spinner.values = project_names if project_names else ['저장된 프로젝트가 없습니다']
        self.projects_data = {name: project for name, project in zip(project_names, projects)}
        
        if project_names:
            self.project_spinner.text = project_names[0]
            self.load_project_content(projects[0])
    
    def on_project_selected(self, spinner, text):
        """프로젝트 선택 시"""
        if text in self.projects_data:
            self.load_project_content(self.projects_data[text])
    
    def load_project_content(self, project):
        """프로젝트 내용 로드"""
        self.content_layout.clear_widgets()
        
        if not project:
            return
        
        # 프로젝트 정보
        info_layout = BoxLayout(orientation='vertical', size_hint_y=None, spacing=5)
        info_layout.bind(minimum_height=info_layout.setter('height'))
        
        info_label = Label(
            text=f"📄 {project['title']} | {project['category']}",
            font_size='16sp',
            size_hint_y=None,
            height='30dp'
        )
        info_layout.add_widget(info_label)
        self.content_layout.add_widget(info_layout)
        
        # 저장된 파일들 표시
        saved_files = project.get('saved_files', {})
        
        # 아코디언으로 버전별 표시
        accordion = Accordion(orientation='vertical', size_hint_y=None)
        accordion.bind(minimum_height=accordion.setter('height'))
        
        version_names = {
            'original': '원본 스크립트',
            'ted': 'TED 3분 말하기',
            'podcast': '팟캐스트 대화',
            'daily': '일상 대화'
        }
        
        for version_id, version_name in version_names.items():
            script_key = f"{version_id}_script"
            audio_key = f"{version_id}_audio"
            
            if script_key in saved_files:
                # 아코디언 아이템 생성
                item = AccordionItem(title=version_name, size_hint_y=None, height='40dp')
                
                item_layout = BoxLayout(orientation='vertical', padding=10, spacing=10)
                
                # 스크립트 내용
                try:
                    with open(saved_files[script_key], 'r', encoding='utf-8') as f:
                        script_content = f.read()
                    
                    script_label = Label(
                        text=script_content,
                        text_size=(None, None),
                        valign='top',
                        size_hint_y=None
                    )
                    script_label.bind(texture_size=script_label.setter('size'))
                    
                    script_scroll = ScrollView(size_hint=(1, 0.7))
                    script_scroll.add_widget(script_label)
                    item_layout.add_widget(script_scroll)
                    
                except Exception as e:
                    error_label = Label(text=f"스크립트 로드 실패: {e}")
                    item_layout.add_widget(error_label)
                
                # 오디오 재생 버튼
                if audio_key in saved_files:
                    audio_layout = BoxLayout(orientation='horizontal', size_hint_y=None, height='50dp')
                    
                    play_button = Button(
                        text="▶️ 재생",
                        size_hint_x=0.5
                    )
                    play_button.bind(on_press=lambda x, path=saved_files[audio_key]: self.play_audio(path))
                    
                    stop_button = Button(
                        text="⏹️ 정지",
                        size_hint_x=0.5
                    )
                    stop_button.bind(on_press=self.stop_audio)
                    
                    audio_layout.add_widget(play_button)
                    audio_layout.add_widget(stop_button)
                    item_layout.add_widget(audio_layout)
                
                item.add_widget(item_layout)
                accordion.add_widget(item)
        
        if accordion.children:
            self.content_layout.add_widget(accordion)
        else:
            no_content = Label(
                text="표시할 내용이 없습니다.",
                size_hint_y=None,
                height='50dp'
            )
            self.content_layout.add_widget(no_content)
    
    def play_audio(self, audio_path):
        """오디오 재생"""
        try:
            if self.current_sound:
                self.current_sound.stop()
            
            if isinstance(audio_path, str) and os.path.exists(audio_path):
                self.current_sound = SoundLoader.load(audio_path)
                if self.current_sound:
                    self.current_sound.play()
            elif isinstance(audio_path, dict):
                # 첫 번째 오디오 파일 재생
                for path in audio_path.values():
                    if isinstance(path, str) and os.path.exists(path):
                        self.current_sound = SoundLoader.load(path)
                        if self.current_sound:
                            self.current_sound.play()
                        break
        except Exception as e:
            print(f"오디오 재생 실패: {e}")
    
    def stop_audio(self, instance):
        """오디오 정지"""
        if self.current_sound:
            self.current_sound.stop()


class MyScriptsTab(TabbedPanelItem):
    """내 스크립트 탭"""
    
    def __init__(self, app_instance, **kwargs):
        super().__init__(**kwargs)
        self.text = "📚 내 스크립트"
        self.app_instance = app_instance
        
        main_layout = BoxLayout(orientation='vertical', padding=10, spacing=10)
        
        # 제목
        title = Label(
            text="📚 내 스크립트",
            font_size='20sp',
            size_hint_y=None,
            height='40dp'
        )
        main_layout.add_widget(title)
        
        # 새로고침 버튼
        refresh_button = Button(
            text="🔄 새로고침",
            size_hint_y=None,
            height='40dp'
        )
        refresh_button.bind(on_press=self.refresh_scripts)
        main_layout.add_widget(refresh_button)
        
        # 스크롤 영역
        scroll = ScrollView()
        self.scripts_layout = BoxLayout(
            orientation='vertical',
            size_hint_y=None,
            spacing=10
        )
        self.scripts_layout.bind(minimum_height=self.scripts_layout.setter('height'))
        scroll.add_widget(self.scripts_layout)
        main_layout.add_widget(scroll)
        
        self.add_widget(main_layout)
        
        # 스크립트 로드
        self.refresh_scripts()
    
    def refresh_scripts(self, instance=None):
        """스크립트 목록 새로고침"""
        self.scripts_layout.clear_widgets()
        
        projects = self.app_instance.storage.load_all_projects()
        
        if not projects:
            no_scripts = Label(
                text="저장된 스크립트가 없습니다.\n스크립트 생성 탭에서 새로운 스크립트를 만들어보세요!",
                size_hint_y=None,
                height='100dp',
                halign='center'
            )
            self.scripts_layout.add_widget(no_scripts)
            return
        
        for project in projects:
            # 프로젝트 카드 생성
            card_layout = BoxLayout(
                orientation='vertical',
                size_hint_y=None,
                height='120dp',
                padding=10,
                spacing=5
            )
            
            # 배경색 (간단한 테두리 효과)
            # Note: Kivy에서는 Canvas로 배경 처리해야 하지만, 여기서는 간소화
            
            # 제목과 정보
            title_label = Label(
                text=f"📄 {project['title']}",
                font_size='16sp',
                size_hint_y=None,
                height='30dp',
                halign='left'
            )
            title_label.text_size = (title_label.width, None)
            card_layout.add_widget(title_label)
            
            info_label = Label(
                text=f"카테고리: {project['category']} | 생성일: {project['created_at'][:10]}",
                font_size='12sp',
                size_hint_y=None,
                height='25dp',
                halign='left'
            )
            info_label.text_size = (info_label.width, None)
            card_layout.add_widget(info_label)
            
            # 버튼들
            button_layout = BoxLayout(
                orientation='horizontal',
                size_hint_y=None,
                height='40dp',
                spacing=10
            )
            
            view_button = Button(
                text="👁️ 보기",
                size_hint_x=0.4
            )
            view_button.bind(on_press=lambda x, p=project: self.view_project(p))
            
            delete_button = Button(
                text="🗑️ 삭제",
                size_hint_x=0.4,
                background_color=(1, 0.3, 0.3, 1)
            )
            delete_button.bind(on_press=lambda x, p=project: self.confirm_delete(p))
            
            button_layout.add_widget(view_button)
            button_layout.add_widget(delete_button)
            
            card_layout.add_widget(button_layout)
            self.scripts_layout.add_widget(card_layout)
    
    def view_project(self, project):
        """프로젝트 상세보기"""
        content_layout = BoxLayout(orientation='vertical', padding=10, spacing=10)
        
        # 제목
        title_label = Label(
            text=f"📄 {project['title']}",
            font_size='18sp',
            size_hint_y=None,
            height='40dp'
        )
        content_layout.add_widget(title_label)
        
        # 스크롤 영역으로 내용 표시
        scroll = ScrollView()
        info_layout = BoxLayout(orientation='vertical', size_hint_y=None, spacing=10)
        info_layout.bind(minimum_height=info_layout.setter('height'))
        
        # 저장된 스크립트들 표시
        saved_files = project.get('saved_files', {})
        for key, file_path in saved_files.items():
            if 'script' in key and isinstance(file_path, str):
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    version_label = Label(
                        text=f"📝 {key.replace('_', ' ').title()}:",
                        font_size='14sp',
                        size_hint_y=None,
                        height='30dp',
                        halign='left'
                    )
                    version_label.text_size = (version_label.width, None)
                    
                    content_label = Label(
                        text=content[:300] + "..." if len(content) > 300 else content,
                        text_size=(None, None),
                        size_hint_y=None,
                        halign='left',
                        valign='top'
                    )
                    content_label.bind(texture_size=content_label.setter('size'))
                    
                    info_layout.add_widget(version_label)
                    info_layout.add_widget(content_label)
                    
                except Exception as e:
                    error_label = Label(text=f"파일 로드 실패: {e}")
                    info_layout.add_widget(error_label)
        
        scroll.add_widget(info_layout)
        content_layout.add_widget(scroll)
        
        # 닫기 버튼
        close_button = Button(
            text="닫기",
            size_hint=(1, None),
            height='50dp'
        )
        content_layout.add_widget(close_button)
        
        popup = Popup(
            title="프로젝트 상세보기",
            content=content_layout,
            size_hint=(0.9, 0.8)
        )
        close_button.bind(on_press=popup.dismiss)
        popup.open()
    
    def confirm_delete(self, project):
        """삭제 확인"""
        content_layout = BoxLayout(orientation='vertical', padding=20, spacing=20)
        
        message = Label(
            text=f"'{project['title']}' 프로젝트를\n정말 삭제하시겠습니까?",
            halign='center'
        )
        content_layout.add_widget(message)
        
        button_layout = BoxLayout(orientation='horizontal', spacing=20)
        
        cancel_button = Button(text="취소", size_hint_x=0.5)
        delete_button = Button(
            text="삭제",
            size_hint_x=0.5,
            background_color=(1, 0.3, 0.3, 1)
        )
        
        button_layout.add_widget(cancel_button)
        button_layout.add_widget(delete_button)
        content_layout.add_widget(button_layout)
        
        popup = Popup(
            title="삭제 확인",
            content=content_layout,
            size_hint=(0.7, 0.4)
        )
        
        def delete_project(instance):
            if self.app_instance.storage.delete_project(project['project_id']):
                popup.dismiss()
                self.refresh_scripts()
                success_popup = Popup(
                    title="성공",
                    content=Label(text="삭제되었습니다!"),
                    size_hint=(0.6, 0.3)
                )
                success_popup.open()
            else:
                popup.dismiss()
                error_popup = Popup(
                    title="오류",
                    content=Label(text="삭제에 실패했습니다."),
                    size_hint=(0.6, 0.3)
                )
                error_popup.open()
        
        cancel_button.bind(on_press=popup.dismiss)
        delete_button.bind(on_press=delete_project)
        popup.open()


class SettingsTab(TabbedPanelItem):
    """설정 탭"""
    
    def __init__(self, app_instance, **kwargs):
        super().__init__(**kwargs)
        self.text = "⚙️ 설정"
        self.app_instance = app_instance
        
        main_layout = BoxLayout(orientation='vertical', padding=10, spacing=15)
        scroll = ScrollView()
        content_layout = BoxLayout(orientation='vertical', size_hint_y=None, spacing=20)
        content_layout.bind(minimum_height=content_layout.setter('height'))
        
        # 제목
        title = Label(
            text="⚙️ 환경 설정",
            font_size='20sp',
            size_hint_y=None,
            height='40dp'
        )
        content_layout.add_widget(title)
        
        # OpenAI 설정
        openai_layout = BoxLayout(orientation='vertical', size_hint_y=None, spacing=10)
        openai_layout.bind(minimum_height=openai_layout.setter('height'))
        
        openai_title = Label(
            text="🤖 OpenAI 설정",
            font_size='16sp',
            size_hint_y=None,
            height='30dp',
            halign='left'
        )
        openai_layout.add_widget(openai_title)
        
        # API Key
        api_layout = BoxLayout(orientation='vertical', size_hint_y=None, spacing=5)
        api_layout.bind(minimum_height=api_layout.setter('height'))
        
        api_label = Label(
            text="API Key:",
            size_hint_y=None,
            height='25dp',
            halign='left'
        )
        api_layout.add_widget(api_label)
        
        self.api_input = TextInput(
            text=self.app_instance.api_key,
            password=True,
            multiline=False,
            size_hint_y=None,
            height='40dp'
        )
        self.api_input.bind(text=self.on_api_key_change)
        api_layout.add_widget(self.api_input)
        
        openai_layout.add_widget(api_layout)
        
        # Model 선택
        model_layout = BoxLayout(orientation='horizontal', size_hint_y=None, height='40dp')
        model_layout.add_widget(Label(text="Model:", size_hint_x=0.3))
        self.model_spinner = Spinner(
            text=self.app_instance.model,
            values=['gpt-4o-mini', 'gpt-4o', 'gpt-4-turbo', 'gpt-3.5-turbo'],
            size_hint_x=0.7
        )
        self.model_spinner.bind(text=self.on_model_change)
        model_layout.add_widget(self.model_spinner)
        openai_layout.add_widget(model_layout)
        
        content_layout.add_widget(openai_layout)
        
        # TTS 설정
        tts_layout = BoxLayout(orientation='vertical', size_hint_y=None, spacing=10)
        tts_layout.bind(minimum_height=tts_layout.setter('height'))
        
        tts_title = Label(
            text="🎤 TTS 음성 설정",
            font_size='16sp',
            size_hint_y=None,
            height='30dp',
            halign='left'
        )
        tts_layout.add_widget(tts_title)
        
        voice_options = [
            'alloy', 'echo', 'fable', 'onyx', 'nova', 'shimmer'
        ]
        
        # 음성언어-1
        voice1_layout = BoxLayout(orientation='horizontal', size_hint_y=None, height='40dp')
        voice1_layout.add_widget(Label(text="음성언어-1:", size_hint_x=0.3))
        self.voice1_spinner = Spinner(
            text=self.app_instance.voice1,
            values=voice_options,
            size_hint_x=0.7
        )
        self.voice1_spinner.bind(text=self.on_voice1_change)
        voice1_layout.add_widget(self.voice1_spinner)
        tts_layout.add_widget(voice1_layout)
        
        # 음성언어-2
        voice2_layout = BoxLayout(orientation='horizontal', size_hint_y=None, height='40dp')
        voice2_layout.add_widget(Label(text="음성언어-2:", size_hint_x=0.3))
        self.voice2_spinner = Spinner(
            text=self.app_instance.voice2,
            values=voice_options,
            size_hint_x=0.7
        )
        self.voice2_spinner.bind(text=self.on_voice2_change)
        voice2_layout.add_widget(self.voice2_spinner)
        tts_layout.add_widget(voice2_layout)
        
        content_layout.add_widget(tts_layout)
        
        # 테스트 버튼들
        test_layout = BoxLayout(orientation='vertical', size_hint_y=None, spacing=10)
        test_layout.bind(minimum_height=test_layout.setter('height'))
        
        test_title = Label(
            text="🎵 TTS 테스트",
            font_size='16sp',
            size_hint_y=None,
            height='30dp',
            halign='left'
        )
        test_layout.add_widget(test_title)
        
        test_buttons_layout = BoxLayout(orientation='horizontal', size_hint_y=None, height='50dp')
        
        test1_button = Button(
            text="🎙️ 음성언어-1 테스트",
            size_hint_x=0.5
        )
        test1_button.bind(on_press=self.test_voice1)
        
        test2_button = Button(
            text="🎤 음성언어-2 테스트",
            size_hint_x=0.5
        )
        test2_button.bind(on_press=self.test_voice2)
        
        test_buttons_layout.add_widget(test1_button)
        test_buttons_layout.add_widget(test2_button)
        test_layout.add_widget(test_buttons_layout)
        
        content_layout.add_widget(test_layout)
        
        # 시스템 정보
        system_layout = BoxLayout(orientation='vertical', size_hint_y=None, spacing=10)
        system_layout.bind(minimum_height=system_layout.setter('height'))
        
        system_title = Label(
            text="📊 시스템 정보",
            font_size='16sp',
            size_hint_y=None,
            height='30dp',
            halign='left'
        )
        system_layout.add_widget(system_title)
        
        projects_count = len(self.app_instance.storage.load_all_projects())
        system_info = Label(
            text=f"저장된 프로젝트: {projects_count}개\n저장 위치: {self.app_instance.storage.base_dir}",
            size_hint_y=None,
            halign='left'
        )
        system_info.bind(texture_size=system_info.setter('size'))
        system_layout.add_widget(system_info)
        
        content_layout.add_widget(system_layout)
        
        scroll.add_widget(content_layout)
        main_layout.add_widget(scroll)
        self.add_widget(main_layout)
    
    def on_api_key_change(self, instance, value):
        """API Key 변경"""
        self.app_instance.api_key = value
        self.app_instance.save_settings()
    
    def on_model_change(self, spinner, text):
        """Model 변경"""
        self.app_instance.model = text
        self.app_instance.save_settings()
    
    def on_voice1_change(self, spinner, text):
        """Voice1 변경"""
        self.app_instance.voice1 = text
        self.app_instance.save_settings()
    
    def on_voice2_change(self, spinner, text):
        """Voice2 변경"""
        self.app_instance.voice2 = text
        self.app_instance.save_settings()
    
    def test_voice1(self, instance):
        """음성언어-1 테스트"""
        self._test_voice("Hello, this is voice one testing.", self.app_instance.voice1, "음성언어-1")
    
    def test_voice2(self, instance):
        """음성언어-2 테스트"""
        self._test_voice("Hello, this is voice two testing.", self.app_instance.voice2, "음성언어-2")
    
    def _test_voice(self, text, voice, voice_name):
        """음성 테스트 실행"""
        if not self.app_instance.api_key:
            popup = Popup(
                title="오류",
                content=Label(text="OpenAI API Key가 필요합니다!"),
                size_hint=(0.8, 0.3)
            )
            popup.open()
            return
        
        # 로딩 표시
        loading = Popup(
            title="음성 테스트",
            content=Label(text=f"{voice_name} 테스트 중..."),
            size_hint=(0.8, 0.3),
            auto_dismiss=False
        )
        loading.open()
        
        def test_background():
            try:
                audio_file = generate_audio_with_openai_tts(
                    text, self.app_instance.api_key, voice
                )
                
                Clock.schedule_once(lambda dt: self._play_test_result(loading, audio_file, voice_name), 0)
            except Exception as e:
                Clock.schedule_once(lambda dt: self._show_test_error(loading, str(e)), 0)
        
        Clock.schedule_once(lambda dt: test_background(), 0.1)
    
    def _play_test_result(self, loading_popup, audio_file, voice_name):
        """테스트 결과 재생"""
        loading_popup.dismiss()
        
        if audio_file and os.path.exists(audio_file):
            try:
                sound = SoundLoader.load(audio_file)
                if sound:
                    sound.play()
                    
                    success_popup = Popup(
                        title="성공",
                        content=Label(text=f"{voice_name} 테스트 완료!"),
                        size_hint=(0.8, 0.3)
                    )
                    success_popup.open()
                else:
                    raise Exception("사운드 로드 실패")
            except Exception as e:
                self._show_test_error(None, f"재생 실패: {e}")
        else:
            self._show_test_error(None, "음성 생성 실패")
    
    def _show_test_error(self, loading_popup, error_msg):
        """테스트 에러 표시"""
        if loading_popup:
            loading_popup.dismiss()
        
        error_popup = Popup(
            title="오류",
            content=Label(text=f"테스트 실패: {error_msg}"),
            size_hint=(0.8, 0.3)
        )
        error_popup.open()


class MyTalkApp(App):
    """메인 애플리케이션 클래스"""
    
    # 앱 속성들
    api_key = StringProperty('')
    model = StringProperty('gpt-4o-mini')
    voice1 = StringProperty('alloy')
    voice2 = StringProperty('nova')
    
    def build(self):
        """앱 빌드"""
        self.title = "MyTalk - 영어 학습 도우미"
        
        # 저장소 초기화
        self.storage = SimpleStorage()
        
        # 설정 로드
        self.load_settings()
        
        # 메인 패널
        root = TabbedPanel(do_default_tab=False)
        
        # 탭들 추가
        script_tab = ScriptCreationTab(self)
        practice_tab = PracticeTab(self)
        scripts_tab = MyScriptsTab(self)
        settings_tab = SettingsTab(self)
        
        root.add_widget(script_tab)
        root.add_widget(practice_tab)
        root.add_widget(scripts_tab)
        root.add_widget(settings_tab)
        
        return root
    
    def load_settings(self):
        """설정 로드"""
        settings_file = self.storage.base_dir / "settings.json"
        try:
            if settings_file.exists():
                with open(settings_file, 'r') as f:
                    settings = json.load(f)
                
                self.api_key = settings.get('api_key', '')
                self.model = settings.get('model', 'gpt-4o-mini')
                self.voice1 = settings.get('voice1', 'alloy')
                self.voice2 = settings.get('voice2', 'nova')
        except Exception as e:
            print(f"설정 로드 실패: {e}")
    
    def save_settings(self):
        """설정 저장"""
        settings = {
            'api_key': self.api_key,
            'model': self.model,
            'voice1': self.voice1,
            'voice2': self.voice2
        }
        
        settings_file = self.storage.base_dir / "settings.json"
        try:
            with open(settings_file, 'w') as f:
                json.dump(settings, f)
        except Exception as e:
            print(f"설정 저장 실패: {e}")
    
    def on_pause(self):
        """앱 일시정지 시"""
        return True
    
    def on_resume(self):
        """앱 재개 시"""
        pass


if __name__ == '__main__':
    MyTalkApp().run()