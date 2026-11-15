# Trytris GBA — Technical & Verification Report

**Studio:** ConsciousNode SoftWorks  
**License:** MIT  
**Target Hardware:** Game Boy Advance (ARM7TDMI @ 16.78 MHz, Mode 3 240 × 160 BGR555, 32 KB SRAM)  

---

## 1. Feature Confirmation Summary

All requested gameplay, UI, audio, save, attract-mode, and positive-control features are implemented and verified in `trytris.gba`:

- **Sound effects + music:** Present in the ROM via GBA PSG Channels 1–4 (`0x04000060..0x04000084`). Channel 1 (Square 1 with sweep) and Channel 4 (Noise) synthesize all 7 reference sound effects (move, rotate, lock, line clear, Triforce 3+ clear, achievement unlock fanfare, and game over). Channel 2 (Square 2) and Channel 3 (Wave RAM custom triangle-stepped waveform) play two original 32-step background compositions (Title theme and Play/Attract theme). Music silences automatically while paused.
- **Title-screen seed entry:** Present in the ROM. The 32-bit seed is displayed in 8-digit hexadecimal (`00000000`–`FFFFFFFF`) on the `SEED` row of the Title screen. Moving the cursor to `SEED` allows selecting any nibble (`0..7`) with `Left`/`Right`, incrementing/decrementing that hex digit with `A`/`B`, or generating a fresh random seed at any time with `L` or `R`.
- **Ghost piece toggle:** Present in the ROM on the `GHOST` row of the Title screen (`ON` / `OFF`, default `ON`), toggled with `Left`, `Right`, `A`, or `B`. When `ON`, the landing position of the active piece is rendered on the board in a dimmed per-piece BGR555 shade.
- **High-score display:** Present in the ROM on the right panel of the Title screen (`TOP 5 - NORMAL`, `TOP 5 - CURSED`, `TOP 5 - HEXIAMOND`), dynamically updating as the selected mode changes. Scores are persisted in 32 KB Cartridge SRAM (`0x0E000000`) with a version byte (`0x01`) and 32-bit FNV-1a-style checksum.
- **Pause:** Present in the ROM during live play via `START`, which toggles `paused` (`0x0203FC26`), sets `accepting_input = 0` (`0x0203FC08`), silences background music channels, and renders a `PAUSED` overlay banner (`START:RESUME` / `SEL:TITLE`).
- **Achievements (all 10) & list screen:** All 10 reference achievements (`Triforce`, `Sphinx Riddle`, `Butterfly Effect`, `Cursed!`, `No Mercy`, `Geodesic`, `Zero State`, `Helix`, `Ternary Perfect`, `Patient`) fire once per session, display a 90-frame unlock toast banner on the playfield, and can be browsed on the scrollable Achievements screen (`SELECT` from Title).
- **Attract mode:** After 10 seconds (`597` frames) idle on the Title screen, the ROM enters Attract Mode running the Porch Toys greedy bot (`cloneEng`, `settle`, `score`, `makePlan`), alternating `NORMAL` and `CURSED` modes with the caption `"Triangles are hard."` at the bottom of the screen. Any button returns immediately to the Title screen.
- **No balanced-ternary readout and no self-test panel:** Excluded as specified; the board uses the exact 12 × 28 cell model (`4` buffer rows + `24` visible rows) from the reference engine.

---

## 2. Deliverable Binaries & Checksums

| File | Description | Size (Bytes) | CRC32 | SHA-256 | Save Type |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `trytris.gba` | Primary release ROM (default `python3 build.py` output) | `20,944` | `0x0734A3C3` | `cd8f559e2f6f81187363ddfb4b6d90c7ea5bd545b8a99b555c6135234f90f564` | `SRAM_V110` (32 KB) |
| `trytris-swap-lr.gba` | Positive-control ROM (`python3 build.py --swap-lr -o trytris-swap-lr.gba`) with D-pad Left/Right swapped | `20,944` | `0x8892B370` | `110444fcd75e3fc553d47a43166bc92b77f87e8d7c0b724d5112b712499f5d51` | `SRAM_V110` (32 KB) |
| `trytris-bad-offset.gba` | Positive-control ROM (`python3 build.py --bad-cell-offset -o trytris-bad-offset.gba`) with board horizontal origin shifted by `+1` px (`BX=73` vs `72`) | `20,944` | `0x23C64154` | `e22b9bb5897ebd354c31e2a0d33ee6ab72e02a6fd2caa5e91439b3343747e858` | `SRAM_V110` (32 KB) |

### Build & Byte-Identity Commands
```bash
# Default build (byte-identical to trytris.gba)
python3 build.py -o trytris.gba

# Separate positive-control builds
python3 build.py --swap-lr -o trytris-swap-lr.gba
python3 build.py --bad-cell-offset -o trytris-bad-offset.gba
```

---

## 3. Triangle Geometry, Timing & Control Parameters

- **Board & Triangle Cell Geometry (Mode 3, 240 × 160):**
  - Visible grid: `12` columns × `24` visible rows (`vr = 0..23`, mapped to engine rows `r = vr + 4`, where `r = 0..3` are hidden spawn/buffer rows).
  - Board origin: `BX = 72`, `BY = 8`.
  - Triangle cell size: Base `S = 14` px (horizontal column pitch `S/2 = 7` px), Height `H = 6` px (`H/S = 6/14 = 0.4286`, matching the equilateral ratio $\sqrt{3}/4 \approx 0.4330$ within 1%). Total board footprint: `91 × 144` px (`x = 72..162`, `y = 8..151`).
  - Scanline rasterization for cell `(vr, c)` with `x0 = 72 + 7*c`, `y0 = 8 + 6*vr`:
    - **UP triangle (`(vr + c)` even):** for `dy in 0..5`, `half_w = dy + 1` (`1..6`), horizontal span `[x0 + 7 - half_w .. x0 + 7 + half_w]`. Interior sample center: `(x0 + 7, y0 + 3)`.
    - **DOWN triangle (`(vr + c)` odd):** for `dy in 0..5`, `half_w = 6 - dy` (`6..1`), horizontal span `[x0 + 7 - half_w .. x0 + 7 + half_w]`. Interior sample center: `(x0 + 7, y0 + 2)`.
- **DAS Auto-Repeat Timing:**
  - Initial delay: `14` frames (~234 ms at 59.7275 Hz).
  - Repeat period: `4` frames (~67 ms at 59.7275 Hz).
  - Holding Left or Right for `N >= 15` frames produces `1 + floor((N - 15) / 4) + 1` horizontal move calls (e.g., `26` frames held produces `4` calls: frames `1, 15, 19, 23`).
- **Gravity Schedule (`round(getDropIntervalMs(level) * 59.7275 / 1000)`):**
  - Levels 1–15: `51, 48, 45, 42, 39, 36, 33, 30, 27, 24, 21, 18, 15, 12, 9` frames per `tick(null)`.
- **Patient Achievement:**
  - Fires when a piece locks at Level $\ge 5$ with `idle_frames >= 1,792` (`round(30 * 59.7275)` frames without player movement, rotation, or drop inputs).

---

## 4. Automated Test Suite Results (`tests/run_tests.py`)

All 9 numbered test sections (including all positive controls) were executed headlessly against unmodified `1337boy/1337boy.html`, `trytris/index.html`, and `porch-toys/index.html`:

1. **Test 1 (Build & Static Scan):** **PASS**
   - `python3 build.py` rebuilds `trytris.gba` byte-for-byte (`20,944` bytes, CRC32 `0x0734A3C3`, SHA-256 `cd8f559e...90f564`).
   - Header checksum at `0xBD` is valid (`0x47`), fixed byte `0xB2 == 0x96`, and `SRAM_V110` ID string is embedded.
   - Static scan of all 32-bit ARM words and 16-bit Thumb halfwords confirms only a single BIOS call (`SWI 0x05` `VBlankIntrWait` at `0x02E0`) exists in the ROM.
2. **Test 2 (Input Mapping & DAS Auto-Repeat):** **PASS**
   - Single 1-frame press-and-release of Left, Right, A, B, Down, and Up in 1337Boy produces exactly 1 matching engine call in the Mailbox call ring buffer (`codes 1..6`).
   - Holding Right for 26 frames produces exactly 4 calls (`1` initial + `3` DAS repeats at delay 14, period 4).
   - Pressing `START` pauses gameplay (`paused = 1, accepting_input = 0`) and ignores movement/rotation keys.
   - **Positive control:** `trytris-swap-lr.gba` (`--swap-lr`) fails the Left/Right input mapping check as required.
3. **Test 3 (Engine Differential — 60 Games × 3,000+ Frames):** **PASS**
   - Ran 60 games (20 seeds × 3 modes: `NORMAL`, `CURSED`, `HEXIAMOND`), 3,000+ frames of pseudo-random input per game (`180,000+` total frames), replaying each game's Mailbox call log in the unmodified reference `TrytrisEngine`.
   - Zero mismatches across all lock records (`pieceId`, `rotIndex`, world `cells`, `linesCleared`, `score`, `level`, `combo`, `backToBack`, and `earnedAchievements`) and final boards (`0` mismatches).
   - First 500 pieces generated for all 60 `(seed, mode)` pairs match the reference `SeededBagGenerator` (`60/60`).
   - **Positive controls:** Modifying the Mulberry32 constant (`0x6D2B79F5` $\to$ `0x6D2B79F4`) fails the sequence check, and modifying `COMBO_MULTIPLIERS` fails the score check.
4. **Test 4 (Gravity Timing):** **PASS**
   - Measured frames between consecutive `tick(null)` calls: Level 1 = `51` frames, Level 5 = `39` frames, Level 10 = `24` frames, Level 15 = `9` frames (100% match to `round(getDropIntervalMs(level) * 59.7275 / 1000)`).
5. **Test 5 (Attract-Mode Bot Differential — 200 Pieces):** **PASS**
   - Across 200 consecutive pieces in Attract Mode on fixed seed `144`, the ROM bot's planned action list in the Mailbox matches Porch Toys' `makePlan` run on the reconstructed reference engine state (`200/200` pieces, `0` mismatches).
   - **Positive control:** Changing the `holes` weight from `60` to `59` in the reference bot changes at least one plan on the same 200-piece trajectory.
6. **Test 6 (Rendering, Screenshots & Automated Pixel Decoding):** **PASS**
   - Captured PNG screenshots of every screen (`screenshots/title.png`, `play_normal.png`, `play_cursed.png`, `play_hexiamond.png`, `pause.png`, `achievements.png`, `attract.png`, `gameover.png`).
   - Automated pixel decoder sampled all `288` visible triangle cells (`12 × 24`) in `NORMAL`, `CURSED`, and `HEXIAMOND` modes and verified 100% agreement (`0` mismatches) with the Mailbox board state and piece colors.
   - **Positive control:** `trytris-bad-offset.gba` (`--bad-cell-offset`) is caught immediately by the pixel decoder.
7. **Test 7 (Second Emulator — mGBA):** **SKIPPED (Not Installed)**
   - `mGBA` (`mgba` / `mgba-qt` / `mgba-sdl`) is not installed in the verification VM environment.
8. **Test 8 (SRAM Saves & Checksum Verification):** **PASS**
   - High scores persist across `B1337.sram()` export and a fresh `B1337.loadRom()` + `importSaveBytes()` reload (`save_valid = 1`).
   - Flipping bits in the exported SRAM checksum is detected on boot, resetting high scores cleanly to `0` without crashing.
9. **Test 9 (10-Minute Zero-Lag Stress Test):** **PASS**
   - Ran `35,837` frames (10.0 minutes at `59.7275` Hz) of `NORMAL` play at Level 15 and `35,837` frames (10.0 minutes) of `CURSED` play with hexiamonds; the Mailbox `lag_counter` (`0x0203FC0C`) remained `0` throughout both runs.

---

## 5. Differences from Reference & Untested Items

- **Intentional Platform Adaptations:**
  - **Whole-frame timing:** Gravity intervals and the 30-second `Patient` achievement threshold (`1,792` frames) are quantized to whole GBA VBlank frames (`59.7275` Hz) as specified.
  - **Pure puzzle HUD:** The web version's balanced-ternary readout and self-test DOM panel are omitted as required by the spec.
- **What Wasn't Tested:**
  - **Test 7 (`mGBA` cross-emulator comparison):** `mGBA` is not installed in the sandbox VM environment, so cross-emulator framebuffer comparison against `mGBA` could not be executed.
