from __future__ import annotations

from dart_analyzer.formatting import fmt_amount
from dart_analyzer.report import CompanyReport


def report_to_markdown(report: CompanyReport, bonds_only: bool = False) -> str:
    corp = report.corp
    lines = [f"# {corp.corp_name} ({corp.stock_code or corp.corp_code})", ""]

    if not bonds_only and report.financials:
        lines += ["## 재무제표 추이 (연결)", "", "| 연도 | 매출액 | 영업이익 | 당기순이익 | 이익잉여금 | 부채비율 |", "|---|---|---|---|---|---|"]
        for s in report.financials:
            v = s.values
            lines.append(
                f"| {s.bsns_year} | {fmt_amount(v.get('revenue'))} | {fmt_amount(v.get('operating_income'))} "
                f"| {fmt_amount(v.get('net_income'))} | {fmt_amount(v.get('retained_earnings'))} "
                f"| {s.debt_ratio if s.debt_ratio is not None else '-'}% |"
            )
        lines.append("")

    if report.bonds:
        lines += ["## 사채 발행 이력", "", "| 종류 | 납입일 | 만기일 | 금액 | 표면이자율 | 방식 |", "|---|---|---|---|---|---|"]
        for b in report.bonds:
            lines.append(
                f"| {b.bond_type} | {b.payment_date or b.resolution_date or '-'} | {b.maturity_date or '-'} "
                f"| {fmt_amount(b.face_amount)} | {b.coupon_rate if b.coupon_rate is not None else '-'}% | {b.issue_method} |"
            )
        lines.append("")

    if not bonds_only and report.shareholders:
        lines += ["## 최대주주 및 특수관계인", "", "| 이름 | 관계 | 종류 | 기초지분율 | 기말지분율 |", "|---|---|---|---|---|"]
        for s in report.shareholders:
            lines.append(
                f"| {s.name} | {s.relation} | {s.stock_kind} "
                f"| {s.begin_ratio if s.begin_ratio is not None else '-'}% "
                f"| {s.end_ratio if s.end_ratio is not None else '-'}% |"
            )
        lines.append("")

    if not bonds_only and report.dividends:
        lines += ["## 배당 현황", "", "| 구분 | 종류 | 당기 | 전기 | 전전기 |", "|---|---|---|---|---|"]
        for d in report.dividends:
            lines.append(f"| {d.label} | {d.stock_kind} | {d.this_term} | {d.prev_term} | {d.before_prev_term} |")
        lines.append("")

    return "\n".join(lines)
