from __future__ import annotations

from dataclasses import dataclass, field

import requests

from dart_analyzer.checklist import EARNINGS_AUTO_MAX, TECH_AUTO_MAX, earnings_auto_score, technical_auto_score
from dart_analyzer.corp_code import find_corp
from dart_analyzer.financials import REPORT_CODES, fetch_financial_trend

STOCK_API_BASE = "http://localhost:8000/api"


@dataclass
class RecommendedStock:
    code: str
    name: str
    tech_score: float
    tech_details: dict
    earnings_score: float | None = None
    earnings_details: dict = field(default_factory=dict)
    close_price: float | None = None
    change_pct: float | None = None
    error: str = ""

    @property
    def combined_score(self) -> float:
        # 실적 데이터가 없으면(DART 조회 실패 등) 기술점수만으로 비교
        e = self.earnings_score if self.earnings_score is not None else 0.0
        return self.tech_score + e

    @property
    def combined_max(self) -> float:
        return TECH_AUTO_MAX + EARNINGS_AUTO_MAX


def _fetch_universe() -> list[dict]:
    resp = requests.get(f"{STOCK_API_BASE}/screener", timeout=15)
    resp.raise_for_status()
    items = resp.json()
    return items if isinstance(items, list) else items.get("items", items)


def build_recommendations(top_n: int = 10, fundamentals_pool: int = 15) -> tuple[list[RecommendedStock], str]:
    """자동 채점 가능한 항목(기술·수급 + 실적)만으로 전체 유니버스를 스캔해 상위 top_n개를 뽑는다.

    1) stock_option_pj 스크리너(이미 계산된 지표, API 호출 1번)로 전 종목 기술점수 계산.
    2) 기술점수 상위 fundamentals_pool개만 DART에서 실적을 추가 조회(전종목 조회는 너무 느림/API 제한).
    3) 기술+실적 합산 점수로 재정렬해 top_n 반환.
    """
    try:
        universe = _fetch_universe()
    except Exception as e:
        return [], f"stock_option_pj 서버(localhost:8000)에 연결하지 못했습니다: {e}"

    candidates: list[RecommendedStock] = []
    for item in universe:
        score, details = technical_auto_score(item)
        candidates.append(RecommendedStock(
            code=item.get("code", ""),
            name=item.get("name", ""),
            tech_score=score,
            tech_details=details,
            close_price=item.get("close_price"),
            change_pct=item.get("change_pct"),
        ))

    candidates.sort(key=lambda c: -c.tech_score)
    pool = candidates[:fundamentals_pool]

    for cand in pool:
        try:
            corp = find_corp(cand.code)
            # 올해 사업보고서는 연초~3월 전까지는 아직 안 나온 상태라, 3개년 범위로 조회해서
            # fetch_financial_trend가 실제 존재하는 연도만 추려내도록 함 (report.py와 동일 패턴).
            # 2개년으로 고정하면 최신 연도 데이터가 없을 때 1개년만 남아 earnings_auto_score가
            # 통째로 0으로 나오는 버그가 있었음.
            financials = fetch_financial_trend(
                corp.corp_code,
                [str(y) for y in range(_this_year() - 2, _this_year() + 1)],
                REPORT_CODES["annual"],
                "CFS",
            )
            score, details = earnings_auto_score(financials)
            cand.earnings_score = score
            cand.earnings_details = details
        except Exception as e:
            cand.error = str(e)

    pool.sort(key=lambda c: -c.combined_score)
    return pool[:top_n], ""


def _this_year() -> int:
    from datetime import date
    return date.today().year
