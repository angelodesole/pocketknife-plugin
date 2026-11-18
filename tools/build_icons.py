"""Builds the Pocket Knife icons (SVG sources and PNG exports).

Command icons follow the Rhino 9 design language: neutral geometry, and only
the element produced or changed by the command in the color of its category
(Open Color palette). Each command icon has a light and a dark variant.

Usage:
    python tools/build_icons.py

Requires ``cairosvg`` for the PNG export (``pip install cairosvg``).
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SVG_DIR = ROOT / "icons" / "svg"
PNG_DIR = ROOT / "icons" / "png"

# Open Color: https://yeun.github.io/open-color/
BLUE = "#339af0"  # NURBS geometry (points, curves, surfaces, solids).
LIME = "#82c91e"  # Transform and edit.
ORANGE = "#ff922b"  # Attributes (layers, materials, colors).

THEMES = {
    "light": {"line": "#343a40", "fill": "#e9ecef", "soft": "#adb5bd"},
    "dark": {"line": "#dee2e6", "fill": "#495057", "soft": "#868e96"},
}

COMMAND_PNG_SIZES = (16, 24, 32, 48, 64)
LOGO_PNG_SIZES = (16, 32, 48, 64, 128, 256, 512)

STROKE = 'stroke-width="1.25" stroke-linejoin="round" stroke-linecap="round"'


def _svg(body: str, size: int = 24) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" '
        f'viewBox="0 0 {size} {size}">\n{body}\n</svg>\n'
    )


def _sheet(x: float, y: float, w: float, h: float) -> str:
    """Isometric layer sheet (rhombus) with its left corner at (x, y)."""
    return f"{x},{y} {x + w / 2},{y - h / 2} {x + w},{y} {x + w / 2},{y + h / 2}"


def icon_layer_color_from_material(t: dict) -> str:
    """Layer stack whose top sheet takes the color of a material sphere."""
    line, fill = t["line"], t["fill"]
    sheets = "".join(
        f'<polygon points="{_sheet(2.5, y, 15, 7.5)}" fill="{fill}" '
        f'stroke="{line}" {STROKE}/>'
        for y in (17.5, 14)
    )
    top = (
        f'<polygon points="{_sheet(2.5, 10.5, 15, 7.5)}" fill="{ORANGE}" '
        f'stroke="{line}" {STROKE}/>'
    )
    sphere = (
        f'<circle cx="18" cy="6" r="4.25" fill="{ORANGE}" stroke="{line}" {STROKE}/>'
        '<circle cx="16.6" cy="4.7" r="1.3" fill="#ffffff" fill-opacity="0.75"/>'
    )
    return _svg(sheets + top + sphere)


def icon_copy_to_layer_copy(t: dict) -> str:
    """Original layer stack and its copy, offset, in the edit color."""
    line, fill = t["line"], t["fill"]

    def stack(x: float, y: float, color: str) -> str:
        return "".join(
            f'<polygon points="{_sheet(x, y + dy, 12, 6)}" fill="{color}" '
            f'stroke="{line}" {STROKE}/>'
            for dy in (3.5, 0)
        )

    arrow = (
        f'<path d="M5 13.5 C5 17.5 7 19 10 19" fill="none" stroke="{line}" {STROKE}/>'
        f'<path d="M8.5 17 L10.5 19 L8.5 21" fill="none" stroke="{line}" {STROKE}/>'
    )
    return _svg(stack(1.5, 6, fill) + stack(10.5, 14, LIME) + arrow)


def icon_inner_point(t: dict) -> str:
    """Concave shape: the centroid falls outside, the inner point inside."""
    line, fill, soft = t["line"], t["fill"], t["soft"]
    shape = (
        f'<polygon points="2.5,2.5 21.5,2.5 21.5,8 12,8 12,16 21.5,16 21.5,21.5 '
        f'2.5,21.5" fill="{fill}" stroke="{line}" {STROKE}/>'
    )
    centroid = (
        f'<path d="M14.5 10.5 L17 13 M17 10.5 L14.5 13" stroke="{soft}" '
        f'stroke-width="1.25" stroke-linecap="round"/>'
    )
    circle = (
        f'<circle cx="7.25" cy="12" r="4.1" fill="none" stroke="{BLUE}" '
        'stroke-width="1" stroke-dasharray="1.6 1.2"/>'
    )
    point = (
        f'<circle cx="7.25" cy="12" r="1.9" fill="{BLUE}" stroke="{line}" {STROKE}/>'
    )
    return _svg(shape + centroid + circle + point)


def icon_min_bounding_box(t: dict) -> str:
    """Tilted object wrapped by a tight box drawn in the NURBS color."""
    line, fill = t["line"], t["fill"]
    # Box in a cabinet-like projection, tilted to suggest an oriented box.
    back = "6,2.5 21.5,6 18,21.5 2.5,18"
    faces = (
        f'<polygon points="{back}" fill="{BLUE}" fill-opacity="0.18" '
        f'stroke="{BLUE}" stroke-width="1.25" stroke-linejoin="round"/>'
    )
    obj = (
        f'<polygon points="6.5,8 13,5.8 17.5,11 15.8,17.6 9,16.4 5.6,12.4" '
        f'fill="{fill}" stroke="{line}" {STROKE}/>'
        f'<path d="M6.5 8 L11.5 11.4 L17.5 11 M11.5 11.4 L9 16.4" fill="none" '
        f'stroke="{line}" {STROKE}/>'
    )
    corners = "".join(
        f'<circle cx="{x}" cy="{y}" r="1.3" fill="{BLUE}"/>'
        for x, y in ((6, 2.5), (21.5, 6), (18, 21.5), (2.5, 18))
    )
    return _svg(faces + obj + corners)


def icon_min_bounding_rect(t: dict) -> str:
    """Top view: irregular outline and its tight rotated rectangle."""
    line, fill = t["line"], t["fill"]
    rect = (
        '<polygon points="1.8,9.6 15.6,1.8 22.2,13.4 8.4,21.2" '
        f'fill="{BLUE}" fill-opacity="0.15" stroke="{BLUE}" stroke-width="1.25" '
        'stroke-linejoin="round"/>'
    )
    shape = (
        '<polygon points="8.7,5.7 13,4.6 18.2,6.4 16.4,11 18.1,15.7 11,17 '
        f'4.4,14.2 6.2,10" fill="{fill}" stroke="{line}" {STROKE}/>'
    )
    return _svg(rect + shape)


def icon_orient_to_min_rect(t: dict) -> str:
    """Rotated ghost rectangle turning into an X-aligned one."""
    line, soft = t["line"], t["soft"]
    ghost = (
        f'<polygon points="4,7.6 14.2,2 17.2,7.4 7,13" fill="none" stroke="{soft}" '
        'stroke-width="1" stroke-dasharray="1.6 1.2" stroke-linejoin="round"/>'
    )
    final = (
        f'<rect x="3" y="14" width="18" height="6.5" rx="0.5" fill="{LIME}" '
        f'stroke="{line}" {STROKE}/>'
    )
    arrow = (
        f'<path d="M18.6 5.2 C21.6 7.4 22 10 20.4 12" fill="none" stroke="{line}" '
        f"{STROKE}/>"
        f'<path d="M18.2 11.6 L20.4 12.2 L21.2 10" fill="none" stroke="{line}" '
        f"{STROKE}/>"
    )
    axis = f'<path d="M2 22.5 H22" stroke="{soft}" stroke-width="1"/>'
    return _svg(ghost + final + arrow + axis)


COMMAND_ICONS = {
    "pkLayerColorFromMaterial": icon_layer_color_from_material,
    "pkCopyToLayerCopy": icon_copy_to_layer_copy,
    "pkInnerPoint": icon_inner_point,
    "pkMinBoundingBox": icon_min_bounding_box,
    "pkMinBoundingRect": icon_min_bounding_rect,
    "pkOrientToMinRect": icon_orient_to_min_rect,
}


def plugin_logo() -> str:
    """Plug-in logo: a minimal 3D pocket knife, half open.

    Large, simple masses and strong value contrast keep it readable from
    16 px (Package Manager list) to 512 px.
    """
    return _svg(
        """<defs>
  <linearGradient id="handleTop" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="#74c0fc"/>
    <stop offset="1" stop-color="#228be6"/>
  </linearGradient>
  <linearGradient id="handleSide" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="#1971c2"/>
    <stop offset="1" stop-color="#1864ab"/>
  </linearGradient>
  <linearGradient id="blade" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0" stop-color="#ffffff"/>
    <stop offset="0.55" stop-color="#dee2e6"/>
    <stop offset="1" stop-color="#adb5bd"/>
  </linearGradient>
  <linearGradient id="bladeSide" x1="0" y1="0" x2="1" y2="0">
    <stop offset="0" stop-color="#868e96"/>
    <stop offset="1" stop-color="#495057"/>
  </linearGradient>
  <radialGradient id="shadow" cx="0.5" cy="0.5" r="0.5">
    <stop offset="0" stop-color="#000" stop-opacity="0.28"/>
    <stop offset="1" stop-color="#000" stop-opacity="0"/>
  </radialGradient>
  <radialGradient id="rivet" cx="0.35" cy="0.35" r="0.7">
    <stop offset="0" stop-color="#ffffff"/>
    <stop offset="1" stop-color="#868e96"/>
  </radialGradient>
</defs>
<ellipse cx="128" cy="214" rx="104" ry="16" fill="url(#shadow)"/>
<g transform="translate(0 -22) rotate(-24 128 150)">
  <!-- blade, hinged on the pivot and opened by about 40 degrees -->
  <g transform="translate(52 170) rotate(-40)">
    <path d="M0 -20 L150 -20 Q176 -18 184 -2 Q140 30 58 30 L0 30 Z"
          transform="translate(0 7)" fill="url(#bladeSide)"/>
    <path d="M0 -20 L150 -20 Q176 -18 184 -2 Q140 30 58 30 L0 30 Z"
          fill="url(#blade)" stroke="#495057" stroke-width="4"
          stroke-linejoin="round"/>
    <path d="M16 -9 H146" stroke="#ffffff" stroke-width="5"
          stroke-linecap="round" opacity="0.85"/>
  </g>
  <!-- handle: side (thickness), then top face -->
  <rect x="16" y="150" width="224" height="72" rx="36" fill="url(#handleSide)"/>
  <rect x="16" y="136" width="224" height="68" rx="34" fill="url(#handleTop)"
        stroke="#1864ab" stroke-width="4"/>
  <path d="M84 150 H210" stroke="#ffffff" stroke-width="7" stroke-linecap="round"
        opacity="0.45"/>
  <!-- pivot -->
  <circle cx="52" cy="170" r="16" fill="url(#rivet)" stroke="#495057"
          stroke-width="4"/>
</g>""",
        size=256,
    )


def site_favicon() -> str:
    """Favicon for the project site, in the extrdd.com mood.

    Flat ink disc (like the extrdd.com mark) cut by a blade-shaped slit, with
    automatic dark mode.
    """
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">'
        "<style>.ink{fill:#1C1C1A}.paper{fill:#F5F5F0}"
        "@media (prefers-color-scheme:dark){.ink{fill:#F2F2EC}.paper{fill:#1C1C1A}}"
        "</style>"
        '<circle class="ink" cx="16" cy="16" r="11"/>'
        '<path class="paper" d="M11.2 21.6 L21.6 9.2 C23.2 7.4 25.6 7.9 24.6 10.4 '
        'C22.4 15.6 18.4 19.8 13.4 23.4 Z"/>'
        '<circle class="ink" cx="12.4" cy="22.4" r="1.6"/>'
        "</svg>\n"
    )


def main() -> None:
    """Writes every SVG and exports the PNG sizes."""
    import cairosvg

    for directory in (SVG_DIR, PNG_DIR):
        directory.mkdir(parents=True, exist_ok=True)

    outputs: list[tuple[str, str, tuple[int, ...]]] = []
    for name, draw in COMMAND_ICONS.items():
        for theme, colors in THEMES.items():
            suffix = "" if theme == "light" else "-dark"
            outputs.append((f"{name}{suffix}", draw(colors), COMMAND_PNG_SIZES))
    outputs.append(("pocketknife-logo", plugin_logo(), LOGO_PNG_SIZES))
    outputs.append(("site-favicon", site_favicon(), (16, 32, 180)))

    for name, svg, sizes in outputs:
        (SVG_DIR / f"{name}.svg").write_text(svg, encoding="utf-8")
        for size in sizes:
            cairosvg.svg2png(
                bytestring=svg.encode(),
                write_to=str(PNG_DIR / f"{name}-{size}.png"),
                output_width=size,
                output_height=size,
            )
    print(f"{len(outputs)} icons written to {SVG_DIR.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
