"""Liest Paketname, versionName und versionCode aus einer APK (binäres AndroidManifest.xml).

Nur Standardbibliothek. Unterstützt das AXML-Format, das aapt/aapt2 erzeugen.
"""

import struct
import zipfile

RES_STRING_POOL_TYPE = 0x0001
RES_XML_TYPE = 0x0003
RES_XML_START_ELEMENT_TYPE = 0x0102
RES_XML_RESOURCE_MAP_TYPE = 0x0180
UTF8_FLAG = 0x100

ATTR_ICON = 0x01010002
ATTR_ROUND_ICON = 0x0101052C
TYPE_REFERENCE = 0x01
ATTR_VERSION_CODE = 0x0101021B
ATTR_VERSION_NAME = 0x0101021C
TYPE_STRING = 0x03
TYPE_INT_DEC = 0x10
TYPE_INT_HEX = 0x11


class ApkError(ValueError):
    pass


def read_apk_info(path: str) -> dict:
    """{"package", "version_name", "version_code", "icon" (Ressourcen-ID oder None), "round_icon"}"""
    try:
        with zipfile.ZipFile(path) as zf:
            try:
                data = zf.read("AndroidManifest.xml")
            except KeyError:
                raise ApkError("Keine gültige APK (AndroidManifest.xml fehlt)")
    except zipfile.BadZipFile:
        raise ApkError("Keine gültige APK (kein ZIP-Archiv)")
    return parse_manifest(data)


def _decode_strings(data: bytes, start: int) -> list:
    _, header_size, _, count, _, flags, strings_start, _ = struct.unpack_from("<HHIIIIII", data, start)
    utf8 = bool(flags & UTF8_FLAG)
    offsets = struct.unpack_from(f"<{count}I", data, start + header_size)
    base = start + strings_start
    result = []
    for off in offsets:
        pos = base + off
        if utf8:
            # Länge in Zeichen (1–2 Byte), dann Länge in Bytes (1–2 Byte)
            n = data[pos]
            pos += 2 if n & 0x80 else 1
            n = data[pos]
            if n & 0x80:
                n = ((n & 0x7F) << 8) | data[pos + 1]
                pos += 2
            else:
                pos += 1
            result.append(data[pos:pos + n].decode("utf-8", "replace"))
        else:
            n = struct.unpack_from("<H", data, pos)[0]
            pos += 2
            if n & 0x8000:
                n = ((n & 0x7FFF) << 16) | struct.unpack_from("<H", data, pos)[0]
                pos += 2
            result.append(data[pos:pos + n * 2].decode("utf-16-le", "replace"))
    return result


def _attributes(data, start, size, count, strings, res_ids):
    """[(name, res_id, raw_string|None, data_type, data)] eines Start-Elements."""
    result = []
    for i in range(count):
        _, name_idx, raw_idx, _, _, dtype, value = struct.unpack_from("<IIIHBBI", data, start + i * size)
        name = strings[name_idx] if 0 <= name_idx < len(strings) else ""
        res_id = res_ids[name_idx] if 0 <= name_idx < len(res_ids) else 0
        raw = strings[raw_idx] if raw_idx != 0xFFFFFFFF and raw_idx < len(strings) else None
        result.append((name, res_id, raw, dtype, value))
    return result


def iter_elements(data: bytes):
    """Liefert (Elementname, Attribute) aller Start-Elemente eines binären XML."""
    typ, header_size, _ = struct.unpack_from("<HHI", data, 0)
    if typ != RES_XML_TYPE:
        raise ApkError("Kein binäres XML")
    strings, res_ids = [], []
    pos = header_size
    while pos + 8 <= len(data):
        ctype, chead, csize = struct.unpack_from("<HHI", data, pos)
        if csize < 8:
            break
        if ctype == RES_STRING_POOL_TYPE:
            strings = _decode_strings(data, pos)
        elif ctype == RES_XML_RESOURCE_MAP_TYPE:
            res_ids = list(struct.unpack_from(f"<{(csize - chead) // 4}I", data, pos + chead))
        elif ctype == RES_XML_START_ELEMENT_TYPE:
            ext = pos + chead
            _, name_idx, attr_start, attr_size, attr_count = struct.unpack_from("<IIHHH", data, ext)
            name = strings[name_idx] if 0 <= name_idx < len(strings) else ""
            yield name, _attributes(data, ext + attr_start, attr_size, attr_count, strings, res_ids)
        pos += csize


RES_XML_END_ELEMENT_TYPE = 0x0103


def iter_events(data: bytes):
    """Wie iter_elements, aber mit End-Elementen: ("start", name, attrs) bzw. ("end", name, None)."""
    typ, header_size, _ = struct.unpack_from("<HHI", data, 0)
    if typ != RES_XML_TYPE:
        raise ApkError("Kein binäres XML")
    strings, res_ids = [], []
    pos = header_size
    while pos + 8 <= len(data):
        ctype, chead, csize = struct.unpack_from("<HHI", data, pos)
        if csize < 8:
            break
        if ctype == RES_STRING_POOL_TYPE:
            strings = _decode_strings(data, pos)
        elif ctype == RES_XML_RESOURCE_MAP_TYPE:
            res_ids = list(struct.unpack_from(f"<{(csize - chead) // 4}I", data, pos + chead))
        elif ctype == RES_XML_START_ELEMENT_TYPE:
            ext = pos + chead
            _, name_idx, attr_start, attr_size, attr_count = struct.unpack_from("<IIHHH", data, ext)
            name = strings[name_idx] if 0 <= name_idx < len(strings) else ""
            yield "start", name, _attributes(data, ext + attr_start, attr_size, attr_count, strings, res_ids)
        elif ctype == RES_XML_END_ELEMENT_TYPE:
            _, name_idx = struct.unpack_from("<II", data, pos + chead)
            yield "end", strings[name_idx] if 0 <= name_idx < len(strings) else "", None
        pos += csize


def parse_manifest(data: bytes) -> dict:
    try:
        info = None
        for name, attrs in iter_elements(data):
            if name == "manifest":
                info = _manifest_attrs(attrs)
            elif name == "application" and info is not None:
                for aname, res_id, raw, dtype, value in attrs:
                    if dtype == TYPE_REFERENCE and (res_id == ATTR_ICON or aname == "icon"):
                        info["icon"] = value
                    elif dtype == TYPE_REFERENCE and (res_id == ATTR_ROUND_ICON or aname == "roundIcon"):
                        info["round_icon"] = value
                break
    except ApkError as e:
        raise ApkError("AndroidManifest.xml ist nicht im Binärformat" if "Kein binäres" in str(e) else str(e))
    except (struct.error, IndexError) as e:
        raise ApkError(f"AndroidManifest.xml nicht lesbar ({e})")
    if info is None:
        raise ApkError("AndroidManifest.xml enthält kein <manifest>-Element")
    return info


def _manifest_attrs(attrs) -> dict:
    info = {"package": None, "version_name": None, "version_code": None, "icon": None, "round_icon": None}
    for name, res_id, raw, dtype, value in attrs:
        if name == "package":
            info["package"] = raw
        elif res_id == ATTR_VERSION_NAME or name == "versionName":
            info["version_name"] = raw
        elif res_id == ATTR_VERSION_CODE or name == "versionCode":
            if dtype in (TYPE_INT_DEC, TYPE_INT_HEX):
                info["version_code"] = value
            elif raw and raw.isdigit():
                info["version_code"] = int(raw)
    if not info["package"]:
        raise ApkError("Paketname in der APK nicht gefunden")
    return info
