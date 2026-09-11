from __future__ import annotations

from dataclasses import dataclass

import requests

from dart_analyzer.config import get_api_key

BASE_URL = "https://opendart.fss.or.kr/api"

# 배당 리포트에서 관심있는 항목 (se 값 기준)
DIVIDEND_KEYS = [
    "주당 현금배당금(원)",
    "(연결)현금배당성향(%)",
    "현금배당수익률(%)",
    "현금배당금총액(백만원)",
]


@dataclass
class Affiliate:
    name: str  # inv_prm — 투자대상 법인명 (사실상 계열/피투자회사)
    first_acquire_date: str
    purpose: str  # invstmnt_purps
    ownership_ratio: float | None  # trmend_blce_qota_rt (%)
    book_value: float | None  # trmend_blce_acntbk_amount (원)
    investee_total_assets: float | None
    investee_net_income: float | None


@dataclass
class DividendItem:
    label: str  # se
    stock_kind: str
    this_term: str
    prev_term: str
    before_prev_term: str


def _to_num(s: str | None) -> float | None:
    if not s or s == "-":
        return None
    s = s.replace(",", "").strip()
    try:
        return float(s)
    except ValueError:
        return None


def fetch_affiliates(corp_code: str, bsns_year: str, reprt_code: str) -> list[Affiliate]:
    """타법인 출자현황 — OpenDART에 '계열회사 목록' 전용 API가 없어 이걸로 대체.
    지분율 5% 이상 등 유의미한 투자만 걸러서 쓰는 걸 권장.
    """
    api_key = get_api_key()
    resp = requests.get(
        f"{BASE_URL}/otrCprInvstmntSttus.json",
        params={"crtfc_key": api_key, "corp_code": corp_code, "bsns_year": bsns_year, "reprt_code": reprt_code},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("status") != "000":
        return []

    return [
        Affiliate(
            name=row.get("inv_prm", ""),
            first_acquire_date=row.get("frst_acqs_de", "-"),
            purpose=row.get("invstmnt_purps", "-"),
            ownership_ratio=_to_num(row.get("trmend_blce_qota_rt")),
            book_value=_to_num(row.get("trmend_blce_acntbk_amount")),
            investee_total_assets=_to_num(row.get("recent_bsns_year_fnnr_sttus_tot_assets")),
            investee_net_income=_to_num(row.get("recent_bsns_year_fnnr_sttus_thstrm_ntpf")),
        )
        for row in data.get("list", [])
    ]


def fetch_dividend_info(corp_code: str, bsns_year: str, reprt_code: str) -> list[DividendItem]:
    """배당에 관한 사항 — 당기/전기/전전기 3개년 비교."""
    api_key = get_api_key()
    resp = requests.get(
        f"{BASE_URL}/alotMatter.json",
        params={"crtfc_key": api_key, "corp_code": corp_code, "bsns_year": bsns_year, "reprt_code": reprt_code},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("status") != "000":
        return []

    return [
        DividendItem(
            label=row.get("se", ""),
            stock_kind=row.get("stock_knd", "-"),
            this_term=row.get("thstrm", "-"),
            prev_term=row.get("frmtrm", "-"),
            before_prev_term=row.get("lwfr", "-"),
        )
        for row in data.get("list", [])
        if row.get("se") in DIVIDEND_KEYS
    ]
