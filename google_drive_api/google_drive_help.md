### 🔍 구글 드라이브 API 키를 이용한 파일 백업

Google Drive API를 이용해 파일 백업을 하려면, 우선 **API 키(Key)** 가 아니라 **OAuth 2.0 클라이언트 ID**를 사용해야 합니다. API 키는 공개 데이터에 접근할 때 주로 사용되며, 사용자 데이터를 다루는 백업 작업에는 **사용자 인증**이 필수적이기 때문입니다.

-----

### 🔑 OAuth 2.0 클라이언트 ID 생성 및 사용 절차

1.  **Google Cloud Platform(GCP) 프로젝트 생성**:

      * Google Cloud Platform 콘솔에 접속하여 새 프로젝트를 만듭니다.

2.  **API 활성화**:

      * 생성한 프로젝트에서 **'라이브러리'** 메뉴로 이동합니다.
      * \*\*'Google Drive API'\*\*를 검색하여 활성화합니다.

3.  **OAuth 동의 화면 구성**:

      * **'OAuth 동의 화면'** 메뉴로 이동하여 애플리케이션 이름, 사용자 지원 이메일 등 필수 정보를 입력합니다.
      * 애플리케이션이 접근할 범위를 지정해야 합니다. 백업 작업을 위해서는 **'[https://www.googleapis.com/auth/drive](https://www.google.com/search?q=https://www.googleapis.com/auth/drive)'** 범위를 추가하는 것이 일반적입니다.

4.  **OAuth 2.0 클라이언트 ID 생성**:

      * **'사용자 인증 정보'** 메뉴에서 \*\*'사용자 인증 정보 만들기'\*\*를 클릭하고 \*\*'OAuth 클라이언트 ID'\*\*를 선택합니다.
      * 애플리케이션 유형을 **'데스크톱 앱'** 또는 **'웹 애플리케이션'** 등 용도에 맞게 선택합니다.
      * 생성 후 **클라이언트 ID**와 **클라이언트 보안 비밀(Client Secret)** 을 다운로드하거나 복사해 둡니다. 이 정보가 바로 사용자 인증에 필요한 핵심 키입니다.

-----

### 💻 백업 스크립트 작성 (Python 예시)

Python 라이브러리인 \*\*`google-api-python-client`\*\*와 \*\*`google-auth-oauthlib`\*\*를 사용하면 쉽게 인증 및 백업 스크립트를 작성할 수 있습니다.

**1. 라이브러리 설치:**

```bash
pip install google-api-python-client google-auth-oauthlib
```

**2. 인증 및 백업 스크립트 (예시):**

```python
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
```

**3. 스크립트 실행:**

  * 위 스크립트를 실행하면 **웹 브라우저 창**이 열리고, Google 계정 로그인 및 **접근 권한 요청** 동의 절차를 거칩니다.
  * 인증이 완료되면 `token.json` 파일이 생성되고, 백업 스크립트가 실행됩니다.
  * **클라이언트 ID(Client ID)** 와 **클라이언트 보안 비밀(Client Secret)** 정보가 포함된 `credentials.json` 파일을 스크립트와 같은 디렉토리에 두어야 합니다.

이러한 OAuth 2.0 방식을 사용하면, 사용자가 직접 인증 과정을 거치므로 보안이 강화되며, 안전하게 파일을 백업할 수 있습니다.