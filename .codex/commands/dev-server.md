# Dev Server (Codex)

## 목적
개발 서버를 실행하기 전에 마이그레이션을 적용하고 실행 상태를 확인한다.

## 절차
1. 마이그레이션 적용
```bash
python manage.py migrate
```
2. 개발 서버 실행
```bash
python manage.py runserver
```
3. 서버 시작 후 접속 주소 확인 (`http://127.0.0.1:8000/`)
