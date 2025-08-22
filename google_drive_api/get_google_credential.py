import os
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# OAuth 2.0 클라이언트 ID가 저장된 파일 경로 (다운로드 받은 JSON 파일)
CLIENT_SECRET_FILE = 'credentials.json'

# 백업할 파일 경로
BACKUP_FILE = 'example.txt'

# 인증 범위
SCOPES = ['https://www.googleapis.com/auth/drive.file']

def get_drive_service():
    creds = None
    # 이전에 인증 정보가 저장되어 있다면 불러옵니다.
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    
    # 인증 정보가 없거나 유효하지 않다면 새로 인증합니다.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                CLIENT_SECRET_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        # 새로운 인증 정보를 저장합니다.
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
            
    return build('drive', 'v3', credentials=creds)

def upload_file(service, filepath):
    # 파일 메타데이터 설정
    file_metadata = {'name': os.path.basename(filepath)}
    
    # 미디어 업로드 객체 생성
    media = MediaFileUpload(filepath, mimetype='text/plain')
    
    # 파일 업로드
    file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
    print(f'File ID: {file.get("id")} uploaded successfully!')

if __name__ == '__main__':
    service = get_drive_service()
    upload_file(service, BACKUP_FILE)