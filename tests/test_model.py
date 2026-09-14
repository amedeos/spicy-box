"""Checks that the generated geometry is actually printable and usable.

A bounding box and a volume only tell you that *something* was built. The tests
that matter here are the functional ones: a tube must fit in every pocket, and
every pocket must open to the outside through its window.
"""

from __future__ import annotations

import math

import pytest
from build123d import Align, Cylinder, GeomType, Part, Pos, Rot

from spicy_box.calibration import CLEARANCES, build_tolerance_coupon
from spicy_box.cli import main
from spicy_box.model import build_carousel
from spicy_box.params import DEFAULT, Params

BOTTOM_UP = (Align.CENTER, Align.CENTER, Align.MIN)

#: Volume below which an intersection counts as numerical noise rather than a
#: real collision, in cubic millimetres.
NEGLIGIBLE = 1e-3


@pytest.fixture(scope="module")
def carousel() -> Part:
    return build_carousel(DEFAULT)


@pytest.fixture(scope="module")
def coupon() -> Part:
    return build_tolerance_coupon(DEFAULT)


class TestSolid:
    def test_is_a_single_valid_solid(self, carousel: Part) -> None:
        # Loose fragments would slice into stray islands floating in mid-air.
        assert carousel.is_valid
        assert len(carousel.solids()) == 1

    def test_stands_on_the_bed(self, carousel: Part) -> None:
        box = carousel.bounding_box()
        assert box.min.Z == pytest.approx(0, abs=1e-6)
        assert box.max.Z == pytest.approx(DEFAULT.height, abs=1e-6)

    def test_fits_the_printer(self, carousel: Part) -> None:
        box = carousel.bounding_box()
        assert max(box.size.X, box.size.Y) <= DEFAULT.usable_bed


class TestPockets:
    def test_every_pocket_accepts_a_tube(self, carousel: Part) -> None:
        """The real test of the model: drop a tube into each slot and look for
        interference. Volume and bounding box would both stay happy if a pocket
        were missing or offset."""
        for index in range(DEFAULT.n_slots):
            angle = 360 * index / DEFAULT.n_slots
            tube = (
                Rot(0, 0, angle)
                * Pos(DEFAULT.pitch_radius, 0, DEFAULT.floor)
                * Cylinder(DEFAULT.tube_dia / 2, DEFAULT.pocket_depth, align=BOTTOM_UP)
            )
            overlap = (carousel & tube).volume
            assert overlap < NEGLIGIBLE, f"slot {index} pinches the tube"

    def test_pocket_count_and_size(self, carousel: Part) -> None:
        mouths = [
            edge
            for edge in carousel.edges().filter_by(GeomType.CIRCLE)
            if math.isclose(
                edge.radius, DEFAULT.pocket_dia / 2 + DEFAULT.mouth_chamfer, rel_tol=1e-6
            )
        ]
        assert len(mouths) == DEFAULT.n_slots

    def test_a_tube_cannot_reach_the_floor_of_the_part(self, carousel: Part) -> None:
        """There must be solid material under every pocket."""
        probe = Pos(DEFAULT.pitch_radius, 0, 0) * Cylinder(
            DEFAULT.tube_dia / 2, DEFAULT.floor / 2, align=BOTTOM_UP
        )
        assert (carousel & probe).volume > 0


class TestWindows:
    def _radial_rod(self, angle: float, height: float) -> Part:
        reach = DEFAULT.outer_radius - DEFAULT.pitch_radius + 2
        rod = Cylinder(1.0, reach, align=BOTTOM_UP)
        return Rot(0, 0, angle) * Pos(DEFAULT.pitch_radius, 0, height) * Rot(0, 90, 0) * rod

    def test_each_pocket_opens_to_the_outside(self, carousel: Part) -> None:
        mid = (DEFAULT.window_bottom + DEFAULT.window_top_z) / 2
        for index in range(DEFAULT.n_slots):
            angle = 360 * index / DEFAULT.n_slots
            blocked = (carousel & self._radial_rod(angle, mid)).volume
            assert blocked < NEGLIGIBLE, f"window {index} is not cut through"

    def test_material_remains_between_pockets(self, carousel: Part) -> None:
        half_step = 180 / DEFAULT.n_slots
        mid = (DEFAULT.window_bottom + DEFAULT.window_top_z) / 2
        assert (carousel & self._radial_rod(half_step, mid)).volume > 0

    def test_lower_band_stays_closed(self, carousel: Part) -> None:
        low = DEFAULT.window_bottom / 2
        assert (carousel & self._radial_rod(0, low)).volume > 0

    def test_rim_is_continuous(self, carousel: Part) -> None:
        """Windows must stop below the rim, or the top edge splits into tabs."""
        high = DEFAULT.height - DEFAULT.rim_height / 2
        for index in range(DEFAULT.n_slots):
            angle = 360 * index / DEFAULT.n_slots
            assert (carousel & self._radial_rod(angle, high)).volume > 0

    def test_open_head_deliberately_cuts_the_rim(self) -> None:
        part = build_carousel(DEFAULT.replace(window_top="open"))
        rod_height = DEFAULT.height - DEFAULT.rim_height / 2
        reach = DEFAULT.outer_radius - DEFAULT.pitch_radius + 2
        rod = Pos(DEFAULT.pitch_radius, 0, rod_height) * Rot(0, 90, 0) * Cylinder(
            1.0, reach, align=BOTTOM_UP
        )
        assert (part & rod).volume < NEGLIGIBLE


class TestParams:
    def test_defaults_are_consistent(self) -> None:
        DEFAULT.validate()
        assert DEFAULT.pocket_dia == pytest.approx(21.0)
        assert DEFAULT.pocket_depth < DEFAULT.tube_total_len

    def test_wall_between_neighbouring_pockets(self) -> None:
        """The pitch radius is derived so this gap is exactly ``wall_min``."""
        chord = 2 * DEFAULT.pitch_radius * math.sin(math.pi / DEFAULT.n_slots)
        assert chord - DEFAULT.pocket_dia == pytest.approx(DEFAULT.wall_min)

    def test_a_window_that_would_release_the_tube_is_refused(self) -> None:
        too_wide = DEFAULT.pocket_dia - DEFAULT.wall_min
        with pytest.raises(ValueError, match="no longer retain a tube"):
            DEFAULT.replace(window_width=too_wide).validate()

    def test_thick_walls_on_few_slots_leave_no_core(self) -> None:
        # Three pockets still work at the default wall; thickening the wall is
        # what finally closes the middle of the ring.
        DEFAULT.replace(n_slots=3).validate()
        with pytest.raises(ValueError, match="no core"):
            DEFAULT.replace(n_slots=3, wall_min=5.0).validate()

    def test_unknown_window_head_is_refused(self) -> None:
        with pytest.raises(ValueError, match="unknown window_top"):
            DEFAULT.replace(window_top="gothic").validate()

    def test_a_deeper_holder_still_leaves_the_tube_grabbable(self) -> None:
        tall = DEFAULT.replace(holder_height_ratio=0.7)
        tall.validate()
        assert tall.tube_protrusion > 0

    def test_a_holder_you_cannot_grab_from_is_refused(self) -> None:
        # At this ratio the tube still pokes out, but by too little to pull on.
        with pytest.raises(ValueError, match="stand above the rim"):
            DEFAULT.replace(holder_height_ratio=0.95).validate()


class TestCoupon:
    def test_is_valid_and_flat(self, coupon: Part) -> None:
        assert coupon.is_valid
        assert len(coupon.solids()) == 1

    def test_one_hole_per_clearance(self, coupon: Part) -> None:
        bores = {
            round(edge.radius * 2, 2)
            for edge in coupon.edges().filter_by(GeomType.CIRCLE)
            if edge.center().Z < 1e-6
        }
        expected = {round(DEFAULT.tube_dia + c, 2) for c in CLEARANCES}
        assert bores == expected

    def test_tubes_pass_through_every_hole(self, coupon: Part) -> None:
        box = coupon.bounding_box()
        pitch = box.size.X / len(CLEARANCES)
        for index, _ in enumerate(CLEARANCES):
            x = box.min.X + pitch * (index + 0.5)
            centre = [
                edge.center()
                for edge in coupon.edges().filter_by(GeomType.CIRCLE)
                if abs(edge.center().X - x) < pitch / 2 and edge.center().Z < 1e-6
            ]
            assert centre, f"hole {index} is missing"


class TestExport:
    def test_cli_writes_every_format(self, tmp_path) -> None:
        code = main(["--out", str(tmp_path), "--only", "carousel"])
        assert code == 0
        for suffix in ("stl", "3mf", "step"):
            written = tmp_path / f"spicy_box.{suffix}"
            assert written.exists() and written.stat().st_size > 0

    def test_cli_rejects_impossible_parameters(self, tmp_path, capsys) -> None:
        code = main(["--out", str(tmp_path), "--window-width", "25"])
        assert code == 2
        assert "no longer retain a tube" in capsys.readouterr().out


def _stl_topology(path) -> tuple[int, int, int]:
    """Return (vertices, edges, faces) of a binary STL, welding equal corners.

    STL carries no connectivity of its own, so the mesh is rebuilt from the
    coordinates before anything can be said about whether it is closed.
    """
    import struct
    from collections import Counter

    with open(path, "rb") as handle:
        handle.seek(80)
        count = struct.unpack("<I", handle.read(4))[0]
        raw = handle.read(count * 50)

    corners: dict[tuple[float, float, float], int] = {}
    edges: Counter[tuple[int, int]] = Counter()
    for index in range(count):
        block = raw[index * 50 + 12 : index * 50 + 48]
        triangle = struct.unpack("<9f", block)
        ids = []
        for start in (0, 3, 6):
            key = tuple(round(value, 4) for value in triangle[start : start + 3])
            ids.append(corners.setdefault(key, len(corners)))
        for a, b in ((0, 1), (1, 2), (2, 0)):
            edges[tuple(sorted((ids[a], ids[b])))] += 1

    assert all(shared == 2 for shared in edges.values()), "mesh has open edges"
    return len(corners), len(edges), count


class TestExportedMesh:
    """The triangulation can tear even when the underlying solid is sound."""

    def test_carousel_mesh_is_closed_with_one_tunnel_per_pocket(self, tmp_path) -> None:
        assert main(["--out", str(tmp_path), "--only", "carousel", "--no-step"]) == 0
        vertices, edges, faces = _stl_topology(tmp_path / "spicy_box.stl")
        # Every pocket reaches the outside through its window, so each one adds a
        # handle to the surface: genus should equal the number of slots.
        genus = (2 - (vertices - edges + faces)) // 2
        assert genus == DEFAULT.n_slots

    def test_coupon_mesh_is_closed_with_one_hole_per_clearance(self, tmp_path) -> None:
        assert main(["--out", str(tmp_path), "--only", "coupon", "--no-step"]) == 0
        vertices, edges, faces = _stl_topology(tmp_path / "tolerance_coupon.stl")
        genus = (2 - (vertices - edges + faces)) // 2
        assert genus == len(CLEARANCES)
