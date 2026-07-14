# -*- coding: utf-8 -*-
import json
from pathlib import Path

for name in ("wuwa", "azurlane"):
    d = json.loads(Path(f"data/{name}.json").read_text(encoding="utf-8"))
    lines = [f"== {name} count={d.get('count')} pending={d.get('pending')} =="]
    for e in d.get("events") or []:
        lines.append(
            f"{e.get('category')}\t{e.get('title')}\t{e.get('start', '')[:16]}\t{e.get('end', '')[:16]}"
        )
    Path(f"scripts/_{name}_sum.txt").write_text("\n".join(lines), encoding="utf-8")
    print(name, d.get("count"))
