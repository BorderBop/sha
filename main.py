import sys
import asyncio # Для совместимости с твоим веб-форматом

import pygame

from config import (
    screen, score_font, game_over_font, clock,
    SCREEN_WIDTH, SCREEN_HEIGHT,
    LINE_COLOR, TEXT_COLOR, TRAIL_LINE_WIDTH, SNAP_TOLERANCE,
    BALL_IMAGE_PATHS, BALL_IMAGE_PATH, player_speed,
    CURSOR_IMAGE_PATH, CURSOR_IMAGE_SIZE, CURSOR_SPEED,
    STARTING_LIVES, LIFE_ICON_GAP, LEVEL_UP_PERCENT,
    PANEL_WIDTH, PANEL_COLOR, PANEL_PADDING, PANEL_LINE_GAP,
    PROGRESS_BAR_HEIGHT, PROGRESS_BAR_BG_COLOR, PROGRESS_BAR_COLOR,
    LEADERBOARD_BASE_URL, USERNAME_MAX_LEN, PIN_LENGTH, LEADERBOARD_LIMIT,
)
from images import load_image, load_ball_image
from obstacles import OBSTACLES, make_initial_obstacles
from ball import Ball
from cursor import Cursor
from physics import resolve_ball_collision, resolve_ball_obstacle_collision
from trail import is_touching_obstacles, get_leave_point, ball_touches_trail
from capture import capture_enclosed_areas, get_captured_percent
from scoring import calculate_score
import net

balls = [
    Ball(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2, player_speed, load_ball_image(path))
    for path in BALL_IMAGE_PATHS
]

cursor = Cursor(
    0,
    SCREEN_HEIGHT // 2,
    load_image(CURSOR_IMAGE_PATH, CURSOR_IMAGE_SIZE),
    CURSOR_SPEED,
)

lives = STARTING_LIVES
game_over = False
elapsed_frames = 0
banked_score = 0
level = 1
level_transition = False
level_up_gain = 0
paused = False

# Экран логина - на нативном запуске сети нет (см. net.py), поэтому сразу
# считаем вошедшими под гостевым именем и пропускаем экран целиком
logged_in = not net.IS_BROWSER
username = "" if net.IS_BROWSER else "Guest"
pin = ""
active_field = "username"
login_status = ""
login_busy = False

score_submitted = False
leaderboard_entries = []


# Главный асинхронный цикл (подходит и для ПК, и для веба через pygbag)
async def main():
    global lives, game_over, elapsed_frames, banked_score, level, level_transition, level_up_gain, paused
    global logged_in, username, pin, active_field, login_status, login_busy
    global score_submitted, leaderboard_entries
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
            elif event.type == pygame.KEYDOWN and logged_in:
                if level_transition and event.key == pygame.K_SPACE:
                    # Пробел запускает следующий уровень: новый шарик, чистое
                    # поле, курсор в стартовой точке, жизни и таймер уровня заново
                    balls.append(
                        Ball(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2, player_speed, load_ball_image(BALL_IMAGE_PATH))
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
                    # Рестарт с тем же игроком, без повторного логина: поле,
                    # шарики, жизни, уровень и очки начинаются заново
                    balls[:] = [
                        Ball(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2, player_speed, load_ball_image(path))
                        for path in BALL_IMAGE_PATHS
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
                elif event.key == pygame.K_SPACE and not game_over:
                    paused = not paused

        if logged_in and not game_over and not level_transition and not paused:
            elapsed_frames += 1

            # Управление курсором стрелками клавиатуры
            keys = pygame.key.get_pressed()
            cursor.handle_input(keys)

            # Курсор тянет за собой линию, когда отрывается от рамки/прямоугольника,
            # а когда линия снова упирается в рамку или прямоугольник - закрашиваем
            # охваченную область и добавляем её в список препятствий
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
                        # Шарик оказался прямо на замыкающем отрезке - если всё равно
                        # закрасить область, он гарантированно окажется внутри неё
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

                        # При достижении порога очки за пройденный уровень уходят в
                        # несгораемую сумму, и игра встаёт на паузу с сообщением -
                        # сам переход (новый шарик, чистое поле и т.д.) происходит
                        # по нажатию любой клавиши, см. обработку событий выше
                        percent = get_captured_percent(OBSTACLES)
                        if percent >= LEVEL_UP_PERCENT:
                            elapsed_seconds = elapsed_frames / 60
                            level_up_gain = calculate_score(percent, elapsed_seconds, len(balls))
                            banked_score += level_up_gain
                            level_transition = True
                else:
                    cursor.trail.append((cursor.x, cursor.y))

            # Двигаем шарики и отталкиваем их от стенок
            for ball in balls:
                ball.update()

            # Отталкиваем шарики друг от друга
            for i in range(len(balls)):
                for j in range(i + 1, len(balls)):
                    resolve_ball_collision(balls[i], balls[j])

            # Отталкиваем шарики от прямоугольников-препятствий
            for ball in balls:
                for obstacle in OBSTACLES:
                    resolve_ball_obstacle_collision(ball, obstacle)

            # Если шарик задел ещё не закрашенную линию - она обрывается,
            # а курсор возвращается в точку, откуда начал её тянуть
            if cursor.drawing:
                trail_points = cursor.trail + [(cursor.x, cursor.y)]
                if any(ball_touches_trail(ball, trail_points) for ball in balls):
                    cursor.x, cursor.y = cursor.trail[0]
                    cursor.drawing = False
                    cursor.trail = []
                    lives -= 1
                    if lives <= 0:
                        game_over = True

        # По Game Over один раз отправляем итоговый счёт на сервер и подтягиваем
        # свежую таблицу рекордов - только в браузере, где сеть вообще доступна
        if game_over and not score_submitted and net.IS_BROWSER:
            score_submitted = True
            final_percent = get_captured_percent(OBSTACLES)
            final_score = banked_score + calculate_score(final_percent, elapsed_frames / 60, len(balls))
            try:
                await net.submit_score(LEADERBOARD_BASE_URL, username, pin, final_score, level)
                result = await net.fetch_leaderboard(LEADERBOARD_BASE_URL, LEADERBOARD_LIMIT)
                if result.get("ok"):
                    leaderboard_entries = result.get("entries", [])
            except Exception:
                pass

        # Отрисовка
        screen.fill((40, 50, 70))  # Очищаем экран фоновым цветом

        if not logged_in:
            # Экран логина: имя + 4-значный PIN, ничего из игры пока не рисуем
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

        for obstacle in OBSTACLES:
            pygame.draw.rect(screen, obstacle.color, obstacle.rect)

        if cursor.drawing and len(cursor.trail) >= 1:
            pygame.draw.lines(screen, LINE_COLOR, False, cursor.trail + [(cursor.x, cursor.y)], TRAIL_LINE_WIDTH)

        for ball in balls:
            screen.blit(ball.image, ball.get_rect())

        screen.blit(cursor.image, cursor.get_rect())

        percent = get_captured_percent(OBSTACLES)
        elapsed_seconds = elapsed_frames / 60
        if level_transition:
            # Очки пройденного уровня уже зачислены в banked_score - поле и шарики
            # ещё не сброшены (только визуально видны такими), пересчитывать их
            # заново текущий процент/время не нужно, иначе уровень посчитается дважды
            score = banked_score
        else:
            score = banked_score + calculate_score(percent, elapsed_seconds, len(balls))

        # Информационная панель справа от игрового поля, на всю высоту окна
        panel_rect = pygame.Rect(SCREEN_WIDTH, 0, PANEL_WIDTH, SCREEN_HEIGHT)
        pygame.draw.rect(screen, PANEL_COLOR, panel_rect)

        panel_x = SCREEN_WIDTH + PANEL_PADDING
        line_y = PANEL_PADDING

        level_line = score_font.render(f"Level: {level}", True, TEXT_COLOR)
        screen.blit(level_line, (panel_x, line_y))
        line_y += level_line.get_height() + PANEL_LINE_GAP

        captured_line = score_font.render(f"Captured: {percent:.1f}%", True, TEXT_COLOR)
        screen.blit(captured_line, (panel_x, line_y))
        line_y += captured_line.get_height() + PANEL_LINE_GAP

        # Прогрессбар - сколько ещё нужно захватить территории до конца уровня
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
                entry_text = f"{entry['username']}: {entry['score']}"
                entry_surface = score_font.render(entry_text, True, TEXT_COLOR)
                screen.blit(entry_surface, (panel_x, line_y))
                line_y += entry_surface.get_height() + PANEL_LINE_GAP // 2

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
