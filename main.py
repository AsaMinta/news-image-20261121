#!/usr/bin/env python3
"""Deterministic 1024x1024 editorial world-news digest PNG generator for Saturday 21 November 2026.
Standard library only (zlib, struct, math, os).
"""

import math
import os
import struct
import zlib

W, H = 1024, 1024

# Color Palette
PAPER    = (246, 245, 240)  # Warm paper background #F6F5F0
INK      = (20, 24, 31)     # Dark ink #14181F
INK_SOFT = (85, 92, 102)    # Muted ink for secondary text
RED      = (180, 40, 45)    # Primary red accent
TEAL     = (20, 110, 110)   # Teal accent
BLUE     = (35, 65, 130)    # Blue accent
AMBER    = (180, 115, 25)   # Amber accent
WHITE    = (255, 255, 255)  # Crisp white
RULE     = (188, 184, 174)  # Subtle divider rules
PANEL    = (238, 236, 230)  # Panel tint background
PIN_RED  = (200, 30, 35)    # Bright red map pins

# 8x8 ASCII bitmap font encoded as 16-character hex strings per character.
# Each row of 8 bits is represented by 2 hex digits (8 rows * 2 hex chars = 16 hex chars per char).
FONT = {
    " ": "0000000000000000",
    "A": "3C42427E42424200",
    "B": "7C42427C42427C00",
    "C": "3C60404040603C00",
    "D": "7844424242447800",
    "E": "7E40407840407E00",
    "F": "7E40407840404000",
    "G": "3C60404E42623C00",
    "H": "4242427E42424200",
    "I": "7E18181818187E00",
    "J": "1E0C0C0C4C6C3800",
    "K": "4648506050484600",
    "L": "4040404040407E00",
    "M": "42665A4242424200",
    "N": "4262524A46424200",
    "O": "3C42424242423C00",
    "P": "7C42427C40404000",
    "Q": "3C424242524C3E00",
    "R": "7C42427C44424200",
    "S": "3E40403C04043800",
    "T": "7F08080808080800",
    "U": "4242424242423C00",
    "V": "4242424242241800",
    "W": "4242425A5A664200",
    "X": "4224181818244200",
    "Y": "4224181818181800",
    "Z": "7E04081020407E00",
    "0": "3C42464A52623C00",
    "1": "0818280808083E00",
    "2": "3C42040810207E00",
    "3": "3C42041804423C00",
    "4": "0C1424447E040400",
    "5": "7E407C0202423C00",
    "6": "3C40407C42423C00",
    "7": "7E02040810202000",
    "8": "3C42423C42423C00",
    "9": "3C42423E02023C00",
    ":": "0018180018180000",
    "-": "0000007E00000000",
    ".": "0000000000180000",
    ",": "0000000018183000",
    "%": "62640810204C1800",
    "$": "183E603C067C1800",
    "&": "384448304A443A00",
    "*": "0044281028440000",
    "/": "0608102040000000",
    "|": "1818181818181800",
    "+": "0018187E18180000",
    "[": "3C20202020203C00",
    "]": "3C04040404043C00",
    "(": "0C18303030180C00",
    ")": "30180C0C0C183000",
    ";": "0018180018183000",
}


class Canvas:
    """2D RGB pixel canvas with basic vector primitives."""

    def __init__(self, w, h, bg_color):
        self.w = w
        self.h = h
        self.buf = bytearray(bytes(bg_color) * (w * h))

    def px(self, x, y, c):
        if 0 <= x < self.w and 0 <= y < self.h:
            idx = (y * self.w + x) * 3
            self.buf[idx:idx + 3] = bytes(c)

    def rect(self, x, y, w, h, c):
        x0 = max(0, x)
        y0 = max(0, y)
        x1 = min(self.w, x + w)
        y1 = min(self.h, y + h)
        if x0 >= x1 or y0 >= y1:
            return
        row = bytes(c) * (x1 - x0)
        row_len = len(row)
        for yy in range(y0, y1):
            idx = (yy * self.w + x0) * 3
            self.buf[idx:idx + row_len] = row

    def frame(self, x, y, w, h, c, thick=1):
        self.rect(x, y, w, thick, c)
        self.rect(x, y + h - thick, w, thick, c)
        self.rect(x, y + thick, thick, h - 2 * thick, c)
        self.rect(x + w - thick, y + thick, thick, h - 2 * thick, c)

    def line(self, x0, y0, x1, y1, c, thick=1):
        dx = abs(x1 - x0)
        dy = -abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx + dy
        while True:
            self.rect(x0, y0, thick, thick, c)
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x0 += sx
            if e2 <= dx:
                err += dx
                y0 += sy

    def disc(self, cx, cy, r, c):
        r2 = r * r
        for dy in range(-r, r + 1):
            span = int(math.isqrt(r2 - dy * dy))
            self.rect(cx - span, cy + dy, 2 * span + 1, 1, c)

    def ring(self, cx, cy, r, c, thick=1):
        steps = max(32, r * 6)
        prev = None
        for i in range(steps + 1):
            angle = 2.0 * math.pi * i / steps
            x = int(round(cx + r * math.cos(angle)))
            y = int(round(cy + r * math.sin(angle)))
            if prev is not None:
                self.line(prev[0], prev[1], x, y, c, thick)
            prev = (x, y)

    def polygon(self, points, outline_color, fill_color=None, thick=1):
        if fill_color:
            min_y = max(0, min(p[1] for p in points))
            max_y = min(self.h - 1, max(p[1] for p in points))
            n = len(points)
            for y in range(min_y, max_y + 1):
                nodes = []
                j = n - 1
                for i in range(n):
                    p1, p2 = points[i], points[j]
                    if (p1[1] < y <= p2[1]) or (p2[1] < y <= p1[1]):
                        x = int(p1[0] + (y - p1[1]) / (p2[1] - p1[1]) * (p2[0] - p1[0]))
                        nodes.append(x)
                    j = i
                nodes.sort()
                for k in range(0, len(nodes) - 1, 2):
                    self.rect(nodes[k], y, max(1, nodes[k + 1] - nodes[k]), 1, fill_color)
        if outline_color:
            n = len(points)
            for i in range(n):
                p1, p2 = points[i], points[(i + 1) % n]
                self.line(p1[0], p1[1], p2[0], p2[1], outline_color, thick)


def text_w(s, scale):
    return len(s) * 8 * scale


def draw_text(cv, x, y, s, scale, color):
    cx = x
    s_clean = s.upper().replace("—", "-").replace("–", "-")
    for ch in s_clean:
        hex_str = FONT.get(ch, FONT[" "])
        for r in range(8):
            byte_val = int(hex_str[r * 2:(r + 1) * 2], 16)
            if byte_val:
                c = 0
                while c < 8:
                    if byte_val & (0x80 >> c):
                        run = 1
                        while c + run < 8 and (byte_val & (0x80 >> (c + run))):
                            run += 1
                        cv.rect(cx + c * scale, y + r * scale, run * scale, scale, color)
                        c += run
                    else:
                        c += 1
        cx += 8 * scale


def text_center(cv, cx, y, s, scale, color):
    draw_text(cv, cx - text_w(s, scale) // 2, y, s, scale, color)


def badge(cv, x, y, w, h, fg, bg, text, scale=1):
    cv.rect(x, y, w, h, bg)
    cv.frame(x, y, w, h, fg, 1)
    tw = text_w(text, scale)
    draw_text(cv, x + (w - tw) // 2, y + (h - 8 * scale) // 2, text, scale, fg)


def pin(cv, cx, cy, num, color):
    cv.line(cx, cy, cx, cy + 8, color, 2)
    cv.disc(cx, cy, 7, color)
    cv.disc(cx, cy, 5, WHITE)
    s = str(num)
    tw = text_w(s, 1)
    draw_text(cv, cx - tw // 2, cy - 3, s, 1, INK)


def write_png(buf, w, h, path):
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    crc = zlib.crc32(b"IHDR" + ihdr) & 0xFFFFFFFF
    chunks = [struct.pack(">I", 13), b"IHDR", ihdr, struct.pack(">I", crc)]

    raw = bytearray()
    stride = w * 3
    for y in range(h):
        raw.append(0)
        raw.extend(buf[y * stride:(y + 1) * stride])

    comp = zlib.compress(raw, level=9)
    crc = zlib.crc32(b"IDAT" + comp) & 0xFFFFFFFF
    chunks.append(struct.pack(">I", len(comp)))
    chunks.append(b"IDAT")
    chunks.append(comp)
    chunks.append(struct.pack(">I", crc))

    crc = zlib.crc32(b"IEND") & 0xFFFFFFFF
    chunks.append(struct.pack(">I", 0))
    chunks.append(b"IEND")
    chunks.append(b"")
    chunks.append(struct.pack(">I", crc))

    with open(path, "wb") as f:
        f.write(bytes([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A]))
        for ch in chunks:
            f.write(ch)


def render():
    cv = Canvas(W, H, PAPER)

    # Canvas Outer Frame
    cv.frame(2, 2, W - 4, H - 4, INK, 2)
    cv.frame(6, 6, W - 12, H - 12, INK, 1)

    # ==========================================
    # 1. Top Editorial Masthead (y=10..98)
    # ==========================================
    cv.rect(10, 10, 1004, 88, PANEL)
    cv.frame(10, 10, 1004, 88, INK, 2)

    text_center(cv, 512, 18, "SATURDAY, 21 NOVEMBER 2026", 4, INK)
    cv.line(20, 58, 1004, 58, RULE, 1)

    sub_text = "COP31 TALKS RUN INTO OVERTIME | MISSILES INTERCEPTED OVER RIYADH | 6.7 QUAKE SHAKES PERU"
    text_center(cv, 512, 68, sub_text, 1, INK)

    cv.line(10, 98, 1014, 98, INK, 2)

    # ==========================================
    # 2. Key Figures Strip (y=106..172)
    # ==========================================
    kx, ky, kw, kh, gap = 12, 106, 160, 66, 8
    key_figures = [
        ("13", "COP31 OVERTIME DAY"),
        ("3", "MISSILES DOWNED RIYADH"),
        ("6.7", "PERU QUAKE MAGNITUDE"),
        ("146", "SAFE DAVAO LANDING"),
        ("$58,983", "BITCOIN EARLY SAT -3.9%"),
        ("124*", "KL RAHUL WELLINGTON"),
    ]

    for i, (val, lab) in enumerate(key_figures):
        x = kx + i * (kw + gap)
        cv.rect(x, ky, kw, kh, WHITE)
        cv.frame(x, ky, kw, kh, INK, 1)
        cv.rect(x, ky, kw, 4, RED if i % 2 == 0 else TEAL)

        scale_val = 3 if text_w(val, 3) <= kw - 8 else 2
        val_y = ky + (10 if scale_val == 3 else 14)
        text_center(cv, x + kw // 2, val_y, val, scale_val, INK)
        text_center(cv, x + kw // 2, ky + 46, lab, 1, INK_SOFT)

    # ==========================================
    # 3. Three Lead Story Cards (y=182..420, 3 columns)
    # ==========================================
    cx0, cy, cw, ch, cg = 12, 182, 328, 238, 8

    leads = [
        {
            "accent": RED,
            "title": "MISSILES OVER RIYADH",
            "summary1": "SAUDI DEFENCES DOWN 3 MISSILES",
            "summary2": "TARGETING CAPITAL AIRSPACE",
            "source": "SOURCE: REUTERS, AFP [OFFICIAL]",
            "type": "radar"
        },
        {
            "accent": TEAL,
            "title": "COP31 IN OVERTIME",
            "summary1": "ANTALYA TALKS MISS DAY 12 DEADLINE",
            "summary2": "FINANCE GOALS REMAIN UNRESOLVED",
            "source": "SOURCE: AP, AFP, AL JAZEERA [CONFIRMED]",
            "type": "gauge"
        },
        {
            "accent": BLUE,
            "title": "6.7 QUAKE SHAKES PERU",
            "summary1": "DEEP TREMOR RATTLES CENTRAL ANDES",
            "summary2": "NO TSUNAMI WARNING ISSUED",
            "source": "SOURCE: USGS, IGP [OFFICIAL]",
            "type": "seismic"
        }
    ]

    for i, card in enumerate(leads):
        x = cx0 + i * (cw + cg)
        cv.rect(x, cy, cw, ch, WHITE)
        cv.frame(x, cy, cw, ch, INK, 2)

        cv.rect(x + 2, cy + 2, cw - 4, 68, card["accent"])

        banner_cx = x + cw // 2
        banner_cy = cy + 36

        if card["type"] == "radar":
            cv.ring(banner_cx, banner_cy, 22, WHITE, 2)
            cv.ring(banner_cx, banner_cy, 12, WHITE, 1)
            cv.line(banner_cx - 26, banner_cy, banner_cx + 26, banner_cy, WHITE, 1)
            cv.line(banner_cx, banner_cy - 26, banner_cx, banner_cy + 26, WHITE, 1)
            cv.line(banner_cx, banner_cy, banner_cx + 18, banner_cy - 14, WHITE, 2)
            cv.disc(banner_cx + 12, banner_cy - 10, 3, WHITE)
            text_center(cv, banner_cx, cy + 54, "AIR DEFENCE RADAR ACTIVE", 1, WHITE)

        elif card["type"] == "gauge":
            cv.ring(banner_cx, banner_cy + 8, 24, WHITE, 2)
            cv.line(banner_cx, banner_cy + 8, banner_cx + 16, banner_cy - 10, WHITE, 2)
            cv.disc(banner_cx, banner_cy + 8, 4, WHITE)
            text_center(cv, banner_cx, cy + 12, "+1.5C TARGET GAUGE", 1, WHITE)
            badge(cv, banner_cx - 32, cy + 46, 64, 16, WHITE, card["accent"], "+1.5C", 1)

        elif card["type"] == "seismic":
            base_y = banner_cy
            cv.line(x + 20, base_y, x + 80, base_y, WHITE, 1)
            points = [(80, 0), (95, -18), (110, 22), (125, -26), (140, 28),
                      (155, -20), (170, 15), (185, -10), (200, 0)]
            prev_pt = (x + 80, base_y)
            for px_off, py_off in points:
                curr_pt = (x + 80 + px_off, base_y + py_off)
                cv.line(prev_pt[0], prev_pt[1], curr_pt[0], curr_pt[1], WHITE, 2)
                prev_pt = curr_pt
            cv.line(prev_pt[0], prev_pt[1], x + cw - 20, base_y, WHITE, 1)
            text_center(cv, banner_cx, cy + 54, "EPICENTRE DEPTH 120KM", 1, WHITE)

        text_center(cv, banner_cx, cy + 82, card["title"], 2, INK)
        cv.line(x + 20, cy + 110, x + cw - 20, cy + 110, RULE, 1)

        text_center(cv, banner_cx, cy + 122, card["summary1"], 1, INK)
        text_center(cv, banner_cx, cy + 138, card["summary2"], 1, INK_SOFT)

        badge(cv, x + 8, cy + ch - 32, cw - 16, 24, INK, PANEL, card["source"], 1)

    # ==========================================
    # 4. Secondary Global Grid (y=430..755, 2 rows x 4 cols)
    # ==========================================
    sg_y1, sg_y2, sg_w, sg_h, sg_gap = 430, 595, 244, 155, 8

    grid_items = [
        ("KYIV WARNING: BRIDGE STRIKES", "NBC", "EUROPE", RED),
        ("HORMUZ: US DRONE CLAIM", "IRIB", "M-EAST", TEAL),
        ("TEHRAN: URANIUM STOCK STAYS", "TASNIM", "M-EAST", BLUE),
        ("US TAX ON DATA CENTRES", "ABC", "USA", AMBER),
        ("CHINA-JAPAN TAIWAN ROW", "AFP", "ASIA", RED),
        ("DAVAO: 146 SAFE AFTER ALERT", "AP", "PACIFIC", TEAL),
        ("BITCOIN SLIPS BELOW $59K", "COINDESK", "MARKETS", BLUE),
        ("RUSSELL P1 LAS VEGAS; RAHUL 124*", "F1 / AFP", "GLOBAL", AMBER),
    ]

    for i, (headline, src, region, tag_color) in enumerate(grid_items):
        col = i % 4
        row = i // 4
        gx = cx0 + col * (sg_w + sg_gap)
        gy = sg_y1 if row == 0 else sg_y2

        cv.rect(gx, gy, sg_w, sg_h, PANEL)
        cv.frame(gx, gy, sg_w, sg_h, INK, 1)

        cv.disc(gx + 12, gy + 14, 4, tag_color)
        draw_text(cv, gx + 22, gy + 10, region, 1, tag_color)

        cv.line(gx + 8, gy + 26, gx + sg_w - 8, gy + 26, RULE, 1)

        words = headline.split(" ")
        line1, line2 = "", ""
        for w in words:
            if text_w((line1 + " " + w).strip(), 1) <= sg_w - 16:
                line1 = (line1 + " " + w).strip()
            else:
                line2 = (line2 + " " + w).strip()

        draw_text(cv, gx + 10, gy + 36, line1, 1, INK)
        if line2:
            draw_text(cv, gx + 10, gy + 52, line2, 1, INK)

        badge(cv, gx + 8, gy + sg_h - 28, sg_w - 16, 20, INK_SOFT, WHITE, f"SOURCE: {src}", 1)

    # ==========================================
    # 5. Bottom World Map & Additional Stories Bar (y=765..1012)
    # ==========================================
    map_x, map_y, map_w, map_h = 12, 765, 590, 247
    cv.rect(map_x, map_y, map_w, map_h, WHITE)
    cv.frame(map_x, map_y, map_w, map_h, INK, 2)

    cv.rect(map_x, map_y, map_w, 22, PANEL)
    cv.frame(map_x, map_y, map_w, 22, INK, 1)
    text_center(cv, map_x + map_w // 2, map_y + 6, "GEOGRAPHIC DISPATCH MAP - 21 NOVEMBER 2026", 1, INK)

    ox, oy = map_x + 10, map_y + 30

    continents = [
        [(ox + 20, oy + 20), (ox + 120, oy + 15), (ox + 150, oy + 45),
         (ox + 130, oy + 90), (ox + 80, oy + 100), (ox + 50, oy + 70), (ox + 20, oy + 50)],
        [(ox + 110, oy + 95), (ox + 145, oy + 95), (ox + 160, oy + 140),
         (ox + 125, oy + 200), (ox + 100, oy + 170), (ox + 105, oy + 120)],
        [(ox + 260, oy + 20), (ox + 320, oy + 18), (ox + 340, oy + 50),
         (ox + 290, oy + 60), (ox + 255, oy + 45)],
        [(ox + 255, oy + 65), (ox + 320, oy + 65), (ox + 340, oy + 110),
         (ox + 300, oy + 180), (ox + 265, oy + 150), (ox + 250, oy + 90)],
        [(ox + 325, oy + 18), (ox + 530, oy + 15), (ox + 550, oy + 80),
         (ox + 480, oy + 120), (ox + 350, oy + 100), (ox + 325, oy + 50)],
        [(ox + 450, oy + 135), (ox + 520, oy + 130), (ox + 515, oy + 180), (ox + 455, oy + 175)]
    ]

    for poly in continents:
        cv.polygon(poly, INK_SOFT, PANEL, thick=1)

    pins = [
        (ox + 335, oy + 42, 1),
        (ox + 330, oy + 82, 2),
        (ox + 125, oy + 140, 3),
        (ox + 480, oy + 105, 4),
        (ox + 345, oy + 78, 5),
        (ox + 348, oy + 70, 6),
        (ox + 70, oy + 50, 7),
        (ox + 535, oy + 190, 8),
        (ox + 315, oy + 60, 9),
        (ox + 338, oy + 46, 10),
        (ox + 115, oy + 90, 11),
    ]

    for px, py, pnum in pins:
        pin(cv, px, py, pnum, PIN_RED)

    rp_x = map_x + map_w + 12
    rp_y = map_y
    rp_w = W - rp_x - 12
    rp_h = map_h

    cv.rect(rp_x, rp_y, rp_w, rp_h, WHITE)
    cv.frame(rp_x, rp_y, rp_w, rp_h, INK, 2)

    cv.rect(rp_x, rp_y, rp_w, 22, PANEL)
    cv.frame(rp_x, rp_y, rp_w, 22, INK, 1)
    text_center(cv, rp_x + rp_w // 2, rp_y + 6, "MORE VERIFIED HEADLINES", 1, INK)

    extra_stories = [
        "1. KRYVYI RIH STRIKES - KYIV IND.",
        "2. PANAMA CANAL TEXT - AL JAZEERA",
        "3. YEMEN PORTS - AL JAZEERA",
        "4. SEJONG RAIL - KOREA HERALD",
        "5. CUMMINS CAPTAINCY - ABC",
        "6. VERSTAPPEN STEWARDS - AUTOSPORT",
        "7. US JOBLESS CLAIMS - BLS",
        "8. EUROZONE CPI - EUROSTAT",
        "9. JAPAN TRADE DATA - JMA",
        "10. BRAZIL RATE DECISION - BCB",
    ]

    for i, headline in enumerate(extra_stories):
        sy = rp_y + 28 + i * 21
        cv.disc(rp_x + 12, sy + 3, 2, RED)
        draw_text(cv, rp_x + 20, sy, headline, 1, INK)

    return cv


def main():
    cv = render()
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "entry.png")
    write_png(cv.buf, W, H, out_path)
    print(f"Successfully generated digest PNG at {out_path} ({len(cv.buf)} bytes)")


if __name__ == "__main__":
    main()
