#!/usr/bin/python3
"""Grouped BOM (CSV) from the KiCad netlist."""
import collections, csv, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sexp import parse, find, findall
PROJ = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
d = parse(open(os.path.join(PROJ, "build", "hom-keyboard.net")).read())
groups = collections.OrderedDict()
for c in findall(find(d, "components"), "comp"):
    ref = find(c, "ref")[1]
    fp = find(c, "footprint")[1] if find(c, "footprint") else ""
    val = find(c, "value")[1]
    if ref.startswith("SW") and "Cherry_MX" in fp:
        val = "MX switch"
    groups.setdefault((val, fp), []).append(ref)
with open(os.path.join(PROJ, "hom-keyboard-bom.csv"), "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["Qty", "Value", "Footprint", "References"])
    for (val, fp), refs in sorted(groups.items(), key=lambda x: (-len(x[1]), x[0])):
        w.writerow([len(refs), val, fp, " ".join(refs)])
print(len(groups), "BOM lines")
