# Landing v2 — Design System (CB-LAND-001)

This directory hosts the Mindgrasp-inspired landing-page redesign tracked under
epic [#3800](https://github.com/theepangnani/emai-dev-03/issues/3800)
(requirements §6.136 / §6.136.2 in `requirements/features-part7.md`).

All visual tokens below are **scoped under `[data-landing="v2"]`** so they do
not leak into the rest of the app (dashboard, auth flows, mobile web, etc.).
Apply the attribute on the landing route's outermost wrapper, e.g.:

```tsx
<main data-landing="v2" className="landing-v2-root">
  {/* hero, feature rows, how-it-works, footer … */}
</main>
```

Reference screenshots: [`docs/design/landing-v2-reference/`](../../../../docs/design/landing-v2-reference/)
(12 annotated Mindgrasp shots committed under PR #3818 / epic #3800).

## Token catalogue

### Typography

| Token                   | Value                                             | When to use                                                              |
| ----------------------- | ------------------------------------------------- | ------------------------------------------------------------------------ |
| `--font-display-serif`  | `'Fraunces', Georgia, serif`                      | Italic hero word and section-lead italic accents only (weight 400 / 500). Never body copy. |
| `--font-landing-sans`   | `'Instrument Sans', 'Source Sans 3', sans-serif`  | All body, sub-heads, nav, CTAs, captions. Weights 400 / 500 / 600.       |

Fonts are loaded in `frontend/index.html` via a single Google Fonts stylesheet
with `rel="preconnect"` + `display=swap`. Global app routes pay only the HTTP
request; unused weights never render in the non-landing tree.

### Pastel row backgrounds

Alternating full-bleed sections on the long-scroll landing page. Apply to the
section's `background-color` — pair with ink `--color-ink` for body copy and
reference screenshots `04a`/`04b`/`04c` for row ordering.

| Token                    | Hex       |
| ------------------------ | --------- |
| `--color-row-peach`      | `#FFF1E6` |
| `--color-row-mint`       | `#E8F7F1` |
| `--color-row-lavender`   | `#F1EDFE` |
| `--color-row-pink`       | `#FDEBF1` |

### Accent hues

Badges, underlines, scanline sweeps, micro-illustration fills. Never a primary
text color on white (contrast < AA); pair with ink or use as fill behind bold
ink glyphs.

| Token                   | Hex       |
| ----------------------- | --------- |
| `--color-accent-cyan`   | `#1FD8FF` |
| `--color-accent-gold`   | `#FFB800` |
| `--color-accent-mint`   | `#46D69A` |
| `--color-accent-coral`  | `#FF5C5C` |

### Motion

Spring easings match the reference bounce on hover/entrance. Scanline loop is
for the "AI is working" strip in the hero (see `01-hero.png`).

| Token                     | Value                                             |
| ------------------------- | ------------------------------------------------- |
| `--motion-spring-fast`    | `380ms cubic-bezier(0.34, 1.56, 0.64, 1)`         |
| `--motion-spring-slow`    | `640ms cubic-bezier(0.34, 1.56, 0.64, 1)`         |
| `--motion-scanline-loop`  | `2.2s linear infinite`                            |

A `@media (prefers-reduced-motion: reduce)` block in `index.css` zeroes these
tokens (`0ms` spring durations, scanline set to `0s linear 1`) so components
that reference the variables automatically comply with WCAG 2.3.3.

## Usage rules

1. **Never consume these tokens outside `[data-landing="v2"]`.** They are not
   part of the app theme and are not exposed to `[data-theme="light|dark|focus"]`.
2. **Never redefine tokens inside a component.** If you need a new value, add
   it here and document it in the table above.
3. **Respect reduced motion.** Always read motion from the tokens — never
   hardcode durations or easings in component CSS.
4. **Do not edit `LaunchLandingPage.tsx` or `frontend/src/components/demo/*`.**
   CB-DEMO-001 (§6.135) ships on its own track and coexists with landing-v2
   behind the `landing_v2` feature flag (see §6.136 rollout plan).
