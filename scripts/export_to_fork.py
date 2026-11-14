#!/usr/bin/env python3
"""Copy the bots into a checkout of the Catalyst harness fork, ready to submit.

    python3 scripts/export_to_fork.py /path/to/megagem-harness            # all three
    python3 scripts/export_to_fork.py /path/to/megagem-harness MarketReader

Copies the bot files plus the shared otis_core.py into src/bot_definitions/ and
registers the classes in src/custom_bots.py. Safe to run again after changes.
"""

import re
import shutil
import sys
from pathlib import Path

BOTS = {
    "FairValuePacer": "fair_value_pacer",
    "MarketReader": "market_reader",
    "EvolvedWeights": "evolved_weights",
}


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    fork = Path(sys.argv[1]).expanduser().resolve()
    names = sys.argv[2:] or list(BOTS)
    unknown = [n for n in names if n not in BOTS]
    if unknown:
        print(f"Unknown bot(s): {unknown}. Choose from {list(BOTS)}.")
        return 2
    target = fork / "src" / "bot_definitions"
    registry = fork / "src" / "custom_bots.py"
    if not target.is_dir() or not registry.is_file():
        print(f"{fork} does not look like the harness (no src/bot_definitions).")
        return 1
    source = Path(__file__).resolve().parents[1] / "otis_bots"
    for module in ["otis_core"] + [BOTS[n] for n in names]:
        shutil.copyfile(source / f"{module}.py", target / f"{module}.py")
        print(f"copied {module}.py")
    text = registry.read_text()
    listed = re.search(r"__all__\s*=\s*\[(.*?)\]", text, re.S)
    exported = re.findall(r"[\"'](\w+)[\"']", listed.group(1)) if listed else []
    for name in names:
        line = f"from bot_definitions.{BOTS[name]} import {name}"
        if line not in text:
            imports = list(re.finditer(r"^from .+ import .+$", text, re.M))
            at = imports[-1].end() if imports else 0
            text = text[:at] + ("\n" if at else "") + line + ("" if at else "\n") + text[at:]
        if name not in exported:
            exported.append(name)
    new_all = "__all__ = [" + ", ".join(f'"{n}"' for n in sorted(exported)) + "]"
    text = re.sub(r"__all__\s*=\s*\[.*?\]", new_all, text, flags=re.S) if listed else text + "\n" + new_all + "\n"
    registry.write_text(text)
    print(f"registered {names} in src/custom_bots.py")
    print(f"try: cd {fork} && python3 src/harness.py 3 --bots custom_bots:{names[0]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
