[app]
title = MyTalk
package.name = mytalk
package.domain = com.mytalk.app
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,json,txt,mp3
source.exclude_dirs = tests,bin,venv,.git,__pycache__,build,.buildozer
version = 1.0

# Simplified requirements to avoid compilation issues
requirements = python3,kivy,kivymd,openai,requests,certifi,urllib3,charset-normalizer,idna

orientation = portrait
fullscreen = 0

# Essential permissions only
android.permissions = INTERNET,WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE,RECORD_AUDIO

# Single architecture for easier build (choose one)
android.archs = arm64-v8a

# API levels
android.api = 33
android.minapi = 21
android.ndk = 25b
android.sdk = 33

android.allow_backup = True

[buildozer]
log_level = 2
warn_on_root = 1

# P4A settings optimized for macOS
p4a.fork = kivy
p4a.branch = master
p4a.bootstrap = sdl2

# Skip problematic recipes
p4a.local_recipes = 
