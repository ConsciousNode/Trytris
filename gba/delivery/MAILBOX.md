# Trytris GBA: Test Mailbox Specification (`MAILBOX.md`)

The Trytris GBA ROM maintains a live 1,024-byte test mailbox in EWRAM at `0x0203FC00..0x0203FFFF`.
Every frame—unconditionally and on the single execution code path—`write_mailbox` populates the mailbox directly from live game state, while `log_engine_call` and `lock_active_piece` append records to the ring buffers at `0x0203FE00..0x0203FFFF`.

## 1. Shared & Scalar State Header (`0x0203FC00..0x0203FC3F`, 64 bytes)

| Address | Offset | Type | Field | Description |
| :--- | :--- | :--- | :--- | :--- |
| `0x0203FC00` | `+0x000` | `uint32` | `magic` | Magic word `0x54525954` (`'TRYT'` in ASCII little-endian) |
| `0x0203FC04` | `+0x004` | `uint32` | `frame_counter` | Total VBlank frames elapsed since boot |
| `0x0203FC08` | `+0x008` | `uint8` | `accepting_input` | `1` when in live `PLAY` screen and not paused/game-over; `0` otherwise |
| `0x0203FC09` | `+0x009` | `uint8` | `screen_state` | `0` = Title, `1` = Play (and Pause/Game Over overlay), `3` = Achievements, `4` = Attract Mode |
| `0x0203FC0A` | `+0x00A` | `uint8` | `mode` | `0` = `NORMAL`, `1` = `CURSED`, `2` = `HEXIAMOND` |
| `0x0203FC0B` | `+0x00B` | `uint8` | `ghost_enabled` | `1` = Ghost piece ON, `0` = Ghost piece OFF |
| `0x0203FC0C` | `+0x00C` | `uint32` | `lag_counter` | VBlank interrupts that arrived while `S_IN_FRAME == 1` |
| `0x0203FC10` | `+0x010` | `uint32` | `seed` | Active 32-bit Mulberry32 game seed |
| `0x0203FC14` | `+0x014` | `uint32` | `score` | Current game score |
| `0x0203FC18` | `+0x018` | `uint32` | `level` | Current level (`1..15`) |
| `0x0203FC1C` | `+0x01C` | `uint32` | `lines` | Total lines cleared in current game |
| `0x0203FC20` | `+0x020` | `uint32` | `combo` | Current `comboStreak` (consecutive piece locks clearing $\ge 1$ row) |
| `0x0203FC24` | `+0x024` | `uint8` | `b2b` | `backToBackActive` (`1` = active, `0` = idle) |
| `0x0203FC25` | `+0x025` | `uint8` | `game_over` | `1` = Game Over, `0` = active |
| `0x0203FC26` | `+0x026` | `uint8` | `paused` | `1` = Paused, `0` = unpaused |
| `0x0203FC27` | `+0x027` | `uint8` | `save_valid` | `1` if valid SRAM record loaded/saved; `0` if blank/corrupt SRAM triggered fresh start |
| `0x0203FC28` | `+0x028` | `uint32` | `ach_mask` | Session-persistent unlocked achievement bits (`bits 0..9`) |
| `0x0203FC2C` | `+0x02C` | `uint8` | `active_id` | Active piece ID (`1..4` = `P1..P4`, `5..16` = `H1..H12`, `0` = none) |
| `0x0203FC2D` | `+0x02D` | `uint8` | `active_rot` | Active piece rotation state index (`0..5`) |
| `0x0203FC2E` | `+0x02E` | `int8` | `active_r` | Active piece anchor row (`0..27`) |
| `0x0203FC2F` | `+0x02F` | `int8` | `active_c` | Active piece anchor column (`0..11`) |
| `0x0203FC30` | `+0x030` | `uint32` | `idle_frames` | Consecutive frames without player input in live Play (`1,792` frames = 30.0 s for `Patient`) |
| `0x0203FC34` | `+0x034` | `uint32` | `grav_timer` | Frames elapsed since last gravity step |
| `0x0203FC38` | `+0x038` | `uint32` | `call_total` | Total engine calls logged in current game (index mod 64 into `0x0203FE00`) |
| `0x0203FC3C` | `+0x03C` | `uint32` | `lock_total` | Total piece locks logged in current game (index mod 16 into `0x0203FF00`) |

### Achievement Bit Positions (`ach_mask` at `0x0203FC28`)

| Bit | Achievement Name | Trigger |
| :--- | :--- | :--- |
| `0` (`0x001`) | `Triforce` | Clear 3+ rows simultaneously |
| `1` (`0x002`) | `Sphinx Riddle` | Lock a `sphinx` (`H5`, ID 9) contributing to a completed row |
| `2` (`0x004`) | `Butterfly Effect` | Clear a row using a `butterfly` (`H12`, ID 16) |
| `3` (`0x008`) | `Cursed!` | Reach level 5 in `CURSED` mode |
| `4` (`0x010`) | `No Mercy` | Reach level 10 in `HEXIAMOND` mode |
| `5` (`0x020`) | `Geodesic` | Clear 100 total lines in a single game |
| `6` (`0x040`) | `Zero State` | All-clear the entire board after a line clear |
| `7` (`0x080`) | `Helix` | Clear at least one line on 10 consecutive piece locks |
| `8` (`0x100`) | `Ternary Perfect` | After any lock, every occupied cell in rows 25..27 is up-pointing (`▲`) |
| `9` (`0x200`) | `Patient` | Lock a piece after $\ge 1,792$ frames (30 s) without input at level $\ge 5$ |

## 2. Packed Board Representations (`0x0203FC40..0x0203FDE3`, 420 bytes)

* **`0x0203FC40..0x0203FC93` (84 bytes) — 2-Bit Cell Orientation Board (`12 × 28 = 336` cells):**
  * Row-major (`r = 0..27`, `c = 0..11`), 3 bytes per row (`4` cells per byte, bits `(c % 4) * 2 .. (c % 4) * 2 + 1`):
    * `0` (`0b00`): Empty (`Z`)
    * `1` (`0b01`): Up-pointing (`▲`, `T`, when `(r + c)` is even and occupied)
    * `2` (`0b10`): Down-pointing (`▽`, `F`, when `(r + c)` is odd and occupied)
* **`0x0203FC94..0x0203FDE3` (336 bytes) — 8-Bit Per-Cell Piece ID Board (`12 × 28 = 336` bytes):**
  * Byte at `0x0203FC94 + r * 12 + c` stores `0` if empty, or `1..16` (`P1..P4` = `1..4`, `H1..H12` = `5..16`).

## 3. Previews & Attract-Mode Bot Plan (`0x0203FDE4..0x0203FDFF`, 28 bytes)

| Address | Offset | Type | Field | Description |
| :--- | :--- | :--- | :--- | :--- |
| `0x0203FDE4` | `+0x1E4` | `uint8[3]` | `preview_ids[0..2]` | Next 3 queued piece IDs (`1..16`) from `SeededBagGenerator` |
| `0x0203FDE7` | `+0x1E7` | `uint8` | `bot_plan_len` | Number of actions in the current attract-mode `makePlan` action list |
| `0x0203FDE8` | `+0x1E8` | `uint8[20]` | `bot_plan_buf[0..19]` | Action codes: `1` = `LEFT`, `2` = `RIGHT`, `3` = `ROT_CW`, `4` = `ROT_CCW` |
| `0x0203FDFC` | `+0x1FC` | `int8` | `ghost_r` | Landing row of ghost piece |
| `0x0203FDFD` | `+0x1FD` | `int8` | `ghost_c` | Landing column of ghost piece |
| `0x0203FDFE` | `+0x1FE` | `uint8` | `attract_games` | Number of games started in attract mode |
| `0x0203FDFF` | `+0x1FF` | `uint8` | `bot_plan_pos` | Next action index to execute in `bot_plan_buf` |

## 4. Engine Call Ring Buffer (`0x0203FE00..0x0203FEFF`, 64 entries × 4 bytes = 256 bytes)

Indexed by `(call_idx & 63) * 4` at `0x0203FE00`, with total call count at `0x0203FC38` (`call_total`):

| Byte Offset | Type | Field | Description |
| :--- | :--- | :--- | :--- |
| `+0x00` | `uint16` | `frame_lo` | Low 16 bits of `frame_counter` when the call occurred |
| `+0x02` | `uint8` | `call_code` | `1` = `moveHorizontal(-1)`, `2` = `moveHorizontal(+1)`, `3` = `rotate(+1)`, `4` = `rotate(-1)`, `5` = `softDrop()`, `6` = `hardDrop()`, `7` = `tick(null)` |
| `+0x03` | `int8` | `result` | Return value (`1`/`0` for `moveHorizontal`, `rotate`, `softDrop`, `tick(null)`; `dropped` steps `0..27` for `hardDrop`) |

## 5. Lock Record Ring Buffer (`0x0203FF00..0x0203FFFF`, 16 entries × 16 bytes = 256 bytes)

Indexed by `(lock_idx & 15) * 16` at `0x0203FF00`, with total lock count at `0x0203FC3C` (`lock_total`):

| Byte Offset | Type | Field | Description |
| :--- | :--- | :--- | :--- |
| `+0x00` | `uint8` | `piece_id` | Locked piece ID (`1..16`) |
| `+0x01` | `uint8` | `rot_index` | Locked piece rotation state index (`0..5`) |
| `+0x02` | `uint8` | `lines_cleared` | Number of full rows cleared by this lock (`0..4+`) |
| `+0x03` | `uint8` | `level_after` | `level` after resolving line clears |
| `+0x04..+0x09` | `uint8[6]` | `cells[0..5]` | Each byte encodes `(r << 4) | (c & 0x0F)` before row collapse; unused slots `4..5` on 4-cell tetriamonds are `0xFF` |
| `+0x0A` | `uint8` | `combo_after` | `comboStreak` after lock |
| `+0x0B` | `uint8` | `b2b_after` | `backToBackActive` (`0` or `1`) after lock |
| `+0x0C..+0x0F` | `uint32` | `score_after` | `score` after lock |
