import pygame
import os
from settings import *

class Player(pygame.sprite.Sprite):
    def __init__(self, pos):
        super().__init__()
        
        self.import_sprites()
        self.frame_index = 0
        self.animation_speed = 0.15
        
        self.image = self.animations['idle'][self.frame_index]
        self.rect = self.image.get_rect(topleft=pos)
        
        # Physics & Movement Properties
        self.direction = pygame.math.Vector2(0, 0)
        self.speed = PLAYER_SPEED
        self.gravity = GRAVITY
        self.jump_speed = JUMP_FORCE
        
        # State
        self.status = 'idle'
        self.facing_right = True
        self.on_ground = False
        self.can_double_jump = False
        self.is_attacking = False
        self.is_ducking = False
        self.combo_active = False
        self.last_attack_time = 0

        # Health / damage
        self.hp = PLAYER_MAX_HP
        self.invincible_until = 0   # ms timestamp
        self.hit_time = 0           # ms timestamp of last hit (drives flash)

        # Dash state
        self.is_dashing = False
        self.dash_start_time = 0
        self.last_dash_time = 0
        self.last_afterimage_time = 0
        self.dash_direction = 1
        self.afterimages = []
        
        # Ultimate / Energy
        self.energy = 0
        self.ultimate_active_until = 0

    def import_sprites(self):
        self.animations = {'idle': [], 'run': [], 'jump': [], 'attack': []}
        
        player_image_path = os.path.join(IMAGE_DIR, "player.png")
        if not os.path.exists(player_image_path):
            # Fallback block
            for state in self.animations.keys():
                surf = pygame.Surface((128, 128))
                surf.fill(GREEN)
                self.animations[state].append(surf)
            return

        try:
            sheet = pygame.image.load(player_image_path).convert_alpha()
            w, h = sheet.get_size()
            
            # 1. Custom chroma key using precise PixelArray distance to blast any green screen noise
            clean_sheet = pygame.Surface((w, h), pygame.SRCALPHA)
            clean_sheet.fill((0, 0, 0, 0))
            
            px = pygame.PixelArray(sheet)
            cx = pygame.PixelArray(clean_sheet)
            
            bg_color = px[0, 0]
            bg_r, bg_g, bg_b, _ = sheet.unmap_rgb(bg_color)
            
            # Python Loop: ~1-2s at load for perfect noise removal
            for x in range(w):
                for y in range(h):
                    c = px[x, y]
                    r, g, b, _ = sheet.unmap_rgb(c)
                    # Chop off color distances and add explicit spill-suppression to kill the dark green anti-aliased border
                    if abs(r - bg_r) + abs(g - bg_g) + abs(b - bg_b) > 150:
                        if g > r + 15 and g > b + 15:
                            # Instead of deleting (which causes holes in the character model), 
                            # we clamp the excessive green down to the limits of red/blue!
                            # This turns halo edges to black outlines, and fixes helmet reflections to grey/teal.
                            g_clamped = max(r, b)
                            c = sheet.map_rgb((r, g_clamped, b, 255))
                        cx[x, y] = c
                        
            px.close()
            cx.close()
            
            # 2. Extract specific character instances by defining the Bounding Boxes
            mask = pygame.mask.from_surface(clean_sheet)
            rects = mask.get_bounding_rects()
            
            def merge_rects(rects, margin):
                merged = []
                for r in rects:
                    if r.width < 10 or r.height < 10: continue
                    inflated = r.inflate(margin, margin)
                    intersected = False
                    for i, m in enumerate(merged):
                        if inflated.colliderect(m):
                            merged[i] = m.union(r)
                            intersected = True
                            break
                    if not intersected:
                        merged.append(r)
                return merged
            
            # Merge floating or disconnected parts (e.g., weapons/limbs) with tight margin
            merged = merge_rects(rects, 10)
            merged = merge_rects(merged, 10)
            
            # Ditch anything too massive (like AI-generated text or full-sheet merged accidents)
            filtered = [r for r in merged if 30 < r.width < 150 and 40 < r.height < 200]
            
            if not filtered:
                raise Exception("No sprites detected after chroma key!")
                
            # 3. Group by rows (assuming typical AI generation grid)
            filtered.sort(key=lambda r: r.y)
            rows = []
            current_row = []
            last_y = filtered[0].y
            for r in filtered:
                if abs(r.y - last_y) > 40:
                    if current_row:
                        current_row.sort(key=lambda x: x.x)
                        rows.append(current_row)
                    current_row = []
                    last_y = r.y
                current_row.append(r)
            if current_row:
                current_row.sort(key=lambda x: x.x)
                rows.append(current_row)
                
            # Filter to rows that actually look like animation sequences (>= 4 frames)
            valid_rows = [r for r in rows if len(r) >= 4]
            
            # The AI generated the running animation across TWO rows!
            # The second row was generated chronologically right-to-left on the sheet, so we REVERSE it before merging
            if len(valid_rows) >= 2:
                valid_rows[1].reverse()
                valid_rows[0].extend(valid_rows[1])
                valid_rows.pop(1)
                
            # The AI ALSO generated the Jump/Airborne animation across TWO rows! Merge them!
            if len(valid_rows) >= 3:
                valid_rows[1].extend(valid_rows[2])
                valid_rows.pop(2)
                
            state_keys = ['run', 'jump', 'attack', 'double_jump', 'attack_combo', 'duck', 'duck_attack', 'dash']
            
            for state in state_keys:
                if state not in self.animations:
                    self.animations[state] = []
                    
            # Explicit mapping logically based on sequence deductions
            mapping = {}
            if len(valid_rows) > 0: mapping['run'] = valid_rows[0]
            if len(valid_rows) > 1: mapping['jump'] = valid_rows[1]
            if len(valid_rows) > 2: mapping['double_jump'] = valid_rows[2] # Flip
            if len(valid_rows) > 3: mapping['attack'] = valid_rows[3] # Swinging sword
            if len(valid_rows) > 4: mapping['attack_combo'] = valid_rows[4] # Combo
            if len(valid_rows) > 5: mapping['duck'] = valid_rows[5] # Duck
            
            # Find a consistent global scale based on the median run dimension to avoid resizing character when sword is drawn!
            run_frames = mapping.get('run', [])
            if run_frames:
                base_h = sum(r.height for r in run_frames) / len(run_frames)
                base_w = sum(r.width for r in run_frames) / len(run_frames)
            else:
                base_h, base_w = 100.0, 80.0
                
            global_scale = 110.0 / base_h
            scaled_base_w = int(base_w * global_scale)
            
            # Determine a safe Surface size that encompasses ALL frames at this scale (e.g. sword reaches out)
            all_rects = [r for state in mapping for r in mapping[state]]
            if all_rects:
                max_w_scaled = max(int(r.width * global_scale) for r in all_rects)
                max_h_scaled = max(int(r.height * global_scale) for r in all_rects)
            else:
                max_w_scaled, max_h_scaled = 128, 128
                
            SURF_W = 110
            SURF_H = max(128, max_h_scaled + 20)
            if SURF_W % 2 != 0: SURF_W += 1
            if SURF_H % 2 != 0: SURF_H += 1

            for state, rect_list in mapping.items():
                if not rect_list: continue
                
                # Use all bounding boxes found per row (removed arbitrary cutoff)
                for rect in rect_list: 
                    surf = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
                    surf.blit(clean_sheet, (0, 0), rect)
                    
                    # Apply constant global scale to prevent character from shrinking
                    new_w = int(rect.width * global_scale)
                    new_h = int(rect.height * global_scale)
                    scaled_surf = pygame.transform.scale(surf, (new_w, new_h))
                    
                    # If the sprite is exceptionally wide (like a sword swing to the right), 
                    # we anchor to the left side to prevent the character's body from lunging backwards due to centering!
                    offset_x = (SURF_W - new_w) // 2
                    if new_w > scaled_base_w * 1.3:
                        offset_x = (SURF_W - scaled_base_w) // 2
                        
                    # Center at the bottom of the bounding box
                    final_surf = pygame.Surface((SURF_W, SURF_H), pygame.SRCALPHA)
                    final_surf.blit(scaled_surf, (offset_x, SURF_H - new_h))
                    
                    self.animations[state].append(final_surf)
                    
            if len(self.animations['run']) >= 4:
                # The AI gave us 4 frames of idle breathing before the run cycle starts!
                # Extract all 4 frames directly into the idle animation and remove them from run!
                for _ in range(4):
                    self.animations['idle'].append(self.animations['run'].pop(0))
            elif self.animations['run']:
                self.animations['idle'].append(self.animations['run'].pop(0))
                
            # Synthesize a duck animation if one wasn't found on the sprite sheet!
            if not self.animations.get('duck') and self.animations.get('idle'):
                idle_frame = self.animations['idle'][0]
                w, h = idle_frame.get_size()
                
                # Squash character vertically to simulate a crouch
                crouch_height = int(h * 0.65)
                squashed = pygame.transform.scale(idle_frame, (w, crouch_height))
                
                # Create surface and anchor the squashed sprite to the floor (bottom)
                duck_surf = pygame.Surface((w, h), pygame.SRCALPHA)
                duck_surf.blit(squashed, (0, h - crouch_height))
                self.animations['duck'].append(duck_surf)
                
            # Synthesize a duck_attack animation by squashing the standard attack frames
            if not self.animations.get('duck_attack') and self.animations.get('attack'):
                for atk_frame in self.animations['attack']:
                    w, h = atk_frame.get_size()
                    
                    crouch_height = int(h * 0.65)
                    squashed = pygame.transform.scale(atk_frame, (w, crouch_height))
                    
                    duck_atk_surf = pygame.Surface((w, h), pygame.SRCALPHA)
                    duck_atk_surf.blit(squashed, (0, h - crouch_height))
                    self.animations['duck_attack'].append(duck_atk_surf)

            # Assign dash to use the duck animation
            if not self.animations.get('dash') and self.animations.get('duck'):
                self.animations['dash'] = self.animations['duck'][:]
                
        except Exception as e:
            print("Failed to slice sprite sheet:", e)
            
        # Fallback if anything failed and lists are empty
        if not self.animations['idle']:
            for state in self.animations.keys():
                surf = pygame.Surface((128, 128))
                surf.fill(GREEN)
                self.animations[state].append(surf)
            
    def get_input(self):
        keys = pygame.key.get_pressed()

        # ── Joystick polling (hat switch + axis fallback) ─────────────────
        joy_left = joy_right = joy_up = joy_down = False
        if pygame.joystick.get_count() > 0:
            # Cache the Joystick object — avoid Joystick(0) lookup at 60 fps
            if not hasattr(self, '_joystick') or self._joystick is None:
                self._joystick = pygame.joystick.Joystick(0)
            joy = self._joystick
            # Hat / D-pad
            if joy.get_numhats() > 0:
                hx, hy = joy.get_hat(0)
                joy_left  = hx == -1
                joy_right = hx ==  1
                joy_up    = hy ==  1
                joy_down  = hy == -1
            # Analog axis fallback
            DEADZONE = 0.5
            if joy.get_numaxes() > 0:
                ax = joy.get_axis(0)
                if ax < -DEADZONE: joy_left  = True
                if ax >  DEADZONE: joy_right = True
            if joy.get_numaxes() > 1:
                ay = joy.get_axis(1)
                if ay < -DEADZONE: joy_up   = True
                if ay >  DEADZONE: joy_down = True
        else:
            self._joystick = None   # reset on disconnect

        # ── State locks (duck) ────────────────────────────────────────────
        if not self.is_attacking:
            self.is_ducking = False
            if self.on_ground:
                if keys[pygame.K_s] or keys[pygame.K_DOWN] or joy_down:
                    self.is_ducking = True

        # ── Horizontal movement ───────────────────────────────────────────
        if not self.is_ducking:
            if keys[pygame.K_RIGHT] or keys[pygame.K_d] or joy_right:
                self.direction.x = 1
                self.facing_right = True
            elif keys[pygame.K_LEFT] or keys[pygame.K_a] or joy_left:
                self.direction.x = -1
                self.facing_right = False
            else:
                self.direction.x = 0
        else:
            self.direction.x = 0
                
    def handle_event(self, event):
        # ── Keyboard ──────────────────────────────────────────────────────
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_SPACE or event.key == pygame.K_w or event.key == pygame.K_UP:
                if self.on_ground:
                    self.jump()
                elif self.can_double_jump:
                    self.double_jump()
            elif event.key == pygame.K_z or event.key == pygame.K_j:
                self.attack()
            elif event.key == pygame.K_LSHIFT or event.key == pygame.K_RSHIFT:
                self.dash()
            elif event.key == pygame.K_f:
                self.use_ultimate()
        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:
                self.attack()
            elif event.button == 3:
                self.dash()

        # ── Joystick hat (fires once per direction change) ────────────────
        elif event.type == pygame.JOYHATMOTION:
            hx, hy = event.value
            if hy == 1:          # hat UP → jump
                if self.on_ground:
                    self.jump()
                elif self.can_double_jump:
                    self.double_jump()

        # ── Joystick buttons ──────────────────────────────────────────────
        elif event.type == pygame.JOYBUTTONDOWN:
            # Button 0 / 2 → attack  (A/X on most USB sticks)
            if event.button in (0, 2):
                self.attack()
            # Button 1 / 3 → jump    (B/Y on most USB sticks)
            elif event.button in (1, 3):
                if self.on_ground:
                    self.jump()
                elif self.can_double_jump:
                    self.double_jump()
            # Button 5 → RB → dash
            elif event.button == 5:
                self.dash()
            # Button 4 → LB → Ultimate
            elif event.button == 4:
                self.use_ultimate()

    def get_status(self):
        if self.is_dashing:
            self.status = 'dash' if self.animations.get('dash') else 'duck'
        elif self.is_attacking:
            if self.is_ducking and self.animations.get('duck_attack'):
                self.status = 'duck_attack'
            else:
                self.status = 'attack_combo' if self.combo_active and self.animations.get('attack_combo') else 'attack'
        elif self.is_ducking:
            self.status = 'duck' if self.animations.get('duck') else 'idle'
        elif not self.on_ground:
            if hasattr(self, 'is_double_jumping') and self.is_double_jumping:
                # Fallback to normal jump if double jump animation is empty
                self.status = 'double_jump' if self.animations.get('double_jump') else 'jump'
            else:
                self.status = 'jump'
        elif self.direction.x != 0:
            self.status = 'run'
        else:
            self.status = 'idle'
            
    def animate(self):
        animation = self.animations[self.status]
        
        self.frame_index += self.animation_speed
        # specific animation modifiers
        if self.status in ['attack', 'attack_combo', 'duck_attack']:
            self.frame_index += 0.15 # Swing sword 50% faster (Total 0.30 vs previous 0.20)
        elif self.status == 'double_jump':
            self.frame_index += 0.05 # Flips can be slightly faster
            
        if self.frame_index >= len(animation):
            if self.status in ['attack', 'attack_combo', 'duck_attack']:
                self.is_attacking = False
                self.combo_active = False
                self.last_attack_time = pygame.time.get_ticks()
                self.frame_index = 0
                self.get_status()
                animation = self.animations[self.status]
            elif self.status in ['jump', 'duck']:
                # Hold on the last frame of the static pose (don't loop)
                self.frame_index = len(animation) - 1
            else:
                self.frame_index = 0
                
        self.image = animation[int(self.frame_index)]

    def jump(self):
        self.direction.y = self.jump_speed
        self.on_ground = False
        self.can_double_jump = True
        self.is_double_jumping = False
        
    def double_jump(self):
        self.direction.y = DOUBLE_JUMP_FORCE
        self.can_double_jump = False
        self.is_double_jumping = True
        self.frame_index = 0
        self.double_jump_attack_until = pygame.time.get_ticks() + 1000
        
    def attack(self):
        if not self.is_attacking:
            current_time = pygame.time.get_ticks()
            if current_time - self.last_attack_time < 1000 and self.animations.get('attack_combo'):
                self.combo_active = True
            else:
                self.combo_active = False
                
            self.is_attacking = True
            self.frame_index = 0

    def dash(self):
        now = pygame.time.get_ticks()
        # Don't allow dash while in ultimate cast invincibility
        if now < self.ultimate_active_until: return
        
        if now - self.last_dash_time > DASH_COOLDOWN_MS:
            # Cancel ongoing attacks
            self.is_attacking = False
            self.combo_active = False
            self.is_dashing = True
            
            self.dash_start_time = now
            self.last_dash_time = now
            self.dash_direction = 1 if self.facing_right else -1
            self.invincible_until = max(self.invincible_until, now + DASH_IFRAME_DURATION_MS)
            
            self.afterimages = []
            self.last_afterimage_time = now

    def take_damage(self):
        """Called by main when a projectile hits.
        Returns  True  if the player just died,
                 False if hit + survived,
                 None  if blocked by invincibility frames."""
        now = pygame.time.get_ticks()
        if now < self.invincible_until or now < self.ultimate_active_until:
            return None           # i-frames active — bullet consumed but no effect
            
        self.hp -= 1
        self.hit_time = now
        self.invincible_until = now + INVINCIBILITY_MS
        self.gain_energy(ENERGY_PER_DAMAGE_TAKEN)
        return self.hp <= 0
        
    def gain_energy(self, amount):
        now = pygame.time.get_ticks()
        if now < self.ultimate_active_until:
            return # Can't gain energy while casting ultimate
        self.energy = min(PLAYER_MAX_ENERGY, self.energy + amount)
        
    def use_ultimate(self):
        if self.energy >= PLAYER_MAX_ENERGY:
            self.energy = 0
            now = pygame.time.get_ticks()
            self.ultimate_active_until = now + ULTIMATE_IFRAME_MS
            # Flash full screen will be handled by main checking this property
            self.trigger_ultimate_flag = True

    def get_hitbox(self):
        """Return the current collision rect, duck-aware.
        Crouching covers only the bottom 45 % of the sprite so ground-level
        projectiles (aimed at the enemy's chest/gun) pass over the player."""
        if self.is_ducking:
            duck_h = int(self.rect.height * 0.45)
            return pygame.Rect(
                self.rect.x + 20,
                self.rect.bottom - duck_h,
                self.rect.width - 40,
                duck_h - 5,
            )
        return self.rect.inflate(-40, -40)

    @property
    def in_reflect_window(self):
        """True during the precise frames where the blade is mid-swing.
        Hitting a projectile in this window reflects it back at enemies."""
        return (
            self.is_attacking and
            REFLECT_FRAME_START <= self.frame_index <= REFLECT_FRAME_END
        )

    def apply_gravity(self, platforms=()):
        self.direction.y += self.gravity
        self.rect.y += self.direction.y

        # Floor collision
        if self.rect.bottom >= FLOOR_Y:
            self.rect.bottom = FLOOR_Y
            self.direction.y = 0
            self.on_ground = True
            self.can_double_jump = False
            self.is_double_jumping = False
            self.double_jump_attack_until = 0
        else:
            # Platform collision (only when falling)
            landed = False
            if self.direction.y >= 0:
                for plat in platforms:
                    pr = plat['rect']
                    if (self.rect.bottom - self.direction.y <= pr.top + 14
                            and self.rect.bottom >= pr.top
                            and self.rect.right > pr.left + 8
                            and self.rect.left  < pr.right - 8):
                        self.rect.bottom = pr.top
                        self.direction.y  = 0
                        self.on_ground    = True
                        self.can_double_jump  = False
                        self.is_double_jumping = False
                        self.double_jump_attack_until = 0
                        landed = True
                        break
            if not landed:
                self.on_ground = False

    def update(self, platforms=()):
        self.get_input()

        now = pygame.time.get_ticks()
        
        if self.is_dashing:
            if now - self.dash_start_time < DASH_DURATION_MS:
                self.direction.x = self.dash_direction
                self.speed = DASH_SPEED
                
                # spawn afterimages
                if now - self.last_afterimage_time > AFTERIMAGE_INTERVAL_MS:
                    # store image without the hit flash modification yet
                    self.afterimages.append({
                        'image': getattr(self, 'display_image', self.image).copy(),
                        'rect': self.rect.copy(),
                        'time': now
                    })
                    self.last_afterimage_time = now
            else:
                self.is_dashing = False
                self.speed = PLAYER_SPEED
                self.direction.x = 0
        else:
            self.speed = PLAYER_SPEED

        # Clean old afterimages (fade duration ~250ms)
        self.afterimages = [ai for ai in self.afterimages if now - ai['time'] < 250]

        self.get_status()
        self.animate()

        # Horizontal movement
        self.rect.x += self.direction.x * self.speed

        # Apply vertical physics (platform-aware)
        self.apply_gravity(platforms)

        # Flip image if moving left
        if not self.facing_right:
            self.display_image = pygame.transform.flip(self.image, True, False)
        else:
            self.display_image = self.image

    def draw(self, surface):
        draw_img = self.display_image if hasattr(self, 'display_image') else self.image
        now = pygame.time.get_ticks()

        # Draw dash afterimages
        for ai in self.afterimages:
            age = now - ai['time']
            alpha = max(0, 150 - int((age / 250) * 150))
            if alpha > 0:
                ghost = ai['image'].copy()
                ghost.set_alpha(alpha)
                # Apply a slight cyan/blue tint to afterimages
                ghost.fill((0, 150, 255, 0), special_flags=pygame.BLEND_RGBA_ADD)
                surface.blit(ghost, ai['rect'])

        # --- Hit flash: rapidly cycle a red-tinted copy while invincible ---
        if now < self.invincible_until or now < self.ultimate_active_until:
            elapsed = now - self.hit_time if now > self.hit_time else 0
            flash_on = (elapsed // HIT_FLASH_DURATION) % 2 == 0
            
            # If ultimate is active, flash blue/cyan instead!
            if now < self.ultimate_active_until:
                flash_on = True
                flash_surf = draw_img.copy()
                flash_surf.fill((0, 200, 255, 160), special_flags=pygame.BLEND_RGBA_MULT)
                surface.blit(flash_surf, self.rect)
            elif flash_on:
                # Build a red overlay the same size as the current frame
                flash_surf = draw_img.copy()
                flash_surf.fill((220, 0, 0, 160), special_flags=pygame.BLEND_RGBA_MULT)
                surface.blit(flash_surf, self.rect)
            else:
                # On the "off" phase show the sprite semi-transparent (ghost effect)
                ghost = draw_img.copy()
                ghost.set_alpha(100)
                surface.blit(ghost, self.rect)
        else:
            surface.blit(draw_img, self.rect)

        # Debug Hitbox for attack
        if self.is_attacking:
            # Use centerx and bottom so hitbox remains aligned with visually anchored character regardless of dynamic surface size
            attack_x = self.rect.centerx + 30 if self.facing_right else self.rect.centerx - 70

            # Lower the attack box sweeping arc if performing a duck attack!
            if self.status == 'duck_attack':
                attack_y = self.rect.bottom - 50
            else:
                attack_y = self.rect.bottom - 98

            attack_rect = pygame.Rect(attack_x, attack_y, 40, 60)
            # pygame.draw.rect(surface, LASER_BLUE, attack_rect, 2)
