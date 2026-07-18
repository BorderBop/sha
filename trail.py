import math

from config import TRAIL_LINE_WIDTH


def is_touching_obstacles(rect, obstacles):
    probe = rect.inflate(4, 4)
    for obstacle in obstacles:
        if probe.colliderect(obstacle.rect):
            return True
    return False


def get_leave_point(x, y, obstacles, tolerance):
    # Find the nearest rectangle/frame the cursor just broke away from
    best_rect = None
    best_dist = tolerance
    for obstacle in obstacles:
        rect = obstacle.rect
        dx = max(rect.left - x, 0, x - rect.right)
        dy = max(rect.top - y, 0, y - rect.bottom)
        dist = math.hypot(dx, dy)
        if dist <= best_dist:
            best_dist = dist
            best_rect = rect

    if best_rect is None:
        return x, y

    # Clamp the point to the found rectangle's border (independently on each
    # axis) - works for points on a side as well as corners, and always
    # gives a point exactly on the border, with no gap
    snapped_x = min(max(x, best_rect.left), best_rect.right)
    snapped_y = min(max(y, best_rect.top), best_rect.bottom)
    return snapped_x, snapped_y


def distance_point_to_segment(px, py, x1, y1, x2, y2):
    dx, dy = x2 - x1, y2 - y1
    if dx == 0 and dy == 0:
        return math.hypot(px - x1, py - y1)

    t = ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)
    t = max(0, min(1, t))
    closest_x = x1 + t * dx
    closest_y = y1 + t * dy
    return math.hypot(px - closest_x, py - closest_y)


def ball_touches_trail(ball, trail_points):
    threshold = ball.radius + TRAIL_LINE_WIDTH / 2
    for i in range(len(trail_points) - 1):
        x1, y1 = trail_points[i]
        x2, y2 = trail_points[i + 1]
        if distance_point_to_segment(ball.x, ball.y, x1, y1, x2, y2) <= threshold:
            return True
    return False
