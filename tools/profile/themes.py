"""Colour themes for the profile SVGs: (main, accent).

Pick one with   python render.py --theme blue    or   PROFILE_THEME=blue python render.py
(the GitHub Action uses DEFAULT unless you set PROFILE_THEME in the workflow).
The city's roofs and windows are derived from the main colour automatically.
"""
import colorsys

THEMES = {
    "cyan":   ("#00d9ff", "#ff2bd6"),   # original neon console
    "green":  ("#3fb950", "#e3b341"),
    "orange": ("#ff9f1c", "#ff2bd6"),
    "violet": ("#bc8cff", "#00d9ff"),
    "red":    ("#ff4d6d", "#ffd166"),   # red / yellow
    "blue":   ("#2f81f7", "#7df9ff"),
}
DEFAULT = "red"


def _hex(h, s, l):
    r, g, b = colorsys.hls_to_rgb(h, l, s)
    return "#%02x%02x%02x" % (round(r * 255), round(g * 255), round(b * 255))


def city_palette(main):
    """Roofs (dark→bright), lit windows (front/side) and wall shades, all in the main colour's hue."""
    r, g, b = (int(main[i:i + 2], 16) / 255 for i in (1, 3, 5))
    h, _l, _s = colorsys.rgb_to_hls(r, g, b)
    return {
        "roofs": [_hex(h, .75, .22), _hex(h, .75, .36), _hex(h, .8, .52), _hex(h, .9, .62)],
        "win_on": _hex(h, 1, .78), "win_side": _hex(h, .8, .62),
        "wall_l": _hex(h, .35, .17), "wall_r": _hex(h, .4, .11),
    }
