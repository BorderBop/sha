import pygame

from config import BALL_IMAGE_SIZE


def load_image(path, size):
    # Load the PNG, convert transparency for the screen format, and resize it
    image = pygame.image.load(path).convert_alpha()
    image = pygame.transform.scale(image, size)
    return image


def load_ball_image(path, size=BALL_IMAGE_SIZE):
    return load_image(path, size)
