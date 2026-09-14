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


def _fetch_sector_info(code: str) -> dict | None:
    """stock_option_pj가 이미 매일 집계하는 업종 수급 데이터를 종목 코드로 조회."""
    try:
        resp = requests.get(f"{STOCK_API_BASE}/sectors/for-stock/{code}", timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception:
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


# 스크리너(다종목 스캔)에서 재사용하는 순수 채점 함수 — API 호출 없이 이미 가진 데이터만으로 계산.
TECH_AUTO_MAX = 10.0  # ma(2) + vol_flow(4) + rsi(2) + chase(2)
EARNINGS_AUTO_MAX = 14.0  # 매출(3) + 영업이익(4) + ROE(2) + 영업이익률개선(2) + 부채비율(3)


def technical_auto_score(tech: dict) -> tuple[float, dict]:
    """stock_option_pj 스크리너 한 종목 dict -> (점수, 세부내역). 중복 카운트 없이 지표당 1번만 반영."""
    if not tech:
        return 0.0, {}
    ma = tech.get("ma_score")
    ma_score = _tier(ma, [(1.5, 2), (0.5, 1), (-999, 0)])

    rsi_val = tech.get("rsi_14")
    rsi_score = 2.0 if (rsi_val is not None and rsi_val < 70) else (1.0 if (rsi_val is not None and rsi_val < 80) else 0.0)

    vol_surge = tech.get("volume_surge") or 0
    fnb, inb = tech.get("foreign_net_buy") or 0, tech.get("institution_net_buy") or 0
    flow_ok = fnb > 0 or inb > 0
    vol_flow_score = (2.0 if vol_surge >= 1.5 else (1.0 if vol_surge >= 1.0 else 0.0)) + (2.0 if flow_ok else 0.0)

    chg = tech.get("change_pct")
    chase_score = 2.0 if (chg is not None and chg < 5) else (1.0 if (chg is not None and chg < 8) else 0.0)

    total = ma_score + rsi_score + vol_flow_score + chase_score
    details = {
        "ma_score": ma, "rsi_14": rsi_val, "volume_surge": vol_surge,
        "foreign_net_buy": fnb, "institution_net_buy": inb, "change_pct": chg,
    }
    return total, details


def earnings_auto_score(financials: list) -> tuple[float, dict]:
    """dart-analyzer FinancialSnapshot 리스트(연도순) -> (점수, 세부내역)."""
    if not financials or len(financials) < 2:
        return 0.0, {}
    prev, curr = financials[-2], financials[-1]
    pv, cv = prev.values, curr.values

    def growth_pct(key):
        p, c = pv.get(key), cv.get(key)
        if p and c and p != 0:
            return (c - p) / abs(p) * 100
        return None

    rg = growth_pct("revenue")
    rev_score = _tier(rg, [(10, 3), (0, 2), (-999, 0)])

    og = growth_pct("operating_income")
    op_score = _tier(og, [(15, 4), (0, 2), (-999, 0)])

    roe_val = None
    ni, eq = cv.get("net_income"), cv.get("total_equity")
    if ni is not None and eq:
        roe_val = ni / eq * 100
    roe_score = _tier(roe_val, [(15, 2), (8, 1), (-999, 0)])

    prev_margin = (pv.get("operating_income") / pv["revenue"] * 100) if pv.get("revenue") else None
    curr_margin = (cv.get("operating_income") / cv["revenue"] * 100) if cv.get("revenue") else None
    margin_score = 2.0 if (prev_margin is not None and curr_margin is not None and curr_margin > prev_margin) else 0.0

    debt_score = _tier(-curr.debt_ratio if curr.debt_ratio is not None else None, [(-100, 3), (-150, 2), (-200, 1), (-99999, 0)])

    total = rev_score + op_score + roe_score + margin_score + debt_score
    details = {
        "revenue_growth_pct": rg, "operating_income_growth_pct": og, "roe_pct": roe_val,
        "prev_margin_pct": prev_margin, "curr_margin_pct": curr_margin, "debt_ratio": curr.debt_ratio,
    }
    return total, details


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

    # ── ② 업종 (15) — stock_option_pj가 이미 집계하는 업종 수급 데이터로 일부 자동
    stock_code = (tech.get("code") if tech else None) or (query if query.isdigit() else None)
    sector_info = _fetch_sector_info(stock_code) if stock_code else None
    sec_strength = sec_updown = sec_flow = None
    sec_strength_note = sec_updown_note = sec_flow_note = ""
    if sector_info:
        rank_pct = sector_info.get("flow_score_rank_pct") or 0
        sec_strength = _tier(rank_pct, [(80, 3), (60, 2), (40, 1), (-1, 0)])
        sec_strength_note = f"{sector_info['sector_name']} 업종 수급강도 상위 {100 - rank_pct:.0f}%"

        up, down = sector_info.get("up_count") or 0, sector_info.get("down_count") or 0
        sec_updown = 2.0 if up > down else 0.0
        sec_updown_note = f"업종 내 상승 {up} / 하락 {down}"

        streak = sector_info.get("buy_streak") or 0
        combined = sector_info.get("combined_net_buy") or 0
        sec_flow = _tier(streak, [(3, 3), (1, 2), (0, 0)]) if streak > 0 else (1.0 if combined > 0 else 0.0)
        sec_flow_note = f"업종 수급 연속 {streak}일" + (f", 순매수 {combined:,.0f}" if combined else "")

    sector = ChecklistSection("업종", 15, [
        ChecklistItem(8, "해당 업종이 시장 대비 강함", 3, sec_strength, sec_strength_note),
        ChecklistItem(9, "업종 내 상승 종목 수 증가", 2, sec_updown, sec_updown_note),
        ChecklistItem(10, "업종 거래대금 증가", 2, None),
        ChecklistItem(11, "업종 실적 전망 개선", 3, None),
        ChecklistItem(12, "업종에 명확한 성장 촉매 존재", 2, None),
        ChecklistItem(13, "외국인·기관의 업종 수급 개선", 3, sec_flow, sec_flow_note),
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

    # ── ④ 밸류에이션 (15) — market_cap(stock_option_pj) + 순이익/자본총계(DART)로 PER/PBR만 근사 자동화.
    # 과거 시계열 PER/PBR, 동종업계 비교, 목표주가는 데이터 부재로 여전히 수동.
    per_score = pbr_score = None
    per_note = pbr_note = ""
    market_cap = tech.get("market_cap") if tech else None
    if market_cap and dart_report and len(dart_report.financials) >= 1:
        curr = dart_report.financials[-1]
        ni, eq = curr.values.get("net_income"), curr.values.get("total_equity")
        if ni and ni > 0:
            per = market_cap / ni
            per_score = _tier(-per, [(-10, 3), (-15, 2), (-25, 1), (-99999, 0)])
            per_note = f"PER {per:.1f}배 (시총 {market_cap/1e8:,.0f}억 / 순이익 {ni/1e8:,.0f}억)"
        if eq and eq > 0:
            pbr = market_cap / eq
            roe_ratio = (ni / eq * 100) if ni else 0
            # ROE 대비 PBR 합리성: PBR이 ROE/10보다 낮으면 저평가 근사치
            justified = roe_ratio / 10 if roe_ratio else 1.0
            pbr_score = 3.0 if pbr <= justified else (1.5 if pbr <= justified * 1.5 else 0.0)
            pbr_note = f"PBR {pbr:.2f}배 (ROE {roe_ratio:.1f}% 대비 근사 적정 {justified:.2f}배)"

    valuation = ChecklistSection("밸류에이션", 15, [
        ChecklistItem(21, "현재 PER이 성장률 대비 합리적", 3, per_score, per_note),
        ChecklistItem(22, "PBR이 ROE 대비 합리적", 3, pbr_score, pbr_note),
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
