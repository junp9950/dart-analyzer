from __future__ import annotations

import re

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse

from dart_analyzer.markdown_export import report_to_markdown
from dart_analyzer.report import build_report
from dart_analyzer.scoring import InvestmentScore, calculate_investment_score

app = FastAPI(title="DART Analyzer")

_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
_ITALIC_RE = re.compile(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)")

_STYLE = """
:root{
  --bg:#0d1117; --panel:#161b22; --border:#30363d; --text:#e6edf3; --muted:#8b949e;
  --accent:#58a6ff; --good:#3fb950; --ok:#58a6ff; --warn:#d29922; --bad:#f85149;
}
*{box-sizing:border-box}
body{
  background:var(--bg); color:var(--text); margin:0; padding:32px 16px;
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Pretendard,Roboto,sans-serif;
  line-height:1.55;
}
.container{max-width:920px;margin:0 auto}
h1{font-size:26px;margin:0 0 4px}
h2{font-size:16px;color:var(--muted);text-transform:uppercase;letter-spacing:.04em;
   margin:28px 0 10px;padding-bottom:6px;border-bottom:1px solid var(--border)}
p{color:var(--text);margin:6px 0}
p i{color:var(--muted);font-style:normal;font-size:13px}
a{color:var(--accent);text-decoration:none}
a:hover{text-decoration:underline}
.card{background:var(--panel);border:1px solid var(--border);border-radius:12px;padding:20px 24px;margin-bottom:16px}
table{width:100%;border-collapse:collapse;font-size:13.5px;background:var(--panel);
      border:1px solid var(--border);border-radius:10px;overflow:hidden}
th,td{padding:9px 12px;text-align:left;border-bottom:1px solid var(--border)}
th{background:#1c2129;color:var(--muted);font-weight:600;font-size:12px;text-transform:uppercase;letter-spacing:.03em}
tr:last-child td{border-bottom:none}
tr:hover td{background:#1b212a}
.topbar{display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:12px;margin-bottom:8px}
.badge{display:inline-block;padding:3px 10px;border-radius:999px;font-size:12px;font-weight:600}
.badge.good{background:rgba(63,185,80,.15);color:var(--good)}
.badge.ok{background:rgba(88,166,255,.15);color:var(--ok)}
.badge.warn{background:rgba(210,153,34,.15);color:var(--warn)}
.badge.bad{background:rgba(248,81,73,.15);color:var(--bad)}
.score-hero{display:flex;align-items:center;gap:24px;flex-wrap:wrap}
.score-num{font-size:52px;font-weight:800;line-height:1}
.score-num sub{font-size:18px;font-weight:500;color:var(--muted)}
.score-cats{flex:1;min-width:260px;display:flex;flex-direction:column;gap:8px}
.cat-row{display:flex;align-items:center;gap:10px;font-size:13px}
.cat-name{width:150px;flex-shrink:0;color:var(--muted)}
.cat-bar{flex:1;height:8px;background:#1c2129;border-radius:4px;overflow:hidden}
.cat-fill{height:100%;border-radius:4px}
.cat-val{width:56px;text-align:right;flex-shrink:0;color:var(--text);font-variant-numeric:tabular-nums}
.reasons{margin-top:16px;display:flex;flex-direction:column;gap:6px}
.reason-line{font-size:13px;color:var(--muted);padding-left:14px;border-left:2px solid var(--border)}
.reason-line b{color:var(--text);font-weight:600}
.search-form{display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin-top:16px}
input[type=text]{
  background:#0d1117;border:1px solid var(--border);color:var(--text);border-radius:8px;
  padding:10px 14px;font-size:14px;width:260px;
}
input[type=text]:focus{outline:none;border-color:var(--accent)}
button{
  background:var(--accent);color:#0d1117;border:none;border-radius:8px;padding:10px 20px;
  font-size:14px;font-weight:600;cursor:pointer;
}
button:hover{opacity:.9}
label{font-size:13px;color:var(--muted);display:flex;align-items:center;gap:6px}
.note{color:var(--muted);font-size:12px;margin-top:8px}
.error{color:var(--bad);font-size:14px}
"""


def _grade_class(grade: str) -> str:
    return {"양호": "good", "보통": "ok", "주의": "warn", "위험": "bad"}.get(grade, "ok")


_GRADE_COLOR_VAR = {"good": "var(--good)", "ok": "var(--ok)", "warn": "var(--warn)", "bad": "var(--bad)"}


def _page_shell(title: str, body: str) -> str:
    return (
        f"<html><head><title>{title}</title><style>{_STYLE}</style></head>"
        f"<body><div class='container'>{body}</div></body></html>"
    )


def _score_hero_html(score: InvestmentScore) -> str:
    cls = _grade_class(score.grade)
    cat_rows = []
    reason_lines = []
    for cat in score.categories:
        pct = 0 if cat.max_score == 0 else round(cat.score / cat.max_score * 100)
        cat_pct_of_max = 0 if cat.max_score == 0 else cat.score / cat.max_score
        cat_cls = "good" if cat_pct_of_max >= 0.8 else "ok" if cat_pct_of_max >= 0.6 else "warn" if cat_pct_of_max >= 0.4 else "bad"
        cat_rows.append(
            f"<div class='cat-row'><div class='cat-name'>{cat.name}</div>"
            f"<div class='cat-bar'><div class='cat-fill' style='width:{pct}%;background:{_GRADE_COLOR_VAR[cat_cls]}'></div></div>"
            f"<div class='cat-val'>{cat.score:.0f} / {cat.max_score:.0f}</div></div>"
        )
        for r in cat.reasons:
            reason_lines.append(f"<div class='reason-line'><b>[{cat.name}]</b> {r.reason}</div>")

    return f"""
    <div class="card">
      <div class="score-hero">
        <div class="score-num badge {cls}">{score.total:.0f}<sub>/100</sub></div>
        <div class="score-cats">
          <div class="badge {cls}" style="width:fit-content;margin-bottom:4px">{score.grade}</div>
          {''.join(cat_rows)}
        </div>
      </div>
      <div class="reasons">{''.join(reason_lines)}</div>
      <p class="note">통계적으로 검증된 수익률 예측 점수가 아니라, 규칙 기반 리스크 스크리닝 참고용입니다.</p>
    </div>
    """


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
                parts.append("<table>")
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
    body = """
    <h1>DART Analyzer</h1>
    <p style="color:var(--muted)">종목명 또는 종목코드로 재무·사채·지분·지배구조를 분석합니다.</p>
    <div class="card">
      <form class="search-form" action="/analyze" method="get">
        <input type="text" name="q" placeholder="예: 삼성전자, 두산로보틱스, 005930" required>
        <label><input type="checkbox" name="doc_search" value="1"> 원문 키워드 검색 포함 (느림)</label>
        <button type="submit">조회</button>
      </form>
    </div>
    """
    return _page_shell("DART Analyzer", body)


@app.get("/analyze", response_class=HTMLResponse)
def analyze(q: str = Query(..., description="종목명 또는 종목코드"), doc_search: bool = False) -> str:
    try:
        report = build_report(q, doc_search=doc_search)
    except ValueError as e:
        body = f"<h1>DART Analyzer</h1><div class='card error'>오류: {e}</div><p><a href='/'>다시 조회</a></p>"
        return _page_shell("DART Analyzer", body)

    score = calculate_investment_score(report)
    corp = report.corp
    md = report_to_markdown(report)  # score는 별도 hero 카드로 렌더링하므로 여기선 제외
    md = "\n".join(md.splitlines()[1:])  # 첫 줄(# 회사명)은 topbar에서 이미 보여주므로 제외

    topbar = f"""
    <div class="topbar">
      <h1>{corp.corp_name} <span style="color:var(--muted);font-weight:400;font-size:16px">({corp.stock_code or corp.corp_code})</span></h1>
      <span class="badge {_grade_class(score.grade)}">{score.grade}</span>
    </div>
    """
    body = topbar + _score_hero_html(score) + _report_to_html(md) + "<p><a href='/'>&larr; 다시 조회</a></p>"
    return _page_shell(f"{corp.corp_name} - DART Analyzer", body)


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
