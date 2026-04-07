import pygame
import os
import math
from collections import Counter
from settings import *
from projectile import Projectile


# ─────────────────────────────────────────────────────────────────────────────
# Shared sprite-sheet parser (used by both Enemy subtypes)
# ─────────────────────────────────────────────────────────────────────────────

def _parse_spritesheet(path, row_defs, surf_w, target_h=110, slice_w=None):
    """Load *path*, chroma-key it, and slice it into animation frames.

    row_defs: list of (state_name, frame_count, y_start_frac, y_end_frac)
              where fractions are 0..1 of the sheet height.
    Returns dict  {state: [Surface, ...]}  or raises on failure.
    """
    sheet = pygame.image.load(path).convert_alpha()
    w, h  = sheet.get_size()

    # Smart chroma-key
    clean = pygame.Surface((w, h), pygame.SRCALPHA)
    clean.fill((0, 0, 0, 0))
    px = pygame.PixelArray(sheet)
    cx = pygame.PixelArray(clean)
    corners  = [px[0, 0], px[w-1, 0], px[0, h-1], px[w-1, h-1]]
    bg_col   = Counter(corners).most_common(1)[0][0]
    bg_r, bg_g, bg_b, _ = sheet.unmap_rgb(bg_col)
    for x in range(w):
        for y in range(h):
            c = px[x, y]
            r, g, b, _ = sheet.unmap_rgb(c)
            if abs(r-bg_r)+abs(g-bg_g)+abs(b-bg_b) > 150:
                if g > r+15 and g > b+15:
                    g = max(r, b)
                    c = sheet.map_rgb((r, g, b, 255))
                cx[x, y] = c
    px.close(); cx.close()

    mapping = {}
    for state, n_frames, y0f, y1f in row_defs:
        y_start = int(h * y0f)
        y_end   = int(h * y1f)
        row_h   = y_end - y_start
        current_cell_w = slice_w if slice_w else w // n_frames
        frames  = []
        for i in range(n_frames):
            x0 = i * current_cell_w
            x1 = min(w, x0 + current_cell_w)
            if x1 <= x0: continue
            cell  = clean.subsurface(pygame.Rect(x0, y_start, x1-x0, row_h))
            mask  = pygame.mask.from_surface(cell)
            bbs   = [b for b in mask.get_bounding_rects() if b.height > 40]
            if not bbs:
                continue
            tight = bbs[0]
            for b in bbs[1:]:
                tight = tight.union(b)
            abs_rect = pygame.Rect(tight.x + x0, tight.y + y_start,
                                   tight.width, tight.height)
            frames.append({'rect': abs_rect, 'cx': x0 + (x1-x0)/2.0})
        mapping[state] = frames

    # Global scale based on first state
    first_key = next(iter(mapping))
    items = mapping[first_key]
    if items:
        base_h = sum(it['rect'].height for it in items) / len(items)
        base_w = sum(it['rect'].width  for it in items) / len(items)
    else:
        base_h, base_w = 100.0, 80.0
    scale      = target_h / base_h
    scaled_bw  = int(base_w * scale)
    all_items  = [it for st in mapping for it in mapping[st]]
    SURF_W = surf_w
    SURF_H = max(160, max(int(it['rect'].height * scale) for it in all_items) + 20)

    animations = {st: [] for st in mapping}
    for state, item_list in mapping.items():
        for it in item_list:
            rect    = it['rect']
            span_cx = it['cx']
            surf = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
            surf.blit(clean, (0, 0), rect)
            nw = int(rect.width  * scale)
            nh = int(rect.height * scale)
            scaled = pygame.transform.scale(surf, (nw, nh))
            drift  = (rect.x + rect.width/2.0 - span_cx) * scale
            if nw > scaled_bw * 1.25:
                off_x = int(SURF_W/2.0 - scaled_bw/2.0)
            else:
                off_x = int(SURF_W/2.0 + drift - nw/2.0)
            final = pygame.Surface((SURF_W, SURF_H), pygame.SRCALPHA)
            final.blit(scaled, (off_x, SURF_H - nh))
            animations[state].append(final)

    return animations


def _tint_animations(base_anims, tint_rgba):
    """Return a deep copy of *base_anims* with each frame color-multiplied."""
    result = {}
    for state, frames in base_anims.items():
        tinted = []
        for f in frames:
            t = f.copy()
            t.fill(tint_rgba, special_flags=pygame.BLEND_RGBA_MULT)
            tinted.append(t)
        result[state] = tinted
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Base Enemy  (ranged shooter)
# ─────────────────────────────────────────────────────────────────────────────

class Enemy(pygame.sprite.Sprite):
    SHARED_ANIMATIONS = None   # per-subclass cache (see __init__ below)
    HP_MAX  = 1
    SPEED   = 3

    def __init__(self, pos, player_ref, projectile_group, platforms):
        super().__init__()
        self.player           = player_ref
        self.projectile_group = projectile_group
        self.platforms        = platforms

        cls = type(self)
        if cls.SHARED_ANIMATIONS is None:
            self.import_sprites()
            cls.SHARED_ANIMATIONS = self.animations
        else:
            self.animations = cls.SHARED_ANIMATIONS

        self.frame_index    = 0
        self.animation_speed = 0.1
        self.image = self.animations[self._first_state()][0]
        self.rect  = self.image.get_rect(bottomleft=pos)

        self.direction = pygame.math.Vector2(0, 0)
        self.speed     = self.SPEED
        self.gravity   = GRAVITY

        self.facing_right     = True
        self.state            = 'walk'
        self.has_shot         = False
        self.cooldown_end_time = 0
        self.hp               = self.HP_MAX
        self.hit_flash_until  = 0

    def _first_state(self):
        return next(iter(self.animations))

    # ── Sprite loading ────────────────────────────────────────────────────

    def import_sprites(self):
        path = os.path.join(IMAGE_DIR, "enemy.png")
        if not os.path.exists(path):
            self._create_fallback_sprites({'walk', 'aim', 'shoot'})
            return
        try:
            row_defs = [
                ('walk',  6, 0,     1/3),
                ('aim',   4, 1/3,   2/3),
                ('shoot', 6, 2/3,   1.0),
            ]
            self.animations = _parse_spritesheet(path, row_defs, surf_w=200, slice_w=200)

            # Fallbacks for missing states
            for st in ('aim', 'shoot'):
                if not self.animations.get(st):
                    self.animations[st] = [self.animations['walk'][0]]

            # Post-process shoot frames (composite body-less frames)
            shoot = self.animations.get('shoot', [])
            if len(shoot) >= 2:
                heights = []
                for sf in shoot:
                    m  = pygame.mask.from_surface(sf)
                    bs = m.get_bounding_rects()
                    if bs:
                        t = bs[0]
                        for b in bs[1:]: t = t.union(b)
                        heights.append(t.height)
                    else:
                        heights.append(0)
                avg_h = sum(n for n in heights if n > 0) / max(1, sum(1 for n in heights if n > 0))
                for idx, (sf, fh) in enumerate(zip(shoot, heights)):
                    if fh < avg_h * 0.6 and idx > 0:
                        comp = shoot[idx-1].copy()
                        comp.blit(sf, (0, 0))
                        self.animations['shoot'][idx] = comp
        except Exception as e:
            print("Enemy sprite parse failed:", e)
            self._create_fallback_sprites({'walk', 'aim', 'shoot'})

    def _create_fallback_sprites(self, states):
        self.animations = {}
        colors = {'walk': RED, 'aim': (200, 100, 0), 'shoot': (255, 255, 0),
                  'charge': (255, 100, 0), 'punch': (255, 50, 0)}
        for st in states:
            surf = pygame.Surface((80, 110))
            surf.fill(colors.get(st, RED))
            self.animations[st] = [surf]

    # ── Physics ───────────────────────────────────────────────────────────

    def apply_gravity(self):
        self.direction.y += self.gravity
        self.rect.y += self.direction.y
        if self.rect.bottom >= FLOOR_Y:
            self.rect.bottom = FLOOR_Y
            self.direction.y = 0
        else:
            # Platform landing (enemies can land then walk off naturally)
            if self.direction.y >= 0:
                for plat in self.platforms:
                    pr = plat['rect']
                    if (self.rect.bottom - self.direction.y <= pr.top + 14
                            and self.rect.bottom >= pr.top
                            and self.rect.right > pr.left + 8
                            and self.rect.left  < pr.right - 8):
                        self.rect.bottom = pr.top
                        self.direction.y  = 0
                        break

    def on_screen(self):
        return self.rect.right > 50 and self.rect.left < SCREEN_WIDTH - 50

    # ── AI ────────────────────────────────────────────────────────────────

    def ai_logic(self):
        now = pygame.time.get_ticks()
        if now < self.cooldown_end_time:
            self.state      = 'walk'
            self.direction.x = 0
            return
        distance     = self.player.rect.centerx - self.rect.centerx
        abs_distance = abs(distance)
        if self.state == 'walk':
            self.facing_right = distance > 0
            if self.on_screen() and 100 < abs_distance < 450:
                self.state      = 'aim'
                self.frame_index = 0
                self.direction.x = 0
            else:
                self.direction.x = 1 if self.facing_right else -1
        elif self.state in ('aim', 'shoot'):
            self.direction.x = 0

    # ── Animation ─────────────────────────────────────────────────────────

    def animate(self):
        anim = self.animations.get(self.state) or self.animations[self._first_state()]
        self.frame_index += self.animation_speed

        if self.state == 'shoot':
            self.frame_index += 0.05
            if not self.has_shot and self.frame_index >= 1.5:
                self.has_shot = True
                sx = self.rect.right if self.facing_right else self.rect.left
                proj = Projectile((sx, self.rect.centery + 5), self.facing_right)
                self.projectile_group.add(proj)

        if self.frame_index >= len(anim):
            if self.state == 'aim':
                self.state       = 'shoot'
                self.frame_index = 0
                self.has_shot    = False
                anim = self.animations['shoot']
            elif self.state == 'shoot':
                self.state            = 'walk'
                self.cooldown_end_time = pygame.time.get_ticks() + 1500
                self.frame_index      = 0
                anim = self.animations[self._first_state()]
            else:
                self.frame_index = 0

        frame = anim[min(int(self.frame_index), len(anim)-1)]
        self.image = pygame.transform.flip(frame, True, False) if not self.facing_right else frame

    # ── Combat ────────────────────────────────────────────────────────────

    def register_hit(self):
        self.hp -= 1
        if self.hp <= 0:
            self.hit_flash_until = pygame.time.get_ticks() + ENEMY_HIT_FLASH_MS
        else:
            # Stagger flash — shorter, doesn't kill
            self.hit_flash_until = pygame.time.get_ticks() + ENEMY_HIT_FLASH_MS // 2

    # ── Update / Draw ─────────────────────────────────────────────────────

    def update(self):
        if self.hit_flash_until:
            if pygame.time.get_ticks() >= self.hit_flash_until:
                if self.hp <= 0:
                    self.kill()
                else:
                    self.hit_flash_until = 0   # stagger over, resume
            return
        self.ai_logic()
        self.animate()
        self.rect.x += self.direction.x * self.speed
        self.apply_gravity()

    def draw(self, surface):
        if self.hit_flash_until:
            flash = self.image.copy()
            flash.fill((255, 255, 255, 0), special_flags=pygame.BLEND_RGB_ADD)
            surface.blit(flash, self.rect)
        else:
            surface.blit(self.image, self.rect)


# ─────────────────────────────────────────────────────────────────────────────
# MeleeEnemy  (charges + punches)
# ─────────────────────────────────────────────────────────────────────────────

class MeleeEnemy(Enemy):
    SHARED_ANIMATIONS = None
    HP_MAX = 1
    SPEED  = 5

    def import_sprites(self):
        path = os.path.join(IMAGE_DIR, "melee_enemy.png")
        if not os.path.exists(path):
            self._create_fallback_sprites({'walk', 'charge', 'punch'})
            return
        try:
            row_defs = [
                ('walk',   6, 0,     0.25),
                ('charge', 6, 0.25,   0.5),
                ('punch',  6, 0.5,   0.75)
            ]
            self.animations = _parse_spritesheet(path, row_defs, surf_w=245)
            for st in ('charge', 'punch'):
                if not self.animations.get(st):
                    self.animations[st] = self.animations.get('walk', [])
        except Exception as e:
            print("MeleeEnemy sprite parse failed:", e)
            self._create_fallback_sprites({'walk', 'charge', 'punch'})

    # ── AI ────────────────────────────────────────────────────────────────

    def ai_logic(self):
        if not self.on_screen():
            self.direction.x = 1 if (self.player.rect.centerx > self.rect.centerx) else -1
            self.facing_right = self.direction.x > 0
            return

        distance     = self.player.rect.centerx - self.rect.centerx
        abs_distance = abs(distance)
        self.facing_right = distance > 0

        now = pygame.time.get_ticks()

        if self.state == 'punch':
            self.direction.x = 0
        elif abs_distance < 75:
            if self.state != 'punch':
                self.state       = 'punch'
                self.frame_index = 0
                self.is_punching = True
                self.direction.x = 0
        elif abs_distance < 320:
            self.state       = 'charge'
            self.direction.x = 1 if self.facing_right else -1
        else:
            self.state       = 'walk'
            self.direction.x = 1 if self.facing_right else -1

    # ── Animation ─────────────────────────────────────────────────────────

    def animate(self):
        anim = self.animations.get(self.state) or self.animations['walk']
        self.frame_index += self.animation_speed

        # Punch window — expose hitbox at frame 2.5–4.5
        self.is_punching = (self.state == 'punch'
                            and 2.5 <= self.frame_index <= 4.5)

        if self.frame_index >= len(anim):
            if self.state == 'punch':
                self.state       = 'walk'
                self.is_punching = False
            self.frame_index = 0
            anim = self.animations.get(self.state) or self.animations['walk']

        frame = anim[min(int(self.frame_index), len(anim)-1)]
        self.image = pygame.transform.flip(frame, True, False) if not self.facing_right else frame

    def get_punch_rect(self):
        """Hitbox active during the punch window."""
        w = 70
        if self.facing_right:
            return pygame.Rect(self.rect.centerx + 10, self.rect.centery - 25, w, 55)
        return pygame.Rect(self.rect.centerx - 10 - w, self.rect.centery - 25, w, 55)

    # ── Speed varies by state ─────────────────────────────────────────────

    def update(self):
        if self.hit_flash_until:
            if pygame.time.get_ticks() >= self.hit_flash_until:
                if self.hp <= 0:
                    self.kill()
                else:
                    self.hit_flash_until = 0
            return
        self.ai_logic()
        self.animate()
        move_speed = 7 if self.state == 'charge' else (0 if self.state == 'punch' else self.speed)
        self.rect.x += self.direction.x * move_speed
        self.apply_gravity()


# ─────────────────────────────────────────────────────────────────────────────
# HeavyEnemy  (slow shooter, 3 HP, purple tint)
# ─────────────────────────────────────────────────────────────────────────────

class HeavyEnemy(Enemy):
    SHARED_ANIMATIONS = None
    HP_MAX = 3
    SPEED  = 1

    def import_sprites(self):
        # Re-use the shooter sprite sheet but apply a purple tint
        if Enemy.SHARED_ANIMATIONS is None:
            # Bootstrap base sprites without a full enemy instance
            Enemy.import_sprites(self)
            Enemy.SHARED_ANIMATIONS = self.animations
        self.animations = _tint_animations(Enemy.SHARED_ANIMATIONS, HEAVY_ENEMY_TINT)
