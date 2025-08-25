"""
Enhanced TTS Module - 안정성과 호환성 향상
다양한 TTS 엔진 지원 및 폴백 시스템 구축
"""

import os
import tempfile
import streamlit as st
from typing import Optional, Dict, List
import base64
import asyncio
import threading
import time

class EnhancedTTSManager:
    """향상된 TTS 관리자"""
    
    def __init__(self):
        self.available_engines = self.detect_available_engines()
        self.engine_priorities = ['gTTS', 'pyttsx3', 'edge-tts']  # 우선순위
        self.cache = {}  # 간단한 메모리 캐시
        
    def detect_available_engines(self) -> List[str]:
        """사용 가능한 TTS 엔진 탐지"""
        engines = []
        
        # gTTS 확인 (가장 안정적)
        try:
            import gtts
            engines.append('gTTS')
        except ImportError:
            pass
        
        # pyttsx3 확인 (오프라인)
        try:
            import pyttsx3
            # 빠른 초기화 테스트
            try:
                engine = pyttsx3.init(debug=False)
                if engine:
                    engine.stop()
                    engines.append('pyttsx3')
            except:
                pass
        except ImportError:
            pass
        
        # edge-tts 확인 (고품질이지만 불안정할 수 있음)
        try:
            import edge_tts
            engines.append('edge-tts')
        except ImportError:
            pass
        
        return engines
    
    def get_cache_key(self, text: str, voice: str, engine: str) -> str:
        """캐시 키 생성"""
        import hashlib
        content = f"{text}_{voice}_{engine}"
        return hashlib.md5(content.encode()).hexdigest()[:12]
    
    def generate_with_gtts(self, text: str, lang: str = 'en', slow: bool = False) -> Optional[str]:
        """gTTS를 사용한 음성 생성 (권장)"""
        try:
            from gtts import gTTS
            
            # 언어 매핑
            lang_map = {
                'en': 'en',
                'en-us': 'en', 
                'en-uk': 'en',
                'en-au': 'com.au',
                'ko': 'ko',
                'ko-kr': 'ko'
            }
            
            tts_lang = lang_map.get(lang.lower(), 'en')
            
            # 임시 파일 생성
            with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as tmp_file:
                output_path = tmp_file.name
            
            # TTS 생성 (재시도 로직 포함)
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    tts = gTTS(text=text, lang=tts_lang, slow=slow)
                    tts.save(output_path)
                    
                    # 파일 생성 확인
                    if os.path.exists(output_path) and os.path.getsize(output_path) > 100:
                        return output_path
                    else:
                        if os.path.exists(output_path):
                            os.unlink(output_path)
                        continue
                        
                except Exception as e:
                    if attempt < max_retries - 1:
                        time.sleep(1)  # 잠시 대기 후 재시도
                        continue
                    else:
                        raise e
            
            return None
            
        except Exception as e:
            return None
    
    def generate_with_pyttsx3(self, text: str, voice_id: Optional[str] = None, rate: int = 150) -> Optional[str]:
        """pyttsx3를 사용한 오프라인 음성 생성"""
        try:
            import pyttsx3
            
            # 임시 파일 생성
            with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as tmp_file:
                output_path = tmp_file.name
            
            # 엔진 초기화 (타임아웃 적용)
            def init_and_generate():
                try:
                    engine = pyttsx3.init(debug=False)
                    
                    # 음성 설정
                    voices = engine.getProperty('voices')
                    if voices and voice_id:
                        for voice in voices:
                            if 'english' in voice.name.lower() or 'en' in voice.id.lower():
                                engine.setProperty('voice', voice.id)
                                break
                    
                    # 속도 설정
                    engine.setProperty('rate', rate)
                    
                    # 볼륨 설정
                    engine.setProperty('volume', 0.9)
                    
                    # 파일로 저장
                    engine.save_to_file(text, output_path)
                    engine.runAndWait()
                    engine.stop()
                    
                    return True
                except:
                    return False
            
            # 스레드로 실행 (타임아웃 방지)
            result = []
            thread = threading.Thread(target=lambda: result.append(init_and_generate()))
            thread.daemon = True
            thread.start()
            thread.join(timeout=30)  # 30초 타임아웃
            
            if result and result[0] and os.path.exists(output_path):
                # WAV를 MP3로 변환 (가능한 경우)
                mp3_path = output_path.replace('.wav', '.mp3')
                try:
                    # ffmpeg가 있다면 변환 시도
                    import subprocess
                    subprocess.run(['ffmpeg', '-i', output_path, '-y', mp3_path], 
                                 check=True, capture_output=True)
                    os.unlink(output_path)
                    return mp3_path
                except:
                    # 변환 실패시 WAV 파일 그대로 반환
                    return output_path
            
            return None
            
        except Exception as e:
            return None
    
    def generate_with_edge_tts_sync(self, text: str, voice: str = 'en-US-AriaNeural') -> Optional[str]:
        """edge-tts를 동기적으로 안전하게 실행"""
        try:
            import edge_tts
            
            # 임시 파일 생성
            with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as tmp_file:
                output_path = tmp_file.name
            
            async def async_generate():
                try:
                    communicate = edge_tts.Communicate(text, voice)
                    await communicate.save(output_path)
                    return True
                except Exception:
                    return False
            
            # 새 이벤트 루프에서 실행
            def run_in_thread():
                try:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    success = loop.run_until_complete(
                        asyncio.wait_for(async_generate(), timeout=30.0)
                    )
                    loop.close()
                    return success
                except Exception:
                    return False
            
            # 스레드로 실행
            result = []
            thread = threading.Thread(target=lambda: result.append(run_in_thread()))
            thread.daemon = True
            thread.start()
            thread.join(timeout=35)  # 추가 여유시간
            
            if result and result[0] and os.path.exists(output_path) and os.path.getsize(output_path) > 100:
                return output_path
            
            # 실패시 정리
            if os.path.exists(output_path):
                try:
                    os.unlink(output_path)
                except:
                    pass
            
            return None
            
        except Exception:
            return None
    
    def generate_tts_auto(self, text: str, voice: str = 'en', engine: str = 'auto') -> Optional[str]:
        """자동 엔진 선택 및 폴백"""
        if not text or not text.strip():
            return None
        
        # 캐시 확인
        cache_key = self.get_cache_key(text, voice, engine)
        if cache_key in self.cache:
            cached_path = self.cache[cache_key]
            if os.path.exists(cached_path):
                return cached_path
            else:
                del self.cache[cache_key]
        
        audio_path = None
        
        if engine == 'auto':
            # 우선순위에 따라 엔진 시도
            for preferred_engine in self.engine_priorities:
                if preferred_engine in self.available_engines:
                    audio_path = self._try_engine(preferred_engine, text, voice)
                    if audio_path:
                        break
        else:
            # 특정 엔진 사용
            if engine in self.available_engines:
                audio_path = self._try_engine(engine, text, voice)
        
        # 캐시에 저장
        if audio_path:
            self.cache[cache_key] = audio_path
        
        return audio_path
    
    def _try_engine(self, engine: str, text: str, voice: str) -> Optional[str]:
        """특정 엔진으로 생성 시도"""
        try:
            if engine == 'gTTS':
                return self.generate_with_gtts(text, voice)
            elif engine == 'pyttsx3':
                return self.generate_with_pyttsx3(text, voice)
            elif engine == 'edge-tts':
                # edge-tts 음성 매핑
                edge_voices = {
                    'en': 'en-US-AriaNeural',
                    'en-us': 'en-US-AriaNeural',
                    'en-uk': 'en-GB-SoniaNeural', 
                    'en-au': 'en-AU-NatashaNeural',
                    'ko': 'ko-KR-SunHiNeural'
                }
                edge_voice = edge_voices.get(voice.lower(), 'en-US-AriaNeural')
                return self.generate_with_edge_tts_sync(text, edge_voice)
        except Exception:
            pass
        
        return None
    
    def get_voice_options(self, engine: str) -> Dict[str, str]:
        """엔진별 사용 가능한 음성 옵션"""
        if engine in ['auto', 'gTTS']:
            return {
                '영어 (미국)': 'en',
                '영어 (영국)': 'en-uk',
                '영어 (호주)': 'en-au',
                '한국어': 'ko'
            }
        elif engine == 'edge-tts':
            return {
                '영어 여성 (Aria)': 'en-US-AriaNeural',
                '영어 여성 (Jenny)': 'en-US-JennyNeural',
                '영어 남성 (Guy)': 'en-US-GuyNeural',
                '영국 여성 (Sonia)': 'en-GB-SoniaNeural',
                '영국 남성 (Ryan)': 'en-GB-RyanNeural',
                '호주 여성 (Natasha)': 'en-AU-NatashaNeural',
                '한국어 여성 (SunHi)': 'ko-KR-SunHiNeural',
                '한국어 남성 (InJoon)': 'ko-KR-InJoonNeural'
            }
        elif engine == 'pyttsx3':
            return {'시스템 기본 음성': None}
        
        return {}
    
    def clear_cache(self):
        """캐시 정리"""
        for cache_path in self.cache.values():
            try:
                if os.path.exists(cache_path):
                    os.unlink(cache_path)
            except:
                pass
        self.cache.clear()

# 전역 TTS 매니저 인스턴스
_tts_manager = None

def get_tts_manager():
    """TTS 매니저 싱글톤 인스턴스 반환"""
    global _tts_manager
    if _tts_manager is None:
        _tts_manager = EnhancedTTSManager()
    return _tts_manager

# 기존 인터페이스와 호환성을 위한 래퍼 클래스
class TTSManager:
    def __init__(self):
        self.manager = get_tts_manager()
        self.available_engines = self.manager.available_engines

# Streamlit 인터페이스 함수들
def generate_audio_with_fallback(text: str, engine: str = 'auto', voice: str = 'en') -> Optional[str]:
    """폴백 기능이 있는 안전한 TTS 생성"""
    if not text:
        return None
    
    manager = get_tts_manager()
    
    # 텍스트 전처리
    text = text.strip()
    if len(text) > 5000:  # 너무 긴 텍스트는 잘라내기
        text = text[:5000] + "..."
    
    return manager.generate_tts_auto(text, voice, engine)

def create_audio_player(audio_path: str, autoplay: bool = False, loop: bool = False, controls: bool = True) -> str:
    """향상된 오디오 플레이어 HTML 생성"""
    if not audio_path or not os.path.exists(audio_path):
        return ""
    
    try:
        with open(audio_path, 'rb') as f:
            audio_bytes = f.read()
        
        audio_b64 = base64.b64encode(audio_bytes).decode()
        
        # 파일 형식 감지
        file_ext = os.path.splitext(audio_path)[1].lower()
        if file_ext == '.wav':
            mime_type = 'audio/wav'
        else:
            mime_type = 'audio/mp3'
        
        attributes = []
        if controls:
            attributes.append('controls')
        if autoplay:
            attributes.append('autoplay')
        if loop:
            attributes.append('loop')
        
        attrs_str = ' '.join(attributes)
        
        audio_html = f"""
        <audio {attrs_str} style="width: 100%; margin: 10px 0;">
            <source src="data:{mime_type};base64,{audio_b64}" type="{mime_type}">
            <p>브라우저가 오디오 재생을 지원하지 않습니다.</p>
        </audio>
        """
        
        return audio_html
        
    except Exception as e:
        return f"<p>오디오 로드 실패: {str(e)}</p>"

def get_browser_tts_script(text: str, lang: str = 'en-US', rate: float = 1.0, pitch: float = 1.0) -> str:
    """향상된 브라우저 Web Speech API 스크립트"""
    
    # 텍스트 정리 및 이스케이프
    clean_text = text.replace("'", "\\'").replace('"', '\\"').replace('\n', '\\n').replace('\r', '')
    
    # 언어 매핑
    lang_map = {
        'en': 'en-US',
        'en-us': 'en-US',
        'en-uk': 'en-GB', 
        'en-au': 'en-AU',
        'ko': 'ko-KR',
        'ko-kr': 'ko-KR'
    }
    
    speech_lang = lang_map.get(lang.lower(), lang)
    
    return f"""
    <div style="margin: 10px 0; padding: 10px; background-color: #f8f9fa; border-radius: 8px;">
        <script>
        function speakText_{hash(clean_text)[:8]}() {{
            if ('speechSynthesis' in window) {{
                // 이전 음성 중지
                window.speechSynthesis.cancel();
                
                const utterance = new SpeechSynthesisUtterance('{clean_text}');
                utterance.lang = '{speech_lang}';
                utterance.rate = {rate};
                utterance.pitch = {pitch};
                utterance.volume = 0.8;
                
                // 음성 로딩 대기
                function setVoiceAndSpeak() {{
                    const voices = window.speechSynthesis.getVoices();
                    
                    // 선호하는 음성 찾기
                    let preferredVoice = null;
                    for (let voice of voices) {{
                        if (voice.lang === '{speech_lang}') {{
                            preferredVoice = voice;
                            break;
                        }}
                        if (voice.lang.startsWith('{speech_lang.split("-")[0]}')) {{
                            preferredVoice = voice;
                        }}
                    }}
                    
                    if (preferredVoice) {{
                        utterance.voice = preferredVoice;
                    }}
                    
                    // 오류 처리
                    utterance.onerror = function(event) {{
                        console.error('Speech error:', event.error);
                        alert('음성 재생 중 오류가 발생했습니다: ' + event.error);
                    }};
                    
                    utterance.onstart = function() {{
                        document.getElementById('speak_btn_{hash(clean_text)[:8]}').textContent = '🔊 재생 중...';
                        document.getElementById('speak_btn_{hash(clean_text)[:8]}').disabled = true;
                    }};
                    
                    utterance.onend = function() {{
                        document.getElementById('speak_btn_{hash(clean_text)[:8]}').textContent = '🔊 브라우저 TTS 재생';
                        document.getElementById('speak_btn_{hash(clean_text)[:8]}').disabled = false;
                    }};
                    
                    window.speechSynthesis.speak(utterance);
                }}
                
                // 음성이 로드될 때까지 대기
                if (window.speechSynthesis.getVoices().length === 0) {{
                    window.speechSynthesis.onvoiceschanged = setVoiceAndSpeak;
                }} else {{
                    setVoiceAndSpeak();
                }}
                
            }} else {{
                alert('죄송합니다. 브라우저가 음성 합성을 지원하지 않습니다.');
            }}
        }}
        
        function stopSpeech_{hash(clean_text)[:8]}() {{
            if ('speechSynthesis' in window) {{
                window.speechSynthesis.cancel();
                document.getElementById('speak_btn_{hash(clean_text)[:8]}').textContent = '🔊 브라우저 TTS 재생';
                document.getElementById('speak_btn_{hash(clean_text)[:8]}').disabled = false;
            }}
        }}
        </script>
        
        <div style="display: flex; gap: 10px; align-items: center;">
            <button 
                id="speak_btn_{hash(clean_text)[:8]}" 
                onclick="speakText_{hash(clean_text)[:8]}()" 
                style="
                    background: linear-gradient(45deg, #FF6B6B, #4ECDC4);
                    color: white;
                    border: none;
                    padding: 10px 15px;
                    border-radius: 20px;
                    cursor: pointer;
                    font-size: 14px;
                    transition: all 0.3s ease;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.2);
                " 
                onmouseover="this.style.transform='scale(1.05)'"
                onmouseout="this.style.transform='scale(1)'"
            >
                🔊 브라우저 TTS 재생
            </button>
            
            <button 
                onclick="stopSpeech_{hash(clean_text)[:8]}()" 
                style="
                    background-color: #dc3545;
                    color: white;
                    border: none;
                    padding: 8px 12px;
                    border-radius: 15px;
                    cursor: pointer;
                    font-size: 12px;
                    transition: all 0.3s ease;
                "
                onmouseover="this.style.backgroundColor='#c82333'"
                onmouseout="this.style.backgroundColor='#dc3545'"
            >
                ⏹️ 중지
            </button>
            
            <span style="font-size: 12px; color: #666;">
                브라우저 내장 TTS | 언어: {speech_lang}
            </span>
        </div>
        
        <div style="margin-top: 8px; font-size: 11px; color: #888;">
            💡 팁: 크롬, 사파리, 엣지에서 최적화되어 있습니다.
        </div>
    </div>
    """

def hash(text: str) -> str:
    """간단한 해시 함수"""
    import hashlib
    return hashlib.md5(text.encode()).hexdigest()

# 설정 UI 함수
def get_tts_settings_ui():
    """TTS 설정 UI 컴포넌트"""
    manager = get_tts_manager()
    
    if not manager.available_engines:
        st.error("❌ 사용 가능한 TTS 엔진이 없습니다.")
        st.markdown("""
        **설치 권장사항:**
        ```bash
        pip install gtts pyttsx3 edge-tts
        ```
        
        - **gTTS**: Google TTS (온라인, 고품질, 권장)
        - **pyttsx3**: 오프라인 TTS (인터넷 불필요)  
        - **edge-tts**: Microsoft Edge TTS (고품질)
        """)
        return None, None
    
    st.success(f"✅ 사용 가능한 엔진: {', '.join(manager.available_engines)}")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # 엔진 선택
        engine_options = ['auto (자동 선택)'] + manager.available_engines
        selected_engine = st.selectbox(
            "TTS 엔진 선택",
            engine_options,
            help="auto 선택시 가장 안정적인 엔진을 자동으로 선택합니다"
        )
        
        engine = 'auto' if selected_engine == 'auto (자동 선택)' else selected_engine
    
    with col2:
        # 음성 선택
        voice_options = manager.get_voice_options(engine)
        
        if voice_options:
            selected_voice_name = st.selectbox(
                "음성 선택", 
                list(voice_options.keys()),
                help="원하는 음성을 선택하세요"
            )
            voice = voice_options[selected_voice_name]
        else:
            voice = 'en'
            st.info("기본 음성을 사용합니다")
    
    # 테스트 버튼
    if st.button("🎵 음성 테스트", help="TTS 설정을 테스트해보세요"):
        test_text = "Hello! This is a test of the text to speech system. How does it sound?"
        
        with st.spinner("음성 생성 중..."):
            audio_path = generate_audio_with_fallback(test_text, engine, voice)
            
            if audio_path:
                st.success("✅ TTS 테스트 성공!")
                
                # 두 가지 방식으로 재생 옵션 제공
                col_a, col_b = st.columns(2)
                
                with col_a:
                    st.markdown("**Streamlit 오디오 플레이어:**")
                    st.audio(audio_path, format='audio/mp3')
                
                with col_b:
                    st.markdown("**HTML 오디오 플레이어:**")
                    html_player = create_audio_player(audio_path, controls=True, loop=False)
                    st.markdown(html_player, unsafe_allow_html=True)
                
            else:
                st.error("❌ TTS 생성 실패")
                st.warning("브라우저 내장 TTS를 대신 사용해보세요:")
                browser_tts = get_browser_tts_script(test_text, voice if isinstance(voice, str) else 'en-US')
                st.markdown(browser_tts, unsafe_allow_html=True)
    
    return engine, voice

# 정리 함수
def cleanup_temp_files():
    """임시 파일 정리"""
    manager = get_tts_manager()
    manager.clear_cache()

# 앱 종료시 정리
import atexit
atexit.register(cleanup_temp_files)

# 사용 예제 및 테스트
if __name__ == "__main__":
    st.title("🔊 Enhanced TTS Module Test")
    
    # 설정 UI
    st.header("설정")
    engine, voice = get_tts_settings_ui()
    
    st.header("테스트")
    
    # 텍스트 입력
    test_text = st.text_area(
        "테스트할 텍스트를 입력하세요:",
        value="Hello! Welcome to MyTalk, your personal English speaking assistant. Let's practice English together!",
        height=100
    )
    
    if st.button("🎯 고급 테스트 실행") and test_text:
        manager = get_tts_manager()
        
        st.subheader("엔진별 테스트 결과")
        
        for test_engine in manager.available_engines:
            st.markdown(f"**{test_engine} 엔진:**")
            
            with st.spinner(f"{test_engine} 생성 중..."):
                start_time = time.time()
                audio_path = generate_audio_with_fallback(test_text, test_engine, voice)
                generation_time = time.time() - start_time
                
                if audio_path:
                    file_size = os.path.getsize(audio_path) / 1024  # KB
                    st.success(f"✅ 성공 (소요시간: {generation_time:.2f}초, 파일크기: {file_size:.1f}KB)")
                    st.audio(audio_path)
                else:
                    st.error(f"❌ 실패 (소요시간: {generation_time:.2f}초)")
            
            st.markdown("---")
        
        # 브라우저 TTS 테스트
        st.markdown("**브라우저 TTS:**")
        browser_tts = get_browser_tts_script(test_text, voice if isinstance(voice, str) else 'en-US')
        st.markdown(browser_tts, unsafe_allow_html=True)
    
    # 캐시 정보
    with st.expander("🗂️ 캐시 정보"):
        manager = get_tts_manager()
        st.write(f"캐시된 파일 수: {len(manager.cache)}")
        
        if st.button("🗑️ 캐시 정리"):
            manager.clear_cache()
            st.success("캐시가 정리되었습니다!")
            st.rerun()