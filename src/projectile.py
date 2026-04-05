import pygame
from settings import *

class Projectile(pygame.sprite.Sprite):
    def __init__(self, pos, facing_right):
        super().__init__()
        
        self.image = pygame.Surface((15, 6))
        self.image.fill(WHITE)
        pygame.draw.rect(self.image, (255, 200, 0), self.image.get_rect(), 2) # Yellow/Orange border
        
        self.rect = self.image.get_rect(center=pos)
        self.speed = 12 if facing_right else -12
        
    def update(self):
        self.rect.x += self.speed
        
        # Destroy if it gets completely off screen
        if self.rect.right < -1000 or self.rect.left > SCREEN_WIDTH + 1000:
            self.kill()
