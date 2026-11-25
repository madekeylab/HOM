"""ANSI 104-key full-size layout and key-matrix assignment.

Coordinates are in key units (1u = 19.05 mm), KLE style: (x, y) is the
top-left corner of the key, (w, h) its size.
"""

U = 19.05

# (label, x, y, w, h) per physical row
ROWS = [
    # Row 0: function row
    [("Esc", 0, 0, 1, 1)]
    + [("F%d" % (i + 1), 2 + i, 0, 1, 1) for i in range(4)]
    + [("F%d" % (i + 5), 6.5 + i, 0, 1, 1) for i in range(4)]
    + [("F%d" % (i + 9), 11 + i, 0, 1, 1) for i in range(4)]
    + [("PrtSc", 15.25, 0, 1, 1), ("ScrLk", 16.25, 0, 1, 1), ("Pause", 17.25, 0, 1, 1)],
    # Row 1: number row
    [("`", 0, 1.5, 1, 1)]
    + [(c, 1 + i, 1.5, 1, 1) for i, c in enumerate("1234567890")]
    + [("-", 11, 1.5, 1, 1), ("=", 12, 1.5, 1, 1), ("Bksp", 13, 1.5, 2, 1)]
    + [("Ins", 15.25, 1.5, 1, 1), ("Home", 16.25, 1.5, 1, 1), ("PgUp", 17.25, 1.5, 1, 1)]
    + [("NumLk", 18.5, 1.5, 1, 1), ("P/", 19.5, 1.5, 1, 1), ("P*", 20.5, 1.5, 1, 1), ("P-", 21.5, 1.5, 1, 1)],
    # Row 2: QWERTY row
    [("Tab", 0, 2.5, 1.5, 1)]
    + [(c, 1.5 + i, 2.5, 1, 1) for i, c in enumerate("QWERTYUIOP")]
    + [("[", 11.5, 2.5, 1, 1), ("]", 12.5, 2.5, 1, 1), ("\\", 13.5, 2.5, 1.5, 1)]
    + [("Del", 15.25, 2.5, 1, 1), ("End", 16.25, 2.5, 1, 1), ("PgDn", 17.25, 2.5, 1, 1)]
    + [("P7", 18.5, 2.5, 1, 1), ("P8", 19.5, 2.5, 1, 1), ("P9", 20.5, 2.5, 1, 1), ("P+", 21.5, 2.5, 1, 2)],
    # Row 3: home row
    [("Caps", 0, 3.5, 1.75, 1)]
    + [(c, 1.75 + i, 3.5, 1, 1) for i, c in enumerate("ASDFGHJKL;'")]
    + [("Enter", 12.75, 3.5, 2.25, 1)]
    + [("P4", 18.5, 3.5, 1, 1), ("P5", 19.5, 3.5, 1, 1), ("P6", 20.5, 3.5, 1, 1)],
    # Row 4: shift row
    [("LShift", 0, 4.5, 2.25, 1)]
    + [(c, 2.25 + i, 4.5, 1, 1) for i, c in enumerate("ZXCVBNM,./")]
    + [("RShift", 12.25, 4.5, 2.75, 1), ("Up", 16.25, 4.5, 1, 1)]
    + [("P1", 18.5, 4.5, 1, 1), ("P2", 19.5, 4.5, 1, 1), ("P3", 20.5, 4.5, 1, 1), ("PEnt", 21.5, 4.5, 1, 2)],
    # Row 5: bottom row
    [("LCtrl", 0, 5.5, 1.25, 1), ("LWin", 1.25, 5.5, 1.25, 1), ("LAlt", 2.5, 5.5, 1.25, 1),
     ("Space", 3.75, 5.5, 6.25, 1), ("RAlt", 10, 5.5, 1.25, 1), ("RWin", 11.25, 5.5, 1.25, 1),
     ("Menu", 12.5, 5.5, 1.25, 1), ("RCtrl", 13.75, 5.5, 1.25, 1),
     ("Left", 15.25, 5.5, 1, 1), ("Down", 16.25, 5.5, 1, 1), ("Right", 17.25, 5.5, 1, 1),
     ("P0", 18.5, 5.5, 2, 1), ("P.", 20.5, 5.5, 1, 1)],
]

NCOLS = 21
NROWS = len(ROWS)

# QMK keycodes for the default keymap
KEYCODES = {
    "Esc": "KC_ESC", "PrtSc": "KC_PSCR", "ScrLk": "KC_SCRL", "Pause": "KC_PAUS",
    "`": "KC_GRV", "-": "KC_MINS", "=": "KC_EQL", "Bksp": "KC_BSPC",
    "Ins": "KC_INS", "Home": "KC_HOME", "PgUp": "KC_PGUP", "NumLk": "KC_NUM",
    "P/": "KC_PSLS", "P*": "KC_PAST", "P-": "KC_PMNS", "Tab": "KC_TAB",
    "[": "KC_LBRC", "]": "KC_RBRC", "\\": "KC_BSLS", "Del": "KC_DEL", "End": "KC_END",
    "PgDn": "KC_PGDN", "P+": "KC_PPLS", "Caps": "KC_CAPS", ";": "KC_SCLN", "'": "KC_QUOT",
    "Enter": "KC_ENT", "LShift": "KC_LSFT", ",": "KC_COMM", ".": "KC_DOT", "/": "KC_SLSH",
    "RShift": "KC_RSFT", "Up": "KC_UP", "PEnt": "KC_PENT", "LCtrl": "KC_LCTL",
    "LWin": "KC_LGUI", "LAlt": "KC_LALT", "Space": "KC_SPC", "RAlt": "KC_RALT",
    "RWin": "KC_RGUI", "Menu": "KC_APP", "RCtrl": "KC_RCTL", "Left": "KC_LEFT",
    "Down": "KC_DOWN", "Right": "KC_RGHT", "P.": "KC_PDOT",
}


def keycode(label):
    if label in KEYCODES:
        return KEYCODES[label]
    if label.startswith("F") and label[1:].isdigit():
        return "KC_" + label
    if label.startswith("P") and label[1:].isdigit():
        return "KC_P" + label[1:]
    if len(label) == 1 and label.isalnum():
        return "KC_" + label.upper()
    raise KeyError(label)


def _assign_cols(keys, slots):
    """Monotone assignment of keys (sorted by x) to column slots minimising
    the horizontal distance (simple DP)."""
    n, m = len(keys), len(slots)
    INF = float("inf")
    dp = [[INF] * (m + 1) for _ in range(n + 1)]
    choice = [[False] * (m + 1) for _ in range(n + 1)]
    for j in range(m + 1):
        dp[0][j] = 0
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            skip = dp[i][j - 1]
            take = dp[i - 1][j - 1] + abs(keys[i - 1] - slots[j - 1])
            if take <= skip:
                dp[i][j], choice[i][j] = take, True
            else:
                dp[i][j] = skip
    res, i, j = [], n, m
    while i > 0:
        if choice[i][j]:
            res.append(j - 1)
            i -= 1
        j -= 1
    return res[::-1]


def build_keys():
    """Return a list of dicts: label, x, y, w, h, cx, cy (u), row, col."""
    slots = [x + w / 2 for (_, x, _, w, _) in ROWS[1]]
    assert len(slots) == NCOLS
    keys = []
    for r, row in enumerate(ROWS):
        centers = [x + w / 2 for (_, x, _, w, _) in row]
        cols = _assign_cols(centers, slots)
        for (label, x, y, w, h), c in zip(row, cols):
            keys.append(dict(label=label, x=x, y=y, w=w, h=h,
                             cx=x + w / 2, cy=y + h / 2, row=r, col=c))
    seen = set()
    for k in keys:
        assert (k["row"], k["col"]) not in seen
        seen.add((k["row"], k["col"]))
    return keys


if __name__ == "__main__":
    ks = build_keys()
    print(len(ks), "keys")
    for r in range(NROWS):
        print(r, [(k["label"], k["col"]) for k in ks if k["row"] == r])
