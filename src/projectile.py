import pygame
from settings import *

class Projectile(pygame.sprite.Sprite):
    def __init__(self, pos, facing_right):
        super().__init__()

        self.reflected         = False
        self.reflect_flash_until = 0
        self._facing_right     = facing_right

        self._build_normal_image()
        self.rect  = self.image.get_rect(center=pos)
        self.speed = 12 if facing_right else -12

    # ------------------------------------------------------------------
    # Visuals
    # ------------------------------------------------------------------
    def _build_normal_image(self):
        """Enemy bullet: white core with a gold border."""
        surf = pygame.Surface((15, 6))
        surf.fill(WHITE)
        pygame.draw.rect(surf, (255, 200, 0), surf.get_rect(), 2)
        self.image      = surf
        self.base_image = surf.copy()

    def _build_reflected_image(self):
        """Reflected bullet: larger cyan bolt."""
        surf = pygame.Surface((22, 9))
        surf.fill((0, 210, 255))          # vivid cyan
        pygame.draw.rect(surf, WHITE, surf.get_rect(), 2)
        # Bright centre highlight line
        pygame.draw.line(surf, (200, 255, 255), (2, 4), (19, 4), 2)
        self.image      = surf
        self.base_image = surf.copy()

    # ------------------------------------------------------------------
    # Reflection
    # ------------------------------------------------------------------
    def reflect(self):
        """Flip and accelerate; enter flash state."""
        self.speed    = -self.speed * 1.3   # 30 % faster when returned
        self.reflected = True
        self.reflect_flash_until = pygame.time.get_ticks() + REFLECT_FLASH_MS

        # Restyle and re-centre rect
        center = self.rect.center
        self._build_reflected_image()
        self.rect = self.image.get_rect(center=center)

    # ------------------------------------------------------------------
    # Update / Draw
    # ------------------------------------------------------------------
    def update(self):
        self.rect.x += int(self.speed)

        # Pulse white↔cyan during the reflect flash window
        now = pygame.time.get_ticks()
        if now < self.reflect_flash_until:
            elapsed = now - (self.reflect_flash_until - REFLECT_FLASH_MS)
            if (elapsed // 45) % 2 == 0:
                bright = self.base_image.copy()
                bright.fill((255, 255, 255), special_flags=pygame.BLEND_RGB_ADD)
                self.image = bright
            else:
                self.image = self.base_image
        else:
            self.image = self.base_image

        # Cull when well off-screen
        if self.rect.right < -1000 or self.rect.left > SCREEN_WIDTH + 1000:
            self.kill()

class Bomb(pygame.sprite.Sprite):
    def __init__(self, pos):
        super().__init__()
        # Bomb visual: larger reddish circle
        self.image = pygame.Surface((18, 18), pygame.SRCALPHA)
        pygame.draw.circle(self.image, (255, 50, 50), (9, 9), 9)
        pygame.draw.circle(self.image, (255, 200, 0), (9, 9), 4)
        
        self.rect = self.image.get_rect(center=pos)
        self.direction_y = 2  # initial fall speed
        self.gravity = GRAVITY * 0.5  # falls slower than player

    def update(self):
        self.direction_y += self.gravity
        self.rect.y += self.direction_y
        
        # Kill bomb if it falls out of screen without hitting the floor 
        if self.rect.top > SCREEN_HEIGHT + 200:
            self.kill()
