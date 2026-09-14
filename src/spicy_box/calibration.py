"""A small test coupon for finding the right pocket clearance.

Hole diameters come out of an FDM printer roughly 0.2-0.3 mm smaller than
drawn, and the exact figure depends on the printer, the filament and the
slicer profile. Rather than guessing, print this coupon first: it takes a few
minutes, it holds a row of pockets cut with different clearances, and the one
that lets a tube drop in and out comfortably is the value to put into
:attr:`Params.clearance`.

The ladder of clearances is centred on the value currently in use, so the
coupon stays useful after the first calibration round: re-running it on a new
filament brackets the setting you already have instead of repeating a fixed
range that may now sit entirely to one side of it.

The coupon reproduces the same mouth chamfer as the real part, so the feel of
inserting a tube matches what the carousel will do.
"""

from __future__ import annotations

from build123d import (
    Align,
    Axis,
    Box,
    Circle,
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

#: Spacing between neighbouring rungs of the clearance ladder.
LADDER_STEP = 0.3

#: How many clearances the coupon samples.
LADDER_COUNT = 5

#: Fonts tried in order. A missing font is silently substituted by the system,
#: and some substitutes produce glyph outlines that cannot be extruded into a
#: valid solid, so each candidate is tested rather than trusted.
FONT_CANDIDATES = ("DejaVu Sans", "Noto Sans", "Liberation Sans", "Arial")

#: Height of the coupon. Deep enough to judge the fit, shallow enough to print
#: in minutes.
THICKNESS = 12.0

#: Depth of the engraved numbers.
ENGRAVE_DEPTH = 0.6


def clearance_ladder(
    p: Params = DEFAULT, step: float = LADDER_STEP, count: int = LADDER_COUNT
) -> tuple[float, ...]:
    """Return the clearances to sample, centred on the one currently in use.

    Rungs that would come out at or below zero are dropped, so a very tight
    setting simply yields a shorter ladder rather than an impossible hole.
    """
    if count < 1:
        raise ValueError(f"the ladder needs at least one rung, got {count}")
    if step <= 0:
        raise ValueError(f"the ladder step must be positive, got {step}")

    middle = (count - 1) / 2
    rungs = [round(p.clearance + step * (index - middle), 2) for index in range(count)]
    usable = tuple(value for value in rungs if value > 0)
    if not usable:
        raise ValueError(
            f"a clearance of {p.clearance} mm with a step of {step} mm produces "
            "no positive rungs to test"
        )
    return usable


def _engravable(text: str, size: float, height: float) -> Part | None:
    """Return a solid for ``text``, or ``None`` if no available font works.

    Fonts are not merely resolved but tried: the substitute a system picks for a
    missing font sometimes yields outlines that cannot be turned into a valid
    solid. Both the outline and the extrusion are attempted inside the guard,
    because OpenCascade may either return something invalid or raise outright,
    depending on how the glyph is malformed.
    """
    for font in FONT_CANDIDATES:
        try:
            sketch = Text(text, font_size=size, font=font)
            if sketch.area <= 0:
                continue
            solid = extrude(sketch, amount=height)
        except Exception:  # pragma: no cover - depends on the host's fonts
            continue
        if solid.is_valid:
            return solid
    return None


def _dots(count: int, size: float, height: float) -> Part:
    """A row of ``count`` engraved dots, used when no usable font is installed."""
    radius = size / 6
    spacing = size / 2
    span = spacing * (count - 1)
    marks = Locations(*[(spacing * index - span / 2, 0) for index in range(count)])
    return extrude(marks * Circle(radius), amount=height)


def build_tolerance_coupon(
    p: Params = DEFAULT, clearances: tuple[float, ...] | None = None
) -> Part:
    """Build the calibration coupon.

    Args:
        p: parameters supplying the tube diameter, the mouth chamfer and the
            clearance the ladder is centred on, so the coupon matches the real
            pockets.
        clearances: the diametral gaps to sample, in millimetres. Defaults to
            :func:`clearance_ladder` for ``p``.

    Returns:
        A flat plate with one pocket per clearance, each labelled with its
        value in millimetres.
    """
    p.validate()
    if clearances is None:
        clearances = clearance_ladder(p)
    if not clearances:
        raise ValueError("the coupon needs at least one clearance to test")
    if min(clearances) <= 0:
        raise ValueError(f"every clearance must be positive, got {clearances}")

    widest = p.tube_dia + max(clearances)
    pitch = widest + 2 * p.wall_min
    text_size = min(6.0, pitch * 0.28)
    length = pitch * len(clearances)
    width = pitch + text_size + 2 * p.wall_min

    # Pockets sit towards one edge, leaving a strip free for the labels.
    pocket_offset = (width - pitch) / 2
    positions = [
        (pitch * (index - (len(clearances) - 1) / 2), pocket_offset)
        for index in range(len(clearances))
    ]

    plate = Box(length, width, THICKNESS, align=(Align.CENTER, Align.CENTER, Align.MIN))

    for (x, y), clearance in zip(positions, clearances):
        plate -= Pos(x, y, -p.cut_overshoot) * Cylinder(
            (p.tube_dia + clearance) / 2,
            THICKNESS + 2 * p.cut_overshoot,
            align=(Align.CENTER, Align.CENTER, Align.MIN),
        )

    if p.mouth_chamfer > 0:
        mouths = plate.edges().filter_by(GeomType.CIRCLE).group_by(Axis.Z)[-1]
        plate = chamfer(mouths, p.mouth_chamfer)

    # The engraving stands proud of the top face before being subtracted, so the
    # boolean never has to resolve two coincident planes.
    mark_height = ENGRAVE_DEPTH + p.cut_overshoot
    label_y = -width / 2 + p.wall_min + text_size / 2
    for index, ((x, _), clearance) in enumerate(zip(positions, clearances)):
        mark = _engravable(f"{clearance:.1f}", text_size, mark_height)
        if mark is None:  # pragma: no cover - only on a host without usable fonts
            mark = _dots(index + 1, text_size, mark_height)
        plate -= Pos(x, label_y, THICKNESS - ENGRAVE_DEPTH) * mark

    return plate
