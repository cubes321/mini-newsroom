"""The mood in the body (2026-11-04): a pose per mood that eases in, arms only for whoever is talking."""
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

from newsroom import sprites


def _fresh(monkeypatch):
    monkeypatch.setattr(sprites, "_POSED", {})


def test_every_mood_has_a_pose_and_every_pose_draws(monkeypatch):
    _fresh(monkeypatch)
    assert set(sprites.POSE_FOR_MOOD) == {m for m in sprites.MOODS if m}
    canvas = pygame.Surface((200, 200))
    plain = None
    for mood, pose in sprites.POSE_FOR_MOOD.items():
        canvas.fill((0, 0, 0))
        sprites.draw_character(canvas, 100, 190, "mag_a", 0.0, 0.5, scale=4, mood=mood, posture=(pose, 1.0))
        drawn = pygame.image.tostring(canvas, "RGB")
        if plain is None:
            canvas.fill((0, 0, 0))
            sprites.draw_character(canvas, 100, 190, "mag_a", 0.0, 0.5, scale=4, posture=("", 1.0))
            plain = pygame.image.tostring(canvas, "RGB")
        assert drawn != plain, mood


def test_a_pose_eases_in_and_the_arms_wait_for_the_speaker(monkeypatch):
    _fresh(monkeypatch)
    key = ("mag_b", None)
    sprites._posture(key, "", 0.0, 10.0)                       # sitting as usual
    pose, e, *_ = sprites._posture(key, "cross", 0.0, 10.0)    # the mood arrives
    assert pose.arms == "fold" and e == 0.0
    pose, e, _, _, arms, _ = sprites._posture(key, "cross", 0.0, 10.15)
    assert 0.4 < e < 0.6 and arms == 0.0                       # half way in; not talking, so arms down
    sprites._posture(key, "cross", 0.6, 10.2)                  # the mouth opens: they are the one talking
    *_, arms, _ = sprites._posture(key, "cross", 0.0, 10.6)
    assert arms == 1.0
    sprites._posture(key, "", 0.0, 10.75)                     # the mood is over
    pose, e, old, left, arms, old_arms = sprites._posture(key, "", 0.0, 10.9)
    assert old.arms == "fold" and 0.4 < left < 0.6 and 0.4 < old_arms < 0.6   # easing back out


def test_a_listener_takes_the_mood_without_raising_their_hands(monkeypatch):
    _fresh(monkeypatch)
    key = ("host_b", None)
    for t in (0.0, 0.5, 1.0):
        pose, e, _, _, arms, _ = sprites._posture(key, "surprised", 0.0, t)
    assert pose.body_dy == -1 and e == 1.0 and arms == 0.0
