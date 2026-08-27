# v5.375 PDF Whitespace-Insensitive Search Fix

## Problem
Chrome PDF Viewer의 Ctrl+F는 `데이터조작어` 검색으로 화면의 `데이터 조작어`를 찾을 수 있지만 AgentStudio 통합 찾기는 pypdf 추출 문자열을 그대로 비교해 0건이 될 수 있었습니다.

PDF의 text layer는 화면에 보이는 단어 사이에 임의 공백, 줄바꿈, zero-width 문자가 포함될 수 있습니다.

## Fix
- PDF 검색에만 Unicode NFKC 정규화 적용
- 검색 비교 시 whitespace 및 zero-width 문자 제거
- 페이지 내 줄바꿈을 사이에 둔 검색어도 검색
- 일반 소스 코드/텍스트 검색은 기존 exact whitespace 의미 유지
- v5.374의 페이지 단위 이동 및 중복 결과 제거 유지

예:
- Query: `데이터조작어`
- PDF text layer: `데이터 조작어`
- Result: match
