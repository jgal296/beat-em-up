"""
Auto-detect frame counts and boundaries per row using vertical density profiles.
Writes results to detect_frames.txt
"""
import pygame, os
from collections import Counter

pygame.init()
pygame.display.set_mode((100, 100), pygame.HIDDEN)

sheet = pygame.image.load(os.path.join('assets', 'images', 'enemy.png')).convert_alpha()
w, h = sheet.get_size()

# --- Chroma key ---
clean = pygame.Surface((w, h), pygame.SRCALPHA)
clean.fill((0, 0, 0, 0))
px = pygame.PixelArray(sheet)
cx = pygame.PixelArray(clean)
corners = [px[0, 0], px[w-1, 0], px[0, h-1], px[w-1, h-1]]
bg_color = Counter(corners).most_common(1)[0][0]
bg_r, bg_g, bg_b, _ = sheet.unmap_rgb(bg_color)
for x in range(w):
    for y in range(h):
        c = px[x, y]
        r, g, b, _ = sheet.unmap_rgb(c)
        if abs(r - bg_r) + abs(g - bg_g) + abs(b - bg_b) > 150:
            cx[x, y] = c
px.close()
cx.close()

h_row = h // 3
rows = [
    ('walk',  0,        h_row),
    ('aim',   h_row,    h_row * 2),
    ('shoot', h_row*2,  h),
]

lines = [f"Sheet: {w}x{h}  h_row={h_row}", ""]

for state, y_start, y_end in rows:
    row_h = y_end - y_start
    row_surf = clean.subsurface(pygame.Rect(0, y_start, w, row_h))
    row_mask = pygame.mask.from_surface(row_surf)

    # Column density: count occupied pixels per column
    col_density = []
    for x in range(w):
        cnt = sum(1 for y in range(row_h) if row_mask.get_at((x, y)))
        col_density.append(cnt)

    # Find columns that are totally empty (density == 0) — these are natural gaps
    empty_cols = [x for x, d in enumerate(col_density) if d == 0]

    # Group empty columns into contiguous gap bands
    gaps = []
    if empty_cols:
        g_start = empty_cols[0]
        g_prev  = empty_cols[0]
        for x in empty_cols[1:]:
            if x == g_prev + 1:
                g_prev = x
            else:
                gaps.append((g_start, g_prev))
                g_start = x
                g_prev  = x
        gaps.append((g_start, g_prev))

    # Filter out very narrow / edge gaps (< 3px wide)
    real_gaps = [(a, b) for a, b in gaps if b - a >= 2]

    # Frame count = number of gap-separated segments
    # Build frame segments from gaps
    segments = []
    prev_end = 0
    for ga, gb in real_gaps:
        if ga > prev_end:
            segments.append((prev_end, ga))
        prev_end = gb + 1
    if prev_end < w:
        segments.append((prev_end, w))

    # Filter trivially small segments (< 20px wide — likely margin pixels)
    segments = [(a, b) for a, b in segments if b - a >= 20]

    lines.append(f"[{state}] y={y_start}-{y_end}")
    lines.append(f"  Gap bands ({len(real_gaps)} total): {real_gaps}")
    lines.append(f"  Frame segments ({len(segments)}): {segments}")
    lines.append(f"  => DETECTED FRAME COUNT: {len(segments)}")

    # Also report tight bounding box per segment
    for i, (sx, ex) in enumerate(segments):
        seg_surf = clean.subsurface(pygame.Rect(sx, y_start, ex - sx, row_h))
        seg_mask = pygame.mask.from_surface(seg_surf)
        bbs = [b for b in seg_mask.get_bounding_rects() if b.height > 40]
        if bbs:
            t = bbs[0]
            for b in bbs[1:]: t = t.union(b)
            lines.append(f"    frame {i}: x={sx}-{ex} ({ex-sx}px)  tight={t.width}x{t.height}")
        else:
            lines.append(f"    frame {i}: x={sx}-{ex} ({ex-sx}px)  NO CHAR")
    lines.append("")

output = "\n".join(lines)
with open('detect_frames.txt', 'w', encoding='utf-8') as f:
    f.write(output)
print(output)
