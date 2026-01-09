from __future__ import annotations
import csv
import io
import json
import inspect
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Literal, Union

@dataclass(frozen=True)
class ToonOptions:
    delimiter: Literal[",", "\t", "|"] = ","
    indent: int = 2
    length_marker: Literal["", "#"] = ""

class JsonConverter:
    def __init__(self, *, sep: str = "."):
        self.sep = sep

    @staticmethod
    def load_json_file(path: Path) -> Any:
        return json.loads(path.read_text(encoding="utf-8"))

    def flatten(self, obj: Any, parent: str = "") -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        if isinstance(obj, dict):
            for k, v in obj.items():
                key = f"{parent}{self.sep}{k}" if parent else str(k)
                out.update(self.flatten(v, key))
            return out
        if isinstance(obj, list):
            key = parent if parent else "value"
            out[key] = json.dumps(obj, ensure_ascii=False)
            return out
        key = parent if parent else "value"
        out[key] = obj
        return out

    @staticmethod
    def guess_records(data: Any) -> List[Dict[str, Any]]:
        if isinstance(data, list):
            return [x if isinstance(x, dict) else {"value": x} for x in data]
        if isinstance(data, dict):
            for key in ("data", "items", "results", "records", "rows"):
                if isinstance(data.get(key), list):
                    return [x if isinstance(x, dict) else {"value": x} for x in data[key]]
            return [data]
        return [{"value": data}]

    @staticmethod
    def _pick_explode_key(records: List[Dict[str, Any]], explode_key: Optional[Union[str, Sequence[str]]]) -> Optional[str]:
        if explode_key is None: return None
        if isinstance(explode_key, str): return explode_key.strip() or None
        for k in explode_key:
            kk = (k or "").strip()
            if not kk: continue
            for r in records:
                if isinstance(r, dict) and isinstance(r.get(kk), list):
                    return kk
        return None

    def _explode_records(self, records: List[Dict[str, Any]], explode_key: Optional[str]) -> List[Dict[str, Any]]:
        if not explode_key: return records
        out: List[Dict[str, Any]] = []
        for r in records:
            val = r.get(explode_key)
            if isinstance(val, list):
                base = dict(r)
                base.pop(explode_key, None)
                if not val:
                    row = dict(base)
                    row[explode_key] = None
                    out.append(row)
                    continue
                for item in val:
                    row = dict(base)
                    row[explode_key] = item if isinstance(item, dict) else {"value": item}
                    out.append(row)
            else:
                out.append(r)
        return out

    def json_to_vsc_text(self, data: Any, *, columns: Optional[Sequence[str]] = None, include_header: bool = False, preserve_key_order: bool = True, explode_key: Optional[Union[str, Sequence[str]]] = None) -> Tuple[str, List[str]]:
        records = self.guess_records(data)
        chosen = self._pick_explode_key(records, explode_key)
        records = self._explode_records(records, chosen)
        flat_rows = [self.flatten(r) for r in records]
        
        if columns is not None:
            col_list = list(columns)
        else:
            if preserve_key_order:
                col_list: List[str] = []
                seen: set[str] = set()
                for row in flat_rows:
                    for k in row.keys():
                        if k not in seen:
                            seen.add(k)
                            col_list.append(k)
            else:
                col_list = sorted({k for row in flat_rows for k in row.keys()})
        
        buf = io.StringIO()
        writer = csv.writer(buf)
        if include_header:
            writer.writerow(col_list)
        for row in flat_rows:
            writer.writerow([row.get(c, "") for c in col_list])
        return buf.getvalue(), col_list

    @staticmethod
    def _call_encode(encode_fn: Any, data: Any, opts: dict) -> str:
        try:
            sig = inspect.signature(encode_fn)
            params = sig.parameters
            if len(params) <= 1: return encode_fn(data)
            if "options" in params: return encode_fn(data, options=opts)
            return encode_fn(data, opts)
        except Exception:
            try: return encode_fn(data, opts)
            except TypeError: return encode_fn(data)

    @staticmethod
    def json_to_toon_text(data: Any, *, options: Optional[ToonOptions] = None) -> str:
        if options is None: options = ToonOptions()
        opts = {"delimiter": options.delimiter, "indent": options.indent, "lengthMarker": options.length_marker}
        try:
            from toon_format import encode as encode_toon
            try: return JsonConverter._call_encode(encode_toon, data, opts)
            except NotImplementedError: pass
        except ImportError: pass
        raise RuntimeError("No working TOON encoder found. pip install -U git+https://github.com/toon-format/toon-python.git")
