"""
Detect frame boundaries using column density minima (works even when chars touch).
User confirmed: walk=6 frames. We'll verify that and detect aim/shoot counts.
"""
import pygame, os
from collections import Counter

pygame.init()
pygame.display.set_mode((100, 100), pygame.HIDDEN)

sheet = pygame.image.load(os.path.join('assets', 'images', 'enemy.png')).convert_alpha()
w, h = sheet.get_size()

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
    ('walk',  0,      h_row,    6),  # user confirmed 6
    ('aim',   h_row,  h_row*2,  4),  # from gap analysis: 4 real frames
    ('shoot', h_row*2, h,        6),  # user said 6
]

def smooth(arr, k=3):
    """Simple moving average."""
    out = []
    for i in range(len(arr)):
        s = arr[max(0,i-k):i+k+1]
        out.append(sum(s)/len(s))
    return out

def find_n_minima(density, n):
    """
    Place exactly n-1 split points that divide the signal into n segments
    by finding the n-1 lowest local minima.
    """
    # Smooth first
    d = smooth(density, k=5)
    w = len(d)
    # Find all local minima
    minima = []
    for i in range(1, w-1):
        if d[i] <= d[i-1] and d[i] <= d[i+1]:
            minima.append((d[i], i))
    # Sort by density value (lowest first = most likely boundary)
    minima.sort(key=lambda x: x[0])
    
    # Pick the n-1 best minima that are spread out (at least w/(n*2) apart)
    min_sep = w // (n * 2)
    chosen = []
    for val, pos in minima:
        if all(abs(pos - p) >= min_sep for p in chosen):
            chosen.append(pos)
        if len(chosen) == n - 1:
            break
    chosen.sort()
    return chosen

lines = [f"Sheet: {w}x{h}  h_row={h_row}", ""]

for state, y_start, y_end, expected_frames in rows:
    row_h = y_end - y_start
    row_surf = clean.subsurface(pygame.Rect(0, y_start, w, row_h))
    row_mask = pygame.mask.from_surface(row_surf)

    density = [sum(1 for y in range(row_h) if row_mask.get_at((x, y))) for x in range(w)]

    splits = find_n_minima(density, expected_frames)
    # Build segments from splits
    boundaries = [0] + splits + [w]
    segments = list(zip(boundaries[:-1], boundaries[1:]))

    lines.append(f"[{state}] y={y_start}-{y_end}  expected={expected_frames}")
    lines.append(f"  Split columns: {splits}")
    for i, (sx, ex) in enumerate(segments):
        seg_surf = clean.subsurface(pygame.Rect(sx, y_start, ex - sx, row_h))
        seg_mask = pygame.mask.from_surface(seg_surf)
        bbs = [b for b in seg_mask.get_bounding_rects() if b.height > 40]
        if bbs:
            t = bbs[0]
            for b in bbs[1:]: t = t.union(b)
            lines.append(f"    frame {i}: cols {sx}-{ex} ({ex-sx}px)  tight={t.width}x{t.height}")
        else:
            lines.append(f"    frame {i}: cols {sx}-{ex} ({ex-sx}px)  NO CHAR FOUND")
    lines.append("")

output = "\n".join(lines)
with open('detect_frames2.txt', 'w', encoding='utf-8') as f:
    f.write(output)
print(output)
