import math
import random

from config import SCREEN_WIDTH, SCREEN_HEIGHT


class Ball:
    def __init__(self, x, y, speed, image):
        self.x = float(x)
        self.y = float(y)
        angle = random.uniform(0, 2 * math.pi)
        self.vx = speed * math.cos(angle)
        self.vy = speed * math.sin(angle)
        self.image = image
        self.radius = image.get_width() / 2

    def update(self):
        self.x += self.vx
        self.y += self.vy

        if self.x - self.radius <= 0:
            self.x = self.radius
            self.vx = -self.vx
        elif self.x + self.radius >= SCREEN_WIDTH:
            self.x = SCREEN_WIDTH - self.radius
            self.vx = -self.vx

        if self.y - self.radius <= 0:
            self.y = self.radius
            self.vy = -self.vy
        elif self.y + self.radius >= SCREEN_HEIGHT:
            self.y = SCREEN_HEIGHT - self.radius
            self.vy = -self.vy

    def get_rect(self):
        rect = self.image.get_rect()
        rect.center = (round(self.x), round(self.y))
        return rect
