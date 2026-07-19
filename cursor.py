import math

import pygame

from config import SCREEN_WIDTH, SCREEN_HEIGHT

MOVE_KEYS = (
    pygame.K_LEFT, pygame.K_RIGHT, pygame.K_UP, pygame.K_DOWN,
    pygame.K_a, pygame.K_d, pygame.K_w, pygame.K_s,
    pygame.K_KP4, pygame.K_KP6, pygame.K_KP8, pygame.K_KP2,
)
KEY_DIRECTIONS = {
    pygame.K_LEFT: (-1, 0),
    pygame.K_RIGHT: (1, 0),
    pygame.K_UP: (0, -1),
    pygame.K_DOWN: (0, 1),
    pygame.K_a: (-1, 0),
    pygame.K_d: (1, 0),
    pygame.K_w: (0, -1),
    pygame.K_s: (0, 1),
    pygame.K_KP4: (-1, 0),
    pygame.K_KP6: (1, 0),
    pygame.K_KP8: (0, -1),
    pygame.K_KP2: (0, 1),
}


class Cursor:
    def __init__(self, x, y, images, speed, frame_delay, input_debounce_frames):
        self.x = float(x)
        self.y = float(y)
        self.images = images
        self.frame_index = 0
        self.frame_timer = 0
        self.frame_delay = frame_delay
        self.image = images[0]
        self.speed = speed
        self.drawing = False
        self.trail = []

        # Keys currently held, oldest first - only the oldest one moves the
        # cursor, so two keys held at once never produce diagonal movement,
        # and whichever key was pressed first keeps control
        self.key_order = []
        self.input_debounce_frames = input_debounce_frames
        self.pending_key = None
        self.pending_timer = 0
        self.active_key = None

        # Sticks to a nearby wall (obstacle/frame) so it's easy to hug it
        # precisely - see stick_to_walls()
        self.stuck_to = None
        self.leaving_timer = 0

    def update_animation(self):
        self.frame_timer += 1
        if self.frame_timer >= self.frame_delay:
            self.frame_timer = 0
            self.frame_index = (self.frame_index + 1) % len(self.images)
            self.image = self.images[self.frame_index]

    def on_key_down(self, key):
        if key in MOVE_KEYS and key not in self.key_order:
            self.key_order.append(key)

    def on_key_up(self, key):
        if key in self.key_order:
            self.key_order.remove(key)

    def move(self):
        leader = self.key_order[0] if self.key_order else None

        if leader != self.pending_key:
            # The oldest held key changed - start (or restart) the debounce
            # window before actually switching direction, so brief overlaps
            # between two keys don't produce a stray diagonal step
            self.pending_key = leader
            self.pending_timer = 0
        elif self.pending_timer < self.input_debounce_frames:
            self.pending_timer += 1

        if leader is None or self.pending_timer >= self.input_debounce_frames:
            self.active_key = leader

        if self.active_key is not None:
            dx, dy = KEY_DIRECTIONS[self.active_key]
            self.x += dx * self.speed
            self.y += dy * self.speed

        half_w = self.image.get_width() / 2
        half_h = self.image.get_height() / 2
        self.x = max(half_w, min(self.x, SCREEN_WIDTH - half_w))
        self.y = max(half_h, min(self.y, SCREEN_HEIGHT - half_h))

    def get_rect(self):
        rect = self.image.get_rect()
        rect.center = (round(self.x), round(self.y))
        return rect

    def stick_to_walls(self, obstacles, snap_distance, leave_delay_frames):
        # Makes it easy to hug a wall precisely: once within snap_distance of
        # an obstacle/frame, the cursor snaps flush onto it immediately; once
        # stuck, moving away from it is held for leave_delay_frames frames
        # before it's actually allowed, so a brief stray step doesn't peel
        # the cursor off the wall by accident
        if self.stuck_to is not None:
            rect = self.stuck_to
            clamped_x = min(max(self.x, rect.left), rect.right)
            clamped_y = min(max(self.y, rect.top), rect.bottom)
            dist = math.hypot(self.x - clamped_x, self.y - clamped_y)

            if dist == 0:
                self.leaving_timer = 0
                return

            if self.leaving_timer < leave_delay_frames:
                self.leaving_timer += 1
                self.x, self.y = clamped_x, clamped_y
                return

            self.stuck_to = None
            self.leaving_timer = 0
            # fall through - a different wall may now be within snap range

        nearest_rect = None
        nearest_dist = snap_distance
        for obstacle in obstacles:
            rect = obstacle.rect
            clamped_x = min(max(self.x, rect.left), rect.right)
            clamped_y = min(max(self.y, rect.top), rect.bottom)
            dist = math.hypot(self.x - clamped_x, self.y - clamped_y)
            if dist <= nearest_dist:
                nearest_dist = dist
                nearest_rect = rect

        if nearest_rect is not None:
            self.stuck_to = nearest_rect
            self.leaving_timer = 0
            self.x = min(max(self.x, nearest_rect.left), nearest_rect.right)
            self.y = min(max(self.y, nearest_rect.top), nearest_rect.bottom)
