import pygame

pygame.init()

# Настройки экрана
SCREEN_WIDTH = 1200
SCREEN_HEIGHT = 900
FRAME_WIDTH = 5
BOTTOM_FRAME_WIDTH = FRAME_WIDTH
FRAME_COLOR = (50, 200, 100)
LINE_COLOR = (255, 250, 205)
TEXT_COLOR = (255, 255, 255)

# Информационная панель справа от игрового поля, на всю высоту окна
PANEL_WIDTH = 260
PANEL_COLOR = (30, 35, 50)
PANEL_PADDING = 16
PANEL_LINE_GAP = 10

# Прогрессбар "сколько осталось захватить до конца уровня"
PROGRESS_BAR_HEIGHT = 18
PROGRESS_BAR_BG_COLOR = (60, 65, 80)
PROGRESS_BAR_COLOR = (220, 50, 50)

WINDOW_WIDTH = SCREEN_WIDTH + PANEL_WIDTH

screen = pygame.display.set_mode((WINDOW_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption("sha game")

# Font(None, ...) грузит встроенный в pygame шрифт - работает одинаково
# и нативно, и в браузере (там системных шрифтов может не быть)
score_font = pygame.font.Font(None, 28)
game_over_font = pygame.font.Font(None, 64)
clock = pygame.time.Clock()

STARTING_LIVES = 3
LIFE_ICON_GAP = 6

# Очки за захват территории: за процент, за скорость (штраф за секунды)
# и за сложность (бонус за количество шариков в игре)
POINTS_PER_PERCENT = 100
TIME_PENALTY_PER_SECOND = 2
BALL_BONUS_PER_BALL = 0.5

PLAY_FIELD_AREA = (SCREEN_WIDTH - 2 * FRAME_WIDTH) * (SCREEN_HEIGHT - FRAME_WIDTH - BOTTOM_FRAME_WIDTH)

# Сетка для поиска замкнутых линией областей (в т.ч. когда линия идёт
# от одного прямоугольника/рамки до другого, не образуя петлю сама по себе)
GRID_CELL = 5
GRID_COLS = SCREEN_WIDTH // GRID_CELL
GRID_ROWS = SCREEN_HEIGHT // GRID_CELL

# Игра начинается с одного шарика - на каждом новом уровне добавляется ещё один
BALL_COUNT = 1
BALL_IMAGE_SIZE = (16, 16)
BALL_IMAGE_PATH = "pics/redball.png"

# Картинка для каждого шарика (по умолчанию у всех одна и та же,
# но можно указать разные пути для разных шариков)
BALL_IMAGE_PATHS = [BALL_IMAGE_PATH] * BALL_COUNT

# Процент захваченной территории, при котором игра переходит на новый уровень
LEVEL_UP_PERCENT = 75

player_speed = 10

CURSOR_IMAGE_PATH = "pics/star.png"
CURSOR_IMAGE_SIZE = (16, 16)
CURSOR_SPEED = 4

TRAIL_LINE_WIDTH = 3

# Насколько далеко от стены курсор ещё считается "касающимся" в момент отрыва
# или замыкания следа (см. is_touching_obstacles) - ровно на эту величину
# нужно "довести" концы следа, чтобы не было зазора. Не используется больше
# нигде, поэтому близко нарисованные, но не соприкасающиеся прямоугольники
# друг к другу не притягиваются.
SNAP_TOLERANCE = 20

# Таблица рекордов: адрес сервера и ограничения на экране логина
LEADERBOARD_BASE_URL = "http://localhost:8765"
USERNAME_MAX_LEN = 12
PIN_LENGTH = 4
LEADERBOARD_LIMIT = 6
