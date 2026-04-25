# ClassBridge Theme System

This document describes the design-token theme system that powers the ClassBridge
frontend. All themes are CSS-driven via a `data-theme` attribute on
`<html>`; no per-page CSS files need to know which theme is active.

## The four themes

| Key      | Description                                                                                                                   |
|----------|-------------------------------------------------------------------------------------------------------------------------------|
| `light`  | The default. Cool blue accent, white surfaces, blue-grey ink. Mapped to `:root` so it is also the implicit fallback.          |
| `dark`   | Warm-charcoal dark mode. Lavender accent, near-black surfaces, off-white ink.                                                 |
| `focus`  | Warm-muted "study" mode. Sand surfaces, slate accent, lower contrast — designed for long focused-reading sessions.            |
| `bridge` | CB-THEME-001 — warm ivory + serif headings (Fraunces / DM Sans). Rust-orange accent, paper-white cards, pine + amber accents. |

All four themes coexist. The `ThemeToggle` button cycles through them in the
order listed above (`light → dark → focus → bridge → light`).

## How `data-theme` swap works

`frontend/src/context/ThemeContext.tsx` owns the active theme as React state and
mirrors it to the DOM by calling
`document.documentElement.setAttribute('data-theme', theme)` whenever it changes.
The mounted theme is also persisted to `localStorage` under the key
`classbridge-theme` so reloads restore the last-picked theme.

`frontend/src/index.css` declares one CSS block per theme:

```css
:root, [data-theme="light"] { /* light tokens */ }
[data-theme="dark"]   { /* dark tokens */ }
[data-theme="focus"]  { /* focus tokens */ }
[data-theme="bridge"] { /* bridge tokens */ }
```

Every page-level `.css` file references the shared `--color-*`, `--shadow-*`,
`--radius-*`, etc. tokens — never hard-coded hex values. Swapping `data-theme`
re-resolves every token via CSS cascade in a single repaint.

## Bridge theme — token mapping

The bridge block defines BOTH bridge-native tokens (new) AND mappings of
existing token names so 120+ existing CSS files automatically inherit the new
look without per-file edits.

### Bridge-native tokens (new)

| Token                  | Value     | Use                              |
|------------------------|-----------|----------------------------------|
| `--color-ivory`        | `#f5f1ea` | Page background                  |
| `--color-paper`        | `#fbf8f2` | Sections / surface-alt           |
| `--color-card`         | `#ffffff` | Card surfaces                    |
| `--color-hair`         | `#e5ddd1` | Hairline borders                 |
| `--color-rail`         | `#ece4d6` | Side rails / chips               |
| `--color-rust`         | `#b04a2c` | Primary accent (CTAs, links)     |
| `--color-rust-ink`     | `#7a2f18` | Pressed / strong accent          |
| `--color-pine`         | `#2d4a3e` | Success / role-teacher           |
| `--color-amber`        | `#d4a24b` | Warning / pending state          |
| `--color-sky`          | `#3b6a8f` | Info / brand-google              |
| `--color-rose`         | `#c25b6f` | Danger                           |
| `--color-on-track-bg`  | `#e6efe8` | "On track" status badge bg       |
| `--color-on-track-ink` | `#23523f` | "On track" status badge text     |
| `--color-pending-bg`   | `#f6ead3` | "Pending" status badge bg        |
| `--color-pending-ink`  | `#7a5a1a` | "Pending" status badge text      |
| `--font-display-serif` | `'Fraunces', Georgia, serif` | H1-H3 (per S1-S6 reskin) |
| `--font-mono`          | `'JetBrains Mono', 'Consolas', monospace` | Numbers, code |
| `--radius-bridge-sm`   | `8px`     | Small bridge radius              |
| `--radius-bridge-md`   | `14px`    | Medium bridge radius             |
| `--radius-bridge-lg`   | `22px`    | Large bridge radius              |

### Existing tokens remapped

These are the same `--color-*` names that the rest of the app already uses; the
bridge block just rebinds them so legacy CSS auto-inherits.

| Group        | Token                  | Bridge value                |
|--------------|------------------------|-----------------------------|
| Surface      | `--color-ink`          | `#1c1a16`                   |
| Surface      | `--color-ink-muted`    | `#6b645b`                   |
| Surface      | `--color-surface`      | `#ffffff`                   |
| Surface      | `--color-surface-alt`  | `#fbf8f2`                   |
| Surface      | `--color-surface-bg`   | `#f5f1ea`                   |
| Surface      | `--color-border`       | `#e5ddd1`                   |
| Accent       | `--color-accent`       | `#b04a2c` (rust)            |
| Accent       | `--color-accent-strong`| `#7a2f18` (rust-ink)        |
| Accent       | `--color-accent-warm`  | `#d4a24b` (amber)           |
| Semantic     | `--color-blue`         | `#3b6a8f` (sky)             |
| Semantic     | `--color-danger`       | `#c25b6f` (rose)            |
| Semantic     | `--color-warning`      | `#d4a24b` (amber)           |
| Semantic     | `--color-success`      | `#2d4a3e` (pine)            |
| Priority     | `--priority-high`      | `#c25b6f`                   |
| Priority     | `--priority-medium`    | `#d4a24b`                   |
| Priority     | `--priority-low`       | `#2d4a3e`                   |
| Brand        | `--brand-google`       | `#3b6a8f`                   |
| Role badges  | `--role-parent`        | `#b04a2c`                   |
| Role badges  | `--role-teacher`       | `#2d4a3e`                   |
| Role badges  | `--role-admin`         | `#7a5a1a`                   |
| Status bg    | `--color-success-bg`   | `#e6efe8` (on-track-bg)     |
| Status bg    | `--color-warning-bg`   | `#f6ead3` (pending-bg)      |
| Patterns     | `--bg-dot-color`       | `rgba(28, 26, 22, 0.04)`    |
| Skeleton     | `--skeleton-from`      | `rgba(229, 221, 209, 0.6)`  |
| Skeleton     | `--skeleton-mid`       | `rgba(245, 241, 234, 0.6)`  |
| Typography   | `--font-sans`          | `'DM Sans', ...`             |
| Typography   | `--font-display`       | `'Fraunces', ...`            |
| Radii        | `--radius-sm` / `--radius-md` / `--radius-lg` | `8px / 14px / 22px` |

Shadows are also remapped to a softer warm-shadow stack (`shadow-soft` /
`shadow-lift` use the prototype's two-stop drop-shadow recipe).

See `docs/design/my-bridge-to-bridge-prototype.html` for the source-of-truth
prototype and `requirements/features-part7.md §6.144` for the feature brief.

## Force-apply via the `theme.bridge_default` feature flag

The `bridge` theme is opt-in by default. To roll it out to a cohort of users,
flip the **`theme.bridge_default`** backend feature flag.

### How the force-apply works

1. `<App>` mounts `<ThemeProvider>` and (inside `<QueryClientProvider>`) a
   tiny `<BridgeDefaultApplier />` component.
2. `<BridgeDefaultApplier>` calls `useFeatureFlagEnabled('theme.bridge_default')`.
3. When the flag resolves to `true` for the current user AND the user has not
   explicitly stored a theme in localStorage, `ThemeProvider` overrides the
   initial theme to `bridge` and writes `data-theme="bridge"` on `<html>`.
4. A `forcedRef` ref guards the override so it fires at most once per session.
   Subsequent `ThemeToggle` clicks remain sticky.

### Variants

The flag uses the standard variant ladder:

- `off` — no force-apply (default).
- `on_5` / `on_25` / `on_50` — sticky-bucket rollout to a percentage of users.
- `on_100` / `on_for_all` — full rollout.

Hard kill-switch semantics from #3930 still apply: setting `enabled=false`
forces the variant to `off` regardless of the stored variant value.

### Known limitation — Flash of Wrong Theme (FOWT)

`useFeatureFlagEnabled` resolves the flag asynchronously via TanStack Query
after first paint. Users in the rollout cohort will see the page render in
their previous theme momentarily before flipping to bridge — visible flash on
every cold-load.

This will be addressed in a follow-up by either:

1. Caching the resolved flag value in `localStorage` and applying it
   synchronously on next mount, OR
2. Adding a `<script>` boot block in `index.html` that reads a backend-set
   cookie and applies `data-theme` before React mounts.

Tracked under #4213.

## Adding a new theme

1. Add the new key to the `Theme` type and the `THEMES` array in
   `frontend/src/context/ThemeContext.tsx`.
2. Add a `[data-theme="<key>"]` block to `frontend/src/index.css` that
   defines (at minimum) every `--color-*`, `--shadow-*`, and `--bg-dot-*`
   token used by `:root`. Inheriting from another theme works only if you
   `@extend` via duplication — CSS custom properties are not inherited
   between selectors.
3. Add an entry to `THEME_META` in `frontend/src/components/ThemeToggle.tsx`
   so the toggle button shows an icon and label for the new state.
4. (Optional) If the theme should have a "force-apply" default for some
   users, register a backend feature flag in
   `app/services/feature_seed_service.py` and add a small
   `<XxxDefaultApplier />` component modeled on `BridgeDefaultApplier`.
5. Update this document.
