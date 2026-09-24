"""Core game logic for Riverside Wrath.

Pure simulation with no curses dependency, so it can be unit-tested
headlessly. Coordinates: x in [0, width), y in [0, height).
Rows 0-1 and the final two rows are reserved for HUD; the play area
runs from PLAY_TOP to play_bottom inclusive.
"""

from __future__ import annotations

import random
from typing import Dict, List, Literal, Union

__all__ = ["GameState", "PLAY_TOP", "DIFFICULTIES", "DifficultyName"]

PLAY_TOP = 2

# Difficulty presets: spawn interval base, trash speed bonus, breach damage multiplier
DifficultyName = Literal["calm", "normal", "raging"]

DIFFICULTIES: Dict[DifficultyName, Dict[str, Union[int, float]]] = {
    "calm": {"spawn_base": 40, "speed_bonus": 1, "damage_mult": 0.7, "max_polluters": 4},
    "normal": {"spawn_base": 34, "speed_bonus": 0, "damage_mult": 1.0, "max_polluters": 6},
    "raging": {"spawn_base": 26, "speed_bonus": -1, "damage_mult": 1.4, "max_polluters": 8},
}


class GameState:
    SURGE_RADIUS = 3
    SURGE_COOLDOWN_TICKS = 14
    TRASH_SCORE = 10
    SLUDGE_SCORE = 20
    POLLUTER_SCORE = 25
    DUMPER_SCORE = 50
    WRATH_PER_TRASH = 5
    WRATH_PER_SLUDGE = 8
    WRATH_PER_POLLUTER = 10
    WRATH_PER_DUMPER = 20
    BREACH_DAMAGE = 10
    SLUDGE_DAMAGE = 20
    COMBO_WINDOW = 40  # ticks a combo stays alive between cleanses
    MAX_COMBO = 8
    MAX_POLLUTERS = 6
    POINTS_PER_LEVEL = 250
    DROPLET_PURITY = 10
    DROPLET_SCORE = 15
    DROPLET_WRATH = 5

    def __init__(self, width: int = 80, height: int = 24, seed: int | None = None,
                 difficulty: DifficultyName = "normal"):
        self.width = width
        self.height = height
        self._seed = seed
        self.rng = random.Random(seed)
        self.difficulty: DifficultyName = difficulty
        self._diff = DIFFICULTIES[difficulty]
        self.play_bottom = height - 3
        mid = width // 2
        self.river_left = mid - 6
        self.river_right = mid + 6
        self.reset()

    def reset(self) -> None:
        """Reset mutable game state for a new run, keeping dimensions and seed.

        Re-seeds the RNG so a fixed seed replays the same river.
        """
        self.rng = random.Random(self._seed)
        mid = self.width // 2
        self.spirit_x = mid
        self.spirit_y = (PLAY_TOP + self.play_bottom) // 2
        self.trash: List[Dict] = []        # {"x": int, "y": int, "cd": int, "kind": "trash"|"sludge"}
        self.polluters: List[Dict] = []    # {"x","y","side","state","t"}
        self.rings: List[Dict] = []        # surge visuals: {"y": int, "ttl": int}
        self.flood_ttl = 0
        self.score = 0
        self.purity = 100
        self.wrath = 0
        self.level = 1
        self.tick_count = 0
        self.spawn_timer = 20
        self.surge_cooldown = 0
        self.game_over = False
        self.breaches = 0
        self.cleansed = 0
        self.combo = 0
        self.combo_timer = 0
        self.max_combo = 0
        self.droplets: List[Dict] = []  # pure droplets: {"x": int, "y": int, "cd": int}
        self.droplet_timer = 180
        self.droplets_collected = 0
        # danger: ticks since last breach warning (for UI flash throttling)
        self.danger_flash = 0

    # ------------------------------------------------------------------
    # player actions
    # ------------------------------------------------------------------
    def move_spirit(self, dx: int = 0, dy: int = 0) -> None:
        """Move the spirit, clamped to the river.

        dy moves along the river (the play area), dx moves across it
        (clamped to the river banks). Collects any droplet touched.
        """
        self.spirit_x = max(self.river_left, min(self.river_right, self.spirit_x + dx))
        self.spirit_y = max(PLAY_TOP, min(self.play_bottom, self.spirit_y + dy))
        self._check_droplet_pickup()

    def surge(self) -> bool:
        """Send a cleansing surge from the spirit. Returns True if fired."""
        if self.game_over or self.surge_cooldown > 0:
            return False
        self.surge_cooldown = self.SURGE_COOLDOWN_TICKS
        self.rings.append({"y": self.spirit_y, "ttl": 5})
        r2 = self.SURGE_RADIUS ** 2
        pr2 = (self.SURGE_RADIUS + 2) ** 2

        def within_radius(item, radius2):
            return self._dist2(item["x"], item["y"],
                               self.spirit_x, self.spirit_y) <= radius2

        # Cleanse trash in radius, keep the rest
        hit, self.trash = self._partition(self.trash, lambda t: within_radius(t, r2))
        for t in hit:
            self._cleanse_trash(t["kind"])

        # Scare off polluters in the wider radius
        fled, self.polluters = self._partition(self.polluters,
                                               lambda p: within_radius(p, pr2))
        for p in fled:
            if p["kind"] == "dumper":
                self.score += self.DUMPER_SCORE
                self._add_wrath(self.WRATH_PER_DUMPER)
            else:
                self.score += self.POLLUTER_SCORE
                self._add_wrath(self.WRATH_PER_POLLUTER)

        # A surge also gathers nearby pure droplets
        caught, self.droplets = self._partition(self.droplets,
                                                lambda d: within_radius(d, r2))
        for _ in caught:
            self._collect_droplet()
        return True

    @staticmethod
    def _partition(items, pred):
        """Split items into (matching, non-matching) lists."""
        yes, no = [], []
        for item in items:
            (yes if pred(item) else no).append(item)
        return yes, no

    def unleash_wrath(self) -> bool:
        """Unleash the flood. Returns True if the wrath was ready.

        Flood scoring is deliberately modest (half the base cleanse value)
        — it's a panic button, not a combo engine.
        """
        if self.game_over or self.wrath < 100:
            return False
        self.score += sum(self.SLUDGE_SCORE // 2 if t["kind"] == "sludge"
                          else self.TRASH_SCORE // 2 for t in self.trash)
        self.score += sum(self.DUMPER_SCORE if p["kind"] == "dumper"
                          else self.POLLUTER_SCORE for p in self.polluters)
        self.cleansed += len(self.trash)
        self.trash = []
        self.polluters = []
        self.wrath = 0
        self.purity = min(100, self.purity + 15)
        self.flood_ttl = self.height
        return True

    # ------------------------------------------------------------------
    # simulation
    # ------------------------------------------------------------------
    def tick(self) -> None:
        """Advance the simulation by one tick."""
        if self.game_over:
            return
        self.tick_count += 1
        self.level = 1 + self.score // self.POINTS_PER_LEVEL
        self._decay_timers()
        self._maybe_spawn()

        self._step_polluters()
        self._step_trash()
        self._step_droplets()

        for ring in self.rings:
            ring["ttl"] -= 1
        self.rings = [r for r in self.rings if r["ttl"] > 0]
        if self.flood_ttl > 0:
            self.flood_ttl -= 1

        if self.purity <= 0:
            self.purity = 0
            self.game_over = True

    def _decay_timers(self) -> None:
        """Tick down cooldowns and expire the combo when its window lapses."""
        if self.surge_cooldown > 0:
            self.surge_cooldown -= 1
        if self.combo_timer > 0:
            self.combo_timer -= 1
            if self.combo_timer == 0:
                self.combo = 0
        if self.danger_flash > 0:
            self.danger_flash -= 1

    def _maybe_spawn(self) -> None:
        """Spawn polluters and droplets when their timers run out."""
        self.spawn_timer -= 1
        if self.spawn_timer <= 0:
            self._spawn_polluter()
            self.spawn_timer = self._spawn_interval()

        self.droplet_timer -= 1
        if self.droplet_timer <= 0:
            self._spawn_droplet()
            self.droplet_timer = self.rng.randint(150, 300)

    # ------------------------------------------------------------------
    # internals
    # ------------------------------------------------------------------
    @staticmethod
    def _dist2(ax: int, ay: int, bx: int, by: int) -> int:
        return (ax - bx) ** 2 + (ay - by) ** 2

    def _cleanse_trash(self, kind: str) -> None:
        """Score a cleanse. Chained cleanses build a combo multiplier."""
        if self.combo_timer > 0:
            self.combo = min(self.MAX_COMBO, self.combo + 1)
        else:
            self.combo = 1
        self.combo_timer = self.COMBO_WINDOW
        self.max_combo = max(self.max_combo, self.combo)
        if kind == "sludge":
            self.score += self.SLUDGE_SCORE * self.combo
            self._add_wrath(self.WRATH_PER_SLUDGE)
        else:
            self.score += self.TRASH_SCORE * self.combo
            self._add_wrath(self.WRATH_PER_TRASH)
        self.cleansed += 1

    def _add_wrath(self, n: int) -> None:
        self.wrath = min(100, self.wrath + n)

    def score_to_next_level(self) -> int:
        """Points needed to reach the next level."""
        next_threshold = self.level * self.POINTS_PER_LEVEL
        return max(0, next_threshold - self.score)

    def level_progress(self) -> float:
        """Fraction (0.0-1.0) of progress toward the next level."""
        base = (self.level - 1) * self.POINTS_PER_LEVEL
        return min(1.0, max(0.0, (self.score - base) / self.POINTS_PER_LEVEL))

    def _trash_speed(self) -> int:
        base = max(2, 6 - self.level)
        return max(1, base + int(self._diff["speed_bonus"]))

    def _spawn_interval(self) -> int:
        base = int(self._diff["spawn_base"])
        return max(8, base - self.level * 3)

    def _max_polluters(self) -> int:
        return int(self._diff["max_polluters"])

    def _breach_damage(self, kind: str) -> int:
        base = self.SLUDGE_DAMAGE if kind == "sludge" else self.BREACH_DAMAGE
        return max(1, int(round(base * float(self._diff["damage_mult"]))))

    def _spawn_polluter(self) -> None:
        if len(self.polluters) >= self._max_polluters():
            return
        side = self.rng.choice((-1, 1))  # -1: west bank, +1: east bank
        # Raging rivers attract more dumpers
        dumper_chance = 0.2 + (0.1 if self.difficulty == "raging" else 0.0)
        kind = "dumper" if self.rng.random() < dumper_chance else "walker"
        x = 2 if side < 0 else self.width - 3
        y = self.rng.randint(PLAY_TOP, self.play_bottom)
        self.polluters.append({"x": x, "y": y, "side": side, "kind": kind,
                               "state": "in", "t": 0})

    def _edge_x(self, side: int) -> int:
        return self.river_left - 1 if side < 0 else self.river_right + 1

    def _step_polluters(self) -> None:
        alive = []
        for p in self.polluters:
            if p["state"] == "in":
                p["t"] += 1
                step_every = 3 if p["kind"] == "dumper" else 2
                if p["t"] % step_every == 0:
                    p["x"] += -p["side"]  # walk toward the river
                if p["x"] == self._edge_x(p["side"]):
                    p["state"] = "litter"
                    p["t"] = 10
                alive.append(p)
            elif p["state"] == "litter":
                p["t"] -= 1
                if p["t"] == 7:
                    self._toss_trash(p)
                if p["t"] <= 0:
                    p["state"] = "out"
                    p["t"] = 0
                alive.append(p)
            else:  # "out" - slink back off screen
                p["t"] += 1
                if p["t"] % 2 == 0:
                    p["x"] += p["side"]
                if 0 <= p["x"] < self.width:
                    alive.append(p)
        self.polluters = alive

    def _toss_trash(self, p: Dict) -> None:
        kind = "sludge" if self.rng.random() < 0.15 else "trash"
        speed = int(self._trash_speed() * 1.5) if kind == "sludge" else self._trash_speed()
        x = self.river_left + 1 if p["side"] < 0 else self.river_right - 1
        if p["kind"] == "dumper":
            for dy in (-1, 0, 1):  # dumpers unload a whole column
                y = max(PLAY_TOP, min(self.play_bottom, p["y"] + dy))
                self.trash.append({"x": x, "y": y, "cd": speed, "kind": kind})
        else:
            self.trash.append({"x": x, "y": p["y"], "cd": speed, "kind": kind})

    def _step_trash(self) -> None:
        kept = []
        for t in self.trash:
            t["cd"] -= 1
            if t["cd"] <= 0:
                t["y"] += 1
                t["cd"] = self._trash_speed()
            if t["y"] > self.play_bottom:
                self.purity -= self._breach_damage(t["kind"])
                self.breaches += 1
                self.combo = 0
                self.combo_timer = 0
                self.danger_flash = 6  # trigger UI warning
            else:
                kept.append(t)
        self.trash = kept

    # ------------------------------------------------------------------
    # pure droplets (power-ups)
    # ------------------------------------------------------------------
    def _spawn_droplet(self) -> None:
        x = self.rng.randint(self.river_left, self.river_right)
        self.droplets.append({"x": x, "y": PLAY_TOP, "cd": self._trash_speed()})

    def _collect_droplet(self) -> None:
        """Bank a pure droplet: restore purity, score, feed wrath a little."""
        self.purity = min(100, self.purity + self.DROPLET_PURITY)
        self.score += self.DROPLET_SCORE
        self._add_wrath(self.DROPLET_WRATH)
        self.droplets_collected += 1

    def _check_droplet_pickup(self) -> None:
        """Collect droplets touching the spirit (Chebyshev distance <= 1)."""
        kept = []
        for d in self.droplets:
            if max(abs(d["x"] - self.spirit_x), abs(d["y"] - self.spirit_y)) <= 1:
                self._collect_droplet()
            else:
                kept.append(d)
        self.droplets = kept

    def _step_droplets(self) -> None:
        kept = []
        for d in self.droplets:
            d["cd"] -= 1
            if d["cd"] <= 0:
                d["y"] += 1
                d["cd"] = self._trash_speed()
            # droplets that reach the estuary simply dissolve — no penalty
            if d["y"] <= self.play_bottom:
                kept.append(d)
        self.droplets = kept
        self._check_droplet_pickup()

    def trash_near_estuary(self, threshold: int = 3) -> int:
        """Count trash within `threshold` rows of the estuary. For UI warnings."""
        return sum(1 for t in self.trash if t["y"] >= self.play_bottom - threshold)
