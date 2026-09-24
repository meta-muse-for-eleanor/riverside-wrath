"""Curses front-end for Riverside Wrath.

Run with:  python3 -m riverside_wrath
"""

import curses
import os
import time

from .game import GameState, PLAY_TOP

BEST_FILE = os.path.expanduser("~/.riverside-wrath-best")
TICK_SECONDS = 0.08
MIN_W, MIN_H = 70, 22

TITLE_ART = [
    r" ____  _                     _     _        __        __         _   _     ",
    r"|  _ \(_)   ___  ___  _ __  | |__ (_)  ___  \ \      / /  _ __  | |_| |__  ",
    r"| |_) | |  / _ \/ _ \| '_ \ | '_ \| | / __|  \ \ /\ / /  / _` | | __| '_ \ ",
    r"|  _ <| | |  __/  __/| | | || | | | || (__    \ V  V /  | (_| | | |_| | | |",
    r"|_| \_|_|  \___|\___||_| |_||_| |_|_| \___|    \_/\_/    \__,_|  \__|_| |_|",
]

STORY = [
    "You are the ancient spirit of the riverside.",
    "For centuries you watched the town grow along your banks.",
    "Now polluters choke your waters with their trash -",
    "and your patience is spent.",
    "",
    "Cleanse the river with your surges. Let your wrath build.",
    "When it peaks... unleash the flood.",
]


def load_best():
    try:
        with open(BEST_FILE) as fh:
            return int(fh.read().strip())
    except (OSError, ValueError):
        return 0


def save_best(value):
    try:
        with open(BEST_FILE, "w") as fh:
            fh.write(str(value))
    except OSError:
        pass


def init_colors():
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(1, curses.COLOR_CYAN, curses.COLOR_BLUE)     # water
    curses.init_pair(2, curses.COLOR_GREEN, -1)                   # banks
    curses.init_pair(3, curses.COLOR_CYAN, -1)                   # spirit
    curses.init_pair(4, curses.COLOR_RED, -1)                     # polluters
    curses.init_pair(5, curses.COLOR_YELLOW, -1)                 # trash
    curses.init_pair(6, curses.COLOR_WHITE, -1)                   # surges / flood
    curses.init_pair(7, curses.COLOR_WHITE, -1)                   # HUD text


def bar(label, value, width=10):
    filled = int(round(value / 100 * width))
    return "{} [{}{}] {:>3}%".format(
        label, "#" * filled, "-" * (width - filled), int(value))


def draw(stdscr, game, best, paused):
    h, w = stdscr.getmaxyx()
    wave = game.tick_count // 5
    # terrain
    for y in range(h):
        for x in range(w):
            if game.river_left <= x <= game.river_right:
                ch = "~" if (x + y + wave) % 4 else " "
                stdscr.addch(y, x, ch, curses.color_pair(1))
            else:
                ch = "," if (x * 7 + y * 13) % 11 == 0 else " "
                stdscr.addch(y, x, ch, curses.color_pair(2))
    # trash
    for t in game.trash:
        if 0 <= t["y"] < h and 0 <= t["x"] < w:
            stdscr.addch(t["y"], t["x"], "*", curses.color_pair(5) | curses.A_BOLD)
    # polluters
    for p in game.polluters:
        if 0 <= p["y"] < h and 0 <= p["x"] < w:
            stdscr.addch(p["y"], p["x"], "P", curses.color_pair(4) | curses.A_BOLD)
    # surge rings (expanding circles)
    for ring in game.rings:
        r = 6 - ring["ttl"]
        x0 = game.spirit_x
        for dx in range(-r, r + 1):
            dy = int(round((r * r - dx * dx) ** 0.5))
            for yy in (ring["y"] - dy, ring["y"] + dy):
                xx = x0 + dx
                if PLAY_TOP <= yy <= game.play_bottom and 0 <= xx < w:
                    try:
                        stdscr.addch(yy, xx, "o", curses.color_pair(6) | curses.A_BOLD)
                    except curses.error:
                        pass
    # flood band sweeping down
    if game.flood_ttl > 0:
        band_y = h - game.flood_ttl
        for yy in (band_y - 1, band_y, band_y + 1):
            if 0 <= yy < h:
                stdscr.addstr(yy, 0, "~" * w, curses.color_pair(6) | curses.A_BOLD)
    # spirit
    stdscr.addch(game.spirit_y, game.spirit_x, "@",
                 curses.color_pair(3) | curses.A_BOLD)
    # HUD
    hud = " Score {:>6}   Best {:>6}   Level {}".format(game.score, best, game.level)
    stdscr.addstr(0, 0, hud[:w - 1], curses.color_pair(7) | curses.A_BOLD)
    status = bar("Purity", game.purity) + "   " + bar("Wrath", game.wrath)
    if game.wrath >= 100:
        status += "  READY - press X!"
    stdscr.addstr(1, 0, status[:w - 1], curses.color_pair(7))
    hint = "move: up/down or W/S    surge: SPACE    wrath: X    pause: P    quit: Q"
    stdscr.addstr(h - 1, 0, hint[:w - 1], curses.color_pair(7) | curses.A_DIM)
    if paused and not game.game_over:
        msg = " PAUSED - press P to resume "
        stdscr.addstr(h // 2, max(0, w // 2 - len(msg) // 2), msg,
                      curses.color_pair(6) | curses.A_REVERSE)


def center_text(stdscr, y, text, attr=0):
    h, w = stdscr.getmaxyx()
    x = max(0, w // 2 - len(text) // 2)
    try:
        stdscr.addstr(y, x, text[:w - x - 1], attr)
    except curses.error:
        pass


def title_screen(stdscr):
    stdscr.clear()
    h, w = stdscr.getmaxyx()
    y = max(1, h // 2 - 12)
    for line in TITLE_ART:
        center_text(stdscr, y, line, curses.color_pair(1) | curses.A_BOLD)
        y += 1
    y += 1
    for line in STORY:
        center_text(stdscr, y, line, curses.color_pair(7))
        y += 1
    y += 1
    center_text(stdscr, y, "Controls: UP/DOWN or W/S to swim, SPACE to surge,",
                curses.color_pair(7) | curses.A_DIM)
    center_text(stdscr, y + 1, "X to unleash your wrath when the meter is full, Q to quit",
                curses.color_pair(7) | curses.A_DIM)
    center_text(stdscr, y + 3, "-- press any key to begin --",
                curses.color_pair(6) | curses.A_BOLD | curses.A_BLINK)
    stdscr.refresh()
    stdscr.getch()


def game_over_screen(stdscr, game, best):
    h, w = stdscr.getmaxyx()
    stdscr.clear()
    y = h // 2 - 4
    center_text(stdscr, y, "THE RIVER IS TAMED", curses.color_pair(4) | curses.A_BOLD)
    center_text(stdscr, y + 2, "The trash reached the estuary. Your waters run still.",
                curses.color_pair(7))
    center_text(stdscr, y + 4, "Final score: {}".format(game.score),
                curses.color_pair(6) | curses.A_BOLD)
    center_text(stdscr, y + 5, "Best score:  {}".format(best), curses.color_pair(7))
    center_text(stdscr, y + 6, "Trash cleansed: {}   Breaches: {}".format(
        game.cleansed, game.breaches), curses.color_pair(7) | curses.A_DIM)
    center_text(stdscr, y + 8, "R to rise again, Q to rest", curses.color_pair(7))
    stdscr.refresh()


def play(stdscr, best):
    h, w = stdscr.getmaxyx()
    game = GameState(w, h, seed=None)
    paused = False
    last = time.time()
    stdscr.nodelay(True)
    while True:
        ch = stdscr.getch()
        if ch == curses.KEY_UP or ch in (ord("w"), ord("W")):
            game.move_spirit(-1)
        elif ch == curses.KEY_DOWN or ch in (ord("s"), ord("S")):
            game.move_spirit(1)
        elif ch == ord(" "):
            game.surge()
        elif ch in (ord("x"), ord("X")):
            game.unleash_wrath()
        elif ch in (ord("p"), ord("P")):
            paused = not paused
        elif ch in (ord("q"), ord("Q")):
            return game.score, False

        if game.game_over:
            if game.score > best:
                best = game.score
                save_best(best)
            game_over_screen(stdscr, game, best)
            stdscr.nodelay(False)
            key = stdscr.getch()
            stdscr.nodelay(True)
            if key in (ord("r"), ord("R")):
                game = GameState(w, h, seed=None)
                paused = False
                last = time.time()
            elif key in (ord("q"), ord("Q"), 27):
                return game.score, False
            continue

        now = time.time()
        if now - last >= TICK_SECONDS:
            if not paused:
                game.tick()
                if game.score > best:
                    best = game.score
            draw(stdscr, game, best, paused)
            stdscr.refresh()
            last = now
        time.sleep(0.005)


def main(stdscr):
    curses.curs_set(0)
    init_colors()
    h, w = stdscr.getmaxyx()
    if w < MIN_W or h < MIN_H:
        stdscr.addstr(0, 0, "Riverside Wrath needs a terminal of at least "
                            "{}x{} (yours is {}x{}).".format(MIN_W, MIN_H, w, h))
        stdscr.addstr(2, 0, "Enlarge the window and press any key.")
        stdscr.refresh()
        stdscr.getch()
        return
    best = load_best()
    title_screen(stdscr)
    play(stdscr, best)


def run():
    try:
        curses.wrapper(main)
    except curses.error:
        print("Riverside Wrath needs a real terminal (curses could not start).")


if __name__ == "__main__":
    run()
