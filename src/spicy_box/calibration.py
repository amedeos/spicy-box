"""A small test coupon for finding the right pocket clearance.

Hole diameters come out of an FDM printer roughly 0.2-0.3 mm smaller than
drawn, and the exact figure depends on the printer, the filament and the
slicer profile. Rather than guessing, print this coupon first: it takes a few
minutes, it holds a row of pockets cut with different clearances, and the one
that lets a tube drop in and out comfortably is the value to put into
:attr:`Params.clearance`.

The coupon reproduces the same mouth chamfer as the real part, so the feel of
inserting a tube matches what the carousel will do.
"""

from __future__ import annotations

from build123d import (
    Align,
    Circle,
    Axis,
    Box,
    Cylinder,
    GeomType,
    Locations,
    Part,
    Pos,
    Text,
    chamfer,
    extrude,
)

from spicy_box.params import DEFAULT, Params

#: Clearances sampled by the coupon, bracketing the default of 1.0 mm.
CLEARANCES = (0.4, 0.7, 1.0, 1.3, 1.6)

#: Fonts tried in order. A missing font is silently substituted by the system,
#: and some substitutes produce glyph outlines that cannot be extruded into a
#: valid solid, so each candidate is tested rather than trusted.
FONT_CANDIDATES = ("DejaVu Sans", "Noto Sans", "Liberation Sans", "Arial")

#: Height of the coupon. Deep enough to judge the fit, shallow enough to print
#: in minutes.
THICKNESS = 12.0

#: Depth of the engraved numbers.
ENGRAVE_DEPTH = 0.6


def _engravable(text: str, size: float) -> Part | None:
    """Return a solid for ``text``, or ``None`` if no available font works.

    Fonts are not merely resolved but tried: the substitute a system picks for a
    missing font sometimes yields outlines that extrude into an invalid solid,
    which would quietly corrupt the whole coupon.
    """
    for font in FONT_CANDIDATES:
        try:
            sketch = Text(text, font_size=size, font=font)
        except Exception:  # pragma: no cover - depends on the host's fonts
            continue
        if sketch.area <= 0:
            continue
        solid = extrude(sketch, amount=ENGRAVE_DEPTH)
        if solid.is_valid:
            return solid
    return None


def _dots(count: int, size: float) -> Part:
    """A row of ``count`` engraved dots, used when no usable font is installed."""
    radius = size / 6
    spacing = size / 2
    span = spacing * (count - 1)
    marks = Locations(*[(spacing * i - span / 2, 0) for i in range(count)])
    return extrude(marks * Circle(radius), amount=ENGRAVE_DEPTH)


def build_tolerance_coupon(
    p: Params = DEFAULT, clearances: tuple[float, ...] = CLEARANCES
) -> Part:
    """Build the calibration coupon.

    Args:
        p: parameters supplying the tube diameter and the mouth chamfer, so the
            coupon matches the real pockets.
        clearances: the diametral gaps to sample, in millimetres.

    Returns:
        A flat plate with one pocket per clearance, each labelled with its
        value in millimetres.
    """
    if not clearances:
        raise ValueError("the coupon needs at least one clearance to test")

    widest = p.tube_dia + max(clearances)
    pitch = widest + 2 * p.wall_min
    text_size = min(6.0, pitch * 0.28)
    length = pitch * len(clearances)
    width = pitch + text_size + 2 * p.wall_min

    # Pockets sit towards one edge, leaving a strip free for the labels.
    pocket_offset = (width - pitch) / 2
    positions = [
        (pitch * (i - (len(clearances) - 1) / 2), pocket_offset)
        for i in range(len(clearances))
    ]

    plate = Box(length, width, THICKNESS, align=(Align.CENTER, Align.CENTER, Align.MIN))

    for (x, y), clearance in zip(positions, clearances):
        plate -= Pos(x, y, -1) * Cylinder(
            (p.tube_dia + clearance) / 2,
            THICKNESS + 2,
            align=(Align.CENTER, Align.CENTER, Align.MIN),
        )

    if p.mouth_chamfer > 0:
        mouths = [
            edge
            for edge in plate.edges().filter_by(GeomType.CIRCLE).group_by(Axis.Z)[-1]
        ]
        plate = chamfer(mouths, p.mouth_chamfer)

    label_y = -width / 2 + p.wall_min + text_size / 2
    for index, ((x, _), clearance) in enumerate(zip(positions, clearances)):
        mark = _engravable(f"{clearance:.1f}", text_size)
        if mark is None:  # pragma: no cover - only on a host without usable fonts
            mark = _dots(index + 1, text_size)
        plate -= Pos(x, label_y, THICKNESS - ENGRAVE_DEPTH) * mark

    return plate
