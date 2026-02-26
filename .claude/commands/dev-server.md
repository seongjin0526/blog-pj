---
allowed-tools: Bash(python manage.py runserver:*), Bash(python manage.py migrate:*), Bash(pip install:*)
description: 개발 서버 실행 (migrate 후 runserver)
---

## 개발 서버 시작

1. 마이그레이션 적용:
```
python manage.py migrate
```

2. 개발 서버를 백그라운드로 실행:
```
python manage.py runserver
```

서버가 시작되면 접속 주소를 알려주세요.
