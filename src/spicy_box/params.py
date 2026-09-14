"""Every dimension of the spice carousel lives here.

The model code never hard-codes a number: it reads measured values and derived
properties from :class:`Params`. Changing a tube size or the slot count is
therefore a one-line edit followed by a re-export.

All lengths are millimetres and all angles are degrees, matching build123d.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from math import pi, sin
from typing import Literal

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
    #: Number of pockets. Six gives the five tubes a spare slot.
    n_slots: int = 6
    #: Fraction of the tube length that the holder covers. Half the tube stays
    #: exposed, which keeps the label readable and the tube easy to grab.
    holder_height_ratio: float = 0.5

    # --- Fit --------------------------------------------------------------
    #: Diametral gap between pocket and tube. Generous on purpose: a pocket cut
    #: to the exact tube diameter behaves like a piston and defeats the whole
    #: point of a grab-and-go holder. Note that FDM prints holes roughly
    #: 0.2-0.3 mm undersize, so the effective gap is smaller than this figure.
    clearance: float = 1.0

    # --- Structure --------------------------------------------------------
    #: Thinnest wall anywhere in the part; six times the extrusion width.
    wall_min: float = 2.4
    #: Solid material under each pocket.
    floor: float = 3.0
    #: Height of the closed lower band that gives the carousel its stability.
    band_height: float = 40.0
    #: Height of the uninterrupted ring at the top. Without it the windows
    #: would split the upper edge into separate tabs and the part would flex.
    rim_height: float = 8.0
    #: Tangential width of the windows cut into the upper part.
    window_width: float = 12.0
    #: Shape of the window head. "pointed" keeps every overhang at 45 degrees,
    #: so the part prints without support.
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
    #: Shortest length of tube that must stay above the rim. A holder that
    #: swallows almost the whole tube is technically printable but you cannot
    #: get hold of what is inside it.
    min_protrusion: float = 20.0
    #: Diameter of an optional bore down the middle. Zero leaves the core
    #: solid, which costs little filament because the slicer fills it with
    #: sparse infill; raise it if you want a central compartment.
    core_bore_dia: float = 0.0

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
    def pitch_radius(self) -> float:
        """Radius of the circle the pocket centres sit on.

        Derived from the requirement that neighbouring pockets keep at least
        ``wall_min`` of material between them: the chord between two adjacent
        centres must be at least ``pocket_dia + wall_min``.
        """
        return (self.pocket_dia + self.wall_min) / (2 * sin(pi / self.n_slots))

    @property
    def outer_radius(self) -> float:
        """Outer radius of the body, excluding any base flare."""
        return self.pitch_radius + self.pocket_dia / 2 + self.wall_min

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
            return self.height + 1.0
        return self.height - self.rim_height

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

        These are the constraints that silently ruin the geometry rather than
        making it fail loudly, so they are worth checking up front.
        """
        if self.n_slots < 3:
            raise ValueError(f"n_slots must be at least 3, got {self.n_slots}")
        if self.tube_dia <= 0:
            raise ValueError(f"tube_dia must be positive, got {self.tube_dia}")
        if self.clearance < 0:
            raise ValueError(f"clearance cannot be negative, got {self.clearance}")
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
        # A window wider than this turns the pocket into an open cradle and the
        # tube falls out sideways instead of being held in a C-shaped channel.
        window_limit = self.pocket_dia - 2 * self.wall_min
        if self.window_width >= window_limit:
            raise ValueError(
                f"window_width ({self.window_width}) must stay below "
                f"{window_limit:.1f} mm or the pockets no longer retain a tube"
            )
        if self.window_top != "open" and self.window_bottom >= self.window_top_z:
            raise ValueError(
                f"no room left for a window between {self.window_bottom} mm and "
                f"{self.window_top_z:.1f} mm; lower band_height or rim_height"
            )
        if self.window_top not in ("pointed", "arch", "open"):
            raise ValueError(f"unknown window_top: {self.window_top!r}")
        if self.mouth_chamfer >= self.wall_min:
            raise ValueError(
                f"mouth_chamfer ({self.mouth_chamfer}) would eat through the "
                f"{self.wall_min} mm wall between pockets"
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
                f"tube sticks out by {self.tube_protrusion:.1f} mm",
                f"bed          : {self.max_footprint:.1f} mm of "
                f"{self.usable_bed:.0f} mm usable",
            ]
        )


DEFAULT = Params()
