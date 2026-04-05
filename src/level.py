import pygame
import os
import math
import random
from settings import *


class Level:
    def __init__(self):
        self.display_surface = pygame.display.get_surface()
        self.world_shift = 0

        # ── Far layer: star field (generated, very slow scroll) ───────────
        self.far_surf   = self._gen_star_layer(SCREEN_WIDTH * 4, SCREEN_HEIGHT)
        self.far_scroll = 0.0

        # ── Mid layer: existing background.png (slight transparency so stars
        #    peek through at their brightest)
        bg_path = os.path.join(IMAGE_DIR, "background.png")
        if os.path.exists(bg_path):
            raw = pygame.image.load(bg_path).convert()
            ratio = SCREEN_HEIGHT / raw.get_height()
            self.mid_surf = pygame.transform.scale(
                raw, (int(raw.get_width() * ratio), SCREEN_HEIGHT)
            )
            self.mid_surf.set_alpha(230)   # 90 % opaque — stars faintly visible
        else:
            self.mid_surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
            self.mid_surf.fill(BG_COLOR)
        self.mid_scroll = 0.0

        # ── Near layer: foreground sci-fi panels (alpha, fast scroll) ─────
        self.near_surf   = self._gen_near_layer(SCREEN_WIDTH * 3, SCREEN_HEIGHT)
        self.near_scroll = 0.0

        # ── Platforms ─────────────────────────────────────────────────────
        # Three neon platforms at different heights.  They scroll with
        # world_shift and wrap when they drift too far off-screen.
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
        for _ in range(600):
            x  = rng.randint(0, w - 1)
            y  = rng.randint(0, h - 1)
            br = rng.randint(130, 255)
            r  = rng.randint(0, 2)
            col = (br, br, int(br * 0.88))
            if r == 0:
                surf.set_at((x, y), col)
            else:
                pygame.draw.circle(surf, col, (x, y), r)
        # Subtle nebula blobs
        for bx, by, br, col in [
            (w // 5,       h // 3,  80, (50, 0, 90, 28)),
            (w * 2 // 5,   h // 2,  70, (0,  30, 90, 24)),
            (w * 3 // 5,   h // 4,  90, (70, 0, 50, 22)),
        ]:
            nb = pygame.Surface((br * 2, br * 2), pygame.SRCALPHA)
            pygame.draw.circle(nb, col, (br, br), br)
            surf.blit(nb, (bx - br, by - br))
        return surf

    def _gen_near_layer(self, w, h):
        """Semi-transparent foreground strip — sci-fi tech panels."""
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        strip_y = FLOOR_Y - 18
        strip_h = 22
        # Dark translucent strip just above the floor
        surf.fill((0, 0, 25, 110), pygame.Rect(0, strip_y, w, strip_h))
        # Tech panel repetition
        for x in range(0, w, 58):
            pw, ph = 36, 10
            px, py = x + 11, strip_y + 6
            pygame.draw.rect(surf, (0, 100, 160, 150), (px, py, pw, ph))
            pygame.draw.rect(surf, (0, 190, 240, 200), (px, py, pw, 2))
            pygame.draw.rect(surf, (0, 140, 200, 160), (px, py, pw, ph), 1)
        return surf

    def _make_platform(self, x, y, w):
        h = PLATFORM_H
        surf = pygame.Surface((w, h))
        surf.fill(PLATFORM_COLOR_BODY)
        pygame.draw.rect(surf, PLATFORM_COLOR_TOP,  (0,   0, w, 3))   # glow top
        pygame.draw.rect(surf, PLATFORM_COLOR_BODY, (0,   3, w, h - 3))
        # Tech detail squares
        for px in range(12, w - 10, 36):
            pygame.draw.rect(surf, (0, 160, 220), (px, 5, 22, 6))
        pygame.draw.rect(surf, PLATFORM_COLOR_GLOW, surf.get_rect(), 1)
        return {'surf': surf, 'rect': pygame.Rect(x, y, w, h)}

    # ── Scroll / Update ───────────────────────────────────────────────────

    def scroll_x(self, player_rect, player_direction_x):
        # Hard left boundary
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

        # Platforms shift with the world and wrap at the edges
        for plat in self.platforms:
            plat['rect'].x += self.world_shift
            if plat['rect'].right < -220:
                plat['rect'].x = SCREEN_WIDTH + 80
            elif plat['rect'].left > SCREEN_WIDTH + 220:
                plat['rect'].x = -plat['rect'].width - 80

    # ── Draw ──────────────────────────────────────────────────────────────

    def _draw_tiled(self, target, surf, scroll):
        w = surf.get_width()
        rel_x = int(scroll) % w
        tiles = (SCREEN_WIDTH // w) + 2
        for i in range(-1, tiles):
            target.blit(surf, (rel_x + i * w, 0))

    def draw(self, surface=None):
        target = surface if surface is not None else self.display_surface
        self._draw_tiled(target, self.far_surf,  self.far_scroll)
        self._draw_tiled(target, self.mid_surf,  self.mid_scroll)
        self._draw_tiled(target, self.near_surf, self.near_scroll)

        # Floor line
        pygame.draw.line(target, (55, 55, 100), (0, FLOOR_Y), (SCREEN_WIDTH, FLOOR_Y), 2)

        # Platforms (and their underside glow)
        for plat in self.platforms:
            target.blit(plat['surf'], plat['rect'])
            # subtle glow beneath
            gx = plat['rect'].x
            gy = plat['rect'].bottom
            gw = plat['rect'].width
            glow = pygame.Surface((gw, 6), pygame.SRCALPHA)
            glow.fill((0, 180, 255, 40))
            target.blit(glow, (gx, gy))
