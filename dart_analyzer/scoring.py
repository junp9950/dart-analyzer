from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

from dart_analyzer.report import CompanyReport

# 규칙 기반 리스크 스크리닝 점수 — 실제 수익률로 백테스트 검증된 값이 아니라
# "이런 신호가 있으면 위험 신호로 본다"는 상식적 규칙의 가중치일 뿐이다.
# 참고용 스크리닝 도구로만 쓸 것.

CATEGORY_MAX = {
    "재무 건전성": 30,
    "자금조달 건전성": 25,
    "감사/회계 신뢰성": 20,
    "지배구조 리스크": 15,
    "주주환원/안정성": 10,
}


@dataclass
class ScoreReason:
    delta: float  # 음수면 감점, 양수면 특이사항 없음(0)도 표기
    reason: str


@dataclass
class CategoryScore:
    name: str
    max_score: float
    score: float
    reasons: list[ScoreReason] = field(default_factory=list)


@dataclass
class InvestmentScore:
    total: float
    categories: list[CategoryScore]

    @property
    def grade(self) -> str:
        if self.total >= 80:
            return "양호"
        if self.total >= 60:
            return "보통"
        if self.total >= 40:
            return "주의"
        return "위험"


def _score_financial_health(report: CompanyReport) -> CategoryScore:
    max_score = CATEGORY_MAX["재무 건전성"]
    score = max_score
    reasons: list[ScoreReason] = []

    snaps = report.financials
    if not snaps:
        reasons.append(ScoreReason(0, "재무 데이터 없음 — 평가 불가, 만점 유지"))
        return CategoryScore("재무 건전성", max_score, score, reasons)

    latest = snaps[-1]
    if latest.debt_ratio is not None:
        if latest.debt_ratio > 300:
            score -= 12
            reasons.append(ScoreReason(-12, f"부채비율 {latest.debt_ratio:.0f}% (300% 초과, 매우 높음)"))
        elif latest.debt_ratio > 200:
            score -= 8
            reasons.append(ScoreReason(-8, f"부채비율 {latest.debt_ratio:.0f}% (200% 초과)"))
        elif latest.debt_ratio > 150:
            score -= 4
            reasons.append(ScoreReason(-4, f"부채비율 {latest.debt_ratio:.0f}% (150% 초과)"))

    # 최근 2개년 연속 당기순손실
    loss_years = [s for s in snaps[-2:] if s.values.get("net_income") is not None and s.values["net_income"] < 0]
    if len(loss_years) >= 2:
        score -= 10
        reasons.append(ScoreReason(-10, "최근 2개년 연속 당기순손실"))
    elif len(loss_years) == 1 and snaps[-1] is loss_years[-1]:
        score -= 5
        reasons.append(ScoreReason(-5, "최근 연도 당기순손실"))

    # 이익잉여금 추세 (2개년 이상 있을 때)
    re_vals = [s.values.get("retained_earnings") for s in snaps if s.values.get("retained_earnings") is not None]
    if len(re_vals) >= 2 and re_vals[-1] < re_vals[0]:
        score -= 8
        reasons.append(ScoreReason(-8, "이익잉여금이 감소 추세"))
    if re_vals and re_vals[-1] < 0:
        score -= 10
        reasons.append(ScoreReason(-10, "이익잉여금 잠식(결손금) 상태"))

    score = max(0, score)
    if not reasons:
        reasons.append(ScoreReason(0, "특이사항 없음"))
    return CategoryScore("재무 건전성", max_score, score, reasons)


def _score_funding_health(report: CompanyReport) -> CategoryScore:
    max_score = CATEGORY_MAX["자금조달 건전성"]
    score = max_score
    reasons: list[ScoreReason] = []

    recent_cutoff = date.today() - timedelta(days=365 * 2)
    recent_bonds = [
        b for b in report.bonds
        if (b.payment_date or b.resolution_date) and (b.payment_date or b.resolution_date) >= recent_cutoff
    ]
    private_bonds = [b for b in recent_bonds if b.issue_method == "사모"]

    if len(private_bonds) >= 3:
        score -= 15
        reasons.append(ScoreReason(-15, f"최근 2년간 사모 CB/BW/EB {len(private_bonds)}건 (잦은 사모 자금조달)"))
    elif len(private_bonds) >= 1:
        score -= 7
        reasons.append(ScoreReason(-7, f"최근 2년간 사모 CB/BW/EB {len(private_bonds)}건"))

    drop_on_issue = [b for b in recent_bonds if b.price_change_before_pct is not None and b.price_change_before_pct < -5]
    if drop_on_issue:
        score -= 5
        reasons.append(ScoreReason(-5, f"주가 약세 구간(발행전 10일 -5% 이상)에 발행된 사채 {len(drop_on_issue)}건"))

    recent_caps = [c for c in report.capital_increases]  # 이미 build_report에서 조회기간이 years_back으로 제한됨
    third_party = [c for c in recent_caps if "제3자배정" in c.method]
    if len(third_party) >= 2:
        score -= 10
        reasons.append(ScoreReason(-10, f"제3자배정 유상증자 {len(third_party)}건 (반복적 제3자배정)"))
    elif len(third_party) == 1:
        score -= 4
        reasons.append(ScoreReason(-4, "제3자배정 유상증자 이력 있음"))

    score = max(0, score)
    if not reasons:
        reasons.append(ScoreReason(0, "특이사항 없음"))
    return CategoryScore("자금조달 건전성", max_score, score, reasons)


def _score_audit_trust(report: CompanyReport) -> CategoryScore:
    max_score = CATEGORY_MAX["감사/회계 신뢰성"]
    score = max_score
    reasons: list[ScoreReason] = []

    if not report.audit_opinions:
        reasons.append(ScoreReason(0, "감사의견 데이터 없음 — 평가 불가, 만점 유지"))
        return CategoryScore("감사/회계 신뢰성", max_score, score, reasons)

    latest = report.audit_opinions[0]
    if latest.opinion != "적정의견":
        score -= 15
        reasons.append(ScoreReason(-15, f"최근 감사의견이 '{latest.opinion}' (적정의견 아님)"))

    if latest.emphasis_matter and latest.emphasis_matter != "-":
        is_going_concern = "계속기업" in latest.emphasis_matter
        penalty = 10 if is_going_concern else 4
        score -= penalty
        reasons.append(ScoreReason(-penalty, f"강조사항 존재: {latest.emphasis_matter[:60]}"))

    if report.auditor_changes:
        score -= 5
        reasons.append(ScoreReason(-5, f"최근 감사인 변경 이력: {report.auditor_changes[-1]}"))

    score = max(0, score)
    if not reasons:
        reasons.append(ScoreReason(0, "적정의견, 강조사항 없음, 감사인 변경 없음"))
    return CategoryScore("감사/회계 신뢰성", max_score, score, reasons)


_OWNER_RISK_KEYWORDS = ["신주발행무효", "가처분", "이사회 결의", "경영권", "배임", "횡령"]


def _score_governance_risk(report: CompanyReport) -> CategoryScore:
    max_score = CATEGORY_MAX["지배구조 리스크"]
    score = max_score
    reasons: list[ScoreReason] = []

    owner_related = [
        l for l in report.litigations
        if any(kw in (l.case_name + l.summary) for kw in _OWNER_RISK_KEYWORDS)
    ]
    other_litigations = [l for l in report.litigations if l not in owner_related]

    if owner_related:
        score -= 15
        reasons.append(ScoreReason(-15, f"경영권/오너 리스크 관련 소송 {len(owner_related)}건 (예: {owner_related[0].case_name})"))
    if other_litigations:
        score -= min(5, len(other_litigations) * 2)
        reasons.append(ScoreReason(-min(5, len(other_litigations) * 2), f"기타 소송 {len(other_litigations)}건"))

    hit_keywords = {h.keyword for h in report.keyword_hits}
    risky_kw = hit_keywords & {"대여금", "대납", "지급보증", "신용공여", "질권"}
    if risky_kw:
        score -= min(8, len(risky_kw) * 3)
        reasons.append(ScoreReason(-min(8, len(risky_kw) * 3), f"원문에서 발견된 위험 키워드: {', '.join(sorted(risky_kw))}"))

    score = max(0, score)
    if not reasons:
        reasons.append(ScoreReason(0, "특이사항 없음"))
    return CategoryScore("지배구조 리스크", max_score, score, reasons)


def _score_shareholder_return(report: CompanyReport) -> CategoryScore:
    max_score = CATEGORY_MAX["주주환원/안정성"]
    score = max_score
    reasons: list[ScoreReason] = []

    has_dividend = any(
        d.label == "주당 현금배당금(원)" and d.this_term not in ("-", "0", "", None)
        for d in report.dividends
    )
    if not has_dividend:
        score -= 5
        reasons.append(ScoreReason(-5, "당기 배당 미실시 (성장주는 정상일 수 있음)"))

    controller = next((s for s in report.shareholders if "본인" in s.relation), None)
    if controller and controller.end_ratio is not None and controller.end_ratio < 10:
        score -= 5
        reasons.append(ScoreReason(-5, f"최대주주 지분율 {controller.end_ratio:.1f}% (10% 미만, 경영권 안정성 낮음)"))

    score = max(0, score)
    if not reasons:
        reasons.append(ScoreReason(0, "특이사항 없음"))
    return CategoryScore("주주환원/안정성", max_score, score, reasons)


def calculate_investment_score(report: CompanyReport) -> InvestmentScore:
    categories = [
        _score_financial_health(report),
        _score_funding_health(report),
        _score_audit_trust(report),
        _score_governance_risk(report),
        _score_shareholder_return(report),
    ]
    total = round(sum(c.score for c in categories), 1)
    return InvestmentScore(total=total, categories=categories)
