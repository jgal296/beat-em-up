"""Diagnostic that saves results to a plain text file."""
import pygame, os
from collections import Counter

pygame.init()
pygame.display.set_mode((100, 100), pygame.HIDDEN)

IMAGE_PATH = os.path.join('assets', 'images', 'enemy.png')
sheet = pygame.image.load(IMAGE_PATH).convert_alpha()
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
    ('walk',  8, 0,        h_row),
    ('aim',   4, h_row,    h_row * 2),
    ('shoot', 6, h_row*2,  h),
]

lines = []
lines.append(f"Sheet: {w}x{h}  BG=({bg_r},{bg_g},{bg_b})")
lines.append(f"Row height: {h_row}")
lines.append("")

for state, frame_count, y_start, y_end in row_defs:
    cell_w = w // frame_count
    row_h  = y_end - y_start
    lines.append(f"[{state}] cells={frame_count} cell_w={cell_w} row_h={row_h} y={y_start}-{y_end}")
    for i in range(frame_count):
        cell_rect = pygame.Rect(i * cell_w, y_start, cell_w, row_h)
        cell_surf = clean.subsurface(cell_rect)
        mask  = pygame.mask.from_surface(cell_surf)
        bounds = mask.get_bounding_rects()
        if not bounds:
            lines.append(f"  [{i}] EMPTY")
            continue
        text_filtered = [b for b in bounds if b.height > 40]
        if not text_filtered:
            lines.append(f"  [{i}] only tiny pixels")
            continue
        tight = text_filtered[0]
        for b in text_filtered[1:]:
            tight = tight.union(b)
        local_cx = tight.x + tight.width / 2.0
        drift = local_cx - (cell_w / 2.0)
        lines.append(f"  [{i}] local pos=({tight.x},{tight.y}) size={tight.width}x{tight.height} cx={local_cx:.1f} drift={drift:+.1f}")
    lines.append("")

result = "\n".join(lines)
with open("enemy_diag2.txt", "w") as f:
    f.write(result)
print("DONE")
print(result)
