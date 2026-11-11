"""Liest das App-Icon aus einer APK (über resources.arsc). Nur Standardbibliothek.

Release-Builds benennen Ressourcen um (res/0Z.png statt res/mipmap-xxxhdpi/ic_launcher.png). Deshalb wird die
Icon-Ressource aus dem Manifest über die Ressourcen-Tabelle aufgelöst. Gibt es Bitmaps je Bildschirmdichte, wird die
größte genommen. Sonst wird ein adaptives Icon bzw. VectorDrawable in ein SVG umgerechnet (Hintergrund + Vordergrund,
abgerundet wie ein Launcher-Icon).
"""

import struct
import zipfile

import apk_info

RES_TABLE_TYPE = 0x0002
RES_TABLE_PACKAGE_TYPE = 0x0200
RES_TABLE_TYPE_TYPE = 0x0201
TYPE_STRING = 0x03
TYPE_REFERENCE = 0x01
FLAG_SPARSE = 0x01
FLAG_OFFSET16 = 0x02
ENTRY_COMPLEX = 0x0001
ENTRY_COMPACT = 0x0008
BITMAP_EXT = (".png", ".webp", ".jpg", ".jpeg")
MAX_ICON_BYTES = 1024 * 1024


class ResourceTable:
    """Minimaler Leser für resources.arsc: Ressourcen-ID -> [(Dichte, Wert)]."""

    def __init__(self, data: bytes):
        self.data = data
        self.strings: list = []
        self.entries: dict = {}   # res_id -> [(density, dtype, value)]
        typ, header_size, _, _ = struct.unpack_from("<HHII", data, 0)
        if typ != RES_TABLE_TYPE:
            raise apk_info.ApkError("resources.arsc hat ein unbekanntes Format")
        pos = header_size
        while pos + 8 <= len(data):
            ctype, chead, csize = struct.unpack_from("<HHI", data, pos)
            if csize < 8:
                break
            if ctype == apk_info.RES_STRING_POOL_TYPE and not self.strings:
                self.strings = apk_info._decode_strings(data, pos)
            elif ctype == RES_TABLE_PACKAGE_TYPE:
                self._package(pos, chead, csize)
            pos += csize

    def _package(self, start, head, size):
        package_id = struct.unpack_from("<I", self.data, start + 8)[0]
        pos = start + head
        end = start + size
        while pos + 8 <= end:
            ctype, chead, csize = struct.unpack_from("<HHI", self.data, pos)
            if csize < 8:
                break
            if ctype == RES_TABLE_TYPE_TYPE:
                self._type(package_id, pos, chead)
            pos += csize

    def _type(self, package_id, start, head):
        d = self.data
        type_id, flags, _, entry_count, entries_start = struct.unpack_from("<BBHII", d, start + 8)
        density = struct.unpack_from("<H", d, start + 20 + 14)[0]  # ResTable_config.density
        offsets_at = start + head
        base = start + entries_start
        if flags & FLAG_SPARSE:
            pairs = [struct.unpack_from("<HH", d, offsets_at + 4 * i) for i in range(entry_count)]
            items = [(idx, off * 4) for idx, off in pairs]
        elif flags & FLAG_OFFSET16:
            raw = struct.unpack_from(f"<{entry_count}H", d, offsets_at)
            items = [(i, o * 4) for i, o in enumerate(raw) if o != 0xFFFF]
        else:
            raw = struct.unpack_from(f"<{entry_count}I", d, offsets_at)
            items = [(i, o) for i, o in enumerate(raw) if o != 0xFFFFFFFF]
        for idx, off in items:
            pos = base + off
            size_or_key, eflags = struct.unpack_from("<HH", d, pos)
            if eflags & ENTRY_COMPACT:
                dtype, value = eflags >> 8, struct.unpack_from("<I", d, pos + 4)[0]
            elif eflags & ENTRY_COMPLEX:
                continue
            else:
                _, _, dtype, value = struct.unpack_from("<HBBI", d, pos + size_or_key)
            res_id = (package_id << 24) | (type_id << 16) | idx
            self.entries.setdefault(res_id, []).append((density, dtype, value))

    def files(self, res_id, depth=0) -> list:
        """[(Dichte, Pfad)] aller Dateien einer Ressource (Verweise werden verfolgt)."""
        result = []
        for density, dtype, value in self.entries.get(res_id, []):
            if dtype == TYPE_STRING and value < len(self.strings):
                result.append((density, self.strings[value]))
            elif dtype == TYPE_REFERENCE and depth < 5:
                result += [(density, p) for _, p in self.files(value, depth + 1)]
        return result


def _density_rank(density: int) -> int:
    if density in (0xFFFE, 0xFFFF):  # anydpi / nodpi
        return 0
    return density or 160


def _best_bitmap(files):
    bitmaps = [(_density_rank(d), p) for d, p in files if p.lower().endswith(BITMAP_EXT) and not p.endswith(".9.png")]
    return max(bitmaps)[1] if bitmaps else None


def extract_icon(path: str):
    """(bytes, Endung) des App-Icons oder None, wenn keines gefunden wird."""
    try:
        info = apk_info.read_apk_info(path)
        res_ids = [r for r in (info.get("icon"), info.get("round_icon")) if r]
        if not res_ids:
            return None
        with zipfile.ZipFile(path) as zf:
            table = ResourceTable(zf.read("resources.arsc"))
            for res_id in res_ids:
                files = table.files(res_id)
                found = _best_bitmap(files)
                if found:
                    data = zf.read(found)
                    if len(data) <= MAX_ICON_BYTES:
                        ext = found.lower().rsplit(".", 1)[-1]
                        return data, "jpg" if ext == "jpeg" else ext
                svg = _vector_icon(zf, table, files)
                if svg and len(svg) <= MAX_ICON_BYTES:
                    return svg, "svg"
    except (apk_info.ApkError, KeyError, zipfile.BadZipFile, struct.error, IndexError, OSError):
        return None
    return None


# ---------------------------------------------------------------------------
# Vektor-Icons (VectorDrawable / adaptive-icon) -> SVG
# ---------------------------------------------------------------------------

import base64  # noqa: E402
import re  # noqa: E402

COLOR_TYPES = (0x1C, 0x1D, 0x1E, 0x1F)
TYPE_FLOAT = 0x04
PATH_SAFE = re.compile(r"^[0-9A-Za-z.,+\-\s]*$")


def _float(dtype, value):
    if dtype == TYPE_FLOAT:
        return struct.unpack("<f", struct.pack("<I", value))[0]
    if dtype in (0x10, 0x11):
        return float(value)
    return None


def _num(x: float) -> str:
    return f"{x:.4f}".rstrip("0").rstrip(".") or "0"


class _SvgBuilder:
    def __init__(self, zf, table):
        self.zf = zf
        self.table = table

    def color(self, dtype, value, depth=0):
        """(css-Farbe, Deckkraft) oder None."""
        if dtype in COLOR_TYPES:
            a = (value >> 24) & 0xFF if dtype in (0x1C, 0x1E) else 0xFF
            return f"#{value & 0xFFFFFF:06x}", a / 255
        if dtype == TYPE_REFERENCE and depth < 5:
            for _, t, v in self.table.entries.get(value, []):
                found = self.color(t, v, depth + 1)
                if found:
                    return found
        return None

    def layer(self, dtype, value, size=108.0):
        """SVG-Inhalt einer Ebene (Farbe, Vektor oder Bitmap) im 108er-Raster."""
        col = self.color(dtype, value)
        if col:
            return f'<rect width="{_num(size)}" height="{_num(size)}" fill="{col[0]}" fill-opacity="{_num(col[1])}"/>'
        if dtype != TYPE_REFERENCE:
            return ""
        files = self.table.files(value)
        bitmap = _best_bitmap(files)
        if bitmap:
            data = self.zf.read(bitmap)
            mime = "image/webp" if bitmap.lower().endswith(".webp") else "image/png"
            return (f'<image width="{_num(size)}" height="{_num(size)}" '
                    f'href="data:{mime};base64,{base64.b64encode(data).decode()}"/>')
        for _, path in files:
            if path.endswith(".xml"):
                inner = self.vector(self.zf.read(path), size)
                if inner:
                    return inner
        return ""

    def vector(self, xml: bytes, size: float):
        out, depth_stack = [], []
        width = height = None
        for kind, name, attrs in apk_info.iter_events(xml):
            if kind == "end":
                if name == "group" and depth_stack:
                    out.append(depth_stack.pop())
                elif name == "vector":
                    out.append("</svg>")
                continue
            a = {n: (t, v, raw) for n, _, raw, t, v in attrs}

            def f(key, default=None):
                if key not in a:
                    return default
                val = _float(a[key][0], a[key][1])
                return default if val is None else val
            if name == "vector":
                width, height = f("viewportWidth", 108.0), f("viewportHeight", 108.0)
                out.append(f'<svg width="{_num(size)}" height="{_num(size)}" '
                           f'viewBox="0 0 {_num(width)} {_num(height)}">')
            elif name == "group":
                px, py = f("pivotX", 0.0), f("pivotY", 0.0)
                transform = (f"translate({_num(f('translateX', 0.0) + px)} {_num(f('translateY', 0.0) + py)}) "
                             f"rotate({_num(f('rotation', 0.0))}) scale({_num(f('scaleX', 1.0))} {_num(f('scaleY', 1.0))}) "
                             f"translate({_num(-px)} {_num(-py)})")
                out.append(f'<g transform="{transform}">')
                depth_stack.append("</g>")
            elif name in ("path", "clip-path"):
                data = (a.get("pathData") or (0, 0, None))[2]
                if not data or not PATH_SAFE.match(data) or name == "clip-path":
                    continue
                parts = [f'd="{data}"']
                fill = self.color(*a["fillColor"][:2]) if "fillColor" in a else None
                parts.append(f'fill="{fill[0]}" fill-opacity="{_num(fill[1] * f("fillAlpha", 1.0))}"'
                             if fill and fill[1] > 0 else 'fill="none"')
                stroke = self.color(*a["strokeColor"][:2]) if "strokeColor" in a else None
                if stroke and stroke[1] > 0:
                    parts.append(f'stroke="{stroke[0]}" stroke-opacity="{_num(stroke[1] * f("strokeAlpha", 1.0))}" '
                                 f'stroke-width="{_num(f("strokeWidth", 1.0))}"')
                if "fillType" in a and a["fillType"][1] == 1:
                    parts.append('fill-rule="evenodd"')
                out.append(f"<path {' '.join(parts)}/>")
        return "".join(out) if width else ""

    def adaptive(self, xml: bytes):
        layers = {}
        for name, attrs in apk_info.iter_elements(xml):
            if name in ("background", "foreground"):
                for _, _, _, dtype, value in attrs:
                    if dtype == TYPE_REFERENCE or dtype in COLOR_TYPES:
                        layers[name] = self.layer(dtype, value)
        if not layers.get("foreground"):
            return None
        return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="18 18 72 72" width="192" height="192">'
                '<defs><clipPath id="m"><rect x="18" y="18" width="72" height="72" rx="16"/></clipPath></defs>'
                f'<g clip-path="url(#m)">{layers.get("background", "")}{layers["foreground"]}</g></svg>')


def _vector_icon(zf, table, files):
    builder = _SvgBuilder(zf, table)
    for _, path in sorted(files, key=lambda x: -_density_rank(x[0])):
        if not path.endswith(".xml"):
            continue
        try:
            xml = zf.read(path)
            root = next(apk_info.iter_elements(xml))[0]
            if root == "adaptive-icon":
                svg = builder.adaptive(xml)
            elif root == "vector":
                inner = builder.vector(xml, 192)
                svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="192" height="192" viewBox="0 0 192 192">'
                       f'{inner}</svg>') if inner else None
            else:
                svg = None
            if svg:
                return svg.encode()
        except (apk_info.ApkError, KeyError, struct.error, IndexError, StopIteration):
            continue
    return None
