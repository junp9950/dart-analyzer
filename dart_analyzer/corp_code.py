from __future__ import annotations

import io
import time
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass

import requests

from dart_analyzer.config import CACHE_DIR, get_api_key

CORP_CODE_URL = "https://opendart.fss.or.kr/api/corpCode.xml"
CACHE_FILE = CACHE_DIR / "corpCode.xml"
CACHE_MAX_AGE_SECONDS = 7 * 24 * 3600  # 1주일


@dataclass
class Corp:
    corp_code: str
    corp_name: str
    stock_code: str  # 상장사가 아니면 빈 문자열
    modify_date: str


def _is_cache_fresh() -> bool:
    if not CACHE_FILE.exists():
        return False
    age = time.time() - CACHE_FILE.stat().st_mtime
    return age < CACHE_MAX_AGE_SECONDS


def _download_corp_code_xml() -> bytes:
    api_key = get_api_key()
    resp = requests.get(CORP_CODE_URL, params={"crtfc_key": api_key}, timeout=30)
    resp.raise_for_status()

    content_type = resp.headers.get("Content-Type", "")
    if "xml" in content_type and b"PK" not in resp.content[:2]:
        # zip이 아니라 에러 XML을 바로 반환한 경우 (키 오류 등)
        raise RuntimeError(f"OpenDART corpCode 요청 실패: {resp.text[:500]}")

    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        names = zf.namelist()
        xml_name = next((n for n in names if n.lower().endswith(".xml")), None)
        if xml_name is None:
            raise RuntimeError(f"corpCode.zip 안에 XML 파일이 없습니다: {names}")
        return zf.read(xml_name)


def _load_corp_code_xml(force_refresh: bool = False) -> bytes:
    if not force_refresh and _is_cache_fresh():
        return CACHE_FILE.read_bytes()

    data = _download_corp_code_xml()
    CACHE_FILE.write_bytes(data)
    return data


def _parse_corp_code_xml(data: bytes) -> list[Corp]:
    root = ET.fromstring(data)
    corps: list[Corp] = []
    for node in root.findall("list"):
        corp_code = (node.findtext("corp_code") or "").strip()
        corp_name = (node.findtext("corp_name") or "").strip()
        stock_code = (node.findtext("stock_code") or "").strip()
        modify_date = (node.findtext("modify_date") or "").strip()
        corps.append(Corp(corp_code, corp_name, stock_code, modify_date))
    return corps


_CORPS_CACHE: list[Corp] | None = None


def load_all_corps(force_refresh: bool = False) -> list[Corp]:
    global _CORPS_CACHE
    if _CORPS_CACHE is not None and not force_refresh:
        return _CORPS_CACHE
    data = _load_corp_code_xml(force_refresh=force_refresh)
    _CORPS_CACHE = _parse_corp_code_xml(data)
    return _CORPS_CACHE


def find_corp(query: str) -> Corp:
    """종목명(정확히 일치, 없으면 부분 일치) 또는 종목코드로 상장사를 찾는다.

    여러 개 일치하면 상장사(stock_code 존재)를 우선하고, 그래도 여러 개면
    ValueError로 후보 목록을 보여준다.
    """
    query = query.strip()
    corps = load_all_corps()

    if query.isdigit() and len(query) == 6:
        matches = [c for c in corps if c.stock_code == query]
        if matches:
            return matches[0]
        raise ValueError(f"종목코드 '{query}'에 해당하는 회사를 찾을 수 없습니다.")

    exact = [c for c in corps if c.corp_name == query]
    listed_exact = [c for c in exact if c.stock_code]
    if listed_exact:
        return listed_exact[0]
    if exact:
        return exact[0]

    partial = [c for c in corps if query in c.corp_name]
    listed_partial = [c for c in partial if c.stock_code]
    candidates = listed_partial or partial

    if not candidates:
        raise ValueError(f"'{query}'와(과) 일치하는 회사를 찾을 수 없습니다.")
    if len(candidates) == 1:
        return candidates[0]

    names = ", ".join(f"{c.corp_name}({c.stock_code or '비상장'})" for c in candidates[:15])
    raise ValueError(
        f"'{query}'에 일치하는 회사가 여러 개입니다 ({len(candidates)}개). "
        f"더 정확한 이름이나 종목코드를 입력하세요: {names}"
    )
