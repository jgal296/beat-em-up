import pygame
import os
import math
import random
from settings import *


class Level:
    def __init__(self):
        self.display_surface = pygame.display.get_surface()
        self.world_shift = 0

        # ── Far layer: star field ─────────────────────────────────────────
        # Keep it ONE screen wide so tiling blits are cheap.
        self.far_surf   = self._gen_star_layer(SCREEN_WIDTH + 4, SCREEN_HEIGHT)
        self.far_scroll = 0.0

        # ── Mid layer: background.png — fully opaque, converted ───────────
        # set_alpha() was the biggest perf killer: it forces per-pixel
        # alpha on every blit.  We drop it and keep the layer opaque.
        bg_path = os.path.join(IMAGE_DIR, "background.png")
        if os.path.exists(bg_path):
            raw   = pygame.image.load(bg_path).convert()
            ratio = SCREEN_HEIGHT / raw.get_height()
            self.mid_surf = pygame.transform.scale(
                raw, (int(raw.get_width() * ratio), SCREEN_HEIGHT)
            )
            # ← NO set_alpha() — avoids surface-level alpha blend every blit
        else:
            self.mid_surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
            self.mid_surf.fill(BG_COLOR)
            self.mid_surf = self.mid_surf.convert()
        self.mid_scroll = 0.0

        # ── Near layer: foreground strip — colorkey, one screen wide ─────
        # SRCALPHA on a 3× wide surface was masking thousands of transparent
        # pixels per frame.  colorkey gives the same visual at a fraction of the cost.
        self.near_surf   = self._gen_near_layer(SCREEN_WIDTH + 4, SCREEN_HEIGHT)
        self.near_scroll = 0.0

        # ── Platforms — glow surface pre-created once ─────────────────────
        self.platforms = [
            self._make_platform(230,  FLOOR_Y - 130, 220),
            self._make_platform(680,  FLOOR_Y - 235, 180),
            self._make_platform(1020, FLOOR_Y - 175, 200),
        ]

    # ── Layer generators ──────────────────────────────────────────────────

    def _gen_star_layer(self, w, h):
        surf = pygame.Surface((w, h))
        surf.fill((6, 4, 18))
        rng = random.Random(99)
        for _ in range(220):          # scale star count to surface size
            x  = rng.randint(0, w - 1)
            y  = rng.randint(0, h - 1)
            br = rng.randint(130, 255)
            r  = rng.randint(0, 2)
            col = (br, br, int(br * 0.88))
            if r == 0:
                surf.set_at((x, y), col)
            else:
                pygame.draw.circle(surf, col, (x, y), r)
        # One small nebula blob (SRCALPHA only used at startup — not per frame)
        nb = pygame.Surface((160, 160), pygame.SRCALPHA)
        pygame.draw.circle(nb, (50, 0, 90, 30), (80, 80), 80)
        surf.blit(nb, (w // 3 - 80, h // 3 - 80))
        return surf.convert()     # ← convert for fast blitting at runtime

    def _gen_near_layer(self, w, h):
        """Foreground tech-panel strip using a colorkey (no per-pixel alpha)."""
        CKEY = (255, 0, 200)       # magenta — marks "transparent" pixels
        surf = pygame.Surface((w, h))
        surf.fill(CKEY)
        strip_y = FLOOR_Y - 18
        strip_h = 22
        # Opaque dark strip just above the floor
        pygame.draw.rect(surf, (12, 12, 36), (0, strip_y, w, strip_h))
        # Tech panels
        for x in range(0, w, 58):
            pw, ph = 36, 10
            px, py = x + 11, strip_y + 6
            pygame.draw.rect(surf, (0, 90, 150),  (px, py, pw, ph))
            pygame.draw.rect(surf, (0, 190, 240), (px, py, pw, 2))
            pygame.draw.rect(surf, (0, 130, 190), (px, py, pw, ph), 1)
        surf.set_colorkey(CKEY)
        return surf.convert()     # ← convert preserves colorkey, very fast to blit

    def _make_platform(self, x, y, w):
        h = PLATFORM_H
        surf = pygame.Surface((w, h))
        surf.fill(PLATFORM_COLOR_BODY)
        pygame.draw.rect(surf, PLATFORM_COLOR_TOP,  (0, 0, w, 3))
        pygame.draw.rect(surf, PLATFORM_COLOR_BODY, (0, 3, w, h - 3))
        for px in range(12, w - 10, 36):
            pygame.draw.rect(surf, (0, 160, 220), (px, 5, 22, 6))
        pygame.draw.rect(surf, PLATFORM_COLOR_GLOW, surf.get_rect(), 1)

        # Pre-create glow surface with surface-level alpha (created ONCE, not per frame)
        glow = pygame.Surface((w, 6)).convert()
        glow.fill((0, 50, 110))
        glow.set_alpha(55)   # surface-level alpha — far cheaper than SRCALPHA per pixel

        return {'surf': surf.convert(), 'rect': pygame.Rect(x, y, w, h), 'glow': glow}

    # ── Scroll / Update ───────────────────────────────────────────────────

    def scroll_x(self, player_rect, player_direction_x):
        if player_rect.left < 20 and player_direction_x <= 0:
            player_rect.left = 20
            self.world_shift = 0
            return
        if player_rect.centerx < SCREEN_WIDTH // 4 and player_direction_x < 0:
            self.world_shift = PLAYER_SPEED
            player_rect.x += PLAYER_SPEED
        elif player_rect.centerx > SCREEN_WIDTH - (SCREEN_WIDTH // 4) and player_direction_x > 0:
            self.world_shift = -PLAYER_SPEED
            player_rect.x -= PLAYER_SPEED
        else:
            self.world_shift = 0

    def update(self):
        self.far_scroll  += self.world_shift * 0.13
        self.mid_scroll  += self.world_shift * 0.5
        self.near_scroll += self.world_shift * 0.88

        for plat in self.platforms:
            plat['rect'].x += self.world_shift
            if plat['rect'].right < -220:
                plat['rect'].x = SCREEN_WIDTH + 80
            elif plat['rect'].left > SCREEN_WIDTH + 220:
                plat['rect'].x = -plat['rect'].width - 80

    # ── Draw ──────────────────────────────────────────────────────────────

    def _draw_tiled(self, target, surf, scroll):
        w     = surf.get_width()
        rel_x = int(scroll) % w
        tiles = (SCREEN_WIDTH // w) + 2
        for i in range(-1, tiles):
            target.blit(surf, (rel_x + i * w, 0))

    def draw(self, surface=None):
        target = surface if surface is not None else self.display_surface
        self._draw_tiled(target, self.far_surf,  self.far_scroll)
        self._draw_tiled(target, self.mid_surf,  self.mid_scroll)
        self._draw_tiled(target, self.near_surf, self.near_scroll)

        pygame.draw.line(target, (55, 55, 100), (0, FLOOR_Y), (SCREEN_WIDTH, FLOOR_Y), 2)

        for plat in self.platforms:
            target.blit(plat['surf'], plat['rect'])
            target.blit(plat['glow'], (plat['rect'].x, plat['rect'].bottom))
