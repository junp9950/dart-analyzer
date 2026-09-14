# dart-analyzer

OpenDART(금융감독원 전자공시) Open API를 이용해 한국 상장사의 공시를 분석하는 Python CLI 도구.

## 기능 (구현 예정 포함)

- [x] 종목명/종목코드 → corp_code 매핑 (전체 기업 목록 캐싱)
- [x] 재무제표 추이 (이익잉여금, 매출/영업이익/순이익, 부채비율)
- [x] 사채(전환사채/신주인수권부사채/교환사채) 발행 이력
- [x] 사채 발행 전후 주가 변동 (±10 영업일)
- [x] 최대주주/특수관계인 지분 변동 (5% 대량보유 포함)
- [x] 계열회사(타법인출자현황으로 대체)·배당 현황
- [x] 사업보고서 원문 키워드 검색 (대여금, 특수관계자 등)
- [x] `--compare`, `--markdown` 옵션

### 지배구조·회계 신뢰성 체크리스트 (2026-09-11 요청, 2026-09-14 구현 완료)

전용 API가 있는 항목은 구조화된 표로, 없는 항목은 `--doc-search` 원문 키워드 검색으로 커버.

**회계 신뢰성**
- [x] 감사의견 및 강조사항 — `accnutAdtorNmNdAdtOpinion` (당기/전기/전전기 3개년, 강조사항·핵심감사사항 포함)
- [x] 내부회계관리제도 검토의견 — 전용 API 없음, `--doc-search` 키워드("내부회계관리제도")로 대체
- [x] 감사인 변경 이력 — 위 API 응답에서 연도별 감사인명 비교해 자동 감지

**오너 리스크**
- [x] 최대주주 주식 담보(질권) 설정 현황 — 전용 API 없음, `--doc-search` 키워드("질권")로 대체
- [x] 특수관계자 매출·매입 거래 (일감몰아주기) — `--doc-search` 키워드("특수관계자") + 계열회사 표
- [x] 계열사 지급보증·자금대여 — `--doc-search` 키워드("지급보증", "대여금")

**성장주 체크포인트**
- [x] 스톡옵션/RSU 행사가격 — 전용 API 없음, `--doc-search` 키워드("주식매수선택권")로 대체
- [x] 유상증자 이력과 목적 — `piicDecsn` (방식/신주 수/자금 사용목적)
- [x] 관리종목/투자주의 환기종목 지정 이력 — KRX 시장조치 영역이라 DART API 없음, `--doc-search` 키워드로 최소 커버 (완전하지 않음, 필요시 KRX 데이터 별도 연동 검토)

**참고용**
- [ ] 임원 보수 대비 실적 연동성 — `hmvAuditIndvdlBySttus`(개인별보수) 등 API는 있으나 아직 리포트에 미연동
- [x] 소송 현황 — `lwstLg` (사건명/법원/원고/청구내용)

## 설치

```bash
python -m venv .venv
.venv\Scripts\activate  # Windows
pip install -r requirements.txt
```

`.env` 파일 생성 (`.env.example` 참고):

```
DART_API_KEY=발급받은_키
```

키는 https://opendart.fss.or.kr 에서 무료로 발급.

## 사용 예시

```bash
python dart_analyzer.py 디아이
python dart_analyzer.py --compare 디아이 저스템 산일전기
python dart_analyzer.py 디아이 --bonds-only
python dart_analyzer.py 디아이 --markdown report.md
```

## 웹서버 (배포됨)

FastAPI로 감싼 웹 버전이 Azure VM(20.196.212.146)에 `dart-analyzer` systemd 서비스(포트 8080)로 떠있고,
Caddy가 앞단에서 HTTPS(Let's Encrypt, sslip.io 매직 도메인)를 처리함.

- https://dart.20-196-212-146.sslip.io/ — 검색 폼 (HTTPS, 추천)
- https://dart.20-196-212-146.sslip.io/analyze?q=종목명 — HTML 리포트
- https://dart.20-196-212-146.sslip.io/api/analyze?q=종목명 — JSON API
- http://20.196.212.146:8080/ 로 직접 접속도 되지만 평문(HTTP)

Caddy 설정은 VM의 `/etc/caddy/Caddyfile` (같은 Caddy가 stock_option_pj도 `stock.20-196-212-146.sslip.io`로 서빙).

`main` 브랜치에 push하면 VM의 self-hosted runner(`jeewoong-test-vm-dart`)가 자동으로 pull + 재시작함 (stock_option_pj와 같은 방식).

## 다음에 할 일 (2026-09-14 기준)

1. 임원 보수 대비 실적 연동성 (API는 확인됨, 리포트 미연동)
2. 관리종목/투자주의 환기종목 지정 이력 — KRX 데이터 별도 연동 검토
3. `/api/analyze` JSON 응답에 governance/keyword_hits 필드 추가 (현재 HTML/markdown에만 있음)
