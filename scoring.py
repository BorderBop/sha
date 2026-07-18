from config import POINTS_PER_PERCENT, BALL_BONUS_PER_BALL


def calculate_score(percent, ball_count):
    ball_multiplier = 1 + (ball_count - 1) * BALL_BONUS_PER_BALL
    raw_score = percent * POINTS_PER_PERCENT * ball_multiplier
    return max(0, round(raw_score))
