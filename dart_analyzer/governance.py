from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

import requests

from dart_analyzer.config import get_api_key

BASE_URL = "https://opendart.fss.or.kr/api"


@dataclass
class AuditOpinion:
    period_label: str  # bsns_year (예: "제20기(당기)")
    auditor: str  # adtor
    opinion: str  # adt_opinion
    emphasis_matter: str  # adt_reprt_spcmnt_matter — 강조사항
    core_audit_matter: str  # core_adt_matter — 핵심감사사항


@dataclass
class CapitalIncrease:
    rcept_no: str
    new_shares: float | None  # nstk_ostk_cnt
    face_value: float | None  # fv_ps
    method: str  # ic_mthn — 제3자배정/주주배정 등
    purpose_operation: str  # fdpp_op
    purpose_biz_acquisition: str  # fdpp_bsninh
    purpose_debt_repayment: str  # fdpp_dtrp
    purpose_other_capital: str  # fdpp_ocsa


@dataclass
class Litigation:
    rcept_no: str
    filed_date: date | None  # cfd
    case_name: str  # icnm
    court: str  # cpct
    plaintiff: str  # ac_ap — 원고/신청인
    summary: str  # rq_cn (청구내용, 앞부분만)


def _to_num(s: str | None) -> float | None:
    if not s or s == "-":
        return None
    s = s.replace(",", "").strip()
    try:
        return float(s)
    except ValueError:
        return None


def _parse_dot_date(s: str | None) -> date | None:
    if not s:
        return None
    m = re.match(r"(\d{4})[.\-년]\s*(\d{1,2})[.\-월]\s*(\d{1,2})", s.strip())
    if not m:
        return None
    y, mo, d = (int(x) for x in m.groups())
    try:
        return date(y, mo, d)
    except ValueError:
        return None


def fetch_audit_opinions(corp_code: str, bsns_year: str, reprt_code: str) -> list[AuditOpinion]:
    """회계감사인의 명칭 및 감사의견 — 보통 당기/전기/전전기 3개년이 한번에 옴 (중복 행 있어 dedup)."""
    api_key = get_api_key()
    resp = requests.get(
        f"{BASE_URL}/accnutAdtorNmNdAdtOpinion.json",
        params={"crtfc_key": api_key, "corp_code": corp_code, "bsns_year": bsns_year, "reprt_code": reprt_code},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("status") != "000":
        return []

    seen = set()
    opinions: list[AuditOpinion] = []
    for row in data.get("list", []):
        key = (row.get("bsns_year"), row.get("adtor"), row.get("adt_opinion"))
        if key in seen:
            continue
        seen.add(key)
        opinions.append(
            AuditOpinion(
                period_label=row.get("bsns_year", "-"),
                auditor=row.get("adtor", "-"),
                opinion=row.get("adt_opinion", "-"),
                emphasis_matter=row.get("adt_reprt_spcmnt_matter", "-"),
                core_audit_matter=row.get("core_adt_matter", "-"),
            )
        )
    return opinions


def detect_auditor_changes(opinions: list[AuditOpinion]) -> list[str]:
    """연속된 기간 사이에 감사인이 바뀐 지점을 찾아 설명 문자열로 반환."""
    changes = []
    for prev, curr in zip(opinions[1:], opinions[:-1]):
        # opinions는 보통 당기->전기->전전기 순으로 옴
        if prev.auditor != curr.auditor and prev.auditor != "-" and curr.auditor != "-":
            changes.append(f"{prev.period_label}({prev.auditor}) -> {curr.period_label}({curr.auditor})")
    return changes


def fetch_capital_increases(corp_code: str, bgn_de: str, end_de: str) -> list[CapitalIncrease]:
    """유상증자 결정 (주요사항보고서)."""
    api_key = get_api_key()
    resp = requests.get(
        f"{BASE_URL}/piicDecsn.json",
        params={"crtfc_key": api_key, "corp_code": corp_code, "bgn_de": bgn_de, "end_de": end_de},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("status") != "000":
        return []

    return [
        CapitalIncrease(
            rcept_no=row.get("rcept_no", ""),
            new_shares=_to_num(row.get("nstk_ostk_cnt")),
            face_value=_to_num(row.get("fv_ps")),
            method=row.get("ic_mthn", "-"),
            purpose_operation=row.get("fdpp_op", "-"),
            purpose_biz_acquisition=row.get("fdpp_bsninh", "-"),
            purpose_debt_repayment=row.get("fdpp_dtrp", "-"),
            purpose_other_capital=row.get("fdpp_ocsa", "-"),
        )
        for row in data.get("list", [])
    ]


def fetch_litigations(corp_code: str, bgn_de: str, end_de: str) -> list[Litigation]:
    """소송 등의 제기 (주요사항보고서)."""
    api_key = get_api_key()
    resp = requests.get(
        f"{BASE_URL}/lwstLg.json",
        params={"crtfc_key": api_key, "corp_code": corp_code, "bgn_de": bgn_de, "end_de": end_de},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("status") != "000":
        return []

    return [
        Litigation(
            rcept_no=row.get("rcept_no", ""),
            filed_date=_parse_dot_date(row.get("cfd")),
            case_name=row.get("icnm", "-"),
            court=row.get("cpct", "-"),
            plaintiff=row.get("ac_ap", "-"),
            summary=(row.get("rq_cn", "-") or "-").replace("\n", " ")[:120],
        )
        for row in data.get("list", [])
    ]
