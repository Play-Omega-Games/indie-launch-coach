# Indie Launch Coach

Omega Games' open launch playbook for small game teams. It powers the 🚀 Indie Launch Coach Grok Bot template: answer a few questions and get a dated launch plan for Steam and other stores, with platform deadlines, weekly tasks and draft templates. The coach drafts; you post and send.

## What is here
- `playbook/`: the eight launch phases, the essentials track, a glossary.
- `data/`: task library, platform gates with official source links, phases, platforms, genres, content prompts, official event pages and a dated event snapshot.
- `templates/`: draft formats for store copy, press kit, outreach, posts, run sheet and more.
- `schema/`: shapes of the owner profile, plan, numbers log and outreach list.
- `scripts/`: `build_plan.py` (answers to dated plan), `check_links.py`, `check_events.py`, `lint_text.py`.
- `tests/`: ten sample profiles and plan checks.

## Use
```
python3 scripts/build_plan.py --profile tests/personas/a_steam_8_months_no_page.json --today 2026-10-26 --summary
python3 -m unittest discover -s tests -v
python3 scripts/check_links.py --quiet
python3 scripts/check_events.py
python3 scripts/lint_text.py
```
Bots load data from `https://raw.githubusercontent.com/Play-Omega-Games/indie-launch-coach/main/data/<file>.json`. Python 3 standard library only.

Platform rules change. Each gate links its official page, and `check_events.py` compares the snapshot with the live Steam event pages. Event dates were last verified on the date in `data/events_snapshot.json`.

Rule-of-thumb advice in this repo is labeled as a guideline. There are no sales predictions or benchmarks here: your own numbers are the ones that count.

Questions or ideas: john@playomega.games

License: content CC0 1.0, code MIT. See `LICENSE`.
