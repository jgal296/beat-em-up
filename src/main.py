import pygame
import sys
import os
import random
import math
from settings import *
from level import Level
from player import Player
from enemy import Enemy
from projectile import Projectile

class Game:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("Super Space Brawler")
        self.clock = pygame.clock.Clock() if hasattr(pygame, "clock") else pygame.time.Clock()
        self.running = True

        self.level = Level()
        self.player = Player((100, FLOOR_Y - 80))

        self.enemies = pygame.sprite.Group()
        self.projectiles = pygame.sprite.Group()

        self.score = 0
        self.game_over = False
        self.last_spawn_time = pygame.time.get_ticks()
        self.spawn_delay = 3000

        # Fonts
        self.font_big   = pygame.font.Font(None, 74)
        self.font_med   = pygame.font.Font(None, 42)
        self.font_small = pygame.font.Font(None, 32)

        # Juice — screen shake + particles
        self.world_surface       = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        self.shake_timer         = 0   # ms timestamp when shake ends
        self.shake_intensity     = 0   # max pixel displacement
        self.particles           = []  # list of particle dicts
        self.reflect_flash_until = 0   # ms — brief screen flash after a parry
        
    def reset_game(self):
        self.player = Player((100, FLOOR_Y - 80))
        self.enemies.empty()
        self.projectiles.empty()
        self.particles = []
        self.reflect_flash_until = 0
        self.score = 0
        self.game_over = False
        self.spawn_delay = 3000
        self.last_spawn_time = pygame.time.get_ticks()
        
    def events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            
            if self.game_over:
                if event.type == pygame.KEYDOWN and event.key == pygame.K_RETURN:
                    self.reset_game()
            else:
                self.player.handle_event(event)
                
    # ------------------------------------------------------------------
    # Juice helpers
    # ------------------------------------------------------------------
    def trigger_shake(self, intensity=8, duration=220):
        """Start or refresh a camera shake."""
        self.shake_intensity = intensity
        self.shake_timer = pygame.time.get_ticks() + duration

    def spawn_sparks(self, pos, count=10):
        """Burst of coloured particles at world-space *pos*."""
        colors = [(255, 220, 50), (255, 160, 30), (255, 255, 180), (255, 80, 0)]
        for _ in range(count):
            angle = random.uniform(0, 2 * math.pi)
            speed = random.uniform(2.5, 7.0)
            lifetime = random.randint(18, 36)   # frames
            self.particles.append({
                'pos':          [float(pos[0]), float(pos[1])],
                'vel':          [math.cos(angle) * speed, math.sin(angle) * speed - 2.5],
                'color':        random.choice(colors),
                'lifetime':     lifetime,
                'max_lifetime': lifetime,
                'radius':       random.uniform(3.0, 6.5),
            })

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------
    def update(self):
        if self.game_over:
            return

        self.player.update()
        self.level.scroll_x(self.player.rect, self.player.direction.x)
        self.level.update()

        for e in self.enemies:
            e.rect.x += self.level.world_shift
        for p in self.projectiles:
            p.rect.x += self.level.world_shift

        # Particles follow camera
        for p in self.particles:
            p['pos'][0] += self.level.world_shift

        current_time = pygame.time.get_ticks()
        if current_time - self.last_spawn_time > self.spawn_delay:
            spawn_x = -100 if random.choice([True, False]) else SCREEN_WIDTH + 100
            self.enemies.add(Enemy((spawn_x, FLOOR_Y), self.player, self.projectiles))
            self.last_spawn_time = current_time
            self.spawn_delay = max(1000, self.spawn_delay - 100)

        self.enemies.update()
        self.projectiles.update()

        # --- Tick particles ---
        alive = []
        for p in self.particles:
            p['lifetime'] -= 1
            if p['lifetime'] > 0:
                p['pos'][0] += p['vel'][0]
                p['pos'][1] += p['vel'][1]
                p['vel'][1] += 0.28   # gravity drag
                p['vel'][0] *= 0.93   # air friction
                alive.append(p)
        self.particles = alive

        # --- Player kills enemies ---
        if self.player.is_attacking:
            attack_x = self.player.rect.centerx + 50 if self.player.facing_right else self.player.rect.centerx - 90
            attack_y = self.player.rect.bottom - 50 if self.player.status == 'duck_attack' else self.player.rect.bottom - 98
            attack_rect = pygame.Rect(attack_x, attack_y, 40, 60)

            for enemy in list(self.enemies):
                if not enemy.hit_flash_until and attack_rect.colliderect(enemy.rect):
                    enemy.register_hit()
                    self.score += 10
                    self.spawn_sparks(enemy.rect.center)   # impact burst

        # --- Parry / projectile reflection ---
        # Must run BEFORE the take-damage check so a successful parry
        # consumes the bullet without also hurting the player.
        if self.player.in_reflect_window:
            attack_x = self.player.rect.centerx + 50 if self.player.facing_right else self.player.rect.centerx - 90
            attack_y = self.player.rect.bottom - 50 if self.player.status == 'duck_attack' else self.player.rect.bottom - 98
            parry_rect = pygame.Rect(attack_x, attack_y, 40, 60)
            for proj in list(self.projectiles):
                if not proj.reflected and parry_rect.colliderect(proj.rect):
                    proj.reflect()
                    self.spawn_sparks(proj.rect.center, count=7)   # deflection burst
                    self.reflect_flash_until = pygame.time.get_ticks() + REFLECT_FLASH_MS

        # --- Reflected projectile hits enemies ---
        for proj in list(self.projectiles):
            if proj.reflected:
                for enemy in list(self.enemies):
                    if not enemy.hit_flash_until and proj.rect.colliderect(enemy.rect):
                        enemy.register_hit()
                        self.score += 25                 # skill bonus
                        self.spawn_sparks(enemy.rect.center, count=14)  # bigger burst
                        proj.kill()
                        break

        # --- Projectile hits player (duck-aware hitbox) ---
        core_hitbox = self.player.get_hitbox()
        for proj in list(self.projectiles):
            if not proj.reflected and proj.rect.colliderect(core_hitbox):
                proj.kill()   # always consume the bullet
                result = self.player.take_damage()
                if result is True:
                    self.trigger_shake(12, 400)
                    self.game_over = True
                elif result is False:
                    self.trigger_shake(6, 200)   # hit — survived
        
    # ------------------------------------------------------------------
    # HUD
    # ------------------------------------------------------------------
    def draw_hud(self):
        """Draw HP bar (bottom-left) and score (top-right)."""
        # --- HP bar (bottom-left) ---
        bar_x, bar_y = 20, SCREEN_HEIGHT - 48
        pip_w, pip_h, pip_gap = 28, 18, 6
        total_bar_w = PLAYER_MAX_HP * (pip_w + pip_gap) - pip_gap + 8

        # Background panel
        panel = pygame.Surface((total_bar_w + 16, pip_h + 20), pygame.SRCALPHA)
        panel.fill((0, 0, 0, 140))
        self.screen.blit(panel, (bar_x - 8, bar_y - 8))

        # "HP" label
        label = self.font_small.render("HP", True, HUD_BORDER)
        self.screen.blit(label, (bar_x, bar_y - 26))

        # Pip hearts
        for i in range(PLAYER_MAX_HP):
            pip_rect = pygame.Rect(bar_x + i * (pip_w + pip_gap), bar_y, pip_w, pip_h)
            color = HUD_RED if i < self.player.hp else HUD_BG
            pygame.draw.rect(self.screen, color, pip_rect, border_radius=4)
            pygame.draw.rect(self.screen, HUD_BORDER, pip_rect, 2, border_radius=4)

        # --- Score (top-right) ---
        score_str = f"SCORE  {self.score:06d}"
        score_surf = self.font_med.render(score_str, True, HUD_GOLD)
        score_rect = score_surf.get_rect(topright=(SCREEN_WIDTH - 20, 16))

        # Shadow for legibility over any background
        shadow = self.font_med.render(score_str, True, (0, 0, 0))
        self.screen.blit(shadow, score_rect.move(2, 2))
        self.screen.blit(score_surf, score_rect)

    # ------------------------------------------------------------------
    # Draw
    # ------------------------------------------------------------------
    def draw(self):
        # --- Compute shake offset ---
        now = pygame.time.get_ticks()
        if now < self.shake_timer:
            ox = random.randint(-self.shake_intensity, self.shake_intensity)
            oy = random.randint(-self.shake_intensity, self.shake_intensity)
        else:
            ox, oy = 0, 0

        # --- Render world to off-screen surface ---
        self.level.draw(self.world_surface)

        for enemy in self.enemies:
            enemy.draw(self.world_surface)

        self.projectiles.draw(self.world_surface)
        self.player.draw(self.world_surface)

        # --- Particles (drawn into world so they shake with it) ---
        for p in self.particles:
            t = max(0.0, p['lifetime'] / p['max_lifetime'])
            radius = max(1, int(p['radius'] * (0.3 + 0.7 * t)))
            pygame.draw.circle(
                self.world_surface, p['color'],
                (int(p['pos'][0]), int(p['pos'][1])), radius
            )

        # --- Glow rings around reflected bullets ---
        for proj in self.projectiles:
            if proj.reflected:
                cx, cy = proj.rect.center
                pygame.draw.circle(self.world_surface, (0, 210, 255), (cx, cy), 16, 2)
                pygame.draw.circle(self.world_surface, WHITE,          (cx, cy),  9, 1)

        # --- Blit world with shake displacement ---
        self.screen.blit(self.world_surface, (ox, oy))

        # --- Parry screen flash (fixed, never shakes, fades quickly) ---
        if now < self.reflect_flash_until:
            t = (self.reflect_flash_until - now) / REFLECT_FLASH_MS
            alpha = int(90 * t)
            flash_overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            flash_overlay.fill((180, 240, 255, alpha))
            self.screen.blit(flash_overlay, (0, 0))

        # --- HUD drawn directly on screen (never shakes) ---
        self.draw_hud()

        # --- Game-over overlay (fixed to screen) ---
        if self.game_over:
            overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 180))
            self.screen.blit(overlay, (0, 0))

            text = self.font_big.render("GAME OVER", True, RED)
            text_rect = text.get_rect(center=(SCREEN_WIDTH/2, SCREEN_HEIGHT/2 - 60))
            self.screen.blit(text, text_rect)

            final_score = self.font_med.render(f"Score: {self.score:06d}", True, HUD_GOLD)
            fs_rect = final_score.get_rect(center=(SCREEN_WIDTH/2, SCREEN_HEIGHT/2))
            self.screen.blit(final_score, fs_rect)

            sub = self.font_small.render("Press ENTER to Restart", True, WHITE)
            sub_rect = sub.get_rect(center=(SCREEN_WIDTH/2, SCREEN_HEIGHT/2 + 52))
            self.screen.blit(sub, sub_rect)

        pygame.display.flip()

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
