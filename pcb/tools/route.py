#!/usr/bin/python3
"""Autoroute the board with Freerouting, then add GND pours.

usage: route.py <freerouting.jar> [max_passes]
"""
import os
import subprocess
import sys

import pcbnew

PROJ = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PCB = os.path.join(PROJ, "hom-keyboard.kicad_pcb")
DSN = os.path.join(PROJ, "build", "hom.dsn")
SES = os.path.join(PROJ, "build", "hom.ses")
jar = sys.argv[1]
passes = sys.argv[2] if len(sys.argv) > 2 else "40"

board = pcbnew.LoadBoard(PCB)
# start from a clean slate
for t in list(board.GetTracks()):
    board.Remove(t)
for z in list(board.Zones()):
    board.Remove(z)
assert pcbnew.ExportSpecctraDSN(board, DSN)

if os.path.exists(SES):
    os.remove(SES)
subprocess.run(["java", "-Djava.awt.headless=true", "-jar", jar, "-de", DSN, "-do", SES,
                "-mp", passes, "-mt", "4"], check=False)
assert os.path.exists(SES), "freerouting produced no session file"
assert pcbnew.ImportSpecctraSES(board, SES)

# GND pours on both layers
bb = board.GetBoardEdgesBoundingBox()
gnd = board.FindNet("GND")
for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
    z = pcbnew.ZONE(board)
    z.SetLayer(layer)
    z.SetNet(gnd)
    z.SetLocalClearance(pcbnew.FromMM(0.3))
    z.SetMinThickness(pcbnew.FromMM(0.25))
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
    z.SetThermalReliefGap(pcbnew.FromMM(0.4))
    z.SetThermalReliefSpokeWidth(pcbnew.FromMM(0.5))
    z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
    o = z.Outline()
    o.NewOutline()
    for x, y in ((bb.GetLeft(), bb.GetTop()), (bb.GetRight(), bb.GetTop()),
                 (bb.GetRight(), bb.GetBottom()), (bb.GetLeft(), bb.GetBottom())):
        o.Append(x, y)
    board.Add(z)
pcbnew.ZONE_FILLER(board).Fill(board.Zones())
board.Save(PCB)
print("tracks:", len(board.GetTracks()))
