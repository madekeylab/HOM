#!/usr/bin/python3
"""Run KiCad DRC on the board and print a summary. usage: drc.py board.kicad_pcb report.txt"""
import sys, re, collections
import pcbnew
b = pcbnew.LoadBoard(sys.argv[1])
out = sys.argv[2]
pcbnew.WriteDRCReport(b, out, pcbnew.EDA_UNITS_MILLIMETRES, True)
txt = open(out).read()
kinds = collections.Counter(re.findall(r"^\[(\w+)\]", txt, re.M))
for k, v in kinds.most_common():
    print("%5d %s" % (v, k))
