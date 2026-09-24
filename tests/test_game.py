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
        g.move_spirit(dy=-1)
    assert g.spirit_y == PLAY_TOP
    for _ in range(1000):
        g.move_spirit(dy=1)
    assert g.spirit_y == g.play_bottom


def test_spirit_horizontal_movement_clamped_to_river():
    g = GameState(seed=7)
    for _ in range(1000):
        g.move_spirit(dx=-1)
    assert g.spirit_x == g.river_left, "spirit should stop at the west bank"
    for _ in range(1000):
        g.move_spirit(dx=1)
    assert g.spirit_x == g.river_right, "spirit should stop at the east bank"
    # combined movement
    g2 = GameState(seed=7)
    start_x, start_y = g2.spirit_x, g2.spirit_y
    g2.move_spirit(dx=2, dy=-3)
    assert g2.spirit_x == start_x + 2
    assert g2.spirit_y == start_y - 3


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
    assert "difficulty" in buf.getvalue().lower(), "help should mention difficulty"


def test_difficulty_affects_spawn_rate():
    from riverside_wrath.game import DIFFICULTIES
    calm = GameState(seed=1, difficulty="calm")
    raging = GameState(seed=1, difficulty="raging")
    # calm should have longer spawn interval than raging at same level
    calm.spawn_timer = 1
    raging.spawn_timer = 1
    calm.tick()
    raging.tick()
    assert calm.spawn_timer > raging.spawn_timer, \
        "calm should spawn slower than raging"


def test_difficulty_affects_damage():
    calm = GameState(seed=1, difficulty="calm")
    raging = GameState(seed=1, difficulty="raging")
    calm_dmg = calm._breach_damage("trash")
    raging_dmg = raging._breach_damage("trash")
    assert raging_dmg > calm_dmg, "raging should hit harder than calm"
    # sludge should always hurt more than trash at same difficulty
    assert calm._breach_damage("sludge") > calm_dmg


def test_level_progress():
    g = GameState(seed=1)
    g.score = 0
    assert g.level_progress() == 0.0
    g.score = 125
    assert 0.4 < g.level_progress() < 0.6, "125/250 should be ~50%"
    g.score = 250
    # level recalculates on tick
    g.tick()
    assert g.level == 2
    assert g.score_to_next_level() == 250


def test_trash_near_estuary_warning():
    g = GameState(seed=1)
    g.spawn_timer = 10 ** 9
    assert g.trash_near_estuary() == 0
    g.trash.append({"x": 10, "y": g.play_bottom, "cd": 5, "kind": "trash"})
    g.trash.append({"x": 11, "y": g.play_bottom - 5, "cd": 5, "kind": "trash"})
    assert g.trash_near_estuary(threshold=3) == 1, "only one trash near edge"


def test_max_combo_tracked():
    g = GameState(seed=7)
    for _ in range(5):
        g._cleanse_trash("trash")
        g.combo_timer = g.COMBO_WINDOW  # keep the chain alive
    assert g.max_combo >= 5
    # combo can reset but the max stays
    g.combo = 0
    assert g.max_combo >= 5


def test_droplet_pickup_restores_purity():
    g = GameState(seed=7)
    g.purity = 50
    g.droplets.append({"x": g.spirit_x, "y": g.spirit_y, "cd": 1})
    before = g.score
    g._check_droplet_pickup()
    assert g.droplets == []
    assert g.purity == 60
    assert g.score == before + 15
    assert g.droplets_collected == 1


def test_droplet_pickup_capped_at_full_purity():
    g = GameState(seed=7)
    g.purity = 95
    g.droplets.append({"x": g.spirit_x + 1, "y": g.spirit_y, "cd": 1})
    g._check_droplet_pickup()
    assert g.purity == 100


def test_droplet_reaching_estuary_is_harmless():
    g = GameState(seed=7)
    g.purity = 80
    g.droplets.append({"x": g.river_left, "y": g.play_bottom, "cd": 1})
    g.tick()  # steps the droplet past the play area
    assert g.droplets == []
    assert g.purity == 80, "expired droplets should not damage purity"
    assert g.breaches == 0


def test_surge_collects_nearby_droplets():
    g = GameState(seed=7)
    g.purity = 50
    g.droplets.append({"x": g.spirit_x + 1, "y": g.spirit_y, "cd": 1})
    assert g.surge() is True
    assert g.droplets == []
    assert g.purity == 60


def test_droplets_spawn_over_time():
    g = GameState(seed=7)
    g.droplet_timer = 1
    g.tick()
    assert len(g.droplets) == 1
    assert g.droplets[0]["y"] in (PLAY_TOP, PLAY_TOP + 1)


def test_reset_restores_initial_state():
    g = GameState(seed=42)
    g.score = 500
    g.purity = 30
    g.wrath = 80
    g.trash.append({"x": 10, "y": 10, "cd": 5, "kind": "trash"})
    g.polluters.append({"x": 5, "y": 5, "side": 1, "kind": "walker",
                        "state": "in", "t": 0})
    g.tick_count = 99
    g.reset()
    assert g.score == 0
    assert g.purity == 100
    assert g.wrath == 0
    assert g.trash == []
    assert g.polluters == []
    assert g.tick_count == 0
    assert g.game_over is False
    assert g.level == 1
    # dimensions survive the reset
    assert g.spirit_x == g.width // 2


def test_reset_replays_seed():
    first = GameState(seed=123)
    for _ in range(30):  # long enough for spawns to consume RNG
        first.tick()
    snapshot = (first.spirit_x, first.spirit_y, len(first.trash),
                len(first.polluters), first.score)
    assert len(first.polluters) > 0, "test needs spawns to exercise the RNG"
    first.reset()
    for _ in range(30):
        first.tick()
    assert (first.spirit_x, first.spirit_y, len(first.trash),
            len(first.polluters), first.score) == snapshot, \
        "reset should replay the same seed"


def test_partition_splits_correctly():
    yes, no = GameState._partition([1, 2, 3, 4], lambda n: n % 2 == 0)
    assert yes == [2, 4]
    assert no == [1, 3]
    yes, no = GameState._partition([], lambda n: True)
    assert yes == [] and no == []


def test_points_per_level_drives_level_ups():
    g = GameState(seed=1)
    step = GameState.POINTS_PER_LEVEL
    g.score = step - 1
    g.tick()
    assert g.level == 1
    assert g.score_to_next_level() == 1
    g.score = step
    g.tick()
    assert g.level == 2
    assert g.score_to_next_level() == step
    assert g.level_progress() == 0.0


if __name__ == "__main__":
    for name, fn in sorted(
            [(k, v) for k, v in globals().items() if k.startswith("test_")]):
        check(name, fn)
    print("\n{} passed, {} failed".format(len(PASS), len(FAIL)))
    sys.exit(1 if FAIL else 0)
