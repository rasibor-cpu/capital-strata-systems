"""Generate the CSS PWA family from the approved 1024px brand source."""

from __future__ import annotations

import binascii
import math
from pathlib import Path
import shutil
import struct
import zlib

ROOT = Path(__file__).resolve().parents[1]
BRANDING = ROOT / "assets" / "branding"
SOURCE = BRANDING / "css_icon_1024x1024.png"
MASKABLE_SCALE = 0.78
BACKGROUND = (8, 14, 25, 255)


def _paeth(left: int, above: int, upper_left: int) -> int:
    estimate = left + above - upper_left
    left_distance = abs(estimate - left)
    above_distance = abs(estimate - above)
    upper_left_distance = abs(estimate - upper_left)
    if left_distance <= above_distance and left_distance <= upper_left_distance:
        return left
    if above_distance <= upper_left_distance:
        return above
    return upper_left


def read_rgba_png(path: Path) -> tuple[int, int, bytes]:
    payload = path.read_bytes()
    if not payload.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("Canonical source is not a PNG")
    offset = 8
    width = height = 0
    compressed = bytearray()
    while offset < len(payload):
        length = struct.unpack(">I", payload[offset : offset + 4])[0]
        kind = payload[offset + 4 : offset + 8]
        data = payload[offset + 8 : offset + 8 + length]
        offset += 12 + length
        if kind == b"IHDR":
            width, height, depth, color_type, compression, filtering, interlace = struct.unpack(
                ">IIBBBBB", data
            )
            if (depth, color_type, compression, filtering, interlace) != (8, 6, 0, 0, 0):
                raise ValueError("Canonical source must be non-interlaced 8-bit RGBA")
        elif kind == b"IDAT":
            compressed.extend(data)
        elif kind == b"IEND":
            break

    raw = zlib.decompress(bytes(compressed))
    stride = width * 4
    output = bytearray(height * stride)
    cursor = 0
    for row in range(height):
        filter_type = raw[cursor]
        cursor += 1
        scanline = bytearray(raw[cursor : cursor + stride])
        cursor += stride
        prior = output[(row - 1) * stride : row * stride] if row else bytes(stride)
        for index in range(stride):
            left = scanline[index - 4] if index >= 4 else 0
            above = prior[index]
            upper_left = prior[index - 4] if index >= 4 else 0
            if filter_type == 1:
                scanline[index] = (scanline[index] + left) & 0xFF
            elif filter_type == 2:
                scanline[index] = (scanline[index] + above) & 0xFF
            elif filter_type == 3:
                scanline[index] = (scanline[index] + ((left + above) // 2)) & 0xFF
            elif filter_type == 4:
                scanline[index] = (
                    scanline[index] + _paeth(left, above, upper_left)
                ) & 0xFF
            elif filter_type != 0:
                raise ValueError(f"Unsupported PNG filter {filter_type}")
        output[row * stride : (row + 1) * stride] = scanline
    return width, height, bytes(output)


def resize_rgba(
    source: bytes,
    source_width: int,
    source_height: int,
    width: int,
    height: int,
) -> bytes:
    output = bytearray(width * height * 4)
    for y in range(height):
        source_y = (y + 0.5) * source_height / height - 0.5
        y0 = max(0, min(source_height - 1, math.floor(source_y)))
        y1 = min(source_height - 1, y0 + 1)
        y_weight = max(0.0, source_y - y0)
        for x in range(width):
            source_x = (x + 0.5) * source_width / width - 0.5
            x0 = max(0, min(source_width - 1, math.floor(source_x)))
            x1 = min(source_width - 1, x0 + 1)
            x_weight = max(0.0, source_x - x0)
            destination = (y * width + x) * 4
            for channel in range(4):
                top_left = source[(y0 * source_width + x0) * 4 + channel]
                top_right = source[(y0 * source_width + x1) * 4 + channel]
                bottom_left = source[(y1 * source_width + x0) * 4 + channel]
                bottom_right = source[(y1 * source_width + x1) * 4 + channel]
                top = top_left + (top_right - top_left) * x_weight
                bottom = bottom_left + (bottom_right - bottom_left) * x_weight
                output[destination + channel] = round(
                    top + (bottom - top) * y_weight
                )
    return bytes(output)


def maskable_rgba(source: bytes, source_width: int, source_height: int, size: int) -> bytes:
    inner_size = round(size * MASKABLE_SCALE)
    inner = resize_rgba(source, source_width, source_height, inner_size, inner_size)
    output = bytearray(BACKGROUND * (size * size))
    offset = (size - inner_size) // 2
    for y in range(inner_size):
        for x in range(inner_size):
            source_index = (y * inner_size + x) * 4
            destination = ((y + offset) * size + x + offset) * 4
            alpha = inner[source_index + 3] / 255
            for channel in range(3):
                output[destination + channel] = round(
                    inner[source_index + channel] * alpha
                    + output[destination + channel] * (1 - alpha)
                )
            output[destination + 3] = 255
    return bytes(output)


def png_bytes(width: int, height: int, rgba: bytes) -> bytes:
    raw = b"".join(
        b"\x00" + rgba[y * width * 4 : (y + 1) * width * 4]
        for y in range(height)
    )

    def chunk(kind: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + kind
            + data
            + struct.pack(">I", binascii.crc32(kind + data) & 0xFFFFFFFF)
        )

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw, 9))
        + chunk(b"IEND", b"")
    )


def write_ico(path: Path, images: list[tuple[int, bytes]]) -> None:
    offset = 6 + 16 * len(images)
    entries = []
    payload = bytearray()
    for size, data in images:
        entries.append(
            struct.pack(
                "<BBBBHHII",
                size,
                size,
                0,
                0,
                1,
                32,
                len(data),
                offset + len(payload),
            )
        )
        payload.extend(data)
    path.write_bytes(
        struct.pack("<HHH", 0, 1, len(images)) + b"".join(entries) + bytes(payload)
    )


def main() -> None:
    source_width, source_height, source = read_rgba_png(SOURCE)
    generated: dict[int, bytes] = {}
    for size, filename in (
        (16, "favicon-16x16.png"),
        (32, "favicon-32x32.png"),
        (180, "apple-touch-icon.png"),
        (192, "css-icon-192.png"),
        (512, "css-icon-512.png"),
    ):
        generated[size] = png_bytes(
            size,
            size,
            resize_rgba(source, source_width, source_height, size, size),
        )
        (BRANDING / filename).write_bytes(generated[size])

    for size, filename in (
        (192, "css-icon-maskable-192.png"),
        (512, "css-icon-maskable-512.png"),
    ):
        (BRANDING / filename).write_bytes(
            png_bytes(
                size,
                size,
                maskable_rgba(source, source_width, source_height, size),
            )
        )

    write_ico(BRANDING / "favicon.ico", [(16, generated[16]), (32, generated[32])])
    shutil.copyfile(BRANDING / "favicon.ico", BRANDING / "css.ico")
    shutil.copyfile(BRANDING / "apple-touch-icon.png", BRANDING / "apple_touch_icon_180.png")
    shutil.copyfile(BRANDING / "css-icon-192.png", BRANDING / "css_pwa_icon_192.png")
    shutil.copyfile(BRANDING / "css-icon-512.png", BRANDING / "css_pwa_icon_512.png")


if __name__ == "__main__":
    main()
