#!/usr/bin/env python3
from __future__ import annotations

import csv
import io
import json
import inspect
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Literal


@dataclass(frozen=True)
class ToonOptions:
    delimiter: Literal[",", "\t", "|"] = ","
    indent: int = 2
    length_marker: Literal["", "#"] = ""  # e.g. "#"


class JsonConverter:
    """
    Convert JSON -> VSC (headerless CSV) and JSON -> TOON.

    - VSC: flattens nested dicts into dotted keys.
    - TOON: uses whichever TOON encoder is available (prefers toon_format).
    """

    def __init__(self, *, sep: str = "."):
        self.sep = sep

    # -------------------------
    # Loading
    # -------------------------
    @staticmethod
    def load_json_file(path: Path) -> Any:
        return json.loads(path.read_text(encoding="utf-8"))

    # -------------------------
    # Common helpers
    # -------------------------
    def flatten(self, obj: Any, parent: str = "") -> Dict[str, Any]:
        out: Dict[str, Any] = {}

        if isinstance(obj, dict):
            for k, v in obj.items():
                key = f"{parent}{self.sep}{k}" if parent else str(k)
                out.update(self.flatten(v, key))
            return out

        if isinstance(obj, list):
            out[parent] = json.dumps(obj, ensure_ascii=False)
            return out

        out[parent] = obj
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

    # -------------------------
    # JSON -> VSC
    # -------------------------
    def json_to_vsc_text(
        self,
        data: Any,
        *,
        columns: Optional[Sequence[str]] = None,
    ) -> Tuple[str, List[str]]:
        records = self.guess_records(data)
        flat_rows = [self.flatten(r) for r in records]

        col_list = sorted({k for row in flat_rows for k in row.keys()}) if columns is None else list(columns)

        buf = io.StringIO()
        writer = csv.writer(buf)
        for row in flat_rows:
            writer.writerow([row.get(c, "") for c in col_list])

        return buf.getvalue(), col_list

    def json_file_to_vsc_file(
        self,
        input_json: Path,
        output_vsc: Path,
        *,
        columns: Optional[Sequence[str]] = None,
    ) -> List[str]:
        data = self.load_json_file(input_json)
        text, cols = self.json_to_vsc_text(data, columns=columns)
        output_vsc.write_text(text, encoding="utf-8")
        return cols

    # -------------------------
    # JSON -> TOON
    # -------------------------
    @staticmethod
    def _call_encode(encode_fn: Any, data: Any, opts: dict) -> str:
        """
        Try to call encode in a signature-tolerant way:
        - encode(data)
        - encode(data, opts)
        - encode(data, options=opts)
        """
        try:
            sig = inspect.signature(encode_fn)
            params = sig.parameters
            if len(params) <= 1:
                return encode_fn(data)
            if "options" in params:
                return encode_fn(data, options=opts)
            return encode_fn(data, opts)
        except Exception:
            # last resort
            try:
                return encode_fn(data, opts)
            except TypeError:
                return encode_fn(data)

    @staticmethod
    def json_to_toon_text(data: Any, *, options: Optional[ToonOptions] = None) -> str:
        if options is None:
            options = ToonOptions()

        opts = {
            "delimiter": options.delimiter,
            "indent": options.indent,
            "lengthMarker": options.length_marker,
        }

        # 1) Preferred: official module name in the repo: toon_format
        try:
            from toon_format import encode as encode_toon  # pip install git+https://github.com/toon-format/toon-python.git :contentReference[oaicite:1]{index=1}
            try:
                return JsonConverter._call_encode(encode_toon, data, opts)
            except NotImplementedError:
                # your current situation: stub build installed
                pass
        except ImportError:
            pass

        # # 2) Some guides/packages expose toon_python
        # try:
        #     from toon_python import encode as encode_toon_python  # alt package name in the wild
        #     return JsonConverter._call_encode(encode_toon_python, data, opts)
        # except ImportError:
        #     pass

        # # 3) Deprecated python-toon uses module "toon"
        # try:
        #     from toon import encode as encode_toon_deprecated
        #     return JsonConverter._call_encode(encode_toon_deprecated, data, opts)
        # except ImportError:
        #     pass

        # # 4) Fallback: pytoony API takes JSON string
        # try:
        #     from pytoony import json2toon
        #     return json2toon(json.dumps(data, ensure_ascii=False))
        # except ImportError:
        #     pass

        raise RuntimeError(
            "No working TOON encoder found.\n\n"
            "If you currently get NotImplementedError from toon_format, you installed a stub.\n"
            "Fix:\n"
            "  pip uninstall -y toon-format toon_format\n"
            "  pip install -U git+https://github.com/toon-format/toon-python.git\n"
        )

    def json_file_to_toon_file(
        self,
        input_json: Path,
        output_toon: Path,
        *,
        options: Optional[ToonOptions] = None,
    ) -> None:
        data = self.load_json_file(input_json)
        toon_str = self.json_to_toon_text(data, options=options)
        output_toon.write_text(toon_str, encoding="utf-8")