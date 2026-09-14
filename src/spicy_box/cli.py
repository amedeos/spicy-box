"""Command line entry point: build the carousel and write the export files."""

from __future__ import annotations

import argparse
from dataclasses import fields
from pathlib import Path
from typing import Sequence, get_args

from build123d import Mesher, Part, Unit, export_step, export_stl

from spicy_box.calibration import build_tolerance_coupon
from spicy_box.model import build_carousel
from spicy_box.params import DEFAULT, Params, WindowTop

DEFAULT_OUT = Path("out")


def _add_param_options(parser: argparse.ArgumentParser) -> None:
    """Expose every field of :class:`Params` as a command line option.

    Deriving the options from the dataclass keeps the two in step: a parameter
    added to the model is immediately overridable from the shell.
    """
    group = parser.add_argument_group("parameters", "override any value in Params")
    for field in fields(Params):
        flag = "--" + field.name.replace("_", "-")
        current = getattr(DEFAULT, field.name)
        if field.type == "WindowTop" or field.name == "window_top":
            group.add_argument(
                flag, choices=get_args(WindowTop), help=f"default: {current}"
            )
        else:
            kind = int if field.type == "int" else float
            group.add_argument(
                flag, type=kind, metavar=kind.__name__, help=f"default: {current}"
            )


def params_from_args(args: argparse.Namespace) -> Params:
    """Fold the command line overrides into the default parameter set."""
    overrides = {
        field.name: getattr(args, field.name)
        for field in fields(Params)
        if getattr(args, field.name, None) is not None
    }
    return DEFAULT.replace(**overrides)


#: Chordal tolerance used when triangulating for STL and 3MF. The coupon gets a
#: coarser one: its engraved digits otherwise generate tens of thousands of
#: triangles for no benefit, and 0.01 mm of deviation is an order of magnitude
#: below what the printer can resolve anyway.
FINE_TOLERANCE = 0.001
COARSE_TOLERANCE = 0.01


def export_part(
    part: Part,
    out_dir: Path,
    stem: str,
    step: bool = True,
    tolerance: float = FINE_TOLERANCE,
) -> list[Path]:
    """Write ``part`` as STL and 3MF, and optionally STEP.

    STL is what every slicer accepts, 3MF carries the units so nothing is
    scaled by accident, and STEP keeps the real surfaces for later CAD work.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []

    stl_path = out_dir / f"{stem}.stl"
    export_stl(part, stl_path, tolerance=tolerance)
    written.append(stl_path)

    mesh_path = out_dir / f"{stem}.3mf"
    mesher = Mesher(unit=Unit.MM)
    mesher.add_shape(part, linear_deflection=tolerance)
    mesher.write(mesh_path)
    written.append(mesh_path)

    if step:
        step_path = out_dir / f"{stem}.step"
        export_step(part, step_path)
        written.append(step_path)

    return written


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="spicy-box-export",
        description="Generate the spice carousel and its calibration coupon.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUT,
        help=f"directory for the exported files (default: {DEFAULT_OUT})",
    )
    parser.add_argument(
        "--only",
        choices=("carousel", "coupon", "both"),
        default="both",
        help="which parts to export (default: both)",
    )
    parser.add_argument(
        "--preview",
        action="store_true",
        help="also render shaded PNG views, handy without a slicer at hand",
    )
    parser.add_argument(
        "--no-step",
        action="store_true",
        help="skip the STEP export, which is the slowest of the three",
    )
    _add_param_options(parser)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    params = params_from_args(args)

    try:
        params.validate()
    except ValueError as error:
        print(f"invalid parameters: {error}")
        return 2

    print(params.summary())

    if params.max_footprint > params.usable_bed:
        print(
            f"warning: {params.max_footprint:.1f} mm across does not fit the "
            f"{params.usable_bed:.0f} mm of usable bed"
        )

    written: list[Path] = []

    if args.only in ("carousel", "both"):
        carousel = build_carousel(params)
        written += export_part(carousel, args.out, "spicy_box", step=not args.no_step)
        if args.preview:
            from spicy_box.preview import render_views

            written += render_views(carousel, args.out, "spicy_box")

    if args.only in ("coupon", "both"):
        coupon = build_tolerance_coupon(params)
        written += export_part(
            coupon,
            args.out,
            "tolerance_coupon",
            step=not args.no_step,
            tolerance=COARSE_TOLERANCE,
        )

    print()
    for path in written:
        print(f"wrote {path} ({path.stat().st_size / 1024:.0f} kB)")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
