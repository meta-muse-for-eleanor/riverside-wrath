"""Curses front-end for Riverside Wrath.

Run with:  python3 -m riverside_wrath
"""

import curses
import json
import os
import sys
import time

from . import __version__
from .game import GameState, PLAY_TOP

BEST_FILE = os.path.expanduser("~/.riverside-wrath-best")
TICK_SECONDS = 0.08
MIN_W, MIN_H = 70, 22
MAX_SCORES = 5

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


def load_scores():
    """Load {"best": int, "scores": [{"name", "score"}]}; tolerates the legacy int file."""
    try:
        with open(BEST_FILE) as fh:
            raw = fh.read().strip()
    except OSError:
        return {"best": 0, "scores": []}
    try:
        return {"best": int(raw), "scores": []}
    except ValueError:
        pass
    try:
        data = json.loads(raw)
        return {"best": int(data.get("best", 0)),
                "scores": data.get("scores", [])[:MAX_SCORES]}
    except (ValueError, AttributeError):
        return {"best": 0, "scores": []}


def save_scores(data):
    try:
        with open(BEST_FILE, "w") as fh:
            json.dump(data, fh)
    except OSError:
        pass


def qualifies(data, score):
    return score > 0 and (len(data["scores"]) < MAX_SCORES
                          or score > data["scores"][-1]["score"])


def record_score(data, name, score):
    data["scores"].append({"name": name[:3].upper() or "YOU", "score": score})
    data["scores"].sort(key=lambda s: s["score"], reverse=True)
    data["scores"] = data["scores"][:MAX_SCORES]
    data["best"] = max(data["best"], score)
    save_scores(data)


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
    curses.init_pair(8, curses.COLOR_MAGENTA, -1)                 # sludge


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
    # trash ("*") and sludge ("#", slower, hurts more)
    for t in game.trash:
        if 0 <= t["y"] < h and 0 <= t["x"] < w:
            if t["kind"] == "sludge":
                stdscr.addch(t["y"], t["x"], "#", curses.color_pair(8) | curses.A_BOLD)
            else:
                stdscr.addch(t["y"], t["x"], "*", curses.color_pair(5) | curses.A_BOLD)
    # polluters ("P") and dumpers ("D", slower, dump triple)
    for p in game.polluters:
        if 0 <= p["y"] < h and 0 <= p["x"] < w:
            ch = "D" if p["kind"] == "dumper" else "P"
            stdscr.addch(p["y"], p["x"], ch, curses.color_pair(4) | curses.A_BOLD)
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
    elif game.combo >= 2:
        status += "  COMBO x{}".format(game.combo)
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


def game_over_screen(stdscr, game, data):
    stdscr.clear()
    h, w = stdscr.getmaxyx()
    y = max(1, h // 2 - 7)
    center_text(stdscr, y, "THE RIVER IS TAMED", curses.color_pair(4) | curses.A_BOLD)
    center_text(stdscr, y + 2, "The trash reached the estuary. Your waters run still.",
                curses.color_pair(7))
    center_text(stdscr, y + 4, "Final score: {}".format(game.score),
                curses.color_pair(6) | curses.A_BOLD)
    center_text(stdscr, y + 5, "Trash cleansed: {}   Breaches: {}".format(
        game.cleansed, game.breaches), curses.color_pair(7) | curses.A_DIM)
    y += 7
    center_text(stdscr, y, "-- HALL OF WRATH --", curses.color_pair(5) | curses.A_BOLD)
    for i, entry in enumerate(data["scores"][:MAX_SCORES], 1):
        center_text(stdscr, y + i, "{}. {}  {:>6}".format(i, entry["name"], entry["score"]),
                    curses.color_pair(7))
    if not data["scores"]:
        center_text(stdscr, y + 1, "(no legends yet)", curses.color_pair(7) | curses.A_DIM)
    center_text(stdscr, y + MAX_SCORES + 2, "R to rise again, Q to rest", curses.color_pair(7))
    stdscr.refresh()


def prompt_initials(stdscr):
    """Ask for 3 initials for the high-score table. Returns a short string."""
    h, w = stdscr.getmaxyx()
    y = max(1, h // 2 + 6)
    prompt = "A new legend! Your initials: "
    x = max(0, w // 2 - len(prompt) // 2 - 2)
    stdscr.nodelay(False)
    curses.echo()
    try:
        stdscr.addstr(y, x, prompt, curses.color_pair(6) | curses.A_BOLD)
        stdscr.refresh()
        raw = stdscr.getstr(y, x + len(prompt), 3)
        name = raw.decode("utf-8", errors="replace").strip()
    except curses.error:
        name = ""
    finally:
        curses.noecho()
        stdscr.nodelay(True)
    return name or "YOU"


def play(stdscr, data):
    h, w = stdscr.getmaxyx()
    game = GameState(w, h, seed=None)
    paused = False
    prev_breaches = 0
    last = time.time()
    stdscr.nodelay(True)
    while True:
        ch = stdscr.getch()
        if ch == curses.KEY_UP or ch in (ord("w"), ord("W")):
            game.move_spirit(-1)
        elif ch == curses.KEY_DOWN or ch in (ord("s"), ord("S")):
            game.move_spirit(1)
        elif ch == ord(" "):
            if game.surge():
                _beep()
        elif ch in (ord("x"), ord("X")):
            if game.unleash_wrath():
                _beep()
                _flash()
        elif ch in (ord("p"), ord("P")):
            paused = not paused
        elif ch in (ord("q"), ord("Q")):
            return

        if game.game_over:
            if qualifies(data, game.score):
                draw(stdscr, game, data["best"], paused)
                name = prompt_initials(stdscr)
                record_score(data, name, game.score)
            game_over_screen(stdscr, game, data)
            stdscr.nodelay(False)
            key = stdscr.getch()
            stdscr.nodelay(True)
            if key in (ord("r"), ord("R")):
                game = GameState(w, h, seed=None)
                paused = False
                prev_breaches = 0
                last = time.time()
            elif key in (ord("q"), ord("Q"), 27):
                return
            continue

        now = time.time()
        if now - last >= TICK_SECONDS:
            if not paused:
                game.tick()
                if game.breaches > prev_breaches:
                    prev_breaches = game.breaches
                    _flash()
                if game.score > data["best"]:
                    data["best"] = game.score
            draw(stdscr, game, data["best"], paused)
            stdscr.refresh()
            last = now
        time.sleep(0.005)


def _beep():
    try:
        curses.beep()
    except curses.error:
        pass


def _flash():
    try:
        curses.flash()
    except curses.error:
        pass


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
    best = load_scores()
    title_screen(stdscr)
    play(stdscr, best)


def run(argv=None):
    args = sys.argv[1:] if argv is None else argv
    if "-V" in args or "--version" in args:
        print("riverside-wrath {}".format(__version__))
        return
    if "-h" in args or "--help" in args:
        print("riverside-wrath {} - a terminal game of river vengeance".format(__version__))
        print()
        print(__doc__.strip())
        print()
        print("usage: riverside-wrath [--help] [--version]")
        print("   or: python3 -m riverside_wrath [--help] [--version]")
        return
    try:
        curses.wrapper(main)
    except curses.error:
        print("Riverside Wrath needs a real terminal (curses could not start).")


if __name__ == "__main__":
    run()
