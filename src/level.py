import pygame
import os
from settings import *

class Level:
    def __init__(self):
        self.display_surface = pygame.display.get_surface()
        self.bg_scroll = 0
        
        # Load background
        bg_path = os.path.join(IMAGE_DIR, "background.png")
        if os.path.exists(bg_path):
            self.background = pygame.image.load(bg_path).convert()
            # scale background to fill screen height and maintain aspect ratio
            bg_rect = self.background.get_rect()
            scale_ratio = SCREEN_HEIGHT / bg_rect.height
            new_size = (int(bg_rect.width * scale_ratio), SCREEN_HEIGHT)
            self.background = pygame.transform.scale(self.background, new_size)
        else:
            self.background = None

        self.world_shift = 0

    def scroll_x(self, player_rect, player_direction_x):
        # We handle screen scrolling based on player position
        if player_rect.centerx < SCREEN_WIDTH // 4 and player_direction_x < 0:
            self.world_shift = PLAYER_SPEED
            player_rect.x += PLAYER_SPEED  # push player back to keep them on screen relative
        elif player_rect.centerx > SCREEN_WIDTH - (SCREEN_WIDTH // 4) and player_direction_x > 0:
            self.world_shift = -PLAYER_SPEED
            player_rect.x -= PLAYER_SPEED  # push player back
        else:
            self.world_shift = 0
            
    def update(self):
        self.bg_scroll += self.world_shift * 0.5  # parallax effect (moves slower than world)

    def draw(self):
        if self.background:
            bg_width = self.background.get_width()
            # Calculate scroll relative to image width
            rel_x = self.bg_scroll % bg_width
            
            # Calculate how many tiles we need to cover the screen width
            num_tiles = (SCREEN_WIDTH // bg_width) + 2
            
            # Draw primary background and tile it horizontally
            for i in range(-1, num_tiles):
                self.display_surface.blit(self.background, (rel_x + i * bg_width, 0))
        else:
            self.display_surface.fill(BG_COLOR)
            
        # Draw floor line for reference
        pygame.draw.line(self.display_surface, WHITE, (0, FLOOR_Y), (SCREEN_WIDTH, FLOOR_Y), 2)
