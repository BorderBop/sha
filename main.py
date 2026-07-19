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
)
from images import load_image, load_ball_image
from obstacles import OBSTACLES, make_initial_obstacles
from ball import Ball
from cursor import Cursor
from physics import resolve_ball_collision, resolve_ball_obstacle_collision
from trail import is_touching_obstacles, get_leave_point, ball_touches_trail
from capture import capture_enclosed_areas, get_captured_percent, find_ball_groups
from scoring import calculate_score
import net

balls = [
    Ball(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2, player_speed, load_ball_image(path))
    for path in BALL_IMAGE_PATHS
]

default_ball_image = load_ball_image(BALL_IMAGE_PATH)
blue_ball_image = load_ball_image(BLUE_BALL_IMAGE_PATH)

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


# Main async loop (works both on desktop and on the web via pygbag)
async def main():
    global lives, game_over, elapsed_frames, banked_score, level, level_transition, level_up_gain, paused
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
            title_text = game_over_font.render("ENTER YOUR NAME", True, TEXT_COLOR)
            screen.blit(
                title_text,
                title_text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 150)),
            )

            box_width, box_height = 300, 40
            username_box = pygame.Rect(0, 0, box_width, box_height)
            username_box.center = (SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 60)
            pin_box = pygame.Rect(0, 0, box_width, box_height)
            pin_box.center = (SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2)

            for field_name, box, label, value in (
                ("username", username_box, "Name", username),
                ("pin", pin_box, "4-digit PIN", "*" * len(pin)),
            ):
                border_color = (255, 220, 80) if active_field == field_name else TEXT_COLOR
                label_surface = score_font.render(label, True, TEXT_COLOR)
                screen.blit(label_surface, (box.left, box.top - label_surface.get_height() - 4))
                pygame.draw.rect(screen, PANEL_COLOR, box)
                pygame.draw.rect(screen, border_color, box, 2)
                value_surface = score_font.render(value, True, TEXT_COLOR)
                screen.blit(value_surface, (box.left + 8, box.centery - value_surface.get_height() // 2))

            status_surface = score_font.render(login_status, True, TEXT_COLOR)
            screen.blit(
                status_surface,
                status_surface.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 60)),
            )

            hint_surface = score_font.render("TAB to switch field, ENTER to continue", True, TEXT_COLOR)
            screen.blit(
                hint_surface,
                hint_surface.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 100)),
            )

            pygame.display.flip()
            await asyncio.sleep(0)
            clock.tick(60)
            continue

        cursor.update_animation()

        for obstacle in OBSTACLES:
            pygame.draw.rect(screen, obstacle.color, obstacle.rect)

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
