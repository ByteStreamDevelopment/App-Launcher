"""Minimaler QR-Code-Generator (Byte-Modus, Fehlerkorrektur M, Versionen 1–19) mit SVG-Ausgabe.

Nur Standardbibliothek. Reicht für URLs bis ca. 530 Zeichen (mit OpenCV gegengeprüft).
"""

# (Gesamtzahl Codewörter, EC-Codewörter pro Block, [(Anzahl Blöcke, Datenwörter pro Block), ...]) für Level M
_TABLE_M = {
    1: (26, 10, [(1, 16)]), 2: (44, 16, [(1, 28)]), 3: (70, 26, [(1, 44)]), 4: (100, 18, [(2, 32)]),
    5: (134, 24, [(2, 43)]), 6: (172, 16, [(4, 27)]), 7: (196, 18, [(4, 31)]),
    8: (242, 22, [(2, 38), (2, 39)]), 9: (292, 22, [(3, 36), (2, 37)]), 10: (346, 26, [(4, 43), (1, 44)]),
    11: (404, 30, [(1, 50), (4, 51)]), 12: (466, 22, [(6, 36), (2, 37)]), 13: (532, 22, [(8, 37), (1, 38)]),
    14: (581, 24, [(4, 40), (5, 41)]), 15: (655, 24, [(5, 41), (5, 42)]), 16: (733, 28, [(7, 45), (3, 46)]),
    17: (815, 28, [(10, 46), (1, 47)]), 18: (901, 26, [(9, 43), (4, 44)]), 19: (991, 26, [(3, 44), (11, 45)]),
    20: (1085, 26, [(3, 41), (13, 42)]),
}
_ALIGN = {
    1: [], 2: [6, 18], 3: [6, 22], 4: [6, 26], 5: [6, 30], 6: [6, 34], 7: [6, 22, 38], 8: [6, 24, 42],
    9: [6, 26, 46], 10: [6, 28, 50], 11: [6, 30, 54], 12: [6, 32, 58], 13: [6, 34, 62], 14: [6, 26, 46, 66],
    15: [6, 26, 48, 70], 16: [6, 26, 50, 74], 17: [6, 30, 54, 78], 18: [6, 30, 56, 82], 19: [6, 30, 58, 86],
    20: [6, 34, 62, 90],
}

# --- Reed-Solomon über GF(256) ----------------------------------------------
_EXP = [0] * 512
_LOG = [0] * 256
_x = 1
for _i in range(255):
    _EXP[_i] = _x
    _LOG[_x] = _i
    _x <<= 1
    if _x & 0x100:
        _x ^= 0x11D
for _i in range(255, 512):
    _EXP[_i] = _EXP[_i - 255]


def _gf_mul(a, b):
    return 0 if a == 0 or b == 0 else _EXP[_LOG[a] + _LOG[b]]


def _rs_generator(n):
    g = [1]
    for i in range(n):
        g = [a ^ _gf_mul(b, _EXP[i]) for a, b in zip(g + [0], [0] + g)]
    return g


def _rs_remainder(data, n):
    gen = _rs_generator(n)
    rem = list(data) + [0] * n
    for i in range(len(data)):
        coef = rem[i]
        if coef:
            for j in range(1, len(gen)):
                rem[i + j] ^= _gf_mul(gen[j], coef)
    return rem[len(data):]


# --- Daten -------------------------------------------------------------------

def _codewords(text: str):
    data = text.encode("utf-8")
    for version in range(1, 20):
        total, ec, blocks = _TABLE_M[version]
        capacity = sum(n * d for n, d in blocks)
        count_bits = 8 if version <= 9 else 16
        if 4 + count_bits + 8 * len(data) <= capacity * 8:
            break
    else:
        raise ValueError("Text zu lang für QR-Code")
    bits = [0, 1, 0, 0]  # Byte-Modus
    bits += [(len(data) >> i) & 1 for i in range(count_bits - 1, -1, -1)]
    for byte in data:
        bits += [(byte >> i) & 1 for i in range(7, -1, -1)]
    bits += [0] * min(4, capacity * 8 - len(bits))
    bits += [0] * (-len(bits) % 8)
    words = [int("".join(map(str, bits[i:i + 8])), 2) for i in range(0, len(bits), 8)]
    i = 0
    while len(words) < capacity:  # Füllbytes abwechselnd 0xEC, 0x11
        words.append(0xEC if i % 2 == 0 else 0x11)
        i += 1
    # Blöcke bilden, EC berechnen, verschränken
    data_blocks, ec_blocks, pos = [], [], 0
    for n, d in blocks:
        for _ in range(n):
            block = words[pos:pos + d]
            pos += d
            data_blocks.append(block)
            ec_blocks.append(_rs_remainder(block, ec))
    result = []
    for i in range(max(len(b) for b in data_blocks)):
        result += [b[i] for b in data_blocks if i < len(b)]
    for i in range(ec):
        result += [b[i] for b in ec_blocks]
    return version, result


# --- Matrix ------------------------------------------------------------------

def _bch(value, poly, bits):
    v = value << bits
    for i in range(v.bit_length() - 1, bits - 1, -1):
        if v >> i & 1:
            v ^= poly << (i - bits)
    return (value << bits) | v


def matrix(text: str):
    """Liefert die QR-Matrix als Liste von Listen (True = dunkel)."""
    version, words = _codewords(text)
    size = 17 + 4 * version
    m = [[None] * size for _ in range(size)]

    def put(r, c, v):
        if 0 <= r < size and 0 <= c < size:
            m[r][c] = v

    for r0, c0 in ((0, 0), (0, size - 7), (size - 7, 0)):
        for r in range(-1, 8):
            for c in range(-1, 8):
                inside = 0 <= r <= 6 and 0 <= c <= 6
                dark = inside and (r in (0, 6) or c in (0, 6) or (2 <= r <= 4 and 2 <= c <= 4))
                put(r0 + r, c0 + c, dark)
    centers = _ALIGN[version]
    corners = {(centers[0], centers[0]), (centers[0], centers[-1]), (centers[-1], centers[0])} if centers else set()
    for r in centers:
        for c in centers:
            if (r, c) in corners:  # überlappt einen Finder
                continue
            for dr in range(-2, 3):
                for dc in range(-2, 3):
                    m[r + dr][c + dc] = max(abs(dr), abs(dc)) != 1
    for i in range(8, size - 8):
        if m[6][i] is None:
            m[6][i] = i % 2 == 0
        if m[i][6] is None:
            m[i][6] = i % 2 == 0
    m[size - 8][8] = True  # dunkles Modul
    # Bereiche für Format-/Versionsinfo reservieren
    for i in range(9):
        if m[8][i] is None:
            m[8][i] = False
        if m[i][8] is None:
            m[i][8] = False
    for i in range(8):
        if m[8][size - 1 - i] is None:
            m[8][size - 1 - i] = False
        if m[size - 1 - i][8] is None:
            m[size - 1 - i][8] = False
    if version >= 7:
        info = _bch(version, 0x1F25, 12)
        for i in range(18):
            bit = bool(info >> i & 1)
            m[size - 11 + i % 3][i // 3] = bit
            m[i // 3][size - 11 + i % 3] = bit

    reserved = [[cell is not None for cell in row] for row in m]
    bits = [(w >> i) & 1 for w in words for i in range(7, -1, -1)]
    idx = 0
    col = size - 1
    upward = True
    while col > 0:
        if col == 6:
            col -= 1
        rows = range(size - 1, -1, -1) if upward else range(size)
        for r in rows:
            for c in (col, col - 1):
                if not reserved[r][c]:
                    m[r][c] = bool(bits[idx]) if idx < len(bits) else False
                    idx += 1
        upward = not upward
        col -= 2

    masks = [
        lambda r, c: (r + c) % 2 == 0, lambda r, c: r % 2 == 0, lambda r, c: c % 3 == 0,
        lambda r, c: (r + c) % 3 == 0, lambda r, c: (r // 2 + c // 3) % 2 == 0,
        lambda r, c: (r * c) % 2 + (r * c) % 3 == 0, lambda r, c: ((r * c) % 2 + (r * c) % 3) % 2 == 0,
        lambda r, c: ((r + c) % 2 + (r * c) % 3) % 2 == 0,
    ]
    best = None
    for mask_id, mask in enumerate(masks):
        cand = [row[:] for row in m]
        for r in range(size):
            for c in range(size):
                if not reserved[r][c] and mask(r, c):
                    cand[r][c] = not cand[r][c]
        _format(cand, size, mask_id)
        score = _penalty(cand, size)
        if best is None or score < best[0]:
            best = (score, cand)
    return best[1]


def _format(m, size, mask_id):
    fmt = _bch(mask_id, 0x537, 10) ^ 0x5412  # Level M hat die Formatbits 00
    bit = lambda i: bool(fmt >> i & 1)  # noqa: E731
    for i in range(6):
        m[i][8] = bit(i)
    m[7][8] = bit(6)
    m[8][8] = bit(7)
    m[8][7] = bit(8)
    for i in range(9, 15):
        m[8][14 - i] = bit(i)
    for i in range(8):
        m[8][size - 1 - i] = bit(i)
    for i in range(8, 15):
        m[size - 15 + i][8] = bit(i)
    m[size - 8][8] = True


def _penalty(m, size):
    score = 0
    for lines in (m, list(zip(*m))):
        for line in lines:
            run, prev = 0, None
            for cell in line:
                if cell == prev:
                    run += 1
                else:
                    if run >= 5:
                        score += run - 2
                    run, prev = 1, cell
            if run >= 5:
                score += run - 2
            s = "".join("1" if c else "0" for c in line)
            score += 40 * (s.count("10111010000") + s.count("00001011101"))
    for r in range(size - 1):
        for c in range(size - 1):
            if m[r][c] == m[r + 1][c] == m[r][c + 1] == m[r + 1][c + 1]:
                score += 3
    dark = sum(sum(1 for c in row if c) for row in m)
    score += abs(dark * 20 - size * size * 10) // (size * size) * 10
    return score


def svg(text: str, module: int = 6, border: int = 4, dark: str = "#111827", light: str = "#ffffff") -> str:
    """QR-Code als eigenständiges SVG."""
    mx = matrix(text)
    size = len(mx)
    full = (size + 2 * border) * module
    path = "".join(f"M{(c + border) * module},{(r + border) * module}h{module}v{module}h-{module}z"
                   for r in range(size) for c in range(size) if mx[r][c])
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {full} {full}" width="{full}" height="{full}" '
            f'shape-rendering="crispEdges"><rect width="100%" height="100%" fill="{light}"/>'
            f'<path d="{path}" fill="{dark}"/></svg>')
