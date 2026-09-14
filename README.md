# spicy-box

A 3D-printable carousel that stands a set of tall spice tubes upright, so any
one of them can be picked out with a single hand while you are cooking. The
tubes it was designed around are 20 mm across and about 180 mm long, and they
came flat-packed in a wooden box — fine for storage, awkward at the hob.

Everything is generated from a parameter set, so a different tube diameter, a
different number of slots or a taller holder is a one-line change followed by a
re-export.

```
       ║║  ║║  ║║        tubes stand proud by ~94 mm, labels readable
     ┌─────────────┐
     │  ( ) ( )    │     6 pockets on a circle, 21.0 mm across
     │ ( )  ( ) ( )│     windows open the upper half
     │ ▓▓▓▓▓▓▓▓▓▓▓ │     closed band at the bottom for stability
     └─────────────┘     72.6 mm across, 91.2 mm tall
```

## What you get

| File | Purpose |
| --- | --- |
| `out/spicy_box.stl` | the carousel, for any slicer |
| `out/spicy_box.3mf` | same part, with units embedded so nothing gets scaled |
| `out/spicy_box.step` | real surfaces, for further CAD work |
| `out/tolerance_coupon.stl` | a five-hole test piece for dialling in the fit |
| `out/spicy_box_*.png` | shaded previews, with `--preview` |

## Getting started

The project is managed with [uv](https://docs.astral.sh/uv/); `pip` is not used
anywhere.

```bash
uv sync                          # set up the environment
uv run scripts/export.py         # write everything to out/
uv run scripts/export.py --preview
uv run pytest -q                 # verify the geometry
```

uv fetches its own Python 3.13, because the OpenCascade bindings behind
build123d have no wheels for 3.14 yet. On a headless Linux machine you also need
two system libraries that those bindings link against at import time, even
though nothing is ever drawn: `libGL.so.1` and `libX11.so.6`.

```bash
sudo apt install libgl1 libx11-6        # Debian, Ubuntu
sudo dnf install mesa-libGL libX11      # Fedora
```

## Print it

Print it **standing upright, with no support material**. The geometry is built
so that nothing overhangs by more than 45 degrees: the window heads come to a
point, the pocket mouths are chamfered so they widen upwards, and the bottom
edge is chamfered rather than rounded.

| Setting | Suggestion |
| --- | --- |
| Nozzle / layer height | 0.4 mm / 0.2 mm |
| Perimeters | 3 — the pocket walls are 2.4 mm, so they come out solid |
| Infill | 10-15 %, gyroid or grid |
| Supports | none |
| Material | PLA or PETG; PETG if it will sit near the hob |

The solid occupies about 186 cm³, most of which the slicer will fill with sparse
infill. Let the slicer report the real filament figure for your profile.

## Get the fit right first

Holes come out of an FDM printer roughly 0.2-0.3 mm narrower than drawn, and the
error differs from machine to machine. Rather than discovering that after a long
print:

1. print `out/tolerance_coupon.stl` — a flat plate, a few minutes' work, with
   five pockets cut at 0.4, 0.7, 1.0, 1.3 and 1.6 mm of clearance, each labelled;
2. try a tube in each and keep the one that drops in and lifts out without
   effort and without rattling;
3. put that number into `clearance` in `src/spicy_box/params.py`, or pass it on
   the command line, and export the real part.

The coupon reproduces the same chamfered mouth as the carousel, so it feels like
the finished pockets rather than like a plain drilled hole.

## Changing the design

Every dimension lives in `src/spicy_box/params.py` as a field of `Params`, and
every field is also a command line option:

```bash
uv run scripts/export.py --n-slots 8            # a wider carousel
uv run scripts/export.py --clearance 1.3        # looser pockets
uv run scripts/export.py --holder-height-ratio 0.35   # a low, open holder
uv run scripts/export.py --window-top arch      # rounded window heads
uv run scripts/export.py --base-flare 8         # a wider foot for heavy tubes
```

The parameters worth knowing about:

| Parameter | Default | What it does |
| --- | --- | --- |
| `tube_dia` | 20.0 | measured tube diameter; the pocket is sized from it |
| `tube_body_len`, `cap_len` | 180.0, 2.5 | tube length, which sets the height |
| `n_slots` | 6 | pockets on the circle — five tubes plus a spare |
| `holder_height_ratio` | 0.5 | how much of the tube the holder covers |
| `clearance` | 1.0 | gap between pocket and tube; see calibration above |
| `band_height` | 40.0 | height of the closed lower band |
| `rim_height` | 8.0 | uninterrupted ring at the top |
| `window_width` | 12.0 | how much of each tube you can see and push on |
| `window_top` | `pointed` | window head: `pointed` and `arch` stop below the rim, `open` runs to the top and breaks the rim into tabs |
| `min_protrusion` | 20.0 | shortest length of tube that must stay grabbable above the rim |
| `base_flare` | 0.0 | extra radius at the foot, for a heavier tube set |
| `core_bore_dia` | 0.0 | optional bore down the middle |

`Params.validate()` refuses combinations that would produce a part you cannot
use — windows so wide that the tubes fall out sideways, a holder so deep that
there is nothing left to grab, pockets that eat the core away. You get a
readable message instead of a wasted print.

## Layout

```
src/spicy_box/
├── params.py       every dimension, measured or derived
├── model.py        the carousel itself
├── calibration.py  the clearance test coupon
├── preview.py      shaded PNG renders, a development aid
└── cli.py          the exporter
scripts/export.py   run the exporter from the repository
tests/              geometry checks, including that a tube fits each pocket
```

## Licence

GPL-3.0. See `LICENSE`.
