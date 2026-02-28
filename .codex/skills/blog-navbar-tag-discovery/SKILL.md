---
name: blog-navbar-tag-discovery
description: Use this skill when implementing or updating blog navbar tag discovery UX, including top tags, expandable full tags, tag search toggle, and incremental autocomplete with future-ready search architecture.
---

# Blog Navbar Tag Discovery

## Use This Skill When
- 사용자가 블로그 상단 네비바에 태그 탐색 UI를 요청할 때
- `더보기`, `검색`, `자동완성` 동작을 함께 구성해야 할 때
- 태그 검색을 이후 제목/본문 검색으로 확장 가능한 구조가 필요할 때

## Workflow
1. 데이터 준비
- 태그 집계 함수에서 `(tag, count)` 빈도 내림차순 결과를 만든다.
- 템플릿 컨텍스트에 `top_tags`와 `all_tag_items`를 같이 전달한다.

2. 네비바 UI
- 상위 태그만 한 줄로 노출한다.
- `더보기` 버튼으로 전체 태그 패널을 토글한다.
- `검색` 버튼으로 검색 패널을 토글한다.

3. 자동완성
- `json_script`로 태그 목록을 안전하게 주입한다.
- 입력 이벤트에서 매칭 결과를 제한 개수로 렌더링한다.
- 매칭 정렬 우선순위:
  - 검색어 포함 시작 위치가 앞선 태그
  - 태그 사용 빈도 높은 순
  - 태그명 사전순

4. 확장 포인트
- 매칭 함수는 `searchTags(query)`처럼 분리한다.
- 이후 `searchPosts(query)`를 추가해 제목/본문 통합 검색으로 확장한다.

5. 품질 확인
- 데스크톱/모바일 네비바 레이아웃 확인
- 검색 패널/추천 패널의 열기/닫기 충돌 확인
- 현재 태그 선택 상태 강조 확인

## Implementation Notes
- 템플릿 로직은 `templates/base.html` 중심으로 유지한다.
- 스타일은 `static/css/style.css`에만 추가한다.
- 태그가 없는 경우 위젯 전체를 숨긴다.
