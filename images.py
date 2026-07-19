import os
import random

import pygame

from config import BALL_IMAGE_SIZE


def load_image(path, size):
    # Load the PNG, convert transparency for the screen format, and resize it
    image = pygame.image.load(path).convert_alpha()
    image = pygame.transform.scale(image, size)
    return image


def load_ball_image(path, size=BALL_IMAGE_SIZE):
    return load_image(path, size)


def load_image_native(path):
    # Like load_image, but keeps the file's own size - for tile images that
    # are already exactly the size they need to be drawn at
    return pygame.image.load(path).convert_alpha()


def load_cover_image(path, size):
    # Like load_image, but scales up just enough to *cover* the target size
    # (preserving aspect ratio) and crops the centered overflow, instead of
    # stretching to fit - so a photo of any shape fills the area without
    # looking distorted
    image = pygame.image.load(path).convert()
    target_width, target_height = size
    image_width, image_height = image.get_size()
    scale = max(target_width / image_width, target_height / image_height)
    scaled = pygame.transform.scale(image, (round(image_width * scale), round(image_height * scale)))
    x = (scaled.get_width() - target_width) // 2
    y = (scaled.get_height() - target_height) // 2
    return scaled.subsurface(pygame.Rect(x, y, target_width, target_height)).copy()


BACKGROUND_IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg")


def load_random_background(directory, size):
    # Picks a random photo from `directory` and scales/crops it to `size`.
    # Returns None if the folder is missing or has no images in it, so
    # callers can fall back to a flat color fill
    try:
        filenames = [name for name in os.listdir(directory) if name.lower().endswith(BACKGROUND_IMAGE_EXTENSIONS)]
    except OSError:
        return None
    if not filenames:
        return None
    return load_cover_image(os.path.join(directory, random.choice(filenames)), size)
