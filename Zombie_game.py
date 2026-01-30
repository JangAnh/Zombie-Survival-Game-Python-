import pygame  # Thư viện chính xây dựng game 2D
import math  # Thực hiện các phép toán hình học
import random  # Sinh giá trị ngẫu nhiên
import os  # Làm việc với hệ thống file
import array  # Xử lý dữ liệu âm thanh
from datetime import datetime  # Xử lý thời gian thực

# --- CẤU HÌNH GAME ---
DEFAULT_WIDTH = 1024
DEFAULT_HEIGHT = 768
FPS = 60
PLAYER_SPEED = 5
BULLET_SPEED = 20
BULLET_COOLDOWN = 100
ZOMBIE_SPEED_MIN = 1.2
ZOMBIE_SPEED_MAX = 2.5
ZOMBIE_DAMAGE = 20
DAMAGE_COOLDOWN = 1000
SPAWN_RATE_START = 80
DIFFICULTY_INCREASE_INTEROVAL = 5000
MAX_ZOMBIE_SPEED = 4.5
PLAYER_MAX_HEALTH = 100

# --- MÀU SẮC ---
WHITE = (240, 240, 240)
BLACK = (10, 10, 15)
RED = (255, 50, 50)
BLUE = (0, 180, 255)
YELLOW = (255, 215, 0)
GREEN = (50, 255, 50)
CYAN = (0, 255, 255)
DARK_GRAY = (35, 35, 40)
BLOOD_RED = (180, 0, 0)
NEON_PURPLE = (150, 0, 255)
ORANGE = (255, 120, 0)

# --- KHỞI TẠO ---
pygame.init()
pygame.mixer.init()
pygame.mixer.set_num_channels(16)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

SOUND_DIR = os.path.join(BASE_DIR, "sounds")

def load_sound(name, volume):
    path = os.path.join(SOUND_DIR, name)
    try:
        snd = pygame.mixer.Sound(path)
        snd.set_volume(volume)
        return snd
    except Exception as e:
        print(f"[WARNING] Không tải được âm thanh: {name} → chuyển sang chế độ âm thanh mặc định")
        fallback = create_sound(440, 0.08)
        fallback.set_volume(volume)
        return fallback

SND_SHOOT = load_sound("shoot.wav", 0.6)
SND_ZOMBIE_DIE = load_sound("explosion.wav", 0.8)
SND_POWERUP = load_sound("powerUp.wav", 0.6)
SND_GAMEOVER = load_sound("gameover.wav", 1.0)
SND_HIT = load_sound("hit.wav", 0.7)

screen = pygame.display.set_mode((DEFAULT_WIDTH, DEFAULT_HEIGHT), pygame.RESIZABLE)
pygame.display.set_caption("KỶ NGUYÊN ZOMBIE")
clock = pygame.time.Clock()

# --- BIẾN TOÀN CỤC ---
is_paused = False
sound_enabled = True
show_help = False


# --- HỆ THỐNG ÂM THANH TỰ TẠO (SYNTHETIC SOUNDS) ---
def create_sound(frequency, duration, volume=0.1, type='square'):
    """Tạo âm thanh thô nếu không có file âm thanh bên ngoài"""
    sample_rate = 44100
    n_samples = int(sample_rate * duration)
    buf = array.array('h', [0] * n_samples)
    for i in range(n_samples):
        t = i / sample_rate
        if type == 'square':
            val = volume * (1 if math.sin(2 * math.pi * frequency * t) > 0 else -1)
        else:  # sine
            val = volume * math.sin(2 * math.pi * frequency * t)
        buf[i] = int(val * 32767)
    return pygame.mixer.Sound(buffer=buf)


def toggle_sounds():
    """Bật/Tắt toàn bộ âm thanh hệ thống"""
    global sound_enabled
    if sound_enabled:
        pygame.mixer.pause()
    else:
        pygame.mixer.unpause()
    sound_enabled = not sound_enabled


# --- FONT ---
def get_font(size):
    """Hàm lấy font hệ thống hoặc font mặc định nếu lỗi"""
    try:
        return pygame.font.SysFont('Segoe UI', size, bold=True)
    except:
        return pygame.font.Font(None, size)


# --- HỆ THỐNG VẾT MÁU TRÊN SÀN ---
class BloodStain:
    """Lớp quản lý các vết máu rơi trên sàn khi zombie chết"""

    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.size = random.randint(15, 35)
        self.color = (random.randint(100, 150), 0, 0)
        self.surface = pygame.Surface((self.size * 2, self.size * 2), pygame.SRCALPHA)
        pygame.draw.circle(self.surface, (*self.color, 120), (self.size, self.size), self.size)
        self.lifetime = 600  # Tồn tại 10 giây (600 frames)

    def draw(self, surface):
        if self.lifetime > 0:
            surface.blit(self.surface, (self.x - self.size, self.y - self.size))
            if not is_paused:  # Chỉ giảm thời gian tồn tại khi không pause
                self.lifetime -= 1


# --- HỆ THỐNG HẠT ---
class Particle:
    """Lớp tạo hiệu ứng hạt (cháy nổ, tia lửa, máu bắn)"""

    def __init__(self, x, y, color):
        self.x = x
        self.y = y
        self.color = color
        self.vx = random.uniform(-4, 4)
        self.vy = random.uniform(-4, 4)
        self.lifetime = random.randint(15, 35)
        self.initial_lifetime = self.lifetime
        self.size = random.randint(3, 6)

    def update(self):
        if is_paused: return  # Không cập nhật khi pause
        self.x += self.vx
        self.y += self.vy
        self.lifetime -= 1
        self.size = max(0, self.size - 0.15)

    def draw(self, surface):
        if self.lifetime > 0:
            alpha = int((self.lifetime / self.initial_lifetime) * 255)
            s = pygame.Surface((int(self.size * 2), int(self.size * 2)), pygame.SRCALPHA)
            pygame.draw.circle(s, (*self.color, alpha), (int(self.size), int(self.size)), int(self.size))
            surface.blit(s, (int(self.x - self.size), int(self.y - self.size)))


# --- DRONE ĐỒNG HÀNH ---
class CombatDrone:
    """Drone tự động bay quanh người chơi và bắn zombie"""

    def __init__(self):
        self.angle = 0
        self.distance = 80
        self.last_shot = 0
        self.cooldown = 800
        self.x = 0
        self.y = 0

    def update(self, p_rect, zombies, bullets):
        if is_paused: return
        self.angle += 0.05
        self.x = p_rect.centerx + math.cos(self.angle) * self.distance
        self.y = p_rect.centery + math.sin(self.angle) * self.distance

        now = pygame.time.get_ticks()
        if now - self.last_shot > self.cooldown and zombies:
            closest_zombie = None
            min_dist = 400
            for z in zombies:
                dist = math.hypot(z.rect.centerx - self.x, z.rect.centery - self.y)
                if dist < min_dist:
                    min_dist = dist
                    closest_zombie = z

            if closest_zombie:
                bullets.add(Bullet((self.x, self.y), closest_zombie.rect.center))
                if sound_enabled: SND_SHOOT.play()
                self.last_shot = now

    def draw(self, surface):
        pygame.draw.circle(surface, DARK_GRAY, (int(self.x), int(self.y)), 10)
        pygame.draw.circle(surface, CYAN, (int(self.x), int(self.y)), 6)
        for a in range(4):
            off_x = math.cos(self.angle * 2 + a * math.pi / 2) * 12
            off_y = math.sin(self.angle * 2 + a * math.pi / 2) * 12
            pygame.draw.line(surface, WHITE, (self.x, self.y), (self.x + off_x, self.y + off_y), 2)


# --- VẬT PHẨM HỖ TRỢ (POWER-UPS) ---
class PowerUp(pygame.sprite.Sprite):
    """Các gói vật phẩm rơi ra khi giết zombie"""

    def __init__(self, x, y):
        super().__init__()
        self.type = random.choice(['HEAL', 'SHOTGUN', 'SPEED', 'SHIELD', 'NUKE'])
        self.image = pygame.Surface((30, 30), pygame.SRCALPHA)
        color = GREEN if self.type == 'HEAL' else ORANGE if self.type == 'SHOTGUN' else BLUE if self.type == 'SPEED' else CYAN if self.type == 'SHIELD' else YELLOW
        pygame.draw.rect(self.image, color, (0, 0, 30, 30), border_radius=5)
        pygame.draw.rect(self.image, WHITE, (0, 0, 30, 30), 2, border_radius=5)
        self.rect = self.image.get_rect(center=(x, y))
        self.created_at = pygame.time.get_ticks()

    def update(self):
        if is_paused: return
        if pygame.time.get_ticks() - self.created_at > 10000:
            self.kill()


# --- QUẢN LÝ NGƯỜI CHƠI & ĐIỂM ---
class UserManager:
    """Lưu trữ tên người chơi và quản lý bảng xếp hạng"""

    def __init__(self):
        self.current_user = "Kẻ Vô Danh"
        self.score_file = "leaderboard.txt"

    def save_high_score(self, score):
        try:
            with open(self.score_file, "a", encoding="utf-8") as f:
                f.write(f"{self.current_user}|{score}|{datetime.now().strftime('%d/%m/%Y')}\n")
        except:
            pass

    def get_leaderboard(self):
        if not os.path.exists(self.score_file): return []
        scores = []
        try:
            with open(self.score_file, "r", encoding="utf-8") as f:
                for line in f:
                    parts = line.strip().split('|')
                    if len(parts) == 3: scores.append(parts)
            scores.sort(key=lambda x: int(x[1]), reverse=True)
        except:
            pass
        return scores[:5]


user_manager = UserManager()


# --- HIỆU ỨNG HÌNH ẢNH NỀN ---
class BackgroundEffect:
    """Tạo lưới (grid) và hiệu ứng sao rơi ở nền"""
    def __init__(self, w, h):
        self.stars = [[random.randint(0, w), random.randint(0, h), random.random() * 0.5 + 0.2] for _ in range(150)]
        self.grid_size = 60

    def draw(self, surface):
        w, h = surface.get_size()
        for x in range(0, w, self.grid_size):
            pygame.draw.line(surface, (15, 15, 25), (x, 0), (x, h))
        for y in range(0, h, self.grid_size):
            pygame.draw.line(surface, (15, 15, 25), (0, y), (w, y))

        for s in self.stars:
            if not is_paused: s[1] += s[2]  # Chỉ di chuyển khi không pause
            if s[1] > h: s[1] = 0
            color_val = int(s[2] * 200)
            pygame.draw.circle(surface, (color_val, color_val, color_val + 40), (int(s[0]), int(s[1])), 1)


# --- ĐỐI TƯỢNG NGƯỜI CHƠI ---
class Player(pygame.sprite.Sprite):
    """Đối tượng chính điều khiển bởi người chơi"""
    def __init__(self):
        super().__init__()
        self.image = pygame.Surface((70, 70), pygame.SRCALPHA)
        pygame.draw.circle(self.image, (20, 20, 30), (35, 35), 22)
        pygame.draw.circle(self.image, (0, 80, 200), (35, 35), 20)
        pygame.draw.circle(self.image, BLUE, (35, 35), 20, 3)
        pygame.draw.rect(self.image, (180, 180, 190), (45, 28, 20, 14), border_radius=4)
        pygame.draw.rect(self.image, BLACK, (55, 30, 8, 10))
        pygame.draw.circle(self.image, CYAN, (35, 35), 6)
        pygame.draw.circle(self.image, WHITE, (35, 35), 2)

        self.original_image = self.image
        self.rect = self.image.get_rect(center=(DEFAULT_WIDTH // 2, DEFAULT_HEIGHT // 2))
        self.radius = 20
        self.health = PLAYER_MAX_HEALTH
        self.last_hit = 0
        self.shake_timer = 0
        self.last_shot = 0
        self.weapon_type = 'PISTOL'
        self.weapon_timer = 0
        self.speed_boost_timer = 0
        self.shield_timer = 0

    def update(self):
        if is_paused: return
        current_speed = PLAYER_SPEED * 1.6 if self.speed_boost_timer > 0 else PLAYER_SPEED
        keys = pygame.key.get_pressed()
        if keys[pygame.K_a]: self.rect.x -= current_speed
        if keys[pygame.K_d]: self.rect.x += current_speed
        if keys[pygame.K_w]: self.rect.y -= current_speed
        if keys[pygame.K_s]: self.rect.y += current_speed
        self.rect.clamp_ip(screen.get_rect())

        if self.shake_timer > 0: self.shake_timer -= 1
        if self.weapon_timer > 0:
            self.weapon_timer -= 1
        else:
            self.weapon_type = 'PISTOL'
        if self.speed_boost_timer > 0: self.speed_boost_timer -= 1
        if self.shield_timer > 0: self.shield_timer -= 1

    def draw(self, surface):
        mx, my = pygame.mouse.get_pos()
        angle = math.degrees(math.atan2(my - self.rect.centery, mx - self.rect.centerx))
        rot_image = pygame.transform.rotate(self.original_image, -angle)
        new_rect = rot_image.get_rect(center=self.rect.center)

        if self.shake_timer > 0:
            new_rect.x += random.randint(-5, 5)
            new_rect.y += random.randint(-5, 5)

        if pygame.time.get_ticks() - self.last_hit < 200:
            surface.blit(rot_image, new_rect, special_flags=pygame.BLEND_RGB_ADD)
        else:
            pulse = (math.sin(pygame.time.get_ticks() * 0.01) + 1) * 2
            pygame.draw.circle(surface, (0, 50, 100), self.rect.center, 25 + pulse, 2)
            surface.blit(rot_image, new_rect)

        if self.shield_timer > 0:
            s_pulse = (math.sin(pygame.time.get_ticks() * 0.02) + 1) * 5
            pygame.draw.circle(surface, (0, 255, 255, 100), self.rect.center, 40 + s_pulse, 3)


class Zombie(pygame.sprite.Sprite):
    """Kẻ thù đuổi theo người chơi"""
    def __init__(self, difficulty, is_boss=False):
        super().__init__()
        self.is_boss = is_boss
        self.size = random.randint(40, 55) if not is_boss else 120
        self.health = 1 if not is_boss else 15
        self.image = pygame.Surface((self.size, self.size), pygame.SRCALPHA)

        color = random.choice([BLOOD_RED, (150, 30, 30), (80, 120, 30)]) if not is_boss else NEON_PURPLE
        pygame.draw.circle(self.image, (20, 10, 10), (self.size // 2, self.size // 2), self.size // 2)
        pygame.draw.circle(self.image, color, (self.size // 2, self.size // 2), self.size // 2 - 3)

        eye_color = random.choice([GREEN, YELLOW, (255, 255, 255)]) if not is_boss else RED
        pygame.draw.circle(self.image, eye_color, (self.size // 2 + self.size // 5, self.size // 3), self.size // 10)
        pygame.draw.circle(self.image, eye_color, (self.size // 2 + self.size // 5, self.size * 2 // 3),self.size // 10)

        self.rect = self.image.get_rect()
        self.radius = self.size // 2
        w, h = screen.get_size()
        side = random.randint(0, 3)
        if side == 0:
            self.rect.center = (random.randint(0, w), -60)
        elif side == 1:
            self.rect.center = (random.randint(0, w), h + 60)
        elif side == 2:
            self.rect.center = (-60, random.randint(0, h))
        else:
            self.rect.center = (w + 60, random.randint(0, h))

        base_speed = random.uniform(ZOMBIE_SPEED_MIN, ZOMBIE_SPEED_MAX) if not is_boss else 1.0
        self.speed = min(base_speed * difficulty, MAX_ZOMBIE_SPEED)

    def update(self, p_pos):
        if is_paused: return
        angle = math.atan2(p_pos[1] - self.rect.centery, p_pos[0] - self.rect.centerx)
        self.rect.x += math.cos(angle) * self.speed
        self.rect.y += math.sin(angle) * self.speed


class Bullet(pygame.sprite.Sprite):
    """Đạn bắn ra từ người chơi hoặc Drone"""
    def __init__(self, start_pos, target_pos, angle_offset=0):
        super().__init__()
        self.image = pygame.Surface((20, 20), pygame.SRCALPHA)
        pygame.draw.circle(self.image, (0, 255, 255, 80), (10, 10), 10)
        pygame.draw.circle(self.image, CYAN, (10, 10), 5)
        pygame.draw.circle(self.image, WHITE, (10, 10), 2)
        self.rect = self.image.get_rect(center=start_pos)
        angle = math.atan2(target_pos[1] - start_pos[1], target_pos[0] - start_pos[0]) + math.radians(angle_offset)
        self.vx = math.cos(angle) * BULLET_SPEED
        self.vy = math.sin(angle) * BULLET_SPEED

    def update(self):
        if is_paused: return
        self.rect.x += self.vx
        self.rect.y += self.vy
        if not screen.get_rect().inflate(100, 100).colliderect(self.rect): self.kill()


# --- CÁC HÀM TIỆN ÍCH ---
def draw_pause_menu():
    """Vẽ menu tạm dừng"""
    overlay = pygame.Surface((DEFAULT_WIDTH, DEFAULT_HEIGHT), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 180))
    screen.blit(overlay, (0, 0))

    txt = get_font(70).render("NGƯNG ĐỌNG", True, YELLOW)
    screen.blit(txt, (DEFAULT_WIDTH // 2 - txt.get_width() // 2, DEFAULT_HEIGHT // 2 - 100))

    hint = get_font(25).render("ESC: Quay lại cuộc chiến | M: Thoát ra Sảnh", True, WHITE)
    screen.blit(hint, (DEFAULT_WIDTH // 2 - hint.get_width() // 2, DEFAULT_HEIGHT // 2 + 20))


def draw_help_overlay():
    """Vẽ bảng hướng dẫn"""
    panel_w, panel_h = 420, 420
    panel = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
    pygame.draw.rect(panel, (10, 10, 20, 250), (0, 0, panel_w, panel_h), border_radius=20)
    pygame.draw.rect(panel, CYAN, (0, 0, panel_w, panel_h), 2, border_radius=20)
    title = get_font(32).render("SỔ TAY CHIẾN THUẬT", True, YELLOW)
    panel.blit(title, (panel_w // 2 - title.get_width() // 2, 30))
    pygame.draw.line(panel, (50, 50, 80), (50, 80), (panel_w - 50, 80), 2)
    lines = [
        ("W-A-S-D", "Di chuyển linh hoạt"), ("CHUỘT TRÁI", "Khai hỏa hủy diệt"), ("ESC / P", "Tạm dừng suy ngẫm"),
        ("PHÍM M", "Trở về Sảnh chính"), ("PHÍM F1", "Âm thanh chiến trường"), ("PHÍM F", "Kích hoạt Drone"),
        ("PHÍM H", "Đóng/Mở sổ tay"),
    ]
    start_y = 105
    for key, desc in lines:
        k_surf = get_font(18).render(f"{key}", True, CYAN)
        panel.blit(k_surf, (50, start_y))
        d_surf = get_font(18).render(f": {desc}", True, WHITE)
        panel.blit(d_surf, (170, start_y))
        start_y += 36
    footer = get_font(14).render("Nhấn [H] để tiếp tục chiến đấu", True, (150, 150, 150))
    panel.blit(footer, (panel_w // 2 - footer.get_width() // 2, panel_h - 35))
    screen.blit(panel, (DEFAULT_WIDTH // 2 - panel_w // 2, DEFAULT_HEIGHT // 2 - panel_h // 2))


# --- MÀN HÌNH ĐĂNG NHẬP ---
def login_screen():
    global sound_enabled
    input_text = ""
    bg_fx = BackgroundEffect(DEFAULT_WIDTH, DEFAULT_HEIGHT)
    pygame.key.start_text_input()

    while True:
        screen.fill(BLACK)
        bg_fx.draw(screen)
        title_font = get_font(85)
        pulse = (math.sin(pygame.time.get_ticks() * 0.005) + 1) * 20
        title_color = (200 + pulse, 0, 0)
        title_shadow = title_font.render("KỶ NGUYÊN ZOMBIE", True, (40, 0, 0))
        title_main = title_font.render("KỶ NGUYÊN ZOMBIE", True, title_color)
        screen.blit(title_shadow, (DEFAULT_WIDTH // 2 - title_shadow.get_width() // 2 + 5, 135))
        screen.blit(title_main, (DEFAULT_WIDTH // 2 - title_main.get_width() // 2, 130))

        subtitle = get_font(24).render("DANH TÍNH NGƯỜI SỐNG SÓT", True, WHITE)
        screen.blit(subtitle, (DEFAULT_WIDTH // 2 - subtitle.get_width() // 2, DEFAULT_HEIGHT // 2 - 80))

        box_rect = pygame.Rect(DEFAULT_WIDTH // 2 - 250, DEFAULT_HEIGHT // 2 - 20, 500, 70)
        pygame.draw.rect(screen, (15, 15, 25), box_rect, border_radius=15)
        pygame.draw.rect(screen, BLUE, box_rect, 3, border_radius=15)

        cursor = "_" if (pygame.time.get_ticks() // 500) % 2 == 0 else ""
        txt_surf = get_font(35).render(input_text + cursor, True, CYAN)
        screen.blit(txt_surf, (box_rect.x + 25, box_rect.y + 12))

        info_txt = get_font(20).render("ENTER: ĐỂ BẮT ĐẦU GAME", True, (150, 150, 170))
        screen.blit(info_txt, (DEFAULT_WIDTH // 2 - info_txt.get_width() // 2, DEFAULT_HEIGHT // 2 + 70))

        # --- CẬP NHẬT: MỞ RỘNG BẢNG XẾP HẠNG ---
        lb_width = 650  # Tăng chiều rộng lên từ 500
        lb_x = DEFAULT_WIDTH // 2 - lb_width // 2
        lb_y = DEFAULT_HEIGHT - 240
        pygame.draw.rect(screen, (20, 20, 30), (lb_x, lb_y, lb_width, 200), border_radius=20)
        pygame.draw.rect(screen, (40, 40, 60), (lb_x, lb_y, lb_width, 200), 2, border_radius=20)

        lb_title = get_font(26).render("ĐỀN THỜ HUYỀN THOẠI", True, YELLOW)
        screen.blit(lb_title, (DEFAULT_WIDTH // 2 - lb_title.get_width() // 2, lb_y + 15))

        scores = user_manager.get_leaderboard()
        for i, s in enumerate(scores):
            # Định dạng lại chuỗi hiển thị để rộng rãi hơn
            rank_str = f"#{i + 1}"
            name_str = f"{s[0]}"
            score_str = f"{int(s[1]):,} ĐIỂM"
            date_str = f"({s[2]})"

            # Vẽ từng cột để đảm bảo căn lề đẹp
            rank_surf = get_font(20).render(rank_str, True, YELLOW)
            name_surf = get_font(20).render(name_str, True, WHITE)
            score_surf = get_font(20).render(score_str, True, CYAN)

            screen.blit(rank_surf, (lb_x + 40, lb_y + 60 + i * 28))
            screen.blit(name_surf, (lb_x + 100, lb_y + 60 + i * 28))
            screen.blit(score_surf, (lb_x + lb_width - 200, lb_y + 60 + i * 28))

        for event in pygame.event.get():
            if event.type == pygame.QUIT: pygame.quit(); exit()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_RETURN and input_text.strip():
                    user_manager.current_user = input_text.strip()
                    pygame.key.stop_text_input()
                    return
                elif event.key == pygame.K_BACKSPACE:
                    input_text = input_text[:-1]
                elif event.key == pygame.K_F1:
                    toggle_sounds()
            if event.type == pygame.TEXTINPUT:
                if len(input_text) < 14: input_text += event.text

        pygame.display.flip()
        clock.tick(FPS)


# --- VÒNG LẶP CHÍNH ---
def game_loop():
    global is_paused, sound_enabled, show_help
    login_screen()

    while True:
        player = Player()
        drone = CombatDrone()
        drone_enabled = True

        zombies = pygame.sprite.Group()
        bullets = pygame.sprite.Group()
        powerups = pygame.sprite.Group()
        particles = []
        blood_stains = []
        bg_fx = BackgroundEffect(DEFAULT_WIDTH, DEFAULT_HEIGHT)
        score = 0
        difficulty = 1.0
        running = True
        is_paused = False
        show_help = False
        spawn_timer = 0
        last_diff_time = pygame.time.get_ticks()

        while running:
            screen.fill(BLACK)
            bg_fx.draw(screen)
            for stain in blood_stains: stain.draw(screen)
            now = pygame.time.get_ticks()

            for event in pygame.event.get():
                if event.type == pygame.QUIT: pygame.quit(); exit()
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE or event.key == pygame.K_p:
                        is_paused = not is_paused
                        show_help = False
                    if event.key == pygame.K_m:
                        return game_loop()
                    if event.key == pygame.K_F1:
                        toggle_sounds()
                    if event.key == pygame.K_h:
                        show_help = not show_help
                    if event.key == pygame.K_f:
                        drone_enabled = not drone_enabled

            if not is_paused:
                mouse_pressed = pygame.mouse.get_pressed()
                if mouse_pressed[0]:
                    cooldown = BULLET_COOLDOWN if player.weapon_type == 'PISTOL' else BULLET_COOLDOWN * 2.5
                    if now - player.last_shot > cooldown:
                        if player.weapon_type == 'SHOTGUN':
                            for angle in [-15, -7, 0, 7, 15]:
                                bullets.add(Bullet(player.rect.center, pygame.mouse.get_pos(), angle))
                        else:
                            bullets.add(Bullet(player.rect.center, pygame.mouse.get_pos()))

                        if sound_enabled: SND_SHOOT.play()

                        player.last_shot = now
                        player.shake_timer = 4
                        for _ in range(3):
                            particles.append(Particle(player.rect.centerx, player.rect.centery, YELLOW))

                player.update()
                if drone_enabled: drone.update(player.rect, zombies, bullets)
                bullets.update()
                zombies.update(player.rect.center)
                powerups.update()

                for p in particles[:]:
                    p.update()
                    if p.lifetime <= 0: particles.remove(p)

                if now - last_diff_time > DIFFICULTY_INCREASE_INTEROVAL:
                    difficulty += 0.12
                    last_diff_time = now

                spawn_timer += 1
                if spawn_timer > max(15, SPAWN_RATE_START - int(difficulty * 12)):
                    is_boss = (score > 0 and score % 5000 == 0 and not any(z.is_boss for z in zombies))
                    zombies.add(Zombie(difficulty, is_boss))
                    spawn_timer = 0

                zombie_hits = pygame.sprite.spritecollide(player, zombies, True, pygame.sprite.collide_circle)
                if zombie_hits:
                   if player.shield_timer <= 0:
                      player.health -= ZOMBIE_DAMAGE
                      player.last_hit = now
                      player.shake_timer = 15

                      if sound_enabled: 
                          SND_HIT.play()

                      for _ in range(20):
                        particles.append(
                              Particle(player.rect.centerx, player.rect.centery, RED)
                        )
                   else:
                      # CÓ KHIÊN → KHÔNG MẤT MÁU
                        player.shield_timer -= 60

                   if player.health <= 0:
                      if sound_enabled:
                          pygame.mixer.stop()
                          SND_GAMEOVER.play()
                      user_manager.save_high_score(score)
                      running = False


                pu_hits = pygame.sprite.spritecollide(player, powerups, True)
                for pu in pu_hits:
                    if sound_enabled: SND_POWERUP.play()
                    if pu.type == 'HEAL':
                        player.health = min(PLAYER_MAX_HEALTH, player.health + 30)
                    elif pu.type == 'SHOTGUN':
                        player.weapon_type = 'SHOTGUN'
                        player.weapon_timer = 500
                    elif pu.type == 'SPEED':
                        player.speed_boost_timer = 400
                    elif pu.type == 'SHIELD':
                        player.shield_timer = 600
                    elif pu.type == 'NUKE':
                        for z in zombies:
                            score += 50
                            blood_stains.append(BloodStain(z.rect.centerx, z.rect.centery))
                        zombies.empty()

                hits = pygame.sprite.groupcollide(zombies, bullets, False, True)
                for zombie in hits:
                    zombie.health -= 1
                    if zombie.health <= 0:
                        zombie.kill()
                        if sound_enabled: SND_ZOMBIE_DIE.play()

                        score += 100 if not zombie.is_boss else 1000
                        blood_stains.append(BloodStain(zombie.rect.centerx, zombie.rect.centery))
                        if random.random() < 0.12:
                            powerups.add(PowerUp(zombie.rect.centerx, zombie.rect.centery))
                        for _ in range(12):
                            particles.append(Particle(zombie.rect.centerx, zombie.rect.centery,random.choice([BLOOD_RED, GREEN, (200, 200, 0)])))

            for p in particles: p.draw(screen)
            powerups.draw(screen)
            zombies.draw(screen)
            bullets.draw(screen)
            if drone_enabled: drone.draw(screen)
            player.draw(screen)

            # --- GIAO DIỆN CHIẾN TRƯỜNG (HUD) ---
            hb_bg = pygame.Rect(30, 30, 250, 35)
            pygame.draw.rect(screen, (20, 20, 30), hb_bg, border_radius=12)
            pygame.draw.rect(screen, (50, 50, 70), hb_bg, 2, border_radius=12)
            hp_ratio = max(0, player.health) / PLAYER_MAX_HEALTH
            hp_w = int(240 * hp_ratio)
            if hp_w > 0:
                hp_color = GREEN if hp_ratio > 0.4 else RED
                pygame.draw.rect(screen, hp_color, (35, 35, hp_w, 25), border_radius=8)

            score_txt = get_font(30).render(f"Điểm: {score:,}", True, WHITE)
            screen.blit(score_txt, (30, 75))
            user_txt = get_font(18).render(f"Người chơi: {user_manager.current_user}", True, CYAN)
            screen.blit(user_txt, (35, 115))

            curr_y = 145
            if player.weapon_type == 'SHOTGUN':
                wp_txt = get_font(18).render(f"BỘ PHÁ KÍCH: {player.weapon_timer // 60}s", True, ORANGE)
                screen.blit(wp_txt, (30, curr_y))
                curr_y += 25
            if player.shield_timer > 0:
                sh_txt = get_font(18).render(f"GIÁP NĂNG LƯỢNG: ĐANG BẬT", True, CYAN)
                screen.blit(sh_txt, (30, curr_y))
                curr_y += 25

            sound_icon = "F1: Bật Âm" if sound_enabled else "F1: Tắt Âm"
            drone_icon = "F: Vệ Binh" if drone_enabled else "F: Nghỉ"
            status_txt = get_font(16).render(f"{drone_icon} | {sound_icon} | H: Trợ giúp", True, (100, 100, 120))
            screen.blit(status_txt, (35, curr_y + 10))

            diff_label = get_font(20).render(f"ĐỘ NGUY HIỂM: {difficulty:.1f}x", True, YELLOW)
            screen.blit(diff_label, (DEFAULT_WIDTH - 230, 35))

            if is_paused:
                draw_pause_menu()
            elif show_help:
                draw_help_overlay()

            pygame.display.flip()
            clock.tick(FPS)
            if not is_paused and len(blood_stains) > 50: blood_stains.pop(0)

        # --- MÀN HÌNH TỬ TRẬN (Game Over) ---
        go = True
        while go:
            overlay = pygame.Surface((DEFAULT_WIDTH, DEFAULT_HEIGHT), pygame.SRCALPHA)
            overlay.fill((10, 0, 0, 230))
            screen.blit(overlay, (0, 0))

            msg = get_font(90).render("GỤC NGÃ", True, RED)
            stat = get_font(40).render(f"Chiến tích cuối cùng: {score:,}", True, WHITE)
            retry = get_font(24).render("R: Hồi sinh & Phục thù | M: Rút lui về Sảnh", True, CYAN)

            off_x = random.randint(-2, 2)
            screen.blit(msg, (DEFAULT_WIDTH // 2 - msg.get_width() // 2 + off_x, DEFAULT_HEIGHT // 3))
            screen.blit(stat, (DEFAULT_WIDTH // 2 - stat.get_width() // 2, DEFAULT_HEIGHT // 2))
            screen.blit(retry, (DEFAULT_WIDTH // 2 - retry.get_width() // 2, DEFAULT_HEIGHT // 2 + 120))

            for event in pygame.event.get():
                if event.type == pygame.QUIT: pygame.quit(); exit()
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_r: go = False
                    if event.key == pygame.K_m: return game_loop()
                    if event.key == pygame.K_F1: toggle_sounds()
            pygame.display.flip()
            clock.tick(FPS)


if __name__ == "__main__":
    game_loop()