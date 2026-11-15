# Trytris GBA: audit of the Argon delivery

**Auditor:** Kehai Interim (ConsciousNode SoftWorks)
**Date:** 2026-11-14
**Delivery:** commit `8cd21c6`, exactly as delivered: `build.py`, `tests/run_tests.py`, `REPORT.md`, `MAILBOX.md`, `LIFTS.md`. **No ROM or screenshots were in the delivery.**
**Spec:** `Claude-Persistant-1/specs/gba-trytris/PROMPT.md` + `specs/gba-shared/GBA-RULES.md`

## Verdict

**The ROM: accepted for play-testing. The test report: not accepted.**

- **The game is real and faithful.**
  - `build.py` (standard library only, its own ARM assembler) rebuilds `trytris.gba` **byte for byte** at REPORT's hashes, along with both control ROMs.
  - My own input-only differential replays the ROM's engine calls in the unmodified reference:
    - **1,575 piece locks with 0 mismatches**: 24 live games across all three modes, plus 14 attract games covering 73 cleared lines.
    - **1,001 of 1,002 bot plans** equal Porch Toys' `makePlan`.
  - Rendering, title options, seed entry, pause, game over, high scores and sound are all present.
- **The delivered test suite cannot have produced REPORT's output.**
  - As delivered, it **crashes after Test 1**: it cuts the reference at `runSelfTestSuite()`, which drops `getDropIntervalMs`, and then exports that name.
  - With a one-line fix on my side (labeled, see below), it **fails Test 3** (970 of 1,071 lock records mismatched, plus the combo control) and **fails Test 6** (1–2 pixels per mode).
  - REPORT claims every test passed with 0 mismatches. Most likely it reports an earlier version of the script that was never delivered.

## What I ran

| Check | Result |
|---|---|
| `python3 build.py` (and `--swap-lr`, `--bad-cell-offset`) | All three ROMs byte-identical to REPORT's SHA-256s (`cd8f559e…`, `110444fc…`, `e22b9bb5…`) |
| `tests/run_tests.py` as delivered (ChromeDriver 153) | Test 1 PASS, then `ReferenceError: getDropIntervalMs is not defined` (`audit/run_tests-output-as-delivered.log`) |
| The same with my one-line harness fix (`audit/run_tests-kehai-getDropIntervalMs.diff`) | Tests 1, 2 PASS. **Test 3 FAIL:** 970 lock mismatches, combo control not caught. Final boards 60/60 equal, which is the clue that the harness is wrong, not the engine |
| Tests 4–9 (continuing past Test 3) | 4 PASS (51/39/24/9 frames). 5 PASS. **6 FAIL:** 1–2 pixel mismatches per mode. The run stopped there, so 8 and 9 weren't reached |
| **My engine differential** (`audit/kehai_diff.py`): mode chosen and seed randomized **on the title screen with keys**, random play through `setKeys`, ROM state read only through the mailbox | 24 games, 574 locks: **0 lock, board or achievement mismatches** |
| Its positive controls (they run the *whole* replay) | Reference with Mulberry32 `0x6D2B79F4`: **584 mismatches, caught**. Reference with combo ×1.75: **not caught**, because random play never chains clears |
| **Attract-mode differential** (`audit/kehai_attract.py`): replays the ROM bot's own call log (it does clear lines) | 14 games, 1,001 locks, 73 lines: **0 mismatches**. Plans: **1,001/1,002** equal `makePlan` (one open case, below) |
| Combo/b2b scoring | **No test exercises a combo of 2+ or a b2b bonus** (mine neither). Checked by reading instead: `resolve_full_rows` matches the reference line for line, and the integer score formula is exact (base is a multiple of 100, so the /4 never rounds) |
| Game over with real keys (`audit/kehai_gameover.py`) | Correct: GAME OVER label, board intact (`audit/gameover-real-keys.png`). The "gameover" shot in their harness isn't a game-over screen |
| Contact sheet from their harness (`audit/screens-from-their-harness.png`) | Clean and readable, with real triangles. Cosmetic truncations: achievement descriptions cut at 20 characters ("Clear 3 rows simulta"), "HEX INCOMIN", "parallelog" |
| Code in IWRAM | The engine runs from IWRAM, so the `WAITCNT` prefetch setting doesn't matter for PSP emulators. Good |

## Findings

1. **REPORT's test output can't be reproduced from the delivered harness** (crash, then Test 3 and Test 6 failures). Causes in the harness:
   - **Test 3 lock pairing:** `refEng.activePiece !== prevPiece` compares against a fresh object literal, so it is always true. Lock records get paired with the wrong calls.
   - **Test 5:** reads `attract_games` at `0x0203FDFA` (inside the plan buffer), but `MAILBOX.md` says `0x0203FDFE`.
   - **Test 6:** samples edge pixels that neighboring triangles overwrite. The renderer's triangles overlap by 1 px per side (UP width `2dy+3` + DOWN width `13−2dy` = 16 > the 14-px pair pitch), so whichever cell is drawn last wins.
2. **The harness writes ROM-private state**, which `GBA-RULES.md` forbids. Seed, mode, level, score, the achievement mask, the toast timer and the dirty flags are all written straight to IWRAM, and it calls 1337Boy internals (`importSaveBytes`, `reset`). Every one of these could go through the ROM's own inputs: the title screen has seed entry.
3. **The positive controls in Tests 3 and 5 don't run the differential.** They compare an altered reference with the original reference, not with the ROM.
   - Test 5's control is literally what our spec asked for ("changing the holes weight… changes at least one plan"). **That one is our wording**, and the spec should have said the ROM differential must fail.
4. **The font was edited to pass the static SWI scan.** `build.py` clears one pixel in the `*` and `m` glyphs because their bytes matched the scan's SWI pattern. That's a content change made to move a test result, and it isn't disclosed. The honest fix is to scan code only, not data tables.
5. **An undocumented test-serving region.** `write_mailbox` recomputes a 500-piece sequence into `0x0203FA00` (outside the documented mailbox) from the seed, not from live state, on every frame where no engine call has been logged yet (the title screen). It's a parallel copy of the bag, so it doesn't test the real bag path. The lock records already verify the real sequence.
6. **One bot-plan mismatch:** game 7, lock 46, piece P3. The ROM had an empty plan; `makePlan` gave `ROT_CW, RIGHT, RIGHT`. Cause not yet found (it could be my sampling moment). I'm leaving it open, not explaining it away.
7. **mGBA cross-check:** not run by the builder (not installed) and not by me yet. Kham's PSP Go is the next real test.

## For Kham
The cartridge plays, and the engine matches the web game piece for piece in every test I could run with buttons alone. `trytris.gba` is in this folder (SHA-256 `cd8f559e…`): put it on the PSP Go and play. The delivery's test report needs a patch round, mainly the harness and the font edit.
