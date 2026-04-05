import pygame
import os

def test_parse():
    pygame.init()
    # Need a display for some pygame functions, hidden
    pygame.display.set_mode((100, 100), pygame.HIDDEN)
    
    path = r"c:\Users\jdogg\.gemini\antigravity\scratch\beat_em_up\assets\images\player.png"
    sheet = pygame.image.load(path).convert_alpha()
    
    # 1. Chroma key green (Top left pixel)
    bg_color = sheet.get_at((0, 0))
    print(f"BG Color: {bg_color}")
    
    # Fast threshold (remove colors close to bg_color)
    pygame.transform.threshold(
        dest_surf=sheet,
        surf=sheet,
        search_color=bg_color,
        threshold=(40, 40, 40, 255),
        set_color=(0, 0, 0, 0),
        set_behavior=1
    )
    
    # 2. Get masks
    mask = pygame.mask.from_surface(sheet)
    rects = mask.get_bounding_rects()
    print(f"Initial rects: {len(rects)}")
    
    # 3. Merge rects
    def merge_rects(rects, margin):
        merged = []
        for r in rects:
            if r.width < 5 or r.height < 5: continue
            inflated = r.inflate(margin, margin)
            intersected = False
            for i, m in enumerate(merged):
                if inflated.colliderect(m):
                    merged[i] = m.union(r)
                    intersected = True
                    break
            if not intersected:
                merged.append(r)
        return merged
    
    merged = merge_rects(rects, 40)
    merged = merge_rects(merged, 40)
    print(f"Merged rects: {len(merged)}")
    
    # 4. Group into rows
    merged.sort(key=lambda r: r.y)
    rows = []
    current_row = []
    
    if not merged:
        print("No rects found!")
        return
        
    last_y = merged[0].y
    for r in merged:
        if abs(r.y - last_y) > 80: # generic row height leeway
            rows.append(current_row)
            current_row = []
            last_y = r.y
        current_row.append(r)
    rows.append(current_row)
    
    print(f"Found {len(rows)} rows.")
    for i, r in enumerate(rows):
        print(f"Row {i} has {len(r)} frames.")
        for j, frame in enumerate(r):
            print(f"  Frame {j}: {frame}")
            
test_parse()
