import pygame
import sys
import os
import random
import math
from settings import *
from level import Level
from player import Player
from enemy import Enemy, MeleeEnemy, HeavyEnemy
from projectile import Projectile


# ─────────────────────────────────────────────────────────────────────────────
# Spawn Portal
# ─────────────────────────────────────────────────────────────────────────────

class SpawnPortal:
    OPEN_MS  = 650   # time before enemy materialises
    CLOSE_MS = 350   # time to close after enemy spawns

    def __init__(self, pos, enemy_cls, ctor_args):
        self.pos        = list(float(c) for c in pos)
        self.born       = pygame.time.get_ticks()
        self.enemy_cls  = enemy_cls
        self.ctor_args  = ctor_args   # (player, projectiles, platforms)
        self._spawned   = False

    # ── Lifecycle ─────────────────────────────────────────────────────────

    def shift(self, dx):
        self.pos[0] += dx

    def _elapsed(self):
        return pygame.time.get_ticks() - self.born

    def _scale(self):
        e = self._elapsed()
        if e < 280:
            return e / 280.0
        elif e < self.OPEN_MS:
            return 1.0
        else:
            t = (e - self.OPEN_MS) / self.CLOSE_MS
            return max(0.0, 1.0 - t)

    def should_spawn(self):
        if not self._spawned and self._elapsed() >= self.OPEN_MS:
            self._spawned = True
            return True
        return False

    def is_done(self):
        return self._elapsed() >= self.OPEN_MS + self.CLOSE_MS

    def spawn_enemy(self, group):
        cx, cy = int(self.pos[0]), int(self.pos[1])
        enemy = self.enemy_cls((cx, cy), *self.ctor_args)
        group.add(enemy)

    # ── Draw ──────────────────────────────────────────────────────────────

    def draw(self, surface):
        scale = self._scale()
        if scale < 0.02:
            return
        cx, cy  = int(self.pos[0]), int(self.pos[1])
        now     = pygame.time.get_ticks()
        angle   = now * 0.005
        max_r   = 44
        r       = max(2, int(max_r * scale))

        # Inner filled glow
        glow = pygame.Surface((r*2+4, r*2+4), pygame.SRCALPHA)
        a = int(170 * scale)
        pygame.draw.circle(glow, (10, 50, 200, a),        (r+2, r+2), r)
        pygame.draw.circle(glow, (0,  150, 255, a // 2),  (r+2, r+2), int(r * 0.55))
        surface.blit(glow, (cx - r - 2, cy - r - 2))

        # Rotating spokes
        for i in range(6):
            a_spoke = angle + i * math.pi / 3
            for j, col in enumerate([(0, 220, 255), (80, 170, 255), (0, 140, 220)]):
                aa = a_spoke + j * 0.12
                x1 = cx + int(r * 0.28 * math.cos(aa))
                y1 = cy + int(r * 0.28 * math.sin(aa))
                x2 = cx + int(r * 0.96 * math.cos(aa))
                y2 = cy + int(r * 0.96 * math.sin(aa))
                pygame.draw.line(surface, col, (x1, y1), (x2, y2), max(1, 2-j))

        # Outer rings
        pygame.draw.circle(surface, (0,  210, 255), (cx, cy), r,              3)
        pygame.draw.circle(surface, (100, 200, 255), (cx, cy), int(r * 0.75), 2)

        # Rim sparks
        for i in range(4):
            sa = angle * 2 + i * math.pi / 2
            sx = cx + int(r * math.cos(sa))
            sy = cy + int(r * math.sin(sa))
            pygame.draw.circle(surface, (210, 240, 255), (sx, sy), max(1, int(3 * scale)))


# ─────────────────────────────────────────────────────────────────────────────
# Game
# ─────────────────────────────────────────────────────────────────────────────

class Game:
    def __init__(self):
        pygame.init()
        pygame.joystick.init()
        # Init any joysticks already connected at startup
        for i in range(pygame.joystick.get_count()):
            pygame.joystick.Joystick(i).init()
        # Block high-frequency axis events — they fire continuously from
        # analog noise and flood the event queue.  We poll axes directly
        # in get_input() so we don't need the events at all.
        pygame.event.set_blocked(pygame.JOYAXISMOTION)
        pygame.event.set_blocked(pygame.JOYBALLMOTION)
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("Super Space Brawler")
        self.clock = pygame.clock.Clock() if hasattr(pygame, "clock") else pygame.time.Clock()
        self.running = True

        self.level  = Level()
        self.player = Player((100, FLOOR_Y - 80))

        self.enemies     = pygame.sprite.Group()
        self.projectiles = pygame.sprite.Group()
        self.portals     = []

        self.score     = 0
        self.game_over = False
        self.last_spawn_time = pygame.time.get_ticks()
        self.spawn_delay     = 3000

        # Fonts
        self.font_big   = pygame.font.Font(None, 74)
        self.font_med   = pygame.font.Font(None, 42)
        self.font_small = pygame.font.Font(None, 32)

        # Juice
        self.world_surface       = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT)).convert()
        self.shake_timer         = 0
        self.shake_intensity     = 0
        self.particles           = []
        self.reflect_flash_until = 0

        # Pre-created overlays (avoids per-frame Surface allocation)
        self._game_over_overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        self._game_over_overlay.fill((0, 0, 0, 180))

    # ── Reset ─────────────────────────────────────────────────────────────

    def reset_game(self):
        self.player = Player((100, FLOOR_Y - 80))
        self.enemies.empty()
        self.projectiles.empty()
        self.portals  = []
        self.particles = []
        self.reflect_flash_until = 0
        self.score     = 0
        self.game_over = False
        self.spawn_delay     = 3000
        self.last_spawn_time = pygame.time.get_ticks()

    # ── Events ────────────────────────────────────────────────────────────

    def events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            # Hot-plug: initialise joystick when connected
            if event.type == pygame.JOYDEVICEADDED:
                pygame.joystick.Joystick(event.device_index).init()
            if self.game_over:
                if event.type == pygame.KEYDOWN and event.key == pygame.K_RETURN:
                    self.reset_game()
            else:
                self.player.handle_event(event)

    # ── Juice helpers ─────────────────────────────────────────────────────

    def trigger_shake(self, intensity=8, duration=220):
        self.shake_intensity = intensity
        self.shake_timer     = pygame.time.get_ticks() + duration

    def spawn_sparks(self, pos, count=10):
        colors = [(255, 220, 50), (255, 160, 30), (255, 255, 180), (255, 80, 0)]
        for _ in range(count):
            angle    = random.uniform(0, 2 * math.pi)
            speed    = random.uniform(2.5, 7.0)
            lifetime = random.randint(18, 36)
            self.particles.append({
                'pos':          [float(pos[0]), float(pos[1])],
                'vel':          [math.cos(angle) * speed, math.sin(angle) * speed - 2.5],
                'color':        random.choice(colors),
                'lifetime':     lifetime,
                'max_lifetime': lifetime,
                'radius':       random.uniform(3.0, 6.5),
            })

    # ── Spawn helpers ─────────────────────────────────────────────────────

    def _pick_enemy_cls(self):
        r = random.random()
        if r < SPAWN_W_SHOOTER:
            return Enemy
        elif r < SPAWN_W_SHOOTER + SPAWN_W_MELEE:
            return MeleeEnemy
        return HeavyEnemy

    def _make_spawn(self, pos, enemy_cls, via_portal=False):
        platforms = self.level.platforms
        ctor_args = (self.player, self.projectiles, platforms)
        if via_portal:
            self.portals.append(SpawnPortal(pos, enemy_cls, ctor_args))
        else:
            self.enemies.add(enemy_cls(pos, *ctor_args))

    def _do_spawn(self):
        platforms = self.level.platforms
        # 35 % chance: spawn on a visible platform via portal
        if platforms and random.random() < 0.35:
            plat = random.choice(platforms)
            pr   = plat['rect']
            if 0 < pr.left < SCREEN_WIDTH:   # only on-screen platforms
                portal_x = pr.centerx
                portal_y = pr.top
                self._make_spawn((portal_x, portal_y), self._pick_enemy_cls(),
                                 via_portal=True)
                return
        # Otherwise: off-screen floor edge (no portal needed)
        spawn_x = -100 if random.choice([True, False]) else SCREEN_WIDTH + 100
        self._make_spawn((spawn_x, FLOOR_Y), self._pick_enemy_cls(), via_portal=False)

    # ── Update ────────────────────────────────────────────────────────────

    def update(self):
        if self.game_over:
            return

        platforms = self.level.platforms
        self.player.update(platforms)
        self.level.scroll_x(self.player.rect, self.player.direction.x)
        self.level.update()

        # Shift everything with the camera
        for e in self.enemies:
            e.rect.x += self.level.world_shift
        for p in self.projectiles:
            p.rect.x += self.level.world_shift
        for portal in self.portals:
            portal.shift(self.level.world_shift)
        for p in self.particles:
            p['pos'][0] += self.level.world_shift

        # Spawn timing
        now = pygame.time.get_ticks()
        if now - self.last_spawn_time > self.spawn_delay:
            self._do_spawn()
            self.last_spawn_time = now
            self.spawn_delay = max(1000, self.spawn_delay - 100)

        # Update portals (spawn enemy when ready, remove when done)
        for portal in list(self.portals):
            if portal.should_spawn():
                portal.spawn_enemy(self.enemies)
            if portal.is_done():
                self.portals.remove(portal)

        self.enemies.update()
        self.projectiles.update()

        # Tick particles
        alive = []
        for p in self.particles:
            p['lifetime'] -= 1
            if p['lifetime'] > 0:
                p['pos'][0] += p['vel'][0]
                p['pos'][1] += p['vel'][1]
                p['vel'][1] += 0.28
                p['vel'][0] *= 0.93
                alive.append(p)
        self.particles = alive

        # ── Player melee kills enemies ────────────────────────────────────
        if self.player.is_attacking:
            ax = self.player.rect.centerx + 50 if self.player.facing_right else self.player.rect.centerx - 90
            ay = self.player.rect.bottom - 50 if self.player.status == 'duck_attack' else self.player.rect.bottom - 98
            attack_rect = pygame.Rect(ax, ay, 40, 60)
            for enemy in list(self.enemies):
                if not enemy.hit_flash_until and attack_rect.colliderect(enemy.rect):
                    enemy.register_hit()
                    if enemy.hp <= 0:
                        self.score += 10
                        self.spawn_sparks(enemy.rect.center)

        # ── Parry window ──────────────────────────────────────────────────
        if self.player.in_reflect_window:
            ax = self.player.rect.centerx + 50 if self.player.facing_right else self.player.rect.centerx - 90
            ay = self.player.rect.bottom - 50 if self.player.status == 'duck_attack' else self.player.rect.bottom - 98
            parry_rect = pygame.Rect(ax, ay, 40, 60)
            for proj in list(self.projectiles):
                if not proj.reflected and parry_rect.colliderect(proj.rect):
                    proj.reflect()
                    self.spawn_sparks(proj.rect.center, count=7)
                    self.reflect_flash_until = pygame.time.get_ticks() + REFLECT_FLASH_MS

        # ── Reflected projectile hits enemies ─────────────────────────────
        for proj in list(self.projectiles):
            if proj.reflected:
                for enemy in list(self.enemies):
                    if not enemy.hit_flash_until and proj.rect.colliderect(enemy.rect):
                        enemy.register_hit()
                        if enemy.hp <= 0:
                            self.score += 25
                        self.spawn_sparks(enemy.rect.center, count=14)
                        proj.kill()
                        break

        # ── Melee enemy punch hits player ─────────────────────────────────
        for enemy in list(self.enemies):
            if isinstance(enemy, MeleeEnemy) and getattr(enemy, 'is_punching', False):
                if not enemy.hit_flash_until:
                    punch_rect = enemy.get_punch_rect()
                    if punch_rect.colliderect(self.player.get_hitbox()):
                        result = self.player.take_damage()
                        if result is True:
                            self.trigger_shake(12, 400)
                            self.game_over = True
                        elif result is False:
                            self.trigger_shake(6, 200)

        # ── Projectile hits player (duck-aware, non-reflected only) ───────
        core_hitbox = self.player.get_hitbox()
        for proj in list(self.projectiles):
            if not proj.reflected and proj.rect.colliderect(core_hitbox):
                proj.kill()
                result = self.player.take_damage()
                if result is True:
                    self.trigger_shake(12, 400)
                    self.game_over = True
                elif result is False:
                    self.trigger_shake(6, 200)

    # ── HUD ───────────────────────────────────────────────────────────────

    def draw_hud(self):
        bar_x, bar_y = 20, SCREEN_HEIGHT - 48
        pip_w, pip_h, pip_gap = 28, 18, 6
        total_bar_w = PLAYER_MAX_HP * (pip_w + pip_gap) - pip_gap + 8
        panel = pygame.Surface((total_bar_w + 16, pip_h + 20), pygame.SRCALPHA)
        panel.fill((0, 0, 0, 140))
        self.screen.blit(panel, (bar_x - 8, bar_y - 8))
        label = self.font_small.render("HP", True, HUD_BORDER)
        self.screen.blit(label, (bar_x, bar_y - 26))
        for i in range(PLAYER_MAX_HP):
            pip_rect = pygame.Rect(bar_x + i * (pip_w + pip_gap), bar_y, pip_w, pip_h)
            color = HUD_RED if i < self.player.hp else HUD_BG
            pygame.draw.rect(self.screen, color, pip_rect, border_radius=4)
            pygame.draw.rect(self.screen, HUD_BORDER, pip_rect, 2, border_radius=4)
        score_str  = f"SCORE  {self.score:06d}"
        score_surf = self.font_med.render(score_str, True, HUD_GOLD)
        score_rect = score_surf.get_rect(topright=(SCREEN_WIDTH - 20, 16))
        shadow     = self.font_med.render(score_str, True, (0, 0, 0))
        self.screen.blit(shadow, score_rect.move(2, 2))
        self.screen.blit(score_surf, score_rect)

    # ── Draw ──────────────────────────────────────────────────────────────

    def draw(self):
        now = pygame.time.get_ticks()
        if now < self.shake_timer:
            ox = random.randint(-self.shake_intensity, self.shake_intensity)
            oy = random.randint(-self.shake_intensity, self.shake_intensity)
        else:
            ox, oy = 0, 0

        self.level.draw(self.world_surface)

        # Portals (behind enemies, in world space)
        for portal in self.portals:
            portal.draw(self.world_surface)

        for enemy in self.enemies:
            enemy.draw(self.world_surface)

        self.projectiles.draw(self.world_surface)
        self.player.draw(self.world_surface)

        # Particles
        for p in self.particles:
            t      = max(0.0, p['lifetime'] / p['max_lifetime'])
            radius = max(1, int(p['radius'] * (0.3 + 0.7 * t)))
            pygame.draw.circle(
                self.world_surface, p['color'],
                (int(p['pos'][0]), int(p['pos'][1])), radius)

        # Glow around reflected projectiles
        for proj in self.projectiles:
            if proj.reflected:
                cx, cy = proj.rect.center
                pygame.draw.circle(self.world_surface, (0, 210, 255), (cx, cy), 16, 2)
                pygame.draw.circle(self.world_surface, WHITE,          (cx, cy),  9, 1)

        self.screen.blit(self.world_surface, (ox, oy))

        # Parry screen flash (fixed, never shakes)
        if now < self.reflect_flash_until:
            t     = (self.reflect_flash_until - now) / REFLECT_FLASH_MS
            alpha = int(90 * t)
            fo    = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            fo.fill((180, 240, 255, alpha))
            self.screen.blit(fo, (0, 0))

        self.draw_hud()

        if self.game_over:
            self.screen.blit(self._game_over_overlay, (0, 0))
            text = self.font_big.render("GAME OVER", True, RED)
            self.screen.blit(text, text.get_rect(center=(SCREEN_WIDTH/2, SCREEN_HEIGHT/2 - 60)))
            fs = self.font_med.render(f"Score: {self.score:06d}", True, HUD_GOLD)
            self.screen.blit(fs, fs.get_rect(center=(SCREEN_WIDTH/2, SCREEN_HEIGHT/2)))
            sub = self.font_small.render("Press ENTER to Restart", True, WHITE)
            self.screen.blit(sub, sub.get_rect(center=(SCREEN_WIDTH/2, SCREEN_HEIGHT/2 + 52)))

        pygame.display.flip()

    # ── Run ───────────────────────────────────────────────────────────────

    def run(self):
        while self.running:
            self.events()
            self.update()
            self.draw()
            self.clock.tick(FPS)
        pygame.quit()
        sys.exit()


if __name__ == "__main__":
    game = Game()
    game.run()
