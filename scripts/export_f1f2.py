# -*- coding: utf-8 -*-
"""Quick export of F1 and F2 only."""
import sys
sys.path.insert(0, r"c:\Users\咸\Desktop\project\scripts")
from pathlib import Path

# Monkey-patch the main to only do F1/F2
root = Path(r"c:\Users\咸\Desktop\project") / "docs" / "software-eng"
out_dir = Path(r"c:\Users\咸\Desktop\project") / "docs" / "export_docx"
names = ["SparkOrbit-F1-开发进度月报.md", "SparkOrbit-F2-项目开发总结报告.md"]

exec(open(r"c:\Users\咸\Desktop\project\scripts\md_to_docx.py").read().split("def main():")[0])

for name in names:
    md = root / name
    if md.exists():
        convert(md, out_dir / (md.stem + ".docx"))
    else:
        print(f"MISSING: {name}")
