import pygame

from config import SCREEN_WIDTH, SCREEN_HEIGHT


class Cursor:
    def __init__(self, x, y, images, speed, frame_delay):
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

    def update_animation(self):
        self.frame_timer += 1
        if self.frame_timer >= self.frame_delay:
            self.frame_timer = 0
            self.frame_index = (self.frame_index + 1) % len(self.images)
            self.image = self.images[self.frame_index]

    def handle_input(self, keys):
        if keys[pygame.K_LEFT]:
            self.x -= self.speed
        if keys[pygame.K_RIGHT]:
            self.x += self.speed
        if keys[pygame.K_UP]:
            self.y -= self.speed
        if keys[pygame.K_DOWN]:
            self.y += self.speed

        half_w = self.image.get_width() / 2
        half_h = self.image.get_height() / 2
        self.x = max(half_w, min(self.x, SCREEN_WIDTH - half_w))
        self.y = max(half_h, min(self.y, SCREEN_HEIGHT - half_h))

    def get_rect(self):
        rect = self.image.get_rect()
        rect.center = (round(self.x), round(self.y))
        return rect
