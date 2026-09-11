# dart-analyzer

OpenDART(금융감독원 전자공시) Open API를 이용해 한국 상장사의 공시를 분석하는 Python CLI 도구.

## 기능 (구현 예정 포함)

- [x] 종목명/종목코드 → corp_code 매핑 (전체 기업 목록 캐싱)
- [ ] 재무제표 추이 (이익잉여금, 매출/영업이익/순이익, 부채비율)
- [ ] 사채(전환사채/신주인수권부사채/교환사채) 발행 이력 + 전후 주가
- [ ] 최대주주/특수관계인 지분 변동
- [ ] 계열회사·배당 현황
- [ ] 사업보고서 원문 키워드 검색 (대여금, 특수관계자 등)
- [ ] `--compare`, `--markdown` 옵션

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
