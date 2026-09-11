from __future__ import annotations

from dataclasses import dataclass

import requests

from dart_analyzer.config import get_api_key

FNLTT_URL = "https://opendart.fss.or.kr/api/fnlttSinglAcntAll.json"

# 정기보고서 코드: 1분기, 반기, 3분기, 사업(연간)보고서
REPORT_CODES = {
    "1Q": "11013",
    "2Q": "11012",  # 반기보고서
    "3Q": "11014",
    "annual": "11011",
}

# 재무제표에서 뽑을 핵심 계정과목 (account_nm 기준, 여러 표기 후보를 순서대로 시도)
KEY_ACCOUNTS = {
    "revenue": ["매출액", "수익(매출액)", "영업수익"],
    "operating_income": ["영업이익", "영업이익(손실)"],
    "net_income": ["당기순이익", "당기순이익(손실)", "분기순이익(손실)"],
    "retained_earnings": ["이익잉여금", "미처분이익잉여금"],
    "total_equity": ["자본총계"],
    "total_liabilities": ["부채총계"],
    "total_assets": ["자산총계"],
}


@dataclass
class FinancialSnapshot:
    corp_code: str
    bsns_year: str
    reprt_code: str
    fs_div: str  # CFS(연결) / OFS(별도)
    values: dict[str, float]  # key -> 당기 금액(원)
    debt_ratio: float | None  # 부채비율(%) = 부채총계/자본총계*100


def _to_amount(s: str | None) -> float | None:
    if not s:
        return None
    s = s.replace(",", "").strip()
    if not s or s == "-":
        return None
    try:
        return float(s)
    except ValueError:
        return None


def fetch_financials(corp_code: str, bsns_year: str, reprt_code: str, fs_div: str = "CFS") -> FinancialSnapshot | None:
    """단일회사 전체 재무제표 조회. fs_div: CFS(연결) 또는 OFS(별도).

    해당 연도/보고서에 데이터가 없으면(status != '000') None 반환.
    """
    api_key = get_api_key()
    resp = requests.get(
        FNLTT_URL,
        params={
            "crtfc_key": api_key,
            "corp_code": corp_code,
            "bsns_year": bsns_year,
            "reprt_code": reprt_code,
            "fs_div": fs_div,
        },
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()

    if data.get("status") != "000":
        return None

    rows = data.get("list", [])
    values: dict[str, float] = {}
    for key, name_candidates in KEY_ACCOUNTS.items():
        for row in rows:
            if row.get("account_nm") in name_candidates:
                amount = _to_amount(row.get("thstrm_amount"))
                if amount is not None:
                    values[key] = amount
                    break

    debt_ratio = None
    if values.get("total_liabilities") is not None and values.get("total_equity"):
        debt_ratio = round(values["total_liabilities"] / values["total_equity"] * 100, 2)

    return FinancialSnapshot(
        corp_code=corp_code,
        bsns_year=bsns_year,
        reprt_code=reprt_code,
        fs_div=fs_div,
        values=values,
        debt_ratio=debt_ratio,
    )


def fetch_financial_trend(
    corp_code: str, years: list[str], reprt_code: str = REPORT_CODES["annual"], fs_div: str = "CFS"
) -> list[FinancialSnapshot]:
    """여러 연도의 재무 스냅샷을 순서대로 조회 (데이터 없는 연도는 건너뜀)."""
    snapshots = []
    for year in years:
        snap = fetch_financials(corp_code, year, reprt_code, fs_div)
        if snap is not None:
            snapshots.append(snap)
    return snapshots
