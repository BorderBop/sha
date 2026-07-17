import math
from collections import deque

from config import GRID_CELL, GRID_COLS, GRID_ROWS, TRAIL_LINE_WIDTH, FRAME_COLOR, PLAY_FIELD_AREA
from obstacles import Obstacle


def get_captured_percent(obstacles):
    captured_area = sum(
        obstacle.rect.width * obstacle.rect.height
        for obstacle in obstacles
        if not obstacle.is_frame
    )
    return captured_area / PLAY_FIELD_AREA * 100


def build_blocked_grid(obstacles):
    blocked = [[False] * GRID_COLS for _ in range(GRID_ROWS)]
    for obstacle in obstacles:
        rect = obstacle.rect
        col_start = max(0, rect.left // GRID_CELL)
        col_end = min(GRID_COLS, math.ceil(rect.right / GRID_CELL))
        row_start = max(0, rect.top // GRID_CELL)
        row_end = min(GRID_ROWS, math.ceil(rect.bottom / GRID_CELL))
        for row in range(row_start, row_end):
            for col in range(col_start, col_end):
                blocked[row][col] = True
    return blocked


def mark_trail_blocked(blocked, trail_points):
    for i in range(len(trail_points) - 1):
        x1, y1 = trail_points[i]
        x2, y2 = trail_points[i + 1]
        left = min(x1, x2) - TRAIL_LINE_WIDTH
        right = max(x1, x2) + TRAIL_LINE_WIDTH
        top = min(y1, y2) - TRAIL_LINE_WIDTH
        bottom = max(y1, y2) + TRAIL_LINE_WIDTH

        col_start = max(0, int(left) // GRID_CELL)
        col_end = min(GRID_COLS, math.ceil(right / GRID_CELL))
        row_start = max(0, int(top) // GRID_CELL)
        row_end = min(GRID_ROWS, math.ceil(bottom / GRID_CELL))

        for row in range(row_start, row_end):
            for col in range(col_start, col_end):
                blocked[row][col] = True


def find_enclosed_cells(wall_grid, obstacle_grid, ball_cells):
    # wall_grid (препятствия + линия) используется, чтобы найти, куда шарики
    # могут добраться. obstacle_grid (только реальные препятствия) - чтобы
    # не создавать повторно уже закрашенные клетки. Клетки, заблокированные
    # только линией (ещё не ставшей препятствием), должны попасть в захват -
    # иначе вдоль бывшей линии останется незакрашенная щель.
    reachable = [[False] * GRID_COLS for _ in range(GRID_ROWS)]
    queue = deque()

    for col, row in ball_cells:
        if 0 <= row < GRID_ROWS and 0 <= col < GRID_COLS and not wall_grid[row][col] and not reachable[row][col]:
            reachable[row][col] = True
            queue.append((col, row))

    while queue:
        col, row = queue.popleft()
        for dcol, drow in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            ncol, nrow = col + dcol, row + drow
            if 0 <= ncol < GRID_COLS and 0 <= nrow < GRID_ROWS \
                    and not wall_grid[nrow][ncol] and not reachable[nrow][ncol]:
                reachable[nrow][ncol] = True
                queue.append((ncol, nrow))

    enclosed = set()
    for row in range(GRID_ROWS):
        for col in range(GRID_COLS):
            if not obstacle_grid[row][col] and not reachable[row][col]:
                enclosed.add((col, row))
    return enclosed


def merge_cells_to_rects(cells):
    consumed = set()
    rects = []

    for col, row in sorted(cells):
        if (col, row) in consumed:
            continue

        # Горизонтальный разбег вправо
        run_end = col
        while (run_end, row) in cells and (run_end, row) not in consumed:
            run_end += 1

        # Тянем эту полосу вниз, пока снизу повторяется тот же разбег
        height = 1
        while all((c, row + height) in cells and (c, row + height) not in consumed for c in range(col, run_end)):
            height += 1

        for r in range(row, row + height):
            for c in range(col, run_end):
                consumed.add((c, r))

        rects.append((col, row, run_end - col, height))

    return rects


def capture_enclosed_areas(trail_points, obstacles, balls):
    obstacle_grid = build_blocked_grid(obstacles)
    wall_grid = [row[:] for row in obstacle_grid]
    mark_trail_blocked(wall_grid, trail_points)

    ball_cells = [(int(ball.x) // GRID_CELL, int(ball.y) // GRID_CELL) for ball in balls]
    enclosed = find_enclosed_cells(wall_grid, obstacle_grid, ball_cells)
    if not enclosed:
        return []

    new_obstacles = []
    for col, row, width_cells, height_cells in merge_cells_to_rects(enclosed):
        x = col * GRID_CELL
        y = row * GRID_CELL
        width = width_cells * GRID_CELL
        height = height_cells * GRID_CELL
        new_obstacles.append(Obstacle(x, y, width, height, FRAME_COLOR))

    return new_obstacles
