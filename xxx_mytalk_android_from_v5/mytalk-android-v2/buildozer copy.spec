[app]
title = MyTalk
package.name = mytalk
package.domain = com.mytalk.app
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,json,txt,mp3
source.exclude_dirs = tests,bin,venv,.git,__pycache__,build,.buildozer
version = 1.0

# Python 3.10 optimized requirements
requirements = python3,kivy==2.1.0,kivymd,openai,requests,certifi,urllib3,charset-normalizer,idna,Cython

orientation = portrait
fullscreen = 0

android.permissions = INTERNET,WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE,RECORD_AUDIO,ACCESS_NETWORK_STATE,WAKE_LOCK,VIBRATE
android.archs = arm64-v8a, armeabi-v7a
android.api = 34
android.minapi = 21
android.ndk = 26b
android.sdk = 34
android.allow_backup = True

[buildozer]
log_level = 2
warn_on_root = 1

# Python-for-Android settings
p4a.fork = kivy
p4a.branch = develop
p4a.bootstrap = sdl2
