#!/usr/bin/python3
"""Cross-check the KiCad-exported netlist against the design model in build.py."""
import collections
import sys
import os
sys.argv = [sys.argv[0]]
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build  # noqa: E402  (computes the model, does not write files)

comps, nets = build.export_netlist()
errors = 0
# group model pins by intended net, and KiCad pins by actual net
want = collections.defaultdict(set)
for c in build.COMPS:
    if not c.in_bom:
        continue
    for num, net in c.pins.items():
        want[net if net else ("NC", c.ref, num)].add((c.ref, num))
# internal per-key nets
for k in build.KEYS:
    n = k["n"]
    want[("SWD", n)] = {("SW%d" % n, "2"), ("D%d" % n, "2")}
    want[("LR", n)] = {("LD%d" % n, "1"), ("R%d" % n, "1")}
    for p in (("SW%d" % n, "2"), ("D%d" % n, "2"), ("LD%d" % n, "1"), ("R%d" % n, "1")):
        for key in list(want):
            if not isinstance(key, tuple) or key[0] == "NC":
                if key[0:1] == ("NC",) and (key[1], key[2]) == p:
                    del want[key]
have = collections.defaultdict(set)
for node, net in nets.items():
    have[net].add(node)
# compare partitions
have_sets = {frozenset(v) for v in have.values()}
for key, pins in want.items():
    if isinstance(key, tuple) and key[0] == "NC":
        fs = frozenset(pins)
        # unconnected pin must be alone on its net
        if fs not in have_sets:
            print("NC pin not isolated:", key); errors += 1
        continue
    if frozenset(pins) not in have_sets:
        actual = [n for n, v in have.items() if pins & v]
        print("MISMATCH", key, "->", actual[:5]); errors += 1
# every net with a single node that is not intentionally NC
for net, v in have.items():
    if len(v) == 1 and not net.startswith("unconnected-"):
        print("single-node net:", net, v); errors += 1
print("nets:", len(have), "errors:", errors)
sys.exit(1 if errors else 0)
