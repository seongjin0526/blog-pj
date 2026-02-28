# Security Check (Codex)

## 목적
배포 전 기본 보안 점검을 수행한다.

## 절차
1. 테스트 실행
```bash
python manage.py test blog
```
실패 시 중단.

2. SAST(Bandit)
```bash
bandit -r blog/ -x blog/tests.py,blog/migrations/ -ll
```
미설치 시:
```bash
pip install bandit
```

3. 수동 체크
- `|safe` 필터 사용 위치 점검 (XSS 위험)
- POST 폼의 `{% csrf_token %}` 누락 여부
- Staff 뷰 데코레이터 적용 여부
- API 인증 데코레이터 적용 여부
- 경로 탈출(path traversal) 가능성
- `.env`, `db.sqlite3` 등 민감 파일 Git 추적 여부
- Docker `web` 컨테이너 UID 확인 (`docker compose exec -T web id -u`) 값이 `0`이면 실패
- `docker-compose.yml`에 `privileged: false` 유지 여부 확인
- `docker-compose.yml`에 `security_opt: [no-new-privileges:true]`, `cap_drop: [ALL]` 유지 여부 확인

4. 결과 기록
- `CODEX_CHANGELOG.md`에 점검 결과 요약 추가
