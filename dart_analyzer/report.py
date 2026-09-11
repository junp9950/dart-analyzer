from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

from dart_analyzer.bonds import BondIssuance, fetch_bond_issuances
from dart_analyzer.corp_code import Corp, find_corp
from dart_analyzer.corp_group import Affiliate, DividendItem, fetch_affiliates, fetch_dividend_info
from dart_analyzer.financials import REPORT_CODES, FinancialSnapshot, fetch_financial_trend
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


def build_report(query: str, years_back: int = 5, bonds_only: bool = False) -> CompanyReport:
    corp = find_corp(query)
    this_year = date.today().year
    years = [str(y) for y in range(this_year - 2, this_year + 1)]  # 최근 3개년

    report = CompanyReport(corp=corp)

    bgn_de = (date.today() - timedelta(days=365 * years_back)).strftime("%Y%m%d")
    end_de = date.today().strftime("%Y%m%d")
    report.bonds = fetch_bond_issuances(corp.corp_code, bgn_de, end_de)

    if bonds_only:
        return report

    report.financials = fetch_financial_trend(corp.corp_code, years, REPORT_CODES["annual"], "CFS")

    latest_year = years[-1]
    report.shareholders = fetch_major_shareholders(corp.corp_code, latest_year, REPORT_CODES["annual"])
    if not report.shareholders and len(years) > 1:
        # 최신 연도 사업보고서가 아직 안 나왔으면 전년도로 재시도
        report.shareholders = fetch_major_shareholders(corp.corp_code, years[-2], REPORT_CODES["annual"])

    report.ownership_changes = fetch_ownership_changes(corp.corp_code)
    report.affiliates = fetch_affiliates(corp.corp_code, latest_year, REPORT_CODES["annual"])
    report.dividends = fetch_dividend_info(corp.corp_code, latest_year, REPORT_CODES["annual"])

    return report
