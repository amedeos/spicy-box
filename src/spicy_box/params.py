"""Every dimension of the spice carousel lives here.

The model code never hard-codes a number: it reads measured values and derived
properties from :class:`Params`. Changing a tube size or the slot count is
therefore a one-line edit followed by a re-export.

All lengths are millimetres and all angles are degrees, matching build123d.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from math import pi, sin
from typing import Literal, get_args

WindowTop = Literal["pointed", "arch", "open"]

#: Extrusion width of a 0.4 mm nozzle. Wall thicknesses are kept to multiples of
#: this value so the slicer can fill them with whole perimeters.
EXTRUSION_WIDTH = 0.4


@dataclass(frozen=True)
class Params:
    """Parameters of the carousel, grouped by where the numbers come from."""

    # --- Measured on the actual tubes -------------------------------------
    #: Outer diameter of the tube body. Calipers read 19.95 mm; rounded up.
    tube_dia: float = 20.0
    #: Length of the tube body without the cap.
    tube_body_len: float = 180.0
    #: The cap sits flush with the body and adds only a couple of millimetres.
    cap_len: float = 2.5

    # --- Layout -----------------------------------------------------------
    #: Number of pockets, one per tube. Raise it if the set grows.
    n_slots: int = 5
    #: Fraction of the tube length that the holder covers. At 0.4 the tube
    #: stands 112 mm proud: the label reads easily, there is plenty to grab,
    #: and the print is a fifth shorter than at 0.5.
    holder_height_ratio: float = 0.40

    # --- Fit --------------------------------------------------------------
    #: Diametral gap between pocket and tube, measured with the calibration
    #: coupon on a Prusa MK4 at 0.2 mm layers rather than estimated: 0.7 mm
    #: drawn came out best, with 1.0 already loose enough to rattle. Remember
    #: that FDM prints holes roughly 0.2-0.3 mm undersize, so the gap you feel
    #: is smaller than the figure here. Re-run the coupon after changing
    #: printer, filament or slicer profile.
    clearance: float = 0.7

    # --- Structure --------------------------------------------------------
    #: Thinnest wall in the load-bearing body; six extrusions wide.
    wall_min: float = 6 * EXTRUSION_WIDTH
    #: Thinnest material allowed on the top face, where the mouth chamfers and
    #: the top chamfer all bite into the same wall. It is deliberately smaller
    #: than :attr:`wall_min`, because this edge carries nothing, but it still
    #: has to be three extrusions wide: anything thinner is a knife edge that
    #: the slicer cannot fill with real perimeters and that is unpleasant to
    #: put a hand on.
    rim_wall_min: float = 3 * EXTRUSION_WIDTH
    #: Solid material under each pocket.
    floor: float = 3.0
    #: Height of the closed lower band, measured from the bed. It wraps the
    #: pockets over the stretch where the tubes rest and forms the stiffest
    #: ring of the part. Note that this and :attr:`rim_height` are absolute, so
    #: the window is whatever height is left between them: shortening the
    #: holder takes millimetres from the window alone.
    band_height: float = 40.0
    #: Height of the uninterrupted ring at the top. Without it the windows
    #: would split the upper edge into separate tabs and the part would flex.
    rim_height: float = 8.0
    #: Tangential width of the windows cut into the upper part.
    window_width: float = 12.0
    #: How much narrower than the tube each window must stay on either side, so
    #: that the pocket remains a C-shaped channel the tube cannot escape from.
    retention_margin: float = 2.0
    #: Shape of the window head. "pointed" keeps every overhang at 45 degrees,
    #: so the part prints without support. See :attr:`window_top` handling in
    #: ``model.py`` for what the other two cost.
    window_top: WindowTop = "pointed"
    #: Lead-in chamfer at the pocket mouth, so a tube drops in without aiming.
    mouth_chamfer: float = 1.0
    #: Chamfers on the outer silhouette. A fillet at the bottom would overhang;
    #: a chamfer at 45 degrees does not.
    bottom_chamfer: float = 1.2
    top_chamfer: float = 0.8
    #: Extra radius added to the foot, blended over :attr:`flare_height`.
    #: Left at zero because the tubes are light plastic rather than glass.
    base_flare: float = 0.0
    flare_height: float = 12.0
    #: Diameter of an optional bore down the middle. Zero leaves the core
    #: solid, which costs little filament because the slicer fills it with
    #: sparse infill; raise it if you want a central compartment.
    core_bore_dia: float = 0.0
    #: Shortest length of tube that must stay above the rim. A holder that
    #: swallows almost the whole tube is technically printable but you cannot
    #: get hold of what is inside it.
    min_protrusion: float = 20.0
    #: How far a cutting body is pushed past the surface it cuts through.
    #: Coincident faces are the classic way to make a boolean fail or leave a
    #: sliver behind, so every cut deliberately overshoots.
    cut_overshoot: float = 1.0

    # --- Printer ----------------------------------------------------------
    #: Usable bed size, used by the tests to confirm the part still fits.
    bed_size: float = 220.0
    #: Margin kept clear at the edges of the bed.
    bed_margin: float = 10.0

    # --- Derived ----------------------------------------------------------

    @property
    def tube_total_len(self) -> float:
        """Overall tube length, cap included."""
        return self.tube_body_len + self.cap_len

    @property
    def pocket_dia(self) -> float:
        """Diameter of the cut pocket."""
        return self.tube_dia + self.clearance

    @property
    def mouth_dia(self) -> float:
        """Diameter the pocket opens out to on the top face.

        The lead-in chamfer widens the mouth, and it is this larger circle —
        not the pocket itself — that decides how much material is left between
        neighbouring pockets where a hand actually touches the part.
        """
        return self.pocket_dia + 2 * self.mouth_chamfer

    @property
    def pitch_radius(self) -> float:
        """Radius of the circle the pocket centres sit on.

        Derived from the tightest of the two walls it has to respect: the chord
        between adjacent centres must leave :attr:`rim_wall_min` between the
        chamfered mouths on the top face, and :attr:`wall_min` between the
        pockets themselves lower down.
        """
        needed = max(self.mouth_dia + self.rim_wall_min, self.pocket_dia + self.wall_min)
        return needed / (2 * sin(pi / self.n_slots))

    @property
    def outer_radius(self) -> float:
        """Outer radius of the body, excluding any base flare.

        Sized the same way as :attr:`pitch_radius`: the top chamfer eats into
        the outer edge just as the mouth chamfer eats into the inner one, so
        both are accounted for before the wall is measured.
        """
        return self.pitch_radius + max(
            self.mouth_dia / 2 + self.rim_wall_min + self.top_chamfer,
            self.pocket_dia / 2 + self.wall_min,
        )

    @property
    def pocket_wall(self) -> float:
        """Material between two neighbouring pockets, below the chamfers."""
        return 2 * self.pitch_radius * sin(pi / self.n_slots) - self.pocket_dia

    @property
    def rim_wall(self) -> float:
        """Material between two neighbouring mouths, on the top face."""
        return 2 * self.pitch_radius * sin(pi / self.n_slots) - self.mouth_dia

    @property
    def outer_rim_wall(self) -> float:
        """Material between a mouth and the outer edge, on the top face."""
        return (
            self.outer_radius
            - self.top_chamfer
            - self.pitch_radius
            - self.mouth_dia / 2
        )

    @property
    def foot_radius(self) -> float:
        """Outer radius at the very bottom, flare included."""
        return self.outer_radius + self.base_flare

    @property
    def height(self) -> float:
        """Overall height of the holder."""
        return self.holder_height_ratio * self.tube_total_len

    @property
    def pocket_depth(self) -> float:
        """Depth of a pocket, measured from the top face."""
        return self.height - self.floor

    @property
    def tube_protrusion(self) -> float:
        """How much of the tube stands above the rim once it is seated."""
        return self.tube_total_len - self.pocket_depth

    @property
    def core_radius(self) -> float:
        """Radius of the solid core inside the ring of pockets."""
        return self.pitch_radius - self.pocket_dia / 2 - self.wall_min

    @property
    def window_bottom(self) -> float:
        """Height at which the windows start."""
        return self.band_height

    @property
    def window_top_z(self) -> float:
        """Height at which the window opening ends.

        For the ``"open"`` head the window runs past the top face, which
        deliberately interrupts the rim.
        """
        if self.window_top == "open":
            return self.height + self.cut_overshoot
        return self.height - self.rim_height

    @property
    def window_head_height(self) -> float:
        """Vertical room the window head needs above its straight flanks."""
        return 0.0 if self.window_top == "open" else self.window_width / 2

    @property
    def window_shoulder(self) -> float:
        """Height at which the straight flanks of a window stop."""
        return self.window_top_z - self.window_head_height

    @property
    def window_reach(self) -> float:
        """How far a window cutter travels outwards from the pocket axis."""
        return self.foot_radius - self.pitch_radius + self.cut_overshoot

    @property
    def max_footprint(self) -> float:
        """Largest horizontal dimension of the printed part."""
        return 2 * self.foot_radius

    @property
    def usable_bed(self) -> float:
        """Bed size minus the margin kept clear at the edges."""
        return self.bed_size - 2 * self.bed_margin

    def replace(self, **changes: object) -> "Params":
        """Return a copy with some fields overridden."""
        return replace(self, **changes)  # type: ignore[arg-type]

    def validate(self) -> None:
        """Raise :class:`ValueError` if the parameters cannot produce a sane part.

        Two kinds of failure are worth catching here: geometry that makes
        build123d fail deep inside OpenCascade with a message nobody can act
        on, and geometry that builds perfectly but yields a part that does not
        do its job. The second kind is the dangerous one — it only shows up
        after the print.
        """
        # Checked first: every later message would otherwise be computed from a
        # window head this class does not know how to build.
        if self.window_top not in get_args(WindowTop):
            raise ValueError(
                f"unknown window_top: {self.window_top!r}; "
                f"expected one of {', '.join(get_args(WindowTop))}"
            )

        positives = (
            "tube_dia",
            "tube_body_len",
            "wall_min",
            "rim_wall_min",
            "floor",
            "rim_height",
            "window_width",
            "cut_overshoot",
        )
        for name in positives:
            if getattr(self, name) <= 0:
                raise ValueError(f"{name} must be positive, got {getattr(self, name)}")

        non_negatives = (
            "clearance",
            "cap_len",
            "band_height",
            "mouth_chamfer",
            "bottom_chamfer",
            "top_chamfer",
            "base_flare",
            "retention_margin",
        )
        for name in non_negatives:
            if getattr(self, name) < 0:
                raise ValueError(
                    f"{name} cannot be negative, got {getattr(self, name)}"
                )

        if self.n_slots < 3:
            raise ValueError(f"n_slots must be at least 3, got {self.n_slots}")
        if self.base_flare > 0 and self.flare_height <= 0:
            raise ValueError("a base flare needs a positive flare_height")

        if self.pocket_depth <= 0:
            raise ValueError(
                f"floor ({self.floor}) leaves no depth inside a holder "
                f"{self.height:.1f} mm tall"
            )
        if self.tube_protrusion < self.min_protrusion:
            raise ValueError(
                f"only {self.tube_protrusion:.1f} mm of tube would stand above "
                f"the rim, less than the {self.min_protrusion:.1f} mm needed to "
                "grab it; lower holder_height_ratio"
            )
        if self.core_radius <= 0:
            raise ValueError(
                f"{self.n_slots} pockets of {self.pocket_dia:.1f} mm leave no "
                "core in the middle; reduce n_slots or pocket size"
            )
        if self.core_bore_dia / 2 >= self.core_radius:
            raise ValueError(
                f"core_bore_dia ({self.core_bore_dia}) breaks into the pockets; "
                f"keep it below {2 * self.core_radius:.1f} mm"
            )

        # Retention is a property of the tube, not of the pocket: widening the
        # clearance must never be allowed to widen the opening past the tube it
        # is supposed to hold on to.
        window_limit = self.tube_dia - 2 * self.retention_margin
        if self.window_width > window_limit:
            raise ValueError(
                f"window_width ({self.window_width}) must stay at or below "
                f"{window_limit:.1f} mm — {self.retention_margin} mm inside the "
                f"{self.tube_dia} mm tube on each side — or the pockets no "
                "longer retain a tube"
            )

        # The head sits above the straight flanks, so a window needs room for
        # both. Checking only the opening would let the flanks run backwards.
        if self.window_bottom >= self.window_shoulder:
            raise ValueError(
                f"no room for a window: its flanks would run from "
                f"{self.window_bottom:.1f} mm up to {self.window_shoulder:.1f} mm; "
                "lower band_height, lower rim_height, or narrow window_width"
            )

        if self.bottom_chamfer >= self.floor:
            raise ValueError(
                f"bottom_chamfer ({self.bottom_chamfer}) reaches above the "
                f"{self.floor} mm floor and would open the side of every pocket"
            )
        if self.top_chamfer >= self.rim_height:
            raise ValueError(
                f"top_chamfer ({self.top_chamfer}) eats the whole "
                f"{self.rim_height} mm rim"
            )

        # These three cannot fail while pitch_radius and outer_radius are
        # derived as they are, but they are the invariants those formulas exist
        # to hold, so they are asserted rather than assumed.
        if self.pocket_wall < self.wall_min - 1e-9:
            raise ValueError(
                f"only {self.pocket_wall:.2f} mm between neighbouring pockets, "
                f"below wall_min ({self.wall_min})"
            )
        if self.rim_wall < self.rim_wall_min - 1e-9:
            raise ValueError(
                f"only {self.rim_wall:.2f} mm between neighbouring mouths on the "
                f"top face, below rim_wall_min ({self.rim_wall_min})"
            )
        if self.outer_rim_wall < self.rim_wall_min - 1e-9:
            raise ValueError(
                f"only {self.outer_rim_wall:.2f} mm between a mouth and the outer "
                f"edge, below rim_wall_min ({self.rim_wall_min})"
            )

    def summary(self) -> str:
        """A short, human-readable report of the resulting geometry."""
        return "\n".join(
            [
                f"tubes        : {self.n_slots} pockets for "
                f"{self.tube_dia:.1f} x {self.tube_total_len:.1f} mm tubes",
                f"pocket       : {self.pocket_dia:.1f} mm wide, "
                f"{self.pocket_depth:.1f} mm deep "
                f"({self.clearance:.1f} mm clearance)",
                f"body         : {self.max_footprint:.1f} mm across, "
                f"{self.height:.1f} mm tall",
                f"thinnest wall: {self.pocket_wall:.1f} mm between pockets, "
                f"{self.rim_wall:.1f} mm between mouths on the top face",
                f"tube sticks out by {self.tube_protrusion:.1f} mm",
                f"bed          : {self.max_footprint:.1f} mm of "
                f"{self.usable_bed:.0f} mm usable",
            ]
        )


DEFAULT = Params()
