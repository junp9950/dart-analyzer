from __future__ import annotations

from dataclasses import dataclass

import requests

from dart_analyzer.config import get_api_key

BASE_URL = "https://opendart.fss.or.kr/api"


@dataclass
class MajorShareholder:
    name: str  # nm
    relation: str  # relate (최대주주 본인 / 특수관계인)
    stock_kind: str  # stock_knd
    begin_shares: float | None
    begin_ratio: float | None  # %
    end_shares: float | None
    end_ratio: float | None  # %
    note: str  # rm


@dataclass
class OwnershipChange:
    rcept_no: str
    rcept_dt: str
    reporter: str  # repror — 대량보유자 이름
    stock_qty: float | None  # stkqy — 보유주식수
    stock_qty_change: float | None  # stkqy_irds
    stock_ratio: float | None  # stkrt (%)
    stock_ratio_change: float | None  # stkrt_irds
    reason: str  # report_resn


def _to_num(s: str | None) -> float | None:
    if not s or s == "-":
        return None
    s = s.replace(",", "").strip()
    try:
        return float(s)
    except ValueError:
        return None


def fetch_major_shareholders(corp_code: str, bsns_year: str, reprt_code: str) -> list[MajorShareholder]:
    """최대주주 및 특수관계인 소유주식 현황 (해당 정기보고서 기준 스냅샷)."""
    api_key = get_api_key()
    resp = requests.get(
        f"{BASE_URL}/hyslrSttus.json",
        params={"crtfc_key": api_key, "corp_code": corp_code, "bsns_year": bsns_year, "reprt_code": reprt_code},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("status") != "000":
        return []

    return [
        MajorShareholder(
            name=row.get("nm", ""),
            relation=row.get("relate", ""),
            stock_kind=row.get("stock_knd", ""),
            begin_shares=_to_num(row.get("bsis_posesn_stock_co")),
            begin_ratio=_to_num(row.get("bsis_posesn_stock_qota_rt")),
            end_shares=_to_num(row.get("trmend_posesn_stock_co")),
            end_ratio=_to_num(row.get("trmend_posesn_stock_qota_rt")),
            note=row.get("rm", "-"),
        )
        for row in data.get("list", [])
    ]


def fetch_ownership_changes(corp_code: str) -> list[OwnershipChange]:
    """주식등의 대량보유상황보고 (5% rule) 변동 이력 — 접수일 기준 최신순으로 옴."""
    api_key = get_api_key()
    resp = requests.get(
        f"{BASE_URL}/majorstock.json",
        params={"crtfc_key": api_key, "corp_code": corp_code},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("status") != "000":
        return []

    return [
        OwnershipChange(
            rcept_no=row.get("rcept_no", ""),
            rcept_dt=row.get("rcept_dt", ""),
            reporter=row.get("repror", ""),
            stock_qty=_to_num(row.get("stkqy")),
            stock_qty_change=_to_num(row.get("stkqy_irds")),
            stock_ratio=_to_num(row.get("stkrt")),
            stock_ratio_change=_to_num(row.get("stkrt_irds")),
            reason=row.get("report_resn", "-"),
        )
        for row in data.get("list", [])
    ]
