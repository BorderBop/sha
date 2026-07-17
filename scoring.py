from config import POINTS_PER_PERCENT, TIME_PENALTY_PER_SECOND, BALL_BONUS_PER_BALL


def calculate_score(percent, elapsed_seconds, ball_count):
    ball_multiplier = 1 + (ball_count - 1) * BALL_BONUS_PER_BALL
    raw_score = percent * POINTS_PER_PERCENT * ball_multiplier
    time_penalty = elapsed_seconds * TIME_PENALTY_PER_SECOND
    return max(0, round(raw_score - time_penalty))
