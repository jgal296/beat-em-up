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
HUD_RED    = (220,  50,  50)
HUD_BG     = ( 50,  20,  20)
HUD_BORDER = (200, 200, 200)
HUD_GOLD   = (255, 210,  50)
HIT_FLASH_ENEMY = (255, 255, 255)

# Platforms
PLATFORM_H          = 16
PLATFORM_COLOR_TOP  = (  0, 210, 255)   # cyan top-glow edge
PLATFORM_COLOR_BODY = ( 22,  22,  55)   # dark body
PLATFORM_COLOR_GLOW = (  0, 120, 200)   # border glow

# Enemy tints (RGBA multiplied onto copies of base frames)
HEAVY_ENEMY_TINT  = (130,  60, 255, 255)   # deep purple

# Spawn weights (must sum to 1.0)
SPAWN_W_SHOOTER = 0.30
SPAWN_W_MELEE   = 0.25
SPAWN_W_HEAVY   = 0.15
SPAWN_W_SHIELD  = 0.15
SPAWN_W_FLYING  = 0.15

# Energy and Ultimate
PLAYER_MAX_ENERGY    = 100
ENERGY_PER_HIT       = 10
ENERGY_PER_DAMAGE_TAKEN = 5
ULTIMATE_DAMAGE      = 2
ULTIMATE_IFRAME_MS   = 1500
HUD_BLUE             = (0, 150, 255)

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

# Dash / Dodge Roll
DASH_SPEED = 18
DASH_DURATION_MS = 250
DASH_COOLDOWN_MS = 700
DASH_IFRAME_DURATION_MS = 250
AFTERIMAGE_INTERVAL_MS = 40

# Combat / Health
PLAYER_MAX_HP        = 5          # number of hit points
INVINCIBILITY_MS     = 1200       # ms of i-frames after a hit
HIT_FLASH_DURATION   = 80         # ms each flash cycle lasts
ENEMY_HIT_FLASH_MS   = 120        # ms enemy flashes white before dying

# Projectile reflection (parry)
REFLECT_FRAME_START = 0.4   # attack frame_index when parry window opens
REFLECT_FRAME_END   = 2.0   # attack frame_index when parry window closes
REFLECT_FLASH_MS    = 200   # ms the reflected bullet pulses bright + screen flashes
