"""Geometry of the spice carousel.

The part is built as one solid so it can be printed upright in a single piece,
with no support material anywhere:

* the pockets are blind vertical bores, which is the easiest feature an FDM
  printer can produce;
* the pocket mouths are chamfered, so the opening widens upwards and never
  overhangs;
* the outer silhouette uses chamfers rather than fillets at the bottom, because
  a fillet there would curl under;
* the windows have a pointed head, so their topmost surfaces stay at 45 degrees
  instead of bridging across the opening.
"""

from __future__ import annotations

from build123d import (
    Align,
    Axis,
    Cone,
    Cylinder,
    GeomType,
    Part,
    Plane,
    Polygon,
    PolarLocations,
    Pos,
    Sketch,
    Circle,
    Rectangle,
    chamfer,
    extrude,
)

from spicy_box.params import DEFAULT, Params

BOTTOM_UP = (Align.CENTER, Align.CENTER, Align.MIN)


def _window_profile(p: Params) -> Sketch:
    """The outline of one window, drawn in the tangential/vertical plane.

    The straight flanks run from :attr:`Params.window_bottom` upwards; the head
    on top is what keeps the opening printable without support.
    """
    half = p.window_width / 2
    top = p.window_top_z

    if p.window_top == "open":
        # A plain slot that runs past the top face and interrupts the rim.
        height = top - p.window_bottom
        return Plane.YZ * Pos(0, p.window_bottom + height / 2) * Rectangle(
            p.window_width, height
        )

    shoulder = top - half
    flanks = Plane.YZ * Pos(0, (p.window_bottom + shoulder) / 2) * Rectangle(
        p.window_width, shoulder - p.window_bottom
    )

    if p.window_top == "arch":
        # A half-round crown. Only the single topmost point is horizontal, which
        # any printer bridges over without trouble.
        return flanks + Plane.YZ * Pos(0, shoulder) * Circle(half)

    # "pointed": two flanks meeting at 45 degrees, the safest head of the three.
    peak = Plane.YZ * Polygon(
        (-half, shoulder),
        (half, shoulder),
        (0, top),
        align=None,
    )
    return flanks + peak


def _pocket_cutters(p: Params) -> Part:
    """The six blind bores that hold the tubes."""
    pocket = Pos(0, 0, p.floor) * Cylinder(
        p.pocket_dia / 2, p.pocket_depth + 1, align=BOTTOM_UP
    )
    return PolarLocations(p.pitch_radius, p.n_slots) * pocket


def _window_cutters(p: Params) -> Part:
    """Prisms that open each pocket towards the outside of the body."""
    # Extruded from the pocket axis radially outwards, far enough to clear the
    # outer surface even when the foot is flared.
    reach = p.foot_radius - p.pitch_radius + 1
    cutter = extrude(_window_profile(p), amount=reach)
    return PolarLocations(p.pitch_radius, p.n_slots) * cutter


def _outer_body(p: Params) -> Part:
    """The plain body, chamfered top and bottom, before anything is cut out."""
    body = Cylinder(p.outer_radius, p.height, align=BOTTOM_UP)

    if p.base_flare > 0:
        body += Cone(
            p.foot_radius, p.outer_radius, p.flare_height, align=BOTTOM_UP
        )

    circles = body.edges().filter_by(GeomType.CIRCLE)
    if p.bottom_chamfer > 0:
        body = chamfer(circles.group_by(Axis.Z)[0], p.bottom_chamfer)
    if p.top_chamfer > 0:
        top_circle = body.edges().filter_by(GeomType.CIRCLE).group_by(Axis.Z)[-1]
        body = chamfer(top_circle, p.top_chamfer)

    return body


def build_carousel(p: Params = DEFAULT) -> Part:
    """Build the carousel and return it as a single solid.

    Args:
        p: the parameter set to build from. It is validated first, so an
            impossible combination fails here rather than in the slicer.

    Returns:
        A :class:`~build123d.Part` standing on the XY plane, ready to export.
    """
    p.validate()

    body = _outer_body(p)

    if p.core_bore_dia > 0:
        body -= Pos(0, 0, p.floor) * Cylinder(
            p.core_bore_dia / 2, p.height, align=BOTTOM_UP
        )

    body -= _pocket_cutters(p)

    if p.mouth_chamfer > 0:
        mouths = [
            edge
            for edge in body.edges().filter_by(GeomType.CIRCLE).group_by(Axis.Z)[-1]
            if abs(edge.radius - p.pocket_dia / 2) < 1e-6
        ]
        if len(mouths) != p.n_slots:
            raise RuntimeError(
                f"expected {p.n_slots} pocket mouths to chamfer, found {len(mouths)}"
            )
        body = chamfer(mouths, p.mouth_chamfer)

    body -= _window_cutters(p)

    return body
