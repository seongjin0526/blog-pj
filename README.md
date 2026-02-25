# blog-pj

Django 기반 마크다운 블로그 프로젝트입니다.

## 실행 방법

### 1. 의존성 설치

```bash
pip install -r requirements.txt
```

### 2. 환경변수 설정

프로젝트 루트에 `.env` 파일을 생성합니다.

```env
SECRET_KEY=your-secret-key-here
DEBUG=True
ALLOWED_HOSTS=

GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret
OWNER_EMAIL=your-email@gmail.com
```

- `SECRET_KEY` — 미설정 시 서버가 시작되지 않습니다
- `OWNER_EMAIL` — 이 이메일로 Google 로그인 시 자동으로 관리자 권한이 부여됩니다

### 3. DB 마이그레이션

```bash
python manage.py migrate
```

### 4. Site 도메인 설정

Django shell에서 Site 도메인을 로컬 개발 환경에 맞게 변경합니다.

```bash
python manage.py shell -c "
from django.contrib.sites.models import Site
s = Site.objects.get(id=1)
s.domain = '127.0.0.1:8000'
s.name = 'localhost'
s.save()
"
```

### 5. 서버 실행

```bash
python manage.py runserver
```

`http://127.0.0.1:8000/` 에서 접속할 수 있습니다.

### 6. 테스트 실행

```bash
python manage.py test blog
```

## Google OAuth 설정

### Google Cloud Console

1. [Google Cloud Console](https://console.cloud.google.com/) 접속
2. 프로젝트 생성 (또는 기존 프로젝트 선택)
3. **API 및 서비스 > 사용자 인증 정보** 이동
4. **사용자 인증 정보 만들기 > OAuth 클라이언트 ID** 클릭
5. 애플리케이션 유형: **웹 애플리케이션**
6. **승인된 리디렉션 URI**에 추가:
   ```
   http://127.0.0.1:8000/accounts/google/login/callback/
   ```
7. 생성된 **클라이언트 ID**와 **클라이언트 보안 비밀번호**를 `.env`에 입력

> OAuth 동의 화면 설정을 먼저 요구할 수 있습니다. 테스트 단계에서는 "외부" 선택 후 앱 이름만 입력하면 됩니다.

### 확인

- 네비바의 **Google 로그인** 클릭 → Google 계정 선택 → 로그인 완료
- `OWNER_EMAIL`과 일치하는 계정으로 로그인하면 자동으로 관리자(staff) 권한이 부여됩니다

## API

API 키 기반 인증으로 외부에서 블로그 데이터를 조회하거나 댓글/게시글을 관리할 수 있습니다.

### 인증

모든 API 요청에 `Authorization` 헤더를 포함합니다.

```
Authorization: Key YOUR_API_KEY
```

API 키는 로그인 후 **API 키** 메뉴에서 발급할 수 있으며, 발급 시 한 번만 표시됩니다.

### 권한 체계

| Scope | 조회 | 댓글 | 업로드 |
|-------|------|------|--------|
| Read  | O    | X    | X      |
| Write | O    | O    | X      |
| Admin | O    | O    | O      |

- Admin 키는 staff 계정만 발급 가능합니다
- 상위 권한은 하위 권한의 모든 기능을 포함합니다

### 엔드포인트

| 메서드 | 경로 | 권한 | 설명 |
|--------|------|------|------|
| GET    | `/api/posts/` | read | 글 목록 조회 (`tag`, `page`, `per_page` 파라미터) |
| GET    | `/api/posts/{slug}/` | read | 글 상세 조회 |
| POST   | `/api/posts/{slug}/comments/` | write | 댓글 작성 (JSON: `{"content": "..."}`) |
| DELETE | `/api/comments/{id}/` | write | 본인 댓글 삭제 |
| POST   | `/api/upload-post/` | admin | MD/ZIP 파일 업로드로 게시글 생성 |

### 사용 예시

```bash
# 글 목록 조회
curl -H "Authorization: Key YOUR_API_KEY" http://127.0.0.1:8000/api/posts/

# 댓글 작성
curl -X POST \
  -H "Authorization: Key YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"content":"좋은 글이네요!"}' \
  http://127.0.0.1:8000/api/posts/my-post/comments/

# 게시글 업로드 (admin 키 필요)
curl -X POST \
  -H "Authorization: Key YOUR_ADMIN_KEY" \
  -F "file=@my-post.md" \
  http://127.0.0.1:8000/api/upload-post/
```

웹에서도 `/api-guide/` 페이지에서 상세 가이드를 확인할 수 있습니다.
