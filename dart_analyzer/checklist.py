from __future__ import annotations

from dataclasses import dataclass

import requests

STOCK_API_BASE = "http://localhost:8000/api"  # 같은 VM의 stock_option_pj 서버 (내부 호출)


@dataclass
class ChecklistItem:
    no: int
    label: str
    max_score: float
    auto_score: float | None  # None이면 자동 채움 불가 (수동 입력)
    auto_note: str = ""  # 자동 채움 근거 설명


@dataclass
class ChecklistSection:
    name: str
    max_score: int
    items: list[ChecklistItem]


def _fetch_technical(query: str) -> dict | None:
    """stock_option_pj 스크리너에서 종목명/코드로 일치하는 기술적 지표 데이터를 찾는다."""
    try:
        resp = requests.get(f"{STOCK_API_BASE}/screener", timeout=10)
        resp.raise_for_status()
        items = resp.json()
        items = items if isinstance(items, list) else items.get("items", items)
    except Exception:
        return None

    q = query.strip()
    for item in items:
        if item.get("code") == q or item.get("name") == q:
            return item
    for item in items:
        if q in (item.get("name") or ""):
            return item
    return None


def _fetch_market_signal_detail() -> dict | None:
    try:
        resp = requests.get(f"{STOCK_API_BASE}/market-signal/details", timeout=10)
        resp.raise_for_status()
        rows = resp.json()
        return {r["key"]: r for r in rows}
    except Exception:
        return None


def _tier(value: float | None, thresholds: list[tuple[float, float]], default: float = 0.0) -> float:
    """thresholds: [(기준값, 점수)] 내림차순으로 정렬돼 있다고 가정, value가 기준값 이상이면 해당 점수."""
    if value is None:
        return default
    for bound, score in thresholds:
        if value >= bound:
            return score
    return default


def build_checklist(query: str, dart_report=None) -> tuple[list[ChecklistSection], dict]:
    """자동 채움 가능한 항목은 auto_score를 채우고, 나머지는 None(수동 입력)으로 둔 30개 체크리스트를 만든다.
    dart_report: report.CompanyReport (재무 데이터 자동 채움용, 없으면 실적/밸류에이션은 전부 수동)
    """
    tech = _fetch_technical(query)
    mkt = _fetch_market_signal_detail()

    context = {"tech": tech, "market_available": mkt is not None}

    # ── ① 시장 환경 (15)
    foreign_5d = mkt.get("foreign_5d_trend") if mkt else None
    market_env = ChecklistSection("시장 환경", 15, [
        ChecklistItem(1, "KOSPI/KOSDAQ 중장기 추세 상승", 3, None),
        ChecklistItem(2, "지수가 20일·60일선 위", 2, None),
        ChecklistItem(3, "외국인 시장 누적 순매수", 2,
                       _tier(foreign_5d["normalized_score"] if foreign_5d else None, [(1, 2), (0, 1), (-999, 0)])
                       if foreign_5d else None,
                       foreign_5d["interpretation"] if foreign_5d else ""),
        ChecklistItem(4, "미국 증시 상승 추세", 2, None),
        ChecklistItem(5, "SOX/반도체 지수 상승", 2, None),
        ChecklistItem(6, "원/달러 환율·금리 리스크 안정", 2, None),
        ChecklistItem(7, "시장 변동성 과도하지 않음", 2, None),
    ])

    # ── ② 업종 (15) — 종목-섹터 매핑 자동 연동은 아직 미구현, 전부 수동
    sector = ChecklistSection("업종", 15, [
        ChecklistItem(8, "해당 업종이 시장 대비 강함", 3, None),
        ChecklistItem(9, "업종 내 상승 종목 수 증가", 2, None),
        ChecklistItem(10, "업종 거래대금 증가", 2, None),
        ChecklistItem(11, "업종 실적 전망 개선", 3, None),
        ChecklistItem(12, "업종에 명확한 성장 촉매 존재", 2, None),
        ChecklistItem(13, "외국인·기관의 업종 수급 개선", 3, None),
    ])

    # ── ③ 기업 실적 (20) — dart-analyzer 재무 데이터로 일부 자동
    rev_growth = op_growth = roe = op_margin_improve = debt_score = None
    rev_note = op_note = roe_note = margin_note = debt_note = ""
    if dart_report and len(dart_report.financials) >= 2:
        prev, curr = dart_report.financials[-2], dart_report.financials[-1]
        pv, cv = prev.values, curr.values

        def growth_pct(key):
            p, c = pv.get(key), cv.get(key)
            if p and c and p != 0:
                return (c - p) / abs(p) * 100
            return None

        rg = growth_pct("revenue")
        rev_growth = _tier(rg, [(10, 3), (0, 2), (-999, 0)])
        rev_note = f"매출 성장률 {rg:+.1f}%" if rg is not None else ""

        og = growth_pct("operating_income")
        op_growth = _tier(og, [(15, 4), (0, 2), (-999, 0)])
        op_note = f"영업이익 성장률 {og:+.1f}%" if og is not None else ""

        ni, eq = cv.get("net_income"), cv.get("total_equity")
        if ni is not None and eq:
            roe_val = ni / eq * 100
            roe = _tier(roe_val, [(15, 2), (8, 1), (-999, 0)])
            roe_note = f"ROE {roe_val:.1f}%"

        prev_margin = (pv.get("operating_income") / pv["revenue"] * 100) if pv.get("revenue") else None
        curr_margin = (cv.get("operating_income") / cv["revenue"] * 100) if cv.get("revenue") else None
        if prev_margin is not None and curr_margin is not None:
            op_margin_improve = 2.0 if curr_margin > prev_margin else 0.0
            margin_note = f"영업이익률 {prev_margin:.1f}% -> {curr_margin:.1f}%"

        if curr.debt_ratio is not None:
            debt_score = _tier(-curr.debt_ratio, [(-100, 3), (-150, 2), (-200, 1), (-99999, 0)])
            debt_note = f"부채비율 {curr.debt_ratio:.0f}%"

    earnings = ChecklistSection("기업 실적", 20, [
        ChecklistItem(14, "매출 성장", 3, rev_growth, rev_note),
        ChecklistItem(15, "영업이익 성장", 4, op_growth, op_note),
        ChecklistItem(16, "EPS 성장", 4, None, "EPS 데이터 미제공 - 영업이익 성장으로 대체 판단 권장"),
        ChecklistItem(17, "ROE 양호", 2, roe, roe_note),
        ChecklistItem(18, "영업이익률 개선", 2, op_margin_improve, margin_note),
        ChecklistItem(19, "영업현금흐름/FCF 양호", 2, None),
        ChecklistItem(20, "부채·이자 부담 안정", 3, debt_score, debt_note),
    ])

    # ── ④ 밸류에이션 (15) — PER/PBR 등은 종목별 EPS/BPS 별도 조회 필요, 전부 수동
    valuation = ChecklistSection("밸류에이션", 15, [
        ChecklistItem(21, "현재 PER이 성장률 대비 합리적", 3, None),
        ChecklistItem(22, "PBR이 ROE 대비 합리적", 3, None),
        ChecklistItem(23, "과거 평균 PER/PBR보다 저평가", 2, None),
        ChecklistItem(24, "동종업계 대비 저평가", 2, None),
        ChecklistItem(25, "목표주가 대비 상승여력 충분", 3, None),
        ChecklistItem(26, "현재 가격이 적정가치 이하", 2, None),
    ])

    # ── ⑤ 차트·수급 (20) — stock_option_pj 스크리너 지표로 자동
    ma_score = rsi = vol_flow = chase_risk = None
    ma_note = rsi_note = vol_note = chase_note = ""
    if tech:
        ma = tech.get("ma_score")
        ma_score = _tier(ma, [(1.5, 2), (0.5, 1), (-999, 0)])
        ma_note = f"MA 위치 점수 {ma}"

        rsi_val = tech.get("rsi_14")
        if rsi_val is not None:
            rsi = 2.0 if rsi_val < 70 else (1.0 if rsi_val < 80 else 0.0)
            rsi_note = f"RSI(14) {rsi_val:.0f}"

        vol_surge = tech.get("volume_surge") or 0
        fnb, inb = tech.get("foreign_net_buy") or 0, tech.get("institution_net_buy") or 0
        flow_ok = fnb > 0 or inb > 0
        vol_flow = (2.0 if vol_surge >= 1.5 else (1.0 if vol_surge >= 1.0 else 0.0)) + (2.0 if flow_ok else 0.0)
        vol_note = f"거래량 {vol_surge:.1f}배, 외인/기관 순매수 {'있음' if flow_ok else '없음'}"

        chg = tech.get("change_pct")
        if chg is not None:
            chase_risk = 2.0 if chg < 5 else (1.0 if chg < 8 else 0.0)
            chase_note = f"당일 등락률 {chg:+.1f}%"

    chart_flow = ChecklistSection("차트·수급", 20, [
        ChecklistItem(27, "20일선 > 60일선", 2, ma_score, ma_note),
        ChecklistItem(28, "60일선 상승", 2, ma_score, ma_note + " (근사치)" if ma_note else ""),
        ChecklistItem(29, "주가가 주요 이동평균선 위", 2, ma_score, ma_note),
        ChecklistItem(30, "거래량·거래대금 증가 + 외국인/기관 수급 개선", 4, vol_flow, vol_note),
        ChecklistItem(31, "전고점 돌파 또는 건강한 눌림목", 3, None),
        ChecklistItem(32, "RSI 과열 아님", 2, rsi, rsi_note),
        ChecklistItem(33, "MACD 상승", 2, None),
        ChecklistItem(34, "상승일 거래량 > 하락일 거래량", 1, None),
        ChecklistItem(35, "최근 고점 대비 과도한 추격매수 구간 아님", 2, chase_risk, chase_note),
    ])

    sections = [market_env, sector, earnings, valuation, chart_flow]
    return sections, context
