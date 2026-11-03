# Modified for MahjongCopilotPlus on 2026-11-03; see NOTICE.md.
"""Map the game's 16:9 drawing area within a resizable browser viewport."""


def fit_game_rect(width, height, canvas=None):
    left, top, area_width, area_height = 0.0, 0.0, float(width), float(height)
    if canvas and canvas.get('width', 0) > 0 and canvas.get('height', 0) > 0:
        left = max(0.0, float(canvas['x']))
        top = max(0.0, float(canvas['y']))
        area_width = min(float(canvas['width']), width - left)
        area_height = min(float(canvas['height']), height - top)
    scale = max(1.0, min(area_width / 16, area_height / 9))
    return (left + (area_width - scale * 16) / 2,
            top + (area_height - scale * 9) / 2, scale * 16, scale * 9)
