import pygame

pygame.init()

# Screen settings
# Must both be exact multiples of GRID_CELL (below) - otherwise the grid's
# floor division leaves a few leftover pixels at the right/bottom edge that
# the capture grid can never cover, showing up as a gap between the frame
# and captured territory there
SCREEN_WIDTH = 1197
SCREEN_HEIGHT = 903
FRAME_WIDTH = 7  # must match GRID_CELL below, or a gap appears between the frame and captured territory
BOTTOM_FRAME_WIDTH = FRAME_WIDTH
FRAME_COLOR = (50, 200, 100)
LINE_COLOR = (255, 250, 205)
TEXT_COLOR = (255, 255, 255)

# Info panel to the right of the play field, full window height
PANEL_WIDTH = 260
PANEL_COLOR = (30, 35, 50)
PANEL_PADDING = 16
PANEL_LINE_GAP = 10

# Progress bar "how much is left to capture before the level ends"
PROGRESS_BAR_HEIGHT = 18
PROGRESS_BAR_BG_COLOR = (60, 65, 80)
PROGRESS_BAR_COLOR = (220, 50, 50)

WINDOW_WIDTH = SCREEN_WIDTH + PANEL_WIDTH

screen = pygame.display.set_mode((WINDOW_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption("sha game")

# Font(None, ...) loads pygame's built-in font - works the same natively
# and in the browser (system fonts may not be available there)
score_font = pygame.font.Font(None, 28)
game_over_font = pygame.font.Font(None, 64)
clock = pygame.time.Clock()

STARTING_LIVES = 3
LIFE_ICON_GAP = 6

# Points for capturing territory: for percent captured and for difficulty
# (bonus per ball in play)
POINTS_PER_PERCENT = 100
BALL_BONUS_PER_BALL = 0.5

PLAY_FIELD_AREA = (SCREEN_WIDTH - 2 * FRAME_WIDTH) * (SCREEN_HEIGHT - FRAME_WIDTH - BOTTOM_FRAME_WIDTH)

# Grid for finding areas enclosed by the line (including when the line runs
# from one rectangle/frame to another without forming a loop by itself).
# 7px matches WALL_THICKNESS below, so every captured rectangle is always
# a multiple of the wall tile thickness in both dimensions - never thinner
# than a single tile, so the border always renders cleanly
GRID_CELL = 7
GRID_COLS = SCREEN_WIDTH // GRID_CELL
GRID_ROWS = SCREEN_HEIGHT // GRID_CELL

# The game starts with one ball - each new level adds one more
BALL_COUNT = 1
BALL_IMAGE_SIZE = (16, 16)
BALL_IMAGE_PATH = "pics/redball.png"

# Image for each ball (by default all the same, but different balls can
# be given different paths)
BALL_IMAGE_PATHS = [BALL_IMAGE_PATH] * BALL_COUNT

# A ball walled off from all the other balls turns blue and rewards the
# player: bonus points, and the level timer (and with it the ball speed
# ramp) resets back to the start
BLUE_BALL_IMAGE_PATH = "pics/blueball.png"
ISOLATION_BONUS_SCORE = 1000

# Percent of captured territory at which the game moves to the next level
LEVEL_UP_PERCENT = 75

# Level timer: level N gets (LEVEL_TIME_BASE_MINUTES + N - 1) minutes to
# capture - level 1 gets 2 minutes, level 2 gets 3 minutes, etc. Run out
# of time - Game Over
LEVEL_TIME_BASE_MINUTES = 2

# Ball speed ramps up linearly over the course of a level: at the start of
# the level it's BALL_SPEED_MIN_FACTOR times the base speed (player_speed),
# by the time the level's timer runs out it's BALL_SPEED_MAX_FACTOR times
BALL_SPEED_MIN_FACTOR = 0.5
BALL_SPEED_MAX_FACTOR = 2.0

player_speed = 10

# Cursor "spins" - animation frames cycle one after another
CURSOR_ANIMATION_PATHS = ["pics/star.png", "pics/star2.png", "pics/star3.png"]
CURSOR_IMAGE_SIZE = (16, 16)
CURSOR_SPEED = 4
CURSOR_FRAME_DELAY = 8  # game frames between switching images (~130ms at 60 fps)

# If a second arrow key is pressed while one is already held, the cursor
# keeps moving along the first key's direction - this debounce is how many
# frames a newly-leading key must stay held before it actually takes over,
# so brief overlaps between two keys don't produce a diagonal trail step
CURSOR_INPUT_DEBOUNCE_FRAMES = 3

# Once within this many pixels of a wall (obstacle/frame), the cursor snaps
# flush onto it, making it easy to hug the border precisely. Moving away
# from a wall it's stuck to is held for CURSOR_WALL_LEAVE_DELAY_FRAMES
# frames before it's actually allowed, to avoid accidentally peeling off
CURSOR_WALL_SNAP_DISTANCE = 3
CURSOR_WALL_LEAVE_DELAY_FRAMES = 5

# Both the outer field frame and captured territory get a tiled wall border
# around their edges instead of a plain flat rectangle, each side using its
# own directional sprite, all WALL_THICKNESS px thick
BORDER_LEFT_IMAGE_PATH = "pics/verleft.png"
BORDER_TOP_IMAGE_PATH = "pics/horup.png"
BORDER_BOTTOM_IMAGE_PATH = "pics/hordown.png"
BORDER_RIGHT_IMAGE_PATH = "pics/vertrigth.png"
WALL_THICKNESS = 7

TRAIL_LINE_WIDTH = 3

# How far from a wall the cursor still counts as "touching" it at the
# moment it leaves or closes the trail (see is_touching_obstacles) - the
# ends of the trail get snapped to exactly this distance so there's no
# gap. Not used anywhere else, so rectangles drawn close together but not
# actually touching don't get pulled together.
SNAP_TOLERANCE = 20

# Leaderboard: server address and limits for the login screen
LEADERBOARD_BASE_URL = "http://localhost:8765"
USERNAME_MAX_LEN = 12
PIN_LENGTH = 4
LEADERBOARD_LIMIT = 6

# Per-environment overrides (e.g. LEADERBOARD_BASE_URL = "/api" for the
# production build) live in local_settings.py, which is gitignored - so a
# deployed server's local settings never conflict with `git pull`
try:
    from local_settings import *  # noqa: F401,F403
except ImportError:
    pass
