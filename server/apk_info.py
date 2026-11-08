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

ATTR_VERSION_CODE = 0x0101021B
ATTR_VERSION_NAME = 0x0101021C
TYPE_STRING = 0x03
TYPE_INT_DEC = 0x10
TYPE_INT_HEX = 0x11


class ApkError(ValueError):
    pass


def read_apk_info(path: str) -> dict:
    """{"package": str, "version_name": str|None, "version_code": int|None}"""
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


def parse_manifest(data: bytes) -> dict:
    try:
        typ, header_size, _ = struct.unpack_from("<HHI", data, 0)
        if typ != RES_XML_TYPE:
            raise ApkError("AndroidManifest.xml ist nicht im Binärformat")
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
                if 0 <= name_idx < len(strings) and strings[name_idx] == "manifest":
                    return _manifest_attrs(data, ext + attr_start, attr_size, attr_count, strings, res_ids)
            pos += csize
    except (struct.error, IndexError) as e:
        raise ApkError(f"AndroidManifest.xml nicht lesbar ({e})")
    raise ApkError("AndroidManifest.xml enthält kein <manifest>-Element")


def _manifest_attrs(data, start, size, count, strings, res_ids) -> dict:
    info = {"package": None, "version_name": None, "version_code": None}
    for i in range(count):
        _, name_idx, raw_idx, _, _, dtype, value = struct.unpack_from("<IIIHBBI", data, start + i * size)
        name = strings[name_idx] if 0 <= name_idx < len(strings) else ""
        res_id = res_ids[name_idx] if 0 <= name_idx < len(res_ids) else 0
        raw = strings[raw_idx] if raw_idx != 0xFFFFFFFF and raw_idx < len(strings) else None
        if name == "package":
            info["package"] = raw
        elif res_id == ATTR_VERSION_NAME or name == "versionName":
            info["version_name"] = raw if raw is not None else (strings[value] if dtype == TYPE_STRING else None)
        elif res_id == ATTR_VERSION_CODE or name == "versionCode":
            if dtype in (TYPE_INT_DEC, TYPE_INT_HEX):
                info["version_code"] = value
            elif raw and raw.isdigit():
                info["version_code"] = int(raw)
    if not info["package"]:
        raise ApkError("Paketname in der APK nicht gefunden")
    return info
