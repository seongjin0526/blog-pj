---
allowed-tools: Bash(python manage.py test:*), Bash(bandit:*), Bash(pip install bandit:*)
description: 보안 점검 — 테스트 실행 + SAST(Bandit) + 수동 보안 리뷰
---

## 보안 점검 수행

아래 단계를 순서대로 수행하세요.

### 1단계: 테스트 실행
```
python manage.py test blog
```
테스트가 실패하면 중단하고 결과를 보고하세요.

### 2단계: SAST (Bandit)
bandit이 설치되어 있지 않으면 `pip install bandit`으로 설치하세요.
```
bandit -r blog/ -x blog/tests.py,blog/migrations/ -ll
```

### 3단계: 수동 보안 체크
다음 항목을 코드에서 확인하세요:
- `|safe` 템플릿 필터 사용 여부 (XSS 위험)
- `{% csrf_token %}` 누락된 POST 폼
- Staff 전용 뷰에 `@staff_member_required(login_url='/')` + `@never_cache` 적용 여부
- API 뷰에 인증 데코레이터 적용 여부
- 경로 탈출(path traversal) 가능성
- `.env`, `db.sqlite3` 등 민감 파일이 git에 포함되지 않는지

### 결과 보고
각 단계의 결과를 요약하고, 발견된 이슈가 있으면 심각도와 함께 보고하세요.
모든 항목이 통과하면 "보안 점검 통과" 로 요약하세요.
