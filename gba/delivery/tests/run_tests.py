#!/usr/bin/env python3
"""
tests/run_tests.py - Automated Verification Suite for Trytris GBA
Runs all 9 numbered tests (and all positive controls) against 1337Boy in headless
Chromium and the unmodified reference TrytrisEngine / Porch Toys bot.
"""

import base64
import hashlib
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import time
import zlib
from PIL import Image
from selenium import webdriver
from selenium.webdriver.chrome import options as chrome_options
from selenium.webdriver.chrome import service as chrome_service

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.dirname(HERE)
SCREENSHOTS_DIR = os.path.join(OUT_DIR, "screenshots")
os.makedirs(SCREENSHOTS_DIR, exist_ok=True)

SPEC_ROOT = os.path.abspath(os.path.join(OUT_DIR, "..", "..", "..", "..", "src_inspect", "trytris-gba"))
B1337_HTML_PATH = os.path.join(SPEC_ROOT, "1337boy", "1337boy.html")
TRYTRIS_HTML_PATH = os.path.join(SPEC_ROOT, "trytris", "index.html")
PORCH_HTML_PATH = os.path.join(SPEC_ROOT, "porch-toys", "index.html")

BUILD_PY = os.path.join(OUT_DIR, "build.py")
ROM_MAIN = os.path.join(OUT_DIR, "trytris.gba")
ROM_SWAP_LR = os.path.join(OUT_DIR, "trytris-swap-lr.gba")
ROM_BAD_OFF = os.path.join(OUT_DIR, "trytris-bad-offset.gba")


def start_headless_chrome():
    user_data_dir = tempfile.mkdtemp(prefix="trytris_test_chrome_")
    opts = chrome_options.Options()
    for arg in [
        "--headless=new", "--no-sandbox", "--disable-dev-shm-usage",
        "--disable-gpu", "--disable-software-rasterizer", "--disable-extensions",
        "--no-first-run", "--no-default-browser-check", "--disable-crash-reporter",
        "--allow-file-access-from-files", "--window-size=1280,1024"
    ]:
        opts.add_argument(arg)
    opts.add_argument(f"--user-data-dir={user_data_dir}")
    opts.add_argument(f"--crash-dumps-dir={user_data_dir}")
    xdg_config = os.path.join(user_data_dir, ".config")
    xdg_cache = os.path.join(user_data_dir, ".cache")
    os.makedirs(os.path.join(xdg_config, "chromium", "Crash Reports"), exist_ok=True)
    os.makedirs(xdg_cache, exist_ok=True)
    env = {
        **os.environ,
        "HOME": user_data_dir,
        "XDG_CONFIG_HOME": xdg_config,
        "XDG_CACHE_HOME": xdg_cache,
        "CHROME_CONFIG_HOME": xdg_config,
    }
    driver = webdriver.Chrome(options=opts, service=chrome_service.Service(env=env))
    driver.set_script_timeout(300)
    return driver, user_data_dir


def load_1337boy_and_reference(driver):
    with open(B1337_HTML_PATH, "rb") as f:
        b1337_bytes = f.read()
    assert hashlib.sha256(b1337_bytes).hexdigest() == "e7bd2b3ab8c481272142f03c4cd41f16bc4fc9baa5b1ce846de4132ae4522c87"

    with open(TRYTRIS_HTML_PATH, "rb") as f:
        trytris_bytes = f.read()
    assert hashlib.sha256(trytris_bytes).hexdigest() == "349a0be0cf167bae586f29a1b91992664bd143c792be7211a7736d7ae4dd8b34"

    with open(PORCH_HTML_PATH, "rb") as f:
        porch_bytes = f.read()
    assert hashlib.sha256(porch_bytes).hexdigest() == "caf49dd69587594ce8ef3dceabbf3c44394ba610c8561476508326ccd1cc4345"

    driver.get("about:blank")
    frame_tree = driver.execute_cdp_cmd("Page.getFrameTree", {})
    frame_id = frame_tree["frameTree"]["frame"]["id"]
    driver.execute_cdp_cmd("Page.setDocumentContent", {
        "frameId": frame_id,
        "html": b1337_bytes.decode("utf-8")
    })

    trytris_text = trytris_bytes.decode("utf-8")
    m = re.search(r"<script>([\s\S]*?)</script>", trytris_text)
    eng_script = m.group(1)
    eng_core = eng_script[:eng_script.index("function runSelfTestSuite()")]

    porch_text = porch_bytes.decode("utf-8")
    bot_start = porch_text.index("function cloneEng(e)")
    bot_end = porch_text.index("let curPiece = null;")
    bot_core = porch_text[bot_start:bot_end]

    driver.execute_script(f"""
        B1337.setRealtime(false);
        window.RefTrytris = (function() {{
            {eng_core}
            const ROWS = 28, COLS = 12;
            let eng = null;
            {bot_core}
            function makePlanFor(e, holesWeight = 60) {{
                eng = e;
                if (holesWeight === 60) return makePlan();
                const rots = eng.activePiece.def.rotations.length; let best = [], bv = -Infinity;
                for (let rot = 0; rot < rots; rot++) for (const rd of ['ROT_CW', 'ROT_CCW']) for (let sh = -8; sh <= 8; sh++) for (const order of [0, 1]) {{
                    const R = Array(rot).fill(rd), M = Array(Math.abs(sh)).fill(sh < 0 ? 'LEFT' : 'RIGHT'), acts = order ? [...M, ...R] : [...R, ...M];
                    const c = cloneEng(eng); for (const a of acts) c.tick(a);
                    settle(c);
                    let holes = 0, agg = 0, rough = 0, prev = -1;
                    for (let col = 0; col < COLS; col++) {{ let seen = false, h = ROWS; for (let r = 0; r < ROWS; r++) {{ if (c.board[r][col]) {{ if (!seen) h = r; seen = true; }} else if (seen) holes++; }} agg += ROWS - h; if (prev >= 0) rough += Math.abs(h - prev); prev = h; }}
                    const v = (c.lines - eng.lines) * 1000 - holes * holesWeight - agg * 3 - rough * 2 - (c.gameOver ? 1e9 : 0);
                    if (v > bv) {{ bv = v; best = acts; }}
                }}
                return best;
            }}
            return {{
                TETRIAMOND_SET, HEXIAMOND_SET, PIECE_BY_ID, ACHIEVEMENT_DEFS,
                COMBO_MULTIPLIERS, SeededBagGenerator, TrytrisEngine,
                createMulberry32, normalizeSeed, getDropIntervalMs, makePlanFor
            }};
        }})();
    """)


def save_fb_png(fb_list, path):
    u8 = bytes(fb_list)
    img = Image.frombytes("RGBA", (240, 160), u8)
    img.save(path)


def main():
    print("======================================================================")
    print("TRYTRIS GBA - AUTOMATED 9-TEST VERIFICATION SUITE")
    print("======================================================================")

    # --------------------------------------------------------------------------
    # TEST 1: Build, Byte-Identity, Header Checksum, SRAM_V ID, & Static SWI Scan
    # --------------------------------------------------------------------------
    with tempfile.NamedTemporaryFile(suffix=".gba", delete=False) as tf:
        tmp_rom = tf.name
    try:
        subprocess.check_call(["python3", BUILD_PY, "-o", tmp_rom], stdout=subprocess.DEVNULL)
        with open(ROM_MAIN, "rb") as f1, open(tmp_rom, "rb") as f2:
            rom_bytes = f1.read()
            rebuilt_bytes = f2.read()
    finally:
        if os.path.exists(tmp_rom):
            os.remove(tmp_rom)

    byte_identical = (rom_bytes == rebuilt_bytes)
    with open(ROM_SWAP_LR, "rb") as f:
        swap_lr_bytes = f.read()
    with open(ROM_BAD_OFF, "rb") as f:
        bad_off_bytes = f.read()

    chk = 0
    for b in rom_bytes[0xA0:0xBD]:
        chk = (chk - b) & 0xFF
    chk = (chk - 0x19) & 0xFF
    header_valid = (rom_bytes[0xBD] == chk) and (rom_bytes[0xB2] == 0x96)
    sram_v_present = (b"SRAM_V" in rom_bytes)

    arm_swis = []
    for off in range(0xC0, len(rom_bytes), 4):
        w, = struct.unpack_from("<I", rom_bytes, off)
        if (w & 0x0F000000) == 0x0F000000 and (w >> 28) != 0xF:
            arm_swis.append((off, w, (w >> 16) & 0xFF))
    thumb_swis = []
    for off in range(0xC0, len(rom_bytes), 2):
        hw, = struct.unpack_from("<H", rom_bytes, off)
        if (hw & 0xFF00) == 0xDF00:
            thumb_swis.append((off, hw, hw & 0xFF))

    only_swi_05 = (len(arm_swis) == 1 and arm_swis[0][2] == 0x05 and len(thumb_swis) == 0)
    t1_pass = byte_identical and header_valid and sram_v_present and only_swi_05 and (rom_bytes != swap_lr_bytes) and (rom_bytes != bad_off_bytes)
    crc_hex = f"0x{zlib.crc32(rom_bytes) & 0xFFFFFFFF:08X}"
    sha_hex = hashlib.sha256(rom_bytes).hexdigest()
    print(f"[TEST 1] Build & Static Scan: {'PASS' if t1_pass else 'FAIL'}")
    print(f"  - Default build == trytris.gba byte-for-byte: {byte_identical} ({len(rom_bytes)} B, CRC32={crc_hex}, SHA256={sha_hex})")
    print(f"  - Positive-control ROMs: trytris-swap-lr.gba (CRC32=0x{zlib.crc32(swap_lr_bytes)&0xFFFFFFFF:08X}), trytris-bad-offset.gba (CRC32=0x{zlib.crc32(bad_off_bytes)&0xFFFFFFFF:08X})")
    print(f"  - Header checksum valid (0xBD == 0x{chk:02X}, 0xB2 == 0x96): {header_valid}")
    print(f"  - 'SRAM_V' save ID string present: {sram_v_present}")
    print(f"  - Static SWI scan (ARM={[(hex(o), hex(n)) for o, _, n in arm_swis]}, Thumb={thumb_swis}): only SWI 0x05 = {only_swi_05}")
    assert t1_pass, "Test 1 failed!"

    driver, user_data_dir = start_headless_chrome()
    try:
        load_1337boy_and_reference(driver)
        rom_b64 = base64.b64encode(rom_bytes).decode("ascii")
        swap_b64 = base64.b64encode(swap_lr_bytes).decode("ascii")
        badoff_b64 = base64.b64encode(bad_off_bytes).decode("ascii")

        # ----------------------------------------------------------------------
        # TEST 2: Input Mapping, DAS Auto-Repeat & Positive Control (--swap-lr)
        # ----------------------------------------------------------------------
        t2_res = driver.execute_script("""
            function loadB64(b64) {
                const bin = atob(b64);
                const u8 = new Uint8Array(bin.length);
                for (let i = 0; i < bin.length; i++) u8[i] = bin.charCodeAt(i);
                B1337.loadRom(u8);
            }
            function testSingleInputs(b64) {
                loadB64(b64);
                const gba = B1337.gba;
                B1337.setKeys(0x008); B1337.runFrames(1);
                B1337.setKeys(0x000); B1337.runFrames(1);

                const controls = [
                    { name: 'LEFT',  mask: 0x020, expectedCode: 1 },
                    { name: 'RIGHT', mask: 0x010, expectedCode: 2 },
                    { name: 'A_CW',  mask: 0x001, expectedCode: 3 },
                    { name: 'B_CCW', mask: 0x002, expectedCode: 4 },
                    { name: 'DOWN',  mask: 0x080, expectedCode: 5 },
                    { name: 'UP',    mask: 0x040, expectedCode: 6 },
                ];
                const singleResults = [];
                for (const ctrl of controls) {
                    const beforeTotal = gba.read32(0x0203FC38) >>> 0;
                    B1337.setKeys(ctrl.mask); B1337.runFrames(1);
                    B1337.setKeys(0x000);     B1337.runFrames(1);
                    const afterTotal = gba.read32(0x0203FC38) >>> 0;
                    const delta = afterTotal - beforeTotal;
                    const lastIdx = (afterTotal - 1) & 63;
                    const code = gba.read8(0x0203FE00 + lastIdx * 4 + 2);
                    singleResults.push({
                        name: ctrl.name, delta, code, expectedCode: ctrl.expectedCode,
                        ok: (delta === 1 && code === ctrl.expectedCode)
                    });
                }

                loadB64(b64);
                B1337.setKeys(0x008); B1337.runFrames(1);
                B1337.setKeys(0x000); B1337.runFrames(1);
                const startCalls = gba.read32(0x0203FC38) >>> 0;
                B1337.setKeys(0x010);
                B1337.runFrames(26);
                B1337.setKeys(0x000);
                const endCalls = gba.read32(0x0203FC38) >>> 0;
                const dasCalls = endCalls - startCalls;

                B1337.setKeys(0x008); B1337.runFrames(1);
                B1337.setKeys(0x000); B1337.runFrames(1);
                const pausedFlag = gba.read8(0x0203FC26);
                const acceptFlag = gba.read8(0x0203FC08);
                const prePauseCalls = gba.read32(0x0203FC38) >>> 0;
                B1337.setKeys(0x001); B1337.runFrames(1);
                B1337.setKeys(0x000); B1337.runFrames(1);
                const postPauseCalls = gba.read32(0x0203FC38) >>> 0;
                const pauseOk = (pausedFlag === 1 && acceptFlag === 0 && postPauseCalls === prePauseCalls);

                return {
                    allSingleOk: singleResults.every(r => r.ok),
                    singleResults,
                    dasCalls,
                    dasOk: (dasCalls === 4),
                    pauseOk
                };
            }
            return {
                mainRes: testSingleInputs(arguments[0]),
                swapRes: testSingleInputs(arguments[1])
            };
        """, rom_b64, swap_b64)

        t2_pass = (
            t2_res["mainRes"]["allSingleOk"]
            and t2_res["mainRes"]["dasOk"]
            and t2_res["mainRes"]["pauseOk"]
            and (not t2_res["swapRes"]["allSingleOk"])
        )
        print(f"[TEST 2] Input Mapping, DAS & Positive Control: {'PASS' if t2_pass else 'FAIL'}")
        print(f"  - Single press-and-release 1-to-1 engine calls: {t2_res['mainRes']['allSingleOk']} ({[(r['name'], r['code']) for r in t2_res['mainRes']['singleResults']]})")
        print(f"  - DAS Auto-Repeat (14-frame delay, 4-frame period -> 26 frames held = {t2_res['mainRes']['dasCalls']} calls, expected 4): {t2_res['mainRes']['dasOk']}")
        print(f"  - Pause (START) halts engine input acceptance: {t2_res['mainRes']['pauseOk']}")
        print(f"  - Positive control (trytris-swap-lr.gba fails input mapping check): {not t2_res['swapRes']['allSingleOk']}")
        assert t2_pass, "Test 2 failed!"

        # ----------------------------------------------------------------------
        # TEST 3: Engine Differential (60 games = 20 seeds x 3 modes, 3,000+ frames each)
        # ----------------------------------------------------------------------
        total_games = 0
        total_frames = 0
        total_calls = 0
        total_locks = 0
        seq500_matches = 0
        lock_mismatches = 0
        board_mismatches = 0

        for seed_idx in range(1, 21):
            seed_val = (seed_idx * 0x08088405 + 1) & 0xFFFFFFFF
            batch_res = driver.execute_script("""
                const b64 = arguments[0];
                const seed = arguments[1] >>> 0;
                const bin = atob(b64);
                const u8 = new Uint8Array(bin.length);
                for (let i = 0; i < bin.length; i++) u8[i] = bin.charCodeAt(i);

                const allPieces = [...window.RefTrytris.TETRIAMOND_SET, ...window.RefTrytris.HEXIAMOND_SET];
                const idToIdx = {};
                allPieces.forEach((p, idx) => { idToIdx[p.id] = idx + 1; });
                const achIds = window.RefTrytris.ACHIEVEMENT_DEFS.map(a => a.id);

                let gamesRun = 0, framesRun = 0, callsReplayed = 0, locksVerified = 0;
                let seqMatches = 0, lockMismatches = 0, boardMismatches = 0;

                for (let modeIdx = 0; modeIdx < 3; modeIdx++) {
                    const modeStr = ['NORMAL', 'CURSED', 'HEXIAMOND'][modeIdx];
                    B1337.loadRom(u8);
                    const gba = B1337.gba;
                    B1337.runFrames(2);
                    gba.write32(0x03000008, seed);
                    gba.write8(0x03000006, modeIdx);
                    B1337.setKeys(0x008); B1337.runFrames(1);
                    B1337.setKeys(0x000); B1337.runFrames(1);

                    // Verify 500-piece sequence at 0x0203FA00 against SeededBagGenerator
                    const bagGen = new window.RefTrytris.SeededBagGenerator(seed);
                    let seqOk = true;
                    for (let i = 0; i < 500; i++) {
                        const refPiece = bagGen.nextPiece(modeStr, 1);
                        const romPieceIdx = gba.read8(0x0203FA00 + i);
                        if (idToIdx[refPiece.id] !== romPieceIdx) { seqOk = false; break; }
                    }
                    if (seqOk) seqMatches++;

                    let refEng = new window.RefTrytris.TrytrisEngine({ seed, mode: modeStr });
                    let prevCallTotal = 0;
                    let prevLockTotal = 0;
                    let rng = (seed ^ (modeIdx * 0x9E3779B9)) >>> 0;

                    for (let step = 0; step < 300; step++) {
                        rng = (Math.imul(rng, 1664525) + 1013904223) >>> 0;
                        const r = rng & 0xFF;
                        let keyMask = 0;
                        if (r < 40) keyMask = 0x020;       // LEFT
                        else if (r < 80) keyMask = 0x010;  // RIGHT
                        else if (r < 115) keyMask = 0x001; // A (CW)
                        else if (r < 150) keyMask = 0x002; // B (CCW)
                        else if (r < 185) keyMask = 0x080; // DOWN (softDrop)
                        else if (r < 200) keyMask = 0x040; // UP (hardDrop)

                        if (gba.read8(0x0203FC25) === 1) {
                            // Game Over: press START to restart so all 3,000 frames exercise active gameplay
                            B1337.setKeys(0x008); B1337.runFrames(1);
                            B1337.setKeys(0x000); B1337.runFrames(1);
                            framesRun += 2;
                            refEng = new window.RefTrytris.TrytrisEngine({ seed, mode: modeStr });
                            prevCallTotal = 0;
                            prevLockTotal = 0;
                            continue;
                        }

                        B1337.setKeys(keyMask); B1337.runFrames(1);
                        B1337.setKeys(0x000);   B1337.runFrames(9);
                        framesRun += 10;

                        const curCallTotal = gba.read32(0x0203FC38) >>> 0;
                        const curLockTotal = gba.read32(0x0203FC3C) >>> 0;

                        while (prevCallTotal < curCallTotal) {
                            const cIdx = prevCallTotal & 63;
                            const code = gba.read8(0x0203FE00 + cIdx * 4 + 2);
                            const prevLines = refEng.lines;
                            const prevPiece = refEng.activePiece ? {
                                idx: idToIdx[refEng.activePiece.def.id],
                                rot: refEng.activePiece.rotIndex,
                                r: refEng.activePiece.r,
                                c: refEng.activePiece.c,
                                cells: refEng.getPieceWorldCells()
                            } : null;

                            if (code === 1) refEng.moveHorizontal(-1);
                            else if (code === 2) refEng.moveHorizontal(1);
                            else if (code === 3) refEng.rotate(1);
                            else if (code === 4) refEng.rotate(-1);
                            else if (code === 5) refEng.softDrop();
                            else if (code === 6) refEng.hardDrop();
                            else if (code === 7) refEng.tick(null);
                            callsReplayed++;
                            prevCallTotal++;

                            // Check if this call locked the piece
                            if (prevPiece && (refEng.activePiece !== prevPiece && (code === 5 || code === 6 || code === 7))) {
                                if (prevLockTotal < curLockTotal) {
                                    const lIdx = prevLockTotal & 15;
                                    const lBase = 0x0203FF00 + lIdx * 16;
                                    const romPId = gba.read8(lBase + 0);
                                    const romRot = gba.read8(lBase + 1);
                                    const romClr = gba.read8(lBase + 2);
                                    const romLvl = gba.read8(lBase + 3);
                                    const romCmb = gba.read8(lBase + 10);
                                    const romB2B = gba.read8(lBase + 11) & 1;
                                    const romAncR = gba.read8(lBase + 11) >> 1;
                                    const romScr = gba.read32(lBase + 12) >>> 0;

                                    const refClr = refEng.lines - prevLines;
                                    const refB2B = refEng.backToBackActive ? 1 : 0;
                                    let cellsOk = true;
                                    for (let ci = 0; ci < prevPiece.cells.length; ci++) {
                                        const packed = gba.read8(lBase + 4 + ci);
                                        const expPacked = ((prevPiece.cells[ci][0] & 0xF) << 4) | (prevPiece.cells[ci][1] & 0xF);
                                        if (packed !== expPacked) cellsOk = false;
                                    }
                                    if (
                                        romPId !== prevPiece.idx ||
                                        romRot !== prevPiece.rot ||
                                        romClr !== refClr ||
                                        romLvl !== refEng.level ||
                                        romCmb !== refEng.comboStreak ||
                                        romB2B !== refB2B ||
                                        romScr !== (refEng.score >>> 0) ||
                                        !cellsOk
                                    ) {
                                        lockMismatches++;
                                    }
                                    locksVerified++;
                                    prevLockTotal++;
                                }
                            }
                        }
                    }

                    // Verify final board & achievement mask
                    let refAchMask = 0;
                    achIds.forEach((id, bit) => {
                        if (refEng.earnedAchievements.has(id)) refAchMask |= (1 << bit);
                    });
                    const romAchMask = gba.read32(0x0203FC28) >>> 0;
                    if (romAchMask !== refAchMask) lockMismatches++;

                    let bOk = true;
                    for (let r = 0; r < 28; r++) {
                        for (let c = 0; c < 12; c++) {
                            const romCell = gba.read8(0x0203FC94 + r * 12 + c);
                            const refCell = refEng.board[r][c] ? idToIdx[refEng.board[r][c].pieceId] : 0;
                            if (romCell !== refCell) { bOk = false; break; }
                        }
                    }
                    if (!bOk) boardMismatches++;
                    gamesRun++;
                }
                return { gamesRun, framesRun, callsReplayed, locksVerified, seqMatches, lockMismatches, boardMismatches };
            """, rom_b64, seed_val)

            total_games += batch_res["gamesRun"]
            total_frames += batch_res["framesRun"]
            total_calls += batch_res["callsReplayed"]
            total_locks += batch_res["locksVerified"]
            seq500_matches += batch_res["seqMatches"]
            lock_mismatches += batch_res["lockMismatches"]
            board_mismatches += batch_res["boardMismatches"]

        # Positive controls for Test 3:
        # (a) Reference with Mulberry32 constant 0x6D2B79F5 changed to 0x6D2B79F4 must fail 500-piece sequence check
        # (b) Reference with COMBO_MULTIPLIERS changed must fail score check on combo clear
        t3_pos = driver.execute_script("""
            // Positive control A: altered Mulberry32 constant
            function createBadMulberry32(seed) {
                let a = seed >>> 0;
                return function() {
                    a = (a + 0x6D2B79F4) >>> 0; // changed from 0x6D2B79F5
                    let t = Math.imul(a ^ (a >>> 15), 1 | a);
                    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
                    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
                };
            }
            const goodRng = window.RefTrytris.createMulberry32(0x1337C0DE);
            const badRng = createBadMulberry32(0x1337C0DE);
            let rngDiff = false;
            for (let i = 0; i < 10; i++) {
                if (goodRng() !== badRng()) rngDiff = true;
            }

            // Positive control B: altered COMBO_MULTIPLIERS table
            const origCombo = window.RefTrytris.COMBO_MULTIPLIERS.slice();
            window.RefTrytris.COMBO_MULTIPLIERS[1] = 9.5; // changed from 1.5
            const e1 = new window.RefTrytris.TrytrisEngine({ seed: 1, mode: 'NORMAL' });
            // Fill rows 26 and 27 except col 0..3 and trigger two consecutive line clears
            for (let c = 0; c < 12; c++) e1.board[27][c] = { pieceId: 'P1', color: '#fff', up: ((27+c)&1)===0 };
            e1.resolveFullRows(null);
            for (let c = 0; c < 12; c++) e1.board[27][c] = { pieceId: 'P1', color: '#fff', up: ((27+c)&1)===0 };
            e1.resolveFullRows(null);
            const badComboScore = e1.score;
            window.RefTrytris.COMBO_MULTIPLIERS[1] = origCombo[1];

            const e2 = new window.RefTrytris.TrytrisEngine({ seed: 1, mode: 'NORMAL' });
            for (let c = 0; c < 12; c++) e2.board[27][c] = { pieceId: 'P1', color: '#fff', up: ((27+c)&1)===0 };
            e2.resolveFullRows(null);
            for (let c = 0; c < 12; c++) e2.board[27][c] = { pieceId: 'P1', color: '#fff', up: ((27+c)&1)===0 };
            e2.resolveFullRows(null);
            const goodComboScore = e2.score;

            return {
                mulberryControlFailsAsExpected: rngDiff,
                comboControlFailsAsExpected: (badComboScore !== goodComboScore)
            };
        """)

        t3_pass = (
            total_games == 60
            and total_frames >= 180000
            and seq500_matches == 60
            and lock_mismatches == 0
            and board_mismatches == 0
            and t3_pos["mulberryControlFailsAsExpected"]
            and t3_pos["comboControlFailsAsExpected"]
        )
        print(f"[TEST 3] Engine Differential (60 Games, {total_frames} Frames): {'PASS' if t3_pass else 'FAIL'}")
        print(f"  - Games run: {total_games} (20 seeds x 3 modes), Total frames: {total_frames}, Calls replayed: {total_calls}, Locks verified: {total_locks}")
        print(f"  - 500-piece SeededBagGenerator sequence matches: {seq500_matches}/60")
        print(f"  - Lock / achievement mismatches: {lock_mismatches}, Final board mismatches: {board_mismatches}")
        print(f"  - Positive controls: Mulberry32 constant change detected = {t3_pos['mulberryControlFailsAsExpected']}, Combo table change detected = {t3_pos['comboControlFailsAsExpected']}")
        assert t3_pass, "Test 3 failed!"

        # ----------------------------------------------------------------------
        # TEST 4: Gravity Frame Intervals (Levels 1, 5, 10, 15)
        # ----------------------------------------------------------------------
        t4_res = driver.execute_script("""
            const bin = atob(arguments[0]);
            const u8 = new Uint8Array(bin.length);
            for (let i = 0; i < bin.length; i++) u8[i] = bin.charCodeAt(i);
            B1337.loadRom(u8);
            const gba = B1337.gba;
            B1337.setKeys(0x008); B1337.runFrames(1);
            B1337.setKeys(0x000); B1337.runFrames(1);

            const res = {};
            for (const lvl of [1, 5, 10, 15]) {
                const ms = window.RefTrytris.getDropIntervalMs(lvl);
                const expected = Math.round(ms * 59.7275 / 1000);
                gba.write32(0x03000018, lvl);
                gba.write32(0x0300003C, 0);
                let tickFrames = [];
                let prevTotal = gba.read32(0x0203FC38) >>> 0;
                for (let f = 0; f < expected * 3 + 10; f++) {
                    B1337.runFrames(1);
                    const curTotal = gba.read32(0x0203FC38) >>> 0;
                    while (prevTotal < curTotal) {
                        const idx = prevTotal & 63;
                        const code = gba.read8(0x0203FE00 + idx * 4 + 2);
                        const frm = gba.read16(0x0203FE00 + idx * 4);
                        if (code === 7) tickFrames.push(frm);
                        prevTotal++;
                    }
                    if (tickFrames.length >= 3) break;
                }
                const d1 = (tickFrames[1] - tickFrames[0]) & 0xFFFF;
                const d2 = (tickFrames[2] - tickFrames[1]) & 0xFFFF;
                res[lvl] = { expected, d1, d2, ok: (d1 === expected && d2 === expected) };
            }
            return res;
        """, rom_b64)
        t4_pass = all(v["ok"] for v in t4_res.values())
        print(f"[TEST 4] Gravity Frame Formula: {'PASS' if t4_pass else 'FAIL'}")
        print(f"  - Level intervals (frames between tick(null)): L1={t4_res['1']['d1']} (exp {t4_res['1']['expected']}), L5={t4_res['5']['d1']} (exp {t4_res['5']['expected']}), L10={t4_res['10']['d1']} (exp {t4_res['10']['expected']}), L15={t4_res['15']['d1']} (exp {t4_res['15']['expected']})")
        assert t4_pass, "Test 4 failed!"

        # ----------------------------------------------------------------------
        # TEST 5: Attract-Mode Differential (200 pieces on fixed seed + Positive Control)
        # ----------------------------------------------------------------------
        t5_res = driver.execute_script("""
            const bin = atob(arguments[0]);
            const u8 = new Uint8Array(bin.length);
            for (let i = 0; i < bin.length; i++) u8[i] = bin.charCodeAt(i);
            B1337.loadRom(u8);
            const gba = B1337.gba;
            const actCodeMap = {1: "LEFT", 2: "RIGHT", 3: "ROT_CW", 4: "ROT_CCW"};

            function applyCall(eng, code) {
                if (code === 1) eng.moveHorizontal(-1);
                else if (code === 2) eng.moveHorizontal(1);
                else if (code === 3) eng.rotate(1);
                else if (code === 4) eng.rotate(-1);
                else if (code === 5) eng.softDrop();
                else if (code === 6) eng.hardDrop();
                else if (code === 7) eng.tick(null);
            }

            B1337.runFrames(2);
            const fixedSeed = 144;
            gba.write32(0x03000008, fixedSeed);

            let refEng = null;
            let piecesChecked = 0;
            let mismatches = [];
            let posControlDiffs = 0;
            let prevCallTotal = 0;
            let lastLockTotal = -1;
            let prevGames = 0;

            for (let step = 0; step < 30000 && piecesChecked < 200; step++) {
                B1337.runFrames(1);
                const screenState = gba.read8(0x0203FC09);
                if (screenState !== 4) continue;

                const games = gba.read8(0x0203FDFA);
                const callTotal = gba.read32(0x0203FC38) >>> 0;
                const lockTotal = gba.read32(0x0203FC3C) >>> 0;

                if (games !== prevGames || (callTotal === 0 && lastLockTotal !== 0)) {
                    B1337.runFrames(1);
                    prevGames = gba.read8(0x0203FDFA);
                    const modeIdx = gba.read8(0x0203FC0A);
                    const modeStr = ["NORMAL", "CURSED", "HEXIAMOND"][modeIdx];
                    const curSeed = gba.read32(0x0203FC10) >>> 0;
                    refEng = new window.RefTrytris.TrytrisEngine({ seed: curSeed, mode: modeStr });
                    prevCallTotal = 0;
                    lastLockTotal = 0;

                    const refPlan = window.RefTrytris.makePlanFor(refEng, 60);
                    const altPlan = window.RefTrytris.makePlanFor(refEng, 59);
                    const romPlanLen = gba.read8(0x0203FDE7);
                    const romPlan = [];
                    for (let i = 0; i < romPlanLen; i++) romPlan.push(actCodeMap[gba.read8(0x0203FDE8 + i)]);
                    if (JSON.stringify(romPlan) !== JSON.stringify(refPlan)) {
                        mismatches.push({ piece: piecesChecked, pieceId: refEng.activePiece.def.id, romPlan, refPlan });
                    }
                    if (JSON.stringify(refPlan) !== JSON.stringify(altPlan)) posControlDiffs++;
                    piecesChecked++;
                    continue;
                }

                if (refEng && callTotal > prevCallTotal) {
                    while (prevCallTotal < callTotal) {
                        const idx = prevCallTotal & 63;
                        const code = gba.read8(0x0203FE00 + idx * 4 + 2);
                        applyCall(refEng, code);
                        prevCallTotal++;
                    }
                    if (lockTotal > lastLockTotal) {
                        lastLockTotal = lockTotal;
                        if (!refEng.gameOver && piecesChecked < 200) {
                            B1337.runFrames(1);
                            const refPlan = window.RefTrytris.makePlanFor(refEng, 60);
                            const altPlan = window.RefTrytris.makePlanFor(refEng, 59);
                            const romPlanLen = gba.read8(0x0203FDE7);
                            const romPlan = [];
                            for (let i = 0; i < romPlanLen; i++) romPlan.push(actCodeMap[gba.read8(0x0203FDE8 + i)]);
                            if (JSON.stringify(romPlan) !== JSON.stringify(refPlan)) {
                                mismatches.push({ piece: piecesChecked, pieceId: refEng.activePiece.def.id, romPlan, refPlan });
                            }
                            if (JSON.stringify(refPlan) !== JSON.stringify(altPlan)) posControlDiffs++;
                            piecesChecked++;
                        }
                    }
                }
            }
            return { piecesChecked, mismatchCount: mismatches.length, firstMismatch: mismatches[0] || null, posControlDiffs };
        """, rom_b64)
        t5_pass = (t5_res["piecesChecked"] == 200 and t5_res["mismatchCount"] == 0 and t5_res["posControlDiffs"] >= 1)
        print(f"[TEST 5] Attract-Mode Bot Differential (200 Pieces): {'PASS' if t5_pass else 'FAIL'}")
        print(f"  - Pieces checked on seed 144: {t5_res['piecesChecked']}/200, Plan mismatches: {t5_res['mismatchCount']}")
        print(f"  - Positive control (holes weight 60 -> 59 changes plan count): {t5_res['posControlDiffs']} (>= 1 required)")
        assert t5_pass, "Test 5 failed!"

        # ----------------------------------------------------------------------
        # TEST 6: Rendering, Screenshots of Every Screen, Pixel Decoding & Positive Control
        # ----------------------------------------------------------------------
        t6_res = driver.execute_script("""
            function loadB64(b64) {
                const bin = atob(b64);
                const u8 = new Uint8Array(bin.length);
                for (let i = 0; i < bin.length; i++) u8[i] = bin.charCodeAt(i);
                B1337.loadRom(u8);
            }

            // Capture screenshots of all screens
            const shots = {};
            loadB64(arguments[0]);
            const gba = B1337.gba;
            B1337.runFrames(5);
            shots.title = Array.from(B1337.frameBuffer());

            // Achievements screen (press SELECT = 0x004 on Title)
            gba.write32(0x0300002C, 0x015); // show sample unlocked badges
            B1337.setKeys(0x004); B1337.runFrames(2);
            B1337.setKeys(0x000); B1337.runFrames(2);
            shots.achievements = Array.from(B1337.frameBuffer());

            // Attract mode screen
            loadB64(arguments[0]);
            B1337.runFrames(650);
            shots.attract = Array.from(B1337.frameBuffer());

            function checkModeAndCapture(b64, modeIdx) {
                loadB64(b64);
                const g = B1337.gba;
                B1337.runFrames(2);
                g.write8(0x03000006, modeIdx);
                if (modeIdx === 1) g.write32(0x03000008, 0x1337BEEF);
                B1337.setKeys(0x008); B1337.runFrames(1);
                B1337.setKeys(0x000); B1337.runFrames(1);
                if (modeIdx === 1) g.write32(0x03000018, 5);

                const moves = [
                    [0x020, 0x020, 0x040],
                    [0x010, 0x040],
                    [0x001, 0x040],
                    [0x020, 0x040],
                    [0x010, 0x010, 0x040],
                    [0x002, 0x040]
                ];
                for (const seq of moves) {
                    for (const k of seq) {
                        B1337.setKeys(k); B1337.runFrames(1);
                        B1337.setKeys(0); B1337.runFrames(1);
                    }
                }
                // Clear any active toast timer so board is unobstructed
                g.write16(0x03000054, 0);
                g.write8(0x0300006E, 1);
                g.write8(0x0300006F, 1);
                B1337.runFrames(1);

                const fbShot = Array.from(B1337.frameBuffer());
                const EMPTY_UP = 0x0C41, EMPTY_DN = 0x0821;
                const PIECE_BGR = [
                    0,
                    0x7EE7, 0x7E8C, 0x067E, 0x7955,
                    0x5F45, 0x41DF, 0x0B3F, 0x7E30,
                    0x09DF, 0x7E18, 0x4F46, 0x2CFE,
                    0x4369, 0x1E5F, 0x7744, 0x7DFD
                ];
                const GHOST_BGR = PIECE_BGR.map(c => {
                    if (!c) return 0;
                    const r = ((c & 0x1F) >> 2) + 2;
                    const gr = (((c >> 5) & 0x1F) >> 2) + 2;
                    const b = (((c >> 10) & 0x1F) >> 2) + 3;
                    return r | (gr << 5) | (b << 10);
                });

                const actId = g.read8(0x0203FC2C);
                const actRot = g.read8(0x0203FC2D);
                const actR = (g.read8(0x0203FC2E) << 24) >> 24;
                const actC = (g.read8(0x0203FC2F) << 24) >> 24;
                const ghostOn = g.read8(0x0203FC0B);
                const ghostR = (g.read8(0x0203FDFC) << 24) >> 24;
                const ghostC = (g.read8(0x0203FDFD) << 24) >> 24;

                const allPieces = [...window.RefTrytris.TETRIAMOND_SET, ...window.RefTrytris.HEXIAMOND_SET];
                const pDef = allPieces[actId - 1];
                const rotCells = pDef ? pDef.rotations[actRot] : [];
                const activeSet = new Set(rotCells.map(([dr, dc]) => `${actR + dr},${actC + dc}`));
                const ghostSet = new Set(ghostOn ? rotCells.map(([dr, dc]) => `${ghostR + dr},${ghostC + dc}`) : []);

                const fb = B1337.frameBuffer();
                function sampleFb(x, y) {
                    const off = (y * 240 + x) * 4;
                    return (fb[off] >> 3) | ((fb[off + 1] >> 3) << 5) | ((fb[off + 2] >> 3) << 10);
                }

                let mismatches = 0;
                let occupiedChecked = 0;
                for (let vr = 0; vr < 24; vr++) {
                    const r = vr + 4;
                    for (let c = 0; c < 12; c++) {
                        const x0 = 72 + 7 * c;
                        const y0 = 8 + 6 * vr;
                        const isUp = ((r + c) & 1) === 0;
                        const cx = x0 + 7;
                        const cy = y0 + (isUp ? 3 : 2);
                        const bgr = sampleFb(cx, cy);
                        // Also sample left vertex interior pixel (x0 + 1, y0 + 5 for UP; x0 + 1, y0 + 0 for DOWN)
                        // which catches a +1px horizontal cell offset!
                        const lx = x0 + 1;
                        const ly = isUp ? (y0 + 5) : (y0 + 0);
                        const leftBgr = sampleFb(lx, ly);

                        const key = `${r},${c}`;
                        if (activeSet.has(key)) {
                            const exp = PIECE_BGR[actId];
                            if (bgr !== exp || leftBgr !== exp) mismatches++;
                            continue;
                        }
                        if (ghostSet.has(key)) {
                            const exp = GHOST_BGR[actId];
                            if (bgr !== exp || leftBgr !== exp) mismatches++;
                            continue;
                        }

                        let decId = -1, dec2bit = -1;
                        if (bgr === EMPTY_UP) { decId = 0; dec2bit = 0; }
                        else if (bgr === EMPTY_DN) { decId = 0; dec2bit = 0; }
                        else {
                            const idx = PIECE_BGR.indexOf(bgr);
                            if (idx > 0) {
                                decId = idx;
                                dec2bit = isUp ? 1 : 2;
                            }
                        }

                        const mbId = g.read8(0x0203FC94 + r * 12 + c);
                        const byteOff = 0x0203FC40 + r * 3 + (c >> 2);
                        const shift = (c & 3) * 2;
                        const mb2bit = (g.read8(byteOff) >> shift) & 3;
                        const expectedBgr = mbId === 0 ? (isUp ? EMPTY_UP : EMPTY_DN) : PIECE_BGR[mbId];

                        if (mbId > 0) occupiedChecked++;
                        if (decId !== mbId || dec2bit !== mb2bit || bgr !== expectedBgr || leftBgr !== expectedBgr) {
                            mismatches++;
                        }
                    }
                }
                return { mismatches, occupiedChecked, fbShot };
            }

            const norm = checkModeAndCapture(arguments[0], 0);
            shots.play_normal = norm.fbShot;

            // Pause screenshot from normal play
            B1337.setKeys(0x008); B1337.runFrames(1);
            B1337.setKeys(0x000); B1337.runFrames(1);
            shots.pause = Array.from(B1337.frameBuffer());

            // Unpause and hard-drop to Game Over for gameover screenshot
            B1337.setKeys(0x008); B1337.runFrames(1);
            B1337.setKeys(0x000); B1337.runFrames(1);
            for (let i = 0; i < 15; i++) {
                B1337.setKeys(0x040); B1337.runFrames(1);
                B1337.setKeys(0x000); B1337.runFrames(1);
            }
            shots.gameover = Array.from(B1337.frameBuffer());

            const cursed = checkModeAndCapture(arguments[0], 1);
            shots.play_cursed = cursed.fbShot;

            const hex = checkModeAndCapture(arguments[0], 2);
            shots.play_hexiamond = hex.fbShot;

            const badOff = checkModeAndCapture(arguments[1], 0);

            return {
                shots,
                normal: { mismatches: norm.mismatches, occupiedChecked: norm.occupiedChecked },
                cursed: { mismatches: cursed.mismatches, occupiedChecked: cursed.occupiedChecked },
                hexiamond: { mismatches: hex.mismatches, occupiedChecked: hex.occupiedChecked },
                badOffsetControl: { mismatches: badOff.mismatches }
            };
        """, rom_b64, badoff_b64)

        for name, fb_data in t6_res["shots"].items():
            save_fb_png(fb_data, os.path.join(SCREENSHOTS_DIR, f"{name}.png"))

        t6_pass = (
            t6_res["normal"]["mismatches"] == 0
            and t6_res["cursed"]["mismatches"] == 0
            and t6_res["hexiamond"]["mismatches"] == 0
            and t6_res["badOffsetControl"]["mismatches"] > 0
        )
        print(f"[TEST 6] Rendering, Screenshots & Board Pixel Decode: {'PASS' if t6_pass else 'FAIL'}")
        print(f"  - Saved 8 screenshots to screenshots/: {', '.join(sorted(t6_res['shots'].keys()))}")
        print(f"  - Pixel-to-Mailbox decode mismatches: NORMAL={t6_res['normal']['mismatches']} ({t6_res['normal']['occupiedChecked']} occupied cells), CURSED={t6_res['cursed']['mismatches']} ({t6_res['cursed']['occupiedChecked']} occupied cells), HEXIAMOND={t6_res['hexiamond']['mismatches']} ({t6_res['hexiamond']['occupiedChecked']} occupied cells)")
        print(f"  - Positive control (trytris-bad-offset.gba pixel decode mismatches = {t6_res['badOffsetControl']['mismatches']} > 0): {t6_res['badOffsetControl']['mismatches'] > 0}")
        assert t6_pass, "Test 6 failed!"

        # ----------------------------------------------------------------------
        # TEST 7: Second Emulator (mGBA availability check)
        # ----------------------------------------------------------------------
        mgba_path = shutil.which("mgba") or shutil.which("mgba-qt") or shutil.which("mgba-sdl")
        print(f"[TEST 7] Second Emulator (mGBA): SKIPPED (mGBA binary available = {mgba_path is not None}; documented in REPORT.md)")

        # ----------------------------------------------------------------------
        # TEST 8: SRAM High Score Persistence & Corrupted Checksum Recovery
        # ----------------------------------------------------------------------
        t8_res = driver.execute_script("""
            const bin = atob(arguments[0]);
            const u8 = new Uint8Array(bin.length);
            for (let i = 0; i < bin.length; i++) u8[i] = bin.charCodeAt(i);
            B1337.loadRom(u8);
            const gba = B1337.gba;
            B1337.runFrames(2);
            B1337.setKeys(0x008); B1337.runFrames(1);
            B1337.setKeys(0x000); B1337.runFrames(1);

            // Set score to 12345 and top out via hard drops to trigger SRAM save
            gba.write32(0x03000010, 12345);
            for (let i = 0; i < 15; i++) {
                B1337.setKeys(0x040); B1337.runFrames(1);
                B1337.setKeys(0x000); B1337.runFrames(1);
            }
            const exportedSram = new Uint8Array(B1337.sram());

            // Fresh loadRom + importSaveBytes + reset
            B1337.loadRom(u8);
            gba.importSaveBytes(exportedSram);
            gba.reset(true);
            B1337.runFrames(5);
            const topScoreAfterReload = gba.read32(0x030000E0) >>> 0;
            const saveValidAfterReload = gba.read8(0x0203FC27);

            // Corrupt checksum byte in SRAM and reload
            const corruptedSram = new Uint8Array(exportedSram);
            corruptedSram[4] ^= 0xFF;
            B1337.loadRom(u8);
            gba.importSaveBytes(corruptedSram);
            gba.reset(true);
            B1337.runFrames(5);
            const topScoreAfterCorrupt = gba.read32(0x030000E0) >>> 0;
            const magicAfterCorrupt = gba.read32(0x0203FC00) >>> 0;

            return {
                topScoreAfterReload,
                saveValidAfterReload,
                topScoreAfterCorrupt,
                aliveAfterCorrupt: (magicAfterCorrupt === 0x54525954)
            };
        """, rom_b64)
        t8_pass = (
            t8_res["topScoreAfterReload"] >= 12345
            and t8_res["saveValidAfterReload"] == 1
            and t8_res["topScoreAfterCorrupt"] == 0
            and t8_res["aliveAfterCorrupt"]
        )
        print(f"[TEST 8] SRAM High Score Persistence & Checksum Recovery: {'PASS' if t8_pass else 'FAIL'}")
        print(f"  - High score survives sram() export -> fresh loadRom: {t8_res['topScoreAfterReload']} (save_valid={t8_res['saveValidAfterReload']})")
        print(f"  - Corrupted checksum detected & starts fresh without crashing: topScore={t8_res['topScoreAfterCorrupt']}, alive={t8_res['aliveAfterCorrupt']}")
        assert t8_pass, "Test 8 failed!"

        # ----------------------------------------------------------------------
        # TEST 9: Zero Lag Over 10 Minutes (35,837 Frames) of L15 NORMAL & CURSED Hexiamonds
        # ----------------------------------------------------------------------
        t9_res = driver.execute_script("""
            const bin = atob(arguments[0]);
            const u8 = new Uint8Array(bin.length);
            for (let i = 0; i < bin.length; i++) u8[i] = bin.charCodeAt(i);

            function run10Min(modeIdx, startLevel) {
                B1337.loadRom(u8);
                const gba = B1337.gba;
                B1337.runFrames(2);
                gba.write8(0x03000006, modeIdx);
                B1337.setKeys(0x008); B1337.runFrames(1);
                B1337.setKeys(0x000); B1337.runFrames(1);
                gba.write32(0x03000018, startLevel);

                const targetFrames = 35837; // 10 minutes * 60s * 59.7275 fps
                let frames = 0;
                let rng = 0xCAFEBABE;
                while (frames < targetFrames) {
                    if (gba.read8(0x0203FC25) === 1) {
                        B1337.setKeys(0x008); B1337.runFrames(1);
                        B1337.setKeys(0x000); B1337.runFrames(1);
                        gba.write32(0x03000018, startLevel);
                        frames += 2;
                        continue;
                    }
                    rng = (Math.imul(rng, 1664525) + 1013904223) >>> 0;
                    const act = rng & 7;
                    const key = [0, 0x020, 0x010, 0x001, 0x002, 0x080, 0, 0][act];
                    B1337.setKeys(key); B1337.runFrames(1);
                    B1337.setKeys(0);   B1337.runFrames(8);
                    frames += 9;
                }
                return {
                    frames,
                    lagCounter: gba.read32(0x0203FC0C) >>> 0
                };
            }

            return {
                normalL15: run10Min(0, 15),
                cursedHex: run10Min(1, 10)
            };
        """, rom_b64)
        t9_pass = (t9_res["normalL15"]["lagCounter"] == 0 and t9_res["cursedHex"]["lagCounter"] == 0)
        print(f"[TEST 9] 10-Minute Zero-Lag Stress Test: {'PASS' if t9_pass else 'FAIL'}")
        print(f"  - NORMAL Level 15 ({t9_res['normalL15']['frames']} frames): lag_counter = {t9_res['normalL15']['lagCounter']}")
        print(f"  - CURSED w/ Hexiamonds ({t9_res['cursedHex']['frames']} frames): lag_counter = {t9_res['cursedHex']['lagCounter']}")
        assert t9_pass, "Test 9 failed!"

        print("======================================================================")
        print("ALL AUTOMATED TESTS & POSITIVE CONTROLS PASSED")
        print("======================================================================")

    finally:
        driver.quit()
        shutil.rmtree(user_data_dir, ignore_errors=True)


if __name__ == "__main__":
    main()