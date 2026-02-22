# blog-pj

## Google 로그인 설정 가이드

댓글 기능을 사용하려면 Google OAuth 설정이 필요합니다.

### 1. Google Cloud Console 설정

1. [Google Cloud Console](https://console.cloud.google.com/)에 접속
2. 프로젝트 생성 (또는 기존 프로젝트 선택)
3. **API 및 서비스 > 사용자 인증 정보** 이동
4. **사용자 인증 정보 만들기 > OAuth 클라이언트 ID** 클릭
5. 애플리케이션 유형: **웹 애플리케이션**
6. **승인된 리디렉션 URI** 에 아래 주소 추가:
   ```
   http://localhost:8000/accounts/google/login/callback/
   ```
7. 생성된 **클라이언트 ID**와 **클라이언트 보안 비밀번호**를 메모

> OAuth 동의 화면 설정을 먼저 요구할 수 있습니다. 테스트 단계에서는 "외부" 선택 후 앱 이름만 입력하면 됩니다.

### 2. Django 관리자 계정 생성

```bash
python manage.py createsuperuser
```

### 3. Django Admin에서 Social Application 등록

1. `python manage.py runserver` 실행
2. `http://localhost:8000/admin/` 접속 후 로그인
3. **Social applications > Add** 클릭
4. 아래와 같이 입력:
   - **Provider**: Google
   - **Name**: Google (자유)
   - **Client id**: 1단계에서 메모한 클라이언트 ID
   - **Secret key**: 1단계에서 메모한 클라이언트 보안 비밀번호
   - **Sites**: `example.com`을 오른쪽(Chosen sites)으로 이동
5. 저장

### 4. 확인

- 네비바의 **Google 로그인** 클릭 → Google 계정 선택 → 로그인 완료
- 포스트 상세 페이지에서 댓글 작성/삭제 테스트
