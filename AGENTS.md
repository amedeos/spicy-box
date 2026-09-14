# Working on this repository

A parametric 3D-printable carousel that holds tall spice tubes upright, so one
can be grabbed with a single hand while cooking. The model is written in
build123d and exported to STL, 3MF and STEP.

## Reference measurements

These come from the actual tubes and are the reason the defaults look the way
they do. Re-measure before changing them; the photographs they were read off
are in `ref/`.

| Property | Value | How it was obtained |
| --- | --- | --- |
| Tube material | Hard plastic | Confirmed by the owner |
| Body diameter | 19.95 mm, rounded to 20.0 | Calipers |
| Body length | ~180 mm | Measured by the owner |
| Cap | Flush with the body, a couple of millimetres tall | Photographs |
| Bottom | Flat, with a rounded edge | Photographs |
| Label | Paper, wrapped around the upper part of the tube | Photographs |

The widest rigid part of a tube is therefore the body, not the cap, which is why
pockets are sized from `tube_dia`.

## Tooling

**This project uses `uv` exclusively. Never call `pip`.**

```bash
uv sync                      # create .venv and install from uv.lock
uv run scripts/export.py     # regenerate everything in out/
uv run pytest -q             # run the checks
uv add <package>             # add a dependency
```

`uv.lock` and `.python-version` are committed on purpose: they pin both the
dependency set and the interpreter.

Python 3.13 is pinned because `cadquery-ocp`, which build123d builds on,
publishes wheels for CPython 3.12 and 3.13 but not for 3.14. uv downloads a
matching interpreter itself, so the system Python version does not matter.

On a headless Linux box the OCP extension is still linked against two X11
libraries at import time, even though nothing is ever drawn: `libGL.so.1` and
`libX11.so.6`. Without them the import fails with
`ImportError: libGL.so.1: cannot open shared object file`, and fixing only that
one reveals the second. Install both:

```bash
sudo apt install libgl1 libx11-6        # Debian, Ubuntu
sudo dnf install mesa-libGL libX11      # Fedora
```

`ldd .venv/lib64/python3.13/site-packages/OCP/OCP*.so | grep "not found"` lists
anything still missing.

## Language

Everything inside the repository is written in English at a B2/C1 level:
identifiers, comments, docstrings, documentation, CLI output, error messages and
exported file names. Write full sentences and use precise terms — *clearance*,
*pocket*, *overhang*, *bed size* — rather than padding or jargon.

## Conventions

**Every dimension lives in `src/spicy_box/params.py`.** The model code contains
no hard-coded millimetre values: measured numbers are fields of `Params` and
anything computable from them is a property. If you find yourself typing a
number into `model.py`, it belongs in `Params` instead.

`Params.validate()` is where design constraints are enforced. Add a check there
when you discover a combination that produces a technically valid but useless
part — it is much cheaper than finding out on the print bed.

## Printing constraints that must not be broken

The part is designed to print upright in one piece with **no support material**.
Any change has to preserve that:

* no overhang shallower than 45 degrees — this is why window heads are pointed
  and why the bottom outer edge is chamfered rather than filleted;
* pockets stay vertical and blind, and their mouths are chamfered so the opening
  widens upwards;
* wall thicknesses stay multiples of the 0.4 mm extrusion width.

`uv run pytest -q` checks the functional side of this: that a tube fits every
pocket, that each pocket opens through its window, and that the rim survives.

## Calibration

FDM printers produce holes roughly 0.2-0.3 mm smaller than drawn, and by
different amounts on different machines. Whenever the printer, the filament or
the slicer profile changes, print `out/tolerance_coupon.stl` first, find the
hole the tube likes, and put that number into `Params.clearance`.
