from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

from dart_analyzer.bonds import BondIssuance, attach_price_around_issuance, fetch_bond_issuances
from dart_analyzer.corp_code import Corp, find_corp
from dart_analyzer.corp_group import Affiliate, DividendItem, fetch_affiliates, fetch_dividend_info
from dart_analyzer.documents import (
    KeywordHit,
    fetch_document_text,
    find_recent_reports,
    search_bw_allottee_hits,
    search_keywords,
)
from dart_analyzer.financials import REPORT_CODES, FinancialSnapshot, fetch_financial_trend
from dart_analyzer.governance import (
    AuditOpinion,
    CapitalIncrease,
    Litigation,
    detect_auditor_changes,
    fetch_audit_opinions,
    fetch_capital_increases,
    fetch_litigations,
)
from dart_analyzer.ownership import MajorShareholder, OwnershipChange, fetch_major_shareholders, fetch_ownership_changes


@dataclass
class CompanyReport:
    corp: Corp
    financials: list[FinancialSnapshot] = field(default_factory=list)
    bonds: list[BondIssuance] = field(default_factory=list)
    shareholders: list[MajorShareholder] = field(default_factory=list)
    ownership_changes: list[OwnershipChange] = field(default_factory=list)
    affiliates: list[Affiliate] = field(default_factory=list)
    dividends: list[DividendItem] = field(default_factory=list)
    keyword_hits: list[KeywordHit] = field(default_factory=list)
    keyword_source_report: str = ""
    audit_opinions: list[AuditOpinion] = field(default_factory=list)
    auditor_changes: list[str] = field(default_factory=list)
    capital_increases: list[CapitalIncrease] = field(default_factory=list)
    litigations: list[Litigation] = field(default_factory=list)


def _attach_keyword_search(report: CompanyReport, corp_code: str) -> None:
    """가장 최근 정기보고서(사업/반기/분기) 원문에서 키워드 문맥을 찾아 report에 채운다.
    원문이 커서 느릴 수 있어 실패해도 리포트 전체를 막지 않는다.
    """
    try:
        bgn_de = (date.today() - timedelta(days=400)).strftime("%Y%m%d")
        end_de = date.today().strftime("%Y%m%d")
        recent = find_recent_reports(corp_code, bgn_de, end_de)
        if recent:
            target = recent[0]
            text = fetch_document_text(target.rcept_no)
            report.keyword_hits = search_keywords(text)
            report.keyword_source_report = f"{target.report_name} ({target.rcept_date})"
    except Exception:
        # 원문 파싱은 부가 기능 — 실패해도 나머지 리포트는 정상 출력
        report.keyword_hits = []

    # BW(신주인수권부사채) 발행결정 원문에서 오너/특수관계인 이름이 워런트 배정과
    # 함께 언급되는지 확인 — 최신 정기보고서 검색으로는 발행 당시 배정 내역을
    # 놓치는 경우가 있어(디아이 사례에서 확인) 별도로 원본 공시를 더 연다.
    try:
        owner_names = [
            s.name for s in report.shareholders
            if any(k in s.relation for k in ("본인", "특수관계인")) and s.name not in ("계", "-")
        ][:5]
        bw_targets = [
            (b.rcept_no, str(b.payment_date or b.resolution_date or "-"))
            for b in report.bonds if b.bond_type == "BW" and b.rcept_no
        ]
        bw_hits = search_bw_allottee_hits(bw_targets, owner_names)
        report.keyword_hits.extend(bw_hits)
    except Exception:
        pass


def build_report(query: str, years_back: int = 5, bonds_only: bool = False, doc_search: bool = False) -> CompanyReport:
    corp = find_corp(query)
    this_year = date.today().year
    years = [str(y) for y in range(this_year - 2, this_year + 1)]  # 최근 3개년

    report = CompanyReport(corp=corp)

    bgn_de = (date.today() - timedelta(days=365 * years_back)).strftime("%Y%m%d")
    end_de = date.today().strftime("%Y%m%d")
    report.bonds = fetch_bond_issuances(corp.corp_code, bgn_de, end_de)
    attach_price_around_issuance(report.bonds, corp.stock_code)

    if bonds_only:
        return report

    report.financials = fetch_financial_trend(corp.corp_code, years, REPORT_CODES["annual"], "CFS")

    latest_year = years[-1]
    report.shareholders = fetch_major_shareholders(corp.corp_code, latest_year, REPORT_CODES["annual"])
    if not report.shareholders and len(years) > 1:
        # 최신 연도(예: 올해) 사업보고서가 아직 안 나왔으면 전년도로 재시도
        latest_year = years[-2]
        report.shareholders = fetch_major_shareholders(corp.corp_code, latest_year, REPORT_CODES["annual"])

    report.ownership_changes = fetch_ownership_changes(corp.corp_code)
    report.affiliates = fetch_affiliates(corp.corp_code, latest_year, REPORT_CODES["annual"])
    report.dividends = fetch_dividend_info(corp.corp_code, latest_year, REPORT_CODES["annual"])

    report.audit_opinions = fetch_audit_opinions(corp.corp_code, latest_year, REPORT_CODES["annual"])
    report.auditor_changes = detect_auditor_changes(report.audit_opinions)
    report.capital_increases = fetch_capital_increases(corp.corp_code, bgn_de, end_de)
    report.litigations = fetch_litigations(corp.corp_code, bgn_de, end_de)

    if doc_search:
        _attach_keyword_search(report, corp.corp_code)

    return report
