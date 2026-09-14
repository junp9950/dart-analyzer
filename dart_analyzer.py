from __future__ import annotations

import argparse
import sys

from dart_analyzer.display import console, render_report
from dart_analyzer.markdown_export import report_to_markdown
from dart_analyzer.report import build_report


def main() -> None:
    parser = argparse.ArgumentParser(description="OpenDART 공시 분석 CLI")
    parser.add_argument("companies", nargs="*", help="종목명 또는 종목코드")
    parser.add_argument("--compare", nargs="+", metavar="종목", help="여러 종목을 나란히 비교")
    parser.add_argument("--bonds-only", action="store_true", help="사채 발행 이력만 조회")
    parser.add_argument("--markdown", metavar="FILE", help="마크다운 리포트로 저장")
    parser.add_argument("--years", type=int, default=5, help="사채 조회 기간(년), 기본 5년")
    parser.add_argument(
        "--doc-search", action="store_true",
        help="최근 정기보고서 원문에서 대여금/특수관계자 등 키워드 문맥 검색 (원문이 커서 느릴 수 있음)",
    )
    args = parser.parse_args()

    targets = args.compare or args.companies
    if not targets:
        parser.print_help()
        sys.exit(1)

    reports = []
    for query in targets:
        try:
            report = build_report(
                query, years_back=args.years, bonds_only=args.bonds_only, doc_search=args.doc_search
            )
        except ValueError as e:
            console.print(f"[red]오류:[/red] {e}")
            continue
        reports.append(report)
        render_report(report, bonds_only=args.bonds_only)

    if args.markdown and reports:
        md = "\n\n---\n\n".join(report_to_markdown(r, bonds_only=args.bonds_only) for r in reports)
        with open(args.markdown, "w", encoding="utf-8") as f:
            f.write(md)
        console.print(f"[green]마크다운 리포트 저장됨: {args.markdown}[/green]")


if __name__ == "__main__":
    main()
