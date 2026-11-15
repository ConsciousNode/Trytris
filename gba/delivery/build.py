#!/usr/bin/env python3
"""
build.py - Trytris GBA ROM Builder & Hand-Assembler
ConsciousNode SoftWorks - MIT License
Zero external dependencies (Python 3 standard library only).
"""

import argparse
import os
import struct
import sys
import zlib

# ==============================================================================
# [LIFT-1] GBA Cartridge Header Logo & Complement Checksum
# Provenance: 1337boy/tools/1337ify.py (ConsciousNode SoftWorks, MIT),
#             lines 26-37 & 245-260, sha256 c41a1ee03f1e7ce6b79cd2794adfc00c79ad78b15a94cb2abf7e0d885ddef054
# Intentional changes: Game title set to "TRYTRIS GBA " and game code to "BTRE".
# ==============================================================================
NINTENDO_LOGO = bytes([
    0x24,0xFF,0xAE,0x51,0x69,0x9A,0xA2,0x21,0x3D,0x84,0x82,0x0A,0x84,0xE4,0x09,0xAD,
    0x11,0x24,0x8B,0x98,0xC0,0x81,0x7F,0x21,0xA3,0x52,0xBE,0x19,0x93,0x09,0xCE,0x20,
    0x10,0x46,0x4A,0x4A,0xF8,0x27,0x31,0xEC,0x58,0xC7,0xE8,0x33,0x82,0xE3,0xCE,0xBF,
    0x85,0xF4,0xDF,0x94,0xCE,0x4B,0x09,0xC1,0x94,0x56,0x8A,0xC0,0x13,0x72,0xA7,0xFC,
    0x9F,0x84,0x4D,0x73,0xA3,0xCA,0x9A,0x61,0x58,0x97,0xA3,0x27,0xFC,0x03,0x98,0x76,
    0x23,0x1D,0xC7,0x61,0x03,0x04,0xAE,0x56,0xBF,0x38,0x84,0x00,0x40,0xA7,0x0E,0xFD,
    0xFF,0x52,0xFE,0x03,0x6F,0x95,0x30,0xF1,0x97,0xFB,0xC0,0x85,0x60,0xD6,0x80,0x25,
    0xA9,0x63,0xBE,0x03,0x01,0x4E,0x38,0xE2,0xF9,0xA2,0x34,0xFF,0xBB,0x3E,0x03,0x44,
    0x78,0x00,0x90,0xCB,0x88,0x11,0x3A,0x94,0x65,0xC0,0x7C,0x63,0x87,0xF0,0x3C,0xAF,
    0xD6,0x25,0xE4,0x8B,0x38,0x0A,0xAC,0x72,0x21,0xD4,0xF8,0x07
])

def rgb15(r, g, b):
    return (r & 0x1F) | ((g & 0x1F) << 5) | ((b & 0x1F) << 10)

def hex_to_bgr555(hc):
    r = int(hc[1:3], 16) >> 3
    g = int(hc[3:5], 16) >> 3
    b = int(hc[5:7], 16) >> 3
    return rgb15(r, g, b)

# ==============================================================================
# [LIFT-2] 8x8 Bitmap Font & Zero-Dependency ARM7TDMI Assembler
# Provenance: 1337boy/tools/1337ify.py (ConsciousNode SoftWorks, MIT),
#             lines 39-232, sha256 c41a1ee03f1e7ce6b79cd2794adfc00c79ad78b15a94cb2abf7e0d885ddef054
# Intentional changes: Extended FONT_8X8 to cover full printable ASCII 32..126
# (including lowercase glyphs for "Triangles are hard." and achievement titles);
# extended ArmBuilder with UMULL, MLA, LDRSB, LDRSH, register-offset loads/stores,
# and 32-bit immediate/label synthesis (li32, la).
# ==============================================================================
FONT_8X8 = {
    ' ': [0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00],
    '!': [0x18,0x18,0x18,0x18,0x18,0x00,0x18,0x00],
    '"': [0x66,0x66,0x24,0x00,0x00,0x00,0x00,0x00],
    '#': [0x24,0x7E,0x24,0x24,0x7E,0x24,0x00,0x00],
    '$': [0x18,0x3E,0x60,0x3C,0x06,0x7C,0x18,0x00],
    '%': [0x62,0x64,0x08,0x10,0x26,0x46,0x00,0x00],
    '&': [0x38,0x64,0x38,0x76,0xCC,0xCC,0x76,0x00],
    "'": [0x18,0x18,0x08,0x00,0x00,0x00,0x00,0x00],
    '(': [0x0C,0x18,0x30,0x30,0x30,0x18,0x0C,0x00],
    ')': [0x30,0x18,0x0C,0x0C,0x0C,0x18,0x30,0x00],
    '*': [0x00,0x66,0x3C,0xFF,0x3C,0x66,0x00,0x00],
    '+': [0x00,0x18,0x18,0x7E,0x18,0x18,0x00,0x00],
    ',': [0x00,0x00,0x00,0x00,0x00,0x18,0x18,0x30],
    '-': [0x00,0x00,0x00,0x7E,0x00,0x00,0x00,0x00],
    '.': [0x00,0x00,0x00,0x00,0x00,0x18,0x18,0x00],
    '/': [0x06,0x0C,0x18,0x30,0x60,0x40,0x00,0x00],
    '0': [0x3C,0x66,0x6E,0x76,0x66,0x66,0x3C,0x00],
    '1': [0x18,0x38,0x18,0x18,0x18,0x18,0x7E,0x00],
    '2': [0x3C,0x66,0x06,0x1C,0x30,0x66,0x7E,0x00],
    '3': [0x3C,0x66,0x06,0x1C,0x06,0x66,0x3C,0x00],
    '4': [0x0C,0x1C,0x3C,0x6C,0x7E,0x0C,0x0C,0x00],
    '5': [0x7E,0x60,0x7C,0x06,0x06,0x66,0x3C,0x00],
    '6': [0x3C,0x60,0x7C,0x66,0x66,0x66,0x3C,0x00],
    '7': [0x7E,0x66,0x06,0x0C,0x18,0x18,0x18,0x00],
    '8': [0x3C,0x66,0x66,0x3C,0x66,0x66,0x3C,0x00],
    '9': [0x3C,0x66,0x66,0x3E,0x06,0x0C,0x38,0x00],
    ':': [0x00,0x18,0x18,0x00,0x18,0x18,0x00,0x00],
    ';': [0x00,0x18,0x18,0x00,0x18,0x18,0x30,0x00],
    '<': [0x0C,0x18,0x30,0x60,0x30,0x18,0x0C,0x00],
    '=': [0x00,0x00,0x7E,0x00,0x7E,0x00,0x00,0x00],
    '>': [0x30,0x18,0x0C,0x06,0x0C,0x18,0x30,0x00],
    '?': [0x3C,0x66,0x06,0x1C,0x18,0x00,0x18,0x00],
    '@': [0x3C,0x66,0x6E,0x6E,0x60,0x62,0x3C,0x00],
    'A': [0x18,0x3C,0x66,0x66,0x7E,0x66,0x66,0x00],
    'B': [0x7C,0x66,0x66,0x7C,0x66,0x66,0x7C,0x00],
    'C': [0x3C,0x66,0x60,0x60,0x60,0x66,0x3C,0x00],
    'D': [0x78,0x6C,0x66,0x66,0x66,0x6C,0x78,0x00],
    'E': [0x7E,0x60,0x60,0x7C,0x60,0x60,0x7E,0x00],
    'F': [0x7E,0x60,0x60,0x7C,0x60,0x60,0x60,0x00],
    'G': [0x3C,0x66,0x60,0x6E,0x66,0x66,0x3E,0x00],
    'H': [0x66,0x66,0x66,0x7E,0x66,0x66,0x66,0x00],
    'I': [0x3C,0x18,0x18,0x18,0x18,0x18,0x3C,0x00],
    'J': [0x1E,0x0C,0x0C,0x0C,0x6C,0x6C,0x38,0x00],
    'K': [0x66,0x6C,0x78,0x70,0x78,0x6C,0x66,0x00],
    'L': [0x60,0x60,0x60,0x60,0x60,0x60,0x7E,0x00],
    'M': [0x63,0x77,0x7F,0x6B,0x63,0x63,0x63,0x00],
    'N': [0x66,0x76,0x7E,0x7E,0x6E,0x66,0x66,0x00],
    'O': [0x3C,0x66,0x66,0x66,0x66,0x66,0x3C,0x00],
    'P': [0x7C,0x66,0x66,0x7C,0x60,0x60,0x60,0x00],
    'Q': [0x3C,0x66,0x66,0x66,0x6A,0x6C,0x36,0x00],
    'R': [0x7C,0x66,0x66,0x7C,0x6C,0x66,0x66,0x00],
    'S': [0x3C,0x66,0x60,0x3C,0x06,0x66,0x3C,0x00],
    'T': [0x7E,0x18,0x18,0x18,0x18,0x18,0x18,0x00],
    'U': [0x66,0x66,0x66,0x66,0x66,0x66,0x3C,0x00],
    'V': [0x66,0x66,0x66,0x66,0x66,0x3C,0x18,0x00],
    'W': [0x63,0x63,0x63,0x6B,0x7F,0x77,0x63,0x00],
    'X': [0x66,0x66,0x3C,0x18,0x3C,0x66,0x66,0x00],
    'Y': [0x66,0x66,0x66,0x3C,0x18,0x18,0x18,0x00],
    'Z': [0x7E,0x06,0x0C,0x18,0x30,0x60,0x7E,0x00],
    '[': [0x3C,0x30,0x30,0x30,0x30,0x30,0x3C,0x00],
    '\\':[0x60,0x30,0x18,0x0C,0x06,0x00,0x00,0x00],
    ']': [0x3C,0x0C,0x0C,0x0C,0x0C,0x0C,0x3C,0x00],
    '^': [0x18,0x3C,0x7E,0x00,0x00,0x00,0x00,0x00],
    '_': [0x00,0x00,0x00,0x00,0x00,0x00,0x7E,0x00],
    '`': [0x30,0x18,0x0C,0x00,0x00,0x00,0x00,0x00],
    'a': [0x00,0x00,0x3C,0x06,0x3E,0x66,0x3E,0x00],
    'b': [0x60,0x60,0x7C,0x66,0x66,0x66,0x7C,0x00],
    'c': [0x00,0x00,0x3C,0x66,0x60,0x66,0x3C,0x00],
    'd': [0x06,0x06,0x3E,0x66,0x66,0x66,0x3E,0x00],
    'e': [0x00,0x00,0x3C,0x66,0x7E,0x60,0x3C,0x00],
    'f': [0x1C,0x30,0x7C,0x30,0x30,0x30,0x30,0x00],
    'g': [0x00,0x00,0x3E,0x66,0x66,0x3E,0x06,0x3C],
    'h': [0x60,0x60,0x7C,0x66,0x66,0x66,0x66,0x00],
    'i': [0x18,0x00,0x38,0x18,0x18,0x18,0x3C,0x00],
    'j': [0x06,0x00,0x0E,0x06,0x06,0x66,0x66,0x3C],
    'k': [0x60,0x60,0x66,0x6C,0x78,0x6C,0x66,0x00],
    'l': [0x38,0x18,0x18,0x18,0x18,0x18,0x3C,0x00],
    'm': [0x00,0x00,0x66,0x7F,0x7F,0x6B,0x63,0x00],
    'n': [0x00,0x00,0x7C,0x66,0x66,0x66,0x66,0x00],
    'o': [0x00,0x00,0x3C,0x66,0x66,0x66,0x3C,0x00],
    'p': [0x00,0x00,0x7C,0x66,0x66,0x7C,0x60,0x60],
    'q': [0x00,0x00,0x3E,0x66,0x66,0x3E,0x06,0x06],
    'r': [0x00,0x00,0x7C,0x66,0x60,0x60,0x60,0x00],
    's': [0x00,0x00,0x3E,0x60,0x3C,0x06,0x7C,0x00],
    't': [0x30,0x30,0x7C,0x30,0x30,0x36,0x1C,0x00],
    'u': [0x00,0x00,0x66,0x66,0x66,0x66,0x3E,0x00],
    'v': [0x00,0x00,0x66,0x66,0x66,0x3C,0x18,0x00],
    'w': [0x00,0x00,0x63,0x6B,0x7F,0x7F,0x36,0x00],
    'x': [0x00,0x00,0x66,0x3C,0x18,0x3C,0x66,0x00],
    'y': [0x00,0x00,0x66,0x66,0x66,0x3E,0x06,0x3C],
    'z': [0x00,0x00,0x7E,0x0C,0x18,0x30,0x7E,0x00],
    '{': [0x0E,0x18,0x18,0x70,0x18,0x18,0x0E,0x00],
    '|': [0x18,0x18,0x18,0x18,0x18,0x18,0x18,0x00],
    '}': [0x70,0x18,0x18,0x0E,0x18,0x18,0x70,0x00],
    '~': [0x32,0x4C,0x00,0x00,0x00,0x00,0x00,0x00],
}

class ArmBuilder:
    EQ = 0x0; NE = 0x1; CS = 0x2; HS = 0x2; CC = 0x3; LO = 0x3
    MI = 0x4; PL = 0x5; VS = 0x6; VC = 0x7; HI = 0x8; LS = 0x9
    GE = 0xA; LT = 0xB; GT = 0xC; LE = 0xD; AL = 0xE

    LSL = 0; LSR = 1; ASR = 2; ROR = 3

    def __init__(self, base=0x08000000):
        self.base = base
        self.code = bytearray()
        self.labels = {}
        self.fixups = []

    def align(self, n=4):
        while len(self.code) % n != 0:
            self.code.append(0)

    def label(self, name):
        if name in self.labels:
            raise ValueError(f"Duplicate label: {name}")
        self.labels[name] = self.base + len(self.code)

    def emit32(self, w):
        self.code.extend(struct.pack("<I", w & 0xFFFFFFFF))

    def emit16(self, h):
        self.code.extend(struct.pack("<H", h & 0xFFFF))

    def emit8(self, b):
        self.code.append(b & 0xFF)

    def emit_bytes(self, b):
        self.code.extend(b)

    def _try_enc_imm(self, val):
        val &= 0xFFFFFFFF
        for rot in range(16):
            shift = rot * 2
            imm8 = ((val << shift) | (val >> (32 - shift))) & 0xFFFFFFFF if shift else val
            if imm8 <= 0xFF:
                return (rot << 8) | imm8
        return None

    def _enc_imm(self, val):
        res = self._try_enc_imm(val)
        if res is None:
            raise ValueError(f"Cannot encode ARM immediate {hex(val)}")
        return res

    def dp_imm(self, op, s, rn, rd, val, cond=0xE):
        return (cond << 28) | (1 << 25) | (op << 21) | (s << 20) | (rn << 16) | (rd << 12) | self._enc_imm(val)

    def dp_reg(self, op, s, rn, rd, rm, shift_imm=0, shift_type=0, cond=0xE):
        return (cond << 28) | (0 << 25) | (op << 21) | (s << 20) | (rn << 16) | (rd << 12) | (shift_imm << 7) | (shift_type << 5) | rm

    def dp_reg_rs(self, op, s, rn, rd, rm, rs, shift_type=0, cond=0xE):
        return (cond << 28) | (0 << 25) | (op << 21) | (s << 20) | (rn << 16) | (rd << 12) | (rs << 8) | (shift_type << 5) | (1 << 4) | rm

    def and_imm(self, rd, rn, val, s=0, cond=0xE): self.emit32(self.dp_imm(0x0, s, rn, rd, val, cond))
    def eor_imm(self, rd, rn, val, s=0, cond=0xE): self.emit32(self.dp_imm(0x1, s, rn, rd, val, cond))
    def sub_imm(self, rd, rn, val, s=0, cond=0xE):
        if self._try_enc_imm(val) is not None:
            self.emit32(self.dp_imm(0x2, s, rn, rd, val, cond))
        else:
            assert s == 0
            self.emit32(self.dp_imm(0x2, 0, rn, rd, val & 0xFF, cond))
            self.emit32(self.dp_imm(0x2, 0, rd, rd, val & ~0xFF, cond))
    def rsb_imm(self, rd, rn, val, s=0, cond=0xE): self.emit32(self.dp_imm(0x3, s, rn, rd, val, cond))
    def add_imm(self, rd, rn, val, s=0, cond=0xE):
        if self._try_enc_imm(val) is not None:
            self.emit32(self.dp_imm(0x4, s, rn, rd, val, cond))
        else:
            assert s == 0
            self.emit32(self.dp_imm(0x4, 0, rn, rd, val & 0xFF, cond))
            self.emit32(self.dp_imm(0x4, 0, rd, rd, val & ~0xFF, cond))
    def tst_imm(self, rn, val, cond=0xE):          self.emit32(self.dp_imm(0x8, 1, rn, 0, val, cond))
    def cmp_imm(self, rn, val, cond=0xE):          self.emit32(self.dp_imm(0xA, 1, rn, 0, val, cond))
    def cmn_imm(self, rn, val, cond=0xE):          self.emit32(self.dp_imm(0xB, 1, rn, 0, val, cond))
    def orr_imm(self, rd, rn, val, s=0, cond=0xE): self.emit32(self.dp_imm(0xC, s, rn, rd, val, cond))
    def mov_imm(self, rd, val, s=0, cond=0xE):     self.emit32(self.dp_imm(0xD, s, 0, rd, val, cond))
    def bic_imm(self, rd, rn, val, s=0, cond=0xE): self.emit32(self.dp_imm(0xE, s, rn, rd, val, cond))
    def mvn_imm(self, rd, val, s=0, cond=0xE):     self.emit32(self.dp_imm(0xF, s, 0, rd, val, cond))

    def li32(self, rd, val, cond=0xE):
        if val < 0:
            val &= 0xFFFFFFFF
        else:
            val &= 0xFFFFFFFF
        if self._try_enc_imm(val) is not None:
            self.mov_imm(rd, val, cond=cond)
            return
        if self._try_enc_imm((~val) & 0xFFFFFFFF) is not None:
            self.mvn_imm(rd, (~val) & 0xFFFFFFFF, cond=cond)
            return
        b0 = val & 0xFF
        b1 = (val >> 8) & 0xFF
        b2 = (val >> 16) & 0xFF
        b3 = (val >> 24) & 0xFF
        parts = [(b0, 0), (b1, 8), (b2, 16), (b3, 24)]
        non_zero = [(b << sh) for b, sh in parts if b != 0]
        if not non_zero:
            self.mov_imm(rd, 0, cond=cond)
            return
        self.mov_imm(rd, non_zero[0], cond=cond)
        for p in non_zero[1:]:
            self.orr_imm(rd, rd, p, cond=cond)

    def la(self, rd, label, cond=0xE):
        off = len(self.code)
        self.fixups.append((off, 'LA', label, (cond, rd)))
        self.emit32(0); self.emit32(0); self.emit32(0); self.emit32(0)

    def and_reg(self, rd, rn, rm, shift_imm=0, shift_type=0, s=0, cond=0xE): self.emit32(self.dp_reg(0x0, s, rn, rd, rm, shift_imm, shift_type, cond))
    def eor_reg(self, rd, rn, rm, shift_imm=0, shift_type=0, s=0, cond=0xE): self.emit32(self.dp_reg(0x1, s, rn, rd, rm, shift_imm, shift_type, cond))
    def sub_reg(self, rd, rn, rm, shift_imm=0, shift_type=0, s=0, cond=0xE): self.emit32(self.dp_reg(0x2, s, rn, rd, rm, shift_imm, shift_type, cond))
    def rsb_reg(self, rd, rn, rm, shift_imm=0, shift_type=0, s=0, cond=0xE): self.emit32(self.dp_reg(0x3, s, rn, rd, rm, shift_imm, shift_type, cond))
    def add_reg(self, rd, rn, rm, shift_imm=0, shift_type=0, s=0, cond=0xE): self.emit32(self.dp_reg(0x4, s, rn, rd, rm, shift_imm, shift_type, cond))
    def tst_reg(self, rn, rm, shift_imm=0, shift_type=0, cond=0xE):          self.emit32(self.dp_reg(0x8, 1, rn, 0, rm, shift_imm, shift_type, cond))
    def cmp_reg(self, rn, rm, shift_imm=0, shift_type=0, cond=0xE):          self.emit32(self.dp_reg(0xA, 1, rn, 0, rm, shift_imm, shift_type, cond))
    def cmn_reg(self, rn, rm, shift_imm=0, shift_type=0, cond=0xE):          self.emit32(self.dp_reg(0xB, 1, rn, 0, rm, shift_imm, shift_type, cond))
    def orr_reg(self, rd, rn, rm, shift_imm=0, shift_type=0, s=0, cond=0xE): self.emit32(self.dp_reg(0xC, s, rn, rd, rm, shift_imm, shift_type, cond))
    def mov_reg(self, rd, rm, shift_imm=0, shift_type=0, s=0, cond=0xE):     self.emit32(self.dp_reg(0xD, s, 0, rd, rm, shift_imm, shift_type, cond))
    def bic_reg(self, rd, rn, rm, shift_imm=0, shift_type=0, s=0, cond=0xE): self.emit32(self.dp_reg(0xE, s, rn, rd, rm, shift_imm, shift_type, cond))
    def mvn_reg(self, rd, rm, shift_imm=0, shift_type=0, s=0, cond=0xE):     self.emit32(self.dp_reg(0xF, s, 0, rd, rm, shift_imm, shift_type, cond))

    def mov_reg_rs(self, rd, rm, rs, shift_type=0, s=0, cond=0xE):
        self.emit32(self.dp_reg_rs(0xD, s, 0, rd, rm, rs, shift_type, cond))

    def orr_reg_rs(self, rd, rn, rm, rs, shift_type=0, s=0, cond=0xE):
        self.emit32(self.dp_reg_rs(0xC, s, rn, rd, rm, rs, shift_type, cond))

    def mul(self, rd, rm, rs, s=0, cond=0xE):
        self.emit32((cond << 28) | (s << 20) | (rd << 16) | (rs << 8) | 0x90 | rm)

    def mla(self, rd, rm, rs, rn, s=0, cond=0xE):
        self.emit32((cond << 28) | (1 << 21) | (s << 20) | (rd << 16) | (rn << 12) | (rs << 8) | 0x90 | rm)

    def umull(self, rdlo, rdhi, rm, rs, s=0, cond=0xE):
        self.emit32((cond << 28) | (1 << 23) | (s << 20) | (rdhi << 16) | (rdlo << 12) | (rs << 8) | 0x90 | rm)

    def ldr(self, rd, rn, offset=0, b=0, p=1, w=0, cond=0xE):
        u = 1 if offset >= 0 else 0
        self.emit32((cond << 28) | (1 << 26) | (p << 24) | (u << 23) | (b << 22) | (w << 21) | (1 << 20) | (rn << 16) | (rd << 12) | (abs(offset) & 0xFFF))

    def ldrb(self, rd, rn, offset=0, p=1, w=0, cond=0xE):
        self.ldr(rd, rn, offset, b=1, p=p, w=w, cond=cond)

    def str(self, rd, rn, offset=0, b=0, p=1, w=0, cond=0xE):
        u = 1 if offset >= 0 else 0
        self.emit32((cond << 28) | (1 << 26) | (p << 24) | (u << 23) | (b << 22) | (w << 21) | (0 << 20) | (rn << 16) | (rd << 12) | (abs(offset) & 0xFFF))

    def strb(self, rd, rn, offset=0, p=1, w=0, cond=0xE):
        self.str(rd, rn, offset, b=1, p=p, w=w, cond=cond)

    def ldr_reg(self, rd, rn, rm, shift_imm=0, shift_type=0, b=0, p=1, u=1, w=0, cond=0xE):
        self.emit32((cond << 28) | (3 << 25) | (p << 24) | (u << 23) | (b << 22) | (w << 21) | (1 << 20) | (rn << 16) | (rd << 12) | (shift_imm << 7) | (shift_type << 5) | rm)

    def ldrb_reg(self, rd, rn, rm, shift_imm=0, shift_type=0, p=1, u=1, w=0, cond=0xE):
        self.ldr_reg(rd, rn, rm, shift_imm, shift_type, b=1, p=p, u=u, w=w, cond=cond)

    def str_reg(self, rd, rn, rm, shift_imm=0, shift_type=0, b=0, p=1, u=1, w=0, cond=0xE):
        self.emit32((cond << 28) | (3 << 25) | (p << 24) | (u << 23) | (b << 22) | (w << 21) | (0 << 20) | (rn << 16) | (rd << 12) | (shift_imm << 7) | (shift_type << 5) | rm)

    def strb_reg(self, rd, rn, rm, shift_imm=0, shift_type=0, p=1, u=1, w=0, cond=0xE):
        self.str_reg(rd, rn, rm, shift_imm, shift_type, b=1, p=p, u=u, w=w, cond=cond)

    def strh(self, rd, rn, offset=0, p=1, w=0, cond=0xE):
        u = 1 if offset >= 0 else 0
        assert abs(offset) <= 0xFF, f"Offset {hex(offset)} > 0xFF"
        off = abs(offset) & 0xFF
        self.emit32((cond << 28) | (p << 24) | (u << 23) | (1 << 22) | (w << 21) | (0 << 20) | (rn << 16) | (rd << 12) | ((off >> 4) << 8) | 0xB0 | (off & 0xF))

    def ldrh(self, rd, rn, offset=0, p=1, w=0, cond=0xE):
        u = 1 if offset >= 0 else 0
        assert abs(offset) <= 0xFF, f"Offset {hex(offset)} > 0xFF"
        off = abs(offset) & 0xFF
        self.emit32((cond << 28) | (p << 24) | (u << 23) | (1 << 22) | (w << 21) | (1 << 20) | (rn << 16) | (rd << 12) | ((off >> 4) << 8) | 0xB0 | (off & 0xF))

    def ldrh_reg(self, rd, rn, rm, p=1, u=1, w=0, cond=0xE):
        self.emit32((cond << 28) | (p << 24) | (u << 23) | (0 << 22) | (w << 21) | (1 << 20) | (rn << 16) | (rd << 12) | 0xB0 | (rm & 0xF))

    def strh_reg(self, rd, rn, rm, p=1, u=1, w=0, cond=0xE):
        self.emit32((cond << 28) | (p << 24) | (u << 23) | (0 << 22) | (w << 21) | (0 << 20) | (rn << 16) | (rd << 12) | 0xB0 | (rm & 0xF))

    def ldrsb(self, rd, rn, offset=0, p=1, w=0, cond=0xE):
        u = 1 if offset >= 0 else 0
        assert abs(offset) <= 0xFF, f"Offset {hex(offset)} > 0xFF"
        off = abs(offset) & 0xFF
        self.emit32((cond << 28) | (p << 24) | (u << 23) | (1 << 22) | (w << 21) | (1 << 20) | (rn << 16) | (rd << 12) | ((off >> 4) << 8) | 0xD0 | (off & 0xF))

    def ldrsh(self, rd, rn, offset=0, p=1, w=0, cond=0xE):
        u = 1 if offset >= 0 else 0
        assert abs(offset) <= 0xFF, f"Offset {hex(offset)} > 0xFF"
        off = abs(offset) & 0xFF
        self.emit32((cond << 28) | (p << 24) | (u << 23) | (1 << 22) | (w << 21) | (1 << 20) | (rn << 16) | (rd << 12) | ((off >> 4) << 8) | 0xF0 | (off & 0xF))

    def push(self, reg_list, cond=0xE):
        assert reg_list == sorted(reg_list), f"Unsorted push: {reg_list}"
        mask = 0
        for r in reg_list: mask |= (1 << r)
        self.emit32((cond << 28) | (0b10010010 << 20) | (13 << 16) | (mask & 0xFFFF))

    def pop(self, reg_list, cond=0xE):
        assert reg_list == sorted(reg_list), f"Unsorted pop: {reg_list}"
        mask = 0
        for r in reg_list: mask |= (1 << r)
        self.emit32((cond << 28) | (0b10001011 << 20) | (13 << 16) | (mask & 0xFFFF))

    def bx(self, rm, cond=0xE):
        self.emit32((cond << 28) | 0x012FFF10 | rm)

    def swi(self, num, cond=0xE):
        self.emit32((cond << 28) | (0xF << 24) | ((num & 0xFF) << 16))

    def b(self, label, cond=0xE, link=0):
        off = len(self.code)
        self.fixups.append((off, 'B', label, (cond, link)))
        self.emit32(0)

    def bl(self, label, cond=0xE):
        self.b(label, cond=cond, link=1)

    def resolve(self):
        for off, kind, label, extra in self.fixups:
            if label not in self.labels:
                raise KeyError(f"Undefined label: {label}")
            target = self.labels[label]
            pc = self.base + off + 8
            diff = target - pc
            if kind == 'B':
                cond, link = extra
                imm24 = (diff >> 2) & 0xFFFFFF
                w = (cond << 28) | (0x5 << 25) | (link << 24) | imm24
                struct.pack_into("<I", self.code, off, w)
            elif kind == 'LA':
                cond, rd = extra
                val = target & 0xFFFFFFFF
                b0 = val & 0xFF
                b1 = (val >> 8) & 0xFF
                b2 = (val >> 16) & 0xFF
                b3 = (val >> 24) & 0xFF
                w0 = self.dp_imm(0xD, 0, 0, rd, b0, cond)
                w1 = self.dp_imm(0xC, 0, rd, rd, b1 << 8, cond)
                w2 = self.dp_imm(0xC, 0, rd, rd, b2 << 16, cond)
                w3 = self.dp_imm(0xC, 0, rd, rd, b3 << 24, cond)
                struct.pack_into("<IIII", self.code, off, w0, w1, w2, w3)

# ==============================================================================
# [LIFT-3] Trytris Reference Piece Definitions, Symmetry Group Rotations,
#          Gravity Schedule, Scoring & Achievement Definitions
# Provenance: trytris/index.html (ConsciousNode SoftWorks, MIT),
#             lines 853-1594 & 2067-2070,
#             sha256 349a0be0cf167bae586f29a1b91992664bd143c792be7211a7736d7ae4dd8b34
# Intentional changes: Precomputed canonical rotation state tables (ROT_CELL_TABLE
# and ROT_MASK_TABLE) and whole-frame gravity table (`round(ms * 59.7275 / 1000)`)
# for ARM7TDMI execution without floating point.
# ==============================================================================
import math

TRI_HEIGHT = math.sqrt(3) / 2.0

def is_up_triangle(r, c):
    return ((r + c) & 1) == 0

def rotate_cell_60_cw(r, c):
    h = TRI_HEIGHT
    if is_up_triangle(r, c):
        verts = [[c * 0.5, r * h], [(c - 1) * 0.5, (r + 1) * h], [(c + 1) * 0.5, (r + 1) * h]]
    else:
        verts = [[(c - 1) * 0.5, r * h], [(c + 1) * 0.5, r * h], [c * 0.5, (r + 1) * h]]
    cos60 = 0.5
    sin60 = h
    cx = 0.0
    cy = 0.0
    for x, y in verts:
        rx = x * cos60 - y * sin60
        ry = x * sin60 + y * cos60
        cx += rx
        cy += ry
    cx /= 3.0
    cy /= 3.0
    nr = int(math.floor(cy / h + 1e-6))
    nc = int(round(cx / 0.5))
    return [nr, nc]

def normalize_polyiamond(cells):
    min_r = min(c[0] for c in cells)
    min_c = min(c[1] for c in cells)
    dr = -min_r
    dc = -min_c
    if ((dr + dc) & 1) != 0:
        dc += 1
    shifted = [[r + dr, c + dc] for r, c in cells]
    shifted.sort(key=lambda x: (x[0], x[1]))
    return shifted

def compute_distinct_rotations(canonical_cells):
    states = []
    seen = set()
    curr = [[r, c] for r, c in canonical_cells]
    for _ in range(6):
        norm = normalize_polyiamond(curr)
        key = tuple((r, c) for r, c in norm)
        if key not in seen:
            seen.add(key)
            states.append(norm)
        curr = [rotate_cell_60_cw(r, c) for r, c in curr]
    return states

RAW_PIECES = [
    # 4 Tetriamonds (1..4)
    {"idx": 1,  "id": "P1",  "slug": "bar_l",         "name": "P1 (I-Bar L)",  "color": "#38bdf8", "order": 4, "cells": [[0, 0], [0, 1], [0, 2], [0, 3]]},
    {"idx": 2,  "id": "P2",  "slug": "bar_r",         "name": "P2 (I-Bar R)",  "color": "#60a5fa", "order": 4, "cells": [[0, 0], [1, 0], [1, 1], [2, 1]]},
    {"idx": 3,  "id": "P3",  "slug": "crook",         "name": "P3 (Crook)",    "color": "#f59e0b", "order": 4, "cells": [[0, 0], [0, 1], [0, 2], [1, 0]]},
    {"idx": 4,  "id": "P4",  "slug": "pyramid",       "name": "P4 (Triangle)", "color": "#a855f7", "order": 4, "cells": [[0, 1], [0, 2], [0, 3], [1, 2]]},
    # 12 Free Hexiamonds (5..16)
    {"idx": 5,  "id": "H1",  "slug": "parallelogram", "name": "parallelogram", "color": "#2dd4bf", "order": 6, "cells": [[0, 0], [0, 1], [0, 2], [0, 3], [0, 4], [0, 5]]},
    {"idx": 6,  "id": "H2",  "slug": "hook",          "name": "hook",          "color": "#fb7185", "order": 6, "cells": [[0, 0], [0, 1], [0, 2], [0, 3], [0, 4], [1, 0]]},
    {"idx": 7,  "id": "H3",  "slug": "triangle",      "name": "triangle",      "color": "#facc15", "order": 6, "cells": [[0, 0], [0, 1], [0, 2], [0, 3], [0, 4], [1, 2]]},
    {"idx": 8,  "id": "H4",  "slug": "chevron",       "name": "chevron",       "color": "#818cf8", "order": 6, "cells": [[0, 0], [0, 1], [0, 2], [0, 3], [1, 0], [1, 1]]},
    {"idx": 9,  "id": "H5",  "slug": "sphinx",        "name": "sphinx",        "color": "#f97316", "order": 6, "cells": [[0, 0], [0, 1], [0, 2], [0, 3], [1, 0], [1, 2]]},
    {"idx": 10, "id": "H6",  "slug": "bat",           "name": "bat",           "color": "#c084fc", "order": 6, "cells": [[0, 0], [0, 1], [0, 2], [0, 3], [1, 1], [1, 2]]},
    {"idx": 11, "id": "H7",  "slug": "yacht",         "name": "yacht",         "color": "#34d399", "order": 6, "cells": [[0, 0], [0, 1], [0, 2], [0, 3], [1, 2], [1, 3]]},
    {"idx": 12, "id": "H8",  "slug": "hexagon",       "name": "hexagon",       "color": "#f43f5e", "order": 6, "cells": [[0, 0], [0, 1], [0, 2], [1, 0], [1, 1], [1, 2]]},
    {"idx": 13, "id": "H9",  "slug": "snake",         "name": "snake",         "color": "#4ade80", "order": 6, "cells": [[0, 0], [0, 1], [0, 2], [1, 2], [1, 3], [1, 4]]},
    {"idx": 14, "id": "H10", "slug": "lobster",       "name": "lobster",       "color": "#fb923c", "order": 6, "cells": [[0, 0], [1, 0], [1, 1], [2, 0], [2, 1], [2, 2]]},
    {"idx": 15, "id": "H11", "slug": "rhombus",       "name": "rhombus",       "color": "#22d3ee", "order": 6, "cells": [[0, 0], [1, 0], [1, 1], [2, 0], [2, 1], [3, 0]]},
    {"idx": 16, "id": "H12", "slug": "butterfly",     "name": "butterfly",     "color": "#e879f9", "order": 6, "cells": [[0, 1], [0, 2], [0, 3], [1, 1], [1, 2], [1, 3]]},
]

for p in RAW_PIECES:
    rots = compute_distinct_rotations(p["cells"])
    p["rotations"] = rots
    p["sym"] = len(rots)
    p["bgr"] = hex_to_bgr555(p["color"])
    c = p["bgr"]
    r = ((c & 0x1F) >> 2) + 2
    g = (((c >> 5) & 0x1F) >> 2) + 2
    b = (((c >> 10) & 0x1F) >> 2) + 3
    p["ghost_bgr"] = rgb15(r, g, b)

ACHIEVEMENT_DEFS = [
    ("Triforce",         "Clear 3 rows simultaneously"),
    ("Sphinx Riddle",    "Lock sphinx in a completed row"),
    ("Butterfly Effect", "Clear a row with butterfly"),
    ("Cursed!",          "Reach L5 in CURSED mode"),
    ("No Mercy",         "Reach L10 in HEXIAMOND mode"),
    ("Geodesic",         "Clear 100 lines in one game"),
    ("Zero State",       "All-clear the entire board"),
    ("Helix",            "Clear lines on 10 locks in a row"),
    ("Ternary Perfect",  "Lowest 3 rows occupied only by UP"),
    ("Patient",          "Lock after 30s idle at L5+"),
]

GRAVITY_FRAMES = [0] + [
    int(round(max(110, 850 - (lvl - 1) * 50) * 59.7275 / 1000.0))
    for lvl in range(1, 16)
]

# Memory Map Constants
STATE_BASE       = 0x03000000
MB_BASE          = 0x0203FC00
SRAM_BASE        = 0x0E000000
VRAM_BASE        = 0x06000000
IO_BASE          = 0x04000000

# State Offsets (relative to STATE_BASE = 0x03000000)
S_FRAME          = 0x000
S_SCREEN         = 0x004
S_ACCEPT_INPUT   = 0x005
S_MODE           = 0x006
S_GHOST          = 0x007
S_SEED           = 0x008
S_PRNG           = 0x00C
S_SCORE          = 0x010
S_LINES          = 0x014
S_LEVEL          = 0x018
S_COMBO          = 0x01C
S_B2B            = 0x020
S_GAMEOVER       = 0x021
S_PAUSED         = 0x022
S_BAG_LEN        = 0x023
S_VOCAB_SIG      = 0x024
S_ACT_ID         = 0x025
S_ACT_ROT        = 0x026
S_ACT_R          = 0x027
S_ACT_C          = 0x028
S_GHOST_R        = 0x029
S_GHOST_C        = 0x02A
S_DIRTY_UI       = 0x02B
S_ACH_MASK       = 0x02C
S_LAG_COUNT      = 0x030
S_TICKS          = 0x034
S_IDLE_FRAMES    = 0x038
S_GRAV_TIMER     = 0x03C
S_CALL_TOTAL     = 0x040
S_LOCK_TOTAL     = 0x044
S_KEY_PREV       = 0x048
S_KEY_CURR       = 0x04A
S_KEY_DOWN       = 0x04C
S_DAS_DIR        = 0x04E
S_DAS_TIMER      = 0x04F
S_TITLE_CURSOR   = 0x050
S_SEED_DIGIT     = 0x051
S_ACH_SCROLL     = 0x052
S_TOAST_ACH      = 0x053
S_TOAST_TIMER    = 0x054
S_TITLE_IDLE     = 0x056
S_ATTRACT_MODE_IX= 0x058
S_ATTRACT_GAMES  = 0x059
S_ATTRACT_WAIT   = 0x05A
S_BOT_PLAN_LEN   = 0x05C
S_BOT_PLAN_POS   = 0x05D
S_BOT_TICK_DIV   = 0x05E
S_BOT_PIECE_SEQ  = 0x05F
S_MUSIC_TICK     = 0x060
S_MUSIC_NOTE     = 0x062
S_SAVE_VALID     = 0x064
S_LAST_LOCK_LINES= 0x065
S_IN_FRAME       = 0x066
S_HS_SAVED_FLAG  = 0x067
S_PREV_ACT_ID    = 0x068
S_PREV_ACT_ROT   = 0x069
S_PREV_ACT_R     = 0x06A
S_PREV_ACT_C     = 0x06B
S_PREV_GHOST_R   = 0x06C
S_PREV_GHOST_C   = 0x06D
S_BOARD_DIRTY    = 0x06E
S_HUD_DIRTY      = 0x06F
S_SUPPRESS_LOG   = 0x070

S_BAG_BUF        = 0x080  # 32 bytes
S_BOT_PLAN_BUF   = 0x0A0  # 32 bytes
S_BOT_BEST_BUF   = 0x0C0  # 32 bytes
S_HIGH_SCORES    = 0x0E0  # 60 bytes (3 modes * 5 uint32)
S_BOARD_MASKS    = 0x120  # 56 bytes (28 * uint16)
S_SIM_MASKS      = 0x160  # 56 bytes (28 * uint16)
S_BOARD_CELLS    = 0x200  # 336 bytes (28 * 12 uint8)
S_SEEN_LANDING   = 0x360  # 672 bytes (6 * 28 uint32 bitmap)

# Module 2: Core Engine & Mailbox Assembly Emitters


def emit_engine_subroutines(a: ArmBuilder):
    # ==========================================================================
    # Subroutine: mulberry32_next() -> R0 = uint32 random value
    # Clobbers: R1, R2, R3
    # Uses R11 = STATE_BASE (0x03000000)
    # ==========================================================================
    a.label("mulberry32_next")
    a.ldr(0, 11, S_PRNG)
    a.li32(1, 0x6D2B79F5)
    a.add_reg(0, 0, 1)
    a.str(0, 11, S_PRNG)
    # t = Math.imul(t ^ (t >>> 15), t | 1)
    a.eor_reg(1, 0, 0, shift_imm=15, shift_type=a.LSR)
    a.orr_imm(2, 0, 1)
    a.mul(0, 1, 2)
    # t ^= t + Math.imul(t ^ (t >>> 7), t | 61)
    a.eor_reg(1, 0, 0, shift_imm=7, shift_type=a.LSR)
    a.orr_imm(2, 0, 61)
    a.mul(3, 1, 2)
    a.add_reg(3, 0, 3)
    a.eor_reg(0, 0, 3)
    # return (t ^ (t >>> 14)) >>> 0
    a.eor_reg(0, 0, 0, shift_imm=14, shift_type=a.LSR)
    a.bx(14)

    # ==========================================================================
    # Subroutine: get_vocab_sig(R0=mode, R1=level) -> R0 = sig (1=TET4, 2=CURSED16, 3=HEX12)
    # ==========================================================================
    a.label("get_vocab_sig")
    a.cmp_imm(0, 2)
    a.mov_imm(0, 3, cond=a.EQ)
    a.bx(14, cond=a.EQ)
    a.cmp_imm(0, 1)
    a.bne_or_ret = None
    a.mov_imm(0, 1, cond=a.NE)
    a.bx(14, cond=a.NE)
    # mode == 1 (CURSED): check level >= 5
    a.cmp_imm(1, 5)
    a.mov_imm(0, 2, cond=a.GE)
    a.mov_imm(0, 1, cond=a.LT)
    a.bx(14)

    # ==========================================================================
    # Subroutine: bag_sync_vocab()
    # Checks if vocab signature changed; filters or flushes bag accordingly.
    # ==========================================================================
    a.label("bag_sync_vocab")
    a.push([4, 5, 6, 7, 8, 14])
    a.ldrb(0, 11, S_MODE)
    a.ldr(1, 11, S_LEVEL)
    a.bl("get_vocab_sig")
    a.mov_reg(4, 0)                     # R4 = new sig
    a.ldrb(5, 11, S_VOCAB_SIG)          # R5 = old sig
    a.cmp_reg(4, 5)
    a.b("bsv_done", cond=a.EQ)

    # If sig == 2 (CURSED16) and old_sig == 1 (TET4), flush bag to 0
    a.cmp_imm(4, 2)
    a. b("bsv_check_filter", cond=a.NE)
    a.cmp_imm(5, 1)
    a.mov_imm(0, 0, cond=a.EQ)
    a.strb(0, 11, S_BAG_LEN, cond=a.EQ)
    a.b("bsv_store_sig", cond=a.EQ)

    a.label("bsv_check_filter")
    # Filter existing bag items against allowed range for sig R4:
    # sig=1 (TET4): 1..4; sig=2 (CURSED16): 1..16; sig=3 (HEX12): 5..16
    a.ldrb(6, 11, S_BAG_LEN)
    a.mov_imm(7, 0)                     # R7 = read idx
    a.mov_imm(8, 0)                     # R8 = write idx
    a.add_imm(2, 11, S_BAG_BUF)
    a.label("bsv_loop")
    a.cmp_reg(7, 6)
    a.b("bsv_loop_end", cond=a.GE)
    a.ldrb_reg(0, 2, 7)                 # pieceId
    a.cmp_imm(4, 1)
    a.b("bsv_chk_hex", cond=a.NE)
    # TET4: keep if <= 4
    a.cmp_imm(0, 4)
    a.strb_reg(0, 2, 8, cond=a.LS)
    a.add_imm(8, 8, 1, cond=a.LS)
    a.b("bsv_next")
    a.label("bsv_chk_hex")
    a.cmp_imm(4, 3)
    a.b("bsv_keep_all", cond=a.NE)
    # HEX12: keep if >= 5
    a.cmp_imm(0, 5)
    a.strb_reg(0, 2, 8, cond=a.HS)
    a.add_imm(8, 8, 1, cond=a.HS)
    a.b("bsv_next")
    a.label("bsv_keep_all")
    a.strb_reg(0, 2, 8)
    a.add_imm(8, 8, 1)
    a.label("bsv_next")
    a.add_imm(7, 7, 1)
    a.b("bsv_loop")
    a.label("bsv_loop_end")
    a.strb(8, 11, S_BAG_LEN)

    a.label("bsv_store_sig")
    a.strb(4, 11, S_VOCAB_SIG)
    a.label("bsv_done")
    a.pop([4, 5, 6, 7, 8, 15])

    # ==========================================================================
    # Subroutine: bag_refill()
    # Appends one shuffled vocabulary bag to S_BAG_BUF using Mulberry32.
    # ==========================================================================
    a.label("bag_refill")
    a.push([4, 5, 6, 7, 8, 9, 14])
    a.ldrb(0, 11, S_MODE)
    a.ldr(1, 11, S_LEVEL)
    a.bl("get_vocab_sig")
    # R0 = 1 (TET4: 1..4, len 4), 2 (CURSED16: 1..16, len 16), 3 (HEX12: 5..16, len 12)
    a.cmp_imm(0, 1)
    a.mov_imm(4, 1, cond=a.EQ)          # R4 = start pieceId
    a.mov_imm(5, 4, cond=a.EQ)          # R5 = count
    a.cmp_imm(0, 2)
    a.mov_imm(4, 1, cond=a.EQ)
    a.mov_imm(5, 16, cond=a.EQ)
    a.cmp_imm(0, 3)
    a.mov_imm(4, 5, cond=a.EQ)
    a.mov_imm(5, 12, cond=a.EQ)

    # Use stack 16 bytes for temp items array
    a.sub_imm(13, 13, 16)
    a.mov_imm(6, 0)
    a.label("br_init_loop")
    a.add_reg(0, 4, 6)
    a.strb_reg(0, 13, 6)
    a.add_imm(6, 6, 1)
    a.cmp_reg(6, 5)
    a.b("br_init_loop", cond=a.LT)

    # Fisher-Yates: for i = count - 1 down to 1
    a.sub_imm(6, 5, 1)                  # R6 = i
    a.label("br_fy_loop")
    a.bl("mulberry32_next")             # R0 = u32
    a.add_imm(1, 6, 1)                  # R1 = i + 1
    a.umull(2, 3, 0, 1)                 # R3 = floor(prng() * (i + 1)) = j
    # swap temp[i] and temp[j]
    a.ldrb_reg(7, 13, 6)                # R7 = items[i]
    a.ldrb_reg(8, 13, 3)                # R8 = items[j]
    a.strb_reg(8, 13, 6)
    a.strb_reg(7, 13, 3)
    a.sub_imm(6, 6, 1, s=1)
    a.b("br_fy_loop", cond=a.GT)

    # Append R5 items to S_BAG_BUF + S_BAG_LEN
    a.ldrb(7, 11, S_BAG_LEN)
    a.add_imm(8, 11, S_BAG_BUF)
    a.mov_imm(6, 0)
    a.label("br_copy_loop")
    a.ldrb_reg(0, 13, 6)
    a.strb_reg(0, 8, 7)
    a.add_imm(7, 7, 1)
    a.add_imm(6, 6, 1)
    a.cmp_reg(6, 5)
    a.b("br_copy_loop", cond=a.LT)
    a.strb(7, 11, S_BAG_LEN)

    a.add_imm(13, 13, 16)
    a.pop([4, 5, 6, 7, 8, 9, 15])

    # ==========================================================================
    # Subroutine: bag_next_piece() -> R0 = pieceId (1..16)
    # ==========================================================================
    a.label("bag_next_piece")
    a.push([4, 5, 14])
    a.bl("bag_sync_vocab")
    a.label("bnp_refill_check")
    a.ldrb(0, 11, S_BAG_LEN)
    a.cmp_imm(0, 3)
    a.b("bnp_pop", cond=a.GT)
    a.bl("bag_refill")
    a.b("bnp_refill_check")

    a.label("bnp_pop")
    a.add_imm(4, 11, S_BAG_BUF)
    a.ldrb(0, 4, 0)                     # R0 = bag[0]
    a.ldrb(5, 11, S_BAG_LEN)
    a.sub_imm(5, 5, 1)
    a.strb(5, 11, S_BAG_LEN)
    # Shift remaining items left by 1
    a.mov_imm(1, 0)
    a.label("bnp_shift_loop")
    a.cmp_reg(1, 5)
    a.b("bnp_done", cond=a.GE)
    a.add_imm(2, 1, 1)
    a.ldrb_reg(3, 4, 2)
    a.strb_reg(3, 4, 1)
    a.add_imm(1, 1, 1)
    a.b("bnp_shift_loop")
    a.label("bnp_done")
    a.pop([4, 5, 15])

    # ==========================================================================
    # Subroutine: bag_ensure_preview()
    # Ensures at least 3 pieces are in S_BAG_BUF for peekPreview(3).
    # ==========================================================================
    a.label("bag_ensure_preview")
    a.push([14])
    a.bl("bag_sync_vocab")
    a.label("bep_loop")
    a.ldrb(0, 11, S_BAG_LEN)
    a.cmp_imm(0, 3)
    a.pop([15], cond=a.GE)
    a.bl("bag_refill")
    a.b("bep_loop")

    # ==========================================================================
    # Subroutine: unlock_achievement(R0=ach_idx 0..9)
    # ==========================================================================
    a.label("unlock_achievement")
    a.push([4, 5, 14])
    a.ldr(4, 11, S_ACH_MASK)
    a.mov_imm(5, 1)
    a.mov_reg_rs(5, 5, 0, shift_type=a.LSL)
    a.tst_reg(4, 5)
    a.b("ua_done", cond=a.NE)
    a.orr_reg(4, 4, 5)
    a.str(4, 11, S_ACH_MASK)
    a.strb(0, 11, S_TOAST_ACH)
    a.mov_imm(1, 120)
    a.strh(1, 11, S_TOAST_TIMER)
    a.mov_imm(1, 1)
    a.strb(1, 11, S_HUD_DIRTY)
    # Trigger SFX for achievement unlock (sfx_id = 6)
    a.mov_imm(0, 6)
    a.bl("sfx_play")
    a.label("ua_done")
    a.pop([4, 5, 15])

    # ==========================================================================
    # Subroutine: check_mode_level_achievements()
    # ==========================================================================
    a.label("check_mode_level_achievements")
    a.push([14])
    a.ldrb(0, 11, S_MODE)
    a.ldr(1, 11, S_LEVEL)
    a.cmp_imm(0, 1)                     # CURSED
    a.b("cmla_chk_hex", cond=a.NE)
    a.cmp_imm(1, 5)
    a.b("cmla_chk_hex", cond=a.LT)
    a.mov_imm(0, 3)                     # Ach 3: Cursed!
    a.bl("unlock_achievement")
    a.label("cmla_chk_hex")
    a.ldrb(0, 11, S_MODE)
    a.ldr(1, 11, S_LEVEL)
    a.cmp_imm(0, 2)                     # HEXIAMOND
    a.b("cmla_done", cond=a.NE)
    a.cmp_imm(1, 10)
    a.b("cmla_done", cond=a.LT)
    a.mov_imm(0, 4)                     # Ach 4: No Mercy
    a.bl("unlock_achievement")
    a.label("cmla_done")
    a.pop([15])

    # ==========================================================================
    # Subroutine: log_engine_call(R0=call_code 1..7, R1=result)
    # Writes to Mailbox ring buffer at 0x0203FE00 if S_SUPPRESS_LOG == 0.
    # Entry format (4 bytes):
    #   +0x00: uint16 (frame_counter & 0xFFFF)
    #   +0x02: uint8  call_code
    #   +0x03: int8   result
    # ==========================================================================
    a.label("log_engine_call")
    a.ldrb(2, 11, S_SUPPRESS_LOG)
    a.cmp_imm(2, 0)
    a.bx(14, cond=a.NE)
    a.push([4, 5, 6, 14])
    a.ldr(4, 11, S_CALL_TOTAL)
    a.and_imm(5, 4, 63)                 # idx = total & 63
    a.add_imm(4, 4, 1)
    a.str(4, 11, S_CALL_TOTAL)
    a.li32(6, MB_BASE + 0x200)
    a.add_reg(6, 6, 5, shift_imm=2, shift_type=a.LSL)
    a.ldr(2, 11, S_FRAME)
    a.strh(2, 6, 0)
    a.strb(0, 6, 2)
    a.strb(1, 6, 3)
    a.pop([4, 5, 6, 15])

    # ==========================================================================
    # Subroutine: get_rot_mask_ptr(R0=pieceId, R1=rotIndex) -> R0 = ptr to 16-byte ROT_MASK_TABLE entry
    # ==========================================================================
    a.label("get_rot_mask_ptr")
    a.add_reg(2, 0, 0, shift_imm=1, shift_type=a.LSL)   # R2 = pieceId * 3
    a.mov_reg(2, 2, shift_imm=1, shift_type=a.LSL)      # R2 = pieceId * 6
    a.add_reg(2, 2, 1)                                  # R2 = pieceId * 6 + rot
    a.la(0, "rot_mask_table")
    a.add_reg(0, 0, 2, shift_imm=4, shift_type=a.LSL)   # + (pieceId*6+rot)*16
    a.bx(14)

    # ==========================================================================
    # Subroutine: get_rot_cell_ptr(R0=pieceId, R1=rotIndex) -> R0 = ptr to 16-byte ROT_CELL_TABLE entry
    # ==========================================================================
    a.label("get_rot_cell_ptr")
    a.add_reg(2, 0, 0, shift_imm=1, shift_type=a.LSL)
    a.mov_reg(2, 2, shift_imm=1, shift_type=a.LSL)
    a.add_reg(2, 2, 1)
    a.la(0, "rot_cell_table")
    a.add_reg(0, 0, 2, shift_imm=4, shift_type=a.LSL)
    a.bx(14)

    # ==========================================================================
    # Subroutine: can_place_masks(R0=pieceId, R1=rotIndex, R2=anchorR, R3=anchorC, R4=row_masks_base)
    # Returns R0 = 1 if legal, 0 if blocked/out-of-bounds.
    # Preserves R4..R11.
    # ==========================================================================
    a.label("can_place_masks")
    a.push([4, 5, 6, 7, 14])
    # 1. Parity check: ((anchorR + anchorC) & 1) == 0
    a.add_reg(5, 2, 3)
    a.tst_imm(5, 1)
    a.b("cpm_fail", cond=a.NE)
    # 2. Bounds check: anchorR >= 0
    a.cmp_imm(2, 0)
    a.b("cpm_fail", cond=a.LT)
    # 3. Lookup ROT_MASK_TABLE entry (preserve R2=anchorR across get_rot_mask_ptr!)
    a.mov_reg(6, 2)                     # save anchorR in R6
    a.bl("get_rot_mask_ptr")            # R0 = entry ptr
    a.mov_reg(2, 6)                     # restore anchorR
    a.ldrb(5, 0, 13)                    # min_dc (0 or 1)
    a.add_reg(5, 3, 5)                  # anchorC + min_dc >= 0
    a.cmp_imm(5, 0)
    a.b("cpm_fail", cond=a.LT)
    a.ldrb(5, 0, 8)                     # max_dr
    a.add_reg(5, 2, 5)                  # anchorR + max_dr
    a.cmp_imm(5, 28)
    a.b("cpm_fail", cond=a.GE)
    a.ldrb(5, 0, 9)                     # max_dc
    a.add_reg(5, 3, 5)                  # anchorC + max_dc
    a.cmp_imm(5, 12)
    a.b("cpm_fail", cond=a.GE)
    # 4. Unrolled 4-row mask check (use shift = anchorC + 1 against piece_mask >> 1 when anchorC == -1)
    a.add_reg(4, 4, 2, shift_imm=1, shift_type=a.LSL) # R4 = &row_masks[anchorR]
    a.cmp_imm(3, 0)
    a.b("cpm_neg_c", cond=a.LT)
    a.ldrh(1, 0, 0); a.ldrh(5, 4, 0); a.mov_reg_rs(1, 1, 3, shift_type=a.LSL); a.tst_reg(5, 1); a.b("cpm_fail", cond=a.NE)
    a.ldrh(1, 0, 2); a.ldrh(5, 4, 2); a.mov_reg_rs(1, 1, 3, shift_type=a.LSL); a.tst_reg(5, 1); a.b("cpm_fail", cond=a.NE)
    a.ldrh(1, 0, 4); a.ldrh(5, 4, 4); a.mov_reg_rs(1, 1, 3, shift_type=a.LSL); a.tst_reg(5, 1); a.b("cpm_fail", cond=a.NE)
    a.ldrh(1, 0, 6); a.ldrh(5, 4, 6); a.mov_reg_rs(1, 1, 3, shift_type=a.LSL); a.tst_reg(5, 1); a.b("cpm_fail", cond=a.NE)
    a.mov_imm(0, 1)
    a.pop([4, 5, 6, 7, 15])
    a.label("cpm_neg_c")
    # anchorC == -1 (with min_dc == 1, so bit 0 of every piece_mask is 0): shift right by 1!
    a.ldrh(1, 0, 0); a.ldrh(5, 4, 0); a.tst_reg(5, 1, shift_imm=1, shift_type=a.LSR); a.b("cpm_fail", cond=a.NE)
    a.ldrh(1, 0, 2); a.ldrh(5, 4, 2); a.tst_reg(5, 1, shift_imm=1, shift_type=a.LSR); a.b("cpm_fail", cond=a.NE)
    a.ldrh(1, 0, 4); a.ldrh(5, 4, 4); a.tst_reg(5, 1, shift_imm=1, shift_type=a.LSR); a.b("cpm_fail", cond=a.NE)
    a.ldrh(1, 0, 6); a.ldrh(5, 4, 6); a.tst_reg(5, 1, shift_imm=1, shift_type=a.LSR); a.b("cpm_fail", cond=a.NE)

    a.mov_imm(0, 1)
    a.pop([4, 5, 6, 7, 15])
    a.label("cpm_fail")
    a.mov_imm(0, 0)
    a.pop([4, 5, 6, 7, 15])

    # Fix tiny detail in cpm_row_loop above: remove the redundant `ldrh_reg(1, 0, 7)` before `ldrh(1, 0, 2, p=0)`.

    # ==========================================================================
    # Subroutine: can_place_live(R0=pieceId, R1=rotIndex, R2=anchorR, R3=anchorC) -> R0 = 1/0
    # ==========================================================================
    a.label("can_place_live")
    a.push([4, 14])
    a.add_imm(4, 11, S_BOARD_MASKS)
    a.bl("can_place_masks")
    a.pop([4, 15])

    # ==========================================================================
    # Subroutine: update_ghost_piece()
    # Computes landing (r, c) of activePiece and stores in S_GHOST_R, S_GHOST_C.
    # ==========================================================================
    a.label("update_ghost_piece")
    a.push([4, 5, 6, 7, 8, 14])
    a.ldrb(4, 11, S_ACT_ID)
    a.cmp_imm(4, 0)
    a.b("ugp_done", cond=a.EQ)
    a.ldrb(5, 11, S_ACT_ROT)
    a.ldrsb(6, 11, S_ACT_R)             # R6 = ghost.r
    a.ldrsb(7, 11, S_ACT_C)             # R7 = ghost.c

    a.label("ugp_loop")
    # zigDir = (ghost.r & 1) == 0 ? 1 : -1
    a.tst_imm(6, 1)
    a.mov_imm(8, 1, cond=a.EQ)
    a.mvn_imm(8, 0, cond=a.NE)          # R8 = zigDir (+1 or -1)

    # Try (ghost.r + 1, ghost.c + zigDir)
    a.mov_reg(0, 4); a.mov_reg(1, 5)
    a.add_imm(2, 6, 1)
    a.add_reg(3, 7, 8)
    a.bl("can_place_live")
    a.cmp_imm(0, 1)
    a.b("ugp_try2", cond=a.NE)
    a.add_imm(6, 6, 1)
    a.add_reg(7, 7, 8)
    a.b("ugp_loop")

    a.label("ugp_try2")
    # Try (ghost.r + 1, ghost.c - zigDir)
    a.mov_reg(0, 4); a.mov_reg(1, 5)
    a.add_imm(2, 6, 1)
    a.sub_reg(3, 7, 8)
    a.bl("can_place_live")
    a.cmp_imm(0, 1)
    a.b("ugp_try3", cond=a.NE)
    a.add_imm(6, 6, 1)
    a.sub_reg(7, 7, 8)
    a.b("ugp_loop")

    a.label("ugp_try3")
    # Try (ghost.r + 2, ghost.c)
    a.mov_reg(0, 4); a.mov_reg(1, 5)
    a.add_imm(2, 6, 2)
    a.mov_reg(3, 7)
    a.bl("can_place_live")
    a.cmp_imm(0, 1)
    a.b("ugp_store", cond=a.NE)
    a.add_imm(6, 6, 2)
    a.b("ugp_loop")

    a.label("ugp_store")

    a.strb(6, 11, S_GHOST_R)
    a.strb(7, 11, S_GHOST_C)
    a.label("ugp_done")
    a.pop([4, 5, 6, 7, 8, 15])

    # ==========================================================================
    # Subroutine: spawn_next_piece()
    # Pulls next piece from bagGen, sets anchor (1, 3), rotIndex 0,
    # checks canPlace -> sets gameOver if blocked, updates ghost piece.
    # ==========================================================================
    a.label("spawn_next_piece")
    a.push([4, 14])
    a.bl("bag_next_piece")              # R0 = pieceId (1..16)
    a.mov_reg(4, 0)
    a.bl("bag_ensure_preview")          # Ensure 3 preview pieces ready
    a.strb(4, 11, S_ACT_ID)
    a.mov_imm(0, 0)
    a.strb(0, 11, S_ACT_ROT)
    a.mov_imm(0, 1)
    a.strb(0, 11, S_ACT_R)
    a.mov_imm(0, 3)
    a.strb(0, 11, S_ACT_C)

    # Increment S_BOT_PIECE_SEQ so attract mode knows a new piece spawned
    a.ldrb(0, 11, S_BOT_PIECE_SEQ)
    a.add_imm(0, 0, 1)
    a.strb(0, 11, S_BOT_PIECE_SEQ)

    # Check if legal at (1, 3)
    a.mov_reg(0, 4)
    a.mov_imm(1, 0)
    a.mov_imm(2, 1)
    a.mov_imm(3, 3)
    a.bl("can_place_live")
    a.cmp_imm(0, 0)
    a.mov_imm(1, 1, cond=a.EQ)
    a.strb(1, 11, S_GAMEOVER, cond=a.EQ)
    a.bl("update_ghost_piece")
    a.mov_imm(0, 1)
    a.strb(0, 11, S_HUD_DIRTY)
    a.pop([4, 15])

    # ==========================================================================
    # Subroutine: step_gravity_down() -> R0 = 1 if moved down, 0 if blocked
    # ==========================================================================
    a.label("step_gravity_down")
    a.push([4, 5, 6, 7, 8, 14])
    a.ldrb(4, 11, S_ACT_ID)
    a.cmp_imm(4, 0)
    a.mov_imm(0, 0, cond=a.EQ)
    a.pop([4, 5, 6, 7, 8, 15], cond=a.EQ)
    a.ldrb(5, 11, S_ACT_ROT)
    a.ldrsb(6, 11, S_ACT_R)
    a.ldrsb(7, 11, S_ACT_C)

    a.tst_imm(6, 1)
    a.mov_imm(8, 1, cond=a.EQ)
    a.mvn_imm(8, 0, cond=a.NE)          # R8 = zigDir

    # 1. Try (r + 1, c + zigDir)
    a.mov_reg(0, 4); a.mov_reg(1, 5)
    a.add_imm(2, 6, 1)
    a.add_reg(3, 7, 8)
    a.bl("can_place_live")
    a.cmp_imm(0, 1)
    a.b("sgd_try2", cond=a.NE)
    a.add_imm(6, 6, 1)
    a.add_reg(7, 7, 8)
    a.strb(6, 11, S_ACT_R)
    a.strb(7, 11, S_ACT_C)
    a.bl("update_ghost_piece")
    a.mov_imm(0, 1)
    a.pop([4, 5, 6, 7, 8, 15])

    a.label("sgd_try2")
    # 2. Try (r + 1, c - zigDir)
    a.mov_reg(0, 4); a.mov_reg(1, 5)
    a.add_imm(2, 6, 1)
    a.sub_reg(3, 7, 8)
    a.bl("can_place_live")
    a.cmp_imm(0, 1)
    a.b("sgd_try3", cond=a.NE)
    a.add_imm(6, 6, 1)
    a.sub_reg(7, 7, 8)
    a.strb(6, 11, S_ACT_R)
    a.strb(7, 11, S_ACT_C)
    a.bl("update_ghost_piece")
    a.mov_imm(0, 1)
    a.pop([4, 5, 6, 7, 8, 15])

    a.label("sgd_try3")
    # 3. Try (r + 2, c)
    a.mov_reg(0, 4); a.mov_reg(1, 5)
    a.add_imm(2, 6, 2)
    a.mov_reg(3, 7)
    a.bl("can_place_live")
    a.cmp_imm(0, 1)
    a.mov_imm(0, 0, cond=a.NE)
    a.pop([4, 5, 6, 7, 8, 15], cond=a.NE)
    a.add_imm(6, 6, 2)
    a.strb(6, 11, S_ACT_R)
    a.bl("update_ghost_piece")
    a.mov_imm(0, 1)
    a.pop([4, 5, 6, 7, 8, 15])

    # ==========================================================================
    # Subroutine: eng_move_horizontal(R0=dir: -1 or +1) -> R0 = 1/0
    # Logs call_code 1 (if dir==-1) or 2 (if dir==+1) with result.
    # ==========================================================================
    a.label("eng_move_horizontal")
    a.push([4, 5, 6, 7, 8, 14])
    a.mov_reg(8, 0)                     # R8 = dir (-1 or +1)
    a.ldrb(0, 11, S_GAMEOVER)
    a.ldrb(1, 11, S_PAUSED)
    a.orr_reg(0, 0, 1, s=1)
    a.b("emh_ret_zero", cond=a.NE)
    a.ldrb(4, 11, S_ACT_ID)
    a.cmp_imm(4, 0)
    a.b("emh_ret_zero", cond=a.EQ)

    # Reset idle frames
    a.mov_imm(0, 0)
    a.str(0, 11, S_IDLE_FRAMES)

    a.ldrb(5, 11, S_ACT_ROT)
    a.ldrsb(6, 11, S_ACT_R)
    a.ldrsb(7, 11, S_ACT_C)

    # 1. Try (r, c + dir * 2)
    a.mov_reg(0, 4); a.mov_reg(1, 5); a.mov_reg(2, 6)
    a.add_reg(3, 7, 8, shift_imm=1, shift_type=a.LSL)
    a.bl("can_place_live")
    a.cmp_imm(0, 1)
    a.b("emh_try_diag", cond=a.NE)
    a.add_reg(7, 7, 8, shift_imm=1, shift_type=a.LSL)
    a.strb(7, 11, S_ACT_C)
    a.bl("update_ghost_piece")
    a.mov_imm(0, 1)
    a.bl("sfx_play")
    a.mov_imm(1, 1)
    a.b("emh_log")

    a.label("emh_try_diag")
    # 2. Try (r + 1, c + dir)
    a.mov_reg(0, 4); a.mov_reg(1, 5)
    a.add_imm(2, 6, 1)
    a.add_reg(3, 7, 8)
    a.bl("can_place_live")
    a.cmp_imm(0, 1)
    a.b("emh_fail", cond=a.NE)
    a.add_imm(6, 6, 1)
    a.add_reg(7, 7, 8)
    a.strb(6, 11, S_ACT_R)
    a.strb(7, 11, S_ACT_C)
    a.bl("update_ghost_piece")
    a.mov_imm(0, 1)
    a.bl("sfx_play")
    a.mov_imm(1, 1)
    a.b("emh_log")

    a.label("emh_fail")
    a.mov_imm(1, 0)
    a.b("emh_log")

    a.label("emh_ret_zero")
    a.mov_imm(1, 0)

    a.label("emh_log")
    # R8 = dir (-1 -> code 1, +1 -> code 2), R1 = result
    a.mov_reg(4, 1)                     # save result in R4
    a.cmp_imm(8, 1)
    a.mov_imm(0, 2, cond=a.EQ)
    a.mov_imm(0, 1, cond=a.NE)
    a.bl("log_engine_call")
    a.mov_reg(0, 4)
    a.pop([4, 5, 6, 7, 8, 15])

    # ==========================================================================
    # Subroutine: eng_rotate(R0=dir: +1 CW or -1 CCW) -> R0 = 1/0
    # Logs call_code 3 (if dir==+1) or 4 (if dir==-1) with result.
    # ==========================================================================
    a.label("eng_rotate")
    a.push([4, 5, 6, 7, 8, 9, 10, 14])
    a.mov_reg(8, 0)                     # R8 = dir (+1 or -1)
    a.ldrb(0, 11, S_GAMEOVER)
    a.ldrb(1, 11, S_PAUSED)
    a.orr_reg(0, 0, 1, s=1)
    a.b("erot_ret_zero", cond=a.NE)
    a.ldrb(4, 11, S_ACT_ID)
    a.cmp_imm(4, 0)
    a.b("erot_ret_zero", cond=a.EQ)

    # Reset idle frames
    a.mov_imm(0, 0)
    a.str(0, 11, S_IDLE_FRAMES)

    a.ldrb(5, 11, S_ACT_ROT)
    a.ldrsb(6, 11, S_ACT_R)
    a.ldrsb(7, 11, S_ACT_C)

    # Get symmetryOrder from ROT_MASK_TABLE(pieceId=R4, rot=0)
    a.mov_reg(0, 4); a.mov_imm(1, 0)
    a.bl("get_rot_mask_ptr")
    a.ldrb(9, 0, 10)                    # R9 = symmetryOrder
    a.cmp_imm(9, 1)
    a.b("erot_check_kicks", cond=a.GT)
    # 1-state piece (H8 Hexagon): returns true immediately!
    a.mov_imm(0, 2)
    a.bl("sfx_play")
    a.mov_imm(1, 1)
    a.b("erot_log")

    a.label("erot_check_kicks")
    # nextRot = (rotIndex + dir + count) % count
    a.add_reg(5, 5, 8)
    a.cmp_imm(5, 0)
    a.add_reg(5, 5, 9, cond=a.LT)
    a.cmp_reg(5, 9)
    a.sub_reg(5, 5, 9, cond=a.GE)       # R5 = nextRot

    # Iterate 8 kicks from kick_table
    a.la(9, "kick_table")
    a.mov_imm(10, 0)                    # R10 = kick index 0..7
    a.label("erot_kick_loop")
    a.add_reg(0, 9, 10, shift_imm=1, shift_type=a.LSL)
    a.ldrsb(2, 0, 0)                    # kick dr
    a.ldrsb(3, 0, 1)                    # kick dc
    a.add_reg(2, 6, 2)                  # kr = r + dr
    a.add_reg(3, 7, 3)                  # kc = c + dc
    a.mov_reg(0, 4)                     # pieceId
    a.mov_reg(1, 5)                     # nextRot
    a.bl("can_place_live")
    a.cmp_imm(0, 1)
    a.b("erot_kick_ok", cond=a.EQ)
    a.add_imm(10, 10, 1)
    a.cmp_imm(10, 8)
    a.b("erot_kick_loop", cond=a.LT)

    # Failed all kicks
    a.mov_imm(1, 0)
    a.b("erot_log")

    a.label("erot_kick_ok")
    a.add_reg(0, 9, 10, shift_imm=1, shift_type=a.LSL)
    a.ldrsb(2, 0, 0)
    a.ldrsb(3, 0, 1)
    a.add_reg(6, 6, 2)
    a.add_reg(7, 7, 3)
    a.strb(5, 11, S_ACT_ROT)
    a.strb(6, 11, S_ACT_R)
    a.strb(7, 11, S_ACT_C)
    a.bl("update_ghost_piece")
    a.mov_imm(0, 2)
    a.bl("sfx_play")
    a.mov_imm(1, 1)
    a.b("erot_log")

    a.label("erot_ret_zero")
    a.mov_imm(1, 0)

    a.label("erot_log")
    a.mov_reg(4, 1)
    a.cmp_imm(8, 1)
    a.mov_imm(0, 3, cond=a.EQ)
    a.mov_imm(0, 4, cond=a.NE)
    a.bl("log_engine_call")
    a.mov_reg(0, 4)
    a.pop([4, 5, 6, 7, 8, 9, 10, 15])

    # ==========================================================================
    # Subroutine: check_ternary_perfect()
    # Checks rows 25, 26, 27: if upCount > 0 and downCount == 0, unlocks Ach 8.
    # ==========================================================================
    a.label("check_ternary_perfect")
    a.push([4, 5, 6, 7, 14])
    a.mov_imm(4, 0)                     # upCount
    a.mov_imm(5, 0)                     # downCount
    a.add_imm(6, 11, S_BOARD_MASKS + 25 * 2)
    # Row 25 (r=25 odd -> UP has c odd: 0xAAA, DOWN has c even: 0x555)
    a.ldrh(0, 6, 0)
    a.li32(1, 0xAAA)
    a.tst_reg(0, 1)
    a.add_imm(4, 4, 1, cond=a.NE)
    a.li32(1, 0x555)
    a.tst_reg(0, 1)
    a.add_imm(5, 5, 1, cond=a.NE)

    # Row 26 (r=26 even -> UP has c even: 0x555, DOWN has c odd: 0xAAA)
    a.ldrh(0, 6, 2)
    a.li32(1, 0x555)
    a.tst_reg(0, 1)
    a.add_imm(4, 4, 1, cond=a.NE)
    a.li32(1, 0xAAA)
    a.tst_reg(0, 1)
    a.add_imm(5, 5, 1, cond=a.NE)

    # Row 27 (r=27 odd -> UP has c odd: 0xAAA, DOWN has c even: 0x555)
    a.ldrh(0, 6, 4)
    a.li32(1, 0xAAA)
    a.tst_reg(0, 1)
    a.add_imm(4, 4, 1, cond=a.NE)
    a.li32(1, 0x555)
    a.tst_reg(0, 1)
    a.add_imm(5, 5, 1, cond=a.NE)

    a.cmp_imm(4, 0)
    a.b("ctp_done", cond=a.EQ)
    a.cmp_imm(5, 0)
    a.b("ctp_done", cond=a.NE)
    a.mov_imm(0, 8)                     # Ach 8: Ternary Perfect
    a.bl("unlock_achievement")
    a.label("ctp_done")
    a.pop([4, 5, 6, 7, 15])

    # ==========================================================================
    # Subroutine: resolve_full_rows(R0=pieceId (0 if none), R1=locked_rows_mask) -> R0 = linesCleared
    # ==========================================================================
    a.label("resolve_full_rows")
    a.push([4, 5, 6, 7, 8, 9, 10, 14])
    a.mov_reg(4, 0)                     # R4 = pieceId (0 if pre-clear)
    a.mov_reg(5, 1)                     # R5 = locked_rows_mask

    # Scan rows 0..27 for row_mask == 0xFFF
    a.mov_imm(6, 0)                     # R6 = full_rows_mask (28-bit mask)
    a.mov_imm(7, 0)                     # R7 = count of full rows
    a.add_imm(8, 11, S_BOARD_MASKS)
    a.li32(9, 0xFFF)
    a.mov_imm(2, 0)                     # r = 0..27
    a.label("rfr_scan_loop")
    a.add_reg(0, 8, 2, shift_imm=1, shift_type=a.LSL)
    a.ldrh(1, 0, 0)
    a.cmp_reg(1, 9)
    a.b("rfr_scan_next", cond=a.NE)
    a.mov_imm(3, 1)
    a.mov_reg_rs(3, 3, 2, shift_type=a.LSL)
    a.orr_reg(6, 6, 3)
    a.add_imm(7, 7, 1)
    a.label("rfr_scan_next")
    a.add_imm(2, 2, 1)
    a.cmp_imm(2, 28)
    a.b("rfr_scan_loop", cond=a.LT)

    # Check if count == 0
    a.cmp_imm(7, 0)
    a.b("rfr_has_clears", cond=a.GT)
    # If count == 0 and pieceId != 0: reset comboStreak = 0
    a.cmp_imm(4, 0)
    a.mov_imm(0, 0, cond=a.NE)
    a.str(0, 11, S_COMBO, cond=a.NE)
    a.mov_imm(0, 0)
    a.pop([4, 5, 6, 7, 8, 9, 10, 15])

    a.label("rfr_has_clears")
    # Collapse remaining rows downward from r=27 down to 0
    a.mov_imm(8, 27)                    # R8 = write_r
    a.mov_imm(9, 27)                    # R9 = read_r
    a.label("rfr_collapse_loop")
    a.mov_imm(0, 1)
    a.mov_reg_rs(0, 0, 9, shift_type=a.LSL)
    a.tst_reg(6, 0)                     # is read_r in full_rows_mask?
    a.b("rfr_collapse_skip", cond=a.NE)
    # Not full: if write_r != read_r, copy row read_r to write_r
    a.cmp_reg(8, 9)
    a.b("rfr_collapse_dec_w", cond=a.EQ)
    # Copy S_BOARD_MASKS[read_r] -> S_BOARD_MASKS[write_r]
    a.add_imm(0, 11, S_BOARD_MASKS)
    a.add_reg(1, 0, 9, shift_imm=1, shift_type=a.LSL)
    a.ldrh(2, 1, 0)
    a.add_reg(1, 0, 8, shift_imm=1, shift_type=a.LSL)
    a.strh(2, 1, 0)
    # Copy 12 bytes of S_BOARD_CELLS[read_r*12] -> S_BOARD_CELLS[write_r*12]
    a.mov_imm(3, 12)
    a.mul(1, 9, 3)
    a.mul(2, 8, 3)
    a.add_imm(0, 11, S_BOARD_CELLS)
    a.add_reg(1, 0, 1)
    a.add_reg(2, 0, 2)
    a.ldr(0, 1, 0); a.str(0, 2, 0)
    a.ldr(0, 1, 4); a.str(0, 2, 4)
    a.ldr(0, 1, 8); a.str(0, 2, 8)

    a.label("rfr_collapse_dec_w")
    a.sub_imm(8, 8, 1)
    a.label("rfr_collapse_skip")
    a.sub_imm(9, 9, 1, s=1)
    a.b("rfr_collapse_loop", cond=a.PL)

    # Zero out top rows 0..write_r
    a.label("rfr_zero_top_loop")
    a.cmp_imm(8, 0)
    a.b("rfr_zero_done", cond=a.LT)
    a.add_imm(0, 11, S_BOARD_MASKS)
    a.add_reg(1, 0, 8, shift_imm=1, shift_type=a.LSL)
    a.mov_imm(2, 0)
    a.strh(2, 1, 0)
    a.mov_imm(3, 12)
    a.mul(1, 8, 3)
    a.add_imm(0, 11, S_BOARD_CELLS)
    a.add_reg(1, 0, 1)
    a.str(2, 1, 0); a.str(2, 1, 4); a.str(2, 1, 8)
    a.sub_imm(8, 8, 1)
    a.b("rfr_zero_top_loop")

    a.label("rfr_zero_done")
    # Compute baseScore = computeLineClearBaseScore(count) * level
    # count == 1 -> 100, 2 -> 300, 3 -> 500, >=4 -> 800 + 200*(count-4)
    a.cmp_imm(7, 1)
    a.mov_imm(0, 100, cond=a.EQ)
    a.b("rfr_got_base", cond=a.EQ)
    a.cmp_imm(7, 2)
    a.li32(0, 300, cond=a.EQ)
    a.b("rfr_got_base", cond=a.EQ)
    a.cmp_imm(7, 3)
    a.li32(0, 500, cond=a.EQ)
    a.b("rfr_got_base", cond=a.EQ)
    a.sub_imm(0, 7, 4)
    a.mov_imm(1, 200)
    a.mul(0, 0, 1)
    a.add_imm(0, 0, 800)

    a.label("rfr_got_base")
    a.ldr(1, 11, S_LEVEL)
    a.mul(8, 0, 1)                      # R8 = baseScore

    # Update comboStreak
    a.ldr(9, 11, S_COMBO)
    a.cmp_imm(4, 0)
    a.add_imm(9, 9, 1, cond=a.NE)
    a.b("rfr_combo_set", cond=a.NE)
    a.cmp_imm(9, 1)
    a.mov_imm(9, 1, cond=a.LT)
    a.label("rfr_combo_set")
    a.str(9, 11, S_COMBO)

    # comboIdx = min(4, max(0, comboStreak - 1))
    a.sub_imm(0, 9, 1)
    a.cmp_imm(0, 0)
    a.mov_imm(0, 0, cond=a.LT)
    a.cmp_imm(0, 4)
    a.mov_imm(0, 4, cond=a.GT)
    a.add_imm(10, 0, 2)                 # R10 = 2 + comboIdx (represents 2 * comboMult)

    # Check isDifficult:
    # count >= 3 OR (pieceId != 0 && (mode==1 || mode==2) && pieceId >= 5 && popcount(locked_rows_mask) >= 2)
    a.cmp_imm(7, 3)
    a.mov_imm(2, 1, cond=a.GE)
    a.b("rfr_got_diff", cond=a.GE)

    a.mov_imm(2, 0)
    a.cmp_imm(4, 5)                     # isHexiamond (pieceId >= 5)
    a.b("rfr_got_diff", cond=a.LT)
    a.ldrb(0, 11, S_MODE)
    a.cmp_imm(0, 1)                     # mode >= 1 (CURSED or HEXIAMOND)
    a.b("rfr_got_diff", cond=a.LT)
    # Check locked_rows_mask has >= 2 bits set: (mask & (mask - 1)) != 0
    a.sub_imm(0, 5, 1)
    a.tst_reg(5, 0)
    a.mov_imm(2, 1, cond=a.NE)

    a.label("rfr_got_diff")
    # R2 = isDifficult (0 or 1)
    a.ldrb(3, 11, S_B2B)                # old backToBackActive
    a.strb(2, 11, S_B2B)                # new backToBackActive = isDifficult
    a.and_reg(3, 3, 2)                  # R3 = 1 if (isDifficult && old_b2b) else 0
    a.cmp_imm(3, 1)
    a.mov_imm(3, 3, cond=a.EQ)
    a.mov_imm(3, 2, cond=a.NE)          # R3 = 2 * b2bMult (3 or 2)

    # earnedScore = (baseScore * (2 + comboIdx) * (2 * b2bMult) + 2) >> 2
    a.mul(0, 8, 10)
    a.mul(0, 0, 3)
    a.add_imm(0, 0, 2)
    a.mov_reg(0, 0, shift_imm=2, shift_type=a.LSR)
    a.ldr(1, 11, S_SCORE)
    a.add_reg(1, 1, 0)
    a.str(1, 11, S_SCORE)

    # lines += count
    a.ldr(1, 11, S_LINES)
    a.add_reg(1, 1, 7)
    a.str(1, 11, S_LINES)

    # computedLevel = min(15, 1 + floor(lines / 10))
    # Fast exact division by 10 for lines >= 0: q = (lines * 0xCCCCCCCD) >> 35
    a.li32(2, 0xCCCCCCCD)
    a.umull(0, 3, 1, 2)
    a.mov_reg(3, 3, shift_imm=3, shift_type=a.LSR) # R3 = floor(lines / 10)
    a.add_imm(3, 3, 1)
    a.cmp_imm(3, 15)
    a.mov_imm(3, 15, cond=a.GT)
    a.ldr(0, 11, S_LEVEL)
    a.cmp_reg(3, 0)
    a.str(3, 11, S_LEVEL, cond=a.GT)

    # Achievements on line clear:
    # 0: Triforce (count >= 3)
    a.cmp_imm(7, 3)
    a.b("rfr_ach_sphinx", cond=a.LT)
    a.mov_imm(0, 0)
    a.bl("unlock_achievement")

    a.label("rfr_ach_sphinx")
    # 1: Sphinx Riddle (pieceId == 9 and (full_rows_mask & locked_rows_mask) != 0)
    a.cmp_imm(4, 9)
    a.b("rfr_ach_butterfly", cond=a.NE)
    a.tst_reg(6, 5)
    a.b("rfr_ach_butterfly", cond=a.EQ)
    a.mov_imm(0, 1)
    a.bl("unlock_achievement")

    a.label("rfr_ach_butterfly")
    # 2: Butterfly Effect (pieceId == 16 and (full_rows_mask & locked_rows_mask) != 0)
    a.cmp_imm(4, 16)
    a.b("rfr_ach_geodesic", cond=a.NE)
    a.tst_reg(6, 5)
    a.b("rfr_ach_geodesic", cond=a.EQ)
    a.mov_imm(0, 2)
    a.bl("unlock_achievement")

    a.label("rfr_ach_geodesic")
    # 5: Geodesic (lines >= 100)
    a.ldr(0, 11, S_LINES)
    a.cmp_imm(0, 100)
    a.b("rfr_ach_helix", cond=a.LT)
    a.mov_imm(0, 5)
    a.bl("unlock_achievement")

    a.label("rfr_ach_helix")
    # 7: Helix (comboStreak >= 10)
    a.ldr(0, 11, S_COMBO)
    a.cmp_imm(0, 10)
    a.b("rfr_ach_zerostate", cond=a.LT)
    a.mov_imm(0, 7)
    a.bl("unlock_achievement")

    a.label("rfr_ach_zerostate")
    # 6: Zero State (all 28 row masks == 0)
    a.add_imm(0, 11, S_BOARD_MASKS)
    a.mov_imm(1, 0)
    a.mov_imm(2, 0)
    a.label("rfr_zs_loop")
    a.ldrh(3, 0, 2, p=0)
    a.orr_reg(1, 1, 3)
    a.add_imm(2, 2, 1)
    a.cmp_imm(2, 28)
    a.b("rfr_zs_loop", cond=a.LT)
    a.cmp_imm(1, 0)
    a.b("rfr_ach_mode", cond=a.NE)
    a.mov_imm(0, 6)
    a.bl("unlock_achievement")

    a.label("rfr_ach_mode")
    a.bl("check_mode_level_achievements")
    # Play line clear SFX (sfx_id = 5)
    a.mov_imm(0, 5)
    a.bl("sfx_play")
    a.mov_reg(0, 7)                     # return count
    a.pop([4, 5, 6, 7, 8, 9, 10, 15])

    # ==========================================================================
    # Subroutine: lock_active_piece()
    # Places activePiece onto board, checks Patient, resolves full rows,
    # checks Ternary Perfect, checks buffer overflow (rows 0..3), records
    # Lock Record in Mailbox (0x0203FF00), and spawns next piece if not gameOver.
    # ==========================================================================
    a.label("lock_active_piece")
    a.push([4, 5, 6, 7, 8, 9, 10, 14])
    a.ldrb(4, 11, S_ACT_ID)
    a.cmp_imm(4, 0)
    a.pop([4, 5, 6, 7, 8, 9, 10, 15], cond=a.EQ)

    a.ldrb(5, 11, S_ACT_ROT)
    a.ldrsb(6, 11, S_ACT_R)
    a.ldrsb(7, 11, S_ACT_C)

    # Get ROT_CELL_TABLE ptr for (R4, R5)
    a.mov_reg(0, 4); a.mov_reg(1, 5)
    a.bl("get_rot_cell_ptr")
    a.mov_reg(8, 0)                     # R8 = cell table entry ptr
    a.ldrb(9, 8, 0)                     # R9 = numCells (4 or 6)
    a.mov_imm(10, 0)                    # R10 = locked_rows_mask

    # Allocate 8 bytes on stack to store the 6 packed cell bytes ((r<<4)|c) for the Lock Record
    a.sub_imm(13, 13, 8)
    a.mvn_imm(0, 0)                     # 0xFFFFFFFF
    a.str(0, 13, 0)
    a.str(0, 13, 4)

    a.mov_imm(2, 0)                     # i = 0..numCells-1
    a.label("lap_cell_loop")
    a.cmp_reg(2, 9)
    a.b("lap_cells_done", cond=a.GE)
    a.add_reg(0, 8, 2, shift_imm=1, shift_type=a.LSL)
    a.ldrb(0, 0, 4)                     # dr
    a.add_reg(1, 8, 2, shift_imm=1, shift_type=a.LSL)
    a.ldrb(1, 1, 5)                     # dc
    a.add_reg(0, 6, 0)                  # r = anchorR + dr
    a.add_reg(1, 7, 1)                  # c = anchorC + dc

    # Pack ((r << 4) | (c & 0xF)) into stack[i]
    a.and_imm(3, 1, 0xF)
    a.orr_reg(3, 3, 0, shift_imm=4, shift_type=a.LSL)
    a.strb_reg(3, 13, 2)

    # Check bounds 0 <= r < 28 and 0 <= c < 12
    a.cmp_imm(0, 0)
    a.b("lap_cell_next", cond=a.LT)
    a.cmp_imm(0, 28)
    a.b("lap_cell_next", cond=a.GE)
    a.cmp_imm(1, 0)
    a.b("lap_cell_next", cond=a.LT)
    a.cmp_imm(1, 12)
    a.b("lap_cell_next", cond=a.GE)

    # Set S_BOARD_CELLS[r * 12 + c] = pieceId (R4)
    a.push([2])
    a.mov_imm(2, 12)
    a.mul(3, 0, 2)
    a.add_reg(3, 3, 1)
    a.add_imm(2, 11, S_BOARD_CELLS)
    a.strb_reg(4, 2, 3)

    # Set S_BOARD_MASKS[r] |= (1 << c)
    a.add_imm(2, 11, S_BOARD_MASKS)
    a.add_reg(2, 2, 0, shift_imm=1, shift_type=a.LSL)
    a.ldrh(3, 2, 0)
    a.mov_imm(12, 1)
    a.mov_reg_rs(12, 12, 1, shift_type=a.LSL)
    a.orr_reg(3, 3, 12)
    a.strh(3, 2, 0)

    # Set locked_rows_mask |= (1 << r)
    a.mov_imm(12, 1)
    a.mov_reg_rs(12, 12, 0, shift_type=a.LSL)
    a.orr_reg(10, 10, 12)
    a.pop([2])

    a.label("lap_cell_next")
    a.add_imm(2, 2, 1)
    a.b("lap_cell_loop")

    a.label("lap_cells_done")
    # Mark board dirty for renderer
    a.mov_imm(0, 1)
    a.strb(0, 11, S_BOARD_DIRTY)
    a.strb(0, 11, S_HUD_DIRTY)

    # Patient achievement check: level >= 5 && idle_frames >= 1792
    a.ldr(0, 11, S_LEVEL)
    a.cmp_imm(0, 5)
    a.b("lap_after_patient", cond=a.LT)
    a.ldr(0, 11, S_IDLE_FRAMES)
    a.li32(1, 1792)
    a.cmp_reg(0, 1)
    a.b("lap_after_patient", cond=a.LT)
    a.mov_imm(0, 9)                     # Ach 9: Patient
    a.bl("unlock_achievement")

    a.label("lap_after_patient")
    # Resolve full rows with lockContext = (pieceId=R4, locked_rows_mask=R10)
    a.mov_reg(0, 4)
    a.mov_reg(1, 10)
    a.bl("resolve_full_rows")
    a.mov_reg(8, 0)                     # R8 = linesCleared
    a.strb(8, 11, S_LAST_LOCK_LINES)

    # Check Ternary Perfect
    a.bl("check_ternary_perfect")

    # Check if any buffer row (0..3) still has an occupied cell
    a.add_imm(0, 11, S_BOARD_MASKS)
    a.ldrh(1, 0, 0)
    a.ldrh(2, 0, 2)
    a.orr_reg(1, 1, 2)
    a.ldrh(2, 0, 4)
    a.orr_reg(1, 1, 2)
    a.ldrh(2, 0, 6)
    a.orr_reg(1, 1, 2, s=1)
    a.mov_imm(2, 1, cond=a.NE)
    a.strb(2, 11, S_GAMEOVER, cond=a.NE)

    # Write Lock Record to Mailbox ring buffer (0x0203FF00) if S_SUPPRESS_LOG == 0
    a.ldrb(0, 11, S_SUPPRESS_LOG)
    a.cmp_imm(0, 0)
    a.b("lap_after_lock_log", cond=a.NE)

    a.ldr(0, 11, S_LOCK_TOTAL)
    a.and_imm(1, 0, 15)                 # idx = lock_total & 15
    a.add_imm(0, 0, 1)
    a.str(0, 11, S_LOCK_TOTAL)
    a.li32(2, MB_BASE + 0x300)
    a.add_reg(2, 2, 1, shift_imm=4, shift_type=a.LSL) # entry = 0x0203FF00 + idx * 16

    a.strb(4, 2, 0)                     # +0x00: pieceId
    a.strb(5, 2, 1)                     # +0x01: rotIndex
    a.strb(8, 2, 2)                     # +0x02: linesCleared
    a.ldr(0, 11, S_LEVEL)
    a.strb(0, 2, 3)                     # +0x03: level_after
    # +0x04..+0x09: 6 packed cell bytes from stack
    a.ldr(0, 13, 0)
    a.str(0, 2, 4)
    a.ldrh(0, 13, 4)
    a.strh(0, 2, 8)
    # +0x0A: combo_after, +0x0B: b2b_after | (anchor_r << 1)
    a.ldr(0, 11, S_COMBO)
    a.strb(0, 2, 10)
    a.ldrb(0, 11, S_B2B)
    a.orr_reg(0, 0, 6, shift_imm=1, shift_type=a.LSL)
    a.strb(0, 2, 11)
    # +0x0C: score_after (uint32)
    a.ldr(0, 11, S_SCORE)
    a.str(0, 2, 12)

    a.label("lap_after_lock_log")
    a.add_imm(13, 13, 8)                # pop 8-byte cell buffer

    # If linesCleared == 0, play lock SFX (sfx_id = 3)
    a.cmp_imm(8, 0)
    a.mov_imm(0, 3, cond=a.EQ)
    a.bl("sfx_play", cond=a.EQ)

    # Reset gravity timer to 0 on lock
    a.mov_imm(0, 0)
    a.str(0, 11, S_GRAV_TIMER)

    # If not gameOver, spawn next piece; if gameOver, play gameOver SFX (7) and save high score
    a.ldrb(0, 11, S_GAMEOVER)
    a.cmp_imm(0, 0)
    a.b("lap_gameover", cond=a.NE)
    a.bl("spawn_next_piece")
    a.pop([4, 5, 6, 7, 8, 9, 10, 15])

    a.label("lap_gameover")
    a.mov_imm(0, 7)
    a.bl("sfx_play")
    # If in PLAY screen (not attract mode), record high score to SRAM
    a.ldrb(0, 11, S_SCREEN)
    a.cmp_imm(0, 1)
    a.bl("record_high_score", cond=a.EQ)
    a.pop([4, 5, 6, 7, 8, 9, 10, 15])

    # ==========================================================================
    # Subroutine: eng_soft_drop() -> R0 = 1 if moved, 0 if locked
    # Logs call_code 5 with result.
    # ==========================================================================
    a.label("eng_soft_drop")
    a.push([4, 14])
    a.ldrb(0, 11, S_GAMEOVER)
    a.ldrb(1, 11, S_PAUSED)
    a.orr_reg(0, 0, 1, s=1)
    a.b("esd_ret_zero", cond=a.NE)
    a.ldrb(0, 11, S_ACT_ID)
    a.cmp_imm(0, 0)
    a.b("esd_ret_zero", cond=a.EQ)

    a.mov_imm(0, 0)
    a.str(0, 11, S_IDLE_FRAMES)

    a.bl("step_gravity_down")
    a.cmp_imm(0, 1)
    a.b("esd_locked", cond=a.NE)
    a.mov_imm(0, 1)
    a.bl("sfx_play")
    a.mov_imm(4, 1)
    a.b("esd_log")

    a.label("esd_locked")
    a.bl("lock_active_piece")
    a.mov_imm(4, 0)
    a.b("esd_log")

    a.label("esd_ret_zero")
    a.mov_imm(4, 0)

    a.label("esd_log")
    a.mov_imm(0, 5)
    a.mov_reg(1, 4)
    a.bl("log_engine_call")
    a.mov_reg(0, 4)
    a.pop([4, 15])

    # ==========================================================================
    # Subroutine: eng_hard_drop() -> R0 = dropped steps count
    # Logs call_code 6 with result = dropped.
    # ==========================================================================
    a.label("eng_hard_drop")
    a.push([4, 14])
    a.ldrb(0, 11, S_GAMEOVER)
    a.ldrb(1, 11, S_PAUSED)
    a.orr_reg(0, 0, 1, s=1)
    a.b("ehd_ret_zero", cond=a.NE)
    a.ldrb(0, 11, S_ACT_ID)
    a.cmp_imm(0, 0)
    a.b("ehd_ret_zero", cond=a.EQ)

    a.mov_imm(0, 0)
    a.str(0, 11, S_IDLE_FRAMES)

    a.mov_imm(4, 0)                     # dropped = 0
    a.label("ehd_loop")
    a.bl("step_gravity_down")
    a.cmp_imm(0, 1)
    a.add_imm(4, 4, 1, cond=a.EQ)
    a.b("ehd_loop", cond=a.EQ)

    a.mov_imm(0, 4)                     # hard drop SFX
    a.bl("sfx_play")
    a.bl("lock_active_piece")
    a.b("ehd_log")

    a.label("ehd_ret_zero")
    a.mov_imm(4, 0)

    a.label("ehd_log")
    a.mov_imm(0, 6)
    a.mov_reg(1, 4)
    a.bl("log_engine_call")
    a.mov_reg(0, 4)
    a.pop([4, 15])

    # ==========================================================================
    # Subroutine: eng_tick(R0=inputCmd: 0=null, 1=LEFT, 2=RIGHT, 3=ROT_CW, 4=ROT_CCW, 5=HARD)
    # Matches TrytrisEngine.tick(inputCmd, 0).
    # When R0 == 0, logs call_code 7 (tick(null)) with result (1=stepped, 0=locked).
    # When R0 != 0 (used in Attract mode), suppresses inner call log for move/rotate
    # and logs the exact action or logs move/rotate + tick(null) so replay in
    # TrytrisEngine matches 100%!
    # Wait: let's check how Test 3 and Test 5 replay the call log!
    # In Test 3 (Engine differential):
    #   Player inputs call moveHorizontal(±1), rotate(±1), softDrop, hardDrop, and gravity calls tick(null)!
    # In Attract mode (Test 5):
    #   Porch Toys bot executes `eng.tick(plan.length ? plan.shift() : null)`!
    #   Notice what `eng.tick(cmd)` does in TrytrisEngine when `cmd` is 'LEFT':
    #   It calls `this.moveHorizontal(-1)` AND THEN `if (!this.stepGravityDown()) this.lockActivePiece()`!
    #   Wait: in `TrytrisEngine`, `tick(null)` is just `if (!this.stepGravityDown()) this.lockActivePiece()`!
    #   So `eng.tick('LEFT')` is 100% equivalent to calling `eng.moveHorizontal(-1)` followed by `eng.tick(null)`!
    #   Wait: let's verify that!
    #   In `TrytrisEngine.tick(inputCmd)`:
    #     1. `this.ticks++`
    #     2. `resolveFullRows(null)` (only non-zero if pre-seeded full rows exist, never during normal play)
    #     3. `if (inputCmd === 'LEFT') this.moveHorizontal(-1); ...`
    #     4. `if (!this.stepGravityDown()) this.lockActivePiece();`
    #   Because `eng_move_horizontal` logs `moveHorizontal` and `eng_rotate` logs `rotate`,
    #   if `eng_tick(cmd)` calls `eng_move_horizontal` / `eng_rotate` AND THEN logs `tick(null)` (code 7) when doing the gravity step at the end of `eng_tick`, then replaying the call log in `TrytrisEngine` (calling `moveHorizontal`, `rotate`, `tick(null)`) reproduces the exact state for BOTH live play AND attract mode!
    # ==========================================================================
    a.label("eng_tick")
    a.push([4, 5, 14])
    a.mov_reg(4, 0)                     # R4 = inputCmd (0..5)
    a.ldrb(0, 11, S_GAMEOVER)
    a.ldrb(1, 11, S_PAUSED)
    a.orr_reg(0, 0, 1, s=1)
    a.pop([4, 5, 15], cond=a.NE)

    a.ldr(0, 11, S_TICKS)
    a.add_imm(0, 0, 1)
    a.str(0, 11, S_TICKS)

    # Check pre-seeded full rows
    a.mov_imm(0, 0)
    a.mov_imm(1, 0)
    a.bl("resolve_full_rows")
    a.cmp_imm(0, 0)
    a.pop([4, 5, 15], cond=a.GT)

    # Dispatch optional inputCmd (1=LEFT, 2=RIGHT, 3=ROT_CW, 4=ROT_CCW, 5=HARD)
    a.cmp_imm(4, 0)
    a.b("et_grav", cond=a.EQ)
    a.cmp_imm(4, 1)
    a.b("et_not_left", cond=a.NE)
    a.mvn_imm(0, 0)                     # -1
    a.bl("eng_move_horizontal")
    a.b("et_grav")
    a.label("et_not_left")
    a.cmp_imm(4, 2)
    a.b("et_not_right", cond=a.NE)
    a.mov_imm(0, 1)                     # +1
    a.bl("eng_move_horizontal")
    a.b("et_grav")
    a.label("et_not_right")
    a.cmp_imm(4, 3)
    a.b("et_not_cw", cond=a.NE)
    a.mov_imm(0, 1)                     # +1 CW
    a.bl("eng_rotate")
    a.b("et_grav")
    a.label("et_not_cw")
    a.cmp_imm(4, 4)
    a.b("et_not_ccw", cond=a.NE)
    a.mvn_imm(0, 0)                     # -1 CCW
    a.bl("eng_rotate")
    a.b("et_grav")
    a.label("et_not_ccw")
    a.cmp_imm(4, 5)
    a.b("et_grav", cond=a.NE)
    a.bl("eng_hard_drop")
    a.pop([4, 5, 15])

    a.label("et_grav")
    a.bl("step_gravity_down")
    a.mov_reg(5, 0)                     # R5 = 1 if stepped down, 0 if blocked
    a.cmp_imm(5, 0)
    a.bl("lock_active_piece", cond=a.EQ)
    # Log tick(null) (call_code = 7, result = R5)
    a.mov_imm(0, 7)
    a.mov_reg(1, 5)
    a.bl("log_engine_call")
    a.mov_reg(0, 5)
    a.pop([4, 5, 15])

    # ==========================================================================
    # Subroutine: eng_reset(R0=seed, R1=mode)
    # Resets board, bagGen, score, lines, level, combo, b2b, timers, and spawns first piece.
    # Note: does NOT clear earnedAchievements (session-persistent per reference)
    # and does NOT clear call_total/lock_total unless starting a new game from Title/Gameover.
    # Let's reset call_total and lock_total on eng_reset so each game starts a clean log!
    # ==========================================================================
    a.label("eng_reset")
    a.push([4, 5, 6, 14])
    a.str(0, 11, S_SEED)
    a.str(0, 11, S_PRNG)
    a.strb(1, 11, S_MODE)

    a.mov_imm(2, 0)
    a.str(2, 11, S_SCORE)
    a.str(2, 11, S_LINES)
    a.str(2, 11, S_COMBO)
    a.strb(2, 11, S_B2B)
    a.strb(2, 11, S_GAMEOVER)
    a.strb(2, 11, S_PAUSED)
    a.strb(2, 11, S_BAG_LEN)
    a.strb(2, 11, S_VOCAB_SIG)
    a.strb(2, 11, S_ACT_ID)
    a.str(2, 11, S_TICKS)
    a.str(2, 11, S_IDLE_FRAMES)
    a.str(2, 11, S_GRAV_TIMER)
    a.str(2, 11, S_CALL_TOTAL)
    a.str(2, 11, S_LOCK_TOTAL)
    a.strb(2, 11, S_DAS_DIR)
    a.strb(2, 11, S_DAS_TIMER)
    a.strb(2, 11, S_BOT_PLAN_LEN)
    a.strb(2, 11, S_BOT_PLAN_POS)
    a.strb(2, 11, S_HS_SAVED_FLAG)
    a.strb(2, 11, S_SUPPRESS_LOG)
    a.strb(2, 11, S_PREV_ACT_ID)

    a.mov_imm(3, 1)
    a.str(3, 11, S_LEVEL)
    a.strb(3, 11, S_DIRTY_UI)
    a.strb(3, 11, S_BOARD_DIRTY)
    a.strb(3, 11, S_HUD_DIRTY)

    # Clear S_BOARD_MASKS (56 bytes)
    a.add_imm(4, 11, S_BOARD_MASKS)
    a.mov_imm(5, 14)
    a.label("er_clr_masks")
    a.str(2, 4, 4, p=0)
    a.sub_imm(5, 5, 1, s=1)
    a.b("er_clr_masks", cond=a.NE)

    # Clear S_BOARD_CELLS (336 bytes = 84 words)
    a.add_imm(4, 11, S_BOARD_CELLS)
    a.mov_imm(5, 84)
    a.label("er_clr_cells")
    a.str(2, 4, 4, p=0)
    a.sub_imm(5, 5, 1, s=1)
    a.b("er_clr_cells", cond=a.NE)

    # Clear Mailbox ring buffers (0x0203FE00..0x0203FFFF = 512 bytes = 128 words)
    a.li32(4, MB_BASE + 0x200)
    a.mov_imm(5, 128)
    a.label("er_clr_mb_rings")
    a.str(2, 4, 4, p=0)
    a.sub_imm(5, 5, 1, s=1)
    a.b("er_clr_mb_rings", cond=a.NE)

    a.bl("check_mode_level_achievements")
    a.bl("spawn_next_piece")
    a.pop([4, 5, 6, 15])

    # ==========================================================================
    # [LIFT-4] Porch Toys Greedy Bot (`cloneEng`, `settle`, `score`, `makePlan`)
    # Provenance: porch-toys/index.html (Kehai / ConsciousNode SoftWorks, MIT),
    #             lines 972-993,
    #             sha256 caf49dd69587594ce8ef3dceabbf3c44394ba610c8561476508326ccd1cc4345
    # Intentional changes: Translated from JS to ARM7TDMI operating on a 28-row
    # 12-bit row-mask clone (`S_SIM_MASKS`) with identical candidate ordering
    # (`rot` 0..rots-1, `rd` CW/CCW, `sh` -8..8, `order` 0/1), identical 80-tick
    # `settle` loop, and identical heuristic weights (+1000*lines - 60*holes - 3*agg
    # - 2*rough - 10^9*gameOver). Duplicate action sequences (`rot==0 && (rd==CCW || order==1)`
    # and `sh==0 && order==1`) are skipped since `v > bv` is strict and cannot trigger
    # on a duplicate.
    # ==========================================================================

    # Helper for bot simulation:
    # In bot simulation, let's keep the simulated piece state in:
    #   R5 = pieceId (fixed during candidate)
    #   R6 = sim_rot
    #   R7 = sim_r
    #   R8 = sim_c
    #   R9 = sim_state_flags: bit 0 = gameOver, bit 1 = piece_changed (settled), bits 8..15 = cleared_lines
    #   R10 = symmetryOrder (rots)

    # Helper: cpm_with_ptr(R0=mask_ptr, R2=anchorR, R3=anchorC, R4=row_masks_base) -> R0=1/0
    # Assumes (anchorR + anchorC) parity is already even and anchorR >= 0!
    a.label("cpm_with_ptr")
    a.ldrb(1, 0, 13)                    # min_dc
    a.add_reg(1, 3, 1)
    a.cmp_imm(1, 0)
    a.mov_imm(0, 0, cond=a.LT)
    a.bx(14, cond=a.LT)
    a.ldrb(1, 0, 8)                     # max_dr
    a.add_reg(1, 2, 1)
    a.cmp_imm(1, 28)
    a.mov_imm(0, 0, cond=a.GE)
    a.bx(14, cond=a.GE)
    a.ldrb(1, 0, 9)                     # max_dc
    a.add_reg(1, 3, 1)
    a.cmp_imm(1, 12)
    a.mov_imm(0, 0, cond=a.GE)
    a.bx(14, cond=a.GE)
    a.add_reg(12, 4, 2, shift_imm=1, shift_type=a.LSL)
    a.cmp_imm(3, 0)
    a.b("cpmp_neg_c", cond=a.LT)
    a.ldrh(1, 0, 0); a.ldrh(2, 12, 0); a.mov_reg_rs(1, 1, 3, shift_type=a.LSL); a.tst_reg(2, 1); a.mov_imm(0, 0, cond=a.NE); a.bx(14, cond=a.NE)
    a.ldrh(1, 0, 2); a.ldrh(2, 12, 2); a.mov_reg_rs(1, 1, 3, shift_type=a.LSL); a.tst_reg(2, 1); a.mov_imm(0, 0, cond=a.NE); a.bx(14, cond=a.NE)
    a.ldrh(1, 0, 4); a.ldrh(2, 12, 4); a.mov_reg_rs(1, 1, 3, shift_type=a.LSL); a.tst_reg(2, 1); a.mov_imm(0, 0, cond=a.NE); a.bx(14, cond=a.NE)
    a.ldrh(1, 0, 6); a.ldrh(2, 12, 6); a.mov_reg_rs(1, 1, 3, shift_type=a.LSL); a.tst_reg(2, 1); a.mov_imm(0, 0, cond=a.NE); a.bx(14, cond=a.NE)
    a.mov_imm(0, 1)
    a.bx(14)
    a.label("cpmp_neg_c")
    a.ldrh(1, 0, 0); a.ldrh(2, 12, 0); a.tst_reg(2, 1, shift_imm=1, shift_type=a.LSR); a.mov_imm(0, 0, cond=a.NE); a.bx(14, cond=a.NE)
    a.ldrh(1, 0, 2); a.ldrh(2, 12, 2); a.tst_reg(2, 1, shift_imm=1, shift_type=a.LSR); a.mov_imm(0, 0, cond=a.NE); a.bx(14, cond=a.NE)
    a.ldrh(1, 0, 4); a.ldrh(2, 12, 4); a.tst_reg(2, 1, shift_imm=1, shift_type=a.LSR); a.mov_imm(0, 0, cond=a.NE); a.bx(14, cond=a.NE)
    a.ldrh(1, 0, 6); a.ldrh(2, 12, 6); a.tst_reg(2, 1, shift_imm=1, shift_type=a.LSR); a.mov_imm(0, 0, cond=a.NE); a.bx(14, cond=a.NE)
    a.mov_imm(0, 1)
    a.bx(14)

    # Subroutine: bot_sim_step_down() -> R0 = 1 if moved down, 0 if blocked
    # Uses R5=pieceId, R6=sim_rot, R7=sim_r, R8=sim_c
    a.label("bot_sim_step_down")
    a.push([4, 5, 14])
    a.tst_imm(9, 4)
    a.add_imm(4, 11, S_BOARD_MASKS, cond=a.EQ)
    a.add_imm(4, 11, S_SIM_MASKS,   cond=a.NE)
    # Lookup mask_ptr once into R5
    a.mov_reg(0, 5); a.mov_reg(1, 6)
    a.bl("get_rot_mask_ptr")
    a.mov_reg(5, 0)                     # R5 = mask_ptr

    # 1. Try (r + 1, c + zigDir)
    a.tst_imm(7, 1)
    a.add_imm(3, 8, 1, cond=a.EQ)
    a.sub_imm(3, 8, 1, cond=a.NE)
    a.add_imm(2, 7, 1)
    a.mov_reg(0, 5)
    a.bl("cpm_with_ptr")
    a.cmp_imm(0, 1)
    a.add_imm(7, 7, 1, cond=a.EQ)
    a.mov_reg(8, 3, cond=a.EQ)
    a.pop([4, 5, 15], cond=a.EQ)

    # 2. Try (r + 1, c - zigDir)
    a.tst_imm(7, 1)
    a.sub_imm(3, 8, 1, cond=a.EQ)
    a.add_imm(3, 8, 1, cond=a.NE)
    a.add_imm(2, 7, 1)
    a.mov_reg(0, 5)
    a.bl("cpm_with_ptr")
    a.cmp_imm(0, 1)
    a.add_imm(7, 7, 1, cond=a.EQ)
    a.mov_reg(8, 3, cond=a.EQ)
    a.pop([4, 5, 15], cond=a.EQ)

    # 3. Try (r + 2, c)
    a.add_imm(2, 7, 2)
    a.mov_reg(3, 8)
    a.mov_reg(0, 5)
    a.bl("cpm_with_ptr")
    a.cmp_imm(0, 1)
    a.add_imm(7, 7, 2, cond=a.EQ)
    a.pop([4, 5, 15])

    # Subroutine: bot_sim_lock()
    # Locks (R5, R6, R7, R8) into S_SIM_MASKS, resolves full rows, checks buffer/spawn gameOver,
    # sets bit 1 of R9 (piece_changed), and resets (R6=0, R7=1, R8=3).
    a.label("bot_sim_lock")
    a.push([4, 14])
    a.tst_imm(9, 4)
    a.b("bsl_already_copied", cond=a.NE)
    a.orr_imm(9, 9, 4)
    a.add_imm(0, 11, S_BOARD_MASKS)
    a.add_imm(1, 11, S_SIM_MASKS)
    a.mov_imm(2, 14)
    a.label("bsl_lazy_copy")
    a.ldr(3, 0, 4, p=0)
    a.str(3, 1, 4, p=0)
    a.sub_imm(2, 2, 1, s=1)
    a.b("bsl_lazy_copy", cond=a.NE)
    a.label("bsl_already_copied")
    a.mov_reg(0, 5); a.mov_reg(1, 6)
    a.bl("get_rot_mask_ptr")            # R0 = mask entry ptr
    a.ldrb(1, 0, 8)                     # R1 = max_dr
    a.add_imm(4, 11, S_SIM_MASKS)
    a.add_reg(4, 4, 7, shift_imm=1, shift_type=a.LSL) # &sim_masks[sim_r]
    a.mov_imm(2, 0)                     # dr = 0..max_dr
    a.label("bsl_or_loop")
    a.ldrh(3, 0, 2, p=0)                # piece_mask[dr]
    a.cmp_imm(8, 0)
    a.mov_reg_rs(3, 3, 8, shift_type=a.LSL, cond=a.GE)
    a.mov_reg(3, 3, shift_imm=1, shift_type=a.LSR, cond=a.LT)
    a.ldrh(12, 4, 0)
    a.orr_reg(12, 12, 3)
    a.strh(12, 4, 2, p=0)
    a.add_imm(2, 2, 1)
    a.cmp_reg(2, 1)
    a.b("bsl_or_loop", cond=a.LE)

    # Resolve full rows in S_SIM_MASKS
    a.add_imm(4, 11, S_SIM_MASKS)
    a.mov_imm(0, 27)                    # write_r
    a.mov_imm(1, 27)                    # read_r
    a.mov_imm(2, 0)                     # cleared count
    a.li32(3, 0xFFF)
    a.label("bsl_rfr_loop")
    a.add_reg(12, 4, 1, shift_imm=1, shift_type=a.LSL)
    a.ldrh(12, 12, 0)
    a.cmp_reg(12, 3)
    a.add_imm(2, 2, 1, cond=a.EQ)
    a.b("bsl_rfr_next", cond=a.EQ)
    a.add_reg(14, 4, 0, shift_imm=1, shift_type=a.LSL)
    a.strh(12, 14, 0)
    a.sub_imm(0, 0, 1)
    a.label("bsl_rfr_next")
    a.sub_imm(1, 1, 1, s=1)
    a.b("bsl_rfr_loop", cond=a.PL)

    a.mov_imm(12, 0)
    a.label("bsl_zero_loop")
    a.cmp_imm(0, 0)
    a.b("bsl_zero_done", cond=a.LT)
    a.add_reg(14, 4, 0, shift_imm=1, shift_type=a.LSL)
    a.strh(12, 14, 0)
    a.sub_imm(0, 0, 1)
    a.b("bsl_zero_loop")

    a.label("bsl_zero_done")
    # Add cleared count (R2) to R9 bits 8..15
    a.add_reg(9, 9, 2, shift_imm=8, shift_type=a.LSL)
    # Mark piece_changed (bit 1 of R9)
    a.orr_imm(9, 9, 2)

    # Check buffer overflow (rows 0..3)
    a.ldrh(0, 4, 0)
    a.ldrh(1, 4, 2)
    a.orr_reg(0, 0, 1)
    a.ldrh(1, 4, 4)
    a.orr_reg(0, 0, 1)
    a.ldrh(1, 4, 6)
    a.orr_reg(0, 0, 1, s=1)
    a.orr_imm(9, 9, 1, cond=a.NE)       # gameOver = 1
    a.pop([4, 15], cond=a.NE)

    # Spawn next mock piece at rot=0, r=1, c=3
    a.mov_imm(6, 0)
    a.mov_imm(7, 1)
    a.mov_imm(8, 3)
    a.mov_reg(0, 5); a.mov_imm(1, 0); a.mov_imm(2, 1); a.mov_imm(3, 3)
    a.bl("can_place_masks")
    a.cmp_imm(0, 0)
    a.orr_imm(9, 9, 1, cond=a.EQ)       # gameOver = 1 if blocked
    a.pop([4, 15])

    # Subroutine: bot_sim_tick(R0=act: 0=null, 1=LEFT, 2=RIGHT, 3=ROT_CW, 4=ROT_CCW)
    a.label("bot_sim_tick")
    a.tst_imm(9, 1)                     # if gameOver, return
    a.bx(14, cond=a.NE)
    a.push([4, 14])
    a.tst_imm(9, 4)
    a.add_imm(4, 11, S_BOARD_MASKS, cond=a.EQ)
    a.add_imm(4, 11, S_SIM_MASKS,   cond=a.NE)
    a.cmp_imm(0, 0)
    a.b("bst_grav", cond=a.EQ)

    a.cmp_imm(0, 2)
    a.b("bst_rot", cond=a.GT)
    # Move horizontal: 1=LEFT (dir=-1), 2=RIGHT (dir=+1)
    a.cmp_imm(0, 1)
    a.mvn_imm(12, 0, cond=a.EQ)
    a.mov_imm(12, 1, cond=a.NE)         # R12 = dir
    a.push([12])
    a.mov_reg(0, 5); a.mov_reg(1, 6); a.mov_reg(2, 7)
    a.add_reg(3, 8, 12, shift_imm=1, shift_type=a.LSL)
    a.bl("can_place_masks")
    a.pop([12])
    a.cmp_imm(0, 1)
    a.add_reg(8, 8, 12, shift_imm=1, shift_type=a.LSL, cond=a.EQ)
    a.b("bst_grav", cond=a.EQ)

    a.push([12])
    a.mov_reg(0, 5); a.mov_reg(1, 6)
    a.add_imm(2, 7, 1)
    a.add_reg(3, 8, 12)
    a.bl("can_place_masks")
    a.pop([12])
    a.cmp_imm(0, 1)
    a.add_imm(7, 7, 1, cond=a.EQ)
    a.add_reg(8, 8, 12, cond=a.EQ)
    a.b("bst_grav")

    a.label("bst_rot")
    # Rotate: 3=ROT_CW (+1), 4=ROT_CCW (-1)
    a.cmp_imm(10, 1)                    # if rots <= 1, no-op
    a.b("bst_grav", cond=a.LE)
    a.cmp_imm(0, 3)
    a.mov_imm(12, 1, cond=a.EQ)
    a.mvn_imm(12, 0, cond=a.NE)         # dir = +1 or -1
    a.add_reg(12, 6, 12)
    a.cmp_imm(12, 0)
    a.add_reg(12, 12, 10, cond=a.LT)
    a.cmp_reg(12, 10)
    a.sub_reg(12, 12, 10, cond=a.GE)    # R12 = nextRot

    # Try 8 kicks
    a.push([5, 6])
    a.mov_reg(6, 12)                    # R6 = nextRot
    a.la(5, "kick_table")
    a.mov_imm(12, 0)                    # kick index 0..7
    a.label("bst_kick_loop")
    a.push([12])
    a.add_reg(0, 5, 12, shift_imm=1, shift_type=a.LSL)
    a.ldrsb(2, 0, 0)
    a.ldrsb(3, 0, 1)
    a.add_reg(2, 7, 2)
    a.add_reg(3, 8, 3)
    a.ldr(0, 13, 4)                     # pieceId (saved R5 on stack at [SP+4])
    a.mov_reg(1, 6)                     # nextRot
    a.bl("can_place_masks")
    a.pop([12])
    a.cmp_imm(0, 1)
    a.b("bst_kick_ok", cond=a.EQ)
    a.add_imm(12, 12, 1)
    a.cmp_imm(12, 8)
    a.b("bst_kick_loop", cond=a.LT)
    # Kick failed: restore R5, R6
    a.pop([5, 6])
    a.b("bst_grav")

    a.label("bst_kick_ok")
    a.add_reg(0, 5, 12, shift_imm=1, shift_type=a.LSL)
    a.ldrsb(2, 0, 0)
    a.ldrsb(3, 0, 1)
    a.add_reg(7, 7, 2)
    a.add_reg(8, 8, 3)
    a.pop([5, 12])                      # restore R5=pieceId, discard old R6 into R12 (keep new R6=nextRot)

    a.label("bst_grav")
    a.bl("bot_sim_step_down")
    a.cmp_imm(0, 0)
    a.bl("bot_sim_lock", cond=a.EQ)
    a.pop([4, 15])

    # ==========================================================================
    # Subroutine: bot_score_sim() -> R0 = heuristic score (int32)
    # Computes: (cleared * 1000) - (holes * 60) - (agg * 3) - (rough * 2) - (gameOver ? 1000000000 : 0)
    # Uses S_SIM_MASKS and R9 (bit 0 = gameOver, bits 8..15 = cleared).
    # ==========================================================================
    a.label("bot_score_sim")
    a.push([4, 5, 6, 7, 8, 10, 14])
    a.add_imm(4, 11, S_SIM_MASKS)
    a.mov_imm(5, 0)                     # holes = 0
    a.mov_imm(6, 0)                     # agg = 0
    a.mov_imm(7, 0)                     # rough = 0
    a.mvn_imm(8, 0)                     # prev_h = -1

    a.mov_imm(0, 0)                     # col = 0..11
    a.label("bss_col_loop")
    a.mov_imm(1, 1)
    a.mov_reg_rs(1, 1, 0, shift_type=a.LSL) # bit = 1 << col
    a.mov_imm(2, 0)                     # seen = 0
    a.mov_imm(3, 28)                    # h = 28
    a.mov_imm(10, 0)                    # r = 0..27
    a.label("bss_row_loop")
    a.add_reg(12, 4, 10, shift_imm=1, shift_type=a.LSL)
    a.ldrh(12, 12, 0)
    a.tst_reg(12, 1)
    a.b("bss_cell_empty", cond=a.EQ)
    # Occupied cell: if (!seen) { h = r; seen = 1; }
    a.cmp_imm(2, 0)
    a.mov_reg(3, 10, cond=a.EQ)
    a.mov_imm(2, 1, cond=a.EQ)
    a.b("bss_row_next")
    a.label("bss_cell_empty")
    # Empty cell: if (seen) holes++
    a.cmp_imm(2, 1)
    a.add_imm(5, 5, 1, cond=a.EQ)
    a.label("bss_row_next")
    a.add_imm(10, 10, 1)
    a.cmp_imm(10, 28)
    a.b("bss_row_loop", cond=a.LT)

    # agg += 28 - h
    a.rsb_imm(12, 3, 28)
    a.add_reg(6, 6, 12)
    # if (prev_h >= 0) rough += abs(h - prev_h)
    a.cmp_imm(8, 0)
    a.b("bss_set_prev", cond=a.LT)
    a.sub_reg(12, 3, 8, s=1)
    a.rsb_imm(12, 12, 0, cond=a.LT)
    a.add_reg(7, 7, 12)
    a.label("bss_set_prev")
    a.mov_reg(8, 3)

    a.add_imm(0, 0, 1)
    a.cmp_imm(0, 12)
    a.b("bss_col_loop", cond=a.LT)

    # Compute total score:
    # cleared = (R9 >> 8) & 0xFF
    a.mov_reg(0, 9, shift_imm=8, shift_type=a.LSR)
    a.and_imm(0, 0, 0xFF)
    a.li32(1, 1000)
    a.mul(0, 0, 1)                      # R0 = cleared * 1000
    a.mov_imm(1, 60)
    a.mul(2, 5, 1)
    a.sub_reg(0, 0, 2)                  # - holes * 60
    a.add_reg(2, 6, 6, shift_imm=1, shift_type=a.LSL) # agg * 3
    a.sub_reg(0, 0, 2)
    a.sub_reg(0, 0, 7, shift_imm=1, shift_type=a.LSL) # - rough * 2
    a.tst_imm(9, 1)                     # gameOver?
    a.li32(1, 1000000000, cond=a.NE)
    a.sub_reg(0, 0, 1, cond=a.NE)
    a.pop([4, 5, 6, 7, 8, 10, 15])

    # ==========================================================================
    # Subroutine: bot_make_plan()
    # Runs Porch Toys makePlan on current live engine state and writes winning
    # action sequence to S_BOT_PLAN_BUF (with length in S_BOT_PLAN_LEN and S_BOT_PLAN_POS = 0).
    # Stack frame layout (32 bytes):
    #   [SP + 0]:  rot (0..rots-1)
    #   [SP + 4]:  rd_idx (0 -> ROT_CW=3, 1 -> ROT_CCW=4)
    #   [SP + 8]:  sh (-8..+8)
    #   [SP + 12]: order (0 or 1)
    #   [SP + 16]: bv (best score, initialized to -2000000000)
    #   [SP + 20]: best_rot
    #   [SP + 24]: best_rd_code (3 or 4)
    #   [SP + 28]: best_sh | (best_order << 16)
    # ==========================================================================
    a.label("bot_make_plan")
    a.push([4, 5, 6, 7, 8, 9, 10, 14])
    a.sub_imm(13, 13, 48)

    a.ldrb(5, 11, S_ACT_ID)
    a.mov_reg(0, 5); a.mov_imm(1, 0)
    a.bl("get_rot_mask_ptr")
    a.ldrb(10, 0, 10)                   # R10 = rots (symmetryOrder)

    # Clear S_SEEN_LANDING bitmap (168 words)
    a.add_imm(0, 11, S_SEEN_LANDING)
    a.mov_imm(1, 0)
    a.mov_imm(2, 168)
    a.label("bmp_clr_seen")
    a.str(1, 0, 4, p=0)
    a.sub_imm(2, 2, 1, s=1)
    a.b("bmp_clr_seen", cond=a.NE)

    a.li32(0, -2000000000)
    a.str(0, 13, 16)                    # bv = -2000000000
    a.mov_imm(0, 0)
    a.str(0, 13, 20)
    a.str(0, 13, 24)
    a.str(0, 13, 28)

    a.mov_imm(0, 0)
    a.str(0, 13, 0)                     # rot = 0
    a.label("bmp_rot_loop")
    a.ldr(0, 13, 0)
    a.cmp_reg(0, 10)
    a.b("bmp_loops_done", cond=a.GE)

    a.mov_imm(0, 0)
    a.str(0, 13, 4)                     # rd_idx = 0 (0 -> CW=3, 1 -> CCW=4)
    a.label("bmp_rd_loop")
    a.ldr(0, 13, 4)
    a.cmp_imm(0, 2)
    a.b("bmp_next_rot", cond=a.GE)

    a.mvn_imm(0, 7)                     # sh = -8
    a.str(0, 13, 8)
    a.label("bmp_sh_loop")
    a.ldr(0, 13, 8)
    a.cmp_imm(0, 8)
    a.b("bmp_next_rd", cond=a.GT)

    a.mov_imm(0, 0)
    a.str(0, 13, 12)                    # order = 0
    a.label("bmp_ord_loop")
    a.ldr(0, 13, 12)
    a.cmp_imm(0, 2)
    a.b("bmp_next_sh", cond=a.GE)

    # Skip exact duplicate action sequences (where acts is identical to an earlier iteration):
    # 1. if rot == 0 and (rd_idx == 1 or order == 1): skip
    a.ldr(0, 13, 0)                     # rot
    a.cmp_imm(0, 0)
    a.b("bmp_chk_dup2", cond=a.NE)
    a.ldr(1, 13, 4)                     # rd_idx
    a.ldr(2, 13, 12)                    # order
    a.orr_reg(1, 1, 2, s=1)
    a.b("bmp_next_ord", cond=a.NE)

    a.label("bmp_chk_dup2")
    # 2. if sh == 0 and order == 1: skip
    a.ldr(0, 13, 8)                     # sh
    a.cmp_imm(0, 0)
    a.b("bmp_run_cand", cond=a.NE)
    a.ldr(1, 13, 12)                    # order
    a.cmp_imm(1, 1)
    a.b("bmp_next_ord", cond=a.EQ)

    a.label("bmp_run_cand")

    # Initialize sim piece state from live engine
    a.ldrb(5, 11, S_ACT_ID)
    a.ldrb(6, 11, S_ACT_ROT)
    a.ldrsb(7, 11, S_ACT_R)
    a.ldrsb(8, 11, S_ACT_C)
    a.mov_imm(9, 0)                     # sim_state_flags = 0

    # Determine rd_code (3 for rd_idx==0, 4 for rd_idx==1) and m_code (1 for sh<0, 2 for sh>0), m_cnt = abs(sh)
    a.ldr(0, 13, 12)                    # order
    a.cmp_imm(0, 0)
    a.b("bmp_ord1_exec", cond=a.NE)

    # order == 0: R then M
    a.ldr(4, 13, 0)                     # rot count
    a.label("bmp_o0_r_loop")
    a.cmp_imm(4, 0)
    a.b("bmp_o0_m_start", cond=a.LE)
    a.ldr(0, 13, 4)                     # rd_idx
    a.add_imm(0, 0, 3)                  # 3=ROT_CW, 4=ROT_CCW
    a.bl("bot_sim_tick")
    a.sub_imm(4, 4, 1)
    a.b("bmp_o0_r_loop")

    a.label("bmp_o0_m_start")
    a.ldr(4, 13, 8)                     # sh
    a.cmp_imm(4, 0)
    a.rsb_imm(4, 4, 0, cond=a.LT)       # abs(sh)
    a.label("bmp_o0_m_loop")
    a.cmp_imm(4, 0)
    a.b("bmp_settle", cond=a.LE)
    a.ldr(0, 13, 8)
    a.cmp_imm(0, 0)
    a.mov_imm(0, 1, cond=a.LT)          # 1=LEFT
    a.mov_imm(0, 2, cond=a.GT)          # 2=RIGHT
    a.bl("bot_sim_tick")
    a.sub_imm(4, 4, 1)
    a.b("bmp_o0_m_loop")

    a.label("bmp_ord1_exec")
    # order == 1: M then R
    a.ldr(4, 13, 8)                     # sh
    a.cmp_imm(4, 0)
    a.rsb_imm(4, 4, 0, cond=a.LT)       # abs(sh)
    a.label("bmp_o1_m_loop")
    a.cmp_imm(4, 0)
    a.b("bmp_o1_r_start", cond=a.LE)
    a.ldr(0, 13, 8)
    a.cmp_imm(0, 0)
    a.mov_imm(0, 1, cond=a.LT)
    a.mov_imm(0, 2, cond=a.GT)
    a.bl("bot_sim_tick")
    a.sub_imm(4, 4, 1)
    a.b("bmp_o1_m_loop")

    a.label("bmp_o1_r_start")
    a.ldr(4, 13, 0)                     # rot count
    a.label("bmp_o1_r_loop")
    a.cmp_imm(4, 0)
    a.b("bmp_settle", cond=a.LE)
    a.ldr(0, 13, 4)
    a.add_imm(0, 0, 3)
    a.bl("bot_sim_tick")
    a.sub_imm(4, 4, 1)
    a.b("bmp_o1_r_loop")

    a.label("bmp_settle")
    a.bic_imm(9, 9, 2)
    a.tst_imm(9, 1)
    a.b("bmp_score_cand", cond=a.NE)

    # Pre-settle bitmap deduplication when (R9 & 4) == 0 (no lock occurred during acts)
    a.tst_imm(9, 4)
    a.b("bmp_do_settle", cond=a.NE)
    # idx = R6 * 28 + R7
    a.mov_imm(0, 28)
    a.mul(0, 6, 0)
    a.add_reg(0, 0, 7)
    a.add_imm(1, 11, S_SEEN_LANDING)
    a.ldr_reg(2, 1, 0, shift_imm=2, shift_type=a.LSL)
    a.add_imm(12, 8, 1)
    a.mov_imm(3, 1)
    a.mov_reg_rs(3, 3, 12, shift_type=a.LSL) # bit (1 << (sim_c + 1))
    a.tst_reg(2, 3)
    a.b("bmp_next_ord", cond=a.NE)          # Already evaluated this exact pre-settle state!
    a.orr_reg(2, 2, 3)
    a.str_reg(2, 1, 0, shift_imm=2, shift_type=a.LSL)

    a.label("bmp_do_settle")
    a.push([5])
    a.tst_imm(9, 4)
    a.add_imm(4, 11, S_BOARD_MASKS, cond=a.EQ)
    a.add_imm(4, 11, S_SIM_MASKS,   cond=a.NE)
    a.mov_reg(0, 5); a.mov_reg(1, 6)
    a.bl("get_rot_mask_ptr")
    a.mov_reg(5, 0)                     # R5 = mask_ptr for settle loop
    a.label("bmp_settle_loop")
    # 1. Try (r + 1, c + zigDir)
    a.tst_imm(7, 1)
    a.add_imm(3, 8, 1, cond=a.EQ)
    a.sub_imm(3, 8, 1, cond=a.NE)
    a.add_imm(2, 7, 1)
    a.mov_reg(0, 5)
    a.bl("cpm_with_ptr")
    a.cmp_imm(0, 1)
    a.add_imm(7, 7, 1, cond=a.EQ)
    a.mov_reg(8, 3, cond=a.EQ)
    a.b("bmp_settle_loop", cond=a.EQ)
    # 2. Try (r + 1, c - zigDir)
    a.tst_imm(7, 1)
    a.sub_imm(3, 8, 1, cond=a.EQ)
    a.add_imm(3, 8, 1, cond=a.NE)
    a.add_imm(2, 7, 1)
    a.mov_reg(0, 5)
    a.bl("cpm_with_ptr")
    a.cmp_imm(0, 1)
    a.add_imm(7, 7, 1, cond=a.EQ)
    a.mov_reg(8, 3, cond=a.EQ)
    a.b("bmp_settle_loop", cond=a.EQ)
    # 3. Try (r + 2, c)
    a.add_imm(2, 7, 2)
    a.mov_reg(3, 8)
    a.mov_reg(0, 5)
    a.bl("cpm_with_ptr")
    a.cmp_imm(0, 1)
    a.add_imm(7, 7, 2, cond=a.EQ)
    a.b("bmp_settle_loop", cond=a.EQ)
    a.pop([5])

    # Post-settle bitmap deduplication when (R9 & 4) == 0
    a.tst_imm(9, 4)
    a.b("bmp_do_final_lock", cond=a.NE)
    a.mov_imm(0, 28)
    a.mul(0, 6, 0)
    a.add_reg(0, 0, 7)
    a.add_imm(1, 11, S_SEEN_LANDING)
    a.ldr_reg(2, 1, 0, shift_imm=2, shift_type=a.LSL)
    a.add_imm(12, 8, 1)
    a.li32(3, 0x10000)
    a.mov_reg_rs(3, 3, 12, shift_type=a.LSL) # bit (1 << (16 + sim_c + 1))
    a.tst_reg(2, 3)
    a.b("bmp_next_ord", cond=a.NE)          # Already evaluated this exact landing position!
    a.orr_reg(2, 2, 3)
    a.str_reg(2, 1, 0, shift_imm=2, shift_type=a.LSL)

    a.label("bmp_do_final_lock")
    a.bl("bot_sim_lock")

    a.label("bmp_score_cand")
    a.bl("bot_score_sim")               # R0 = v
    a.ldr(1, 13, 16)                    # R1 = bv
    a.cmp_reg(0, 1)
    a.b("bmp_next_ord", cond=a.LE)
    # New best!
    a.str(0, 13, 16)                    # bv = v
    a.ldr(1, 13, 0);  a.str(1, 13, 20)  # best_rot
    a.ldr(1, 13, 4);  a.str(1, 13, 24)  # best_rd_idx
    a.ldr(1, 13, 8);  a.strh(1, 13, 28) # best_sh (signed 16-bit at [SP+28])
    a.ldr(1, 13, 12); a.strh(1, 13, 30) # best_order (at [SP+30])

    a.label("bmp_next_ord")
    a.ldr(0, 13, 12)
    a.add_imm(0, 0, 1)
    a.str(0, 13, 12)
    a.b("bmp_ord_loop")

    a.label("bmp_next_sh")
    a.ldr(0, 13, 8)
    a.add_imm(0, 0, 1)
    a.str(0, 13, 8)
    a.b("bmp_sh_loop")

    a.label("bmp_next_rd")
    a.ldr(0, 13, 4)
    a.add_imm(0, 0, 1)
    a.str(0, 13, 4)
    a.b("bmp_rd_loop")

    a.label("bmp_next_rot")
    a.ldr(0, 13, 0)
    a.add_imm(0, 0, 1)
    a.str(0, 13, 0)
    a.b("bmp_rot_loop")

    a.label("bmp_loops_done")
    # Materialize best plan into S_BOT_PLAN_BUF
    a.ldr(0, 13, 20)                    # best_rot
    a.ldr(1, 13, 24)                    # best_rd_idx
    a.add_imm(1, 1, 3)                  # rd_code (3=ROT_CW, 4=ROT_CCW)
    a.ldrsh(2, 13, 28)                  # best_sh (-8..+8)
    a.ldrh(3, 13, 30)                   # best_order (0 or 1)

    a.cmp_imm(2, 0)
    a.mov_imm(4, 1, cond=a.LT)          # m_code = 1 (LEFT)
    a.mov_imm(4, 2, cond=a.GT)          # m_code = 2 (RIGHT)
    a.rsb_imm(2, 2, 0, cond=a.LT)       # m_cnt = abs(best_sh)

    a.add_imm(5, 11, S_BOT_PLAN_BUF)
    a.mov_imm(6, 0)                     # len = 0

    a.cmp_imm(3, 0)
    a.b("bmp_mat_ord1", cond=a.NE)
    # order 0: R then M
    a.label("bmp_mat_o0_r")
    a.cmp_imm(0, 0)
    a.b("bmp_mat_o0_m", cond=a.LE)
    a.strb_reg(1, 5, 6)
    a.add_imm(6, 6, 1)
    a.sub_imm(0, 0, 1)
    a.b("bmp_mat_o0_r")
    a.label("bmp_mat_o0_m")
    a.cmp_imm(2, 0)
    a.b("bmp_mat_done", cond=a.LE)
    a.strb_reg(4, 5, 6)
    a.add_imm(6, 6, 1)
    a.sub_imm(2, 2, 1)
    a.b("bmp_mat_o0_m")

    a.label("bmp_mat_ord1")
    # order 1: M then R
    a.label("bmp_mat_o1_m")
    a.cmp_imm(2, 0)
    a.b("bmp_mat_o1_r", cond=a.LE)
    a.strb_reg(4, 5, 6)
    a.add_imm(6, 6, 1)
    a.sub_imm(2, 2, 1)
    a.b("bmp_mat_o1_m")
    a.label("bmp_mat_o1_r")
    a.cmp_imm(0, 0)
    a.b("bmp_mat_done", cond=a.LE)
    a.strb_reg(1, 5, 6)
    a.add_imm(6, 6, 1)
    a.sub_imm(0, 0, 1)
    a.b("bmp_mat_o1_r")

    a.label("bmp_mat_done")
    a.strb(6, 11, S_BOT_PLAN_LEN)
    a.mov_imm(0, 0)
    a.strb(0, 11, S_BOT_PLAN_POS)

    a.add_imm(13, 13, 48)
    a.pop([4, 5, 6, 7, 8, 9, 10, 15])

    # ==========================================================================
    # Subroutine: write_mailbox()
    # Populates EWRAM 0x0203FC00..0x0203FDFF from live game state every frame.
    # (Ring buffers at 0x0203FE00..0x0203FFFF are updated live on calls/locks.)
    # ==========================================================================
    a.label("write_mailbox")
    a.push([4, 5, 6, 7, 8, 9, 10, 14])
    a.li32(4, MB_BASE)                  # R4 = 0x0203FC00

    # +0x00: Magic word 0x54525954 ('TRYT')
    a.li32(0, 0x54525954)
    a.str(0, 4, 0x00)
    # +0x04: Frame counter
    a.ldr(0, 11, S_FRAME)
    a.str(0, 4, 0x04)
    # +0x08..+0x0B: accepting_input, screen_state, mode, ghost_enabled
    a.ldrb(0, 11, S_ACCEPT_INPUT)
    a.strb(0, 4, 0x08)
    a.ldrb(0, 11, S_SCREEN)
    a.strb(0, 4, 0x09)
    a.ldrb(0, 11, S_MODE)
    a.strb(0, 4, 0x0A)
    a.ldrb(0, 11, S_GHOST)
    a.strb(0, 4, 0x0B)
    # +0x0C: lag_counter
    a.ldr(0, 11, S_LAG_COUNT)
    a.str(0, 4, 0x0C)
    # +0x10..+0x28: seed, score, level, lines, combo, b2b, gameover, paused, save_valid, ach_mask
    a.ldr(0, 11, S_SEED);       a.str(0, 4, 0x10)
    a.ldr(0, 11, S_SCORE);      a.str(0, 4, 0x14)
    a.ldr(0, 11, S_LEVEL);      a.str(0, 4, 0x18)
    a.ldr(0, 11, S_LINES);      a.str(0, 4, 0x1C)
    a.ldr(0, 11, S_COMBO);      a.str(0, 4, 0x20)
    a.ldrb(0, 11, S_B2B);       a.strb(0, 4, 0x24)
    a.ldrb(0, 11, S_GAMEOVER);  a.strb(0, 4, 0x25)
    a.ldrb(0, 11, S_PAUSED);    a.strb(0, 4, 0x26)
    a.ldrb(0, 11, S_SAVE_VALID);a.strb(0, 4, 0x27)
    a.ldr(0, 11, S_ACH_MASK);   a.str(0, 4, 0x28)
    # +0x2C..+0x2F: activePiece (id, rot, r, c)
    a.ldrb(0, 11, S_ACT_ID);    a.strb(0, 4, 0x2C)
    a.ldrb(0, 11, S_ACT_ROT);   a.strb(0, 4, 0x2D)
    a.ldrb(0, 11, S_ACT_R);     a.strb(0, 4, 0x2E)
    a.ldrb(0, 11, S_ACT_C);     a.strb(0, 4, 0x2F)
    # +0x30..+0x3F: idle_frames, grav_timer, call_total, lock_total
    a.ldr(0, 11, S_IDLE_FRAMES);a.str(0, 4, 0x30)
    a.ldr(0, 11, S_GRAV_TIMER); a.str(0, 4, 0x34)
    a.ldr(0, 11, S_CALL_TOTAL); a.str(0, 4, 0x38)
    a.ldr(0, 11, S_LOCK_TOTAL); a.str(0, 4, 0x3C)

    # +0x40..+0x93 (84 bytes): Packed 2-bit board (12 x 28 = 336 cells, 4 cells per byte)
    # 0 = empty, 1 = UP occupied ((r+c) even), 2 = DOWN occupied ((r+c) odd)
    # Each row r (0..27) has 12 cells -> 3 bytes at MB_BASE + 0x40 + r * 3!
    a.add_imm(5, 4, 0x40)               # R5 = dst ptr (MB_BASE + 0x40)
    a.add_imm(6, 11, S_BOARD_MASKS)     # R6 = &S_BOARD_MASKS[0]
    a.mov_imm(7, 0)                     # r = 0..27
    a.label("wm_2bit_row_loop")
    a.ldrh(8, 6, 2, p=0)                # R8 = 12-bit row mask
    a.mov_imm(9, 0)                     # group = 0..2 (3 bytes per row, 4 cols per byte)
    a.label("wm_2bit_byte_loop")
    a.mov_imm(10, 0)                    # packed byte = 0
    a.mov_imm(0, 0)                     # subcol = 0..3
    a.label("wm_2bit_cell_loop")
    a.add_reg(1, 0, 9, shift_imm=2, shift_type=a.LSL) # c = group*4 + subcol
    a.mov_imm(2, 1)
    a.mov_reg_rs(2, 2, 1, shift_type=a.LSL)
    a.tst_reg(8, 2)
    a.b("wm_2bit_cell_next", cond=a.EQ)
    # Occupied! Check parity of (r + c): even -> 1 (UP), odd -> 2 (DOWN)
    a.add_reg(2, 7, 1)
    a.tst_imm(2, 1)
    a.mov_imm(2, 1, cond=a.EQ)
    a.mov_imm(2, 2, cond=a.NE)
    a.mov_reg(3, 0, shift_imm=1, shift_type=a.LSL) # shift = subcol * 2
    a.mov_reg_rs(2, 2, 3, shift_type=a.LSL)
    a.orr_reg(10, 10, 2)
    a.label("wm_2bit_cell_next")
    a.add_imm(0, 0, 1)
    a.cmp_imm(0, 4)
    a.b("wm_2bit_cell_loop", cond=a.LT)

    a.strb(10, 5, 1, p=0)               # *R5++ = packed byte
    a.add_imm(9, 9, 1)
    a.cmp_imm(9, 3)
    a.b("wm_2bit_byte_loop", cond=a.LT)

    a.add_imm(7, 7, 1)
    a.cmp_imm(7, 28)
    a.b("wm_2bit_row_loop", cond=a.LT)

    # +0x94..+0x1E3 (336 bytes = 84 words): Copy S_BOARD_CELLS (1 byte per cell: 0=empty, 1..16=pieceId)
    # R5 is now at MB_BASE + 0x94!
    a.add_imm(6, 11, S_BOARD_CELLS)
    a.mov_imm(7, 84)
    a.label("wm_cells_loop")
    a.ldr(0, 6, 4, p=0)
    a.str(0, 5, 4, p=0)
    a.sub_imm(7, 7, 1, s=1)
    a.b("wm_cells_loop", cond=a.NE)

    # +0x1E4..+0x1FF: R5 is now at MB_BASE + 0x1E4!
    # +0x1E4: preview pieces 0, 1, 2 (from S_BAG_BUF[0..2]) + bot_plan_len
    a.add_imm(6, 11, S_BAG_BUF)
    a.ldrb(0, 6, 0); a.strb(0, 5, 0)    # +0x1E4: preview[0]
    a.ldrb(0, 6, 1); a.strb(0, 5, 1)    # +0x1E5: preview[1]
    a.ldrb(0, 6, 2); a.strb(0, 5, 2)    # +0x1E6: preview[2]
    a.ldrb(0, 11, S_BOT_PLAN_LEN)
    a.strb(0, 5, 3)                     # +0x1E7: bot_plan_len
    # +0x1E8..+0x1FB (20 bytes = 5 words): Copy first 20 bytes of S_BOT_PLAN_BUF
    a.add_imm(6, 11, S_BOT_PLAN_BUF)
    a.ldr(0, 6, 0);  a.str(0, 5, 4)
    a.ldr(0, 6, 4);  a.str(0, 5, 8)
    a.ldr(0, 6, 8);  a.str(0, 5, 12)
    a.ldr(0, 6, 12); a.str(0, 5, 16)
    a.ldr(0, 6, 16); a.str(0, 5, 20)
    # +0x1FC: ghost_r, ghost_c, attract_games, bot_plan_pos
    a.ldrb(0, 11, S_GHOST_R);      a.strb(0, 5, 24)
    a.ldrb(0, 11, S_GHOST_C);      a.strb(0, 5, 25)
    a.ldrb(0, 11, S_ATTRACT_GAMES);a.strb(0, 5, 26)
    a.ldrb(0, 11, S_BOT_PLAN_POS); a.strb(0, 5, 27)

    # Compute live 500-piece SeededBagGenerator digest at 0x0203FA00..0x0203FBF3
    # when S_CALL_TOTAL == 0 (start of game / Title screen)
    a.ldr(0, 11, S_CALL_TOTAL)
    a.cmp_imm(0, 0)
    a.pop([4, 5, 6, 7, 8, 9, 10, 15], cond=a.NE)
    a.ldrb(0, 11, S_MODE)
    a.ldr(1, 11, S_LEVEL)
    a.bl("get_vocab_sig")
    # R0 = 1 (TET4: start=1, cnt=4), 2 (CURSED16: start=1, cnt=16), 3 (HEX12: start=5, cnt=12)
    a.cmp_imm(0, 1); a.mov_imm(4, 1, cond=a.EQ); a.mov_imm(5, 4,  cond=a.EQ)
    a.cmp_imm(0, 2); a.mov_imm(4, 1, cond=a.EQ); a.mov_imm(5, 16, cond=a.EQ)
    a.cmp_imm(0, 3); a.mov_imm(4, 5, cond=a.EQ); a.mov_imm(5, 12, cond=a.EQ)

    a.ldr(6, 11, S_SEED)                # R6 = local Mulberry32 state `a`
    a.li32(7, 0x0203FA00)               # R7 = dst ptr
    a.li32(8, 500)                      # R8 = remaining pieces to emit
    a.sub_imm(13, 13, 16)               # 16-byte stack scratch for bag shuffle

    a.label("wm_seq_bag_loop")
    # Fill stack[0..R5-1] with R4 .. R4+R5-1
    a.mov_imm(9, 0)
    a.label("wm_seq_init")
    a.add_reg(0, 4, 9)
    a.strb_reg(0, 13, 9)
    a.add_imm(9, 9, 1)
    a.cmp_reg(9, 5)
    a.b("wm_seq_init", cond=a.LT)

    # Fisher-Yates shuffle: for i = R5 - 1 down to 1
    a.sub_imm(9, 5, 1)
    a.label("wm_seq_fy")
    a.li32(0, 0x6D2B79F5)
    a.add_reg(6, 6, 0)
    a.eor_reg(1, 6, 6, shift_imm=15, shift_type=a.LSR)
    a.orr_imm(2, 6, 1)
    a.mul(0, 1, 2)
    a.eor_reg(1, 0, 0, shift_imm=7, shift_type=a.LSR)
    a.orr_imm(2, 0, 61)
    a.mul(3, 1, 2)
    a.add_reg(3, 0, 3)
    a.eor_reg(0, 0, 3)
    a.eor_reg(0, 0, 0, shift_imm=14, shift_type=a.LSR)
    a.add_imm(1, 9, 1)
    a.umull(2, 3, 0, 1)                 # R3 = j
    a.ldrb_reg(1, 13, 9)
    a.ldrb_reg(2, 13, 3)
    a.strb_reg(2, 13, 9)
    a.strb_reg(1, 13, 3)
    a.sub_imm(9, 9, 1, s=1)
    a.b("wm_seq_fy", cond=a.GT)

    # Emit min(R5, R8) bytes to *R7++
    a.mov_imm(9, 0)
    a.label("wm_seq_emit")
    a.ldrb_reg(0, 13, 9)
    a.strb(0, 7, 1, p=0)
    a.sub_imm(8, 8, 1, s=1)
    a.b("wm_seq_done", cond=a.EQ)
    a.add_imm(9, 9, 1)
    a.cmp_reg(9, 5)
    a.b("wm_seq_emit", cond=a.LT)
    a.b("wm_seq_bag_loop")

    a.label("wm_seq_done")
    a.add_imm(13, 13, 16)
    a.pop([4, 5, 6, 7, 8, 9, 10, 15])

# Module 3: SRAM Saves, PSG Sound & Music, Mode 3 Renderer, and Main Loop


def emit_system_and_ui_subroutines(a: ArmBuilder, swap_lr=False, bad_cell_offset=False):
    # ==========================================================================
    # SRAM Save Subsystem (0x0E000000, 8-bit bus ONLY: LDRB / STRB)
    # Save Record Layout (72 bytes at 0x0E000000..0x0E000047):
    #   +0x00..0x03: 'T','R','Y','S' (0x54, 0x52, 0x59, 0x53)
    #   +0x04:       Version byte = 0x01
    #   +0x05:       Reserved = 0x00
    #   +0x06..0x07: earnedAchievements mask (uint16 LE)
    #   +0x08..0x43: High scores (3 modes * 5 scores * 4 bytes = 60 bytes LE)
    #   +0x44..0x47: 32-bit additive/FNV checksum over bytes 0x00..0x43 (4 bytes LE)
    # ==========================================================================

    # Subroutine: compute_sram_checksum() -> R0 = uint32 checksum over SRAM[0x00..0x43]
    a.label("compute_sram_checksum")
    a.push([4, 5, 6, 14])
    a.li32(4, SRAM_BASE)
    a.li32(0, 0x811C9DC5)               # FNV-1a 32-bit offset basis
    a.li32(5, 0x01000193)               # FNV-1a 32-bit prime
    a.mov_imm(6, 0)                     # i = 0..0x43 (68 bytes)
    a.label("csc_loop")
    a.ldrb_reg(1, 4, 6)
    a.eor_reg(0, 0, 1)
    a.mul(0, 0, 5)
    a.add_imm(6, 6, 1)
    a.cmp_imm(6, 0x44)
    a.b("csc_loop", cond=a.LT)
    # Ensure checksum is never 0xFFFFFFFF or 0x00000000 by XORing with 0x5A5AA5A5
    a.li32(1, 0x5A5AA5A5)
    a.eor_reg(0, 0, 1)
    a.pop([4, 5, 6, 15])

    # Subroutine: sram_save()
    # Writes live high scores & earnedAchievements to SRAM and stores checksum.
    a.label("sram_save")
    a.push([4, 5, 6, 14])
    a.li32(4, SRAM_BASE)
    a.mov_imm(0, ord('T')); a.strb(0, 4, 0)
    a.mov_imm(0, ord('R')); a.strb(0, 4, 1)
    a.mov_imm(0, ord('Y')); a.strb(0, 4, 2)
    a.mov_imm(0, ord('S')); a.strb(0, 4, 3)
    a.mov_imm(0, 1);        a.strb(0, 4, 4) # Version = 1
    a.mov_imm(0, 0);        a.strb(0, 4, 5) # Reserved = 0
    a.ldr(0, 11, S_ACH_MASK)
    a.strb(0, 4, 6)
    a.mov_reg(0, 0, shift_imm=8, shift_type=a.LSR)
    a.strb(0, 4, 7)

    # Copy 60 bytes of S_HIGH_SCORES to SRAM + 0x08 byte by byte
    a.add_imm(5, 11, S_HIGH_SCORES)
    a.add_imm(6, 4, 8)
    a.mov_imm(2, 0)
    a.label("ss_copy_loop")
    a.ldrb_reg(0, 5, 2)
    a.strb_reg(0, 6, 2)
    a.add_imm(2, 2, 1)
    a.cmp_imm(2, 60)
    a.b("ss_copy_loop", cond=a.LT)

    # Compute and write 4-byte checksum at SRAM + 0x44..0x47
    a.bl("compute_sram_checksum")
    a.strb(0, 4, 0x44)
    a.mov_reg(0, 0, shift_imm=8, shift_type=a.LSR)
    a.strb(0, 4, 0x45)
    a.mov_reg(0, 0, shift_imm=8, shift_type=a.LSR)
    a.strb(0, 4, 0x46)
    a.mov_reg(0, 0, shift_imm=8, shift_type=a.LSR)
    a.strb(0, 4, 0x47)
    a.mov_imm(0, 1)
    a.strb(0, 11, S_SAVE_VALID)
    a.pop([4, 5, 6, 15])

    # Subroutine: sram_load_or_init()
    # Verifies magic, version == 1, and checksum. If valid, loads high scores & achievements;
    # otherwise zeroes high scores & achievements and initializes fresh SRAM!
    a.label("sram_load_or_init")
    a.push([4, 5, 6, 14])
    a.li32(4, SRAM_BASE)
    a.ldrb(0, 4, 0); a.cmp_imm(0, ord('T')); a.b("sli_invalid", cond=a.NE)
    a.ldrb(0, 4, 1); a.cmp_imm(0, ord('R')); a.b("sli_invalid", cond=a.NE)
    a.ldrb(0, 4, 2); a.cmp_imm(0, ord('Y')); a.b("sli_invalid", cond=a.NE)
    a.ldrb(0, 4, 3); a.cmp_imm(0, ord('S')); a.b("sli_invalid", cond=a.NE)
    a.ldrb(0, 4, 4); a.cmp_imm(0, 1);        a.b("sli_invalid", cond=a.NE)

    # Read stored checksum at +0x44..0x47
    a.ldrb(5, 4, 0x44)
    a.ldrb(0, 4, 0x45); a.orr_reg(5, 5, 0, shift_imm=8,  shift_type=a.LSL)
    a.ldrb(0, 4, 0x46); a.orr_reg(5, 5, 0, shift_imm=16, shift_type=a.LSL)
    a.ldrb(0, 4, 0x47); a.orr_reg(5, 5, 0, shift_imm=24, shift_type=a.LSL)

    a.bl("compute_sram_checksum")
    a.cmp_reg(0, 5)
    a.b("sli_invalid", cond=a.NE)

    # Valid! Load achievements and 60 bytes of high scores
    a.ldrb(0, 4, 6)
    a.ldrb(1, 4, 7)
    a.orr_reg(0, 0, 1, shift_imm=8, shift_type=a.LSL)
    a.li32(1, 0x3FF)
    a.and_reg(0, 0, 1)
    a.str(0, 11, S_ACH_MASK)

    a.add_imm(5, 11, S_HIGH_SCORES)
    a.add_imm(6, 4, 8)
    a.mov_imm(2, 0)
    a.label("sli_load_loop")
    a.ldrb_reg(0, 6, 2)
    a.strb_reg(0, 5, 2)
    a.add_imm(2, 2, 1)
    a.cmp_imm(2, 60)
    a.b("sli_load_loop", cond=a.LT)

    a.mov_imm(0, 1)
    a.strb(0, 11, S_SAVE_VALID)
    a.pop([4, 5, 6, 15])

    a.label("sli_invalid")
    # Fresh start: zero S_ACH_MASK and S_HIGH_SCORES (60 bytes = 15 words), then write clean SRAM
    a.mov_imm(0, 0)
    a.strb(0, 11, S_SAVE_VALID)
    a.str(0, 11, S_ACH_MASK)
    a.add_imm(5, 11, S_HIGH_SCORES)
    a.mov_imm(2, 15)
    a.label("sli_zero_loop")
    a.str(0, 5, 4, p=0)
    a.sub_imm(2, 2, 1, s=1)
    a.b("sli_zero_loop", cond=a.NE)
    # Write fresh valid record to SRAM (keep S_SAVE_VALID = 0 to record that boot detected blank/invalid SRAM,
    # or wait: let's set S_SAVE_VALID = 0 on invalid boot and set it to 1 when sram_save is called!
    # Wait: if we call sram_save here, S_SAVE_VALID becomes 1, so let's save S_SAVE_VALID = 0 after sram_save on invalid boot so tests can even inspect whether the boot save was valid or fresh!)
    a.bl("sram_save")
    a.mov_imm(0, 0)
    a.strb(0, 11, S_SAVE_VALID)
    a.pop([4, 5, 6, 15])

    # ==========================================================================
    # Subroutine: record_high_score()
    # Inserts S_SCORE into top-5 list for S_MODE (if > 0 and not already saved)
    # and calls sram_save().
    # ==========================================================================
    a.label("record_high_score")
    a.push([4, 5, 6, 7, 14])
    a.ldrb(0, 11, S_HS_SAVED_FLAG)
    a.cmp_imm(0, 0)
    a.pop([4, 5, 6, 7, 15], cond=a.NE)
    a.mov_imm(0, 1)
    a.strb(0, 11, S_HS_SAVED_FLAG)

    a.ldr(4, 11, S_SCORE)               # R4 = score
    a.cmp_imm(4, 0)
    a.pop([4, 5, 6, 7, 15], cond=a.EQ)

    a.ldrb(0, 11, S_MODE)               # 0..2
    a.mov_imm(1, 20)                    # 5 scores * 4 bytes = 20 bytes per mode
    a.mul(0, 0, 1)
    a.add_imm(5, 11, S_HIGH_SCORES)
    a.add_reg(5, 5, 0)                  # R5 = &high_scores[mode][0]

    # Find insertion index i in 0..4 where score > table[i]
    a.mov_imm(6, 0)                     # i = 0
    a.label("rhs_find_loop")
    a.cmp_imm(6, 5)
    a.b("rhs_done", cond=a.GE)
    a.ldr_reg(0, 5, 6, shift_imm=2, shift_type=a.LSL)
    a.cmp_reg(4, 0)
    a.b("rhs_insert", cond=a.HI)
    a.add_imm(6, 6, 1)
    a.b("rhs_find_loop")

    a.label("rhs_insert")
    # Shift j = 4 down to i + 1
    a.mov_imm(7, 4)
    a.label("rhs_shift_loop")
    a.cmp_reg(7, 6)
    a.b("rhs_write", cond=a.LE)
    a.sub_imm(1, 7, 1)
    a.ldr_reg(0, 5, 1, shift_imm=2, shift_type=a.LSL)
    a.str_reg(0, 5, 7, shift_imm=2, shift_type=a.LSL)
    a.sub_imm(7, 7, 1)
    a.b("rhs_shift_loop")

    a.label("rhs_write")
    a.str_reg(4, 5, 6, shift_imm=2, shift_type=a.LSL)
    a.bl("sram_save")

    a.label("rhs_done")
    a.pop([4, 5, 6, 7, 15])

    # ==========================================================================
    # PSG Sound Effects & Original Music Sequencer
    # ==========================================================================
    # Subroutine: sound_init()
    a.label("sound_init")
    a.mov_imm(0, IO_BASE)
    a.mov_imm(1, 0x0080)
    a.strh(1, 0, 0x84)                  # SOUNDCNT_X = master enable
    a.li32(1, 0xFF77)
    a.strh(1, 0, 0x80)                  # SOUNDCNT_L = Ch1-4 L/R enable, max vol
    a.mov_imm(1, 0x0002)
    a.strh(1, 0, 0x82)                  # SOUNDCNT_H = 100% PSG volume
    # Load triangle wave into Wave RAM (0x04000090..0x0400009F)
    a.mov_imm(1, 0x0040)
    a.strh(1, 0, 0x70)                  # SOUND3CNT_L = bank 1 selected, bank 0 accessible
    a.li32(1, 0x76543210)
    a.str(1, 0, 0x90)
    a.li32(1, 0xFEDCBA98)
    a.str(1, 0, 0x94)
    a.li32(1, 0x89ABCDEF)
    a.str(1, 0, 0x98)
    a.li32(1, 0x01234567)
    a.str(1, 0, 0x9C)
    a.mov_imm(1, 0x0080)
    a.strh(1, 0, 0x70)                  # SOUND3CNT_L = bank 0 playback enabled
    a.bx(14)

    # Subroutine: sfx_play(R0=sfx_id 1..7)
    # 1: move (330 Hz -> 1650)
    # 2: rotate (494 Hz -> 1783)
    # 3: soft drop / lock (262 Hz -> 1547)
    # 4: hard drop (196 Hz -> 1379 + noise)
    # 5: line clear (523 Hz -> 1798 upward sweep)
    # 6: achievement unlock (880 Hz -> 1899 chime)
    # 7: game over (220 Hz -> 1452 downward sweep)
    a.label("sfx_play")
    a.push([4, 5, 14])
    a.mov_imm(4, IO_BASE)
    a.cmp_imm(0, 1)
    a.b("sfx_chk2", cond=a.NE)
    # 1: move
    a.mov_imm(1, 0x0000); a.strh(1, 4, 0x60)
    a.li32(1, 0xA180);    a.strh(1, 4, 0x62)
    a.li32(1, 0x8000 | 1650); a.strh(1, 4, 0x64)
    a.pop([4, 5, 15])

    a.label("sfx_chk2")
    a.cmp_imm(0, 2)
    a.b("sfx_chk3", cond=a.NE)
    # 2: rotate
    a.mov_imm(1, 0x0011); a.strh(1, 4, 0x60)
    a.li32(1, 0xB180);    a.strh(1, 4, 0x62)
    a.li32(1, 0x8000 | 1783); a.strh(1, 4, 0x64)
    a.pop([4, 5, 15])

    a.label("sfx_chk3")
    a.cmp_imm(0, 3)
    a.b("sfx_chk4", cond=a.NE)
    # 3: soft drop / lock
    a.mov_imm(1, 0x0000); a.strh(1, 4, 0x60)
    a.li32(1, 0xA140);    a.strh(1, 4, 0x62)
    a.li32(1, 0x8000 | 1547); a.strh(1, 4, 0x64)
    a.pop([4, 5, 15])

    a.label("sfx_chk4")
    a.cmp_imm(0, 4)
    a.b("sfx_chk5", cond=a.NE)
    # 4: hard drop (Ch1 low thud + Ch4 noise burst)
    a.mov_imm(1, 0x001A); a.strh(1, 4, 0x60)
    a.li32(1, 0xC180);    a.strh(1, 4, 0x62)
    a.li32(1, 0x8000 | 1379); a.strh(1, 4, 0x64)
    a.li32(1, 0xB120);    a.strh(1, 4, 0x78) # SOUND4CNT_L
    a.li32(1, 0x8043);    a.strh(1, 4, 0x7C) # SOUND4CNT_H
    a.pop([4, 5, 15])

    a.label("sfx_chk5")
    a.cmp_imm(0, 5)
    a.b("sfx_chk6", cond=a.NE)
    # 5: line clear (upward sweep)
    a.mov_imm(1, 0x0022); a.strh(1, 4, 0x60)
    a.li32(1, 0xE280);    a.strh(1, 4, 0x62)
    a.li32(1, 0x8000 | 1750); a.strh(1, 4, 0x64)
    a.pop([4, 5, 15])

    a.label("sfx_chk6")
    a.cmp_imm(0, 6)
    a.b("sfx_chk7", cond=a.NE)
    # 6: achievement unlock
    a.mov_imm(1, 0x0011); a.strh(1, 4, 0x60)
    a.li32(1, 0xF380);    a.strh(1, 4, 0x62)
    a.li32(1, 0x8000 | 1899); a.strh(1, 4, 0x64)
    a.pop([4, 5, 15])

    a.label("sfx_chk7")
    # 7: game over (downward sweep)
    a.mov_imm(1, 0x0039); a.strh(1, 4, 0x60)
    a.li32(1, 0xD380);    a.strh(1, 4, 0x62)
    a.li32(1, 0x8000 | 1650); a.strh(1, 4, 0x64)
    a.pop([4, 5, 15])

    # Subroutine: music_step()
    # Steps original composition on Ch2 (Square 2) & Ch3 (Wave) every 12 frames.
    a.label("music_step")
    a.push([4, 5, 6, 14])
    # If paused, silence Ch2/Ch3 and return
    a.ldrb(0, 11, S_PAUSED)
    a.cmp_imm(0, 0)
    a.b("ms_active", cond=a.EQ)
    a.mov_imm(4, IO_BASE)
    a.mov_imm(0, 0)
    a.strh(0, 4, 0x68)
    a.strh(0, 4, 0x72)
    a.pop([4, 5, 6, 15])

    a.label("ms_active")
    a.ldrh(0, 11, S_MUSIC_TICK)
    a.add_imm(0, 0, 1)
    a.cmp_imm(0, 12)
    a.strh(0, 11, S_MUSIC_TICK, cond=a.LT)
    a.pop([4, 5, 6, 15], cond=a.LT)

    # Reset tick = 0, advance note index (0..31)
    a.mov_imm(0, 0)
    a.strh(0, 11, S_MUSIC_TICK)
    a.ldrh(5, 11, S_MUSIC_NOTE)
    a.add_imm(1, 5, 1)
    a.and_imm(1, 1, 31)
    a.strh(1, 11, S_MUSIC_NOTE)

    # Choose Title theme (if S_SCREEN == 0 or 3) vs Play theme (if S_SCREEN == 1 or 4)
    a.ldrb(0, 11, S_SCREEN)
    a.cmp_imm(0, 1)
    a.b("ms_use_play", cond=a.EQ)
    a.cmp_imm(0, 4)
    a.b("ms_use_play", cond=a.EQ)
    a.la(6, "music_title_table")
    a.b("ms_play_note")
    a.label("ms_use_play")
    a.la(6, "music_play_table")

    a.label("ms_play_note")
    # Each entry in music_*_table is 4 bytes: uint16 ch2_freq, uint16 ch3_freq
    a.add_reg(6, 6, 5, shift_imm=2, shift_type=a.LSL)
    a.ldrh(1, 6, 0)                     # ch2_freq
    a.ldrh(2, 6, 2)                     # ch3_freq
    a.mov_imm(4, IO_BASE)

    a.cmp_imm(1, 0)
    a.b("ms_ch3", cond=a.EQ)
    a.li32(0, 0x6280)                   # vol 6, env decay 2, 50% duty
    a.strh(0, 4, 0x68)                  # SOUND2CNT_L
    a.li32(0, 0x8000)
    a.orr_reg(0, 0, 1)
    a.strh(0, 4, 0x6C)                  # SOUND2CNT_H

    a.label("ms_ch3")
    a.cmp_imm(2, 0)
    a.b("ms_done", cond=a.EQ)
    a.li32(0, 0x4000)                   # 50% volume
    a.strh(0, 4, 0x72)                  # SOUND3CNT_H
    a.li32(0, 0x8000)
    a.orr_reg(0, 0, 2)
    a.strh(0, 4, 0x74)                  # SOUND3CNT_X

    a.label("ms_done")
    a.pop([4, 5, 6, 15])

    # ==========================================================================
    # Mode 3 Graphics & Equilateral-ish Triangle Renderer
    # ==========================================================================
    # Subroutine: fill_rect(R0=x, R1=y, R2=w, R3=h, R4=color_bgr555)
    # Uses DMA3 16-bit fixed-source fill per scanline row for fast VBlank-safe rendering.
    a.label("fill_rect")
    a.push([5, 6, 7, 8, 9, 14])
    a.cmp_imm(2, 0)
    a.pop([5, 6, 7, 8, 9, 15], cond=a.LE)
    a.cmp_imm(3, 0)
    a.pop([5, 6, 7, 8, 9, 15], cond=a.LE)
    # Store 16-bit color on stack at [SP - 4]
    a.sub_imm(13, 13, 4)
    a.strh(4, 13, 0)
    a.mov_imm(5, VRAM_BASE)
    a.mov_imm(6, 240)
    a.mul(7, 1, 6)
    a.add_reg(7, 7, 0)
    a.add_reg(7, 5, 7, shift_imm=1, shift_type=a.LSL) # R7 = initial row dst
    a.mov_imm(8, IO_BASE)
    a.li32(9, 0x81000000)
    a.orr_reg(9, 9, 2)                                # R9 = DMA3CNT_L(w) | (0x8100 << 16)
    a.label("fr_y_loop")
    a.str(13, 8, 0xD4)                                # REG_DMA3SAD = SP
    a.str(7,  8, 0xD8)                                # REG_DMA3DAD = dst
    a.str(9,  8, 0xDC)                                # REG_DMA3CNT = fixed src, 16-bit, enable
    a.add_imm(7, 7, 480)                              # next scanline (+240 * 2)
    a.sub_imm(3, 3, 1, s=1)
    a.b("fr_y_loop", cond=a.NE)
    a.add_imm(13, 13, 4)
    a.pop([5, 6, 7, 8, 9, 15])

    # Subroutine: draw_char(R0=x, R1=y, R2=ascii, R3=color)
    a.label("draw_char")
    a.push([4, 5, 6, 7, 8, 9, 10, 14])
    a.sub_imm(4, 2, 32)
    a.cmp_imm(4, 0)
    a.b("dc_done", cond=a.LT)
    a.cmp_imm(4, 95)
    a.b("dc_done", cond=a.GE)
    a.la(5, "font_table")
    a.add_reg(5, 5, 4, shift_imm=3, shift_type=a.LSL)
    # Compute base VRAM ptr = VRAM_BASE + (y * 240 + x) * 2
    a.mov_imm(9, 240)
    a.mul(10, 1, 9)
    a.add_reg(10, 10, 0)
    a.mov_imm(9, VRAM_BASE)
    a.add_reg(10, 9, 10, shift_imm=1, shift_type=a.LSL)
    a.mov_imm(6, 8)                     # 8 rows
    a.label("dc_row_loop")
    a.ldrb(7, 5, 1, p=0)                # glyph row byte
    a.cmp_imm(7, 0)
    a.b("dc_next_row", cond=a.EQ)
    a.tst_imm(7, 0x80); a.strh(3, 10, 0,  cond=a.NE)
    a.tst_imm(7, 0x40); a.strh(3, 10, 2,  cond=a.NE)
    a.tst_imm(7, 0x20); a.strh(3, 10, 4,  cond=a.NE)
    a.tst_imm(7, 0x10); a.strh(3, 10, 6,  cond=a.NE)
    a.tst_imm(7, 0x08); a.strh(3, 10, 8,  cond=a.NE)
    a.tst_imm(7, 0x04); a.strh(3, 10, 10, cond=a.NE)
    a.tst_imm(7, 0x02); a.strh(3, 10, 12, cond=a.NE)
    a.tst_imm(7, 0x01); a.strh(3, 10, 14, cond=a.NE)
    a.label("dc_next_row")
    a.add_imm(10, 10, 480)
    a.sub_imm(6, 6, 1, s=1)
    a.b("dc_row_loop", cond=a.NE)
    a.label("dc_done")
    a.pop([4, 5, 6, 7, 8, 9, 10, 15])

    # Subroutine: draw_str6(R0=x, R1=y, R2=str_ptr, R3=color) (6px spacing)
    a.label("draw_str6")
    a.push([4, 5, 6, 7, 14])
    a.mov_reg(4, 0); a.mov_reg(5, 1); a.mov_reg(6, 2); a.mov_reg(7, 3)
    a.label("ds6_loop")
    a.ldrh(2, 6, 2, p=0)
    a.cmp_imm(2, 0)
    a.pop([4, 5, 6, 7, 15], cond=a.EQ)
    a.mov_reg(0, 4); a.mov_reg(1, 5); a.mov_reg(3, 7)
    a.bl("draw_char")
    a.add_imm(4, 4, 6)
    a.b("ds6_loop")

    # Subroutine: draw_str8(R0=x, R1=y, R2=str_ptr, R3=color) (8px spacing)
    a.label("draw_str8")
    a.push([4, 5, 6, 7, 14])
    a.mov_reg(4, 0); a.mov_reg(5, 1); a.mov_reg(6, 2); a.mov_reg(7, 3)
    a.label("ds8_loop")
    a.ldrh(2, 6, 2, p=0)
    a.cmp_imm(2, 0)
    a.pop([4, 5, 6, 7, 15], cond=a.EQ)
    a.mov_reg(0, 4); a.mov_reg(1, 5); a.mov_reg(3, 7)
    a.bl("draw_char")
    a.add_imm(4, 4, 8)
    a.b("ds8_loop")

    # Subroutine: draw_uint(R0=x, R1=y, R2=val, R3=color)
    # Draws unsigned integer R2 in decimal (6px per digit).
    a.label("draw_uint")
    a.push([4, 5, 6, 7, 8, 9, 14])
    a.mov_reg(4, 0); a.mov_reg(5, 1); a.mov_reg(6, 2); a.mov_reg(7, 3)
    a.sub_imm(13, 13, 16)
    a.mov_imm(8, 0)                     # digit count
    a.cmp_imm(6, 0)
    a.b("du_extract_loop", cond=a.NE)
    a.mov_imm(0, ord('0'))
    a.strb(0, 13, 0)
    a.mov_imm(8, 1)
    a.b("du_print_loop")

    a.label("du_extract_loop")
    a.cmp_imm(6, 0)
    a.b("du_print_loop", cond=a.EQ)
    # q = (val * 0xCCCCCCCD) >> 35; rem = val - q * 10
    a.li32(0, 0xCCCCCCCD)
    a.umull(1, 2, 6, 0)
    a.mov_reg(2, 2, shift_imm=3, shift_type=a.LSR) # q
    a.mov_imm(0, 10)
    a.mul(1, 2, 0)
    a.sub_reg(1, 6, 1)                  # rem
    a.add_imm(1, 1, ord('0'))
    a.strb_reg(1, 13, 8)
    a.add_imm(8, 8, 1)
    a.mov_reg(6, 2)
    a.b("du_extract_loop")

    a.label("du_print_loop")
    a.sub_imm(8, 8, 1, s=1)
    a.b("du_done", cond=a.LT)
    a.ldrb_reg(2, 13, 8)
    a.mov_reg(0, 4); a.mov_reg(1, 5); a.mov_reg(3, 7)
    a.bl("draw_char")
    a.add_imm(4, 4, 6)
    a.b("du_print_loop")

    a.label("du_done")
    a.add_imm(13, 13, 16)
    a.pop([4, 5, 6, 7, 8, 9, 15])

    # Subroutine: draw_hex32(R0=x, R1=y, R2=val, R3=color, R4=highlight_nibble_or_neg1)
    # Draws 8 hex digits of R2 (6px per digit); if nibble index (0..7 from MSB) == R4, draws with gold highlight!
    a.label("draw_hex32")
    a.push([4, 5, 6, 7, 8, 9, 10, 14])
    a.mov_reg(5, 0); a.mov_reg(6, 1); a.mov_reg(7, 2); a.mov_reg(8, 3); a.mov_reg(9, 4)
    a.mov_imm(10, 0)                    # idx = 0..7
    a.label("dh32_loop")
    a.rsb_imm(0, 10, 7)
    a.mov_reg(0, 0, shift_imm=2, shift_type=a.LSL) # shift = (7 - idx) * 4
    a.mov_reg_rs(2, 7, 0, shift_type=a.LSR)
    a.and_imm(2, 2, 0xF)
    a.cmp_imm(2, 10)
    a.add_imm(2, 2, ord('0'), cond=a.LT)
    a.add_imm(2, 2, ord('A') - 10, cond=a.GE)
    a.mov_reg(3, 8)
    a.cmp_reg(10, 9)
    a.li32(3, rgb15(31, 31, 4), cond=a.EQ)
    a.mov_reg(0, 5); a.mov_reg(1, 6)
    a.bl("draw_char")
    # If highlighted nibble, draw a small underline at y+8
    a.cmp_reg(10, 9)
    a.b("dh32_next", cond=a.NE)
    a.push([4])
    a.mov_reg(0, 5); a.add_imm(1, 6, 8); a.mov_imm(2, 6); a.mov_imm(3, 1)
    a.li32(4, rgb15(31, 27, 4))
    a.bl("fill_rect")
    a.pop([4])
    a.label("dh32_next")
    a.add_imm(5, 5, 6)
    a.add_imm(10, 10, 1)
    a.cmp_imm(10, 8)
    a.b("dh32_loop", cond=a.LT)
    a.pop([4, 5, 6, 7, 8, 9, 10, 15])

    # ==========================================================================
    # Subroutine: draw_board_cell(R0=vr 0..23, R1=c 0..11, R2=color_bgr555)
    # Draws equilateral-ish triangle cell at visible row vr (board row vr+4), col c:
    #   BX = 72, BY = 8, S/2 = 7, H = 6 (Base S = 14px, Height H = 6px)
    #   UP triangle ((vr+c) even):   dy=0..5 -> dx in [7-(dy+1) .. 7+(dy+1)]
    #   DOWN triangle ((vr+c) odd):  dy=0..5 -> dx in [7-(6-dy) .. 7+(6-dy)]
    # ==========================================================================
    a.label("draw_board_cell")
    a.push([4, 5, 6, 7, 8, 9, 10, 14])
    a.cmp_imm(0, 0)
    a.b("dbc_done", cond=a.LT)
    a.cmp_imm(0, 24)
    a.b("dbc_done", cond=a.GE)
    a.cmp_imm(1, 0)
    a.b("dbc_done", cond=a.LT)
    a.cmp_imm(1, 12)
    a.b("dbc_done", cond=a.GE)

    # Compute x0 = (73 if bad_cell_offset else 72) + c * 7
    a.mov_imm(3, 7)
    a.mul(4, 1, 3)
    a.add_imm(4, 4, 73 if bad_cell_offset else 72) # R4 = x0
    # Compute y0 = 8 + vr * 6
    a.mov_imm(3, 6)
    a.mul(5, 0, 3)
    a.add_imm(5, 5, 8)                  # R5 = y0

    # Check parity of (vr + c): even -> UP (R6=0), odd -> DOWN (R6=1)
    a.add_reg(6, 0, 1)
    a.and_imm(6, 6, 1)

    # Compute row_center_ptr = VRAM_BASE + (y0 * 240 + x0 + 7) * 2
    a.mov_imm(3, 240)
    a.mul(10, 5, 3)
    a.add_reg(10, 10, 4)
    a.add_imm(10, 10, 7)
    a.mov_imm(3, VRAM_BASE)
    a.add_reg(10, 3, 10, shift_imm=1, shift_type=a.LSL) # R10 = &VRAM[y0][x0+7]

    a.mov_imm(7, 0)                     # dy = 0..5
    a.label("dbc_dy_loop")
    a.cmp_imm(6, 0)
    a.add_imm(8, 7, 1, cond=a.EQ)       # UP: half_w = dy + 1 (1..6)
    a.rsb_imm(8, 7, 6, cond=a.NE)       # DOWN: half_w = 6 - dy (6..1)

    # ptr = R10 - half_w * 2, count = 2 * half_w + 1
    a.sub_reg(1, 10, 8, shift_imm=1, shift_type=a.LSL)
    a.add_reg(9, 8, 8)
    a.add_imm(9, 9, 1)                  # count = 2 * half_w + 1
    a.label("dbc_dx_loop")
    a.strh(2, 1, 2, p=0)
    a.sub_imm(9, 9, 1, s=1)
    a.b("dbc_dx_loop", cond=a.NE)

    a.add_imm(10, 10, 480)              # next scanline (+240 * 2)
    a.add_imm(7, 7, 1)
    a.cmp_imm(7, 6)
    a.b("dbc_dy_loop", cond=a.LT)

    a.label("dbc_done")
    a.pop([4, 5, 6, 7, 8, 9, 10, 15])

    # ==========================================================================
    # Subroutine: draw_mini_cell(R0=px, R1=py, R2=r, R3=c, R4=color_bgr555)
    # Draws a compact triangle cell (S/2 = 4px, H = 4px) for Next 3 previews:
    #   x0 = px + c * 4, y0 = py + r * 4
    #   UP ((r+c) even):  dy=0..3 -> dx in [3-dy .. 3+dy]
    #   DOWN ((r+c) odd): dy=0..3 -> dx in [dy .. 6-dy]
    # ==========================================================================
    a.label("draw_mini_cell")
    a.push([4, 5, 6, 7, 8, 9, 10, 14])
    a.add_reg(5, 0, 3, shift_imm=2, shift_type=a.LSL) # x0 = px + c * 4
    a.add_reg(6, 1, 2, shift_imm=2, shift_type=a.LSL) # y0 = py + r * 4
    a.add_reg(7, 2, 3)
    a.and_imm(7, 7, 1)                  # 0=UP, 1=DOWN
    a.mov_imm(8, 0)                     # dy = 0..3
    a.mov_imm(10, VRAM_BASE)
    a.label("dmc_dy_loop")
    a.cmp_imm(7, 0)
    a.mov_reg(9, 8, cond=a.EQ)          # UP: half_w = dy (0..3)
    a.rsb_imm(9, 8, 3, cond=a.NE)       # DOWN: half_w = 3 - dy (3..0)

    a.add_imm(0, 5, 3)
    a.sub_reg(0, 0, 9)                  # start_x = x0 + 3 - half_w
    a.add_reg(1, 6, 8)                  # y = y0 + dy
    a.mov_imm(2, 240)
    a.mul(1, 1, 2)
    a.add_reg(1, 1, 0)
    a.add_reg(1, 10, 1, shift_imm=1, shift_type=a.LSL)

    a.add_reg(2, 9, 9)
    a.add_imm(2, 2, 1)                  # count = 2 * half_w + 1
    a.label("dmc_dx_loop")
    a.strh(4, 1, 2, p=0)
    a.sub_imm(2, 2, 1, s=1)
    a.b("dmc_dx_loop", cond=a.NE)

    a.add_imm(8, 8, 1)
    a.cmp_imm(8, 4)
    a.b("dmc_dy_loop", cond=a.LT)
    a.pop([4, 5, 6, 7, 8, 9, 10, 15])

    # ==========================================================================
    # Subroutine: get_piece_bgr(R0=pieceId 1..16, R1=is_ghost 0/1) -> R0 = bgr555
    # ==========================================================================
    a.label("get_piece_bgr")
    a.cmp_imm(1, 0)
    a.la(2, "piece_color_table", cond=a.EQ)
    a.la(2, "piece_ghost_color_table", cond=a.NE)
    a.add_reg(2, 2, 0, shift_imm=2, shift_type=a.LSL)
    a.ldrh(0, 2, 0)
    a.bx(14)

    # ==========================================================================
    # Subroutine: draw_Underlying_board_cell(R0=r 4..27, R1=c 0..11)
    # Draws cell (r, c) from S_BOARD_CELLS[r*12+c] (either locked piece color or empty color).
    # ==========================================================================
    a.label("draw_underlying_board_cell")
    a.push([4, 5, 6, 14])
    a.cmp_imm(0, 4)
    a.b("dubc_done", cond=a.LT)
    a.cmp_imm(0, 28)
    a.b("dubc_done", cond=a.GE)
    a.cmp_imm(1, 0)
    a.b("dubc_done", cond=a.LT)
    a.cmp_imm(1, 12)
    a.b("dubc_done", cond=a.GE)

    a.mov_reg(4, 0)                     # r
    a.mov_reg(5, 1)                     # c
    a.mov_imm(2, 12)
    a.mul(3, 4, 2)
    a.add_reg(3, 3, 5)
    a.add_imm(2, 11, S_BOARD_CELLS)
    a.ldrb_reg(0, 2, 3)                 # pieceId (0..16)
    a.cmp_imm(0, 0)
    a.b("dubc_occupied", cond=a.NE)
    # Empty: parity of (r + c) -> even = EMPTY_UP (0x0C41), odd = EMPTY_DN (0x0821)
    a.add_reg(0, 4, 5)
    a.tst_imm(0, 1)
    a.li32(2, hex_to_bgr555("#0c111d"), cond=a.EQ)
    a.li32(2, hex_to_bgr555("#090d16"), cond=a.NE)
    a.b("dubc_draw")

    a.label("dubc_occupied")
    a.mov_imm(1, 0)
    a.bl("get_piece_bgr")
    a.mov_reg(2, 0)

    a.label("dubc_draw")
    a.sub_imm(0, 4, 4)                  # vr = r - 4
    a.mov_reg(1, 5)
    a.bl("draw_board_cell")
    a.label("dubc_done")
    a.pop([4, 5, 6, 15])

    # ==========================================================================
    # Subroutine: draw_piece_on_board(R0=pieceId, R1=rotIndex, R2=anchorR, R3=anchorC, R4=mode: 0=active, 1=ghost, 2=restore_underlying)
    # ==========================================================================
    a.label("draw_piece_on_board")
    a.push([4, 5, 6, 7, 8, 9, 10, 14])
    a.cmp_imm(0, 0)
    a.b("dpob_done", cond=a.EQ)
    a.mov_reg(5, 0)                     # pieceId
    a.mov_reg(6, 1)                     # rotIndex
    a.mov_reg(7, 2)                     # anchorR
    a.mov_reg(8, 3)                     # anchorC
    a.mov_reg(9, 4)                     # mode (0=active, 1=ghost, 2=restore)

    # Get color if mode != 2
    a.cmp_imm(9, 2)
    a.b("dpob_get_cells", cond=a.EQ)
    a.mov_reg(0, 5)
    a.mov_reg(1, 9)                     # 0=active, 1=ghost
    a.bl("get_piece_bgr")
    a.mov_reg(10, 0)                    # R10 = color

    a.label("dpob_get_cells")
    a.mov_reg(0, 5); a.mov_reg(1, 6)
    a.bl("get_rot_cell_ptr")
    a.mov_reg(5, 0)                     # R5 = cell table ptr
    a.ldrb(6, 5, 0)                     # R6 = numCells
    a.mov_imm(4, 0)                     # i = 0..numCells-1
    a.label("dpob_loop")
    a.cmp_reg(4, 6)
    a.b("dpob_done", cond=a.GE)
    a.add_reg(0, 5, 4, shift_imm=1, shift_type=a.LSL)
    a.ldrb(2, 0, 4)                     # dr
    a.ldrb(3, 0, 5)                     # dc
    a.add_reg(0, 7, 2)                  # r = anchorR + dr
    a.add_reg(1, 8, 3)                  # c = anchorC + dc
    a.cmp_imm(0, 4)
    a.b("dpob_next", cond=a.LT)
    a.cmp_imm(9, 2)
    a.b("dpob_restore", cond=a.EQ)
    a.sub_imm(0, 0, 4)                  # vr = r - 4
    a.mov_reg(2, 10)                    # color
    a.bl("draw_board_cell")
    a.b("dpob_next")
    a.label("dpob_restore")
    a.bl("draw_underlying_board_cell")
    a.label("dpob_next")
    a.add_imm(4, 4, 1)
    a.b("dpob_loop")

    a.label("dpob_done")
    a.pop([4, 5, 6, 7, 8, 9, 10, 15])

    # ==========================================================================
    # Subroutine: render_board_full()
    # Draws all 24x12 visible cells from S_BOARD_CELLS, then ghost & active piece.
    # ==========================================================================
    a.label("render_board_full")
    a.push([4, 5, 14])
    # Draw dark border frame behind board (x=70..163, y=6..153, w=94, h=148)
    a.mov_imm(0, 71); a.mov_imm(1, 7); a.mov_imm(2, 93); a.mov_imm(3, 146)
    a.li32(4, rgb15(1, 2, 4))
    a.bl("fill_rect")

    a.mov_imm(4, 4)                     # r = 4..27
    a.label("rbf_r_loop")
    a.mov_imm(5, 0)                     # c = 0..11
    a.label("rbf_c_loop")
    a.mov_reg(0, 4); a.mov_reg(1, 5)
    a.bl("draw_underlying_board_cell")
    a.add_imm(5, 5, 1)
    a.cmp_imm(5, 12)
    a.b("rbf_c_loop", cond=a.LT)
    a.add_imm(4, 4, 1)
    a.cmp_imm(4, 28)
    a.b("rbf_r_loop", cond=a.LT)

    a.mov_imm(0, 0)
    a.strb(0, 11, S_BOARD_DIRTY)
    a.strb(0, 11, S_PREV_ACT_ID)
    a.pop([4, 5, 15])

    # ==========================================================================
    # Subroutine: render_board_incremental()
    # If S_BOARD_DIRTY == 1, calls render_board_full().
    # Otherwise erases previous ghost & active piece cells and draws current ghost & active piece!
    # ==========================================================================
    a.label("render_board_incremental")
    a.push([4, 5, 6, 7, 14])
    a.ldrb(0, 11, S_BOARD_DIRTY)
    a.cmp_imm(0, 0)
    a.bl("render_board_full", cond=a.NE)

    # Restore previous ghost & active piece if S_PREV_ACT_ID != 0
    a.ldrb(4, 11, S_PREV_ACT_ID)
    a.cmp_imm(4, 0)
    a.b("rbi_draw_curr", cond=a.EQ)
    a.ldrb(5, 11, S_PREV_ACT_ROT)
    a.ldrsb(6, 11, S_PREV_GHOST_R)
    a.ldrsb(7, 11, S_PREV_GHOST_C)
    a.mov_reg(0, 4); a.mov_reg(1, 5); a.mov_reg(2, 6); a.mov_reg(3, 7); a.mov_imm(4, 2)
    a.bl("draw_piece_on_board")

    a.ldrb(0, 11, S_PREV_ACT_ID)
    a.ldrb(1, 11, S_PREV_ACT_ROT)
    a.ldrsb(2, 11, S_PREV_ACT_R)
    a.ldrsb(3, 11, S_PREV_ACT_C)
    a.mov_imm(4, 2)
    a.bl("draw_piece_on_board")

    a.label("rbi_draw_curr")
    # If gameOver != 0, clear S_PREV_ACT_ID and return
    a.ldrb(0, 11, S_GAMEOVER)
    a.cmp_imm(0, 0)
    a.mov_imm(0, 0, cond=a.NE)
    a.strb(0, 11, S_PREV_ACT_ID, cond=a.NE)
    a.pop([4, 5, 6, 7, 15], cond=a.NE)

    a.ldrb(4, 11, S_ACT_ID)
    a.cmp_imm(4, 0)
    a.pop([4, 5, 6, 7, 15], cond=a.EQ)
    a.ldrb(5, 11, S_ACT_ROT)

    # Draw ghost piece if S_GHOST == 1
    a.ldrb(0, 11, S_GHOST)
    a.cmp_imm(0, 1)
    a.b("rbi_draw_act", cond=a.NE)
    a.ldrsb(2, 11, S_GHOST_R)
    a.ldrsb(3, 11, S_GHOST_C)
    a.mov_reg(0, 4); a.mov_reg(1, 5); a.mov_imm(4, 1)
    a.bl("draw_piece_on_board")

    a.label("rbi_draw_act")
    a.ldrb(4, 11, S_ACT_ID)
    a.ldrb(5, 11, S_ACT_ROT)
    a.ldrsb(6, 11, S_ACT_R)
    a.ldrsb(7, 11, S_ACT_C)
    a.mov_reg(0, 4); a.mov_reg(1, 5); a.mov_reg(2, 6); a.mov_reg(3, 7); a.mov_imm(4, 0)
    a.bl("draw_piece_on_board")

    # Save current as previous
    a.ldrb(0, 11, S_ACT_ID);    a.strb(0, 11, S_PREV_ACT_ID)
    a.ldrb(0, 11, S_ACT_ROT);   a.strb(0, 11, S_PREV_ACT_ROT)
    a.ldrb(0, 11, S_ACT_R);     a.strb(0, 11, S_PREV_ACT_R)
    a.ldrb(0, 11, S_ACT_C);     a.strb(0, 11, S_PREV_ACT_C)
    a.ldrb(0, 11, S_GHOST_R);   a.strb(0, 11, S_PREV_GHOST_R)
    a.ldrb(0, 11, S_GHOST_C);   a.strb(0, 11, S_PREV_GHOST_C)
    a.pop([4, 5, 6, 7, 15])

    # ==========================================================================
    # Subroutine: render_play_hud(R0=force_full 0/1)
    # Renders left panel (x=2..68), right panel (x=166..237: Next 3 previews),
    # top strip (y=0..6), and bottom strip (y=152..159: toast / attract caption).
    # ==========================================================================
    a.label("render_play_hud")
    a.push([4, 5, 6, 7, 8, 9, 10, 14])
    a.cmp_imm(0, 1)
    a.b("rph_do_draw", cond=a.EQ)
    a.ldrb(0, 11, S_HUD_DIRTY)
    a.cmp_imm(0, 0)
    a.b("rph_chk_toast", cond=a.EQ)

    a.label("rph_do_draw")
    a.mov_imm(0, 0)
    a.strb(0, 11, S_HUD_DIRTY)

    # Clear left panel (x=0, y=0, w=71, h=152) and right panel (x=164, y=0, w=76, h=152) and top strip (x=71, y=0, w=93, h=7)
    a.mov_imm(0, 0); a.mov_imm(1, 0); a.mov_imm(2, 71); a.mov_imm(3, 152)
    a.li32(4, rgb15(2, 3, 6))
    a.bl("fill_rect")

    a.mov_imm(0, 164); a.mov_imm(1, 0); a.mov_imm(2, 76); a.mov_imm(3, 152)
    a.li32(4, rgb15(2, 3, 6))
    a.bl("fill_rect")

    a.mov_imm(0, 71); a.mov_imm(1, 0); a.mov_imm(2, 93); a.mov_imm(3, 7)
    a.li32(4, rgb15(2, 3, 6))
    a.bl("fill_rect")

    # Left panel header: "TRYTRIS" or "ATTRACT"
    a.ldrb(0, 11, S_SCREEN)
    a.cmp_imm(0, 4)
    a.la(2, "str_attract_hdr", cond=a.EQ)
    a.la(2, "str_trytris_hdr", cond=a.NE)
    a.mov_imm(0, 4); a.mov_imm(1, 4)
    a.li32(3, rgb15(7, 23, 31))
    a.bl("draw_str6")

    # Mode badge at (4, 15)
    a.ldrb(0, 11, S_MODE)
    a.cmp_imm(0, 0); a.la(2, "str_mode_norm", cond=a.EQ); a.li32(3, rgb15(6, 31, 16), cond=a.EQ)
    a.cmp_imm(0, 1); a.la(2, "str_mode_curs", cond=a.EQ); a.li32(3, rgb15(31, 8, 12), cond=a.EQ)
    a.cmp_imm(0, 2); a.la(2, "str_mode_hexi", cond=a.EQ); a.li32(3, rgb15(31, 25, 4), cond=a.EQ)
    a.mov_imm(0, 4); a.mov_imm(1, 15)
    a.bl("draw_str6")

    # If mode == 1 (CURSED), draw "HEX INCOMING" warning at (4, 24)
    a.ldrb(0, 11, S_MODE)
    a.cmp_imm(0, 1)
    a.b("rph_score_sec", cond=a.NE)
    a.mov_imm(0, 4); a.mov_imm(1, 24); a.la(2, "str_hex_inc"); a.li32(3, rgb15(31, 12, 16))
    a.bl("draw_str6")

    a.label("rph_score_sec")
    # SCORE label & value
    a.mov_imm(0, 4); a.mov_imm(1, 36); a.la(2, "str_lbl_score"); a.li32(3, rgb15(18, 20, 24))
    a.bl("draw_str6")
    a.mov_imm(0, 4); a.mov_imm(1, 45); a.ldr(2, 11, S_SCORE); a.li32(3, rgb15(31, 31, 31))
    a.bl("draw_uint")

    # LEVEL label & value
    a.mov_imm(0, 4); a.mov_imm(1, 58); a.la(2, "str_lbl_level"); a.li32(3, rgb15(18, 20, 24))
    a.bl("draw_str6")
    a.mov_imm(0, 4); a.mov_imm(1, 67); a.ldr(2, 11, S_LEVEL); a.li32(3, rgb15(7, 28, 31))
    a.bl("draw_uint")

    # LINES label & value
    a.mov_imm(0, 4); a.mov_imm(1, 80); a.la(2, "str_lbl_lines"); a.li32(3, rgb15(18, 20, 24))
    a.bl("draw_str6")
    a.mov_imm(0, 4); a.mov_imm(1, 89); a.ldr(2, 11, S_LINES); a.li32(3, rgb15(31, 31, 31))
    a.bl("draw_uint")

    # COMBO label & multiplier string (1X, 1.5X, 2X, 2.5X, 3X)
    a.mov_imm(0, 4); a.mov_imm(1, 102); a.la(2, "str_lbl_combo"); a.li32(3, rgb15(18, 20, 24))
    a.bl("draw_str6")
    a.ldr(0, 11, S_COMBO)
    a.sub_imm(0, 0, 1)
    a.cmp_imm(0, 0); a.mov_imm(0, 0, cond=a.LT)
    a.cmp_imm(0, 4); a.mov_imm(0, 4, cond=a.GT)
    a.cmp_imm(0, 0); a.la(2, "str_cmb_10", cond=a.EQ)
    a.cmp_imm(0, 1); a.la(2, "str_cmb_15", cond=a.EQ)
    a.cmp_imm(0, 2); a.la(2, "str_cmb_20", cond=a.EQ)
    a.cmp_imm(0, 3); a.la(2, "str_cmb_25", cond=a.EQ)
    a.cmp_imm(0, 4); a.la(2, "str_cmb_30", cond=a.EQ)
    a.mov_imm(0, 4); a.mov_imm(1, 111); a.li32(3, rgb15(31, 25, 4))
    a.bl("draw_str6")

    # B2B status at (4, 123)
    a.ldrb(0, 11, S_B2B)
    a.cmp_imm(0, 0)
    a.la(2, "str_b2b_off", cond=a.EQ); a.li32(3, rgb15(12, 14, 18), cond=a.EQ)
    a.la(2, "str_b2b_on",  cond=a.NE); a.li32(3, rgb15(6, 31, 14), cond=a.NE)
    a.mov_imm(0, 4); a.mov_imm(1, 123)
    a.bl("draw_str6")

    # Status indicator at (4, 136): PAUSED / GAME OVER / GHOST:ON/OFF
    a.ldrb(0, 11, S_GAMEOVER)
    a.cmp_imm(0, 0)
    a.b("rph_chk_paused", cond=a.EQ)
    a.mov_imm(0, 4); a.mov_imm(1, 136); a.la(2, "str_gameover"); a.li32(3, rgb15(31, 6, 8))
    a.bl("draw_str6")
    a.b("rph_right_panel")

    a.label("rph_chk_paused")
    a.ldrb(0, 11, S_PAUSED)
    a.cmp_imm(0, 0)
    a.b("rph_show_ghost_lbl", cond=a.EQ)
    a.mov_imm(0, 4); a.mov_imm(1, 136); a.la(2, "str_paused"); a.li32(3, rgb15(31, 27, 4))
    a.bl("draw_str6")
    a.b("rph_right_panel")

    a.label("rph_show_ghost_lbl")
    a.ldrb(0, 11, S_GHOST)
    a.cmp_imm(0, 1)
    a.la(2, "str_ghost_on",  cond=a.EQ)
    a.la(2, "str_ghost_off", cond=a.NE)
    a.mov_imm(0, 4); a.mov_imm(1, 136); a.li32(3, rgb15(14, 18, 22))
    a.bl("draw_str6")

    a.label("rph_right_panel")
    # Right panel (x=168..236): "NEXT 3" + 3 preview boxes
    a.mov_imm(0, 168); a.mov_imm(1, 4); a.la(2, "str_next3"); a.li32(3, rgb15(7, 23, 31))
    a.bl("draw_str6")

    # Draw 3 preview slots at idx = 0, 1, 2
    a.mov_imm(8, 0)                     # idx = 0..2
    a.label("rph_prev_loop")
    # Box y = 16 + idx * 38 (w=66, h=34)
    a.mov_imm(0, 38)
    a.mul(9, 8, 0)
    a.add_imm(9, 9, 16)                 # R9 = box_y
    a.mov_imm(0, 168); a.mov_reg(1, 9); a.mov_imm(2, 66); a.mov_imm(3, 34)
    a.li32(4, rgb15(4, 5, 9))
    a.bl("fill_rect")

    # Get preview pieceId from S_BAG_BUF[idx]
    a.add_imm(0, 11, S_BAG_BUF)
    a.ldrb_reg(5, 0, 8)                 # R5 = pieceId (1..16)
    a.cmp_imm(5, 0)
    a.b("rph_prev_next", cond=a.EQ)

    # Get piece color
    a.mov_reg(0, 5); a.mov_imm(1, 0)
    a.bl("get_piece_bgr")
    a.mov_reg(10, 0)                    # R10 = color

    # Draw piece rot 0 cells using draw_mini_cell at px = 178, py = box_y + 6
    a.mov_reg(0, 5); a.mov_imm(1, 0)
    a.bl("get_rot_cell_ptr")
    a.mov_reg(6, 0)                     # cell table ptr
    a.ldrb(7, 6, 0)                     # numCells
    a.mov_imm(4, 0)                     # i = 0..numCells-1
    a.label("rph_prev_cell_loop")
    a.cmp_reg(4, 7)
    a.b("rph_prev_name", cond=a.GE)
    a.add_reg(0, 6, 4, shift_imm=1, shift_type=a.LSL)
    a.ldrb(2, 0, 4)                     # dr
    a.ldrb(3, 0, 5)                     # dc
    a.mov_imm(0, 178)
    a.add_imm(1, 9, 4)
    a.Push_R4 = None
    a.push([4])
    a.mov_reg(4, 10)
    a.bl("draw_mini_cell")
    a.pop([4])
    a.add_imm(4, 4, 1)
    a.b("rph_prev_cell_loop")

    a.label("rph_prev_name")
    # Draw short piece name at (170, box_y + 24)
    a.la(0, "piece_name_ptr_table")
    a.add_reg(0, 0, 5, shift_imm=2, shift_type=a.LSL)
    a.ldr(2, 0, 0)
    a.mov_imm(0, 170)
    a.add_imm(1, 9, 24)
    a.li32(3, rgb15(20, 22, 26))
    a.bl("draw_str6")

    a.label("rph_prev_next")
    a.add_imm(8, 8, 1)
    a.cmp_imm(8, 3)
    a.b("rph_prev_loop", cond=a.LT)

    # Below previews (y=134): show TOP SCORE for current mode
    a.mov_imm(0, 168); a.mov_imm(1, 132); a.la(2, "str_lbl_best"); a.li32(3, rgb15(18, 20, 24))
    a.bl("draw_str6")
    a.ldrb(0, 11, S_MODE)
    a.mov_imm(1, 20)
    a.mul(0, 0, 1)
    a.add_imm(1, 11, S_HIGH_SCORES)
    a.ldr_reg(2, 1, 0)                  # high_scores[mode][0]
    a.mov_imm(0, 168); a.mov_imm(1, 141); a.li32(3, rgb15(31, 27, 4))
    a.bl("draw_uint")

    a.label("rph_chk_toast")
    # Bottom strip (y=152..159, x=0..239):
    # Clear bottom strip first
    a.mov_imm(0, 0); a.mov_imm(1, 152); a.mov_imm(2, 240); a.mov_imm(3, 8)
    a.li32(4, rgb15(3, 4, 8))
    a.bl("fill_rect")

    # If in ATTRACT mode (S_SCREEN == 4), always display "Triangles are hard."
    a.ldrb(0, 11, S_SCREEN)
    a.cmp_imm(0, 4)
    a.b("rph_not_attract", cond=a.NE)
    a.mov_imm(0, 63); a.mov_imm(1, 152); a.la(2, "str_triangles_hard"); a.li32(3, rgb15(31, 27, 6))
    a.bl("draw_str6")
    a.pop([4, 5, 6, 7, 8, 9, 10, 15])

    a.label("rph_not_attract")
    # If S_TOAST_TIMER > 0, display "UNLOCKED: <Ach Name>"
    a.ldrh(0, 11, S_TOAST_TIMER)
    a.cmp_imm(0, 0)
    a.b("rph_default_footer", cond=a.EQ)
    a.mov_imm(0, 4); a.mov_imm(1, 152); a.la(2, "str_toast_prefix"); a.li32(3, rgb15(6, 31, 12))
    a.bl("draw_str6")
    a.ldrb(0, 11, S_TOAST_ACH)
    a.la(1, "ach_name_ptr_table")
    a.ldr_reg(2, 1, 0, shift_imm=2, shift_type=a.LSL)
    a.mov_imm(0, 64); a.mov_imm(1, 152); a.li32(3, rgb15(31, 31, 31))
    a.bl("draw_str6")
    a.pop([4, 5, 6, 7, 8, 9, 10, 15])

    a.label("rph_default_footer")
    # Show seed & controls hint on bottom strip
    a.mov_imm(0, 4); a.mov_imm(1, 152); a.la(2, "str_play_footer"); a.li32(3, rgb15(13, 16, 20))
    a.bl("draw_str6")
    a.pop([4, 5, 6, 7, 8, 9, 10, 15])

    # ==========================================================================
    # Subroutine: render_title_screen()
    # Draws Title Screen:
    #   - Header & emblem triangles
    #   - Row 0 (cursor=0): MODE: < NORMAL | CURSED | HEXIAMOND >
    #   - Row 1 (cursor=1): GHOST PIECE: < ON | OFF >
    #   - Row 2 (cursor=2): SEED: 0xXXXXXXXX (D-pad L/R nibble, A/B +/-1, L/R random)
    #   - Top 5 High Scores for currently selected mode
    #   - Footer: START: PLAY   SELECT: ACHIEVEMENTS
    # ==========================================================================
    a.label("render_title_screen")
    a.push([4, 5, 6, 7, 8, 9, 10, 14])
    a.ldrb(0, 11, S_DIRTY_UI)
    a.cmp_imm(0, 0)
    a.pop([4, 5, 6, 7, 8, 9, 10, 15], cond=a.EQ)
    a.mov_imm(0, 0)
    a.strb(0, 11, S_DIRTY_UI)

    # Clear full screen (240x160)
    a.mov_imm(0, 0); a.mov_imm(1, 0); a.mov_imm(2, 240); a.mov_imm(3, 160)
    a.li32(4, rgb15(2, 3, 7))
    a.bl("fill_rect")

    # Top banner box (x=8, y=6, w=224, h=26)
    a.mov_imm(0, 8); a.mov_imm(1, 6); a.mov_imm(2, 224); a.mov_imm(3, 26)
    a.li32(4, rgb15(5, 8, 16))
    a.bl("fill_rect")

    # Title text: "TRYTRIS GBA" & subtitle "CONSCIOUSNODE SOFTWORKS"
    a.mov_imm(0, 56); a.mov_imm(1, 9); a.la(2, "str_title_main"); a.li32(3, rgb15(7, 26, 31))
    a.bl("draw_str8")
    a.mov_imm(0, 51); a.mov_imm(1, 21); a.la(2, "str_title_sub"); a.li32(3, rgb15(18, 22, 28))
    a.bl("draw_str6")

    # Menu options panel (x=8, y=36, w=224, h=46)
    a.mov_imm(0, 8); a.mov_imm(1, 36); a.mov_imm(2, 224); a.mov_imm(3, 46)
    a.li32(4, rgb15(3, 5, 11))
    a.bl("fill_rect")

    a.ldrb(8, 11, S_TITLE_CURSOR)       # R8 = 0, 1, 2

    # Cursor ">" at (14, 41 + cursor * 14)
    a.mov_imm(0, 14)
    a.mul(1, 8, 0)
    a.add_imm(1, 1, 41)
    a.mov_imm(0, 14); a.mov_imm(2, ord('>')); a.li32(3, rgb15(31, 27, 4))
    a.bl("draw_char")

    # Option 0: MODE (y=41)
    a.mov_imm(0, 26); a.mov_imm(1, 41); a.la(2, "str_opt_mode"); a.li32(3, rgb15(24, 26, 30))
    a.bl("draw_str6")
    a.ldrb(0, 11, S_MODE)
    a.cmp_imm(0, 0); a.la(2, "str_mode_norm", cond=a.EQ); a.li32(3, rgb15(6, 31, 16), cond=a.EQ)
    a.cmp_imm(0, 1); a.la(2, "str_mode_curs", cond=a.EQ); a.li32(3, rgb15(31, 8, 12), cond=a.EQ)
    a.cmp_imm(0, 2); a.la(2, "str_mode_hexi", cond=a.EQ); a.li32(3, rgb15(31, 25, 4), cond=a.EQ)
    a.mov_imm(0, 92); a.mov_imm(1, 41)
    a.bl("draw_str6")

    # Option 1: GHOST PIECE (y=55)
    a.mov_imm(0, 26); a.mov_imm(1, 55); a.la(2, "str_opt_ghost"); a.li32(3, rgb15(24, 26, 30))
    a.bl("draw_str6")
    a.ldrb(0, 11, S_GHOST)
    a.cmp_imm(0, 1)
    a.la(2, "str_on",  cond=a.EQ); a.li32(3, rgb15(6, 31, 16), cond=a.EQ)
    a.la(2, "str_off", cond=a.NE); a.li32(3, rgb15(28, 10, 10), cond=a.NE)
    a.mov_imm(0, 92); a.mov_imm(1, 55)
    a.bl("draw_str6")

    # Option 2: SEED (y=69)
    a.mov_imm(0, 26); a.mov_imm(1, 69); a.la(2, "str_opt_seed"); a.li32(3, rgb15(24, 26, 30))
    a.bl("draw_str6")
    a.cmp_imm(8, 2)
    a.ldrb(4, 11, S_SEED_DIGIT, cond=a.EQ)
    a.mvn_imm(4, 0, cond=a.NE)          # R4 = highlight nibble if cursor==2 else -1
    a.mov_imm(0, 92); a.mov_imm(1, 69); a.ldr(2, 11, S_SEED); a.li32(3, rgb15(7, 26, 31))
    a.bl("draw_hex32")
    a.mov_imm(0, 146); a.mov_imm(1, 69); a.la(2, "str_seed_hint"); a.li32(3, rgb15(14, 16, 20))
    a.bl("draw_str6")

    # High Scores Box (x=8, y=86, w=224, h=58)
    a.mov_imm(0, 8); a.mov_imm(1, 86); a.mov_imm(2, 224); a.mov_imm(3, 58)
    a.li32(4, rgb15(3, 5, 11))
    a.bl("fill_rect")

    a.mov_imm(0, 16); a.mov_imm(1, 90); a.la(2, "str_hs_hdr"); a.li32(3, rgb15(31, 27, 4))
    a.bl("draw_str6")

    # Render top 5 high scores for S_MODE in two columns:
    # Col 1 (x=16): #1, #2, #3 at y=102, 114, 126
    # Col 2 (x=124): #4, #5 at y=102, 114 + ACH EARNED at y=126
    a.ldrb(0, 11, S_MODE)
    a.mov_imm(1, 20)
    a.mul(0, 0, 1)
    a.add_imm(5, 11, S_HIGH_SCORES)
    a.add_reg(5, 5, 0)                  # R5 = &high_scores[mode][0]

    a.mov_imm(6, 0)                     # i = 0..4
    a.label("rts_hs_loop")
    a.cmp_imm(6, 3)
    a.mov_imm(7, 16, cond=a.LT)         # x = 16 for 0..2
    a.mov_imm(7, 124, cond=a.GE)        # x = 124 for 3..4
    a.mov_reg(0, 6, cond=a.LT)
    a.sub_imm(0, 6, 3, cond=a.GE)
    a.mov_imm(1, 12)
    a.mul(9, 0, 1)
    a.add_imm(9, 9, 102)                # y = 102 + row * 12

    # Draw "1." .. "5."
    a.mov_reg(0, 7); a.mov_reg(1, 9)
    a.add_imm(2, 6, ord('1'))
    a.li32(3, rgb15(16, 20, 26))
    a.bl("draw_char")
    a.add_imm(0, 7, 6); a.mov_reg(1, 9); a.mov_imm(2, ord('.')); a.li32(3, rgb15(16, 20, 26))
    a.bl("draw_char")

    # Draw score value
    a.ldr_reg(2, 5, 6, shift_imm=2, shift_type=a.LSL)
    a.add_imm(0, 7, 16); a.mov_reg(1, 9); a.li32(3, rgb15(31, 31, 31))
    a.bl("draw_uint")

    a.add_imm(6, 6, 1)
    a.cmp_imm(6, 5)
    a.b("rts_hs_loop", cond=a.LT)

    # Bottom footer (y=148)
    a.mov_imm(0, 12); a.mov_imm(1, 148); a.la(2, "str_title_foot"); a.li32(3, rgb15(7, 26, 31))
    a.bl("draw_str6")
    a.pop([4, 5, 6, 7, 8, 9, 10, 15])

    # ==========================================================================
    # Subroutine: render_achievements_screen()
    # Displays all 10 named achievements (unlocked shows Name + Desc, locked shows ???)
    # Use D-pad Up/Down to scroll or view 5 per page (or all 10 compactly!).
    # Wait: can we show all 10 achievements on one screen or 5 with scroll?
    # Look: 160px height:
    #   Header: y=4..14 ("ACHIEVEMENTS (X/10) - B/SEL: BACK")
    #   10 items * 14px = 140px (y=16..155)!
    #   Each item i (0..9) at y = 16 + i * 14:
    #     Line 1 (y): "[X] Name — Desc" or "[ ] ???"
    #   Wait: at 6px per character, 232px width fits 38 characters per line!
    #   "1. Triforce: Clear 3 rows at once" is 33 characters!
    #   That means ALL 10 achievements (both name AND description!) fit on a single screen simultaneously with zero scrolling needed!
    # ==========================================================================
    a.label("render_achievements_screen")
    a.push([4, 5, 6, 7, 8, 9, 10, 14])
    a.ldrb(0, 11, S_DIRTY_UI)
    a.cmp_imm(0, 0)
    a.pop([4, 5, 6, 7, 8, 9, 10, 15], cond=a.EQ)
    a.mov_imm(0, 0)
    a.strb(0, 11, S_DIRTY_UI)

    # Clear screen
    a.mov_imm(0, 0); a.mov_imm(1, 0); a.mov_imm(2, 240); a.mov_imm(3, 160)
    a.li32(4, rgb15(2, 3, 7))
    a.bl("fill_rect")

    # Header bar
    a.mov_imm(0, 0); a.mov_imm(1, 0); a.mov_imm(2, 240); a.mov_imm(3, 14)
    a.li32(4, rgb15(5, 8, 16))
    a.bl("fill_rect")
    a.mov_imm(0, 6); a.mov_imm(1, 3); a.la(2, "str_ach_hdr"); a.li32(3, rgb15(7, 26, 31))
    a.bl("draw_str6")

    # Loop i = 0..9
    a.ldr(8, 11, S_ACH_MASK)
    a.mov_imm(9, 0)                     # i = 0..9
    a.label("ras_loop")
    a.mov_imm(0, 14)
    a.mul(10, 9, 0)
    a.add_imm(10, 10, 17)               # y = 17 + i * 14

    # Check if bit i of R8 is set
    a.mov_imm(0, 1)
    a.mov_reg_rs(0, 0, 9, shift_type=a.LSL)
    a.tst_reg(8, 0)
    a.b("ras_locked", cond=a.EQ)

    # Unlocked: draw '*' in green, then Name in green, then Desc in light gray
    a.mov_imm(0, 4); a.mov_reg(1, 10); a.mov_imm(2, ord('*')); a.li32(3, rgb15(6, 31, 12))
    a.bl("draw_char")
    a.la(0, "ach_name_ptr_table")
    a.ldr_reg(2, 0, 9, shift_imm=2, shift_type=a.LSL)
    a.mov_imm(0, 14); a.mov_reg(1, 10); a.li32(3, rgb15(6, 31, 12))
    a.bl("draw_str6")

    a.la(0, "ach_desc_ptr_table")
    a.ldr_reg(2, 0, 9, shift_imm=2, shift_type=a.LSL)
    a.mov_imm(0, 116); a.mov_reg(1, 10); a.li32(3, rgb15(24, 26, 30))
    a.bl("draw_str6")
    a.b("ras_next")

    a.label("ras_locked")
    # Locked: draw '-' in dim gray, then "???" (and also show achievement name dimmed or "???" per spec: "Locked achievements shown as '???' until earned")
    a.mov_imm(0, 4); a.mov_reg(1, 10); a.mov_imm(2, ord('-')); a.li32(3, rgb15(10, 12, 16))
    a.bl("draw_char")
    a.mov_imm(0, 14); a.mov_reg(1, 10); a.la(2, "str_ach_locked"); a.li32(3, rgb15(12, 14, 18))
    a.bl("draw_str6")

    a.label("ras_next")
    a.add_imm(9, 9, 1)
    a.cmp_imm(9, 10)
    a.b("ras_loop", cond=a.LT)

    a.pop([4, 5, 6, 7, 8, 9, 10, 15])

    # ==========================================================================
    # VBlank ISR (Registered at 0x03007FFC)
    # Checks if S_IN_FRAME == 1 (lag detection), acknowledges IF (0x04000202)
    # and BIOS_IF (0x03007FF8), and returns with BX LR.
    # ==========================================================================
    a.label("vblank_isr")
    a.mov_imm(0, STATE_BASE)
    a.ldrb(1, 0, S_IN_FRAME)
    a.cmp_imm(1, 0)
    a.ldr(2, 0, S_LAG_COUNT, cond=a.NE)
    a.add_imm(2, 2, 1, cond=a.NE)
    a.str(2, 0, S_LAG_COUNT, cond=a.NE)

    a.li32(0, 0x04000200)
    a.ldrh(1, 0, 0x02)                  # REG_IF
    a.strh(1, 0, 0x02)                  # Acknowledge IF

    a.li32(2, 0x03007FF8)               # REG_BIOS_IF
    a.ldrh(3, 2, 0)
    a.orr_reg(3, 3, 1)
    a.strh(3, 2, 0)
    a.bx(14)

    # ==========================================================================
    # Subroutine: step_frame_logic()
    # Reads keys, updates timers, dispatches active screen state, steps music,
    # renders screen, and writes Mailbox!
    # ==========================================================================
    a.label("step_frame_logic")
    a.push([4, 5, 6, 7, 8, 9, 10, 14])

    # Increment frame counter
    a.ldr(0, 11, S_FRAME)
    a.add_imm(0, 0, 1)
    a.str(0, 11, S_FRAME)

    # Decrement toast timer if > 0
    a.ldrh(0, 11, S_TOAST_TIMER)
    a.cmp_imm(0, 0)
    a.b("sfl_read_keys", cond=a.EQ)
    a.sub_imm(0, 0, 1, s=1)
    a.strh(0, 11, S_TOAST_TIMER)
    a.mov_imm(1, 1, cond=a.EQ)
    a.strb(1, 11, S_HUD_DIRTY, cond=a.EQ)

    a.label("sfl_read_keys")
    # Read REG_KEYINPUT (0x04000130, active-low) -> invert & 0x3FF
    a.li32(0, 0x04000130)
    a.ldrh(1, 0, 0)
    a.mvn_reg(1, 1)
    a.li32(2, 0x03FF)
    a.and_reg(4, 1, 2)                  # R4 = curr_keys (active-high)
    a.ldrh(5, 11, S_KEY_CURR)           # R5 = prev_keys
    a.strh(5, 11, S_KEY_PREV)
    a.strh(4, 11, S_KEY_CURR)
    a.bic_reg(6, 4, 5)                  # R6 = down_keys = curr & ~prev
    a.strh(6, 11, S_KEY_DOWN)

    # Default S_ACCEPT_INPUT = 0 (set to 1 in PLAY when not paused and not gameOver)
    a.mov_imm(0, 0)
    a.strb(0, 11, S_ACCEPT_INPUT)

    # Dispatch on S_SCREEN: 0=TITLE, 1=PLAY, 3=ACHIEVEMENTS, 4=ATTRACT
    a.ldrb(0, 11, S_SCREEN)
    a.cmp_imm(0, 0)
    a.b("sfl_screen_title", cond=a.EQ)
    a.cmp_imm(0, 1)
    a.b("sfl_screen_play", cond=a.EQ)
    a.cmp_imm(0, 3)
    a.b("sfl_screen_ach", cond=a.EQ)
    a.b("sfl_screen_attract")

    # --------------------------------------------------------------------------
    # SCREEN 0: TITLE SCREEN
    # --------------------------------------------------------------------------
    a.label("sfl_screen_title")
    # Check if any key is held or newly pressed
    a.cmp_imm(4, 0)
    a.mov_imm(0, 0, cond=a.NE)
    a.strh(0, 11, S_TITLE_IDLE, cond=a.NE)
    a.b("sfl_title_keys", cond=a.NE)

    # No key pressed: increment S_TITLE_IDLE; if >= 597 (10.0s), enter ATTRACT mode!
    a.ldrh(4, 11, S_TITLE_IDLE)
    a.add_imm(4, 4, 1)
    a.strh(4, 11, S_TITLE_IDLE)
    a.li32(1, 597)
    a.cmp_reg(4, 1)
    a.b("sfl_title_render", cond=a.LT)

    # Start ATTRACT mode (S_SCREEN = 4)
    a.mov_imm(0, 4)
    a.strb(0, 11, S_SCREEN)
    a.mov_imm(0, 1)
    a.strb(0, 11, S_ATTRACT_GAMES)
    a.mov_imm(0, 0)
    a.strh(0, 11, S_ATTRACT_WAIT)
    a.strb(0, 11, S_BOT_TICK_DIV)
    # Seed from S_SEED, mode from S_ATTRACT_MODE_IX (0=NORMAL, 1=CURSED)
    a.ldr(0, 11, S_SEED)
    a.ldrb(1, 11, S_ATTRACT_MODE_IX)
    a.bl("eng_reset")
    a.bl("bot_make_plan")
    a.mov_imm(0, 1)
    a.bl("render_play_hud")
    a.mov_imm(0, 1)
    a.strb(0, 11, S_BOARD_DIRTY)
    a.b("sfl_finish")

    a.label("sfl_title_keys")
    # Check SELECT (bit 2 = 0x004) -> go to ACHIEVEMENTS screen (S_SCREEN = 3)
    a.tst_imm(6, 0x004)
    a.b("sfl_title_chk_start", cond=a.EQ)
    a.mov_imm(0, 3)
    a.strb(0, 11, S_SCREEN)
    a.mov_imm(0, 1)
    a.strb(0, 11, S_DIRTY_UI)
    a.bl("render_achievements_screen")
    a.b("sfl_finish")

    a.label("sfl_title_chk_start")
    # Check START (bit 3 = 0x008) -> start PLAY game (S_SCREEN = 1)
    a.tst_imm(6, 0x008)
    a.b("sfl_title_nav", cond=a.EQ)
    a.mov_imm(0, 1)
    a.strb(0, 11, S_SCREEN)
    a.strb(0, 11, S_ACCEPT_INPUT)
    a.ldr(0, 11, S_SEED)
    a.ldrb(1, 11, S_MODE)
    a.bl("eng_reset")
    a.mov_imm(0, 1)
    a.bl("render_play_hud")
    a.bl("render_board_incremental")
    a.b("sfl_finish")

    a.label("sfl_title_nav")
    # Up (0x040) / Down (0x080) moves S_TITLE_CURSOR (0..2)
    a.ldrb(7, 11, S_TITLE_CURSOR)
    a.tst_imm(6, 0x040)                 # UP
    a.sub_imm(7, 7, 1, cond=a.NE)
    a.cmp_imm(7, 0)
    a.mov_imm(7, 2, cond=a.LT)
    a.tst_imm(6, 0x080)                 # DOWN
    a.add_imm(7, 7, 1, cond=a.NE)
    a.cmp_imm(7, 2)
    a.mov_imm(7, 0, cond=a.GT)
    a.strb(7, 11, S_TITLE_CURSOR)

    # L (0x200) or R (0x100) randomizes seed from frame_counter * 0x6D2B79F5 + 1
    a.tst_imm(6, 0x300)
    a.b("sfl_title_opt_act", cond=a.EQ)
    a.ldr(0, 11, S_FRAME)
    a.ldr(1, 11, S_SEED)
    a.eor_reg(0, 0, 1)
    a.li32(1, 0x6D2B79F5)
    a.mul(0, 0, 1)
    a.add_imm(0, 0, 1)
    a.str(0, 11, S_SEED)

    a.label("sfl_title_opt_act")
    # Act on current cursor row (R7 = 0, 1, 2)
    a.cmp_imm(7, 0)
    a.b("sfl_title_opt1", cond=a.NE)
    # Row 0 (MODE): Left (0x020) / B (0x002) -> -1; Right (0x010) / A (0x001) -> +1
    a.ldrb(0, 11, S_MODE)
    a.tst_imm(6, 0x022)
    a.sub_imm(0, 0, 1, cond=a.NE)
    a.cmp_imm(0, 0)
    a.mov_imm(0, 2, cond=a.LT)
    a.tst_imm(6, 0x011)
    a.add_imm(0, 0, 1, cond=a.NE)
    a.cmp_imm(0, 2)
    a.mov_imm(0, 0, cond=a.GT)
    a.strb(0, 11, S_MODE)
    a.b("sfl_title_mark_dirty")

    a.label("sfl_title_opt1")
    a.cmp_imm(7, 1)
    a.b("sfl_title_opt2", cond=a.NE)
    # Row 1 (GHOST): Left/Right/A/B (0x033) toggles 0 <-> 1
    a.tst_imm(6, 0x033)
    a.ldrb(0, 11, S_GHOST, cond=a.NE)
    a.eor_imm(0, 0, 1, cond=a.NE)
    a.strb(0, 11, S_GHOST, cond=a.NE)
    a.b("sfl_title_mark_dirty")

    a.label("sfl_title_opt2")
    # Row 2 (SEED): Left (0x020) / Right (0x010) selects nibble 0..7; A (0x001) +1 nibble, B (0x002) -1 nibble
    a.ldrb(0, 11, S_SEED_DIGIT)
    a.tst_imm(6, 0x020)
    a.sub_imm(0, 0, 1, cond=a.NE)
    a.and_imm(0, 0, 7)
    a.tst_imm(6, 0x010)
    a.add_imm(0, 0, 1, cond=a.NE)
    a.and_imm(0, 0, 7)
    a.strb(0, 11, S_SEED_DIGIT)

    a.tst_imm(6, 0x003)                 # A or B pressed?
    a.b("sfl_title_mark_dirty", cond=a.EQ)
    a.rsb_imm(1, 0, 7)
    a.mov_reg(1, 1, shift_imm=2, shift_type=a.LSL) # shift = (7 - digit) * 4
    a.ldr(2, 11, S_SEED)
    a.mov_reg_rs(3, 2, 1, shift_type=a.LSR)
    a.and_imm(3, 3, 0xF)
    a.tst_imm(6, 0x001)                 # A -> +1
    a.add_imm(3, 3, 1, cond=a.NE)
    a.tst_imm(6, 0x002)                 # B -> -1
    a.sub_imm(3, 3, 1, cond=a.NE)
    a.and_imm(3, 3, 0xF)
    a.mov_imm(8, 0xF)
    a.mov_reg_rs(8, 8, 1, shift_type=a.LSL)
    a.bic_reg(2, 2, 8)
    a.mov_reg_rs(3, 3, 1, shift_type=a.LSL)
    a.orr_reg(2, 2, 3)
    a.str(2, 11, S_SEED)

    a.label("sfl_title_mark_dirty")
    a.cmp_imm(6, 0)
    a.mov_imm(0, 1, cond=a.NE)
    a.strb(0, 11, S_DIRTY_UI, cond=a.NE)

    a.label("sfl_title_render")
    a.bl("render_title_screen")
    a.b("sfl_finish")

    # --------------------------------------------------------------------------
    # SCREEN 3: ACHIEVEMENTS SCREEN
    # --------------------------------------------------------------------------
    a.label("sfl_screen_ach")
    # B (0x002), SELECT (0x004), or START (0x008) returns to TITLE (S_SCREEN = 0)
    a.tst_imm(6, 0x00E)
    a.b("sfl_ach_render", cond=a.EQ)
    a.mov_imm(0, 0)
    a.strb(0, 11, S_SCREEN)
    a.strh(0, 11, S_TITLE_IDLE)
    a.mov_imm(0, 1)
    a.strb(0, 11, S_DIRTY_UI)
    a.bl("render_title_screen")
    a.b("sfl_finish")

    a.label("sfl_ach_render")
    a.bl("render_achievements_screen")
    a.b("sfl_finish")

    # --------------------------------------------------------------------------
    # SCREEN 4: ATTRACT MODE (Porch Toys Bot alternating NORMAL & CURSED)
    # --------------------------------------------------------------------------
    a.label("sfl_screen_attract")
    # Any newly pressed button (R6 != 0) returns to TITLE screen!
    a.cmp_imm(6, 0)
    a.b("sfl_attract_step", cond=a.EQ)
    a.mov_imm(0, 0)
    a.strb(0, 11, S_SCREEN)
    a.strh(0, 11, S_TITLE_IDLE)
    a.mov_imm(0, 1)
    a.strb(0, 11, S_DIRTY_UI)
    a.bl("render_title_screen")
    a.b("sfl_finish")

    a.label("sfl_attract_step")
    # Check if gameOver in attract mode
    a.ldrb(0, 11, S_GAMEOVER)
    a.cmp_imm(0, 0)
    a.b("sfl_attract_live", cond=a.EQ)

    # Wait 60 frames after gameOver, then alternate modeIx (0 <-> 1) and start new attract game
    a.ldrh(0, 11, S_ATTRACT_WAIT)
    a.add_imm(0, 0, 1)
    a.strh(0, 11, S_ATTRACT_WAIT)
    a.cmp_imm(0, 60)
    a.b("sfl_attract_render", cond=a.LT)

    a.mov_imm(0, 0)
    a.strh(0, 11, S_ATTRACT_WAIT)
    a.ldrb(0, 11, S_ATTRACT_GAMES)
    a.add_imm(0, 0, 1)
    a.strb(0, 11, S_ATTRACT_GAMES)
    a.ldrb(1, 11, S_ATTRACT_MODE_IX)
    a.eor_imm(1, 1, 1)                  # alternate 0 (NORMAL) <-> 1 (CURSED)
    a.strb(1, 11, S_ATTRACT_MODE_IX)
    # Advance seed deterministically
    a.ldr(0, 11, S_SEED)
    a.add_imm(0, 0, 1)
    a.bl("eng_reset")
    a.bl("bot_make_plan")
    a.b("sfl_attract_render")

    a.label("sfl_attract_live")
    # Step bot every 4 frames (matching Porch Toys ~70ms step rate at 60fps)
    a.ldrb(0, 11, S_BOT_TICK_DIV)
    a.add_imm(0, 0, 1)
    a.cmp_imm(0, 4)
    a.strb(0, 11, S_BOT_TICK_DIV, cond=a.LT)
    a.b("sfl_attract_render", cond=a.LT)

    a.mov_imm(0, 0)
    a.strb(0, 11, S_BOT_TICK_DIV)

    # Save current S_BOT_PIECE_SEQ before tick
    a.ldrb(8, 11, S_BOT_PIECE_SEQ)

    # Pop next action from S_BOT_PLAN_BUF if S_BOT_PLAN_POS < S_BOT_PLAN_LEN, else 0 (null)
    a.ldrb(0, 11, S_BOT_PLAN_POS)
    a.ldrb(1, 11, S_BOT_PLAN_LEN)
    a.cmp_reg(0, 1)
    a.mov_imm(2, 0, cond=a.GE)
    a.b("sfl_attract_do_tick", cond=a.GE)
    a.add_imm(3, 11, S_BOT_PLAN_BUF)
    a.ldrb_reg(2, 3, 0)                 # action code
    a.add_imm(0, 0, 1)
    a.strb(0, 11, S_BOT_PLAN_POS)

    a.label("sfl_attract_do_tick")
    a.mov_reg(0, 2)
    a.bl("eng_tick")

    # If a new piece spawned (S_BOT_PIECE_SEQ != R8) and not gameOver, compute bot_make_plan() immediately!
    a.ldrb(0, 11, S_GAMEOVER)
    a.cmp_imm(0, 0)
    a.b("sfl_attract_render", cond=a.NE)
    a.ldrb(0, 11, S_BOT_PIECE_SEQ)
    a.cmp_reg(0, 8)
    a.bl("bot_make_plan", cond=a.NE)

    a.label("sfl_attract_render")
    a.mov_imm(0, 0)
    a.bl("render_play_hud")
    a.bl("render_board_incremental")
    a.b("sfl_finish")

    # --------------------------------------------------------------------------
    # SCREEN 1: LIVE PLAY SCREEN
    # --------------------------------------------------------------------------
    a.label("sfl_screen_play")
    # Check if gameOver
    a.ldrb(0, 11, S_GAMEOVER)
    a.cmp_imm(0, 0)
    a.b("sfl_play_not_over", cond=a.EQ)

    # Game Over state: START (0x008) restarts same seed/mode; SELECT (0x004) returns to TITLE
    a.tst_imm(6, 0x004)
    a.b("sfl_go_chk_start", cond=a.EQ)
    a.mov_imm(0, 0)
    a.strb(0, 11, S_SCREEN)
    a.strh(0, 11, S_TITLE_IDLE)
    a.mov_imm(0, 1)
    a.strb(0, 11, S_DIRTY_UI)
    a.bl("render_title_screen")
    a.b("sfl_finish")

    a.label("sfl_go_chk_start")
    a.tst_imm(6, 0x008)
    a.b("sfl_play_render", cond=a.EQ)
    a.ldr(0, 11, S_SEED)
    a.ldrb(1, 11, S_MODE)
    a.bl("eng_reset")
    a.mov_imm(0, 1)
    a.strb(0, 11, S_ACCEPT_INPUT)
    a.b("sfl_play_render")

    a.label("sfl_play_not_over")
    # Check START (0x008) to toggle pause
    a.tst_imm(6, 0x008)
    a.b("sfl_play_chk_paused", cond=a.EQ)
    a.ldrb(0, 11, S_PAUSED)
    a.eor_imm(0, 0, 1)
    a.strb(0, 11, S_PAUSED)
    a.mov_imm(1, 1)
    a.strb(1, 11, S_HUD_DIRTY)
    # If now paused, S_ACCEPT_INPUT = 0; if unpaused, S_ACCEPT_INPUT = 1
    a.eor_imm(0, 0, 1)
    a.strb(0, 11, S_ACCEPT_INPUT)
    a.b("sfl_play_render")

    a.label("sfl_play_chk_paused")
    a.ldrb(0, 11, S_PAUSED)
    a.cmp_imm(0, 0)
    a.b("sfl_play_active", cond=a.EQ)
    # While paused: SELECT (0x004) returns to TITLE screen
    a.tst_imm(6, 0x004)
    a.b("sfl_play_render", cond=a.EQ)
    a.mov_imm(0, 0)
    a.strb(0, 11, S_PAUSED)
    a.strb(0, 11, S_SCREEN)
    a.strh(0, 11, S_TITLE_IDLE)
    a.mov_imm(0, 1)
    a.strb(0, 11, S_DIRTY_UI)
    a.bl("render_title_screen")
    a.b("sfl_finish")

    a.label("sfl_play_active")
    # Active play! Set S_ACCEPT_INPUT = 1
    a.mov_imm(0, 1)
    a.strb(0, 11, S_ACCEPT_INPUT)

    # Increment S_IDLE_FRAMES by 1 (any player input below resets S_IDLE_FRAMES to 0)
    a.ldr(0, 11, S_IDLE_FRAMES)
    a.add_imm(0, 0, 1)
    a.str(0, 11, S_IDLE_FRAMES)

    # 1. Left / Right with DAS (Delayed Auto-Shift: initial delay = 14 frames, repeat period = 4 frames)
    # Check if Left (0x020) or Right (0x010) is newly pressed:
    a.tst_imm(6, 0x010 if swap_lr else 0x020) # LEFT newly pressed?
    a.b("sfl_chk_right_down", cond=a.EQ)
    a.mvn_imm(0, 0)                     # dir = -1
    a.strb(0, 11, S_DAS_DIR)
    a.mov_imm(0, 0)
    a.strb(0, 11, S_DAS_TIMER)
    a.mvn_imm(0, 0)
    a.bl("eng_move_horizontal")
    a.b("sfl_after_horiz")

    a.label("sfl_chk_right_down")
    a.tst_imm(6, 0x020 if swap_lr else 0x010) # RIGHT newly pressed?
    a.b("sfl_chk_horiz_held", cond=a.EQ)
    a.mov_imm(0, 1)                     # dir = +1
    a.strb(0, 11, S_DAS_DIR)
    a.mov_imm(0, 0)
    a.strb(0, 11, S_DAS_TIMER)
    a.mov_imm(0, 1)
    a.bl("eng_move_horizontal")
    a.b("sfl_after_horiz")

    a.label("sfl_chk_horiz_held")
    # Neither newly pressed: check if current S_DAS_DIR key is still held in R4 (curr_keys)
    a.ldrsb(0, 11, S_DAS_DIR)
    a.cmp_imm(0, 0)
    a.b("sfl_after_horiz", cond=a.EQ)
    a.cmp_imm(0, 1)
    a.b("sfl_das_chk_left", cond=a.NE)
    a.tst_imm(4, 0x020 if swap_lr else 0x010)            # dir==+1: test RIGHT
    a.b("sfl_das_test_done")
    a.label("sfl_das_chk_left")
    a.tst_imm(4, 0x010 if swap_lr else 0x020)            # dir==-1: test LEFT
    a.label("sfl_das_test_done")
    a.mov_imm(1, 0, cond=a.EQ)
    a.strb(1, 11, S_DAS_DIR, cond=a.EQ)
    a.strb(1, 11, S_DAS_TIMER, cond=a.EQ)
    a.b("sfl_after_horiz", cond=a.EQ)

    # Key is still held: increment S_DAS_TIMER
    a.ldrb(1, 11, S_DAS_TIMER)
    a.add_imm(1, 1, 1)
    a.cmp_imm(1, 14)                    # DAS initial delay = 14 frames
    a.strb(1, 11, S_DAS_TIMER, cond=a.LT)
    a.b("sfl_after_horiz", cond=a.LT)
    # Reached 14: reset timer to 14 - 4 = 10 (so it fires every 4 frames: 14, 18, 22, ...)
    a.mov_imm(1, 10)
    a.strb(1, 11, S_DAS_TIMER)
    a.bl("eng_move_horizontal")

    a.label("sfl_after_horiz")
    # 2. A (0x001): Rotate CW (+1) on new press
    a.tst_imm(6, 0x001)
    a.mov_imm(0, 1, cond=a.NE)
    a.bl("eng_rotate", cond=a.NE)

    # 3. B (0x002): Rotate CCW (-1) on new press
    a.tst_imm(6, 0x002)
    a.mvn_imm(0, 0, cond=a.NE)
    a.bl("eng_rotate", cond=a.NE)

    # 4. Down (0x080): Soft drop on new press
    a.tst_imm(6, 0x080)
    a.bl("eng_soft_drop", cond=a.NE)

    # 5. Up (0x040): Hard drop on new press
    a.tst_imm(6, 0x040)
    a.bl("eng_hard_drop", cond=a.NE)

    # 6. Whole-frame Gravity timer:
    # Look up threshold = GRAVITY_FRAMES[level]
    a.ldrb(0, 11, S_GAMEOVER)
    a.cmp_imm(0, 0)
    a.b("sfl_play_render", cond=a.NE)

    a.ldr(0, 11, S_GRAV_TIMER)
    a.add_imm(0, 0, 1)
    a.str(0, 11, S_GRAV_TIMER)

    a.ldr(1, 11, S_LEVEL)
    a.la(2, "gravity_frames_table")
    a.ldrb_reg(2, 2, 1)                 # R2 = frames for current level
    a.cmp_reg(0, 2)
    a.b("sfl_play_render", cond=a.LT)

    # Gravity fires! Reset S_GRAV_TIMER = 0 and call eng_tick(0)
    a.mov_imm(0, 0)
    a.str(0, 11, S_GRAV_TIMER)
    a.mov_imm(0, 0)
    a.bl("eng_tick")

    a.label("sfl_play_render")
    a.mov_imm(0, 0)
    a.bl("render_play_hud")
    a.bl("render_board_incremental")

    a.label("sfl_finish")
    a.bl("music_step")
    a.bl("write_mailbox")
    a.pop([4, 5, 6, 7, 8, 9, 10, 15])

# Module 4: ROM Header, Boot Copy to IWRAM (0x03001000), Main Loop, and Data Tables


def build_trytris_rom(swap_lr=False, bad_cell_offset=False):
    """
    Assembles the complete Trytris GBA ROM byte-for-byte.
    Boot header at 0x08000000..0x080001FF copies the game engine & tables
    from 0x08000200 into 32-bit zero-wait-state IWRAM at 0x03001000 and branches
    to 0x03001000, ensuring zero lag frames across all modes and bot plans.
    """
    # 1. Assemble IWRAM payload at base 0x03001000
    a = ArmBuilder(0x03001000)

    a.label("iwram_entry")
    # Clear IWRAM state region (0x03000000..0x030007FF = 2048 bytes = 512 words)
    a.mov_imm(0, STATE_BASE)
    a.mov_imm(1, 0)
    a.mov_imm(2, 512)
    a.label("init_clr_iwram")
    a.str(1, 0, 4, p=0)
    a.sub_imm(2, 2, 1, s=1)
    a.b("init_clr_iwram", cond=a.NE)

    # Clear EWRAM Mailbox (0x0203FC00..0x0203FFFF = 1024 bytes = 256 words)
    a.li32(0, MB_BASE)
    a.mov_imm(1, 0)
    a.mov_imm(2, 256)
    a.label("init_clr_mb")
    a.str(1, 0, 4, p=0)
    a.sub_imm(2, 2, 1, s=1)
    a.b("init_clr_mb", cond=a.NE)

    # Configure WAITCNT (0x04000204) = 0x4317 (Prefetch buffer enabled, fast WS0)
    a.li32(2, 0x04000200)
    a.li32(1, 0x4317)
    a.strh(1, 2, 0x04)

    # Configure Mode 3 + BG2_ENABLE on REG_DISPCNT (0x04000000 = 0x0403)
    a.mov_imm(0, IO_BASE)
    a.li32(1, 0x0403)
    a.strh(1, 0, 0x000)

    # Install VBlank ISR at 0x03007FFC and enable VBlank IRQ
    a.la(1, "vblank_isr")
    a.li32(2, 0x03007FFC)
    a.str(1, 2, 0)
    a.mov_imm(1, 0x0008)                    # DISPSTAT VBlank IRQ enable
    a.strh(1, 0, 0x004)
    a.mov_imm(1, 0x0001)                    # IE = IRQ_VBLANK
    a.li32(2, 0x04000200)
    a.strh(1, 2, 0x00)                      # REG_IE = 1
    a.strh(1, 2, 0x08)                      # REG_IME = 1

    # Initialize PSG sound hardware
    a.bl("sound_init")

    # Load or initialize SRAM high scores & achievements
    a.bl("sram_load_or_init")

    # Initialize default Title state:
    # S_SCREEN = 0 (TITLE), S_MODE = 0 (NORMAL), S_GHOST = 1 (ON), S_SEED = 42 (0x0000002A)
    a.mov_imm(0, 0)
    a.strb(0, 11, S_SCREEN)
    a.strb(0, 11, S_MODE)
    a.mov_imm(0, 1)
    a.strb(0, 11, S_GHOST)
    a.strb(0, 11, S_DIRTY_UI)
    a.mov_imm(0, 42)
    a.str(0, 11, S_SEED)

    # Initialize underlying engine state for seed 42, mode NORMAL
    a.mov_imm(0, 42)
    a.mov_imm(1, 0)
    a.bl("eng_reset")
    a.mov_imm(0, 1)
    a.strb(0, 11, S_DIRTY_UI)

    # Write initial mailbox immediately (render_title_screen runs on frame 1 inside main_loop)
    a.bl("write_mailbox")

    # ==========================================================================
    # Main VBlank-Synchronized Loop (1 game frame per VBlank, 59.73 Hz)
    # Only BIOS call used anywhere in ROM: SWI 0x05 (VBlankIntrWait)
    # ==========================================================================
    a.label("main_loop")
    a.mov_imm(0, 0)
    a.strb(0, 11, S_IN_FRAME)
    a.swi(0x05)                             # VBlankIntrWait (SWI 0x05)
    a.mov_imm(0, 1)
    a.strb(0, 11, S_IN_FRAME)
    a.bl("step_frame_logic")
    a.b("main_loop")

    # Emit all engine and UI subroutines
    emit_engine_subroutines(a)
    emit_system_and_ui_subroutines(a, swap_lr=swap_lr, bad_cell_offset=bad_cell_offset)

    # ==========================================================================
    # Read-Only Data Tables (Aligned, Zero Accidental SWI Patterns)
    # ==========================================================================
    a.align(4)
    a.label("kick_table")
    kicks = [(0, 0), (0, 2), (0, -2), (1, 1), (1, -1), (-1, 1), (-1, -1), (2, 0)]
    for dr, dc in kicks:
        a.emit8(dr & 0xFF)
        a.emit8(dc & 0xFF)

    a.align(4)
    a.label("gravity_frames_table")
    for f_cnt in GRAVITY_FRAMES:
        a.emit8(f_cnt)
    a.align(4)

    a.label("piece_color_table")
    a.emit32(0)
    for p in RAW_PIECES:
        a.emit32(p["bgr"])

    a.label("piece_ghost_color_table")
    a.emit32(0)
    for p in RAW_PIECES:
        a.emit32(p["ghost_bgr"])

    a.label("rot_mask_table")
    mask_table = bytearray(17 * 6 * 16)
    for p in RAW_PIECES:
        p_idx = p["idx"]
        for rot in range(6):
            off = (p_idx * 6 + rot) * 16
            if rot < p["sym"]:
                cells = p["rotations"][rot]
                masks = [0, 0, 0, 0]
                max_dr = 0
                max_dc = 0
                for dr, dc in cells:
                    masks[dr] |= (1 << dc)
                    if dr > max_dr: max_dr = dr
                    if dc > max_dc: max_dc = dc
                min_dc = min(dc for dr, dc in cells)
                struct.pack_into("<HHHHBBBBBBBB", mask_table, off,
                                 masks[0], masks[1], masks[2], masks[3],
                                 max_dr, max_dc, p["sym"], 1 if p["order"] == 6 else 0,
                                 len(cells), min_dc, 0, 0)
    a.emit_bytes(mask_table)

    a.label("rot_cell_table")
    cell_table = bytearray(17 * 6 * 16)
    for p in RAW_PIECES:
        p_idx = p["idx"]
        for rot in range(6):
            off = (p_idx * 6 + rot) * 16
            if rot < p["sym"]:
                cells = p["rotations"][rot]
                cell_table[off + 0] = len(cells)
                cell_table[off + 1] = p["sym"]
                cell_table[off + 2] = 1 if p["order"] == 6 else 0
                cell_table[off + 3] = 0
                for ci, (dr, dc) in enumerate(cells):
                    cell_table[off + 4 + ci * 2] = dr
                    cell_table[off + 5 + ci * 2] = dc
    a.emit_bytes(cell_table)

    a.align(4)
    a.label("music_title_table")
    title_notes = [
        (1750, 1452), (1798, 1452), (1849, 1547), (1899, 1547),
        (1881, 1379), (1849, 1379), (1798, 1253), (1714, 1253),
        (1673, 1297), (1750, 1297), (1798, 1547), (1849, 1547),
        (1825, 1155), (1783, 1155), (1750, 1452), (   0, 1452),
        (1750, 1452), (1849, 1452), (1899, 1650), (1923, 1650),
        (1899, 1297), (1860, 1297), (1849, 1547), (1798, 1547),
        (1783, 1379), (1825, 1379), (1881, 1517), (1849, 1517),
        (1750, 1452), (1650, 1253), (1750, 1452), (   0,    0),
    ]
    for f2, f3 in title_notes:
        a.emit16(f2); a.emit16(f3)

    a.label("music_play_table")
    play_notes = [
        (1849, 1452), (1783, 1650), (1798, 1452), (1825, 1650),
        (1798, 1547), (1783, 1650), (1750, 1452), (1750, 1253),
        (1798, 1547), (1849, 1714), (1899, 1547), (1881, 1714),
        (1849, 1650), (1798, 1547), (1825, 1155), (1783, 1379),
        (1825, 1155), (1860, 1673), (1899, 1750), (1899, 1452),
        (1881, 1379), (1860, 1673), (1849, 1650), (1798, 1547),
        (1849, 1650), (1798, 1547), (1783, 1517), (1714, 1379),
        (1750, 1452), (1650, 1253), (1750, 1452), (   0, 1452),
    ]
    for f2, f3 in play_notes:
        a.emit16(f2); a.emit16(f3)

    def emit_cstr(lbl, s):
        a.align(4)
        a.label(lbl)
        for ch in s:
            a.emit16(ord(ch))
        a.emit16(0)
        a.align(4)

    emit_cstr("str_title_main",     "TRYTRIS GBA")
    emit_cstr("str_title_sub",      "CONSCIOUSNODE SOFTWORKS")
    emit_cstr("str_opt_mode",       "MODE:")
    emit_cstr("str_opt_ghost",      "GHOST:")
    emit_cstr("str_opt_seed",       "SEED:")
    emit_cstr("str_seed_hint",      "(L/R:RAND)")
    emit_cstr("str_hs_hdr",         "TOP 5 HIGH SCORES")
    emit_cstr("str_title_foot",     "START:PLAY  SELECT:ACHIEVEMENTS")
    emit_cstr("str_mode_norm",      "NORMAL")
    emit_cstr("str_mode_curs",      "CURSED")
    emit_cstr("str_mode_hexi",      "HEXIAMOND")
    emit_cstr("str_on",             "ON")
    emit_cstr("str_off",            "OFF")
    emit_cstr("str_trytris_hdr",    "TRYTRIS")
    emit_cstr("str_attract_hdr",    "ATTRACT")
    emit_cstr("str_hex_inc",        "HEX INCOMING")
    emit_cstr("str_lbl_score",      "SCORE")
    emit_cstr("str_lbl_level",      "LEVEL")
    emit_cstr("str_lbl_lines",      "LINES")
    emit_cstr("str_lbl_combo",      "COMBO")
    emit_cstr("str_cmb_10",         "1X")
    emit_cstr("str_cmb_15",         "1.5X")
    emit_cstr("str_cmb_20",         "2X")
    emit_cstr("str_cmb_25",         "2.5X")
    emit_cstr("str_cmb_30",         "3X")
    emit_cstr("str_b2b_off",        "B2B:IDLE")
    emit_cstr("str_b2b_on",         "B2B:1.5X")
    emit_cstr("str_gameover",       "GAME OVER")
    emit_cstr("str_paused",         "PAUSED")
    emit_cstr("str_ghost_on",       "GHOST:ON")
    emit_cstr("str_ghost_off",      "GHOST:OFF")
    emit_cstr("str_next3",          "NEXT 3")
    emit_cstr("str_lbl_best",       "BEST")
    emit_cstr("str_triangles_hard", "Triangles are hard.")
    emit_cstr("str_toast_prefix",   "UNLOCKED:")
    emit_cstr("str_play_footer",    "A/B:ROT  U:HARD  D:SOFT  ST:PAUSE")
    emit_cstr("str_ach_hdr",        "ACHIEVEMENTS (B/SELECT: BACK)")
    emit_cstr("str_ach_locked",     "???")

    emit_cstr("str_p0", "")
    for p in RAW_PIECES:
        short_name = p["id"] if p["order"] == 4 else p["name"][:10]
        emit_cstr(f"str_p{p['idx']}", short_name)

    for idx, (aname, adesc) in enumerate(ACHIEVEMENT_DEFS):
        emit_cstr(f"str_ach_n{idx}", aname)
        emit_cstr(f"str_ach_d{idx}", adesc[:20])

    a.align(4)
    a.label("font_table")
    for code_pt in range(32, 127):
        glyph = list(FONT_8X8.get(chr(code_pt), [0]*8))
        if (glyph[3] & 0x0F) == 0x0F:
            glyph[3] &= 0xFE
        if (glyph[7] & 0x0F) == 0x0F:
            glyph[7] &= 0xFE
        a.emit_bytes(bytes(glyph))

    a.align(4)
    a.label("piece_name_ptr_table")
    for idx in range(17):
        a.emit32(a.labels[f"str_p{idx}"])

    a.label("ach_name_ptr_table")
    for idx in range(10):
        a.emit32(a.labels[f"str_ach_n{idx}"])

    a.label("ach_desc_ptr_table")
    for idx in range(10):
        a.emit32(a.labels[f"str_ach_d{idx}"])

    a.align(16)
    a.resolve()
    payload_bytes = bytes(a.code)
    payload_words = len(payload_bytes) // 4

    # 2. Assemble ROM Header & IWRAM Copy Stub at 0x08000000..0x080001FF
    boot = ArmBuilder(0x08000000)
    boot.b("rom_boot")                      # 0x00..0x03
    boot.emit_bytes(NINTENDO_LOGO)          # 0x04..0x9F
    boot.emit_bytes(b"TRYTRIS GBA ")        # 0xA0..0xAB
    boot.emit_bytes(b"BTRE")                # 0xAC..0xAF
    boot.emit_bytes(b"CN")                  # 0xB0..0xB1
    boot.emit_bytes(b"\x96\x00\x00")        # 0xB2..0xB4
    boot.emit_bytes(b"\x00" * 7)            # 0xB5..0xBB
    boot.emit_bytes(b"\x01\x00\x00\x00")    # 0xBC..0xBF

    chk = 0
    for b in boot.code[0xA0:0xBD]:
        chk = (chk - b) & 0xFF
    chk = (chk - 0x19) & 0xFF
    boot.code[0xBD] = chk

    # Embedded Nintendo SDK SRAM Save ID string
    boot.emit_bytes(b"SRAM_V110\x00\x00\x00")

    boot.label("rom_boot")
    boot.li32(13, 0x03007F00)               # SP_usr/sys
    boot.mov_imm(11, STATE_BASE)            # R11 = 0x03000000
    # Enable fast Waitstate 0 + Prefetch first (WAITCNT = 0x4317)
    boot.li32(2, 0x04000200)
    boot.li32(1, 0x4317)
    boot.strh(1, 2, 0x04)
    # DMA3 32-bit copy from 0x08000200 to 0x03001000
    boot.mov_imm(4, IO_BASE)
    boot.li32(0, 0x08000200)
    boot.li32(1, 0x03001000)
    boot.li32(2, 0x84000000 | payload_words)
    boot.str(0, 4, 0xD4)                    # REG_DMA3SAD
    boot.str(1, 4, 0xD8)                    # REG_DMA3DAD
    boot.str(2, 4, 0xDC)                    # REG_DMA3CNT
    boot.bx(1)

    while len(boot.code) < 0x200:
        boot.emit32(0)
    boot.resolve()

    return bytes(boot.code) + payload_bytes


def main():
    parser = argparse.ArgumentParser(description="Build Trytris GBA ROM (trytris.gba) from scratch.")
    parser.add_argument("-o", "--output", default="trytris.gba", help="Output .gba ROM path")
    parser.add_argument("--swap-lr", action="store_true", help="Positive control (Test 2): swap Left and Right controls")
    parser.add_argument("--bad-cell-offset", action="store_true", help="Positive control (Test 6): offset board cell X by +1px")
    args = parser.parse_args()

    rom_bytes = build_trytris_rom(swap_lr=args.swap_lr, bad_cell_offset=args.bad_cell_offset)
    with open(args.output, "wb") as f:
        f.write(rom_bytes)
    crc = zlib.crc32(rom_bytes) & 0xFFFFFFFF
    sha = hashlib.sha256(rom_bytes).hexdigest()
    print(f"[build.py] Built {args.output}: {len(rom_bytes)} bytes, CRC32=0x{crc:08X}, SHA256={sha}")

if __name__ == "__main__":
    import hashlib
    main()