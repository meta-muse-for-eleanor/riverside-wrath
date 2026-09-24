"""Headless tests for the Riverside Wrath game logic.

Run from the repo root:  python3 tests/test_game.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from riverside_wrath.game import GameState, PLAY_TOP

PASS = []
FAIL = []


def check(name, fn):
    try:
        fn()
    except AssertionError as exc:
        FAIL.append((name, str(exc)))
        print("FAIL {}: {}".format(name, exc))
    else:
        PASS.append(name)
        print("ok   {}".format(name))


def test_trash_drifts_and_breaches():
    g = GameState(seed=1)
    g.spawn_timer = 10 ** 9  # no auto-spawns during the test
    g.trash.append({"x": g.spirit_x, "y": g.play_bottom, "cd": 1, "kind": "trash"})
    purity = g.purity
    g.tick()
    assert len(g.trash) == 0, "breached trash should be removed"
    assert g.purity == purity - GameState.BREACH_DAMAGE, "breach should damage purity"
    assert g.breaches == 1


def test_surge_cleanses_nearby_trash():
    g = GameState(seed=2)
    g.trash.append({"x": g.spirit_x, "y": g.spirit_y, "cd": 5, "kind": "trash"})
    g.trash.append({"x": 1, "y": PLAY_TOP, "cd": 5, "kind": "trash"})  # far away
    assert g.surge() is True
    assert len(g.trash) == 1, "only nearby trash should be cleansed"
    assert g.score == GameState.TRASH_SCORE
    assert g.surge_cooldown > 0
    assert g.surge() is False, "surge should be on cooldown"


def test_surge_scares_polluters():
    g = GameState(seed=3)
    g.polluters.append({"x": g.spirit_x + 2, "y": g.spirit_y,
                        "side": -1, "kind": "walker", "state": "in", "t": 0})
    assert g.surge() is True
    assert len(g.polluters) == 0, "nearby polluter should flee"
    assert g.score == GameState.POLLUTER_SCORE
    assert g.wrath > 0, "scaring polluters should feed wrath"


def test_polluter_walks_in_and_litters():
    g = GameState(seed=4)
    g.spawn_timer = 10 ** 9
    p = {"x": 2, "y": 10, "side": -1, "kind": "walker", "state": "in", "t": 0}
    g.polluters.append(p)
    edge = g.river_left - 1
    for _ in range(500):
        g.tick()
        if p["state"] == "litter":
            break
    assert p["state"] == "litter", "polluter should reach the river edge"
    assert p["x"] == edge
    before = len(g.trash)
    for _ in range(30):
        g.tick()
        if len(g.trash) > before:
            break
    assert len(g.trash) > before, "littering polluter should toss trash"


def test_wrath_unleash_clears_everything():
    g = GameState(seed=5)
    g.spawn_timer = 10 ** 9
    g.purity = 60
    g.wrath = 100
    g.trash = [{"x": 10, "y": 10, "cd": 5, "kind": "trash"}, {"x": 12, "y": 12, "cd": 5, "kind": "trash"}]
    g.polluters = [{"x": 5, "y": 5, "side": 1, "kind": "walker", "state": "in", "t": 0}]
    assert g.unleash_wrath() is True
    assert g.trash == [] and g.polluters == []
    assert g.wrath == 0
    assert g.purity == 75, "wrath should restore some purity"
    assert g.flood_ttl > 0, "flood animation should trigger"
    assert g.unleash_wrath() is False, "wrath needs to recharge"


def test_game_over_at_zero_purity():
    g = GameState(seed=6)
    g.spawn_timer = 10 ** 9
    g.purity = 5
    g.trash.append({"x": g.spirit_x, "y": g.play_bottom, "cd": 1, "kind": "trash"})
    g.tick()
    assert g.game_over is True
    assert g.purity == 0
    score = g.score
    g.tick()
    assert g.score == score, "dead rivers do not score"


def test_spirit_movement_clamped():
    g = GameState(seed=7)
    for _ in range(1000):
        g.move_spirit(-1)
    assert g.spirit_y == PLAY_TOP
    for _ in range(1000):
        g.move_spirit(1)
    assert g.spirit_y == g.play_bottom


def test_level_increases_spawn_pressure():
    slow = GameState(seed=8)
    slow.score = 0
    slow.spawn_timer = 1  # fires on the next tick
    slow.tick()
    interval_calm = slow.spawn_timer
    fast = GameState(seed=8)
    fast.score = 1000  # level 5
    fast.spawn_timer = 1
    fast.tick()
    interval_angry = fast.spawn_timer
    assert interval_calm == 31, "level 1 interval should be 31, got {}".format(interval_calm)
    assert interval_angry < interval_calm, "higher level should spawn faster"


def test_combo_multiplies_chained_cleanses():
    g = GameState(seed=9)
    g.spawn_timer = 10 ** 9
    g.trash.append({"x": g.spirit_x, "y": g.spirit_y, "cd": 5, "kind": "trash"})
    assert g.surge() is True
    assert g.score == 10 and g.combo == 1
    g.surge_cooldown = 0  # test-only reset
    g.trash.append({"x": g.spirit_x, "y": g.spirit_y, "cd": 5, "kind": "trash"})
    assert g.surge() is True
    assert g.combo == 2, "chained cleanse should raise the combo"
    assert g.score == 10 + 20, "second cleanse should score double"
    # let the combo window expire
    g.surge_cooldown = 0
    for _ in range(GameState.COMBO_WINDOW + 1):
        g.tick()
    assert g.combo == 0, "combo should expire"
    g.trash.append({"x": g.spirit_x, "y": g.spirit_y, "cd": 5, "kind": "trash"})
    before = g.score
    assert g.surge() is True
    assert g.score == before + 10, "fresh combo should score base points"


def test_breach_resets_combo():
    g = GameState(seed=10)
    g.spawn_timer = 10 ** 9
    g.combo = 3
    g.combo_timer = GameState.COMBO_WINDOW
    g.trash.append({"x": g.spirit_x, "y": g.play_bottom, "cd": 1, "kind": "trash"})
    g.tick()
    assert g.combo == 0 and g.combo_timer == 0, "a breach should break the combo"


def test_dumper_dumps_triple_trash():
    g = GameState(seed=11)
    g.spawn_timer = 10 ** 9
    edge = g.river_left - 1
    g.polluters.append({"x": edge, "y": 10, "side": -1, "kind": "dumper",
                        "state": "litter", "t": 10})
    for _ in range(3):  # toss happens when the litter timer hits 7
        g.tick()
    assert len(g.trash) == 3, "dumper should dump three trash, got {}".format(len(g.trash))
    ys = sorted(t["y"] for t in g.trash)
    assert ys == [9, 10, 11], "dumper trash should fan out vertically"


def test_dumper_scare_worth_more():
    g = GameState(seed=12)
    g.spawn_timer = 10 ** 9
    g.polluters.append({"x": g.spirit_x + 2, "y": g.spirit_y, "side": -1,
                        "kind": "dumper", "state": "in", "t": 0})
    assert g.surge() is True
    assert g.score == GameState.DUMPER_SCORE
    assert g.wrath == GameState.WRATH_PER_DUMPER


def test_sludge_breach_hits_harder():
    g = GameState(seed=13)
    g.spawn_timer = 10 ** 9
    g.trash.append({"x": g.spirit_x, "y": g.play_bottom, "cd": 1, "kind": "sludge"})
    purity = g.purity
    g.tick()
    assert g.purity == purity - GameState.SLUDGE_DAMAGE


def test_sludge_cleanses_for_more():
    g = GameState(seed=14)
    g.spawn_timer = 10 ** 9
    g.trash.append({"x": g.spirit_x, "y": g.spirit_y, "cd": 5, "kind": "sludge"})
    assert g.surge() is True
    assert g.score == GameState.SLUDGE_SCORE
    assert g.wrath == GameState.WRATH_PER_SLUDGE


def test_cli_version_flag_skips_curses():
    import io
    from contextlib import redirect_stdout
    from riverside_wrath import __main__ as front
    from riverside_wrath import __version__
    buf = io.StringIO()
    with redirect_stdout(buf):
        front.run(["--version"])
    assert __version__ in buf.getvalue(), "version flag should print the version"


def test_cli_help_flag_skips_curses():
    import io
    from contextlib import redirect_stdout
    from riverside_wrath import __main__ as front
    buf = io.StringIO()
    with redirect_stdout(buf):
        front.run(["--help"])
    assert "usage" in buf.getvalue().lower(), "help flag should print usage"


if __name__ == "__main__":
    for name, fn in sorted(
            [(k, v) for k, v in globals().items() if k.startswith("test_")]):
        check(name, fn)
    print("\n{} passed, {} failed".format(len(PASS), len(FAIL)))
    sys.exit(1 if FAIL else 0)
