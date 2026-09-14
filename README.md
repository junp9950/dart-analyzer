# dart-analyzer

OpenDART(금융감독원 전자공시) Open API를 이용해 한국 상장사의 공시를 분석하는 Python CLI 도구.

## 기능 (구현 예정 포함)

- [x] 종목명/종목코드 → corp_code 매핑 (전체 기업 목록 캐싱)
- [x] 재무제표 추이 (이익잉여금, 매출/영업이익/순이익, 부채비율)
- [x] 사채(전환사채/신주인수권부사채/교환사채) 발행 이력
- [ ] 사채 발행 전후 주가 변동 (±10 영업일)
- [x] 최대주주/특수관계인 지분 변동 (5% 대량보유 포함)
- [x] 계열회사(타법인출자현황으로 대체)·배당 현황
- [x] 사업보고서 원문 키워드 검색 (대여금, 특수관계자 등)
- [x] `--compare`, `--markdown` 옵션

### 지배구조·회계 신뢰성 체크리스트 (2026-09-11 추가 요청, 후순위)

**회계 신뢰성**
- [ ] 감사의견 및 강조사항 (계속기업 불확실성/소송/특수관계자 거래 문구, 반기는 검토의견)
- [ ] 내부회계관리제도 검토의견 (비적정/의견없음 여부)
- [ ] 감사인 변경 이력 (교체 주기)

**오너 리스크**
- [ ] 최대주주 주식 담보(질권) 설정 현황
- [ ] 특수관계자 매출·매입 거래 (일감몰아주기)
- [ ] 계열사 지급보증·자금대여

**성장주 체크포인트**
- [ ] 스톡옵션/RSU 행사가격 (시가 대비 저가 부여 여부)
- [ ] 유상증자 이력과 목적 (제3자배정 반복 여부)
- [ ] 관리종목/투자주의 환기종목 지정 이력

**참고용**
- [ ] 임원 보수 대비 실적 연동성
- [ ] 소송 현황 (오너/회사 피고 기준, 지배구조 관련)

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

FastAPI로 감싼 웹 버전이 Azure VM(20.196.212.146)에 `dart-analyzer` systemd 서비스로 떠있음.

- http://20.196.212.146:8080/ — 검색 폼
- http://20.196.212.146:8080/analyze?q=종목명 — HTML 리포트
- http://20.196.212.146:8080/api/analyze?q=종목명 — JSON API

`main` 브랜치에 push하면 VM의 self-hosted runner(`jeewoong-test-vm-dart`)가 자동으로 pull + 재시작함 (stock_option_pj와 같은 방식).

## 다음에 할 일 (2026-09-14 기준 우선순위)

1. 사채 발행 전후 ±10영업일 주가 변동
2. 위 "지배구조·회계 신뢰성 체크리스트" 11개 항목
