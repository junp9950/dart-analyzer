from __future__ import annotations

import re

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse

from dart_analyzer.markdown_export import report_to_markdown
from dart_analyzer.report import build_report
from dart_analyzer.scoring import calculate_investment_score

app = FastAPI(title="DART Analyzer")

_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
_ITALIC_RE = re.compile(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)")


def _inline_md(text: str) -> str:
    text = _BOLD_RE.sub(r"<b>\1</b>", text)
    text = _ITALIC_RE.sub(r"<i>\1</i>", text)
    return text


def _report_to_html(md: str) -> str:
    # 아주 단순한 마크다운 -> HTML 변환 (외부 라이브러리 없이)
    parts: list[str] = []
    in_table = False
    is_header_row = False
    for line in md.splitlines():
        if line.startswith("# "):
            parts.append(f"<h1>{line[2:]}</h1>")
        elif line.startswith("## "):
            if in_table:
                parts.append("</table>")
                in_table = False
            parts.append(f"<h2>{line[3:]}</h2>")
        elif line.startswith("|"):
            cells = [c.strip() for c in line.strip("|").split("|")]
            if set(cells[0]) <= {"-"}:  # 구분선(|---|---|) 행은 건너뛰되, 다음 행부터는 데이터 행
                is_header_row = False
                continue
            if not in_table:
                parts.append("<table border=1 cellpadding=6 style='border-collapse:collapse'>")
                in_table = True
                is_header_row = True
            tag = "th" if is_header_row else "td"
            parts.append("<tr>" + "".join(f"<{tag}>{_inline_md(c)}</{tag}>" for c in cells) + "</tr>")
        elif line.strip():
            if in_table:
                parts.append("</table>")
                in_table = False
            parts.append(f"<p>{_inline_md(line.strip())}</p>")
        else:
            if in_table:
                parts.append("</table>")
                in_table = False
    if in_table:
        parts.append("</table>")
    return "".join(parts)


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return """
    <html><body style="font-family:sans-serif;max-width:700px;margin:40px auto">
    <h2>DART Analyzer</h2>
    <form action="/analyze" method="get">
      <input name="q" placeholder="종목명 또는 종목코드" style="padding:8px;width:250px">
      <label style="margin-left:8px"><input type="checkbox" name="doc_search" value="1"> 원문 키워드 검색 포함(느림)</label>
      <button type="submit" style="padding:8px 16px">조회</button>
    </form>
    </body></html>
    """


@app.get("/analyze", response_class=HTMLResponse)
def analyze(q: str = Query(..., description="종목명 또는 종목코드"), doc_search: bool = False) -> str:
    try:
        report = build_report(q, doc_search=doc_search)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    score = calculate_investment_score(report)
    md = report_to_markdown(report, score=score)
    return f"<html><body style='font-family:sans-serif;max-width:900px;margin:40px auto'>{_report_to_html(md)}<p><a href='/'>다시 조회</a></p></body></html>"


@app.get("/api/analyze")
def analyze_json(q: str = Query(...), doc_search: bool = False):
    try:
        report = build_report(q, doc_search=doc_search)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    score = calculate_investment_score(report)
    return {
        "corp_name": report.corp.corp_name,
        "stock_code": report.corp.stock_code,
        "score": {
            "total": score.total,
            "grade": score.grade,
            "note": "통계적으로 검증된 수익률 예측 점수가 아니라 규칙 기반 리스크 스크리닝 참고용입니다.",
            "categories": [
                {
                    "name": c.name,
                    "score": c.score,
                    "max_score": c.max_score,
                    "reasons": [r.reason for r in c.reasons],
                }
                for c in score.categories
            ],
        },
        "financials": [
            {"year": s.bsns_year, "values": s.values, "debt_ratio": s.debt_ratio} for s in report.financials
        ],
        "bonds": [
            {
                "type": b.bond_type,
                "payment_date": str(b.payment_date) if b.payment_date else None,
                "maturity_date": str(b.maturity_date) if b.maturity_date else None,
                "face_amount": b.face_amount,
                "coupon_rate": b.coupon_rate,
                "issue_method": b.issue_method,
            }
            for b in report.bonds
        ],
        "shareholders": [
            {"name": s.name, "relation": s.relation, "end_ratio": s.end_ratio} for s in report.shareholders
        ],
        "audit_opinions": [
            {"period": o.period_label, "auditor": o.auditor, "opinion": o.opinion, "emphasis": o.emphasis_matter}
            for o in report.audit_opinions
        ],
        "auditor_changes": report.auditor_changes,
        "litigations": [
            {"filed_date": str(l.filed_date) if l.filed_date else None, "case_name": l.case_name, "court": l.court}
            for l in report.litigations
        ],
        "keyword_hits": [{"keyword": h.keyword, "context": h.context} for h in report.keyword_hits],
    }
