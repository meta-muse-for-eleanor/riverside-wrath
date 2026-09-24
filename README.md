# riverside-wrath

**Riverside Wrath** — a terminal game of river vengeance.

You are the ancient spirit of the riverside. For centuries you watched the
town grow along your banks. Now polluters choke your waters with their trash,
and your patience is spent.

Cleanse the river with your surges. Let your wrath build. When it peaks —
unleash the flood.

## Play

Requires Python 3 and a terminal (uses `curses`, ships with Python on
macOS/Linux; needs at least an 80x24 window... 70x22 minimum, really).

```sh
python3 -m riverside_wrath
```

No dependencies beyond the standard library.

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
- Trash drifts downstream. If it reaches the estuary, your **purity** drops.
  At zero purity, the river is tamed — game over.
- **Surges** destroy trash in a radius and send polluters fleeing. Every
  cleanse feeds your **wrath** meter.
- At full wrath, press **X** to call the **flood**: it sweeps the whole river
  clean and restores some purity.
- Score milestones raise your **level**, and the polluters only get bolder.

Your best score is kept in `~/.riverside-wrath-best`.

## Layout

```
riverside-wrath/
├── riverside_wrath/
│   ├── __init__.py      # package blurb
│   ├── __main__.py      # curses front-end (python3 -m riverside_wrath)
│   └── game.py          # pure game logic, no curses dependency
└── tests/
    └── test_game.py     # headless tests: python3 tests/test_game.py
```

## License

See [LICENSE](LICENSE).
