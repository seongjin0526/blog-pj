# blog-pj

Django 기반 마크다운 블로그 프로젝트입니다. Docker Compose로 실행합니다.

## Codex 운영 문서

- 프로젝트 작업 가이드: `CODEX.md`
- Codex 변경 이력: `CODEX_CHANGELOG.md`
- 작업 명령 템플릿: `.codex/commands/`

## 시작하기

### 1. 환경변수 설정

`.env.sample`을 복사하여 `.env`를 만들고 값을 채웁니다.

```bash
cp .env.sample .env
```

| 변수 | 설명 | 예시 |
|------|------|------|
| `SECRET_KEY` | Django 시크릿 키 (필수) | 랜덤 문자열 |
| `DEBUG` | 디버그 모드 | `True` / `False` |
| `ALLOWED_HOSTS` | 허용 호스트 (쉼표 구분) | `localhost` |
| `ADMIN_EMAILS` | 관리자 이메일 (쉼표 구분) | `you@gmail.com` |
| `GOOGLE_CLIENT_ID` | Google OAuth 클라이언트 ID | |
| `GOOGLE_CLIENT_SECRET` | Google OAuth 시크릿 | |
| `DB_ENGINE` | DB 엔진 | `django.db.backends.postgresql` |
| `DB_NAME` | DB 이름 | `blog` |
| `DB_USER` | DB 사용자 | `blog_user` |
| `DB_PASSWORD` | DB 비밀번호 | 강력한 비밀번호 |
| `DB_HOST` | DB 호스트 | `db` |
| `DB_PORT` | DB 포트 | `5432` |

### 2. 실행

```bash
docker compose up --build
```

- PostgreSQL(db) healthcheck 통과 후 Django(web) 자동 시작
- 마이그레이션은 web 컨테이너 시작 시 자동 실행
- 소스코드 바인드 마운트 + `runserver` — 코드 수정 시 자동 리로드 (재빌드 불필요)
- `http://127.0.0.1:8000/` 에서 접속

### 3. Site 도메인 설정

최초 실행 시 Django Site 도메인을 설정합니다.

```bash
docker compose exec web python manage.py shell -c "
from django.contrib.sites.models import Site
s = Site.objects.get(id=1)
s.domain = 'localhost:8000'
s.name = 'localhost'
s.save()
"
```

### 4. 테스트

```bash
docker compose run --rm test
```

### 5. 종료

```bash
docker compose down
```

데이터는 Docker 볼륨(`postgres_data`)과 로컬 `media/` 디렉토리에 보존됩니다.

## 프로덕션 배포

### 환경변수

`.env`에서 다음 항목을 프로덕션 값으로 변경합니다.

```env
DEBUG=False
ALLOWED_HOSTS=your-domain.com
CSRF_TRUSTED_ORIGINS=https://your-domain.com
SECRET_KEY=<충분히 긴 랜덤 문자열>
DB_PASSWORD=<강력한 비밀번호>
```

| 항목 | 설명 |
|------|------|
| `DEBUG=False` | 디버그 비활성화. 자동으로 HTTPS 리다이렉트, HSTS, Secure Cookie 등 보안 설정 활성화 |
| `ALLOWED_HOSTS` | 실제 도메인 설정. 미설정 시 모든 요청 거부 |
| `CSRF_TRUSTED_ORIGINS` | HTTPS 도메인 (예: `https://your-domain.com`). 미설정 시 POST 요청 403 |
| `SECRET_KEY` | `python -c "import secrets; print(secrets.token_urlsafe(50))"` 으로 생성 |
| `DB_PASSWORD` | 강력한 비밀번호로 변경 |

### 실행 방식

개발 환경과 달리 프로덕션에서는 gunicorn으로 서빙합니다. `docker-compose.yml`의 web 서비스 command를 변경합니다.

```yaml
command: >
  sh -c "python manage.py migrate --noinput &&
         gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 3"
```

소스코드 바인드 마운트(`.:/app`)도 제거하고, 이미지에 포함된 코드를 사용합니다.

### Static 파일

WhiteNoise가 gunicorn에서 직접 static 파일을 서빙합니다. 별도 nginx 설정 없이 동작합니다.

### Site 도메인

프로덕션 도메인으로 변경합니다.

```bash
docker compose exec web python manage.py shell -c "
from django.contrib.sites.models import Site
s = Site.objects.get(id=1)
s.domain = 'your-domain.com'
s.name = 'your-domain.com'
s.save()
"
```

### Google OAuth 리디렉션 URI

Google Cloud Console에서 프로덕션 도메인의 콜백 URI를 추가합니다.

```
https://your-domain.com/accounts/google/login/callback/
```

## Google OAuth 설정

1. [Google Cloud Console](https://console.cloud.google.com/) 접속
2. 프로젝트 생성 (또는 기존 프로젝트 선택)
3. **API 및 서비스 > 사용자 인증 정보** 이동
4. **사용자 인증 정보 만들기 > OAuth 클라이언트 ID** 클릭
5. 애플리케이션 유형: **웹 애플리케이션**
6. **승인된 리디렉션 URI**에 추가:
   ```
   http://localhost:8000/accounts/google/login/callback/
   ```
7. 생성된 **클라이언트 ID**와 **클라이언트 보안 비밀번호**를 `.env`에 입력

> OAuth 동의 화면 설정을 먼저 요구할 수 있습니다. 테스트 단계에서는 "외부" 선택 후 앱 이름만 입력하면 됩니다.

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
curl -H "Authorization: Key YOUR_API_KEY" http://localhost:8000/api/posts/

# 댓글 작성
curl -X POST \
  -H "Authorization: Key YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"content":"좋은 글이네요!"}' \
  http://localhost:8000/api/posts/my-post/comments/

# 게시글 업로드 (admin 키 필요)
curl -X POST \
  -H "Authorization: Key YOUR_ADMIN_KEY" \
  -F "file=@my-post.md" \
  http://localhost:8000/api/upload-post/
```

웹에서도 `/api-guide/` 페이지에서 상세 가이드를 확인할 수 있습니다.
