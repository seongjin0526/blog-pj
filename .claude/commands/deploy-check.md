---
allowed-tools: Bash(python manage.py test:*), Bash(python manage.py check:*), Bash(bandit:*), Bash(pip install bandit:*), Bash(git status:*), Bash(git add:*), Bash(git commit:*), Bash(git push:*), Bash(git diff:*), Bash(git log:*)
description: 보안 점검 후 이상 없으면 커밋 + push
---

## Context

- Current git status: !`git status`
- Current git diff (staged and unstaged): !`git diff HEAD`
- Recent commits: !`git log --oneline -5`

## 수행 단계

### 1단계: 테스트 실행
```
python manage.py test blog
```
실패하면 중단.

### 2단계: SAST (Bandit)
```
bandit -r blog/ -x blog/tests.py,blog/migrations/ -ll
```

### 3단계: 수동 보안 체크
- `|safe` 사용, CSRF, 권한 데코레이터, XSS, 경로 탈출 확인

### 4단계: 커밋 + Push
보안 점검이 모두 통과한 경우에만:
1. 변경된 파일을 모두 staging (`.env`, `db.sqlite3`, `media/`, `__pycache__/` 제외)
2. 변경 내용을 요약하여 **한국어** 커밋 메시지 작성
3. `git push origin main`

보안 이슈가 발견되면 커밋하지 말고 이슈를 보고하세요.
