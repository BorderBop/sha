import math


def resolve_ball_collision(a, b):
    dx = b.x - a.x
    dy = b.y - a.y
    dist = math.hypot(dx, dy)
    min_dist = a.radius + b.radius

    if dist >= min_dist:
        return
    if dist == 0:
        dist = 0.01
        dx, dy = 0.01, 0

    nx, ny = dx / dist, dy / dist

    # Раздвигаем шарики, чтобы они не "слипались"
    overlap = min_dist - dist
    a.x -= nx * overlap / 2
    a.y -= ny * overlap / 2
    b.x += nx * overlap / 2
    b.y += ny * overlap / 2

    # Упругое столкновение шариков одинаковой массы: меняем скорости вдоль нормали
    rel_vx = b.vx - a.vx
    rel_vy = b.vy - a.vy
    vel_along_normal = rel_vx * nx + rel_vy * ny

    if vel_along_normal > 0:
        return  # шарики уже разлетаются

    a.vx += vel_along_normal * nx
    a.vy += vel_along_normal * ny
    b.vx -= vel_along_normal * nx
    b.vy -= vel_along_normal * ny


def resolve_ball_obstacle_collision(ball, obstacle):
    rect = obstacle.rect
    closest_x = max(rect.left, min(ball.x, rect.right))
    closest_y = max(rect.top, min(ball.y, rect.bottom))
    dx = ball.x - closest_x
    dy = ball.y - closest_y
    dist_sq = dx * dx + dy * dy

    if dist_sq >= ball.radius * ball.radius:
        return None

    if dist_sq > 0:
        dist = math.sqrt(dist_sq)
        nx, ny = dx / dist, dy / dist
    else:
        # Центр шарика оказался внутри прямоугольника — выталкиваем по ближайшей стороне
        overlap_left = ball.x - rect.left
        overlap_right = rect.right - ball.x
        overlap_top = ball.y - rect.top
        overlap_bottom = rect.bottom - ball.y
        min_overlap = min(overlap_left, overlap_right, overlap_top, overlap_bottom)
        if min_overlap == overlap_left:
            nx, ny, dist = -1, 0, 0
        elif min_overlap == overlap_right:
            nx, ny, dist = 1, 0, 0
        elif min_overlap == overlap_top:
            nx, ny, dist = 0, -1, 0
        else:
            nx, ny, dist = 0, 1, 0

    ball.x += nx * (ball.radius - dist)
    ball.y += ny * (ball.radius - dist)

    vel_along_normal = ball.vx * nx + ball.vy * ny
    if vel_along_normal < 0:
        ball.vx -= 2 * vel_along_normal * nx
        ball.vy -= 2 * vel_along_normal * ny

    return obstacle.id
