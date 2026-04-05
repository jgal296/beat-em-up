import os

# Screen dimensions
SCREEN_WIDTH = 1280
SCREEN_HEIGHT = 720
FPS = 60

# Colors
BG_COLOR = (20, 20, 40)
WHITE = (255, 255, 255)
RED = (255, 0, 0)
GREEN = (0, 255, 0)
LASER_BLUE = (0, 200, 255)
HUD_RED    = (220,  50,  50)   # HP bar filled
HUD_BG     = ( 50,  20,  20)   # HP bar background
HUD_BORDER = (200, 200, 200)   # HP bar outline
HUD_GOLD   = (255, 210,  50)   # Score text
HIT_FLASH_ENEMY = (255, 255, 255)  # white flash on enemy hit

# Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMAGE_DIR = os.path.join(BASE_DIR, "assets", "images")
AUDIO_DIR = os.path.join(BASE_DIR, "assets", "audio")

# Physics / Movement
GRAVITY = 0.8
PLAYER_SPEED = 7
JUMP_FORCE = -15
DOUBLE_JUMP_FORCE = -12

# Floor height (where characters walk)
FLOOR_Y = SCREEN_HEIGHT - 100

# Combat / Health
PLAYER_MAX_HP        = 5          # number of hit points
INVINCIBILITY_MS     = 1200       # ms of i-frames after a hit
HIT_FLASH_DURATION   = 80         # ms each flash cycle lasts
ENEMY_HIT_FLASH_MS   = 120        # ms enemy flashes white before dying
