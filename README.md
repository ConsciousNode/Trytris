# Trytris
A ternary puzzle game! ▲▽

Falling pieces on a real equilateral triangular grid, with a live balanced-ternary readout of the board (▲ = **T**, empty = **Z**, ▽ = **F**). One HTML file, no dependencies, works offline. MIT.

**Play:** https://consciousnode.github.io/Trytris/ (or open `index.html` in a browser).

![Trytris](screenshot.png)

- **NORMAL:** the 4 one-sided tetriamonds (the bar comes in both chiralities, P1/P2).
- **CURSED:** tetriamonds until level 5, then all 12 hexiamonds join.
- **HEXIAMOND:** all 12 free hexiamonds from the first piece.
- Seeded (Mulberry32), ghost piece, achievements, and an in-browser self-test suite (18 assertions; the badge says READY only when all pass).
- **Dead-cell marker** (toggle, or press **K**): a small × on every empty cell that no piece in the current set can reach at all, found by searching every position the game's own movement rules allow. A ▲ has no top edge, so once both of its side neighbors are filled it can never be filled again, and the marker shows it the moment that happens.

## Ternary Negation (a feature)
Moving a row down by one on a triangular grid turns every triangle upside down. So **clearing an odd number of rows flips everything above the clear**, and its balanced-ternary readout is negated: every T becomes F, and every F becomes T. An even clear leaves orientation alone. It started as an accident of the geometry and stayed on purpose. Self-test #18 pins it.

## Credits
Spec by Kham and Ed Interim (`SPEC.md`). Built by Gemini Argon. Audited by Kehai Interim (notes in the `REPORT` block at the bottom of `index.html`).

## Prior art and neighbors
Falling blocks on triangular grids have been done before (for example [Triangular Tetris](https://quuxplusone.github.io/blog/2023/05/19/triangular-tetris) and [MultiMino 2: Polyform](https://axelfox149.itch.io/polyform)), and the balanced-ternary VM [SBTCVM](https://sbtcvm.blogspot.com) has its own ternary games, including *Falling Ternary Targets*. A native TritOS version (App 11), written in Triton guest assembly, now runs on the [Triton](https://github.com/ConsciousNode/Triton) balanced-ternary machine and matches this reference state for state ([audit](https://github.com/ConsciousNode/Triton/blob/main/AUDIT-TRYTRIS-APP.md)).

---

*Tetris was born in Moscow in 1984, a decade after Moscow stopped building ternary computers. Trytris runs on the machine it never got to meet.*
