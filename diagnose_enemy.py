"""
Diagnostic: prints per-frame bounding boxes extracted from enemy.png
Run with: python diagnose_enemy.py
"""
import pygame, os, sys
from collections import Counter

pygame.init()
pygame.display.set_mode((100, 100), pygame.HIDDEN)

IMAGE_PATH = os.path.join('assets', 'images', 'enemy.png')
sheet = pygame.image.load(IMAGE_PATH).convert_alpha()
w, h = sheet.get_size()
print(f"Sheet size: {w} x {h}")

# --- Chroma key ----------------------------------------------------------------
clean = pygame.Surface((w, h), pygame.SRCALPHA)
clean.fill((0, 0, 0, 0))
px = pygame.PixelArray(sheet)
cx = pygame.PixelArray(clean)
corners = [px[0, 0], px[w-1, 0], px[0, h-1], px[w-1, h-1]]
bg_color = Counter(corners).most_common(1)[0][0]
bg_r, bg_g, bg_b, _ = sheet.unmap_rgb(bg_color)
print(f"Detected BG color: ({bg_r}, {bg_g}, {bg_b})")

for x in range(w):
    for y in range(h):
        c = px[x, y]
        r, g, b, _ = sheet.unmap_rgb(c)
        if abs(r - bg_r) + abs(g - bg_g) + abs(b - bg_b) > 150:
            cx[x, y] = c
px.close()
cx.close()

# --- Grid slicing (3 equal rows) ----------------------------------------------
h_row = h // 3
row_defs = [
    ('walk',  8, 0,        h_row),
    ('aim',   4, h_row,    h_row * 2),
    ('shoot', 6, h_row*2,  h),
]

print("\n--- Per-frame bounding boxes ---")
for state, frame_count, y_start, y_end in row_defs:
    cell_w = w // frame_count
    row_h  = y_end - y_start
    print(f"\n[{state}]  grid cell: {cell_w} x {row_h}  (y {y_start}–{y_end})")
    for i in range(frame_count):
        cell_rect = pygame.Rect(i * cell_w, y_start, cell_w, row_h)
        cell_surf = clean.subsurface(cell_rect)
        mask  = pygame.mask.from_surface(cell_surf)
        bounds = mask.get_bounding_rects()

        if not bounds:
            print(f"  frame {i}: EMPTY")
            continue

        text_filtered = [b for b in bounds if b.height > 40]
        if not text_filtered:
            print(f"  frame {i}: only small specks / text")
            continue

        tight = text_filtered[0]
        for b in text_filtered[1:]:
            tight = tight.union(b)

        # local coords inside cell
        local_cx = tight.x + tight.width / 2.0
        offset_from_center = local_cx - (cell_w / 2.0)
        print(f"  frame {i}: local({tight.x},{tight.y}) size({tight.width}x{tight.height}) "
              f"cx={local_cx:.1f}  drift_from_cell_center={offset_from_center:+.1f}px")
