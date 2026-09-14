"""Shaded previews of the part, so the shape can be checked without a slicer.

This is a development aid rather than part of the deliverable: it triangulates
the solid and draws it with matplotlib, which is enough to spot a window in the
wrong place or a pocket that never got cut.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from build123d import Part

#: Views rendered by default, as (name, elevation, azimuth) in degrees.
VIEWS = (("iso", 24.0, -58.0), ("front", 4.0, -90.0), ("top", 88.0, -90.0))


def _eye_vector(elev: float, azim: float) -> np.ndarray:
    """Unit vector pointing from the scene towards the camera."""
    e, a = np.radians(elev), np.radians(azim)
    return np.array([np.cos(e) * np.cos(a), np.cos(e) * np.sin(a), np.sin(e)])


def _triangles(part: Part, tolerance: float = 0.12) -> np.ndarray:
    """Return the part's surface as an ``(n, 3, 3)`` array of triangle corners."""
    vertices, faces = part.tessellate(tolerance)
    points = np.array([(v.X, v.Y, v.Z) for v in vertices])
    return points[np.array(faces)]


def render(part: Part, path: Path, elev: float, azim: float, size: int = 900) -> Path:
    """Draw one shaded view of ``part`` and write it to ``path``."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection

    tris = _triangles(part)

    normals = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
    lengths = np.linalg.norm(normals, axis=1, keepdims=True)
    normals = np.divide(normals, lengths, out=np.zeros_like(normals), where=lengths > 0)

    # matplotlib's own depth sorting is unreliable on a shape with this many
    # concave features, so facets pointing away from the camera are dropped and
    # the rest are drawn back to front by hand.
    eye = _eye_vector(elev, azim)
    facing = normals @ eye
    keep = facing > 0
    tris, normals = tris[keep], normals[keep]
    order = np.argsort(tris.mean(axis=1) @ eye)
    tris, normals = tris[order], normals[order]

    # Flat shading: brightness follows the angle between each facet normal and a
    # light sitting over the viewer's shoulder.
    light = eye + np.array([0.0, 0.0, 0.45])
    light /= np.linalg.norm(light)
    shade = 0.28 + 0.72 * np.clip(normals @ light, 0, 1)
    colours = np.stack([shade * 0.93, shade * 0.62, shade * 0.30, np.ones_like(shade)], axis=1)

    fig = plt.figure(figsize=(size / 100, size / 100), dpi=100)
    ax = fig.add_subplot(projection="3d")
    faces = Poly3DCollection(tris, facecolors=colours, linewidths=0)
    ax.add_collection3d(faces)

    corners = tris.reshape(-1, 3)
    centre = (corners.max(axis=0) + corners.min(axis=0)) / 2
    reach = (corners.max(axis=0) - corners.min(axis=0)).max() / 2
    for axis, mid in zip("xyz", centre):
        getattr(ax, f"set_{axis}lim")(mid - reach, mid + reach)
    ax.set_box_aspect((1, 1, 1))
    ax.view_init(elev=elev, azim=azim)
    ax.set_axis_off()

    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, bbox_inches="tight", pad_inches=0.05, facecolor="white")
    plt.close(fig)
    return path


def render_views(part: Part, out_dir: Path, stem: str = "carousel") -> list[Path]:
    """Render every view in :data:`VIEWS` and return the files written."""
    return [
        render(part, out_dir / f"{stem}_{name}.png", elev, azim)
        for name, elev, azim in VIEWS
    ]
