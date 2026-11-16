#!/usr/bin/env python3
"""Syntax-check ES modules with the system JavaScriptCore binary.

jsc cannot load modules, so imports/exports are stripped first. This catches
typos and unbalanced braces without a Node toolchain.
"""
import re
import subprocess
import sys
from pathlib import Path

JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc"


def strip(src: str) -> str:
    src = re.sub(r"^import\s+[\s\S]*?\sfrom\s+['\"][^'\"]+['\"];\s*", "", src, flags=re.M)
    src = re.sub(r"^import\s+['\"][^'\"]+['\"];\s*", "", src, flags=re.M)
    src = re.sub(r"^export\s+\{[^}]*\};?\s*$", "", src, flags=re.M)
    src = re.sub(r"^export\s+default\s+", "", src, flags=re.M)
    src = re.sub(r"^export\s+(const|let|var|function|class|async function)", r"\1", src, flags=re.M)
    return src


def check(path: Path) -> bool:
    original = path.read_text(encoding="utf-8")
    stripped = strip(original)
    tmp = Path("/tmp") / f"pulse-check-{path.stem}.js"
    tmp.write_text(stripped, encoding="utf-8")
    proc = subprocess.run([JSC, str(tmp)], capture_output=True, text=True)
    out = (proc.stdout + proc.stderr).strip()
    if "SyntaxError" in out:
        print(f"FAIL {path}")
        print(out.splitlines()[0])
        line = re.search(r"at .*:(\d+)", out)
        if line:
            number = int(line.group(1))
            for offset, text in enumerate(stripped.splitlines()[max(0, number - 3):number + 2], start=max(1, number - 2)):
                print(f"  {offset:4d}| {text}")
        return False
    print(f"ok   {path}")
    return True


if __name__ == "__main__":
    targets = [Path(p) for p in sys.argv[1:]] or sorted(Path("pulse/static/js").rglob("*.js"))
    ok = all(check(path) for path in targets)
    sys.exit(0 if ok else 1)
