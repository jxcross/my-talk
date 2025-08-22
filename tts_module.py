"""
TTS Module - 다양한 TTS 엔진 지원
여러 TTS 옵션을 제공하여 안정성 확보
"""

import os
import tempfile
import streamlit as st
from typing import Optional
import base64

# TTS 엔진들
class TTSManager:
    def __init__(self):
        self.engine = None
        self.available_engines = self.check_available_engines()
    
    def check_available_engines(self):
        """사용 가능한 TTS 엔진 확인"""
        engines = []
        
        # gTTS 확인
        try:
            import gtts
            engines.append('gTTS')
        except ImportError:
            pass
        
        # pyttsx3 확인
        try:
            import pyttsx3
            engines.append('pyttsx3')
        except ImportError:
            pass
        
        # edge-tts 확인 (불안정할 수 있음)
        try:
            import edge_tts
            engines.append('edge-tts')
        except ImportError:
            pass
        
        return engines
    
    def generate_with_gtts(self, text: str, lang: str = 'en', output_path: str = None) -> Optional[str]:
        """gTTS를 사용한 음성 생성 (권장)"""
        try:
            from gtts import gTTS
            
            if not output_path:
                output_path = tempfile.NamedTemporaryFile(suffix='.mp3', delete=False).name
            
            # 언어 코드 매핑
            lang_map = {
                'en-US': 'en',
                'en-GB': 'en',
                'en-AU': 'en-au',
                'ko-KR': 'ko'
            }
            
            tts_lang = lang_map.get(lang, 'en')
            
            # TTS 생성
            tts = gTTS(text=text, lang=tts_lang, slow=False)
            tts.save(output_path)
            
            return output_path
            
        except Exception as e:
            st.error(f"gTTS 오류: {str(e)}")
            return None
    
    def generate_with_pyttsx3(self, text: str, voice_id: str = None, output_path: str = None) -> Optional[str]:
        """pyttsx3를 사용한 음성 생성 (오프라인)"""
        try:
            import pyttsx3
            
            if not output_path:
                output_path = tempfile.NamedTemporaryFile(suffix='.mp3', delete=False).name
            
            # 엔진 초기화
            engine = pyttsx3.init()
            
            # 음성 설정
            if voice_id:
                voices = engine.getProperty('voices')
                for voice in voices:
                    if voice_id in voice.id:
                        engine.setProperty('voice', voice.id)
                        break
            
            # 속도 설정
            engine.setProperty('rate', 150)
            
            # 파일로 저장
            engine.save_to_file(text, output_path)
            engine.runAndWait()
            
            return output_path
            
        except Exception as e:
            st.error(f"pyttsx3 오류: {str(e)}")
            return None
    
    def generate_with_edge_tts_safe(self, text: str, voice: str = 'en-US-AriaNeural', output_path: str = None) -> Optional[str]:
        """edge-tts를 안전하게 사용 (에러 처리 강화)"""
        try:
            import edge_tts
            import asyncio
            
            if not output_path:
                output_path = tempfile.NamedTemporaryFile(suffix='.mp3', delete=False).name
            
            async def generate():
                try:
                    # 짧은 타임아웃 설정
                    communicate = edge_tts.Communicate(text, voice)
                    await asyncio.wait_for(
                        communicate.save(output_path),
                        timeout=30.0  # 30초 타임아웃
                    )
                    return True
                except asyncio.TimeoutError:
                    return False
                except Exception:
                    return False
            
            # 비동기 실행
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            success = loop.run_until_complete(generate())
            loop.close()
            
            if success and os.path.exists(output_path):
                return output_path
            return None
            
        except Exception as e:
            # edge-tts 실패시 조용히 None 반환
            return None
    
    def generate_tts(self, text: str, engine: str = 'auto', voice: str = 'en-US', output_path: str = None) -> Optional[str]:
        """통합 TTS 생성 함수"""
        
        if not text:
            return None
        
        # 자동 선택 모드
        if engine == 'auto':
            # gTTS 우선 시도
            if 'gTTS' in self.available_engines:
                result = self.generate_with_gtts(text, voice, output_path)
                if result:
                    return result
            
            # edge-tts 시도
            if 'edge-tts' in self.available_engines:
                result = self.generate_with_edge_tts_safe(text, voice, output_path)
                if result:
                    return result
            
            # pyttsx3 시도
            if 'pyttsx3' in self.available_engines:
                result = self.generate_with_pyttsx3(text, voice, output_path)
                if result:
                    return result
        
        # 특정 엔진 선택
        elif engine == 'gTTS':
            return self.generate_with_gtts(text, voice, output_path)
        elif engine == 'pyttsx3':
            return self.generate_with_pyttsx3(text, voice, output_path)
        elif engine == 'edge-tts':
            return self.generate_with_edge_tts_safe(text, voice, output_path)
        
        return None

# Streamlit 컴포넌트용 헬퍼 함수들
def get_tts_settings():
    """TTS 설정 UI"""
    tts_manager = TTSManager()
    
    st.subheader("🔊 TTS 설정")
    
    # 사용 가능한 엔진 표시
    if not tts_manager.available_engines:
        st.error("사용 가능한 TTS 엔진이 없습니다. 패키지를 설치해주세요.")
        st.code("pip install gtts pyttsx3", language="bash")
        return None, None
    
    st.success(f"사용 가능한 엔진: {', '.join(tts_manager.available_engines)}")
    
    # 엔진 선택
    engine_options = ['auto (자동 선택)'] + tts_manager.available_engines
    selected_engine = st.selectbox(
        "TTS 엔진 선택",
        engine_options,
        help="auto를 선택하면 가장 안정적인 엔진을 자동으로 선택합니다"
    )
    
    if selected_engine == 'auto (자동 선택)':
        selected_engine = 'auto'
    
    # 음성 선택
    if selected_engine in ['auto', 'gTTS']:
        voice_options = {
            '영어 (미국)': 'en',
            '영어 (영국)': 'en-uk',
            '영어 (호주)': 'en-au',
            '한국어': 'ko'
        }
        selected_voice_name = st.selectbox("음성 선택", list(voice_options.keys()))
        selected_voice = voice_options[selected_voice_name]
        
    elif selected_engine == 'edge-tts':
        voice_options = {
            '영어 여성 (Aria)': 'en-US-AriaNeural',
            '영어 여성 (Jenny)': 'en-US-JennyNeural',
            '영어 남성 (Guy)': 'en-US-GuyNeural',
            '영국 여성': 'en-GB-SoniaNeural',
            '영국 남성': 'en-GB-RyanNeural',
            '호주 여성': 'en-AU-NatashaNeural',
            '한국어 여성': 'ko-KR-SunHiNeural',
            '한국어 남성': 'ko-KR-InJoonNeural'
        }
        selected_voice_name = st.selectbox("음성 선택", list(voice_options.keys()))
        selected_voice = voice_options[selected_voice_name]
        
    else:  # pyttsx3
        selected_voice = None
        st.info("시스템 기본 음성을 사용합니다")
    
    return selected_engine, selected_voice

def generate_audio_with_fallback(text: str, engine: str = 'auto', voice: str = 'en') -> Optional[str]:
    """폴백 기능이 있는 안전한 TTS 생성"""
    tts_manager = TTSManager()
    
    # 첫 시도
    audio_path = tts_manager.generate_tts(text, engine, voice)
    
    # 실패시 다른 엔진으로 재시도
    if not audio_path and engine != 'auto':
        st.warning(f"{engine} 실패. 다른 엔진으로 시도 중...")
        audio_path = tts_manager.generate_tts(text, 'auto', voice)
    
    return audio_path

def create_audio_player(audio_path: str, autoplay: bool = False, loop: bool = False) -> str:
    """오디오 플레이어 HTML 생성"""
    if not audio_path or not os.path.exists(audio_path):
        return None
    
    with open(audio_path, 'rb') as f:
        audio_bytes = f.read()
    
    audio_b64 = base64.b64encode(audio_bytes).decode()
    
    autoplay_attr = 'autoplay' if autoplay else ''
    loop_attr = 'loop' if loop else ''
    
    audio_html = f"""
    <audio controls {autoplay_attr} {loop_attr} style="width: 100%;">
        <source src="data:audio/mp3;base64,{audio_b64}" type="audio/mp3">
        브라우저가 오디오를 지원하지 않습니다.
    </audio>
    """
    
    return audio_html

# 브라우저 내장 TTS (백업용)
def get_browser_tts_script(text: str, lang: str = 'en-US') -> str:
    """브라우저 Web Speech API 사용 (최후의 수단)"""
    
    # JavaScript 문자열 이스케이프
    escaped_text = text.replace("'", "\\'").replace("\n", "\\n")
    
    return f"""
    <script>
    function speakText() {{
        if ('speechSynthesis' in window) {{
            // 이전 음성 중지
            window.speechSynthesis.cancel();
            
            const utterance = new SpeechSynthesisUtterance('{escaped_text}');
            utterance.lang = '{lang}';
            utterance.rate = 1.0;
            utterance.pitch = 1.0;
            
            // 음성 선택 (가능한 경우)
            const voices = window.speechSynthesis.getVoices();
            const voice = voices.find(v => v.lang === '{lang}');
            if (voice) {{
                utterance.voice = voice;
            }}
            
            window.speechSynthesis.speak(utterance);
        }} else {{
            alert('브라우저가 음성 합성을 지원하지 않습니다.');
        }}
    }}
    </script>
    <button onclick="speakText()" style="
        background-color: #4CAF50;
        color: white;
        border: none;
        padding: 10px 20px;
        border-radius: 5px;
        cursor: pointer;
        font-size: 16px;
        margin: 10px 0;
    ">
        🔊 브라우저 TTS로 재생
    </button>
    """

# 사용 예제
if __name__ == "__main__":
    st.title("TTS 테스트")
    
    # TTS 설정
    engine, voice = get_tts_settings()
    
    # 텍스트 입력
    text = st.text_area("텍스트 입력", "Hello! This is a test of the text to speech system.")
    
    if st.button("음성 생성"):
        if engine and text:
            with st.spinner("음성 생성 중..."):
                audio_path = generate_audio_with_fallback(text, engine, voice)
                
                if audio_path:
                    st.success("✅ 음성 생성 완료!")
                    st.audio(audio_path)
                    
                    # HTML 플레이어 옵션
                    if st.checkbox("HTML 플레이어 사용"):
                        audio_html = create_audio_player(audio_path, loop=True)
                        st.markdown(audio_html, unsafe_allow_html=True)
                else:
                    st.error("음성 생성 실패")
                    
                    # 브라우저 TTS 폴백
                    st.warning("브라우저 내장 TTS를 대신 사용해보세요:")
                    st.markdown(get_browser_tts_script(text), unsafe_allow_html=True)