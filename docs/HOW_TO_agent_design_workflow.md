# Agent design workflow (GUI / responsive UI)

This document describes a **repeatable, iteration-first** pattern for steering an agent when changing the application GUI. The goal is small, reviewable steps: confirm understanding visually, then fix in thin slices, then loop with new screenshots.

---

## When to use it

- You have **screenshots** of the current PySide6 (or other) UI.
- The change is **visual or layout-related** and benefits from the **responsive-frontend-builder** skill (or equivalent visual-matching instructions).
- You want the agent to **not** ship a large redesign in one shot.

---

## Skills and conventions

| Item | Purpose |
|------|--------|
| **responsive-frontend-builder** | Turn screenshots and design notes into UI that matches layout, spacing, and conventions of this repo (`src/gui/settings.py`, `elements.py`, etc.). |
| **Image generation** (when applicable) | Have the agent produce a **target mock** so intent is explicit before code changes. Replace the placeholder below with your project’s image skill name if different. |

---

## Phase 1 — First prompt (understand + target picture)

Use a prompt in this shape (fill in `<problem>` and adjust the image skill placeholder):

```text
Use the responsive-frontend-builder skill.

I've attached screenshot(s) of the current application GUI. The problem we must work on is: <problem>.

Try to solve this with minimal fixes. We will iterate; the first update does not need to be heavy.

First, to confirm you've understood the goal, produce an image (use <image-generation-skill>) showing what we must achieve.
```

**Intent**

- Locks the agent to **repo-native** UI patterns and **small** diffs.
- Forces a **shared visual target** before touching much code.

---

## Phase 2 — Second prompt (review mock + light fixes)

After the agent returns the target image(s), use:

```text
Review the image(s) you produced. Sticking to the rules about small updates and iterating, apply the necessary fixes to the GUI.
```

**Intent**

- Ties implementation to the **approved direction** without expanding scope.

---

## Phase 3 and onward — Iterate

For each round:

```text
Here are screenshot(s) of the current state after your changes.

- What's still wrong (specific problems)?
- What already matches the goal?

Continue with minimal, targeted fixes; we'll iterate again if needed.
```

**Intent**

- **Tight feedback loop**: screenshots + explicit pass/fail per area.
- Keeps each step **reviewable** and easy to roll back.

---

## Principles (keep these explicit to the agent)

1. **Minimal first change** — prefer one layout/widget issue per iteration when possible.
2. **Match project standards** — colors, spacing, and components from existing GUI modules; no one-off magic numbers unless added to shared settings.
3. **Evidence** — agent should explain what changed and **why**, against the last screenshot set.
4. **Stop for ambiguity** — if the mock and the screenshot disagree, clarify before a large edit.

---

## Checklist before closing a design round

- [ ] Target image (or written spec) agreed for the desired end state.
- [ ] At least one **after** screenshot matches the critical parts of that target.
- [ ] No unrelated files or refactors in the same change set.

---

*File: agent design workflow for GUI work — iteration over single large prompts.*
