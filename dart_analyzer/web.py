from __future__ import annotations

import re

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse

from dart_analyzer.checklist import EARNINGS_AUTO_MAX, TECH_AUTO_MAX, build_checklist
from dart_analyzer.markdown_export import report_to_markdown
from dart_analyzer.recommend import build_recommendations
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
.topsearch{
  position:sticky;top:0;z-index:10;background:var(--bg);
  padding:10px 0 16px;margin:-32px 0 20px;border-bottom:1px solid var(--border);
}
.search-form.compact{margin-top:0}
.search-form.compact input[type=text]{width:200px;padding:8px 12px;font-size:13px}
.search-form.compact button{padding:8px 16px;font-size:13px}
.search-form.compact label{font-size:12px}
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

/* 체크리스트 */
.cl-section{margin-bottom:16px}
.cl-section-head{display:flex;justify-content:space-between;align-items:baseline;margin-bottom:8px}
.cl-section-head h3{font-size:14px;margin:0;color:var(--text)}
.cl-section-score{font-variant-numeric:tabular-nums;color:var(--muted);font-size:13px}
.cl-item{display:flex;align-items:center;gap:10px;padding:7px 0;border-bottom:1px solid var(--border);font-size:13px}
.cl-item:last-child{border-bottom:none}
.cl-item .cl-label{flex:1}
.cl-item .cl-auto-note{color:var(--muted);font-size:11.5px;display:block;margin-top:2px}
.cl-item input[type=number]{
  width:56px;background:#0d1117;border:1px solid var(--border);color:var(--text);
  border-radius:6px;padding:5px 6px;font-size:13px;text-align:center;
}
.cl-item input[type=number].auto{border-color:var(--ok)}
.cl-max{color:var(--muted);font-size:12px;width:36px}
.cl-total-bar{
  position:sticky;bottom:0;background:var(--panel);border:1px solid var(--border);border-radius:12px;
  padding:16px 20px;margin-top:20px;display:flex;align-items:center;gap:20px;flex-wrap:wrap;
}
.cl-total-num{font-size:34px;font-weight:800}
.cl-verdict{font-size:15px;font-weight:700;padding:6px 14px;border-radius:8px}
.pl-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin-top:10px}
.pl-field label{display:block;margin-bottom:4px}
.pl-field input[type=number]{width:100%;padding:8px 10px;font-size:13px}
.mandatory-list{display:flex;flex-direction:column;gap:8px;margin-top:12px}
.mandatory-list label{font-size:13px;color:var(--text)}
"""


def _search_bar_html(value: str = "", doc_search_checked: bool = False, compact: bool = False) -> str:
    checked = "checked" if doc_search_checked else ""
    extra_class = " compact" if compact else ""
    return f"""
    <form class="search-form{extra_class}" action="/analyze" method="get">
      <input type="text" name="q" placeholder="예: 삼성전자, 두산로보틱스, 005930" value="{value}" required>
      <label><input type="checkbox" name="doc_search" value="1" {checked}> 원문 키워드 검색 포함 (느림)</label>
      <button type="submit">조회</button>
    </form>
    """


def _grade_class(grade: str) -> str:
    return {"양호": "good", "보통": "ok", "주의": "warn", "위험": "bad"}.get(grade, "ok")


_GRADE_COLOR_VAR = {"good": "var(--good)", "ok": "var(--ok)", "warn": "var(--warn)", "bad": "var(--bad)"}


_FAVICON = (
    "data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22>"
    "<rect width=%22100%22 height=%22100%22 rx=%2222%22 fill=%22%238957e5%22/>"
    "<text x=%2250%22 y=%2270%22 font-size=%2258%22 text-anchor=%22middle%22>%F0%9F%93%8A</text></svg>"
)


def _page_shell(title: str, body: str) -> str:
    return (
        f"<html><head><title>{title}</title><link rel='icon' href=\"{_FAVICON}\">"
        f"<style>{_STYLE}</style></head>"
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
    body = f"""
    <h1>DART Analyzer</h1>
    <p style="color:var(--muted)">종목명 또는 종목코드로 재무·사채·지분·지배구조를 분석합니다.</p>
    <div class="card">
      {_search_bar_html()}
    </div>
    <p><a href="/recommend">&rarr; 오늘의 매수 후보 스크리너 (자동 채점 기준 Top 10)</a></p>
    """
    return _page_shell("DART Analyzer", body)


@app.get("/analyze", response_class=HTMLResponse)
def analyze(q: str = Query(..., description="종목명 또는 종목코드"), doc_search: bool = False) -> str:
    topsearch = f"<div class='topsearch'>{_search_bar_html(value=q, doc_search_checked=doc_search, compact=True)}</div>"

    try:
        report = build_report(q, doc_search=doc_search)
    except ValueError as e:
        body = f"{topsearch}<h1>DART Analyzer</h1><div class='card error'>오류: {e}</div>"
        return _page_shell("DART Analyzer", body)

    score = calculate_investment_score(report)
    corp = report.corp
    md = report_to_markdown(report)  # score는 별도 hero 카드로 렌더링하므로 여기선 제외
    md = "\n".join(md.splitlines()[1:])  # 첫 줄(# 회사명)은 topbar에서 이미 보여주므로 제외

    topbar = f"""
    {topsearch}
    <div class="topbar">
      <h1>{corp.corp_name} <span style="color:var(--muted);font-weight:400;font-size:16px">({corp.stock_code or corp.corp_code})</span></h1>
      <span class="badge {_grade_class(score.grade)}">{score.grade}</span>
    </div>
    <p><a href="/checklist?q={corp.stock_code or corp.corp_code}">&rarr; 매수 체크리스트(100점) 작성하기</a></p>
    """
    body = topbar + _score_hero_html(score) + _report_to_html(md)
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


def _checklist_section_html(section, idx: int) -> str:
    rows = []
    for item in section.items:
        is_auto = item.auto_score is not None
        val = round(item.auto_score, 1) if is_auto else 0
        cls = "auto" if is_auto else ""
        note = f"<span class='cl-auto-note'>{item.auto_note}</span>" if item.auto_note else (
            "<span class='cl-auto-note'>수동 입력</span>" if not is_auto else ""
        )
        rows.append(f"""
        <div class="cl-item">
          <div class="cl-label">{item.no}. {item.label}{note}</div>
          <input type="number" class="{cls} cl-input" data-max="{item.max_score}" min="0" max="{item.max_score}"
                 step="0.5" value="{val}" oninput="clRecalc()">
          <span class="cl-max">/{item.max_score:g}</span>
        </div>""")
    return f"""
    <div class="card cl-section">
      <div class="cl-section-head"><h3>{idx}. {section.name}</h3>
        <span class="cl-section-score">/ {section.max_score}</span></div>
      {''.join(rows)}
    </div>
    """


_CHECKLIST_JS = """
function clRecalc(){
  var sections = document.querySelectorAll('.cl-input');
  var total = 0;
  sections.forEach(function(inp){
    var v = parseFloat(inp.value)||0;
    var max = parseFloat(inp.dataset.max);
    if (v > max) { v = max; inp.value = max; }
    if (v < 0) { v = 0; inp.value = 0; }
    total += v;
  });

  var price = parseFloat(document.getElementById('pl-price').value) || 0;
  var target = parseFloat(document.getElementById('pl-target').value) || 0;
  var stop = parseFloat(document.getElementById('pl-stop').value) || 0;
  var profitPct = 0, lossPct = 0, ratio = 0;
  if (price > 0) {
    profitPct = (target - price) / price * 100;
    lossPct = (price - stop) / price * 100;
  }
  var plScore = 0;
  if (lossPct > 0) {
    ratio = profitPct / lossPct;
    if (ratio >= 3) plScore = 15;
    else if (ratio >= 2) plScore = 12;
    else if (ratio >= 1.5) plScore = 8;
    else if (ratio >= 1) plScore = 4;
    else plScore = 0;
  }
  document.getElementById('pl-profit').textContent = profitPct.toFixed(1) + '%';
  document.getElementById('pl-loss').textContent = lossPct.toFixed(1) + '%';
  document.getElementById('pl-ratio').textContent = ratio > 0 ? ratio.toFixed(2) : '-';
  document.getElementById('pl-score').textContent = plScore.toFixed(0) + ' / 15';
  document.getElementById('cond-a').checked = ratio >= 1.5;

  total += plScore;

  var grade = '매수 금지', cls='bad';
  if (total >= 85) { grade = '적극 매수 (5/5)'; cls='good'; }
  else if (total >= 80) { grade = '매수 (4/5)'; cls='good'; }
  else if (total >= 70) { grade = '분할매수 (3/5)'; cls='ok'; }
  else if (total >= 60) { grade = '관찰 (2/5)'; cls='warn'; }
  else if (total >= 50) { grade = '보류 (1/5)'; cls='warn'; }
  else { grade = '매수 금지 (0/5)'; cls='bad'; }

  var mandatory = ['cond-a','cond-b','cond-c','cond-d'].every(function(id){
    return document.getElementById(id).checked;
  });
  if (!mandatory) { grade = '매수 금지 (필수조건 미충족)'; cls='bad'; }

  document.getElementById('cl-total-num').textContent = total.toFixed(1);
  var verdictEl = document.getElementById('cl-verdict');
  verdictEl.textContent = grade;
  verdictEl.className = 'cl-verdict badge ' + cls;
}
window.addEventListener('DOMContentLoaded', clRecalc);
"""


@app.get("/checklist", response_class=HTMLResponse)
def checklist(q: str = Query(..., description="종목명 또는 종목코드")) -> str:
    topsearch = f"<div class='topsearch'>{_search_bar_html(value=q, compact=True)}</div>"
    try:
        report = build_report(q)
    except ValueError as e:
        body = f"{topsearch}<h1>DART Analyzer</h1><div class='card error'>오류: {e}</div>"
        return _page_shell("DART Analyzer", body)

    sections, ctx = build_checklist(q, dart_report=report)
    tech = ctx.get("tech") or {}
    current_price = tech.get("close_price") or ""

    corp = report.corp
    topbar = f"""
    {topsearch}
    <div class="topbar">
      <h1>{corp.corp_name} 매수 체크리스트 <span style="color:var(--muted);font-weight:400;font-size:16px">({corp.stock_code or corp.corp_code})</span></h1>
    </div>
    <p class="note">자동 채움(초록 테두리)은 참고용 근사치입니다 — 특히 업종·밸류에이션·시장 매크로 항목은 데이터가 없어 전부 직접 입력해야 합니다.
    {'스톡옵션pj 서버에 연결하지 못해 기술지표 자동 채움이 비활성화된 상태입니다.' if not tech else ''}</p>
    """

    sections_html = "".join(_checklist_section_html(s, i + 1) for i, s in enumerate(sections))

    pl_card = f"""
    <div class="card cl-section">
      <div class="cl-section-head"><h3>6. 매매가격·손익비</h3><span class="cl-section-score">/ 15</span></div>
      <div class="pl-grid">
        <div class="pl-field"><label>현재가</label><input type="number" id="pl-price" value="{current_price}" oninput="clRecalc()"></div>
        <div class="pl-field"><label>목표가</label><input type="number" id="pl-target" oninput="clRecalc()"></div>
        <div class="pl-field"><label>손절가</label><input type="number" id="pl-stop" oninput="clRecalc()"></div>
      </div>
      <div class="pl-grid" style="margin-top:14px">
        <div class="pl-field"><label>예상수익</label><b id="pl-profit">-</b></div>
        <div class="pl-field"><label>예상손실</label><b id="pl-loss">-</b></div>
        <div class="pl-field"><label>손익비</label><b id="pl-ratio">-</b></div>
        <div class="pl-field"><label>이 항목 점수</label><b id="pl-score">0 / 15</b></div>
      </div>
    </div>
    """

    mandatory_card = """
    <div class="card">
      <h3 style="margin-top:0;font-size:14px">필수조건 (하나라도 미충족이면 점수와 무관하게 매수 금지)</h3>
      <div class="mandatory-list">
        <label><input type="checkbox" id="cond-a" onchange="clRecalc()" disabled> A. 손익비 &ge; 1.5 (위에서 자동 판정)</label>
        <label><input type="checkbox" id="cond-b" onchange="clRecalc()"> B. 실적 악화가 심하지 않음</label>
        <label><input type="checkbox" id="cond-c" onchange="clRecalc()"> C. 시장·업종이 동시에 붕괴하고 있지 않음</label>
        <label><input type="checkbox" id="cond-d" onchange="clRecalc()"> D. 손절 기준이 명확함</label>
      </div>
    </div>
    """

    total_bar = """
    <div class="cl-total-bar">
      <div class="cl-total-num" id="cl-total-num">0</div>
      <div style="color:var(--muted);font-size:13px">/ 100</div>
      <span class="cl-verdict badge ok" id="cl-verdict">-</span>
    </div>
    """

    body = topbar + sections_html + pl_card + mandatory_card + total_bar + f"<script>{_CHECKLIST_JS}</script>"
    return _page_shell(f"{corp.corp_name} 체크리스트 - DART Analyzer", body)


@app.get("/recommend", response_class=HTMLResponse)
def recommend(top_n: int = 10, pool: int = 15) -> str:
    results, error = build_recommendations(top_n=top_n, fundamentals_pool=pool)

    body = f"""
    <div class="topbar">
      <h1>오늘의 매수 후보 스크리너</h1>
    </div>
    <p class="note">stock_option_pj 기술·수급 지표와 dart-analyzer 실적 지표만으로 기계적으로 채점한 결과입니다.
    업종·밸류에이션·시장 매크로·손익비는 자동 채점이 불가능해 빠져있으니 참고용으로만 보세요.
    기술점수 상위 {pool}개 중 실적까지 더해 재정렬한 Top {top_n}입니다.</p>
    """

    if error:
        body += f"<div class='card error'>{error}</div>"
        return _page_shell("매수 후보 스크리너 - DART Analyzer", body)

    rows = []
    for i, r in enumerate(results, start=1):
        e_score = f"{r.earnings_score:.1f}" if r.earnings_score is not None else "-"
        pct100 = round(r.combined_score / r.combined_max * 100) if r.combined_max else 0
        rows.append(f"""
        <tr>
          <td>{i}</td>
          <td><a href="/checklist?q={r.code}">{r.name}</a> <span style="color:var(--muted)">({r.code})</span></td>
          <td style="text-align:right">{r.tech_score:.1f} / {TECH_AUTO_MAX:.0f}</td>
          <td style="text-align:right">{e_score} / {EARNINGS_AUTO_MAX:.0f}</td>
          <td style="text-align:right"><b>{r.combined_score:.1f} / {r.combined_max:.0f}</b> <span style="color:var(--muted)">({pct100}점)</span></td>
          <td style="text-align:right">{r.close_price:,.0f}원 ({r.change_pct:+.1f}%)</td>
        </tr>""")

    body += f"""
    <table>
      <tr><th>순위</th><th>종목</th><th>기술·수급</th><th>실적</th><th>합산 (100점 환산)</th><th>현재가</th></tr>
      {''.join(rows)}
    </table>
    """
    return _page_shell("매수 후보 스크리너 - DART Analyzer", body)
