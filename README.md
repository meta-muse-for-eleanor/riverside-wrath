# riverside-wrath

**Riverside Wrath** — a terminal game of river vengeance.

You are the ancient spirit of the riverside. For centuries you watched the
town grow along your banks. Now polluters choke your waters with their trash,
and your patience is spent.

Cleanse the river with your surges. Let your wrath build. When it peaks —
unleash the flood.

## Play

Requires Python 3.8+ and a terminal (uses `curses`, ships with Python on
macOS/Linux; needs at least an 80x24 window... 70x22 minimum, really).

```sh
python3 -m riverside_wrath
```

No dependencies beyond the standard library.

### Options

```sh
python3 -m riverside_wrath --difficulty raging --seed 42
riverside-wrath --difficulty calm   # a gentler river
```

| Flag | Description |
| ---- | ----------- |
| `--difficulty {calm,normal,raging}` | Game difficulty (default: `normal`). Calm spawns slower and hits softer; raging spawns faster, hits harder, and attracts more dumpers. |
| `--seed N` | Random seed for reproducible runs. Share a seed to challenge a friend on the same river. |

## Install

```sh
pip install .
riverside-wrath          # same game, as a command
riverside-wrath --help   # usage
```

## Controls

| Key | Action |
| --- | ------ |
| ↑ / ↓ or W / S | Swim up and down the river |
| SPACE | Surge — cleanse nearby trash, scare off polluters |
| X | Unleash your wrath (when the meter is full) |
| P | Pause |
| Q | Quit |
| R | Rise again (after game over) |

## How it works

- **Polluters (P)** wander in from the banks and toss **trash (\*)** into the water.
- **Dumpers (D)** are slower but meaner: they unload a whole column of trash
  and are worth double points when scared off.
- **Sludge (#)** drifts in with the trash — slower, but a breach costs double
  purity. Cleansing it pays double.
- Trash drifts downstream. If it reaches the estuary, your **purity** drops
  (and your combo breaks). At zero purity, the river is tamed — game over.
- **Surges** destroy trash in a radius and send polluters fleeing. Every
  cleanse feeds your **wrath** meter.
- Chain cleanses quickly to build a **combo** multiplier (up to x8).
- At full wrath, press **X** to call the **flood**: it sweeps the whole river
  clean and restores some purity.
- Score milestones raise your **level**, and the polluters only get bolder.
  The HUD shows your progress to the next level.
- Trash near the estuary **blinks** as a warning — don't let it through!
- The screen flashes when trash breaches, and your top 5 scores live on in
  the **Hall of Wrath** (`~/.riverside-wrath-best`).

## Layout

```
riverside-wrath/
├── pyproject.toml       # packaging: pip install . gives the riverside-wrath command
├── riverside_wrath/
│   ├── __init__.py      # package blurb, __version__
│   ├── __main__.py      # curses front-end (python3 -m riverside_wrath)
│   └── game.py          # pure game logic, no curses dependency
└── tests/
    └── test_game.py     # headless tests: python3 tests/test_game.py
```

## License

See [LICENSE](LICENSE).
