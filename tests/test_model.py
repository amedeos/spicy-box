"""Checks that the generated geometry is actually printable and usable.

A bounding box and a volume only tell you that *something* was built. The tests
that matter here are the functional ones: a tube must fit in every pocket, and
every pocket must open to the outside through its window.
"""

from __future__ import annotations

import math

import pytest
from build123d import Align, Cylinder, GeomType, Part, Pos, Rot

from spicy_box.calibration import build_tolerance_coupon, clearance_ladder
from spicy_box.cli import main
from spicy_box.model import build_carousel
from spicy_box.params import DEFAULT, Params

LADDER = clearance_ladder(DEFAULT)

#: Slack for comparing derived dimensions. The radii are exact in algebra but
#: land a few ulps either side of the rule once trigonometry is involved, which
#: is why validate() compares with the same slack.
EPS = 1e-9

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
        rod = self._radial_rod(0, DEFAULT.height - DEFAULT.rim_height / 2)
        assert (part & rod).volume < NEGLIGIBLE


class TestParams:
    def test_defaults_are_consistent(self) -> None:
        DEFAULT.validate()
        assert DEFAULT.pocket_dia == pytest.approx(21.0)
        assert DEFAULT.pocket_depth < DEFAULT.tube_total_len

    def test_pitch_is_set_by_whichever_wall_is_tightest(self) -> None:
        """At the defaults the chamfered mouths bind before the pockets do."""
        chord = 2 * DEFAULT.pitch_radius * math.sin(math.pi / DEFAULT.n_slots)
        assert chord - DEFAULT.mouth_dia == pytest.approx(DEFAULT.rim_wall_min)
        assert DEFAULT.pocket_wall > DEFAULT.wall_min

    def test_no_wall_is_thinner_than_its_rule(self) -> None:
        """The top face is where three chamfers eat into the same material."""
        assert DEFAULT.rim_wall >= DEFAULT.rim_wall_min - EPS
        assert DEFAULT.outer_rim_wall >= DEFAULT.rim_wall_min - EPS
        assert DEFAULT.pocket_wall >= DEFAULT.wall_min - EPS
        # Three extrusions is the point of rim_wall_min: a thinner rib is a
        # knife edge the slicer cannot fill with real perimeters.
        assert DEFAULT.rim_wall >= 3 * 0.4 - EPS

    def test_a_wider_mouth_chamfer_widens_the_carousel(self) -> None:
        """The chamfer must push the pockets apart, not eat the wall between."""
        wider = DEFAULT.replace(mouth_chamfer=2.0)
        wider.validate()
        assert wider.rim_wall == pytest.approx(DEFAULT.rim_wall)
        assert wider.max_footprint > DEFAULT.max_footprint

    def test_a_window_that_would_release_the_tube_is_refused(self) -> None:
        # Measured against the tube, not the pocket: opening up the clearance
        # must never buy permission for a wider window.
        too_wide = DEFAULT.tube_dia - DEFAULT.retention_margin
        with pytest.raises(ValueError, match="no longer retain a tube"):
            DEFAULT.replace(window_width=too_wide).validate()

    def test_clearance_cannot_buy_a_wider_window(self) -> None:
        loose = DEFAULT.replace(clearance=6.0, window_width=20.5)
        with pytest.raises(ValueError, match="no longer retain a tube"):
            loose.validate()

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
        expected = {round(DEFAULT.tube_dia + c, 2) for c in LADDER}
        assert bores == expected

    def test_tubes_pass_through_every_hole(self, coupon: Part) -> None:
        box = coupon.bounding_box()
        pitch = box.size.X / len(LADDER)
        for index, _ in enumerate(LADDER):
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
        assert genus == len(LADDER)


class TestRejectedParameters:
    """One test per hole found in review: each of these built something wrong.

    All of them need a non-default value, but every one is a documented command
    line flag, so a user following the README could reach them.
    """

    def test_a_zero_floor_would_let_the_tubes_fall_through(self) -> None:
        # pocket_depth only grows as floor shrinks, so the depth check alone
        # never noticed that the pockets had become through holes.
        with pytest.raises(ValueError, match="floor must be positive"):
            DEFAULT.replace(floor=0.0).validate()
        with pytest.raises(ValueError, match="floor must be positive"):
            DEFAULT.replace(floor=-5.0).validate()

    def test_a_band_reaching_the_window_shoulder_is_refused(self) -> None:
        # Above this the window profile would be built with a negative height,
        # which build123d takes the absolute value of: the window reappeared
        # mirrored, eating into the closed band.
        assert DEFAULT.window_shoulder == pytest.approx(
            DEFAULT.window_top_z - DEFAULT.window_width / 2
        )
        with pytest.raises(ValueError, match="no room for a window"):
            DEFAULT.replace(band_height=80.0).validate()

    def test_the_open_head_is_checked_for_room_as_well(self) -> None:
        # The room check used to exempt "open" entirely.
        with pytest.raises(ValueError, match="no room for a window"):
            DEFAULT.replace(window_top="open", band_height=200.0).validate()
        # A holder shorter than its own band: the window profile ended up
        # floating entirely above the part, which built a solid with no windows.
        short = DEFAULT.replace(window_top="open", holder_height_ratio=0.2)
        assert short.height < short.band_height
        with pytest.raises(ValueError, match="no room for a window"):
            short.validate()

    def test_a_bottom_chamfer_that_would_open_the_pockets_is_refused(self) -> None:
        with pytest.raises(ValueError, match="reaches above"):
            DEFAULT.replace(bottom_chamfer=8.0).validate()

    def test_a_top_chamfer_that_would_eat_the_rim_is_refused(self) -> None:
        with pytest.raises(ValueError, match="eats the whole"):
            DEFAULT.replace(top_chamfer=9.0).validate()

    def test_negative_structural_dimensions_are_refused(self) -> None:
        for field, message in (
            ("rim_height", "rim_height must be positive"),
            ("wall_min", "wall_min must be positive"),
            ("window_width", "window_width must be positive"),
            ("tube_dia", "tube_dia must be positive"),
        ):
            with pytest.raises(ValueError, match=message):
                DEFAULT.replace(**{field: -5.0}).validate()

    def test_a_mistyped_window_head_says_so_first(self) -> None:
        # This check runs before any that computes window_top_z, otherwise a
        # typo surfaced as an unrelated complaint about band_height.
        with pytest.raises(ValueError, match="unknown window_top"):
            DEFAULT.replace(window_top="gothic", rim_height=60.0).validate()

    def test_a_flare_needs_a_height_to_blend_over(self) -> None:
        with pytest.raises(ValueError, match="positive flare_height"):
            DEFAULT.replace(base_flare=8.0, flare_height=0.0).validate()


class TestChamferedVariantsStillBuild:
    """Values that used to crash inside OpenCascade with an opaque message."""

    @pytest.mark.parametrize(
        "changes",
        [
            {"mouth_chamfer": 1.2},
            {"mouth_chamfer": 2.0},
            {"mouth_chamfer": 1.0, "top_chamfer": 1.5},
            {"mouth_chamfer": 0.0},
        ],
    )
    def test_chamfer_combinations(self, changes: dict) -> None:
        p = DEFAULT.replace(**changes)
        p.validate()
        part = build_carousel(p)
        assert part.is_valid and len(part.solids()) == 1
        assert p.rim_wall >= p.rim_wall_min - EPS


class TestAdvertisedVariants:
    """Options the README tells users to run, which no test used to build."""

    @pytest.mark.parametrize(
        "changes",
        [
            {"window_top": "arch"},
            {"window_top": "open"},
            {"base_flare": 8.0},
            {"core_bore_dia": 14.0},
            {"n_slots": 8},
            {"holder_height_ratio": 0.35, "band_height": 20.0},
        ],
    )
    def test_variant_is_a_single_valid_solid(self, changes: dict) -> None:
        part = build_carousel(DEFAULT.replace(**changes))
        assert part.is_valid
        assert len(part.solids()) == 1

    def test_a_flared_foot_is_the_widest_point(self) -> None:
        """The bottom chamfer must land on the flare, not on the buried edge."""
        flared = DEFAULT.replace(base_flare=8.0)
        part = build_carousel(flared)
        box = part.bounding_box()
        assert box.size.X == pytest.approx(flared.max_footprint, abs=2 * flared.bottom_chamfer)
        assert box.size.X > DEFAULT.max_footprint

    def test_a_central_bore_removes_material_without_opening_a_pocket(self) -> None:
        bored = DEFAULT.replace(core_bore_dia=14.0)
        part = build_carousel(bored)
        assert part.volume < build_carousel(DEFAULT).volume
        tube = Pos(bored.pitch_radius, 0, bored.floor) * Cylinder(
            bored.tube_dia / 2, bored.pocket_depth, align=BOTTOM_UP
        )
        assert (part & tube).volume < NEGLIGIBLE


class TestClearanceLadder:
    def test_it_is_centred_on_the_clearance_in_use(self) -> None:
        assert clearance_ladder(DEFAULT) == (0.4, 0.7, 1.0, 1.3, 1.6)
        assert clearance_ladder(DEFAULT.replace(clearance=1.6)) == (
            1.0,
            1.3,
            1.6,
            1.9,
            2.2,
        )

    def test_rungs_at_or_below_zero_are_dropped(self) -> None:
        assert clearance_ladder(DEFAULT.replace(clearance=0.3)) == (0.3, 0.6, 0.9)

    def test_a_ladder_with_no_positive_rung_is_refused(self) -> None:
        # Only reachable by calling the ladder directly: build_tolerance_coupon
        # validates first, and validate() rejects a negative clearance.
        with pytest.raises(ValueError, match="no positive rungs"):
            clearance_ladder(DEFAULT.replace(clearance=-5.0))

    def test_the_ladder_rejects_a_nonsense_shape(self) -> None:
        with pytest.raises(ValueError, match="at least one rung"):
            clearance_ladder(DEFAULT, count=0)
        with pytest.raises(ValueError, match="step must be positive"):
            clearance_ladder(DEFAULT, step=0.0)

    def test_the_coupon_follows_the_ladder(self) -> None:
        p = DEFAULT.replace(clearance=1.6)
        coupon = build_tolerance_coupon(p)
        bores = {
            round(edge.radius * 2, 2)
            for edge in coupon.edges().filter_by(GeomType.CIRCLE)
            if edge.center().Z < 1e-6
        }
        assert bores == {round(p.tube_dia + c, 2) for c in clearance_ladder(p)}


class TestPreview:
    """The preview module had no test, which is how a dead sort survived in it."""

    def test_it_renders_every_view(self, carousel: Part, tmp_path) -> None:
        matplotlib = pytest.importorskip("matplotlib")
        from spicy_box.preview import VIEWS, render_views

        written = render_views(carousel, tmp_path, "check")
        assert len(written) == len(VIEWS)
        for path in written:
            assert path.exists()
            # A PNG, not an empty file or a stub.
            assert path.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
            assert path.stat().st_size > 5_000
        assert matplotlib.get_backend().lower() == "agg"

    def test_back_facing_triangles_are_dropped(self, carousel: Part) -> None:
        """The cull is what makes the renders readable; the sort was not."""
        import numpy as np

        from spicy_box.preview import _eye_vector, _triangles

        tris = _triangles(carousel)
        normals = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
        eye = _eye_vector(24.0, -58.0)
        kept = int((normals @ eye > 0).sum())
        assert 0 < kept < len(tris)


class TestCliErrorPaths:
    def test_a_rejected_parameter_exits_cleanly(self, tmp_path, capsys) -> None:
        code = main(["--out", str(tmp_path), "--floor", "0"])
        assert code == 2
        assert "floor must be positive" in capsys.readouterr().out
        assert not list(tmp_path.iterdir())

    def test_integer_options_stay_integers(self, tmp_path) -> None:
        """--n-slots must not arrive as a float and blow up in PolarLocations."""
        from spicy_box.cli import build_parser, params_from_args

        args = build_parser().parse_args(["--n-slots", "8"])
        assert params_from_args(args).n_slots == 8
        assert isinstance(params_from_args(args).n_slots, int)

    def test_every_parameter_is_reachable_from_the_command_line(self) -> None:
        from dataclasses import fields

        from spicy_box.cli import build_parser

        flags = set()
        for action in build_parser()._actions:
            flags.update(action.option_strings)
        for field in fields(Params):
            assert "--" + field.name.replace("_", "-") in flags

    def test_a_missing_preview_extra_is_explained_not_raised(
        self, tmp_path, capsys, monkeypatch
    ) -> None:
        """matplotlib is optional, so --preview must degrade rather than crash.

        The geometry is already on disk by the time previews are attempted, so
        the run is a success apart from the pictures.
        """
        import sys

        monkeypatch.delitem(sys.modules, "spicy_box.preview", raising=False)
        for name in ("matplotlib", "matplotlib.pyplot", "mpl_toolkits"):
            monkeypatch.setitem(sys.modules, name, None)

        code = main(["--out", str(tmp_path), "--only", "carousel", "--no-step", "--preview"])

        assert code == 0
        assert "optional extra" in capsys.readouterr().out
        written = sorted(path.suffix for path in tmp_path.iterdir())
        assert written == [".3mf", ".stl"]
