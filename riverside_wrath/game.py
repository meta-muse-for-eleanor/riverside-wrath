"""Core game logic for Riverside Wrath.

Pure simulation with no curses dependency, so it can be unit-tested
headlessly. Coordinates: x in [0, width), y in [0, height).
Rows 0-1 and the final two rows are reserved for HUD; the play area
runs from PLAY_TOP to play_bottom inclusive.
"""

import random

PLAY_TOP = 2


class GameState:
    SURGE_RADIUS = 3
    SURGE_COOLDOWN_TICKS = 14
    TRASH_SCORE = 10
    SLUDGE_SCORE = 20
    POLLUTER_SCORE = 25
    DUMPER_SCORE = 50
    WRATH_PER_TRASH = 5
    WRATH_PER_SLUDGE = 8
    WRATH_PER_POLlUTER = 10
    WRATH_PER_DUMPER = 20
    BREACH_DAMAGE = 10
    SLUDGE_DAMAGE = 20
    COMBO_WINDOW = 40  # ticks a combo stays alive between cleanses
    MAX_COMBO = 8
    WRATH_PER_TRASH = 5
    WRATH_PER_POLlUTER = 10
    MAX_POLLUTERS = 6

    def __init__(self, width=80, height=24, seed=None):
        self.width = width
        self.height = height
        self.rng = random.Random(seed)
        self.play_bottom = height - 3
        mid = width // 2
        self.river_left = mid - 6
        self.river_right = mid + 6
        self.spirit_x = mid
        self.spirit_y = (PLAY_TOP + self.play_bottom) // 2
        self.trash = []        # {"x": int, "y": int, "cd": int}
        self.polluters = []    # {"x","y","side","state","t"}
        self.rings = []        # surge visuals: {"y": int, "ttl": int}
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

    # ------------------------------------------------------------------
    # player actions
    # ------------------------------------------------------------------
    def move_spirit(self, dy):
        """Move the spirit vertically, clamped to the play area."""
        self.spirit_y = max(PLAY_TOP, min(self.play_bottom, self.spirit_y + dy))

    def surge(self):
        """Send a cleansing surge from the spirit. Returns True if fired."""
        if self.game_over or self.surge_cooldown > 0:
            return False
        self.surge_cooldown = self.SURGE_COOLDOWN_TICKS
        self.rings.append({"y": self.spirit_y, "ttl": 5})
        r2 = self.SURGE_RADIUS ** 2
        pr2 = (self.SURGE_RADIUS + 2) ** 2
        kept_trash = []
        for t in self.trash:
            if self._dist2(t["x"], t["y"], self.spirit_x, self.spirit_y) <= r2:
                self._cleanse_trash(t["kind"])
            else:
                kept_trash.append(t)
        self.trash = kept_trash
        kept_polluters = []
        for p in self.polluters:
            if self._dist2(p["x"], p["y"], self.spirit_x, self.spirit_y) <= pr2:
                if p["kind"] == "dumper":
                    self.score += self.DUMPER_SCORE
                    self._add_wrath(self.WRATH_PER_DUMPER)
                else:
                    self.score += self.POLLUTER_SCORE
                    self._add_wrath(self.WRATH_PER_POLlUTER)
            else:
                kept_polluters.append(p)
        self.polluters = kept_polluters
        return True

    def unleash_wrath(self):
        """Unleash the flood. Returns True if the wrath was ready."""
        if self.game_over or self.wrath < 100:
            return False
        self.score += sum(10 if t["kind"] == "sludge" else 5 for t in self.trash)
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
    def tick(self):
        """Advance the simulation by one tick."""
        if self.game_over:
            return
        self.tick_count += 1
        self.level = 1 + self.score // 250
        if self.surge_cooldown > 0:
            self.surge_cooldown -= 1
        if self.combo_timer > 0:
            self.combo_timer -= 1
            if self.combo_timer == 0:
                self.combo = 0

        self.spawn_timer -= 1
        if self.spawn_timer <= 0:
            self._spawn_polluter()
            self.spawn_timer = max(10, 34 - self.level * 3)

        self._step_polluters()
        self._step_trash()

        for ring in self.rings:
            ring["ttl"] -= 1
        self.rings = [r for r in self.rings if r["ttl"] > 0]
        if self.flood_ttl > 0:
            self.flood_ttl -= 1

        if self.purity <= 0:
            self.purity = 0
            self.game_over = True

    # ------------------------------------------------------------------
    # internals
    # ------------------------------------------------------------------
    @staticmethod
    def _dist2(ax, ay, bx, by):
        return (ax - bx) ** 2 + (ay - by) ** 2

    def _cleanse_trash(self, kind):
        """Score a cleanse. Chained cleanses build a combo multiplier."""
        if self.combo_timer > 0:
            self.combo = min(self.MAX_COMBO, self.combo + 1)
        else:
            self.combo = 1
        self.combo_timer = self.COMBO_WINDOW
        if kind == "sludge":
            self.score += self.SLUDGE_SCORE * self.combo
            self._add_wrath(self.WRATH_PER_SLUDGE)
        else:
            self.score += self.TRASH_SCORE * self.combo
            self._add_wrath(self.WRATH_PER_TRASH)
        self.cleansed += 1

    def _add_wrath(self, n):
        self.wrath = min(100, self.wrath + n)

    def _trash_speed(self):
        return max(2, 6 - self.level)

    def _spawn_polluter(self):
        if len(self.polluters) >= self.MAX_POLLUTERS:
            return
        side = self.rng.choice((-1, 1))  # -1: west bank, +1: east bank
        kind = "dumper" if self.rng.random() < 0.2 else "walker"
        x = 2 if side < 0 else self.width - 3
        y = self.rng.randint(PLAY_TOP, self.play_bottom)
        self.polluters.append({"x": x, "y": y, "side": side, "kind": kind,
                               "state": "in", "t": 0})

    def _edge_x(self, side):
        return self.river_left - 1 if side < 0 else self.river_right + 1

    def _step_polluters(self):
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

    def _toss_trash(self, p):
        kind = "sludge" if self.rng.random() < 0.15 else "trash"
        speed = int(self._trash_speed() * 1.5) if kind == "sludge" else self._trash_speed()
        x = self.river_left + 1 if p["side"] < 0 else self.river_right - 1
        if p["kind"] == "dumper":
            for dy in (-1, 0, 1):  # dumpers unload a whole column
                y = max(PLAY_TOP, min(self.play_bottom, p["y"] + dy))
                self.trash.append({"x": x, "y": y, "cd": speed, "kind": kind})
        else:
            self.trash.append({"x": x, "y": p["y"], "cd": speed, "kind": kind})

    def _step_trash(self):
        kept = []
        for t in self.trash:
            t["cd"] -= 1
            if t["cd"] <= 0:
                t["y"] += 1
                t["cd"] = self._trash_speed()
            if t["y"] > self.play_bottom:
                self.purity -= self.SLUDGE_DAMAGE if t["kind"] == "sludge" else self.BREACH_DAMAGE
                self.breaches += 1
                self.combo = 0
                self.combo_timer = 0
            else:
                kept.append(t)
        self.trash = kept
