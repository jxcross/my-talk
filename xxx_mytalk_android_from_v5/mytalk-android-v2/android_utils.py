"""
android_utils.py
안드로이드 플랫폼 전용 유틸리티 함수들
"""

import os
from pathlib import Path
from kivy.utils import platform

def get_storage_path():
    """플랫폼에 맞는 저장소 경로 반환"""
    if platform == 'android':
        try:
            from android.storage import primary_external_storage_path
            return Path(primary_external_storage_path()) / "MyTalk"
        except ImportError:
            # Fallback for testing
            return Path("/sdcard/MyTalk")
    else:
        return Path.home() / "MyTalk"

def request_android_permissions():
    """안드로이드 권한 요청"""
    if platform == 'android':
        try:
            from android.permissions import request_permissions, Permission
            permissions = [
                Permission.WRITE_EXTERNAL_STORAGE,
                Permission.READ_EXTERNAL_STORAGE,
                Permission.INTERNET,
                Permission.RECORD_AUDIO
            ]
            request_permissions(permissions)
            return True
        except ImportError:
            print("Android permissions module not available")
            return False
    return True

def check_network_connection():
    """네트워크 연결 상태 확인"""
    if platform == 'android':
        try:
            from jnius import autoclass
            ConnectivityManager = autoclass('android.net.ConnectivityManager')
            Context = autoclass('android.content.Context')
            PythonActivity = autoclass('org.kivy.android.PythonActivity')
            
            activity = PythonActivity.mActivity
            connectivity_service = activity.getSystemService(Context.CONNECTIVITY_SERVICE)
            network_info = connectivity_service.getActiveNetworkInfo()
            
            return network_info is not None and network_info.isConnected()
        except Exception as e:
            print(f"Network check failed: {e}")
            return True  # Assume connected if check fails
    else:
        # Desktop - assume connected
        return True

def get_device_info():
    """기기 정보 반환"""
    info = {
        'platform': platform,
        'storage_path': str(get_storage_path()),
        'network': check_network_connection()
    }
    
    if platform == 'android':
        try:
            from jnius import autoclass
            Build = autoclass('android.os.Build')
            info.update({
                'device': Build.DEVICE,
                'model': Build.MODEL,
                'version': Build.VERSION.RELEASE,
                'sdk': Build.VERSION.SDK_INT
            })
        except Exception as e:
            print(f"Device info fetch failed: {e}")
    
    return info

def show_toast(message, duration='short'):
    """토스트 메시지 표시 (안드로이드만)"""
    if platform == 'android':
        try:
            from jnius import autoclass
            PythonActivity = autoclass('org.kivy.android.PythonActivity')
            Toast = autoclass('android.widget.Toast')
            
            activity = PythonActivity.mActivity
            
            def show_toast_on_ui_thread():
                toast_duration = Toast.LENGTH_SHORT if duration == 'short' else Toast.LENGTH_LONG
                toast = Toast.makeText(activity, str(message), toast_duration)
                toast.show()
            
            activity.runOnUiThread(show_toast_on_ui_thread)
            
        except Exception as e:
            print(f"Toast failed: {e}")
    else:
        print(f"Toast: {message}")

def share_text(text, title="Share"):
    """텍스트 공유 (안드로이드 Intent)"""
    if platform == 'android':
        try:
            from jnius import autoclass
            PythonActivity = autoclass('org.kivy.android.PythonActivity')
            Intent = autoclass('android.content.Intent')
            
            activity = PythonActivity.mActivity
            
            share_intent = Intent()
            share_intent.setAction(Intent.ACTION_SEND)
            share_intent.putExtra(Intent.EXTRA_TEXT, str(text))
            share_intent.setType("text/plain")
            
            chooser = Intent.createChooser(share_intent, title)
            activity.startActivity(chooser)
            
            return True
        except Exception as e:
            print(f"Share failed: {e}")
            return False
    else:
        print(f"Share text: {text}")
        return False

def open_url(url):
    """URL 열기"""
    if platform == 'android':
        try:
            from jnius import autoclass
            PythonActivity = autoclass('org.kivy.android.PythonActivity')
            Intent = autoclass('android.content.Intent')
            Uri = autoclass('android.net.Uri')
            
            activity = PythonActivity.mActivity
            intent = Intent()
            intent.setAction(Intent.ACTION_VIEW)
            intent.setData(Uri.parse(url))
            activity.startActivity(intent)
            
            return True
        except Exception as e:
            print(f"Open URL failed: {e}")
            return False
    else:
        import webbrowser
        webbrowser.open(url)
        return True

def vibrate(duration=100):
    """진동 (밀리초)"""
    if platform == 'android':
        try:
            from jnius import autoclass
            PythonActivity = autoclass('org.kivy.android.PythonActivity')
            Context = autoclass('android.content.Context')
            
            activity = PythonActivity.mActivity
            vibrator = activity.getSystemService(Context.VIBRATOR_SERVICE)
            
            if vibrator and vibrator.hasVibrator():
                vibrator.vibrate(duration)
                return True
        except Exception as e:
            print(f"Vibrate failed: {e}")
    return False

def keep_screen_on(keep_on=True):
    """화면 켜짐 상태 유지"""
    if platform == 'android':
        try:
            from jnius import autoclass
            PythonActivity = autoclass('org.kivy.android.PythonActivity')
            WindowManager = autoclass('android.view.WindowManager')
            
            activity = PythonActivity.mActivity
            window = activity.getWindow()
            
            if keep_on:
                window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
            else:
                window.clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
                
            return True
        except Exception as e:
            print(f"Keep screen on failed: {e}")
    return False

def get_battery_level():
    """배터리 레벨 반환 (0-100)"""
    if platform == 'android':
        try:
            from jnius import autoclass
            PythonActivity = autoclass('org.kivy.android.PythonActivity')
            Context = autoclass('android.content.Context')
            BatteryManager = autoclass('android.os.BatteryManager')
            
            activity = PythonActivity.mActivity
            battery_manager = activity.getSystemService(Context.BATTERY_SERVICE)
            
            if battery_manager:
                level = battery_manager.getIntProperty(BatteryManager.BATTERY_PROPERTY_CAPACITY)
                return level
        except Exception as e:
            print(f"Battery level check failed: {e}")
    
    return None

def is_charging():
    """충전 중인지 확인"""
    if platform == 'android':
        try:
            from jnius import autoclass
            PythonActivity = autoclass('org.kivy.android.PythonActivity')
            Context = autoclass('android.content.Context')
            BatteryManager = autoclass('android.os.BatteryManager')
            
            activity = PythonActivity.mActivity
            battery_manager = activity.getSystemService(Context.BATTERY_SERVICE)
            
            if battery_manager:
                is_charging_status = battery_manager.isCharging()
                return is_charging_status
        except Exception as e:
            print(f"Charging status check failed: {e}")
    
    return None

def minimize_app():
    """앱 최소화"""
    if platform == 'android':
        try:
            from jnius import autoclass
            PythonActivity = autoclass('org.kivy.android.PythonActivity')
            Intent = autoclass('android.content.Intent')
            
            activity = PythonActivity.mActivity
            intent = Intent(Intent.ACTION_MAIN)
            intent.addCategory(Intent.CATEGORY_HOME)
            intent.setFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            activity.startActivity(intent)
            
            return True
        except Exception as e:
            print(f"Minimize app failed: {e}")
    return False

class AndroidLifecycle:
    """안드로이드 앱 생명주기 관리"""
    
    def __init__(self):
        self.callbacks = {
            'on_pause': [],
            'on_resume': [],
            'on_destroy': []
        }
    
    def register_callback(self, event, callback):
        """생명주기 콜백 등록"""
        if event in self.callbacks:
            self.callbacks[event].append(callback)
    
    def trigger_callbacks(self, event):
        """콜백 실행"""
        if event in self.callbacks:
            for callback in self.callbacks[event]:
                try:
                    callback()
                except Exception as e:
                    print(f"Callback error ({event}): {e}")

# 전역 생명주기 매니저 인스턴스
lifecycle_manager = AndroidLifecycle()

def get_app_version():
    """앱 버전 정보 반환"""
    if platform == 'android':
        try:
            from jnius import autoclass
            PythonActivity = autoclass('org.kivy.android.PythonActivity')
            
            activity = PythonActivity.mActivity
            package_info = activity.getPackageManager().getPackageInfo(
                activity.getPackageName(), 0
            )
            
            return {
                'version_name': package_info.versionName,
                'version_code': package_info.versionCode,
                'package_name': activity.getPackageName()
            }
        except Exception as e:
            print(f"Version info failed: {e}")
    
    return {
        'version_name': '1.0',
        'version_code': 1,
        'package_name': 'com.mytalk.app'
    }

def setup_android_logging():
    """안드로이드 로깅 설정"""
    if platform == 'android':
        try:
            import logging
            from kivy.logger import Logger
            
            # 로그 레벨 설정
            Logger.setLevel(logging.DEBUG)
            
            # 안드로이드 로그캣으로 출력되도록 설정
            logging.basicConfig(
                level=logging.DEBUG,
                format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            
            return True
        except Exception as e:
            print(f"Logging setup failed: {e}")
    return False

# 앱 시작 시 기본 설정
def initialize_android_app():
    """안드로이드 앱 초기화"""
    print("Initializing Android app...")
    
    # 권한 요청
    request_android_permissions()
    
    # 로깅 설정
    setup_android_logging()
    
    # 디바이스 정보 출력
    device_info = get_device_info()
    print(f"Device info: {device_info}")
    
    # 네트워크 연결 확인
    if not check_network_connection():
        show_toast("네트워크 연결을 확인해주세요", "long")
    
    print("Android app initialization complete!")

if __name__ == '__main__':
    # 테스트 코드
    initialize_android_app()
    
    if platform == 'android':
        show_toast("MyTalk 앱이 시작되었습니다!")
        vibrate(200)