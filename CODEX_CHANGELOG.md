# CODEX Change Log

Codex가 수행한 구현/수정 내역을 기록합니다.  
Claude로 전환할 때 이 파일을 기준으로 변경 의도와 영향 범위를 빠르게 파악합니다.

## Template
```md
## YYYY-MM-DD
- Summary: 한 줄 요약
- Files: path1, path2
- User Impact: 사용자 관점 영향
- Validation: 테스트/검증 명령 및 결과
- Claude Handoff: Claude가 이어서 작업할 때 필요한 맥락
```

## 2026-02-28
- Summary: Claude 전용 문서/명령을 Codex 기준으로 정리하고 전환 지침 체계를 추가함.
- Files: .gitignore, CODEX.md, CODEX_CHANGELOG.md, .codex/commands/dev-server.md, .codex/commands/security-check.md, .codex/commands/deploy-check.md, README.md
- User Impact: Codex 중심 운영 문서가 추가되어 작업 기준이 일관되고, Claude 관련 로컬 파일은 Git 추적에서 제외됨.
- Validation: 문서 변경 작업(코드 실행 없음), `git status --short`로 변경 파일 확인.
- Claude Handoff: 이후 기능/버그 수정 시 본 파일에 누적 기록하면 Claude가 맥락을 잃지 않고 작업을 이어갈 수 있음.

## 2026-02-28
- Summary: `.claude` export 대화 내용을 참고해 Codex 가이드/커맨드/스킬로 이관함.
- Files: CODEX.md, CODEX_CHANGELOG.md, .codex/commands/tag-discovery-ui.md, .codex/skills/blog-navbar-tag-discovery/SKILL.md
- User Impact: 태그 탐색 UI 구현 기준과 향후 제목/본문 검색 확장 포인트를 Codex 문서 체계에서 바로 재사용 가능.
- Validation: `sed`로 `.claude` export 원문 확인 후 신규 문서 생성, `git status --short`로 파일 반영 확인.
- Claude Handoff: `.claude`는 원본 로그 보관용으로 두고, 실제 작업 규칙은 `.codex`와 `CODEX.md`를 우선 참조.

## 2026-02-28
- Summary: Docker 컨테이너 비루트/비특권 실행 정책을 compose와 Codex 보안 가이드에 명시.
- Files: docker-compose.yml, CODEX.md, .codex/commands/security-check.md, CODEX_CHANGELOG.md
- User Impact: web/test 컨테이너의 권한이 최소화되어 컨테이너 탈출 및 권한 상승 리스크를 낮춤.
- Validation: `docker compose exec -T web id -u` 결과 `999`, `docker compose run --rm --no-deps test id -u` 결과 `999`, `docker compose config`로 `no-new-privileges`/`cap_drop` 반영 확인.
- Claude Handoff: 이후 compose 수정 시 `privileged: false`, `no-new-privileges:true`, `cap_drop: [ALL]` 정책 유지 필요.
