from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta

import FinanceDataReader as fdr
import requests

from dart_analyzer.config import get_api_key

BASE_URL = "https://opendart.fss.or.kr/api"

# 사채 종류별 발행결정 API
BOND_ENDPOINTS = {
    "CB": ("cvbdIsDecsn", "전환사채"),
    "BW": ("bdwtIsDecsn", "신주인수권부사채"),
    "EB": ("exbdIsDecsn", "교환사채"),
}


@dataclass
class BondIssuance:
    bond_type: str  # CB / BW / EB
    bond_type_name: str
    corp_name: str
    rcept_no: str
    resolution_date: date | None  # 이사회결의일 (bddd)
    payment_date: date | None  # 납입일 (pymd) — 실제 발행일에 가까움
    maturity_date: date | None  # 사채만기일 (bd_mtd)
    face_amount: float | None  # 사채 권면총액 (bd_fta), 원
    coupon_rate: float | None  # 표면이자율 (bd_intr_ex), %
    yield_rate: float | None  # 만기이자율 (bd_intr_sf), %
    issue_method: str  # 사모/공모 (bdis_mthn)
    bond_kind_desc: str  # 사채의 종류 상세 (bd_knd)
    price_before: float | None = None  # 발행일 기준 10영업일 전 종가
    price_at_issue: float | None = None  # 발행일(납입일) 당일 또는 가장 가까운 거래일 종가
    price_after: float | None = None  # 발행일 기준 10영업일 후 종가
    price_change_before_pct: float | None = None  # (당일 - 10일전)/10일전 * 100
    price_change_after_pct: float | None = None  # (10일후 - 당일)/당일 * 100


def _parse_korean_date(s: str | None) -> date | None:
    if not s or s == "-":
        return None
    m = re.match(r"(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일", s.strip())
    if not m:
        return None
    y, mo, d = (int(x) for x in m.groups())
    try:
        return date(y, mo, d)
    except ValueError:
        return None


def _to_amount(s: str | None) -> float | None:
    if not s or s == "-":
        return None
    s = s.replace(",", "").strip()
    try:
        return float(s)
    except ValueError:
        return None


def _to_pct(s: str | None) -> float | None:
    return _to_amount(s)


def _fetch_one_type(corp_code: str, bond_type: str, bgn_de: str, end_de: str) -> list[BondIssuance]:
    api_key = get_api_key()
    endpoint, type_name = BOND_ENDPOINTS[bond_type]
    resp = requests.get(
        f"{BASE_URL}/{endpoint}.json",
        params={"crtfc_key": api_key, "corp_code": corp_code, "bgn_de": bgn_de, "end_de": end_de},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("status") != "000":
        return []

    issuances = []
    for row in data.get("list", []):
        issuances.append(
            BondIssuance(
                bond_type=bond_type,
                bond_type_name=type_name,
                corp_name=row.get("corp_name", ""),
                rcept_no=row.get("rcept_no", ""),
                resolution_date=_parse_korean_date(row.get("bddd")),
                payment_date=_parse_korean_date(row.get("pymd")),
                maturity_date=_parse_korean_date(row.get("bd_mtd")),
                face_amount=_to_amount(row.get("bd_fta")),
                coupon_rate=_to_pct(row.get("bd_intr_ex")),
                yield_rate=_to_pct(row.get("bd_intr_sf")),
                issue_method=row.get("bdis_mthn", "-"),
                bond_kind_desc=row.get("bd_knd", "-"),
            )
        )
    return issuances


def fetch_bond_issuances(
    corp_code: str, bgn_de: str, end_de: str, bond_types: tuple[str, ...] = ("CB", "BW", "EB")
) -> list[BondIssuance]:
    """전환사채/신주인수권부사채/교환사채 발행결정 이력을 모두 조회해 발행일(납입일) 순으로 정렬."""
    all_issuances: list[BondIssuance] = []
    for bt in bond_types:
        all_issuances.extend(_fetch_one_type(corp_code, bt, bgn_de, end_de))
    all_issuances.sort(key=lambda x: x.payment_date or x.resolution_date or date.min)
    return all_issuances


def attach_price_around_issuance(bonds: list[BondIssuance], stock_code: str, window_business_days: int = 10) -> None:
    """각 사채 발행일(납입일) 기준 ±N영업일 종가와 변동률을 bonds 리스트에 채워넣는다 (in-place).

    비상장 발행법인(stock_code 없음)이나 가격 데이터가 부족한 구간은 조용히 건너뛴다.
    """
    if not stock_code:
        return
    dated = [b for b in bonds if b.payment_date or b.resolution_date]
    if not dated:
        return

    anchor_dates = [b.payment_date or b.resolution_date for b in dated]
    start = min(anchor_dates) - timedelta(days=window_business_days * 2 + 10)
    end = min(date.today(), max(anchor_dates) + timedelta(days=window_business_days * 2 + 10))

    try:
        df = fdr.DataReader(stock_code, start.isoformat(), end.isoformat())
    except Exception:
        return
    if df is None or df.empty:
        return

    closes = df["Close"]  # index: 거래일(Timestamp), 오름차순

    for bond in dated:
        anchor = bond.payment_date or bond.resolution_date
        idx = closes.index.searchsorted(anchor.isoformat())
        if idx >= len(closes):
            idx = len(closes) - 1

        before_idx = idx - window_business_days
        after_idx = idx + window_business_days

        at_price = float(closes.iloc[idx]) if 0 <= idx < len(closes) else None
        before_price = float(closes.iloc[before_idx]) if 0 <= before_idx < len(closes) else None
        after_price = float(closes.iloc[after_idx]) if 0 <= after_idx < len(closes) else None

        bond.price_at_issue = at_price
        bond.price_before = before_price
        bond.price_after = after_price
        if before_price and at_price:
            bond.price_change_before_pct = round((at_price - before_price) / before_price * 100, 2)
        if at_price and after_price:
            bond.price_change_after_pct = round((after_price - at_price) / at_price * 100, 2)
