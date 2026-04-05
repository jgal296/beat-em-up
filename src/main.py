import pygame
import sys
import os
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
        
    def reset_game(self):
        self.player = Player((100, FLOOR_Y - 80))
        self.enemies.empty()
        self.projectiles.empty()
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
            
        current_time = pygame.time.get_ticks()
        if current_time - self.last_spawn_time > self.spawn_delay:
            import random
            spawn_x = -100 if random.choice([True, False]) else SCREEN_WIDTH + 100
            self.enemies.add(Enemy((spawn_x, FLOOR_Y), self.player, self.projectiles))
            self.last_spawn_time = current_time
            self.spawn_delay = max(1000, self.spawn_delay - 100)
            
        self.enemies.update()
        self.projectiles.update()
        
        # Player kills enemies — use register_hit() so the flash plays first
        if self.player.is_attacking:
            attack_x = self.player.rect.centerx + 50 if self.player.facing_right else self.player.rect.centerx - 90
            attack_y = self.player.rect.bottom - 50 if self.player.status == 'duck_attack' else self.player.rect.bottom - 98
            attack_rect = pygame.Rect(attack_x, attack_y, 40, 60)

            for enemy in list(self.enemies):
                if not enemy.hit_flash_until and attack_rect.colliderect(enemy.rect):
                    enemy.register_hit()
                    self.score += 10

        # Projectile hits player — respects invincibility frames
        core_hitbox = self.player.rect.inflate(-40, -40)
        for proj in list(self.projectiles):
            if proj.rect.colliderect(core_hitbox):
                proj.kill()   # always consume the bullet
                if self.player.take_damage():
                    self.game_over = True
        
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

    def draw(self):
        self.level.draw()

        # Ensure enemies draw correctly
        for enemy in self.enemies:
            enemy.draw(self.screen)

        self.projectiles.draw(self.screen)
        self.player.draw(self.screen)

        self.draw_hud()

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
