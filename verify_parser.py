"""Verify corrected equal-width grid: walk=6, aim=4, shoot=6."""
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
row_defs = [
    ('walk',  6, 0,        h_row),
    ('aim',   4, h_row,    h_row * 2),
    ('shoot', 6, h_row*2,  h),
]

all_ok = True
results = []
for state, frame_count, y_start, y_end in row_defs:
    row_h  = y_end - y_start
    cell_w = w // frame_count
    found  = 0
    frame_info = []
    for i in range(frame_count):
        x0 = i * cell_w
        x1 = w if i == frame_count - 1 else (i + 1) * cell_w
        cell_surf = clean.subsurface(pygame.Rect(x0, y_start, x1 - x0, row_h))
        cell_mask = pygame.mask.from_surface(cell_surf)
        bbs = [b for b in cell_mask.get_bounding_rects() if b.height > 40]
        if bbs:
            t = bbs[0]
            for b in bbs[1:]: t = t.union(b)
            found += 1
            frame_info.append(f"frame{i}: cell_w={x1-x0}px tight={t.width}x{t.height}")
        else:
            frame_info.append(f"frame{i}: cell_w={x1-x0}px EMPTY")
            all_ok = False
    status = "OK" if found == frame_count else f"PROBLEM: only {found}/{frame_count} found"
    results.append(f"[{state}] cell_w={cell_w} {status}")
    for fi in frame_info:
        results.append(f"  {fi}")

for r in results:
    print(r)

if all_ok:
    print("\n=== ALL FRAMES FOUND ===")
else:
    print("\n=== SOME FRAMES MISSING ===")
