import sys
import asyncio # for web compatibility (pygbag)

import pygame

from config import (
    screen, score_font, game_over_font, clock,
    SCREEN_WIDTH, SCREEN_HEIGHT,
    LINE_COLOR, TEXT_COLOR, TRAIL_LINE_WIDTH, SNAP_TOLERANCE,
    BALL_IMAGE_PATHS, BALL_IMAGE_PATH, player_speed,
    CURSOR_ANIMATION_PATHS, CURSOR_IMAGE_SIZE, CURSOR_SPEED, CURSOR_FRAME_DELAY,
    CURSOR_INPUT_DEBOUNCE_FRAMES, CURSOR_WALL_SNAP_DISTANCE, CURSOR_WALL_LEAVE_DELAY_FRAMES,
    STARTING_LIVES, LIFE_ICON_GAP, LEVEL_UP_PERCENT,
    LEVEL_TIME_BASE_MINUTES, BALL_SPEED_MIN_FACTOR, BALL_SPEED_MAX_FACTOR,
    PANEL_WIDTH, PANEL_COLOR, PANEL_PADDING, PANEL_LINE_GAP,
    PROGRESS_BAR_HEIGHT, PROGRESS_BAR_BG_COLOR, PROGRESS_BAR_COLOR,
    LEADERBOARD_BASE_URL, USERNAME_MAX_LEN, PIN_LENGTH, LEADERBOARD_LIMIT,
    BLUE_BALL_IMAGE_PATH, ISOLATION_BONUS_SCORE,
    WALL_THICKNESS,
    BORDER_LEFT_IMAGE_PATH, BORDER_TOP_IMAGE_PATH, BORDER_BOTTOM_IMAGE_PATH, BORDER_RIGHT_IMAGE_PATH,
    BACKGROUND_PHOTOS_DIR,
)
from images import load_image, load_ball_image, load_image_native, load_random_background
from obstacles import OBSTACLES, make_initial_obstacles
from ball import Ball
from cursor import Cursor
from physics import resolve_ball_collision, resolve_ball_obstacle_collision
from trail import is_touching_obstacles, get_leave_point, ball_touches_trail
from capture import capture_enclosed_areas, get_captured_percent, find_ball_groups, build_blocked_grid
from scoring import calculate_score
import net

balls = [
    Ball(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2, player_speed, load_ball_image(path))
    for path in BALL_IMAGE_PATHS
]

default_ball_image = load_ball_image(BALL_IMAGE_PATH)
blue_ball_image = load_ball_image(BLUE_BALL_IMAGE_PATH)

# Shared by both the outer field frame and captured territory - each side of
# a border gets its own directional sprite
BORDER_IMAGES = {
    "left": load_image_native(BORDER_LEFT_IMAGE_PATH),
    "top": load_image_native(BORDER_TOP_IMAGE_PATH),
    "bottom": load_image_native(BORDER_BOTTOM_IMAGE_PATH),
    "right": load_image_native(BORDER_RIGHT_IMAGE_PATH),
}
EDGE_IS_HORIZONTAL = {"left": False, "top": True, "bottom": True, "right": False}

# Thickness x thickness crops used to patch inner (concave) corners of
# captured territory, where neither adjacent edge's run reaches on its own.
# Picked by which side (top/bottom) of the corner is involved.
CORNER_TILES = {
    "top": BORDER_IMAGES["top"].subsurface(pygame.Rect(0, 0, WALL_THICKNESS, WALL_THICKNESS)),
    "bottom": BORDER_IMAGES["bottom"].subsurface(pygame.Rect(0, 0, WALL_THICKNESS, WALL_THICKNESS)),
}

# A random photo from BACKGROUND_PHOTOS_DIR fills captured territory instead
# of a flat color, re-picked at the start of every level - None (folder
# empty/missing) falls back to the obstacle's flat fill_color
captured_background_image = load_random_background(BACKGROUND_PHOTOS_DIR, (SCREEN_WIDTH, SCREEN_HEIGHT))

cursor = Cursor(
    0,
    SCREEN_HEIGHT // 2,
    [load_image(path, CURSOR_IMAGE_SIZE) for path in CURSOR_ANIMATION_PATHS],
    CURSOR_SPEED,
    CURSOR_FRAME_DELAY,
    CURSOR_INPUT_DEBOUNCE_FRAMES,
)

lives = STARTING_LIVES
game_over = False
elapsed_frames = 0
banked_score = 0
level = 1
level_transition = False
level_up_gain = 0
paused = False

# Login screen - there's no networking on a native run (see net.py), so we
# log in right away as a guest and skip the screen entirely
logged_in = not net.IS_BROWSER
username = "" if net.IS_BROWSER else "Guest"
pin = ""
active_field = "username"
login_status = ""
login_busy = False

score_submitted = False
leaderboard_entries = []
isolated_ball_count = 0

NAME_BOX_SIZE = (300, 44)
PIN_BOX_SIZE = 54
PIN_BOX_GAP = 12


def login_layout():
    # All geometry for the login screen in one place, computed from the
    # actual font heights - so rows are spaced far enough apart to never
    # overlap regardless of font metrics. Shared by both event handling
    # (click hit-testing) and rendering, so they can never drift apart.
    center_x = SCREEN_WIDTH // 2
    y = SCREEN_HEIGHT // 2 - 190
    label_height = score_font.get_height()

    def advance(height, gap):
        nonlocal y
        top = y
        y += height + gap
        return top

    title_top = advance(game_over_font.get_height(), 40)

    name_label_top = advance(label_height, 4)
    name_box = pygame.Rect(0, 0, *NAME_BOX_SIZE)
    name_box.top = advance(NAME_BOX_SIZE[1], 30)
    name_box.centerx = center_x

    pin_label_top = advance(label_height, 4)
    pin_row_width = 4 * PIN_BOX_SIZE + 3 * PIN_BOX_GAP
    pin_row_left = center_x - pin_row_width // 2
    pin_row_top = advance(PIN_BOX_SIZE, 30)
    pin_boxes = [
        pygame.Rect(pin_row_left + i * (PIN_BOX_SIZE + PIN_BOX_GAP), pin_row_top, PIN_BOX_SIZE, PIN_BOX_SIZE)
        for i in range(PIN_LENGTH)
    ]

    status_top = advance(label_height, 10)
    hint_top = advance(label_height, 0)

    return {
        "center_x": center_x,
        "title_top": title_top,
        "name_label_top": name_label_top,
        "name_box": name_box,
        "pin_label_top": pin_label_top,
        "pin_boxes": pin_boxes,
        "status_top": status_top,
        "hint_top": hint_top,
    }


def blit_line_parts(surface, x, y, parts, font, color):
    # Draws a line made of a mix of text strings and icon surfaces, one
    # after another, and returns the line's height so the caller can move
    # on to the next line
    cursor_x = x
    line_height = font.get_height()
    for part in parts:
        if isinstance(part, str):
            if part:
                text_surface = font.render(part, True, color)
                surface.blit(text_surface, (cursor_x, y))
                cursor_x += text_surface.get_width()
                line_height = max(line_height, text_surface.get_height())
        else:
            icon_y = y + (font.get_height() - part.get_height()) // 2
            surface.blit(part, (cursor_x, icon_y))
            cursor_x += part.get_width() + 4
            line_height = max(line_height, part.get_height())
    return line_height


def find_open_runs(count, is_open_fn):
    # Groups consecutive open cell offsets (0..count-1) into runs of
    # (start_offset, length)
    runs = []
    run_start = None
    for i in range(count):
        if is_open_fn(i):
            if run_start is None:
                run_start = i
        elif run_start is not None:
            runs.append((run_start, i - run_start))
            run_start = None
    if run_start is not None:
        runs.append((run_start, count - run_start))
    return runs


def blit_tiled_run(surface, run_rect, tile_image, horizontal):
    # Tiles tile_image edge-to-edge along run_rect's length (horizontal:
    # left-to-right, vertical: top-to-bottom). The clip rect cuts off the
    # last tile cleanly if run_rect's length isn't an exact multiple of the
    # tile size, so no gap or overflow either way. Caller is responsible for
    # saving/restoring the surface's previous clip.
    surface.set_clip(run_rect)
    tile_size = tile_image.get_width() if horizontal else tile_image.get_height()
    pos = run_rect.left if horizontal else run_rect.top
    end = pos + (run_rect.width if horizontal else run_rect.height)
    while pos < end:
        dest = (pos, run_rect.top) if horizontal else (run_rect.left, pos)
        surface.blit(tile_image, dest)
        pos += tile_size


def draw_frame_edge(surface, rect, fill_color, tile_image, horizontal):
    pygame.draw.rect(surface, fill_color, rect)
    previous_clip = surface.get_clip()
    blit_tiled_run(surface, rect, tile_image, horizontal)
    surface.set_clip(previous_clip)


def draw_captured_obstacle(surface, rect, fill_color, background_image, border_images, corner_tiles, thickness, blocked_grid):
    # Interior fill, then a tiled wall border - but only along the stretches
    # of each edge that face open space. An edge touching another obstacle
    # (another captured piece, or the frame) is left flat, so adjacent
    # captured territory reads as one seamless shape with a border only on
    # its true outer boundary. Each side uses its own directional sprite
    # (border_images: 'left'/'top'/'bottom'/'right').
    # The interior itself is a slice of the shared background photo when one
    # is set (background_image is sized to the whole field, so blitting the
    # same rect from it lines up seamlessly across separate captured
    # pieces), otherwise a flat fill_color.
    if background_image is not None:
        surface.blit(background_image, rect.topleft, area=rect)
    else:
        pygame.draw.rect(surface, fill_color, rect)

    grid_rows = len(blocked_grid)
    grid_cols = len(blocked_grid[0])

    def is_open(col, row):
        if 0 <= row < grid_rows and 0 <= col < grid_cols:
            return not blocked_grid[row][col]
        return True

    col_start = rect.left // thickness
    row_start = rect.top // thickness
    width_cells = rect.width // thickness
    height_cells = rect.height // thickness

    previous_clip = surface.get_clip()

    for start, length in find_open_runs(width_cells, lambda c: is_open(col_start + c, row_start - 1)):
        blit_tiled_run(surface, pygame.Rect(rect.left + start * thickness, rect.top, length * thickness, thickness), border_images["top"], True)
    for start, length in find_open_runs(width_cells, lambda c: is_open(col_start + c, row_start + height_cells)):
        blit_tiled_run(surface, pygame.Rect(rect.left + start * thickness, rect.bottom - thickness, length * thickness, thickness), border_images["bottom"], True)
    for start, length in find_open_runs(height_cells, lambda r: is_open(col_start - 1, row_start + r)):
        blit_tiled_run(surface, pygame.Rect(rect.left, rect.top + start * thickness, thickness, length * thickness), border_images["left"], False)
    for start, length in find_open_runs(height_cells, lambda r: is_open(col_start + width_cells, row_start + r)):
        blit_tiled_run(surface, pygame.Rect(rect.right - thickness, rect.top + start * thickness, thickness, length * thickness), border_images["right"], False)

    surface.set_clip(previous_clip)

    # Inner (concave) corners: a cell whose two straight edges are each
    # covered by a *different* neighboring obstacle, but which is still
    # diagonally next to open space, gets missed by the edge runs above
    # (neither run's straight check ever reaches it). Patch those cells
    # individually so the border wraps all the way around without a notch,
    # picking the top or bottom corner tile depending on which side of the
    # corner is involved.
    boundary_cells = set()
    for c in range(width_cells):
        boundary_cells.add((col_start + c, row_start))
        boundary_cells.add((col_start + c, row_start + height_cells - 1))
    for r in range(height_cells):
        boundary_cells.add((col_start, row_start + r))
        boundary_cells.add((col_start + width_cells - 1, row_start + r))

    for col, row in boundary_cells:
        for dc, dr in ((1, 1), (1, -1), (-1, 1), (-1, -1)):
            if is_open(col + dc, row + dr) and not is_open(col + dc, row) and not is_open(col, row + dr):
                corner_tile = corner_tiles["top"] if dr == -1 else corner_tiles["bottom"]
                surface.blit(corner_tile, (col * thickness, row * thickness))


_blocked_grid_cache = None
_blocked_grid_cache_count = -1


def get_blocked_grid_cached(obstacles):
    # OBSTACLES only ever grows (via .extend()), so its length is a cheap
    # and reliable signal for "did anything change since last frame"
    global _blocked_grid_cache, _blocked_grid_cache_count
    if len(obstacles) != _blocked_grid_cache_count:
        _blocked_grid_cache = build_blocked_grid(obstacles)
        _blocked_grid_cache_count = len(obstacles)
    return _blocked_grid_cache


# Main async loop (works both on desktop and on the web via pygbag)
async def main():
    global lives, game_over, elapsed_frames, banked_score, level, level_transition, level_up_gain, paused, captured_background_image
    global logged_in, username, pin, active_field, login_status, login_busy
    global score_submitted, leaderboard_entries, isolated_ball_count
    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN and not logged_in:
                if login_busy:
                    pass
                elif event.key == pygame.K_TAB:
                    active_field = "pin" if active_field == "username" else "username"
                elif event.key == pygame.K_BACKSPACE:
                    if active_field == "username":
                        username = username[:-1]
                    else:
                        pin = pin[:-1]
                elif event.key == pygame.K_RETURN:
                    if username and len(pin) == PIN_LENGTH:
                        login_busy = True
                        login_status = "Connecting..."
                        try:
                            result = await net.login(LEADERBOARD_BASE_URL, username, pin)
                        except Exception:
                            result = {"ok": False, "error": "connection_failed"}
                        login_busy = False
                        if result.get("ok"):
                            logged_in = True
                            login_status = ""
                            try:
                                lb_result = await net.fetch_leaderboard(LEADERBOARD_BASE_URL, LEADERBOARD_LIMIT)
                                if lb_result.get("ok"):
                                    leaderboard_entries = lb_result.get("entries", [])
                            except Exception:
                                pass
                        elif result.get("error") == "wrong_pin":
                            login_status = "Wrong PIN, try again"
                            pin = ""
                        else:
                            login_status = "Connection failed, try again"
                    else:
                        login_status = f"Enter a name and a {PIN_LENGTH}-digit PIN"
                elif event.unicode:
                    if active_field == "username":
                        if len(username) < USERNAME_MAX_LEN and event.unicode.isprintable():
                            username += event.unicode
                    else:
                        if len(pin) < PIN_LENGTH and event.unicode.isdigit():
                            pin += event.unicode
            elif event.type == pygame.MOUSEBUTTONDOWN and not logged_in and event.button == 1:
                layout = login_layout()
                if layout["name_box"].collidepoint(event.pos):
                    active_field = "username"
                elif any(box.collidepoint(event.pos) for box in layout["pin_boxes"]):
                    active_field = "pin"
            elif event.type == pygame.KEYUP and logged_in:
                cursor.on_key_up(event.key)
            elif event.type == pygame.KEYDOWN and logged_in:
                cursor.on_key_down(event.key)
                if level_transition and event.key == pygame.K_SPACE:
                    # Space starts the next level: a new ball, a clean field,
                    # cursor back at the start point, lives and level timer reset.
                    # Any ball turned blue from being isolated goes back to red.
                    for ball in balls:
                        ball.image = default_ball_image
                    balls.append(
                        Ball(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2, player_speed, default_ball_image)
                    )
                    OBSTACLES[:] = make_initial_obstacles()
                    captured_background_image = load_random_background(BACKGROUND_PHOTOS_DIR, (SCREEN_WIDTH, SCREEN_HEIGHT))
                    cursor.x, cursor.y = 0, SCREEN_HEIGHT // 2
                    cursor.drawing = False
                    cursor.trail = []
                    lives = STARTING_LIVES
                    elapsed_frames = 0
                    level += 1
                    level_transition = False
                elif game_over and event.key == pygame.K_SPACE:
                    # Restart with the same player, no need to log in again:
                    # field, balls, lives, level and score all start over
                    balls[:] = [
                        Ball(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2, player_speed, default_ball_image)
                        for _ in BALL_IMAGE_PATHS
                    ]
                    OBSTACLES[:] = make_initial_obstacles()
                    captured_background_image = load_random_background(BACKGROUND_PHOTOS_DIR, (SCREEN_WIDTH, SCREEN_HEIGHT))
                    cursor.x, cursor.y = 0, SCREEN_HEIGHT // 2
                    cursor.drawing = False
                    cursor.trail = []
                    lives = STARTING_LIVES
                    elapsed_frames = 0
                    banked_score = 0
                    level = 1
                    game_over = False
                    score_submitted = False
                    isolated_ball_count = 0
                elif event.key == pygame.K_SPACE and not game_over:
                    paused = not paused

        # Level timer in frames - needed both for the time-up check and for
        # the panel display, so it's computed unconditionally every frame
        level_time_limit = (LEVEL_TIME_BASE_MINUTES + level - 1) * 60 * 60

        if logged_in and not game_over and not level_transition and not paused:
            elapsed_frames += 1

            if elapsed_frames >= level_time_limit:
                # Level time is up - the game ends immediately
                game_over = True

            if not game_over:
                # Cursor control via arrow keys (see on_key_down/on_key_up above)
                cursor.move()
                cursor.stick_to_walls(OBSTACLES, CURSOR_WALL_SNAP_DISTANCE, CURSOR_WALL_LEAVE_DELAY_FRAMES)

                # The cursor trails a line when it leaves the frame/a rectangle,
                # and when the line touches the frame or a rectangle again, we
                # paint the enclosed area and add it to the obstacle list
                touching = is_touching_obstacles(cursor.get_rect(), OBSTACLES)
                if not cursor.drawing:
                    if not touching:
                        cursor.drawing = True
                        start_x, start_y = get_leave_point(cursor.x, cursor.y, OBSTACLES, SNAP_TOLERANCE)
                        cursor.trail = [(start_x, start_y)]
                else:
                    if touching:
                        end_x, end_y = get_leave_point(cursor.x, cursor.y, OBSTACLES, SNAP_TOLERANCE)
                        closing_trail = cursor.trail + [(end_x, end_y)]
                        if any(ball_touches_trail(ball, closing_trail) for ball in balls):
                            # A ball is right on the closing segment - painting the
                            # area now would guarantee trapping it inside
                            cursor.x, cursor.y = cursor.trail[0]
                            cursor.drawing = False
                            cursor.trail = []
                            lives -= 1
                            if lives <= 0:
                                game_over = True
                        else:
                            new_obstacles = capture_enclosed_areas(closing_trail, OBSTACLES, balls)
                            OBSTACLES.extend(new_obstacles)
                            cursor.drawing = False
                            cursor.trail = []

                            # A ball walled off from every other ball turns blue
                            # and rewards the player: bonus points, and the level
                            # timer (and with it the ball speed ramp) resets.
                            # Skip balls that are already blue - a ball stays
                            # isolated for the rest of the level (walls never
                            # come down), so without this check every later
                            # capture would reward the same ball again
                            if len(balls) > 1:
                                isolated_balls = [
                                    group[0] for group in find_ball_groups(OBSTACLES, balls)
                                    if len(group) == 1 and group[0].image is not blue_ball_image
                                ]
                                if isolated_balls:
                                    for isolated_ball in isolated_balls:
                                        isolated_ball.image = blue_ball_image
                                    isolated_ball_count += len(isolated_balls)
                                    banked_score += ISOLATION_BONUS_SCORE * len(isolated_balls)
                                    elapsed_frames = 0

                            # Once the threshold is reached, points for the
                            # completed level go into the banked total and the
                            # game pauses with a message - the actual transition
                            # (new ball, clean field, etc.) happens on the  
                            # keypress, see the event handling above
                            percent = get_captured_percent(OBSTACLES)
                            if percent >= LEVEL_UP_PERCENT:
                                level_up_gain = calculate_score(percent, len(balls))
                                banked_score += level_up_gain
                                level_transition = True
                    else:
                        cursor.trail.append((cursor.x, cursor.y))

                # Ball speed ramps up linearly over the level's time budget -
                # from half the base speed at the start to double by the time
                # the timer runs out
                level_progress = min(1, elapsed_frames / level_time_limit)
                ball_speed = player_speed * (
                    BALL_SPEED_MIN_FACTOR + (BALL_SPEED_MAX_FACTOR - BALL_SPEED_MIN_FACTOR) * level_progress
                )
                for ball in balls:
                    ball.set_speed(ball_speed)

                # Move the balls and bounce them off the walls
                for ball in balls:
                    ball.update()

                # Bounce the balls off each other
                for i in range(len(balls)):
                    for j in range(i + 1, len(balls)):
                        resolve_ball_collision(balls[i], balls[j])

                # Bounce the balls off the obstacle rectangles
                for ball in balls:
                    for obstacle in OBSTACLES:
                        resolve_ball_obstacle_collision(ball, obstacle)

                # If a ball touches the not-yet-painted line, it breaks and the
                # cursor snaps back to the point where it started drawing
                if cursor.drawing:
                    trail_points = cursor.trail + [(cursor.x, cursor.y)]
                    if any(ball_touches_trail(ball, trail_points) for ball in balls):
                        cursor.x, cursor.y = cursor.trail[0]
                        cursor.drawing = False
                        cursor.trail = []
                        lives -= 1
                        if lives <= 0:
                            game_over = True

        # On Game Over, submit the final score to the server once and pull a
        # fresh leaderboard - only in the browser, where networking exists at all
        if game_over and not score_submitted and net.IS_BROWSER:
            score_submitted = True
            final_percent = get_captured_percent(OBSTACLES)
            final_score = banked_score + calculate_score(final_percent, len(balls))
            try:
                await net.submit_score(LEADERBOARD_BASE_URL, username, pin, final_score, level, isolated_ball_count)
                result = await net.fetch_leaderboard(LEADERBOARD_BASE_URL, LEADERBOARD_LIMIT)
                if result.get("ok"):
                    leaderboard_entries = result.get("entries", [])
            except Exception:
                pass

        # Rendering
        screen.fill((40, 50, 70))  # clear the screen with the background color

        if not logged_in:
            # Login screen: name + 4-digit PIN, nothing from the game is drawn yet
            layout = login_layout()
            active_color = (255, 220, 80)

            title_text = game_over_font.render("ENTER YOUR NAME", True, TEXT_COLOR)
            screen.blit(title_text, title_text.get_rect(midtop=(layout["center_x"], layout["title_top"])))

            name_box = layout["name_box"]
            name_label = score_font.render("Name", True, TEXT_COLOR)
            screen.blit(name_label, (name_box.left, layout["name_label_top"]))
            pygame.draw.rect(screen, PANEL_COLOR, name_box)
            pygame.draw.rect(screen, active_color if active_field == "username" else TEXT_COLOR, name_box, 2)
            name_value = score_font.render(username, True, TEXT_COLOR)
            screen.blit(name_value, (name_box.left + 8, name_box.centery - name_value.get_height() // 2))

            pin_label = score_font.render("4-digit PIN", True, TEXT_COLOR)
            screen.blit(pin_label, (layout["pin_boxes"][0].left, layout["pin_label_top"]))
            pin_border_color = active_color if active_field == "pin" else TEXT_COLOR
            for i, box in enumerate(layout["pin_boxes"]):
                pygame.draw.rect(screen, PANEL_COLOR, box)
                pygame.draw.rect(screen, pin_border_color, box, 2)
                if i < len(pin):
                    pygame.draw.circle(screen, TEXT_COLOR, box.center, 8)

            status_surface = score_font.render(login_status, True, TEXT_COLOR)
            screen.blit(status_surface, status_surface.get_rect(midtop=(layout["center_x"], layout["status_top"])))

            hint_surface = score_font.render("Click a field or press TAB to switch, ENTER to continue", True, TEXT_COLOR)
            screen.blit(hint_surface, hint_surface.get_rect(midtop=(layout["center_x"], layout["hint_top"])))

            pygame.display.flip()
            await asyncio.sleep(0)
            clock.tick(60)
            continue

        cursor.update_animation()

        blocked_grid = get_blocked_grid_cached(OBSTACLES)
        for obstacle in OBSTACLES:
            if obstacle.is_frame:
                tile_image = BORDER_IMAGES[obstacle.edge]
                draw_frame_edge(screen, obstacle.rect, obstacle.color, tile_image, EDGE_IS_HORIZONTAL[obstacle.edge])
            else:
                draw_captured_obstacle(
                    screen, obstacle.rect, obstacle.color,
                    captured_background_image, BORDER_IMAGES, CORNER_TILES, WALL_THICKNESS,
                    blocked_grid,
                )

        if cursor.drawing and len(cursor.trail) >= 1:
            pygame.draw.lines(screen, LINE_COLOR, False, cursor.trail + [(cursor.x, cursor.y)], TRAIL_LINE_WIDTH)

        for ball in balls:
            screen.blit(ball.image, ball.get_rect())

        screen.blit(cursor.image, cursor.get_rect())

        percent = get_captured_percent(OBSTACLES)
        if level_transition:
            # Points for the completed level are already in banked_score - the
            # field and balls haven't been reset yet (they just look that way),
            # so recomputing the current percent would double-count the level
            score = banked_score
        else:
            score = banked_score + calculate_score(percent, len(balls))

        # Info panel to the right of the play field, full window height
        panel_rect = pygame.Rect(SCREEN_WIDTH, 0, PANEL_WIDTH, SCREEN_HEIGHT)
        pygame.draw.rect(screen, PANEL_COLOR, panel_rect)

        panel_x = SCREEN_WIDTH + PANEL_PADDING
        line_y = PANEL_PADDING

        name_line = score_font.render(username, True, TEXT_COLOR)
        screen.blit(name_line, (panel_x, line_y))
        line_y += name_line.get_height() + PANEL_LINE_GAP

        level_line = score_font.render(f"Level: {level}", True, TEXT_COLOR)
        screen.blit(level_line, (panel_x, line_y))
        line_y += level_line.get_height() + PANEL_LINE_GAP

        line_y += blit_line_parts(
            screen, panel_x, line_y, [blue_ball_image, f" {isolated_ball_count}"], score_font, TEXT_COLOR
        ) + PANEL_LINE_GAP

        remaining_seconds = max(0, level_time_limit - elapsed_frames) // 60
        timer_line = score_font.render(f"Time left: {remaining_seconds // 60}:{remaining_seconds % 60:02d}", True, TEXT_COLOR)
        screen.blit(timer_line, (panel_x, line_y))
        line_y += timer_line.get_height() + PANEL_LINE_GAP

        captured_line = score_font.render(f"Captured: {percent:.1f}%", True, TEXT_COLOR)
        screen.blit(captured_line, (panel_x, line_y))
        line_y += captured_line.get_height() + PANEL_LINE_GAP

        # Progress bar - how much territory is still left to capture before the level ends
        bar_width = PANEL_WIDTH - 2 * PANEL_PADDING
        bar_rect = pygame.Rect(panel_x, line_y, bar_width, PROGRESS_BAR_HEIGHT)
        pygame.draw.rect(screen, PROGRESS_BAR_BG_COLOR, bar_rect)
        progress = min(1, percent / LEVEL_UP_PERCENT)
        fill_rect = pygame.Rect(panel_x, line_y, round(bar_width * progress), PROGRESS_BAR_HEIGHT)
        pygame.draw.rect(screen, PROGRESS_BAR_COLOR, fill_rect)
        line_y += PROGRESS_BAR_HEIGHT + PANEL_LINE_GAP

        score_line = score_font.render(f"Score: {score}", True, TEXT_COLOR)
        screen.blit(score_line, (panel_x, line_y))
        line_y += score_line.get_height() + PANEL_LINE_GAP

        lives_label = score_font.render("Lives:", True, TEXT_COLOR)
        screen.blit(lives_label, (panel_x, line_y))
        line_y += lives_label.get_height() + PANEL_LINE_GAP

        icon_w, icon_h = CURSOR_IMAGE_SIZE
        for i in range(lives):
            icon_x = panel_x + i * (icon_w + LIFE_ICON_GAP)
            screen.blit(cursor.image, (icon_x, line_y))
        line_y += icon_h + PANEL_LINE_GAP * 2

        if leaderboard_entries:
            best_label = score_font.render("Best Scores:", True, TEXT_COLOR)
            screen.blit(best_label, (panel_x, line_y))
            line_y += best_label.get_height() + PANEL_LINE_GAP

            for entry in leaderboard_entries:
                parts = [
                    f"{entry['username']}: {entry['score']} (",
                    default_ball_image, f"{entry['level']}, ",
                    blue_ball_image, f"{entry['balls_isolated']})",
                ]
                entry_height = blit_line_parts(screen, panel_x, line_y, parts, score_font, TEXT_COLOR)
                line_y += entry_height + PANEL_LINE_GAP // 2

        if paused:
            paused_text = game_over_font.render("PAUSED", True, TEXT_COLOR)
            screen.blit(
                paused_text,
                paused_text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2)),
            )

        if level_transition:
            title_text = game_over_font.render(f"LEVEL {level} COMPLETE!", True, TEXT_COLOR)
            gain_text = score_font.render(f"+{level_up_gain} points banked", True, TEXT_COLOR)
            continue_text = score_font.render(f"Press SPACE for level {level + 1}", True, TEXT_COLOR)
            screen.blit(
                title_text,
                title_text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 30)),
            )
            screen.blit(
                gain_text,
                gain_text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 20)),
            )
            screen.blit(
                continue_text,
                continue_text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 50)),
            )

        if game_over:
            game_over_text = game_over_font.render("GAME OVER", True, TEXT_COLOR)
            restart_text = score_font.render("Press SPACE to play again", True, TEXT_COLOR)
            screen.blit(
                game_over_text,
                game_over_text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 20)),
            )
            screen.blit(
                restart_text,
                restart_text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 30)),
            )

        pygame.display.flip()

        await asyncio.sleep(0)
        clock.tick(60)

    pygame.quit()
    sys.exit()

asyncio.run(main())
