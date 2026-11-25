#!/usr/bin/python3
"""Generate the HOM full-size keyboard: schematic, PCB placement, QMK config.

Run with the system python that has KiCad's pcbnew module:
    /usr/bin/python3 pcb/tools/build.py

Flow:
  1. compute geometry (key positions, MCU pad positions -> GPIO assignment)
  2. write hom-keyboard.kicad_sch
  3. export the netlist with kicad-cli (so the PCB uses KiCad's own nets)
  4. build hom-keyboard.kicad_pcb with every footprint placed and netted
  5. write QMK keyboard.json
"""
import json
import math
import os
import subprocess
import sys
import uuid as _uuid

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from layout import NCOLS, NROWS, U, build_keys, keycode  # noqa: E402
from sexp import Sym, dump, find, findall, parse  # noqa: E402

PROJ = os.path.abspath(os.path.join(HERE, ".."))
NAME = "hom-keyboard"
SCH = os.path.join(PROJ, NAME + ".kicad_sch")
PCB = os.path.join(PROJ, NAME + ".kicad_pcb")
NET = os.path.join(PROJ, "build", NAME + ".net")
SYMLIB = "/usr/share/kicad/symbols"
FPLIB = "/usr/share/kicad/footprints"

X0, Y0 = 20.0, 20.0      # PCB position of the key-grid origin (mm)
MARGIN = 3.0             # board edge distance from the key grid
BOARD_W = 22.5 * U
BOARD_H = 6.5 * U

_uuid_ns = _uuid.UUID("6f1b3c2a-4c5e-4a8e-9d0b-0b4d5e6f7a81")


def uid(*parts):
    """Deterministic UUIDs so regenerating gives stable files."""
    return str(_uuid.uuid5(_uuid_ns, "/".join(str(p) for p in parts)))


ROOT_UUID = uid("root")

# --------------------------------------------------------------------------
# Component model
# --------------------------------------------------------------------------
POWER_NETS = {"GND", "+5V", "+3V3", "+1V1"}


class Comp:
    def __init__(self, ref, lib_id, value, footprint, pins, sch, pcb=None,
                 side="B", in_bom=True):
        self.ref, self.lib_id, self.value, self.footprint = ref, lib_id, value, footprint
        self.pins = pins            # {pin_number: net or None}
        self.sch = sch              # (x, y, rot)
        self.pcb = pcb              # (x, y, rot) in key-grid mm, or None
        self.side = side            # "F" or "B"
        self.in_bom = in_bom


COMPS = []


def add(*a, **kw):
    c = Comp(*a, **kw)
    COMPS.append(c)
    return c


# --------------------------------------------------------------------------
# Keyboard matrix + per-key LEDs
# --------------------------------------------------------------------------
KEYS = build_keys()


def sw_footprint(w, h):
    if h == 2:
        return "Button_Switch_Keyboard:SW_Cherry_MX_2.00u_Vertical_PCB"
    size = {1: "1.00u", 1.25: "1.25u", 1.5: "1.50u", 1.75: "1.75u", 2: "2.00u",
            2.25: "2.25u", 2.75: "2.75u", 6.25: "6.25u"}[w]
    return "Button_Switch_Keyboard:SW_Cherry_MX_%s_PCB" % size


def g(v, grid=1.27):
    return round(round(v / grid) * grid, 4)


MAT_X0, MAT_Y0 = 38.1, 50.8      # schematic origin of the matrix block
LED_X0, LED_Y0 = 38.1, 190.5     # schematic origin of the LED block
CELL_W, CELL_H = 25.4, 20.32

for i, k in enumerate(KEYS):
    n = i + 1
    k["n"] = n
    cx, cy = k["cx"] * U, k["cy"] * U
    k["mm"] = (cx, cy)
    sx = g(MAT_X0 + k["col"] * CELL_W)
    sy = g(MAT_Y0 + k["row"] * CELL_H)
    # Switch: pin1 -> COL, pin2 -> diode anode.  MX footprint origin is pad 1,
    # switch centre is at (-2.54, +5.08) from it.
    add("SW%d" % n, "Switch:SW_Push", k["label"], sw_footprint(k["w"], k["h"]),
        {"1": "COL%d" % k["col"], "2": None}, (sx, sy, 0),
        (cx + 2.54, cy - 5.08, 0), side="F")
    # Diode (rot 90 -> anode up, sits right on SW pin 2), cathode -> ROW
    add("D%d" % n, "Device:D", "1N4148W", "Diode_SMD:D_SOD-123",
        {"1": "ROW%d" % k["row"], "2": None}, (sx + 5.08, sy + 3.81, 90),
        (cx - 7.3, cy + 2.4, 90), side="B")
    # Per-key LED in the MX LED slot + series resistor to the backlight sink
    lx = g(LED_X0 + k["col"] * CELL_W)
    ly = g(LED_Y0 + k["row"] * CELL_H)
    add("LD%d" % n, "Device:LED", "LED 3mm", "LED_THT:LED_D3.0mm",
        {"1": None, "2": "+5V"}, (lx, ly, 0), (cx - 1.27, cy + 5.08, 0), side="F")
    add("R%d" % n, "Device:R", "1k", "Resistor_SMD:R_0603_1608Metric",
        {"1": None, "2": "BL_K"}, (lx - 3.81, ly + 3.81, 0),
        (cx + 4.4, cy + 6.3, 0), side="B")

# internal 2-pin nets (switch-diode, LED-resistor) get connected by placing
# the pins on top of each other in the schematic; mark them so the writer
# does not put a no-connect there.
INTERNAL = set()
for k in KEYS:
    for p in (("SW%d" % k["n"], "2"), ("D%d" % k["n"], "2"),
              ("LD%d" % k["n"], "1"), ("R%d" % k["n"], "1")):
        INTERNAL.add(p)

# --------------------------------------------------------------------------
# MCU section (all SMD on the back, in the free area above the numpad)
# --------------------------------------------------------------------------
REF_COUNT = {"R": len(KEYS), "C": 0, "U": 0, "J": 0, "SW": len(KEYS), "Q": 0,
             "F": 0, "Y": 0, "LD": len(KEYS), "H": 0}


def nref(prefix):
    REF_COUNT[prefix] += 1
    return "%s%d" % (prefix, REF_COUNT[prefix])


MCU_POS = (370.0, 12.0)        # PCB, key-grid mm
FP_RP2040 = "Package_DFN_QFN:QFN-56-1EP_7x7mm_P0.4mm_EP3.2x3.2mm_ThermalVias"


def load_fp(fpid):
    lib, name = fpid.split(":")
    fp = pcbnew.FootprintLoad(os.path.join(FPLIB, lib + ".pretty"), name)
    if fp is None:
        raise RuntimeError("footprint not found: " + fpid)
    fp.SetFPID(pcbnew.LIB_ID(lib, name))
    return fp


def mm(v):
    return pcbnew.FromMM(v)


def vec(x, y):
    return pcbnew.VECTOR2I(mm(x), mm(y))


def place_fp(board, fp, x, y, rot, side):
    fp.SetPosition(vec(X0 + x, Y0 + y))
    if side == "B":
        fp.Flip(fp.GetPosition(), False)
    fp.SetOrientationDegrees(rot)


def mcu_geometry():
    """Pick the RP2040 orientation (flash/USB side toward +x) and return the
    absolute pad positions in key-grid mm."""
    board = pcbnew.NewBoard(os.path.join(PROJ, "build", "_geom.kicad_pcb"))
    best = None
    for rot in (0, 90, 180, 270):
        fp = load_fp(FP_RP2040)
        board.Add(fp)
        place_fp(board, fp, MCU_POS[0], MCU_POS[1], rot, "B")
        pads = {}
        for p in fp.Pads():
            pos = p.GetPosition()
            pads.setdefault(p.GetNumber(), (pcbnew.ToMM(pos.x) - X0, pcbnew.ToMM(pos.y) - Y0))
        score = pads["50"][0]
        if best is None or score > best[0]:
            best = (score, rot, pads)
    return best[1], best[2]


os.makedirs(os.path.join(PROJ, "build"), exist_ok=True)
MCU_ROT, MCU_PADS = mcu_geometry()


def side_of(pin):
    """Outward unit normal and tangential coord of a QFN pad."""
    px, py = MCU_PADS[pin]
    dx, dy = px - MCU_POS[0], py - MCU_POS[1]
    if abs(dx) > abs(dy):
        return (1 if dx > 0 else -1, 0), dy
    return (0, 1 if dy > 0 else -1), dx


# ---- GPIO assignment: match pins to their targets by angle ----------------
GPIO_PINS = {0: "2", 1: "3", 2: "4", 3: "5", 4: "6", 5: "7", 6: "8", 7: "9",
             8: "11", 9: "12", 10: "13", 11: "14", 12: "15", 13: "16", 14: "17",
             15: "18", 16: "27", 17: "28", 18: "29", 19: "30", 20: "31", 21: "32",
             22: "34", 23: "35", 24: "36", 25: "37", 26: "38", 27: "39", 28: "40",
             29: "41"}

IND_POS = {"LED_NUM": (412.0, 7.0), "LED_CAPS": (420.0, 7.0)}
Q1_POS = (356.0, 22.5)

targets = {}
for c in range(NCOLS):
    top = min((k for k in KEYS if k["col"] == c), key=lambda k: k["cy"])
    targets["COL%d" % c] = (top["mm"][0] + 2.54, top["mm"][1] - 5.08)
for r in range(NROWS):
    right = max((k for k in KEYS if k["row"] == r), key=lambda k: k["cx"])
    targets["ROW%d" % r] = (right["mm"][0] - 7.3, right["mm"][1] + 2.4)
targets["BL_PWM"] = Q1_POS
targets.update(IND_POS)


def ang(p):
    return math.atan2(p[1] - MCU_POS[1], p[0] - MCU_POS[0])


funcs = sorted(targets, key=lambda f: ang(targets[f]))
gpios = sorted(GPIO_PINS, key=lambda gp: ang(MCU_PADS[GPIO_PINS[gp]]))
assert len(funcs) == len(gpios) == 30
best = None
for shift in range(30):
    cost = 0.0
    for i, f in enumerate(funcs):
        gp = gpios[(i + shift) % 30]
        d = abs(ang(targets[f]) - ang(MCU_PADS[GPIO_PINS[gp]]))
        cost += min(d, 2 * math.pi - d)
    if best is None or cost < best[0]:
        best = (cost, shift)
GPIO_OF = {f: gpios[(i + best[1]) % 30] for i, f in enumerate(funcs)}

# ---- RP2040 -----------------------------------------------------------------
MCU_SCH = (165.1, 419.1)
rp_pins = {}
for p in ("1", "10", "22", "33", "42", "49", "43", "44", "48"):
    rp_pins[p] = "+3V3"
for p in ("23", "50", "45"):
    rp_pins[p] = "+1V1"
rp_pins.update({"57": "GND", "19": "GND", "20": "XIN", "21": "XOUT_MCU",
                "24": "SWCLK", "25": "SWDIO", "26": "RUN",
                "46": "USB_DM_MCU", "47": "USB_DP_MCU",
                "51": "QSPI_SD3", "52": "QSPI_SCLK", "53": "QSPI_SD0",
                "54": "QSPI_SD2", "55": "QSPI_SD1", "56": "QSPI_SS"})
for f, gp in GPIO_OF.items():
    rp_pins[GPIO_PINS[gp]] = f
add("U1", "MCU_RaspberryPi:RP2040", "RP2040", FP_RP2040, rp_pins,
    (MCU_SCH[0], MCU_SCH[1], 0), (MCU_POS[0], MCU_POS[1], MCU_ROT))
REF_COUNT["U"] = 1

# ---- parts that hug the MCU pins (decoupling, crystal, USB series R) -------
hug = []   # (ref, pin, distance)
dec_sch_x = 63.5
for i, (pin, val, net) in enumerate([
        ("1", "100n", "+3V3"), ("10", "100n", "+3V3"), ("22", "100n", "+3V3"),
        ("33", "100n", "+3V3"), ("42", "100n", "+3V3"), ("49", "100n", "+3V3"),
        ("43", "100n", "+3V3"), ("44", "1u", "+3V3"), ("23", "100n", "+1V1"),
        ("50", "100n", "+1V1"), ("45", "1u", "+1V1")]):
    ref = nref("C")
    add(ref, "Device:C", val, "Capacitor_SMD:C_0603_1608Metric",
        {"1": net, "2": "GND"}, (g(38.1 + i * 10.16), g(355.6), 0))
    hug.append((ref, pin))

r_xo = nref("R")
add(r_xo, "Device:R", "1k", "Resistor_SMD:R_0603_1608Metric",
    {"1": "XOUT_MCU", "2": "XOUT"}, (g(101.6), g(462.28), 90))
hug.append((r_xo, "21"))
r_dp = nref("R")
add(r_dp, "Device:R", "27", "Resistor_SMD:R_0603_1608Metric",
    {"1": "USB_DP_MCU", "2": "USB_D+"}, (g(101.6), g(388.62), 90))
hug.append((r_dp, "47"))
r_dm = nref("R")
add(r_dm, "Device:R", "27", "Resistor_SMD:R_0603_1608Metric",
    {"1": "USB_DM_MCU", "2": "USB_D-"}, (g(101.6), g(391.16 + 6.35), 90))
hug.append((r_dm, "46"))

# spread the hugging parts along each side of the QFN
by_side = {}
for ref, pin in hug:
    n, t = side_of(pin)
    by_side.setdefault(n, []).append([t, ref])
POS = {}
for n, lst in by_side.items():
    lst.sort()
    spacing = 2.0
    # centre the group on the mean of the targets, keep monotonic order
    for i in range(1, len(lst)):
        if lst[i][0] < lst[i - 1][0] + spacing:
            lst[i][0] = lst[i - 1][0] + spacing
    shift = (sum(t for t, _ in lst) / len(lst)) - (lst[0][0] + lst[-1][0]) / 2
    for t, ref in lst:
        t2 = t - shift if len(lst) > 1 else t
        dist = 6.2
        if n[0] != 0:
            POS[ref] = (MCU_POS[0] + n[0] * dist, t2 + MCU_POS[1] * 0 + 0, 0)
            POS[ref] = (MCU_POS[0] + n[0] * dist, MCU_POS[1] + (t2), 0)
        else:
            POS[ref] = (MCU_POS[0] + t2, MCU_POS[1] + n[1] * dist, 90)
for c in COMPS:
    if c.ref in POS:
        c.pcb = POS[c.ref]

# crystal beyond the XIN/XOUT pins
n_x, _ = side_of("20")
mid = ((MCU_PADS["20"][0] + MCU_PADS["21"][0]) / 2, (MCU_PADS["20"][1] + MCU_PADS["21"][1]) / 2)
xt = (mid[0] + n_x[0] * 10.5 if n_x[0] else mid[0], mid[1] + n_x[1] * 10.5 if n_x[1] else mid[1])
tang = (0, 1) if n_x[0] else (1, 0)
add("Y1", "Device:Crystal_GND24", "12MHz", "Crystal:Crystal_SMD_3225-4Pin_3.2x2.5mm",
    {"1": "XIN", "2": "GND", "3": "XOUT", "4": "GND"}, (g(76.2), g(469.9), 0),
    (xt[0], xt[1], 0))
REF_COUNT["Y"] = 1
c_xi = nref("C")
add(c_xi, "Device:C", "22p", "Capacitor_SMD:C_0603_1608Metric", {"1": "XIN", "2": "GND"},
    (g(68.58), g(482.6), 0),
    (xt[0] - tang[0] * 4.2 + n_x[0] * 0.0, xt[1] - tang[1] * 4.2, 90 if n_x[1] else 0))
c_xo = nref("C")
add(c_xo, "Device:C", "22p", "Capacitor_SMD:C_0603_1608Metric", {"1": "XOUT", "2": "GND"},
    (g(83.82), g(482.6), 0),
    (xt[0] + tang[0] * 4.2, xt[1] + tang[1] * 4.2, 90 if n_x[1] else 0))

# ---- QSPI flash ---------------------------------------------------------------
FLASH_POS = (MCU_POS[0] + 13.5, MCU_POS[1] + 1.0)
add("U2", "Memory_Flash:W25Q128JVS", "W25Q128JVS",
    "Package_SO:SOIC-8_5.23x5.23mm_P1.27mm",
    {"1": "QSPI_SS", "2": "QSPI_SD1", "3": "QSPI_SD2", "4": "GND", "5": "QSPI_SD0",
     "6": "QSPI_SCLK", "7": "QSPI_SD3", "8": "+3V3"},
    (g(76.2), g(419.1), 0), (FLASH_POS[0], FLASH_POS[1], 90))
c_fl = nref("C")
add(c_fl, "Device:C", "100n", "Capacitor_SMD:C_0603_1608Metric", {"1": "+3V3", "2": "GND"},
    (g(55.88), g(406.4), 0), (FLASH_POS[0], FLASH_POS[1] - 7.2, 0))

# BOOTSEL: QSPI_SS -> 1k -> button -> GND
r_bs = nref("R")
add(r_bs, "Device:R", "1k", "Resistor_SMD:R_0603_1608Metric", {"1": "QSPI_SS", "2": "BOOT"},
    (g(43.18), g(436.88), 0), (FLASH_POS[0] - 2.5, FLASH_POS[1] + 9.0, 0))
sw_boot = nref("SW")
add(sw_boot, "Switch:SW_Push", "BOOT", "Button_Switch_SMD:SW_SPST_TL3342",
    {"1": "BOOT", "2": "GND"}, (g(43.18), g(452.12), 90), (414.0, 21.0, 0))

# RUN: 10k pull-up + reset button
r_run = nref("R")
add(r_run, "Device:R", "10k", "Resistor_SMD:R_0603_1608Metric", {"1": "+3V3", "2": "RUN"},
    (g(114.3), g(452.12), 0), (408.5, 12.5, 90))
sw_rst = nref("SW")
add(sw_rst, "Switch:SW_Push", "RESET", "Button_Switch_SMD:SW_SPST_TL3342",
    {"1": "RUN", "2": "GND"}, (g(121.92), g(469.9), 90), (423.0, 21.0, 0))

# SWD header
add("J2", "Connector_Generic:Conn_01x03", "SWD", "Connector_PinHeader_2.54mm:PinHeader_1x03_P2.54mm_Vertical",
    {"1": "SWCLK", "2": "SWDIO", "3": "GND"}, (g(127.0), g(497.84), 0), (425.5, 9.5, 0))

# ---- USB-C, protection, power ------------------------------------------------
USB_X = 398.0
add("J1", "Connector:USB_C_Receptacle_USB2.0_16P", "USB-C", "Connector_USB:USB_C_Receptacle_HRO_TYPE-C-31-M-12",
    {"A1": "GND", "A12": "GND", "B1": "GND", "B12": "GND",
     "A4": "VBUS", "A9": "VBUS", "B4": "VBUS", "B9": "VBUS",
     "A5": "CC1", "B5": "CC2", "A6": "USB_D+", "B6": "USB_D+", "A7": "USB_D-", "B7": "USB_D-",
     "A8": None, "B8": None, "S1": "GND"},
    (g(266.7), g(419.1), 0), (USB_X, None, 0))
REF_COUNT["J"] = 2
r_cc1 = nref("R")
add(r_cc1, "Device:R", "5.1k", "Resistor_SMD:R_0603_1608Metric", {"1": "CC1", "2": "GND"},
    (g(297.18), g(436.88), 0), (USB_X - 6.0, 10.8, 90))
r_cc2 = nref("R")
add(r_cc2, "Device:R", "5.1k", "Resistor_SMD:R_0603_1608Metric", {"1": "CC2", "2": "GND"},
    (g(307.34), g(436.88), 0), (USB_X + 6.0, 10.8, 90))
add("U3", "Power_Protection:USBLC6-2SC6", "USBLC6-2SC6", "Package_TO_SOT_SMD:SOT-23-6",
    {"1": "USB_D+", "6": "USB_D+", "3": "USB_D-", "4": "USB_D-", "2": "GND", "5": "VBUS"},
    (g(325.12), g(381.0), 0), (USB_X, 14.5, 0))
add("F1", "Device:Polyfuse", "500mA", "Fuse:Fuse_1206_3216Metric",
    {"1": "VBUS", "2": "+5V"}, (g(325.12), g(408.94), 0), (USB_X - 6.5, 18.5, 90))
REF_COUNT["F"] = 1
c_5v = nref("C")
add(c_5v, "Device:C", "10u", "Capacitor_SMD:C_0805_2012Metric", {"1": "+5V", "2": "GND"},
    (g(335.28), g(424.18), 0), (USB_X - 6.5, 24.0, 0))
add("U4", "Regulator_Linear:AP2112K-3.3", "AP2112K-3.3", "Package_TO_SOT_SMD:SOT-23-5",
    {"1": "+5V", "2": "GND", "3": "+5V", "4": None, "5": "+3V3"},
    (g(368.3), g(419.1), 0), (USB_X + 6.0, 18.5, 0))
c_li = nref("C")
add(c_li, "Device:C", "1u", "Capacitor_SMD:C_0603_1608Metric", {"1": "+5V", "2": "GND"},
    (g(350.52), g(424.18), 0), (USB_X + 1.5, 22.5, 90))
c_lo = nref("C")
add(c_lo, "Device:C", "10u", "Capacitor_SMD:C_0805_2012Metric", {"1": "+3V3", "2": "GND"},
    (g(386.08), g(424.18), 0), (USB_X + 10.0, 22.5, 90))

# ---- backlight PWM sink -------------------------------------------------------
add("Q1", "Transistor_FET:AO3400A", "AO3400A", "Package_TO_SOT_SMD:SOT-23",
    {"1": "BL_G", "2": "GND", "3": "BL_K"}, (g(444.5), g(419.1), 0),
    (Q1_POS[0], Q1_POS[1], 0))
REF_COUNT["Q"] = 1
r_g = nref("R")
add(r_g, "Device:R", "100", "Resistor_SMD:R_0603_1608Metric", {"1": "BL_PWM", "2": "BL_G"},
    (g(429.26), g(419.1), 90), (Q1_POS[0] - 4.2, Q1_POS[1], 90))
r_pd = nref("R")
add(r_pd, "Device:R", "10k", "Resistor_SMD:R_0603_1608Metric", {"1": "BL_G", "2": "GND"},
    (g(434.34), g(431.8), 0), (Q1_POS[0] - 6.4, Q1_POS[1], 90))

# ---- lock indicators (THT LEDs on top) -----------------------------------------
ind_sch_x = 495.3
for i, (net, label) in enumerate((("LED_NUM", "NumLock"), ("LED_CAPS", "CapsLock"))):
    r_ind = nref("R")
    a_net = net + "_A"
    add(r_ind, "Device:R", "1k", "Resistor_SMD:R_0603_1608Metric", {"1": net, "2": a_net},
        (g(ind_sch_x + i * 20.32), g(411.48), 0),
        (IND_POS[net][0] + 1.27, IND_POS[net][1] + 5.5, 0))
    ld = nref("LD")
    add(ld, "Device:LED", label, "LED_THT:LED_D3.0mm", {"1": "GND", "2": a_net},
        (g(ind_sch_x + i * 20.32 - 3.81), g(426.72), 90),
        (IND_POS[net][0], IND_POS[net][1], 0), side="F")

# ---- power flags (schematic only) ---------------------------------------------
add("#FLG01", "power:PWR_FLAG", "PWR_FLAG", "", {"1": "+5V"}, (g(345.44), g(393.7), 0), None,
    in_bom=False)
add("#FLG02", "power:PWR_FLAG", "PWR_FLAG", "", {"1": "GND"}, (g(358.14), g(393.7), 0), None,
    in_bom=False)
add("#FLG03", "power:PWR_FLAG", "PWR_FLAG", "", {"1": "VBUS"}, (g(312.42), g(393.7), 0), None,
    in_bom=False)


# --------------------------------------------------------------------------
# Schematic writer
# --------------------------------------------------------------------------
def load_symbol(lib_id):
    lib, name = lib_id.split(":")
    d = parse(open(os.path.join(SYMLIB, lib + ".kicad_sym")).read())
    syms = {s[1]: s for s in findall(d, "symbol")}
    s = syms[name]
    ext = find(s, "extends")
    if ext is None:
        out = [Sym("symbol"), lib_id] + s[2:]
        base_name = name
        body = s
    else:
        parent = syms[ext[1]]
        base_name = ext[1]
        body = parent
        out = [Sym("symbol"), lib_id]
        for x in parent[2:]:
            if isinstance(x, list) and x[0] in ("property", "symbol"):
                continue
            out.append(x)
        out += findall(s, "property")
        out += [x for x in parent[2:] if isinstance(x, list) and x[0] == "symbol"]
    # rename units "<base>_a_b" -> "<name>_a_b"
    res = []
    for x in out:
        if isinstance(x, list) and x[0] == "symbol" and x is not out and x[1] != lib_id:
            x = [x[0], name + x[1][len(base_name):]] + x[2:]
        res.append(x)
    return res, body


SYMCACHE = {}


def symbol_def(lib_id):
    if lib_id not in SYMCACHE:
        SYMCACHE[lib_id] = load_symbol(lib_id)[0]
    return SYMCACHE[lib_id]


def symbol_pins(lib_id):
    s = symbol_def(lib_id)
    pins = {}
    for u in findall(s, "symbol"):
        for p in findall(u, "pin"):
            at = find(p, "at")
            num = find(p, "number")[1]
            pins.setdefault(num, (float(at[1]), float(at[2]), float(at[3])))
    return pins


def xform(x, y, rot):
    """lib coords (y up) -> schematic offset (y down), rotated CCW by rot."""
    vx, vy = x, -y
    t = math.radians(rot)
    c, s = round(math.cos(t)), round(math.sin(t))
    return vx * c + vy * s, -vx * s + vy * c


def pin_point(comp, num):
    px, py, pa = symbol_pins(comp.lib_id)[num]
    ox, oy = xform(px, py, comp.sch[2])
    dx, dy = xform(math.cos(math.radians(pa)), math.sin(math.radians(pa)), comp.sch[2])
    x, y = round(comp.sch[0] + ox, 4), round(comp.sch[1] + oy, 4)
    return (x, y), (-round(dx), -round(dy))   # outward direction


def eff(size=1.27, justify=None, hide=False):
    e = [Sym("effects"), [Sym("font"), [Sym("size"), size, size]]]
    if justify:
        e.append([Sym("justify")] + [Sym(j) for j in justify.split()])
    if hide:
        e.append(Sym("hide"))
    return e


ITEMS = []
PWR_N = [0]


def wire(a, b):
    ITEMS.append([Sym("wire"), [Sym("pts"), [Sym("xy"), a[0], a[1]], [Sym("xy"), b[0], b[1]]],
                  [Sym("stroke"), [Sym("width"), 0], [Sym("type"), Sym("default")]],
                  [Sym("uuid"), uid("w", a, b)]])


def label(name, at, out):
    angle = {(-1, 0): 180, (1, 0): 0, (0, -1): 90, (0, 1): 270}[out]
    just = "left bottom" if angle in (0, 90) else "right bottom"
    ITEMS.append([Sym("label"), name, [Sym("at"), at[0], at[1], angle],
                  [Sym("fields_autoplaced")], eff(1.27, just), [Sym("uuid"), uid("l", name, at)]])


def no_connect(at):
    ITEMS.append([Sym("no_connect"), [Sym("at"), at[0], at[1]], [Sym("uuid"), uid("nc", at)]])


def sym_instance(lib_id, ref, value, at, rot, footprint="", hidden_ref=False, in_bom=True,
                 ref_off=None, val_off=None, fields=(), hide_value=False):
    pins = symbol_pins(lib_id)
    u = uid("sym", ref)
    ro = ref_off or (2.54, -1.27)
    vo = val_off or (2.54, 1.27)
    e = [Sym("symbol"), [Sym("lib_id"), lib_id], [Sym("at"), at[0], at[1], rot],
         [Sym("unit"), 1], [Sym("in_bom"), Sym("yes" if in_bom else "no")],
         [Sym("on_board"), Sym("yes" if in_bom else "no")], [Sym("dnp"), Sym("no")],
         [Sym("uuid"), u],
         [Sym("property"), "Reference", ref, [Sym("at"), at[0] + ro[0], at[1] + ro[1], 0],
          eff(1.27, "left", hide=hidden_ref)],
         [Sym("property"), "Value", value, [Sym("at"), at[0] + vo[0], at[1] + vo[1], 0],
          eff(1.27, "left", hide=hide_value)],
         [Sym("property"), "Footprint", footprint, [Sym("at"), at[0], at[1], 0], eff(1.27, hide=True)],
         [Sym("property"), "Datasheet", "~", [Sym("at"), at[0], at[1], 0], eff(1.27, hide=True)]]
    for k, v in fields:
        e.append([Sym("property"), k, v, [Sym("at"), at[0], at[1], 0], eff(1.27, hide=True)])
    for num in sorted(pins):
        e.append([Sym("pin"), num, [Sym("uuid"), uid("pin", ref, num)]])
    e.append([Sym("instances"), [Sym("project"), NAME,
                                 [Sym("path"), "/" + ROOT_UUID, [Sym("reference"), ref],
                                  [Sym("unit"), 1]]]])
    ITEMS.append(e)
    return u


def power_symbol(net, at, out):
    PWR_N[0] += 1
    lib_id = "power:" + net
    if net == "GND":
        rot = {(0, 1): 0, (0, -1): 180, (1, 0): 90, (-1, 0): 270}[out]
    else:
        rot = {(0, -1): 0, (0, 1): 180, (-1, 0): 90, (1, 0): 270}[out]
    sym_instance(lib_id, "#PWR%03d" % PWR_N[0], net, at, rot, hidden_ref=True, in_bom=False,
                 ref_off=(0, 3.81), val_off=(0, 3.81 if net == "GND" else -3.81))


# Pins that the writer must not touch (handled specially)
SPECIAL = set()


def rp2040_power_bus(u1):
    """Join the stacked supply pins on top of the RP2040 with short wires."""
    groups = {}
    for num, net in u1.pins.items():
        if net in ("+3V3", "+1V1"):
            pt, out = pin_point(u1, num)
            groups.setdefault(net, set()).add(pt)
            SPECIAL.add((u1.ref, num))
    for net, pts in groups.items():
        pts = sorted(pts)
        h = 5.08 if net == "+3V3" else 2.54
        tops = []
        for p in pts:
            top = (p[0], round(p[1] - h, 4))
            wire(p, top)
            tops.append(top)
        for a, b in zip(tops, tops[1:]):
            wire(a, b)
        for t in tops[1:-1]:
            ITEMS.append([Sym("junction"), [Sym("at"), t[0], t[1]], [Sym("diameter"), 0],
                          [Sym("color"), 0, 0, 0, 0], [Sym("uuid"), uid("j", t)]])
        power_symbol(net, tops[len(tops) // 2] if net == "+3V3" else tops[0], (0, -1))


def write_schematic():
    u1 = next(c for c in COMPS if c.ref == "U1")
    rp2040_power_bus(u1)
    placed = {}
    for c in COMPS:
        fields = ()
        if c.ref.startswith("SW") and c.ref[2:].isdigit() and int(c.ref[2:]) <= len(KEYS):
            k = KEYS[int(c.ref[2:]) - 1]
            fields = (("Matrix", "R%d C%d" % (k["row"], k["col"])),)
        rot = c.sch[2]
        if c.lib_id.startswith("power:"):
            sym_instance(c.lib_id, c.ref, c.value, (c.sch[0], c.sch[1]), rot, hidden_ref=True,
                         in_bom=False, val_off=(0, -3.81))
            pt, out = pin_point(c, "1")
            power_symbol(c.pins["1"], pt, (0, -1)) if c.pins["1"] in POWER_NETS else \
                label(c.pins["1"], pt, (0, 1))
            continue
        ref_off = val_off = None
        if c.lib_id in ("Device:R", "Device:C", "Device:Polyfuse") and rot == 0:
            ref_off, val_off = (2.54, -1.27), (2.54, 1.27)
        if c.lib_id == "Switch:SW_Push" and rot == 0:
            ref_off, val_off = (-2.54, -3.81), (-2.54, 2.54)
        if c.lib_id == "Device:D" and rot == 90:
            ref_off, val_off = (-1.27, 3.81), (1.27, 1.27)
        if c.lib_id == "Device:LED" and rot == 0:
            ref_off, val_off = (-2.54, -3.81), (-2.54, 3.81)
        if c.ref == "U1":
            ref_off, val_off = (-25.4, -52.07), (-25.4, -49.53)
        sym_instance(c.lib_id, c.ref, c.value, (c.sch[0], c.sch[1]), rot, c.footprint,
                     in_bom=c.in_bom, ref_off=ref_off, val_off=val_off, fields=fields,
                     hide_value=(c.lib_id == "Device:D"))
        for num, net in c.pins.items():
            if (c.ref, num) in SPECIAL:
                continue
            pt, out = pin_point(c, num)
            if (c.ref, num) in INTERNAL:
                continue
            key = (pt, net)
            if key in placed:
                continue          # stacked pins: one label is enough
            placed[key] = True
            if net is None:
                no_connect(pt)
            elif net in POWER_NETS:
                end = (round(pt[0] + out[0] * 2.54, 4), round(pt[1] + out[1] * 2.54, 4))
                wire(pt, end)
                power_symbol(net, end, out)
            else:
                label(net, pt, out)

    # section titles
    def text(s, x, y, size=3.0):
        ITEMS.append([Sym("text"), s, [Sym("at"), x, y, 0], eff(size, "left bottom"),
                      [Sym("uuid"), uid("t", s)]])
    text("KEY MATRIX  (6 rows x 21 cols, COL2ROW, 1N4148W per key)", 25.4, 38.1)
    text("PER-KEY BACKLIGHT  (3 mm LED + 1k per key, PWM sink Q1)", 25.4, 177.8)
    text("MCU  RP2040 + 16 MB QSPI flash", 25.4, 337.82)
    text("USB-C / ESD / 3.3 V", 254.0, 337.82)
    text("BACKLIGHT DRIVER", 419.1, 337.82)
    text("LOCK INDICATORS", 482.6, 337.82)

    libs = []
    seen = set()
    for c in COMPS:
        if c.lib_id not in seen:
            seen.add(c.lib_id)
            libs.append(symbol_def(c.lib_id))
    for net in POWER_NETS:
        lid = "power:" + net
        if lid not in seen:
            seen.add(lid)
            libs.append(symbol_def(lid))

    sch = [Sym("kicad_sch"), [Sym("version"), Sym("20230121")], [Sym("generator"), Sym("eeschema")],
           [Sym("uuid"), ROOT_UUID], [Sym("paper"), "A1"],
           [Sym("title_block"), [Sym("title"), "HOM full-size keyboard (ANSI 104)"],
            [Sym("date"), "2026-11-25"], [Sym("rev"), "0.1"],
            [Sym("comment"), 1, "RP2040 / QMK, per-key LED backlight, 6x21 matrix"]],
           [Sym("lib_symbols")] + libs] + ITEMS + [
        [Sym("sheet_instances"), [Sym("path"), "/", [Sym("page"), "1"]]]]
    with open(SCH, "w") as f:
        f.write(dump(sch) + "\n")


# --------------------------------------------------------------------------
# Netlist (from KiCad itself) -> PCB
# --------------------------------------------------------------------------
def export_netlist():
    os.makedirs(os.path.dirname(NET), exist_ok=True)
    subprocess.run(["kicad-cli", "sch", "export", "netlist", "--format", "kicadsexpr",
                    "-o", NET, SCH], check=True, stdout=subprocess.DEVNULL)
    d = parse(open(NET).read())
    comps = {}
    for c in findall(find(d, "components"), "comp"):
        ref = find(c, "ref")[1]
        tst = find(c, "tstamps")
        comps[ref] = dict(fp=find(c, "footprint")[1] if find(c, "footprint") else "",
                          value=find(c, "value")[1], tstamp=tst[1] if tst else None)
    nets = {}
    for n in findall(find(d, "nets"), "net"):
        name = find(n, "name")[1]
        for node in findall(n, "node"):
            nets[(find(node, "ref")[1], find(node, "pin")[1])] = name
    return comps, nets


def board_outline(board):
    x1, y1 = X0 - MARGIN, Y0 - MARGIN
    x2, y2 = X0 + BOARD_W + MARGIN, Y0 + BOARD_H + MARGIN
    r = 2.0
    pts = [(x1 + r, y1), (x2 - r, y1), (x2, y1 + r), (x2, y2 - r), (x2 - r, y2), (x1 + r, y2),
           (x1, y2 - r), (x1, y1 + r)]
    lines = [(pts[0], pts[1]), (pts[2], pts[3]), (pts[4], pts[5]), (pts[6], pts[7])]
    for a, b in lines:
        s = pcbnew.PCB_SHAPE(board)
        s.SetShape(pcbnew.SHAPE_T_SEGMENT)
        s.SetStart(vec(*a))
        s.SetEnd(vec(*b))
        s.SetLayer(pcbnew.Edge_Cuts)
        s.SetWidth(mm(0.1))
        board.Add(s)
    for c, a, b in (((x2 - r, y1 + r), pts[1], pts[2]), ((x2 - r, y2 - r), pts[3], pts[4]),
                    ((x1 + r, y2 - r), pts[5], pts[6]), ((x1 + r, y1 + r), pts[7], pts[0])):
        s = pcbnew.PCB_SHAPE(board)
        s.SetShape(pcbnew.SHAPE_T_ARC)
        s.SetCenter(vec(*c))
        s.SetStart(vec(*a))
        s.SetArcAngleAndEnd(pcbnew.EDA_ANGLE(90, pcbnew.DEGREES_T), True)
        s.SetLayer(pcbnew.Edge_Cuts)
        s.SetWidth(mm(0.1))
        board.Add(s)
    return (x1, y1, x2, y2)


def obstacles(board):
    """(x, y, r) circles around every pad and footprint courtyard corner."""
    obs = []
    for fp in board.GetFootprints():
        for p in fp.Pads():
            pos = p.GetPosition()
            sz = p.GetSize()
            r = max(pcbnew.ToMM(sz.x), pcbnew.ToMM(sz.y), pcbnew.ToMM(p.GetDrillSize().x)) / 2
            obs.append((pcbnew.ToMM(pos.x), pcbnew.ToMM(pos.y), r))
        if not fp.GetReference().startswith(("SW", "LD")):
            bb = fp.GetBoundingBox(False, False)
            x1, y1 = pcbnew.ToMM(bb.GetX()), pcbnew.ToMM(bb.GetY())
            w, h = pcbnew.ToMM(bb.GetWidth()), pcbnew.ToMM(bb.GetHeight())
            for i in range(5):
                for j in range(5):
                    obs.append((x1 + w * i / 4, y1 + h * j / 4, 0.3))
    return obs


def add_mounting_holes(board, edge):
    want = [(1.5, 0.5), (5.75, 0.5), (10.75, 0.5), (3.0, 3.5), (8.0, 2.5), (12.5, 3.5),
            (2.0, 5.5), (7.0, 5.0), (13.0, 5.5), (16.75, 3.8), (19.0, 3.5), (21.0, 5.0)]
    obs = obstacles(board)
    holes = []
    for wx, wy in want:
        tx, ty = X0 + wx * U, Y0 + wy * U
        best = None
        for i in range(-40, 41):
            for j in range(-40, 41):
                x, y = tx + i * 0.25, ty + j * 0.25
                if not (edge[0] + 4 < x < edge[2] - 4 and edge[1] + 4 < y < edge[3] - 4):
                    continue
                ok = all(math.hypot(x - ox, y - oy) - r >= 3.4 for ox, oy, r in obs)
                ok = ok and all(abs(x - X0 - k["mm"][0]) > 9.4 or abs(y - Y0 - k["mm"][1]) > 9.4
                                for k in KEYS)
                ok = ok and all(math.hypot(x - hx, y - hy) > 20 for hx, hy in holes)
                if ok:
                    d = math.hypot(x - tx, y - ty)
                    if best is None or d < best[0]:
                        best = (d, x, y)
        if best:
            holes.append((best[1], best[2]))
    for i, (x, y) in enumerate(holes):
        fp = load_fp("MountingHole:MountingHole_2.2mm_M2")
        fp.SetReference("H%d" % (i + 1))
        fp.SetValue("M2")
        board.Add(fp)
        fp.SetPosition(vec(x, y))
    return holes


def build_pcb(comps, nets):
    board = pcbnew.NewBoard(PCB)
    ds = board.GetDesignSettings()
    ds.SetCopperLayerCount(2)
    ds.m_TrackMinWidth = mm(0.2)
    ds.m_MinClearance = mm(0.15)
    ds.m_ViasMinSize = mm(0.6)
    ds.m_MinThroughDrill = mm(0.3)
    ds.m_HoleToHoleMin = mm(0.25)
    ds.m_CopperEdgeClearance = mm(0.3)
    nc = ds.m_NetSettings.m_DefaultNetClass
    nc.SetClearance(mm(0.15))
    nc.SetTrackWidth(mm(0.2))
    nc.SetViaDiameter(mm(0.6))
    nc.SetViaDrill(mm(0.3))

    edge = board_outline(board)

    netobjs = {}
    for name in sorted(set(nets.values())):
        ni = pcbnew.NETINFO_ITEM(board, name)
        board.Add(ni)
        netobjs[name] = ni

    by_ref = {c.ref: c for c in COMPS}
    for ref, info in sorted(comps.items()):
        c = by_ref.get(ref)
        if c is None or c.pcb is None or not info["fp"]:
            continue
        fp = load_fp(info["fp"])
        fp.SetReference(ref)
        fp.SetValue(info["value"])
        if info["tstamp"]:
            fp.SetPath(pcbnew.KIID_PATH("/" + info["tstamp"]))
        board.Add(fp)
        x, y, rot = c.pcb
        if c.ref == "J1":
            # opening at the top board edge
            place_fp(board, fp, x, 0, 180, c.side)
            bb = fp.GetBoundingBox(False, False)
            top = pcbnew.ToMM(bb.GetY())
            fp.Move(vec(0, (Y0 - MARGIN) - top - 0.0))
        else:
            place_fp(board, fp, x, y, rot, c.side)
        if ref.startswith("LD") and int(ref[2:]) <= len(KEYS):
            # key LEDs sit inside the switch's LED slot: drop their courtyard
            for item in list(fp.GraphicalItems()):
                if item.GetLayer() in (pcbnew.F_CrtYd, pcbnew.B_CrtYd):
                    item.SetLayer(pcbnew.Dwgs_User)
        if ref == "J1":
            fp.Reference().SetVisible(False)
        for p in fp.Pads():
            if p.GetAttribute() == pcbnew.PAD_ATTRIB_PTH and ref == "U1":
                p.SetDrillSize(pcbnew.VECTOR2I(mm(0.3), mm(0.3)))
                p.SetSize(pcbnew.VECTOR2I(mm(0.6), mm(0.6)))
            net = nets.get((ref, p.GetNumber()))
            if net:
                p.SetNet(netobjs[net])
        # keep switch silkscreen readable: hide values except on switches
        fp.Value().SetVisible(False)
        if ref.startswith(("D", "R", "C")) and ref[1:].isdigit():
            fp.Reference().SetTextSize(pcbnew.VECTOR2I(mm(0.8), mm(0.8)))
            fp.Reference().SetTextThickness(mm(0.12))

    holes = add_mounting_holes(board, edge)

    # silkscreen title
    t = pcbnew.PCB_TEXT(board)
    t.SetText("HOM-104  rev 0.1  RP2040 / QMK")
    t.SetPosition(vec(X0 + 8.0 * U, Y0 + 1.25 * U))
    t.SetLayer(pcbnew.B_SilkS)
    t.SetMirrored(True)
    t.SetTextSize(pcbnew.VECTOR2I(mm(1.5), mm(1.5)))
    t.SetTextThickness(mm(0.25))
    board.Add(t)

    board.Save(PCB)
    return holes


# --------------------------------------------------------------------------
# QMK keyboard.json
# --------------------------------------------------------------------------
def gp(f):
    return "GP%d" % GPIO_OF[f]


def write_qmk():
    out = os.path.join(PROJ, "firmware", "qmk", "hom104")
    os.makedirs(os.path.join(out, "keymaps", "default"), exist_ok=True)
    layout = []
    for k in KEYS:
        item = {"label": k["label"], "matrix": [k["row"], k["col"]], "x": k["x"], "y": k["y"]}
        if k["w"] != 1:
            item["w"] = k["w"]
        if k["h"] != 1:
            item["h"] = k["h"]
        layout.append(item)
    kb = {
        "manufacturer": "HOM",
        "keyboard_name": "HOM-104",
        "maintainer": "hom",
        "processor": "RP2040",
        "bootloader": "rp2040",
        "usb": {"vid": "0xFEED", "pid": "0x0104", "device_version": "0.1.0"},
        "diode_direction": "COL2ROW",
        "matrix_pins": {"cols": [gp("COL%d" % c) for c in range(NCOLS)],
                        "rows": [gp("ROW%d" % r) for r in range(NROWS)]},
        "features": {"bootmagic": True, "extrakey": True, "mousekey": False,
                     "nkro": True, "backlight": True},
        "backlight": {"driver": "pwm", "pin": gp("BL_PWM"), "levels": 6, "breathing": True},
        "indicators": {"caps_lock": gp("LED_CAPS"), "num_lock": gp("LED_NUM"), "on_state": 1},
        "layouts": {"LAYOUT_fullsize_ansi": {"layout": layout}},
    }
    with open(os.path.join(out, "keyboard.json"), "w") as f:
        json.dump(kb, f, indent=4)
        f.write("\n")
    rows = []
    for r in range(NROWS):
        rows.append(", ".join(keycode(k["label"]) for k in KEYS if k["row"] == r))
    keymap = ("// Default keymap for the HOM-104 (ANSI full size)\n"
              "#include QMK_KEYBOARD_H\n\n"
              "const uint16_t PROGMEM keymaps[][MATRIX_ROWS][MATRIX_COLS] = {\n"
              "    [0] = LAYOUT_fullsize_ansi(\n        "
              + ",\n        ".join(rows) + "\n    )\n};\n")
    with open(os.path.join(out, "keymaps", "default", "keymap.c"), "w") as f:
        f.write(keymap)
    with open(os.path.join(out, "mcuconf.h"), "w") as f:
        f.write("#pragma once\n#include_next <mcuconf.h>\n\n"
                "// Backlight PWM\n#undef RP_PWM_USE_PWM%d\n#define RP_PWM_USE_PWM%d TRUE\n"
                % ((GPIO_OF["BL_PWM"] // 2) % 8, (GPIO_OF["BL_PWM"] // 2) % 8))
    with open(os.path.join(out, "halconf.h"), "w") as f:
        f.write("#pragma once\n#define HAL_USE_PWM TRUE\n#include_next <halconf.h>\n")
    with open(os.path.join(out, "config.h"), "w") as f:
        f.write("#pragma once\n\n#define BACKLIGHT_PWM_DRIVER PWMD%d\n#define BACKLIGHT_PWM_CHANNEL RP2040_PWM_CHANNEL_%s\n"
                "#define RP2040_BOOTLOADER_DOUBLE_TAP_RESET\n"
                % ((GPIO_OF["BL_PWM"] // 2) % 8, "A" if GPIO_OF["BL_PWM"] % 2 == 0 else "B"))


def write_project():
    pro = {
        "board": {"design_settings": {
            "rules": {"min_clearance": 0.15, "min_track_width": 0.2, "min_via_diameter": 0.6,
                      "min_through_hole_diameter": 0.3, "min_copper_edge_clearance": 0.3,
                      "min_hole_to_hole": 0.25}}},
        "meta": {"filename": NAME + ".kicad_pro", "version": 1},
        "net_settings": {
            "classes": [
                {"name": "Default", "clearance": 0.15, "track_width": 0.2, "via_diameter": 0.6,
                 "via_drill": 0.3, "wire_width": 6, "bus_width": 12, "schematic_color": "rgba(0, 0, 0, 0.000)",
                 "pcb_color": "rgba(0, 0, 0, 0.000)", "diff_pair_gap": 0.25, "diff_pair_via_gap": 0.25,
                 "diff_pair_width": 0.2, "line_style": 0, "microvia_diameter": 0.3, "microvia_drill": 0.1},
                {"name": "Power", "clearance": 0.2, "track_width": 0.5, "via_diameter": 0.8,
                 "via_drill": 0.4, "wire_width": 6, "bus_width": 12, "schematic_color": "rgba(0, 0, 0, 0.000)",
                 "pcb_color": "rgba(0, 0, 0, 0.000)", "diff_pair_gap": 0.25, "diff_pair_via_gap": 0.25,
                 "diff_pair_width": 0.2, "line_style": 0, "microvia_diameter": 0.3, "microvia_drill": 0.1},
                {"name": "USB", "clearance": 0.15, "track_width": 0.3, "via_diameter": 0.6,
                 "via_drill": 0.3, "wire_width": 6, "bus_width": 12, "schematic_color": "rgba(0, 0, 0, 0.000)",
                 "pcb_color": "rgba(0, 0, 0, 0.000)", "diff_pair_gap": 0.15, "diff_pair_via_gap": 0.25,
                 "diff_pair_width": 0.3, "line_style": 0, "microvia_diameter": 0.3, "microvia_drill": 0.1},
            ],
            "meta": {"version": 3},
            "netclass_patterns": [
                {"netclass": "Power", "pattern": n} for n in ("GND", "+5V", "/VBUS", "/BL_K", "+3V3")
            ] + [{"netclass": "USB", "pattern": n} for n in ("/USB_D*",)],
        },
        "pcbnew": {"last_paths": {}},
        "schematic": {"legacy_lib_dir": "", "legacy_lib_list": []},
        "sheets": [[ROOT_UUID, ""]],
    }
    with open(os.path.join(PROJ, NAME + ".kicad_pro"), "w") as f:
        json.dump(pro, f, indent=2)
        f.write("\n")


if __name__ == "__main__":
    write_project()
    write_schematic()
    comps, nets = export_netlist()
    # sanity: every comp with pins must be in the netlist
    missing = [c.ref for c in COMPS if c.in_bom and c.ref not in comps]
    assert not missing, missing
    holes = build_pcb(comps, nets)
    write_qmk()
    print("MCU rotation", MCU_ROT)
    print("GPIO map", {f: GPIO_OF[f] for f in sorted(GPIO_OF)})
    print("components", len(comps), "nets", len(set(nets.values())), "holes", len(holes))
