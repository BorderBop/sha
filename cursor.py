import pygame

from config import SCREEN_WIDTH, SCREEN_HEIGHT


class Cursor:
    def __init__(self, x, y, image, speed):
        self.x = float(x)
        self.y = float(y)
        self.image = image
        self.speed = speed
        self.drawing = False
        self.trail = []

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
