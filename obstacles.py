import pygame

from config import SCREEN_WIDTH, SCREEN_HEIGHT, FRAME_WIDTH, BOTTOM_FRAME_WIDTH, FRAME_COLOR


class Obstacle:
    _next_id = 0

    def __init__(self, x, y, width, height, color, is_frame=False):
        self.id = Obstacle._next_id
        Obstacle._next_id += 1
        self.rect = pygame.Rect(x, y, width, height)
        self.color = color
        self.is_frame = is_frame


def make_initial_obstacles():
    # Just the field frame, no captured territory - used both when the
    # game starts and when the field resets for a new level
    return [
        Obstacle(0, 0, FRAME_WIDTH, SCREEN_HEIGHT, FRAME_COLOR, is_frame=True),
        Obstacle(0, 0, SCREEN_WIDTH, FRAME_WIDTH, FRAME_COLOR, is_frame=True),
        Obstacle(0, SCREEN_HEIGHT - BOTTOM_FRAME_WIDTH, SCREEN_WIDTH, BOTTOM_FRAME_WIDTH, FRAME_COLOR, is_frame=True),
        Obstacle(SCREEN_WIDTH - FRAME_WIDTH, 0, FRAME_WIDTH, SCREEN_HEIGHT, FRAME_COLOR, is_frame=True),
    ]


# Obstacle rectangles: coordinates, size and color are given as parameters
OBSTACLES = make_initial_obstacles()
