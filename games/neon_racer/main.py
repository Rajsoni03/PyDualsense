#!/usr/bin/env python3
"""
Neon Racer — Entry point.

Run:
    cd games/neon_racer
    python main.py

Controls (keyboard fallback):
    P1: W/S = throttle/brake, A/D = steer, Left Shift = turbo, Esc = pause
    P2: Up/Down = throttle/brake, Left/Right = steer, Right Shift = turbo

DualSense:
    R2 = throttle (adaptive: slope feedback grows with speed)
    L2 = brake    (feedback; rigid on wheel lock; off on oil)
    Left stick = steer
    Touchpad swipe up = turbo
    Touchpad click    = toggle gyro steering
    Options           = pause
    X (cross)         = confirm / restart
"""

import os
import sys

# Allow imports from this directory without a package prefix
sys.path.insert(0, os.path.dirname(__file__))

import pygame
import pygame.font   # explicit import — prevents circular-import failure on Python 3.14

from constants import WINDOW_W, WINDOW_H, FPS, DARK_BG
from game import Game


def main() -> None:
    pygame.init()
    pygame.font.init()  # explicit — pygame.font may not auto-init on Python 3.14
    pygame.display.set_caption("Neon Racer")

    screen = pygame.display.set_mode((WINDOW_W, WINDOW_H))
    clock  = pygame.time.Clock()

    game = Game(screen)

    running = True
    while running:
        dt = clock.tick(FPS) / 1000.0
        dt = min(dt, 0.05)   # cap delta so pauses don't explode physics

        for event in pygame.event.get():
            if not game.handle_event(event):
                running = False

        if running:
            running = game.update(dt)

        game.draw()
        pygame.display.flip()

    game.shutdown()
    pygame.quit()
    sys.exit(0)


if __name__ == "__main__":
    main()
