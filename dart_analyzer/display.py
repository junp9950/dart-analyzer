from __future__ import annotations

from rich.console import Console
from rich.table import Table

from dart_analyzer.formatting import fmt_amount
from dart_analyzer.report import CompanyReport

console = Console()


def render_report(report: CompanyReport, bonds_only: bool = False) -> None:
    corp = report.corp
    console.rule(f"[bold cyan]{corp.corp_name} ({corp.stock_code or corp.corp_code})[/bold cyan]")

    if not bonds_only:
        _render_financials(report)
    _render_bonds(report)
    if not bonds_only:
        _render_ownership(report)
        _render_affiliates(report)
        _render_dividends(report)


def _render_financials(report: CompanyReport) -> None:
    if not report.financials:
        console.print("[yellow]재무 데이터 없음[/yellow]")
        return
    table = Table(title="재무제표 추이 (연결)")
    table.add_column("연도")
    table.add_column("매출액", justify="right")
    table.add_column("영업이익", justify="right")
    table.add_column("당기순이익", justify="right")
    table.add_column("이익잉여금", justify="right")
    table.add_column("부채비율", justify="right")
    for snap in report.financials:
        v = snap.values
        table.add_row(
            snap.bsns_year,
            fmt_amount(v.get("revenue")),
            fmt_amount(v.get("operating_income")),
            fmt_amount(v.get("net_income")),
            fmt_amount(v.get("retained_earnings")),
            f"{snap.debt_ratio:.1f}%" if snap.debt_ratio is not None else "-",
        )
    console.print(table)


def _render_bonds(report: CompanyReport) -> None:
    if not report.bonds:
        console.print("[green]사채(CB/BW/EB) 발행 이력 없음[/green]")
        return
    table = Table(title=f"사채 발행 이력 ({len(report.bonds)}건)")
    table.add_column("종류")
    table.add_column("납입일")
    table.add_column("만기일")
    table.add_column("금액", justify="right")
    table.add_column("표면이자율", justify="right")
    table.add_column("방식")
    for b in report.bonds:
        table.add_row(
            b.bond_type,
            str(b.payment_date or b.resolution_date or "-"),
            str(b.maturity_date or "-"),
            fmt_amount(b.face_amount),
            f"{b.coupon_rate:.1f}%" if b.coupon_rate is not None else "-",
            b.issue_method,
        )
    console.print(table)


def _render_ownership(report: CompanyReport) -> None:
    if report.shareholders:
        table = Table(title="최대주주 및 특수관계인")
        table.add_column("이름")
        table.add_column("관계")
        table.add_column("종류")
        table.add_column("기초지분율", justify="right")
        table.add_column("기말지분율", justify="right")
        for s in report.shareholders:
            table.add_row(
                s.name, s.relation, s.stock_kind,
                f"{s.begin_ratio:.2f}%" if s.begin_ratio is not None else "-",
                f"{s.end_ratio:.2f}%" if s.end_ratio is not None else "-",
            )
        console.print(table)

    if report.ownership_changes:
        table2 = Table(title=f"5% 대량보유 변동 이력 (최근 {min(10, len(report.ownership_changes))}건)")
        table2.add_column("접수일")
        table2.add_column("보고자")
        table2.add_column("보유율", justify="right")
        table2.add_column("변동", justify="right")
        table2.add_column("사유")
        for c in report.ownership_changes[:10]:
            table2.add_row(
                c.rcept_dt, c.reporter,
                f"{c.stock_ratio:.2f}%" if c.stock_ratio is not None else "-",
                f"{c.stock_ratio_change:+.2f}%p" if c.stock_ratio_change is not None else "-",
                (c.reason or "-").replace("\n", " ")[:40],
            )
        console.print(table2)


def _render_affiliates(report: CompanyReport) -> None:
    if not report.affiliates:
        return
    top = sorted(
        (a for a in report.affiliates if a.ownership_ratio is not None),
        key=lambda a: -(a.ownership_ratio or 0),
    )[:10]
    table = Table(title=f"주요 계열/피투자회사 (전체 {len(report.affiliates)}개 중 지분율 상위 10)")
    table.add_column("회사명")
    table.add_column("지분율", justify="right")
    table.add_column("장부가액", justify="right")
    table.add_column("피투자사 순이익", justify="right")
    for a in top:
        table.add_row(
            a.name,
            f"{a.ownership_ratio:.1f}%" if a.ownership_ratio is not None else "-",
            fmt_amount(a.book_value),
            fmt_amount(a.investee_net_income),
        )
    console.print(table)


def _render_dividends(report: CompanyReport) -> None:
    if not report.dividends:
        return
    table = Table(title="배당 현황")
    table.add_column("구분")
    table.add_column("종류")
    table.add_column("당기")
    table.add_column("전기")
    table.add_column("전전기")
    for d in report.dividends:
        table.add_row(d.label, d.stock_kind, d.this_term, d.prev_term, d.before_prev_term)
    console.print(table)
