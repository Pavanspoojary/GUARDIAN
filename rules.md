# GUARDIAN Repository Development & Contribution Guidelines

This document outlines the engineering, commit, licensing, and workflow rules for all contributors and autonomous AI agents working in this repository.

---

## 1. Project Identity & Scope
- **Project Name**: GUARDIAN (Advanced Deterministic Human Behaviour & Safety Decision Engine).
- **Core Principle**: Zero probabilistic generative AI, zero LLMs, zero cloud dependencies. Local, offline-first, explainable decision engine.
- **Repository Visibility**: Public.
- **Software License**: PolyForm Noncommercial License 1.0.0 (`LICENSE`).

---

## 2. Commit & Version Control Standards
- **Granular & Frequent Commits**: Break development work into atomic, logical, well-structured commits to reflect clear progress and maintain clean version history on GitHub.
- **Conventional Commits**: Every commit message must use professional semantic prefixes:
  - `feat:` for new capabilities or user-facing changes.
  - `fix:` for bug fixes and corrective patches.
  - `refactor:` for code restructuring without behavioral alterations.
  - `docs:` for documentation and markdown updates.
  - `test:` for test additions or test harness updates.
  - `chore:` for build tooling, dependencies, or configuration changes.
- **Commit Message Quality**:
  - Capitalize imperative summaries (e.g., `feat: rename decision engine to GUARDIAN and update UI branding`).
  - Keep messages descriptive, precise, and professional. Never use lazy or vague messages like "update", "wip", or "fix".
- **Documentation Sync**: Whenever features, APIs, or configurations change, immediately update `README.md` to keep documentation 100% in sync with code reality.

---

## 3. The Ponytail Engineering Policy (`/ponytail`)
Always enforce the lazy senior developer mindset: "The best code is the code you never wrote."

1. **YAGNI (You Aren't Gonna Need It)**: Question speculative needs; reject unnecessary abstractions or premature configurations.
2. **Reuse Existing Patterns**: Check for existing utilities, types, or helpers in this repo before writing new ones.
3. **Standard Library First**: Prefer Python/Node.js standard libraries (`collections`, `itertools`, `pathlib`, `dataclasses`, `time`, `json`, `math`) over external packages.
4. **Native Platform Features**: Prefer native browser and OS capabilities over bloated third-party dependencies.
5. **Installed Dependencies First**: Never introduce a new package if installed dependencies or 3 lines of standard code solve the problem.
6. **Boring Over Clever**: The simplest, cleanest solution that works reliably is the correct one.

---

## 4. UI, Styling & Zero Emojis Policy
- **Zero Emojis**: Never use emojis in code, UI, modals, buttons, alerts, banners, commit messages, or user-facing text. Use clean inline SVG icons (e.g. Lucide), semantic badges, or crisp typography instead.
- **High-Contrast Dark Aesthetic**: Follow the tactical surveillance HUD design language established in the dashboard.
