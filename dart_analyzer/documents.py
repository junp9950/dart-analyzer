from __future__ import annotations

import io
import re
import zipfile
from dataclasses import dataclass

import requests

from dart_analyzer.config import get_api_key

BASE_URL = "https://opendart.fss.or.kr/api"

DEFAULT_KEYWORDS = [
    "대여금",
    "대납",
    "신용공여",
    "지급보증",
    "자기주식",
    "교환사채",
    "전환사채",
    "특수관계자",
    "특수관계인",
    "제3자배정",
    "질권",
]

_TAG_RE = re.compile(rb"<[^>]+>")
_WS_RE = re.compile(r"\s+")


@dataclass
class DisclosureDoc:
    rcept_no: str
    report_name: str
    rcept_date: str


@dataclass
class KeywordHit:
    keyword: str
    context: str


def find_recent_reports(corp_code: str, bgn_de: str, end_de: str, pblntf_ty: str = "A") -> list[DisclosureDoc]:
    """공시검색으로 정기보고서(pblntf_ty=A: 정기공시) 목록 조회, 최신순."""
    api_key = get_api_key()
    resp = requests.get(
        f"{BASE_URL}/list.json",
        params={
            "crtfc_key": api_key,
            "corp_code": corp_code,
            "bgn_de": bgn_de,
            "end_de": end_de,
            "pblntf_ty": pblntf_ty,
            "page_count": 20,
        },
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("status") != "000":
        return []
    return [
        DisclosureDoc(rcept_no=row["rcept_no"], report_name=row["report_nm"], rcept_date=row["rcept_dt"])
        for row in data.get("list", [])
    ]


def _strip_tags_to_text(xml_bytes: bytes) -> str:
    text = _TAG_RE.sub(b" ", xml_bytes).decode("utf-8", errors="ignore")
    return _WS_RE.sub(" ", text)


def fetch_document_text(rcept_no: str) -> str:
    """공시서류 원본(zip 안의 XML들)을 전부 받아 태그를 제거한 순수 텍스트로 합쳐서 반환."""
    api_key = get_api_key()
    resp = requests.get(f"{BASE_URL}/document.xml", params={"crtfc_key": api_key, "rcept_no": rcept_no}, timeout=60)
    resp.raise_for_status()

    if resp.content[:2] != b"PK":
        raise RuntimeError(f"공시서류 원본을 가져오지 못했습니다: {resp.text[:300]}")

    texts = []
    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        for name in zf.namelist():
            texts.append(_strip_tags_to_text(zf.read(name)))
    return " ".join(texts)


def search_keywords(text: str, keywords: list[str] | None = None, context_chars: int = 60, max_hits_per_keyword: int = 5) -> list[KeywordHit]:
    """키워드별로 최대 max_hits_per_keyword개까지 주변 문맥을 잘라서 반환."""
    keywords = keywords or DEFAULT_KEYWORDS
    hits: list[KeywordHit] = []
    for kw in keywords:
        count = 0
        start = 0
        while count < max_hits_per_keyword:
            idx = text.find(kw, start)
            if idx == -1:
                break
            lo = max(0, idx - context_chars)
            hi = min(len(text), idx + len(kw) + context_chars)
            snippet = text[lo:hi].strip()
            hits.append(KeywordHit(keyword=kw, context=f"...{snippet}..."))
            start = idx + len(kw)
            count += 1
    return hits
