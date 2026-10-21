"""표 읽기 — CSV(UTF-8 · UTF-8 BOM · CP949 자동)와 XLSX(openpyxl 있을 때).

Reading tables. CSV encodings are detected (UTF-8, UTF-8 with BOM, CP949).
XLSX needs the optional `openpyxl` package.
"""
from __future__ import annotations

import csv
import io
import os
from typing import Dict, List

ENCODINGS = ("utf-8-sig", "utf-8", "cp949")


def _read_text(path: str) -> str:
    with open(path, "rb") as f:
        raw = f.read()
    for enc in ENCODINGS:
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    raise ValueError(f"인코딩을 알 수 없습니다 / unknown encoding: {path}")


def load_table(path: str, sheet: str | None = None) -> List[Dict[str, str]]:
    """CSV/TSV/XLSX를 dict 목록으로 읽는다. Load a table as a list of dicts."""
    ext = os.path.splitext(path)[1].lower()
    if ext in (".xlsx", ".xlsm"):
        try:
            import openpyxl  # type: ignore
        except ImportError as e:  # pragma: no cover
            raise RuntimeError("XLSX를 읽으려면 openpyxl이 필요합니다: pip install openpyxl") from e
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        ws = wb[sheet] if sheet else wb.worksheets[0]
        ws.reset_dimensions()  # dimension 정보가 빈 파일도 끝까지 읽는다
        rows = ws.iter_rows(values_only=True)
        header = None
        for r in rows:
            if r and any(c is not None for c in r):
                header = [str(c).strip() if c is not None else f"col{i}" for i, c in enumerate(r)]
                break
        if header is None:
            return []
        out = []
        for r in rows:
            if not r or all(c is None for c in r):
                continue
            out.append({h: ("" if v is None else str(v)) for h, v in zip(header, r)})
        return out
    text = _read_text(path)
    delim = "\t" if ext in (".tsv", ".tab") else ","
    return list(csv.DictReader(io.StringIO(text), delimiter=delim))


def columns(path: str) -> Dict[str, object]:
    """열 이름과 행 수만 돌려준다 — 값(원문)은 돌려주지 않는다.
    Column names and row count only. Cell values are never returned."""
    rows = load_table(path)
    cols = list(rows[0].keys()) if rows else []
    filled = {c: sum(1 for r in rows if str(r.get(c, "")).strip()) for c in cols}
    avg_len = {c: round(sum(len(str(r.get(c, ""))) for r in rows) / max(1, len(rows)), 1) for c in cols}
    distinct = {c: len({r.get(c, "") for r in rows}) for c in cols}
    return {"rows": len(rows), "columns": cols, "filled": filled, "avg_chars": avg_len, "distinct": distinct}
