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
        _render_governance(report)
        _render_keyword_hits(report)


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
    table.add_column("발행전 10일", justify="right")
    table.add_column("발행후 10일", justify="right")
    for b in report.bonds:
        table.add_row(
            b.bond_type,
            str(b.payment_date or b.resolution_date or "-"),
            str(b.maturity_date or "-"),
            fmt_amount(b.face_amount),
            f"{b.coupon_rate:.1f}%" if b.coupon_rate is not None else "-",
            b.issue_method,
            f"{b.price_change_before_pct:+.1f}%" if b.price_change_before_pct is not None else "-",
            f"{b.price_change_after_pct:+.1f}%" if b.price_change_after_pct is not None else "-",
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


def _render_governance(report: CompanyReport) -> None:
    if report.audit_opinions:
        table = Table(title="감사의견 및 강조사항")
        table.add_column("기수")
        table.add_column("감사인")
        table.add_column("의견")
        table.add_column("강조사항")
        table.add_column("핵심감사사항")
        for o in report.audit_opinions:
            table.add_row(o.period_label, o.auditor, o.opinion, o.emphasis_matter, o.core_audit_matter)
        console.print(table)
        if report.auditor_changes:
            console.print(f"[yellow]감사인 변경 이력:[/yellow] {'; '.join(report.auditor_changes)}")

    if report.capital_increases:
        table2 = Table(title=f"유상증자 결정 이력 ({len(report.capital_increases)}건)")
        table2.add_column("방식")
        table2.add_column("신주 수", justify="right")
        table2.add_column("운영자금 목적")
        table2.add_column("채무상환 목적")
        for c in report.capital_increases:
            table2.add_row(
                c.method,
                f"{c.new_shares:,.0f}" if c.new_shares is not None else "-",
                c.purpose_operation,
                c.purpose_debt_repayment,
            )
        console.print(table2)

    if report.litigations:
        table3 = Table(title=f"소송 등의 제기 ({len(report.litigations)}건)")
        table3.add_column("제기일")
        table3.add_column("사건명")
        table3.add_column("법원")
        table3.add_column("원고/신청인")
        for l in report.litigations:
            table3.add_row(str(l.filed_date or "-"), l.case_name, l.court, l.plaintiff)
        console.print(table3)


def _render_keyword_hits(report: CompanyReport) -> None:
    if not report.keyword_hits:
        return
    table = Table(title=f"원문 키워드 검색 결과 ({report.keyword_source_report})")
    table.add_column("키워드")
    table.add_column("문맥")
    for h in report.keyword_hits:
        table.add_row(h.keyword, h.context)
    console.print(table)


def render_investment_score(score) -> None:  # score: InvestmentScore (지연 import로 순환참조 회피)
    grade_color = {"양호": "green", "보통": "cyan", "주의": "yellow", "위험": "red"}.get(score.grade, "white")
    console.print(
        f"\n[bold]종합 스크리닝 점수: [{grade_color}]{score.total:.1f} / 100 ({score.grade})[/{grade_color}][/bold]"
        f"  [dim](통계적으로 검증된 수익률 예측 점수가 아니라, 규칙 기반 리스크 스크리닝 참고용입니다)[/dim]"
    )
    table = Table(title="항목별 점수")
    table.add_column("항목")
    table.add_column("점수", justify="right")
    table.add_column("사유")
    for cat in score.categories:
        reason_text = " / ".join(r.reason for r in cat.reasons)
        table.add_row(cat.name, f"{cat.score:.0f} / {cat.max_score:.0f}", reason_text)
    console.print(table)
