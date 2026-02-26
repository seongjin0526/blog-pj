# Project: My Blog (Django)

## Tech Stack
- Django 4.2, Python 3.12, SQLite
- Bootstrap 5.3 (CDN), highlight.js (CDN), marked.js (에디터 프리뷰)
- Pillow (이미지 처리), bleach (HTML 새니타이즈)
- django-allauth (Google OAuth)
- DRF 미사용 — API는 순수 Django views + JsonResponse

## Project Structure
```
config/          — Django settings, root urls
blog/            — 메인 앱 (models, views, utils, api, decorators, signals)
templates/       — HTML 템플릿 (base.html, blog/*.html)
static/css/      — 커스텀 CSS (style.css)
media/uploads/   — 업로드된 이미지 원본
media/thumbnails/— 리사이즈된 썸네일 (WebP)
```

## Coding Conventions

### Python
- Function-based views (CBV 미사용)
- snake_case 함수명, kebab-case URL 패턴 (`upload-post/`, `delete-posts/`)
- 한국어 커밋 메시지 (예: "글 관리 기능 추가 및 뒤로가기 400 에러 수정")

### Templates & CSS
- Django 템플릿 + Bootstrap 5 유틸리티 클래스
- JS는 템플릿 내 인라인 (별도 빌드 파이프라인 없음)
- `static/css/style.css`에 커스텀 스타일

### URL Routing
- 한국어 slug 지원을 위해 `re_path`와 `[-\w]+` 패턴 사용 (표준 `<slug:slug>`는 ASCII만 매칭)

## Design Principles

### 성능
- 썸네일 이미지는 서버에서 Pillow로 리사이즈 (240x180px WebP)
- CSS만으로 이미지 축소하는 방식은 트래픽 낭비이므로 지양
- 외부 URL(http/https)은 리사이즈 없이 그대로 사용
- 동일 원본은 MD5 해시 기반으로 중복 생성 방지

### 모바일 대응
- 모든 UI는 모바일에서도 보기 편해야 함
- 네비게이션: 모바일에서 햄버거 메뉴 (navbar-expand-md + collapse)
- 글 목록: 모바일 한 화면에 글 3개 정도가 보이도록 콤팩트하게
- 반응형 패턴: `d-none d-md-block`, `mb-2 mb-md-4`, `my-3 my-md-5`

### 보안
- 모든 시크릿은 `.env`에 관리 (SECRET_KEY, OAuth 자격증명, ADMIN_EMAILS)
- `bleach` allowlist 새니타이저로 마크다운 렌더링 결과 정화
- Staff 전용 뷰는 반드시 `@staff_member_required(login_url='/')` + `@never_cache`
- API 엔드포인트는 `@csrf_exempt` + API Key 인증
- `db.sqlite3`, `media/`, `.env`는 `.gitignore`에 포함

### 데이터 저장
- 글 본문/메타데이터는 DB (Post 모델)
- 이미지 파일은 파일시스템 (media/) — DB에는 경로(URL)만 저장

## Known Gotchas
- highlight.js CDN 로딩 전에 `hljs` 참조하면 에디터 전체가 깨짐 → `typeof hljs === 'undefined'` 가드 필수
- Django `<slug:slug>`는 한국어 slug를 매칭하지 않음 → `re_path` 사용
- `@staff_member_required` 기본 login_url이 `/admin/login/`으로 관리자 로그인 페이지 노출 → `login_url='/'`로 오버라이드
- 페이지네이션에서 per_page 파라미터가 페이지 이동 시 유실되지 않도록 query string에 항상 포함
