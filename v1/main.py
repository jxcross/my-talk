"""
MyTalk - Personal English Speaking App
개인용 영어 말하기 학습 앱
"""

import streamlit as st
import os
import json
import sqlite3
from datetime import datetime
import base64
from pathlib import Path
import asyncio
#import edge_tts
from tts_module import TTSManager, get_tts_settings, generate_audio_with_fallback, create_audio_player, get_browser_tts_script

import tempfile
from PIL import Image
import io

# LLM Providers
import openai
from anthropic import Anthropic
import google.generativeai as genai

# Google Drive
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload

# 페이지 설정
st.set_page_config(
    page_title="MyTalk - 영어 말하기",
    page_icon="🎙️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# CSS for mobile optimization
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
    }
    .audio-player {
        width: 100%;
    }
    div[data-testid="stSidebar"] {
        min-width: 250px;
    }
    .script-container {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 10px;
        margin: 1rem 0;
    }
    .script-text {
        font-size: 1.1rem;
        line-height: 1.8;
        color: #1f1f1f;
    }
    .translation-text {
        font-size: 0.95rem;
        color: #666;
        margin-top: 0.5rem;
    }
    @media (max-width: 768px) {
        .stApp {
            padding: 0.5rem;
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
        'current_script': None,
        'audio_file': None,
        'scripts_history': [],
        'tts_engine': 'auto',  # 변경
        'tts_voice': 'en'      # 변경
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

# Database functions
class Database:
    def __init__(self, db_path='mytalk.db'):
        self.db_path = db_path
        self.init_db()
    
    def init_db(self):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS scripts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                translation TEXT,
                category TEXT,
                audio_path TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
        conn.close()
    
    def save_script(self, title, content, translation='', category='general', audio_path=''):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('''
            INSERT INTO scripts (title, content, translation, category, audio_path)
            VALUES (?, ?, ?, ?, ?)
        ''', (title, content, translation, category, audio_path))
        script_id = c.lastrowid
        conn.commit()
        conn.close()
        return script_id
    
    def get_scripts(self, category=None):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        if category:
            c.execute('SELECT * FROM scripts WHERE category = ? ORDER BY created_at DESC', (category,))
        else:
            c.execute('SELECT * FROM scripts ORDER BY created_at DESC')
        scripts = c.fetchall()
        conn.close()
        return scripts
    
    def delete_script(self, script_id):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('DELETE FROM scripts WHERE id = ?', (script_id,))
        conn.commit()
        conn.close()
    
    def search_scripts(self, query):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('''
            SELECT * FROM scripts 
            WHERE title LIKE ? OR content LIKE ? 
            ORDER BY created_at DESC
        ''', (f'%{query}%', f'%{query}%'))
        scripts = c.fetchall()
        conn.close()
        return scripts

# LLM Provider Class
class LLMProvider:
    def __init__(self, provider, api_key, model):
        self.provider = provider
        self.api_key = api_key
        self.model = model
        
        if provider == 'OpenAI':
            openai.api_key = api_key
        elif provider == 'Anthropic':
            self.client = Anthropic(api_key=api_key)
        elif provider == 'Google':
            genai.configure(api_key=api_key)
    
    def generate_script(self, prompt, image=None):
        try:
            if self.provider == 'OpenAI':
                messages = [{"role": "user", "content": prompt}]
                if image:
                    # Convert image to base64
                    buffered = io.BytesIO()
                    image.save(buffered, format="PNG")
                    img_str = base64.b64encode(buffered.getvalue()).decode()
                    messages[0]["content"] = [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_str}"}}
                    ]
                
                response = openai.ChatCompletion.create(
                    model=self.model,
                    messages=messages,
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
            st.error(f"LLM 생성 오류: {str(e)}")
            return None
    
    def translate(self, text, target_lang='ko'):
        prompt = f"""
        Translate the following English text to Korean. 
        Provide natural, fluent translation:
        
        {text}
        """
        return self.generate_script(prompt)

# TTS Functions
# async def generate_tts(text, voice='en-US-AriaNeural', output_path='output.mp3'):
#     """Generate TTS using edge-tts"""
#     try:
#         communicate = edge_tts.Communicate(text, voice)
#         await communicate.save(output_path)
#         return output_path
#     except Exception as e:
#         st.error(f"TTS 생성 오류: {str(e)}")
#         return None

def get_audio_player(audio_path):
    """Create audio player HTML"""
    with open(audio_path, 'rb') as f:
        audio_bytes = f.read()
    audio_b64 = base64.b64encode(audio_bytes).decode()
    
    audio_html = f"""
    <audio controls class="audio-player" loop>
        <source src="data:audio/mp3;base64,{audio_b64}" type="audio/mp3">
    </audio>
    """
    return audio_html

# Script Templates
class ScriptTemplates:
    @staticmethod
    def ted_talk(topic):
        return f"""
        Create a 3-minute TED talk script about {topic}.
        Structure:
        1. Powerful opening hook
        2. Personal story or example
        3. Main insights (2-3 key points)
        4. Call to action
        
        Style: Inspiring, clear, conversational
        Length: About 400-450 words
        """
    
    @staticmethod
    def podcast_dialogue(topic):
        return f"""
        Create a natural 2-person podcast dialogue about {topic}.
        
        Format:
        Host: [Introduction and questions]
        Guest: [Expert insights and examples]
        
        Style: Casual, informative, engaging
        Include: Natural expressions, follow-up questions
        Length: About 400 words total
        """
    
    @staticmethod
    def daily_conversation(situation):
        return f"""
        Create a practical daily conversation for: {situation}
        
        Format:
        Person A: [Initiates conversation]
        Person B: [Responds naturally]
        
        Include: Common phrases, polite expressions, real-life vocabulary
        Style: Natural, practical, useful for daily life
        Length: About 300 words
        """

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
                models = ['claude-3-haiku', 'claude-3-sonnet', 'claude-3-opus']
            else:
                models = ['gemini-pro', 'gemini-pro-vision']
            
            model = st.selectbox("Model 선택", models)
            st.session_state.model = model
        
        api_key = st.text_input(
            "API Key",
            value=st.session_state.api_key,
            type="password"
        )
        st.session_state.api_key = api_key
    
    with st.expander("🔊 TTS 설정"):
        # TTS 매니저 초기화
        tts_manager = TTSManager()
        
        if not tts_manager.available_engines:
            st.error("❌ TTS 엔진이 설치되지 않았습니다.")
            st.code("pip install gtts pyttsx3", language="bash")
            st.info("gtts를 설치하면 고품질 음성을 사용할 수 있습니다.")
        else:
            st.success(f"✅ 사용 가능: {', '.join(tts_manager.available_engines)}")
            
            # 엔진 선택
            col1, col2 = st.columns(2)
            
            with col1:
                engine_options = ['auto (자동)'] + tts_manager.available_engines
                selected_engine = st.selectbox(
                    "TTS 엔진",
                    engine_options,
                    help="auto를 선택하면 가장 안정적인 엔진을 자동으로 선택합니다"
                )
                
                if selected_engine == 'auto (자동)':
                    st.session_state.tts_engine = 'auto'
                else:
                    st.session_state.tts_engine = selected_engine
            
            with col2:
                # 음성 선택
                if st.session_state.tts_engine in ['auto', 'gTTS']:
                    voice_options = {
                        '영어 (미국)': 'en',
                        '영어 (영국)': 'en-uk', 
                        '영어 (호주)': 'en-au',
                        '한국어': 'ko'
                    }
                    selected_voice_name = st.selectbox("음성 언어", list(voice_options.keys()))
                    st.session_state.tts_voice = voice_options[selected_voice_name]
                    
                elif st.session_state.tts_engine == 'edge-tts':
                    voice_options = {
                        '영어 여성': 'en-US-AriaNeural',
                        '영어 남성': 'en-US-GuyNeural',
                        '한국어 여성': 'ko-KR-SunHiNeural'
                    }
                    selected_voice_name = st.selectbox("음성 선택", list(voice_options.keys()))
                    st.session_state.tts_voice = voice_options[selected_voice_name]
                else:
                    st.info("시스템 기본 음성을 사용합니다")
                    st.session_state.tts_voice = None
            
            # 테스트 버튼
            if st.button("🔊 음성 테스트"):
                test_text = "Hello! This is a test of the text to speech system."
                with st.spinner("테스트 중..."):
                    audio_path = generate_audio_with_fallback(
                        test_text, 
                        st.session_state.tts_engine,
                        st.session_state.tts_voice
                    )
                    if audio_path:
                        st.audio(audio_path)
                        st.success("✅ TTS가 정상 작동합니다!")
                    else:
                        st.error("❌ TTS 생성 실패")
                        st.info("브라우저 내장 TTS를 사용해보세요:")
                        st.markdown(get_browser_tts_script(test_text), unsafe_allow_html=True)

    
    with st.expander("☁️ Google Drive 설정"):
        st.info("Google Drive API 설정이 필요합니다. (선택사항)")
        uploaded_file = st.file_uploader(
            "Service Account JSON 파일 업로드",
            type=['json']
        )
        if uploaded_file:
            st.success("✅ Google Drive 연동 준비 완료")
            st.session_state.google_drive_enabled = True

def create_script_page():
    st.header("✍️ 영어 스크립트 생성")
    
    # Input method selection
    input_method = st.radio(
        "입력 방법 선택",
        ["텍스트 입력", "이미지 업로드", "파일 업로드"],
        horizontal=True
    )
    
    input_content = None
    image = None
    
    if input_method == "텍스트 입력":
        input_content = st.text_area(
            "키워드, 문장, 또는 주제를 입력하세요",
            placeholder="예: 'AI의 미래', '커피 주문하기', 'Yesterday I went to...'",
            height=100
        )
    
    elif input_method == "이미지 업로드":
        uploaded_image = st.file_uploader(
            "이미지를 업로드하세요",
            type=['png', 'jpg', 'jpeg']
        )
        if uploaded_image:
            image = Image.open(uploaded_image)
            st.image(image, caption="업로드된 이미지", use_column_width=True)
            input_content = "Describe this image and create an English learning script based on it."
    
    else:  # 파일 업로드
        uploaded_file = st.file_uploader(
            "텍스트 파일을 업로드하세요",
            type=['txt', 'md']
        )
        if uploaded_file:
            input_content = uploaded_file.read().decode('utf-8')
            st.text_area("파일 내용", input_content, height=100, disabled=True)
    
    # Script type selection
    script_type = st.selectbox(
        "스크립트 유형",
        ["자유 주제", "일상 대화", "비즈니스", "여행", "교육"]
    )
    
    # Generate button
    if st.button("🚀 스크립트 생성", type="primary"):
        if not st.session_state.api_key:
            st.error("먼저 설정에서 API Key를 입력해주세요!")
            return
        
        if not input_content:
            st.error("내용을 입력해주세요!")
            return
        
        with st.spinner("스크립트 생성 중..."):
            # Prepare prompt
            if script_type == "자유 주제":
                prompt = f"Create an English learning script about: {input_content}"
            else:
                prompt = f"Create a {script_type} English learning script about: {input_content}"
            
            prompt += """
            Requirements:
            1. Natural, conversational English
            2. Include useful expressions and vocabulary
            3. Appropriate for intermediate learners
            4. About 200-300 words
            
            Format:
            Title: [Clear, descriptive title]
            Content: [The main script]
            Key Phrases: [3-5 important phrases to remember]
            """
            
            # Generate script
            llm = LLMProvider(
                st.session_state.api_provider,
                st.session_state.api_key,
                st.session_state.model
            )
            
            result = llm.generate_script(prompt, image)
            
            if result:
                st.session_state.current_script = result
                st.success("✅ 스크립트 생성 완료!")
                
                # Display script
                st.markdown("### 📝 생성된 스크립트")
                st.markdown(f'<div class="script-container"><div class="script-text">{result}</div></div>', 
                          unsafe_allow_html=True)
                
                # Generate audio
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    if st.button("🔊 음성 생성"):
                        with st.spinner("음성 생성 중..."):
                            audio_path = generate_audio_with_fallback(
                                result,
                                st.session_state.tts_engine,
                                st.session_state.tts_voice
                            )
                            if audio_path:
                                st.session_state.audio_file = audio_path
                                st.audio(audio_path)
                                st.success("✅ 음성 생성 완료!")
                            else:
                                st.error("❌ 음성 생성 실패")
                                # 브라우저 TTS 폴백 제공
                                if st.checkbox("브라우저 TTS 사용"):
                                    st.markdown(get_browser_tts_script(result), unsafe_allow_html=True)

                
                with col2:
                    if st.button("💾 저장"):
                        # Generate title from content
                        title = result.split('\n')[0][:50] if result else "Untitled"
                        
                        db = Database()
                        script_id = db.save_script(
                            title=title,
                            content=result,
                            category=script_type,
                            audio_path=st.session_state.audio_file or ''
                        )
                        st.success(f"✅ 저장 완료! (ID: {script_id})")
                
                with col3:
                    if st.button("🔄 번역"):
                        with st.spinner("번역 중..."):
                            translation = llm.translate(result)
                            if translation:
                                st.markdown("### 🇰🇷 한국어 번역")
                                st.markdown(f'<div class="translation-text">{translation}</div>', 
                                          unsafe_allow_html=True)

def practice_page():
    st.header("🎯 영어 연습")
    
    practice_type = st.selectbox(
        "연습 유형 선택",
        ["TED 3분 말하기", "PODCAST 2인 대화", "일상 생활 대화"]
    )
    
    topic = st.text_input(
        "주제 입력",
        placeholder="예: 'Climate change', 'Morning routine', 'Technology trends'"
    )
    
    if st.button("📝 스크립트 생성", type="primary"):
        if not st.session_state.api_key:
            st.error("먼저 설정에서 API Key를 입력해주세요!")
            return
        
        if not topic:
            st.error("주제를 입력해주세요!")
            return
        
        with st.spinner("스크립트 생성 중..."):
            llm = LLMProvider(
                st.session_state.api_provider,
                st.session_state.api_key,
                st.session_state.model
            )
            
            # Select template
            templates = ScriptTemplates()
            if practice_type == "TED 3분 말하기":
                prompt = templates.ted_talk(topic)
            elif practice_type == "PODCAST 2인 대화":
                prompt = templates.podcast_dialogue(topic)
            else:
                prompt = templates.daily_conversation(topic)
            
            result = llm.generate_script(prompt)
            
            if result:
                # Display in two columns
                col1, col2 = st.columns([1, 1])
                
                with col1:
                    st.markdown("### 🇺🇸 English Script")
                    st.markdown(f'<div class="script-container"><div class="script-text">{result}</div></div>', 
                              unsafe_allow_html=True)
                    
                    # Audio controls
                    if st.button("🔊 음성 재생"):
                        with st.spinner("음성 생성 중..."):
                            audio_path = generate_audio_with_fallback(
                                result,
                                st.session_state.tts_engine,
                                st.session_state.tts_voice
                            )
                            if audio_path:
                                st.audio(audio_path, format='audio/mp3')
                            else:
                                st.error("음성 생성 실패")
                                st.markdown(get_browser_tts_script(result), unsafe_allow_html=True)

                
                with col2:
                    st.markdown("### 🇰🇷 한국어 번역")
                    if st.button("번역하기"):
                        with st.spinner("번역 중..."):
                            translation = llm.translate(result)
                            if translation:
                                st.markdown(f'<div class="script-container"><div class="translation-text">{translation}</div></div>', 
                                          unsafe_allow_html=True)
                
                # Save button
                if st.button("💾 저장하기"):
                    db = Database()
                    script_id = db.save_script(
                        title=f"{practice_type}: {topic}",
                        content=result,
                        category=practice_type
                    )
                    st.success(f"✅ 저장 완료! (ID: {script_id})")

def library_page():
    st.header("📚 저장된 스크립트")
    
    db = Database()
    
    # Search and filter
    col1, col2 = st.columns([2, 1])
    with col1:
        search_query = st.text_input("🔍 검색", placeholder="제목 또는 내용 검색...")
    with col2:
        category_filter = st.selectbox(
            "카테고리",
            ["전체", "자유 주제", "일상 대화", "비즈니스", "여행", "교육", 
             "TED 3분 말하기", "PODCAST 2인 대화", "일상 생활 대화"]
        )
    
    # Get scripts
    if search_query:
        scripts = db.search_scripts(search_query)
    elif category_filter != "전체":
        scripts = db.get_scripts(category_filter)
    else:
        scripts = db.get_scripts()
    
    # Display scripts
    if scripts:
        st.write(f"총 {len(scripts)}개의 스크립트")
        
        for script in scripts:
            script_id, title, content, translation, category, audio_path, created_at, _ = script
            
            with st.expander(f"📝 {title} - {category} ({created_at[:10]})"):
                tab1, tab2, tab3 = st.tabs(["영어", "번역", "설정"])
                
                with tab1:
                    st.markdown(content)
                    if audio_path and os.path.exists(audio_path):
                        st.audio(audio_path)
                    else:
                        if st.button(f"🔊 음성 생성", key=f"tts_{script_id}"):
                            with st.spinner("음성 생성 중..."):
                                audio_path = generate_audio_with_fallback(
                                    content,
                                    st.session_state.tts_engine,
                                    st.session_state.tts_voice
                                )
                                if audio_path:
                                    st.audio(audio_path)
                                    # DB에 경로 저장 (선택사항)
                                    # db.update_audio_path(script_id, audio_path)
                                else:
                                    st.error("음성 생성 실패")
                
                with tab2:
                    if translation:
                        st.markdown(translation)
                    else:
                        st.info("번역이 없습니다.")
                
                with tab3:
                    if st.button(f"🗑️ 삭제", key=f"del_{script_id}"):
                        db.delete_script(script_id)
                        st.success("삭제되었습니다!")
                        st.rerun()
    else:
        st.info("저장된 스크립트가 없습니다.")

# Main App
def main():
    init_session_state()
    
    st.title("🎙️ MyTalk - 나만의 영어 말하기")
    
    # Navigation
    tabs = st.tabs(["📝 생성", "🎯 연습", "📚 보관함", "⚙️ 설정"])
    
    with tabs[0]:
        create_script_page()
    
    with tabs[1]:
        practice_page()
    
    with tabs[2]:
        library_page()
    
    with tabs[3]:
        settings_page()
    
    # Footer
    st.markdown("---")
    st.markdown(
        """
        <div style='text-align: center; color: #666; font-size: 0.8rem;'>
        MyTalk v1.0 | Personal English Learning Assistant<br>
        Copyright © 2025 Sunggeun Han (mysomang@gmail.com)<br>
        Made with ❤️ using Streamlit
        </div>
        """,
        unsafe_allow_html=True
    )

if __name__ == "__main__":
    main()