import pygame
import os
import math
from settings import *
from projectile import Projectile

class Enemy(pygame.sprite.Sprite):
    SHARED_ANIMATIONS = None

    def __init__(self, pos, player_ref, projectile_group):
        super().__init__()
        
        self.player = player_ref
        self.projectile_group = projectile_group
        
        if Enemy.SHARED_ANIMATIONS is None:
            self.import_sprites()
            Enemy.SHARED_ANIMATIONS = self.animations
        else:
            self.animations = Enemy.SHARED_ANIMATIONS
            
        self.frame_index = 0
        self.animation_speed = 0.1
        
        self.image = self.animations['walk'][0]
        self.rect = self.image.get_rect(bottomleft=pos)
        
        # Physics & state
        self.direction = pygame.math.Vector2(0, 0)
        self.speed = 3
        self.gravity = GRAVITY
        
        self.facing_right = True
        self.state = 'walk' # walk, aim, shoot
        self.aim_start_time = 0
        self.has_shot = False
        self.cooldown_end_time = 0

        # Hit flash
        self.hit_flash_until = 0   # ms — enemy flashes white then dies
        
    def import_sprites(self):
        self.animations = {'walk': [], 'aim': [], 'shoot': []}
        
        enemy_image_path = os.path.join(IMAGE_DIR, "enemy.png")
        if not os.path.exists(enemy_image_path):
            self._create_fallback_sprites()
            return

        try:
            sheet = pygame.image.load(enemy_image_path).convert_alpha()
            w, h = sheet.get_size()
            
            clean_sheet = pygame.Surface((w, h), pygame.SRCALPHA)
            clean_sheet.fill((0, 0, 0, 0))
            
            px = pygame.PixelArray(sheet)
            cx = pygame.PixelArray(clean_sheet)
            
            # Smart background detection: read 4 corners and take the most common to avoid top-left text noise!
            corners = [px[0, 0], px[w-1, 0], px[0, h-1], px[w-1, h-1]]
            from collections import Counter
            bg_color = Counter(corners).most_common(1)[0][0]
            bg_r, bg_g, bg_b, _ = sheet.unmap_rgb(bg_color)
            
            for x in range(w):
                for y in range(h):
                    c = px[x, y]
                    r, g, b, _ = sheet.unmap_rgb(c)
                    if abs(r - bg_r) + abs(g - bg_g) + abs(b - bg_b) > 150:
                        if g > r + 15 and g > b + 15:
                            g_clamped = max(r, b)
                            c = sheet.map_rgb((r, g_clamped, b, 255))
                        cx[x, y] = c
            px.close()
            cx.close()

            # --- Row definitions with CORRECT per-animation frame counts ---
            # walk=6, aim=4, shoot=6 (verified from the actual sprite sheet)
            h_row = h // 3
            row_defs = [
                ('walk',  6, 0,        h_row),
                ('aim',   4, h_row,    h_row * 2),
                ('shoot', 6, h_row*2,  h),
            ]

            mapping = {state: [] for state in self.animations}

            for state, frame_count, y_start, y_end in row_defs:
                row_h  = y_end - y_start
                cell_w = w // frame_count   # cell width specific to this row

                for i in range(frame_count):
                    # Strict equal-width cell — no padding overflow between rows
                    x0 = i * cell_w
                    x1 = x1 = min(w, (i + 1) * cell_w)  # last cell gets any remainder
                    if i == frame_count - 1:
                        x1 = w
                    cell_rect = pygame.Rect(x0, y_start, x1 - x0, row_h)
                    cell_surf = clean_sheet.subsurface(cell_rect)
                    cell_mask = pygame.mask.from_surface(cell_surf)
                    bounds    = cell_mask.get_bounding_rects()
                    if not bounds:
                        continue

                    # Drop label text and noise (too short)
                    char_bounds = [b for b in bounds if b.height > 40]
                    if not char_bounds:
                        continue

                    # Union all qualifying rects (captures muzzle flashes, extended limbs)
                    tight = char_bounds[0]
                    for b in char_bounds[1:]:
                        tight = tight.union(b)

                    # Convert cell-local → sheet-absolute
                    abs_rect = pygame.Rect(tight.x + x0, tight.y + y_start,
                                          tight.width, tight.height)

                    # Nominal cell centre is the body anchor for centering
                    nom_cx = x0 + (x1 - x0) / 2.0
                    mapping[state].append({'rect': abs_rect, 'span_cx': nom_cx})


            # --- Global scale based on walk frame average ---
            walk_items = mapping.get('walk', [])
            all_items  = [item for st in mapping for item in mapping[st]]
            if walk_items:
                base_h = sum(item['rect'].height for item in walk_items) / len(walk_items)
                base_w = sum(item['rect'].width  for item in walk_items) / len(walk_items)
            elif all_items:
                base_h = sum(item['rect'].height for item in all_items) / len(all_items)
                base_w = sum(item['rect'].width  for item in all_items) / len(all_items)
            else:
                base_h, base_w = 100.0, 80.0

            global_scale  = 110.0 / base_h
            scaled_base_w = int(base_w * global_scale)

            # Canvas large enough to fit the widest frame (e.g. shoot with muzzle flash)
            all_rects    = [item['rect'] for item in all_items]
            max_w_scaled = max((int(r.width  * global_scale) for r in all_rects), default=150)
            max_h_scaled = max((int(r.height * global_scale) for r in all_rects), default=150)
            SURF_W = max(160, max_w_scaled + 20)
            SURF_H = max(160, max_h_scaled + 20)

            for state, item_list in mapping.items():
                if not item_list:
                    continue
                if state not in self.animations:
                    self.animations[state] = []

                for item in item_list:
                    rect    = item['rect']
                    span_cx = item['span_cx']

                    surf = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
                    surf.blit(clean_sheet, (0, 0), rect)

                    new_w = int(rect.width  * global_scale)
                    new_h = int(rect.height * global_scale)
                    scaled_surf = pygame.transform.scale(surf, (new_w, new_h))

                    # Centre the sprite on the canvas using the nominal cell centre.
                    # For extra-wide shoot frames (muzzle flash) clamp to body width.
                    body_cx_in_sheet = rect.x + rect.width / 2.0
                    drift = (body_cx_in_sheet - span_cx) * global_scale

                    if new_w > scaled_base_w * 1.25:
                        # Oversized frame → pin on nominal body centre, ignore bbox width
                        offset_x = int(SURF_W / 2.0 - scaled_base_w / 2.0)
                    else:
                        offset_x = int(SURF_W / 2.0 + drift - new_w / 2.0)

                    final_surf = pygame.Surface((SURF_W, SURF_H), pygame.SRCALPHA)
                    final_surf.blit(scaled_surf, (offset_x, SURF_H - new_h))
                    self.animations[state].append(final_surf)

            if not self.animations.get('walk'):
                raise Exception("Parsing failed to populate walk")

            # Fallbacks if the AI sheet is missing an animation state
            if not self.animations.get('aim'):
                self.animations['aim'] = [self.animations['walk'][0]]
            if not self.animations.get('shoot'):
                self.animations['shoot'] = [self.animations['walk'][0]]

            # --- Post-process shoot frames ---
            # Some AI sheets generate a bullet-only frame with no character body.
            # Detect these (anomalously short height) and composite them on top of
            # the previous frame so the character remains visible during the blast.
            shoot_frames = self.animations.get('shoot', [])
            if len(shoot_frames) >= 2:
                # Measure average non-zero content height per frame
                heights = []
                for sf in shoot_frames:
                    m = pygame.mask.from_surface(sf)
                    bbs = m.get_bounding_rects()
                    if bbs:
                        t = bbs[0]
                        for b in bbs[1:]: t = t.union(b)
                        heights.append(t.height)
                    else:
                        heights.append(0)

                avg_h = sum(h for h in heights if h > 0) / max(1, sum(1 for h in heights if h > 0))

                for idx, (sf, fh) in enumerate(zip(shoot_frames, heights)):
                    if fh < avg_h * 0.6 and idx > 0:
                        # Composite: copy the previous full-character frame as base,
                        # then blit the current bullet/effect on top
                        composite = shoot_frames[idx - 1].copy()
                        composite.blit(sf, (0, 0))
                        self.animations['shoot'][idx] = composite


        except Exception as e:
            print("Failed to slice enemy sprite sheet:", e)
            self._create_fallback_sprites()

            
    def _create_fallback_sprites(self):
        for state in self.animations.keys():
            self.animations[state] = []
            surf = pygame.Surface((80, 110))
            surf.fill(RED)
            if state == 'aim':
                surf.fill((200, 100, 0))
            elif state == 'shoot':
                surf.fill((255, 255, 0))
            self.animations[state].append(surf)

    def apply_gravity(self):
        self.direction.y += self.gravity
        self.rect.y += self.direction.y
        if self.rect.bottom >= FLOOR_Y:
            self.rect.bottom = FLOOR_Y
            self.direction.y = 0

    def on_screen(self):
        return self.rect.right > 50 and self.rect.left < SCREEN_WIDTH - 50

    def ai_logic(self):
        current_time = pygame.time.get_ticks()
        
        # Are we in cooldown after shooting?
        if current_time < self.cooldown_end_time:
            self.state = 'walk'
            self.direction.x = 0
            return
            
        distance = self.player.rect.centerx - self.rect.centerx
        abs_distance = abs(distance)
        
        if self.state == 'walk':
            # Face player
            self.facing_right = distance > 0
            
            # Enemy must be firmly on screen before transitioning to an aiming stance
            if self.on_screen() and abs_distance < 450 and abs_distance > 100:
                self.state = 'aim'
                self.frame_index = 0
                self.direction.x = 0
            else:
                self.direction.x = 1 if self.facing_right else -1
                
        elif self.state in ['aim', 'shoot']:
            # Horizontal locking during aim and shoot
            self.direction.x = 0

    def animate(self):
        animation = self.animations.get(self.state)
        if not animation: animation = self.animations['walk']
        
        self.frame_index += self.animation_speed
        
        if self.state == 'shoot':
            self.frame_index += 0.05 # Adjust shoot animation speed
            
            # Precisely time the bullet firing to sync with the physical muzzle flash frame!
            if not self.has_shot and self.frame_index >= 1.5:
                self.has_shot = True
                spawn_x = self.rect.right if self.facing_right else self.rect.left
                spawn_pos = (spawn_x, self.rect.centery - 15)
                proj = Projectile(spawn_pos, self.facing_right)
                self.projectile_group.add(proj)
        
        if self.frame_index >= len(animation):
            if self.state == 'aim':
                self.state = 'shoot'
                self.frame_index = 0
                self.has_shot = False
                animation = self.animations[self.state]
            elif self.state == 'shoot':
                self.state = 'walk'
                self.cooldown_end_time = pygame.time.get_ticks() + 1500 # 1.5s cooldown
                self.frame_index = 0
                animation = self.animations[self.state]
            else:
                self.frame_index = 0
            
        # Draw frame (clamp index safely)
        safe_index = min(int(self.frame_index), len(animation)-1)
        frame = animation[safe_index]
        if not self.facing_right:
            self.image = pygame.transform.flip(frame, True, False)
        else:
            self.image = frame

    def register_hit(self):
        """Mark this enemy as hit; it will flash white then die."""
        self.hit_flash_until = pygame.time.get_ticks() + ENEMY_HIT_FLASH_MS

    def update(self):
        # Auto-kill after flash expires
        if self.hit_flash_until:
            if pygame.time.get_ticks() >= self.hit_flash_until:
                self.kill()
            return   # freeze movement / AI during the flash

        self.ai_logic()
        self.animate()
        self.rect.x += self.direction.x * self.speed
        self.apply_gravity()
    
    def draw(self, surface):
        if self.hit_flash_until:
            # White-flash overlay: fill with white using BLEND_ADD so it brightens to white
            flash_surf = self.image.copy()
            flash_surf.fill((255, 255, 255, 0), special_flags=pygame.BLEND_RGB_ADD)
            surface.blit(flash_surf, self.rect)
        else:
            surface.blit(self.image, self.rect)
