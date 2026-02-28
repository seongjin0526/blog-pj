# Deploy Check (Codex)

## 목적
테스트/보안 점검 통과 시에만 배포용 커밋과 푸시를 진행한다.

## 절차
1. 테스트 실행
```bash
python manage.py test blog
```

2. 보안 점검
```bash
bandit -r blog/ -x blog/tests.py,blog/migrations/ -ll
```

3. Git 상태 확인
```bash
git status
git diff HEAD
git log --oneline -5
```

4. 커밋/푸시 전 기준
- `.env`, `db.sqlite3`, `media/`, `__pycache__/` 제외
- 변경 요약이 반영된 한국어 커밋 메시지
- `CODEX_CHANGELOG.md` 최신화 확인

5. 배포 반영
```bash
git add <필요 파일>
git commit -m "<한국어 커밋 메시지>"
git push origin main
```

보안 이슈가 있으면 배포를 중단하고 이슈를 먼저 수정한다.
