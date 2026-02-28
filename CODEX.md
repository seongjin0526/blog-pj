# Project: My Blog (Django) - Codex Guide

## Tech Stack
- Django 4.2, Python 3.12, SQLite (local) / PostgreSQL (Docker)
- Bootstrap 5.3 (CDN), highlight.js (CDN), marked.js
- Pillow, bleach, django-allauth
- API는 DRF 없이 Django views + `JsonResponse`

## Project Structure
```text
config/          Django settings, root urls
blog/            메인 앱 (models, views, utils, api, decorators, signals)
templates/       HTML 템플릿
static/css/      커스텀 CSS
media/uploads/   업로드 원본
media/thumbnails/리사이즈 썸네일(WebP)
.codex/commands/ Codex 작업용 커맨드 문서
CODEX_CHANGELOG.md Codex 작업 내역 로그
```

## Codex Working Rules
- 변경 작업 후 `CODEX_CHANGELOG.md`에 항목을 추가한다.
- 로그에는 날짜, 변경 파일, 사용자 영향, Claude 전환 시 참고사항을 포함한다.
- 보안 관련 변경은 테스트 결과와 점검 결과를 함께 기록한다.
- Python/Django 코딩 스타일은 기존 프로젝트 관례를 우선한다.

## Coding Conventions

### Python
- Function-based views 유지
- snake_case 함수명, kebab-case URL 패턴
- 한국어 커밋 메시지 유지

### Templates & CSS
- Django 템플릿 + Bootstrap 유틸리티 우선
- JS는 템플릿 인라인 스크립트 사용
- 커스텀 스타일은 `static/css/style.css` 중심으로 관리

### URL Routing
- 한국어 slug 대응이 필요하면 `re_path`와 `[-\\w]+` 패턴 사용

## Security Baseline
- 시크릿은 `.env`로만 관리
- 마크다운 렌더링 결과는 `bleach` allowlist로 정화
- Staff 전용 뷰는 `@staff_member_required(login_url='/')` + `@never_cache`
- API 엔드포인트는 인증 데코레이터 적용
- `.env`, `db.sqlite3`, `media/`는 Git 제외
- Docker 컨테이너는 root(UID 0)로 실행하지 않는다 (`USER appuser` 유지)
- Docker 서비스는 `privileged: false`를 유지한다
- Docker 서비스는 `no-new-privileges:true` 및 `cap_drop: [ALL]`를 기본 적용한다

## Known Gotchas
- `hljs` 로딩 전 참조 시 에디터 스크립트 오류 가능
- Django `<slug:slug>`는 한국어 slug 매칭 불가
- 페이지네이션 query string(`per_page`) 누락 주의

## Claude Handoff Notes
- Claude로 재전환 시 `CODEX_CHANGELOG.md`를 먼저 읽고 최근 변경 의도와 영향 범위를 파악한다.
- Claude 전용 로컬 설정/명령은 Git에서 제외되어야 하며, 필요 시 로컬에서만 재생성한다.

## Imported Claude Context (2026-02-28)
- Source: `.claude/2026-02-28-235012-blog.txt`, `.claude/2026-02-28-235027-implement-the-following-plan.txt`
- 태그 탐색 UI는 네비바에서 `상위 태그 1줄 + 더보기 + 검색 + 자동완성` 패턴을 우선한다.
- 태그 검색 구현 시 이후 `제목/본문 검색`으로 확장 가능하도록 검색 로직을 분리한다.
- 다크 모드는 `data-bs-theme` 기반 전환 + 쿠키 유지 + FOUC 방지(초기 head 스크립트) 패턴을 유지한다.
- 가이드/커맨드/스킬은 `.codex/commands`, `.codex/skills`에 유지하고 `.claude` export는 참조 기록으로만 보관한다.
