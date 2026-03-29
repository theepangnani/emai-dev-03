# ClassBridge Accessibility, Design & UI Audit Report

**Date:** 2026-03-27
**Audited by:** Claude Code (automated static analysis)
**Scope:** Frontend React codebase (`frontend/src/`)
**Standards:** WCAG 2.1 Level AA, WAI-ARIA Authoring Practices 1.2

---

## Executive Summary

A comprehensive static code analysis of the ClassBridge frontend revealed **48 findings** across three categories:

- **Accessibility (A11y):** 35 findings — keyboard navigation, ARIA attributes, focus management, semantic HTML, screen reader support
- **Design System:** 10 findings — color tokens, spacing, typography, border-radius, dark mode coverage
- **UI Usability:** 3 findings — responsive design, touch targets, text overflow

These have been organized into **15 GitHub issues**: 4 P0 (critical), 8 P1 (major), 3 P2 (minor).

| Priority | Count | Description |
|----------|-------|-------------|
| P0       | 4     | Blocks keyboard/screen reader users from core features |
| P1       | 8     | Significant degradation in experience or design consistency |
| P2       | 3     | Polish items (animation, print styles, minor inconsistencies) |

---

## P0: Critical — Blocks Users

### Issue 1 ([#2472](https://github.com/theepangnani/emai-dev-03/issues/2472)): Modal dialogs missing dialog semantics, focus trap, and focus restoration

**WCAG:** 2.4.3 Focus Order, 4.1.2 Name/Role/Value, 1.3.1 Info and Relationships

| Finding # | File | Lines | Issue |
|-----------|------|-------|-------|
| 2 | `components/NotificationBell.tsx` | 278-287 | Modal overlay via portal has NO `role="dialog"`, NO `aria-modal="true"`, NO `aria-labelledby`. Close button lacks `aria-label`. |
| 3 | `components/NotificationBell.tsx` | 279-319 | When modal closes (line 310), focus not returned to trigger button. No `useRef` tracking trigger. |
| 22 | `context/AuthContext.tsx` | 176-189 | Session warning modal rendered inline with no `role="dialog"`, no `aria-modal`, no `aria-labelledby`, no focus management. |
| 29 | `hooks/useFocusTrap.ts` + `utils/useFocusTrap.ts` | — | Two duplicate focus trap implementations. Missing selectors: `a[href]`, `[contenteditable]`. |
| 30 | `hooks/useFocusTrap.ts` | 62-70 | Uses `setTimeout(..., 0)` for focus — doesn't account for render timing variability. |
| 31 | `components/AILimitRequestModal.tsx` | 54-132 | No `body.style.overflow = 'hidden'` when modal opens (verify if `.modal-overlay` class triggers global rule). |

**Remediation:**
1. Add `role="dialog"`, `aria-modal="true"`, `aria-labelledby` to NotificationBell modal
2. Add `aria-label="Close"` to close button
3. Track trigger button with `useRef`; restore focus on modal close
4. Refactor AuthContext session warning to use proper dialog semantics and focus trap
5. Consolidate duplicate `useFocusTrap` — remove `utils/` version, keep `hooks/` version, add missing selectors
6. Replace `setTimeout` with `requestAnimationFrame` in focus trap

---

### Issue 2 ([#2473](https://github.com/theepangnani/emai-dev-03/issues/2473)): Clickable divs not keyboard accessible

**WCAG:** 2.1.1 Keyboard, 4.1.2 Name/Role/Value

| Finding # | File | Lines | Issue |
|-----------|------|-------|-------|
| 9 | `components/NotificationBell.tsx` | 211-259 | Notification items are `<div onClick>` with no `tabIndex`, no `role="button"`, no `onKeyDown` handler. |
| 10 | `pages/CoursesPage.tsx` | 54-60 | Custom `handleKeyDown` on divs instead of native `<button>` elements. |

**Remediation:**
1. NotificationBell: Convert notification items to `<button>` or add `role="button"`, `tabIndex={0}`, `onKeyDown` for Enter/Space
2. CoursesPage: Replace div+keyhandler pattern with native `<button>` elements

---

### Issue 3 ([#2474](https://github.com/theepangnani/emai-dev-03/issues/2474)): Form inputs missing error association and required indicators

**WCAG:** 1.3.1 Info and Relationships, 3.3.1 Error Identification, 3.3.2 Labels or Instructions, 4.1.3 Status Messages

| Finding # | File | Lines | Issue |
|-----------|------|-------|-------|
| 4 | `components/ConfirmModal.tsx` | 59-70 | Prompt label (line 61) has no `htmlFor`; input (line 62) has no `id`. |
| 5 | `pages/Login.tsx` | 162-168 | Error messages not linked with `aria-describedby`. Missing `aria-invalid="true"` on inputs. |
| 6 | `pages/Register.tsx` | 113-126 | Username availability check status has no `aria-live` region. |
| 32 | `components/CreateTaskModal.tsx` | 85 | "Title *" visual-only required indicator — no `aria-required="true"`. |
| 33 | `pages/Login.tsx` | 146-160 | Account lockout banner missing `role="alert"`. |

**Remediation:**
1. ConfirmModal: Add matching `id`/`htmlFor` pair on input and label
2. Login: Add `aria-describedby` on inputs referencing error div `id`; add `aria-invalid="true"` when error present
3. Login: Add `role="alert"` to lockout banner
4. Register: Wrap username status in `aria-live="polite"` region
5. CreateTaskModal: Add `aria-required="true"` to title input

---

### Issue 4 ([#2475](https://github.com/theepangnani/emai-dev-03/issues/2475)): Skip navigation broken, no page titles, no focus on route change

**WCAG:** 2.4.1 Bypass Blocks, 2.4.2 Page Titled, 2.4.3 Focus Order

| Finding # | File | Lines | Issue |
|-----------|------|-------|-------|
| 1 | `pages/Dashboard.css` | 32-48 | Skip link uses `left: -9999px` positioning — hidden behind sticky header when focused. |
| 7 | `App.tsx` | 115-536 | No `document.title` updates on route changes. |
| 8 | `App.tsx` | — | Focus not moved to main content area on navigation. |

**Remediation:**
1. Dashboard.css: Replace `left: -9999px` with `transform: translateY(-100%)` approach; ensure z-index above header on focus
2. App.tsx: Add `useEffect` or custom `usePageTitle` hook to set `document.title` per route
3. App.tsx: On route change, move focus to `<main>` element (`tabIndex={-1}`)

---

## P1: Major — Significant Degradation

### Issue 5 ([#2476](https://github.com/theepangnani/emai-dev-03/issues/2476)): Navigation/menu components missing ARIA patterns

**WCAG:** 4.1.2 Name/Role/Value, 2.1.1 Keyboard

| Finding # | File | Lines | Issue |
|-----------|------|-------|-------|
| 24 | `components/DashboardLayout.tsx` | 442-445 | Hamburger button has `aria-label` but missing `aria-expanded` attribute. |
| 25 | `components/DashboardLayout.tsx` | 466-480 | Role switcher dropdown missing `role="menu"`, `role="menuitem"`, arrow key navigation, Escape to close. |
| 26 | `components/DashboardLayout.tsx` | 607-620 | Active nav items show CSS class but no `aria-current="page"`. |
| 28 | `components/DashboardLayout.tsx` | 514 | Mobile menu overlay not marking background content `aria-hidden="true"`. |

**Remediation:**
1. Add `aria-expanded={menuOpen}` to hamburger button
2. Add `role="menu"` to dropdown, `role="menuitem"` to options, implement arrow key + Escape handlers
3. Add `aria-current="page"` to active nav link
4. Add `aria-hidden="true"` to background content when mobile menu is open

---

### Issue 6 ([#2477](https://github.com/theepangnani/emai-dev-03/issues/2477)): Status banners and toasts not announced to screen readers

**WCAG:** 4.1.3 Status Messages

| Finding # | File | Lines | Issue |
|-----------|------|-------|-------|
| 23 | `components/DashboardLayout.tsx` | 430-437 | Reconnecting banner has no `role="status"` or `aria-live="polite"`. |
| 27 | `components/DashboardLayout.tsx` | 497-511 | Email verification banner missing `role="status"`. |
| 34 | — | — | No centralized `aria-live` region for async operation announcements (study guide streaming, etc.). |
| 35 | `components/Toast.tsx` | 48 | Toast div clickable but not keyboard focusable/dismissible. |

**Remediation:**
1. Add `role="status"` and `aria-live="polite"` to reconnecting banner
2. Add `role="status"` to email verification banner
3. Add global visually-hidden `aria-live` region in App.tsx for async announcements
4. Toast: Add keyboard dismiss support (`tabIndex={0}`, `onKeyDown`)

---

### Issue 7 ([#2478](https://github.com/theepangnani/emai-dev-03/issues/2478)): Missing labels, text alternatives, heading hierarchy

**WCAG:** 1.1.1 Non-text Content, 1.3.1 Info and Relationships, 2.4.6 Headings and Labels

| Finding # | File | Lines | Issue |
|-----------|------|-------|-------|
| 11 | Multiple pages | — | Heading levels may skip (h2 to h4) or lack h1. |
| 12 | `components/NotificationBell.tsx` | 154-169 | Emoji spans have `aria-hidden="true"` but no text alternative provided alongside. |
| 13 | `components/RichTextEditor.tsx` | — | No `aria-label` on editor; toolbar buttons likely unlabeled. |
| 14 | `components/Breadcrumb.tsx` | 26 | Current page span missing `aria-current="page"`. |
| 15 | `components/DashboardLayout.tsx` | 44-150 | NAV_SVG icons next to text labels missing `aria-hidden="true"`. |

**Remediation:**
1. Audit and fix heading hierarchy (ensure h1 exists per page, no skipped levels)
2. Verify notification titles provide sufficient text context alongside hidden emoji
3. Add `aria-label` to RichTextEditor container; label toolbar buttons
4. Add `aria-current="page"` to Breadcrumb current item
5. Add `aria-hidden="true"` to decorative SVG icons in nav

---

### Issue 8 ([#2479](https://github.com/theepangnani/emai-dev-03/issues/2479)): Focus-visible states missing on interactive elements

**WCAG:** 2.4.7 Focus Visible

| Finding # | File | Lines | Issue |
|-----------|------|-------|-------|
| 18 | `pages/Dashboard.css` | 103-120, 122-136 | `.role-switcher-option` and `.logout-button` have no `:focus-visible` styles. |
| 18 | `components/Toast.css` | — | No focus indicator on toast elements. |

**Remediation:**
1. Add `:focus-visible` styles to `.role-switcher-option`, `.logout-button`
2. Add `:focus-visible` to Toast for focusable elements
3. Consider a global `:focus-visible` rule using `var(--color-accent)` for consistency

---

### Issue 9 ([#2480](https://github.com/theepangnani/emai-dev-03/issues/2480)): Hardcoded colors bypass CSS custom properties (15+ files)

| Finding # | File | Lines | Issue |
|-----------|------|-------|-------|
| 36 | `components/SearchableSelect.css` | 9,10,18,28,29,34,51,56,62,69,80,81 | `#ddd`, `#4f46e5`, `#fff` instead of `var(--color-*)` |
| 36 | `components/BugReportModal.css` | 5,16,24,34,56,61,62,67,68,73-74,81,87 | `#dc2626` instead of `var(--color-danger)` |
| 36 | `components/SpeedDialFAB.css` | 20,25,39,47,58,101,125,126,144 | `#ef4444` instead of `var(--color-danger)` |
| 36 | `context/AuthContext.tsx` | 177-183 | Inline styles with `#fff`, `#555`, `#4f46e5` |
| 36 | `components/DashboardLayout.tsx` | 431-435 | Inline styles with `#f59e0b`, `#fff` |

**Remediation:**
1. Replace all hardcoded hex/rgba in CSS with `var(--color-*)` tokens from index.css
2. Replace inline styles with CSS classes using design tokens

---

### Issue 10 ([#2481](https://github.com/theepangnani/emai-dev-03/issues/2481)): Inconsistent border-radius, spacing, button styles

| Finding # | File | Issue |
|-----------|------|-------|
| 37 | `pages/StudentDashboard.css` | 13 different border-radius values (mix of tokens and hardcoded 4px-20px) |
| 38 | Multiple files | Gap values: 2px, 4px, 6px, 8px, 10px, 12px, 16px — no consistent scale |
| 39 | Multiple files | 4+ different button padding/radius combinations |
| 40 | 3 files | 3 different empty state implementations with different padding |
| 41 | Multiple files | Card containers use different padding (16px-48px) and radius values |

**Remediation:**
1. Define spacing tokens in index.css (`--space-xs` through `--space-3xl`)
2. Replace all hardcoded border-radius with `var(--radius-*)` tokens
3. Standardize button padding and card padding using spacing tokens
4. Consolidate empty state implementations to use shared EmptyState component

---

### Issue 11 ([#2482](https://github.com/theepangnani/emai-dev-03/issues/2482)): Font sizes in px, no type scale defined

**WCAG:** 1.4.4 Resize Text

| Finding # | File | Lines | Issue |
|-----------|------|-------|-------|
| 16 | `pages/Auth.css` | 30-42 | 28px, 14px instead of rem |
| 16 | `pages/Dashboard.css` | 74-75 | 11px, 13px instead of rem |
| 16 | `components/Toast.css` | 22, 30 | 14px, 16px instead of rem |
| 16 | `components/PageNav.css` | 28, 72 | 14px, 13px instead of rem |
| 16 | `components/NotificationBell.css` | 32, 64, 72 | 10px, 16px, 13px instead of rem |
| 42 | `index.css` | — | No type scale tokens defined. 15+ distinct sizes: 11px through 28px. |

**Remediation:**
1. Define type scale tokens in index.css: `--text-xs` (0.75rem) through `--text-3xl` (1.75rem)
2. Convert all px font sizes to rem using type scale tokens

---

### Issue 12 ([#2483](https://github.com/theepangnani/emai-dev-03/issues/2483)): Dark mode coverage ~50% — many components unstyled

| Finding # | File | Issue |
|-----------|------|-------|
| 45 | `components/BugReportModal.css` | No `[data-theme="dark"]` rules |
| 45 | `components/ContentCard.css` | No dark mode styles |
| 45 | `components/Toast.css` | No dark mode styles |
| 45 | `pages/StudentDashboard.css` | No dark mode section |

**Remediation:**
1. Audit all CSS files for dark mode coverage
2. Add `[data-theme="dark"]` variants using existing dark tokens from index.css
3. Prioritize dashboards and modals

---

## P2: Minor — Polish

### Issue 13 ([#2484](https://github.com/theepangnani/emai-dev-03/issues/2484)): Missing prefers-reduced-motion media queries

**WCAG:** 2.3.3 Animation from Interactions

| Finding # | File | Lines | Issue |
|-----------|------|-------|-------|
| 19 | `components/Toast.css` | 60-69 | `@keyframes toast-in` with no `@media (prefers-reduced-motion: reduce)` fallback |
| 19 | `components/NotificationBell.tsx` | 30 | `scrollIntoView({ behavior: 'smooth' })` not gated on motion preference |

**Remediation:**
1. Add `@media (prefers-reduced-motion: reduce)` to disable animations
2. Check `matchMedia('(prefers-reduced-motion: reduce)')` before smooth scroll

---

### Issue 14 ([#2485](https://github.com/theepangnani/emai-dev-03/issues/2485)): Inconsistent hover/disabled states and z-index

| Finding # | File | Issue |
|-----------|------|-------|
| 20 | Various CSS | Z-index values inconsistent: header z-10, dropdown z-1000, overlay z-20, toast z-10000 |
| 43 | Multiple CSS | Disabled opacity varies: 0.6 (BugReportModal) vs 0.7 (Auth) |
| 44 | Multiple CSS | Hover transforms vary: translateY(-1px/-2px/-3px), scale(0.97), brightness(0.9) |

**Remediation:**
1. Use z-index tokens from index.css consistently
2. Standardize disabled state: opacity 0.6, `cursor: not-allowed`
3. Standardize hover transform: `translateY(-2px)` for cards, none for buttons

---

### Issue 15 ([#2486](https://github.com/theepangnani/emai-dev-03/issues/2486)): Mobile breakpoints, print styles, text overflow

| Finding # | File | Issue |
|-----------|------|-------|
| 17 | `components/NotificationBell.css` (line 45) | `width: 360px` fixed, no mobile breakpoint — overflows small screens |
| 21 | `components/Toast.css` | No min-height for touch targets (WCAG 2.5.5: 44x44px) |
| 46 | Various CSS | Mix of 480px, 600px, 768px, 1024px breakpoints — inconsistent |
| 47 | Most files | Only ContentCard.css and PageNav.css have `@media print` styles |
| 48 | Multiple files | Component titles lack `text-overflow: ellipsis` |

**Remediation:**
1. Add mobile breakpoint to NotificationBell dropdown
2. Standardize breakpoints: 480px, 768px, 1024px only
3. Add touch target minimums (44px) to interactive elements
4. Add print styles to dashboards (hide nav, optimize layout)
5. Add text-overflow handling to truncatable titles

---

## Finding-to-Issue Mapping

| Finding | Issue | Category | Priority |
|---------|-------|----------|----------|
| 1 | 4 | A11y | P0 |
| 2 | 1 | A11y | P0 |
| 3 | 1 | A11y | P0 |
| 4 | 3 | A11y | P0 |
| 5 | 3 | A11y | P0 |
| 6 | 3 | A11y | P0 |
| 7 | 4 | A11y | P0 |
| 8 | 4 | A11y | P0 |
| 9 | 2 | A11y | P0 |
| 10 | 2 | A11y | P0 |
| 11 | 7 | A11y | P1 |
| 12 | 7 | A11y | P1 |
| 13 | 7 | A11y | P1 |
| 14 | 7 | A11y | P1 |
| 15 | 7 | A11y | P1 |
| 16 | 11 | Design | P1 |
| 17 | 15 | Design | P2 |
| 18 | 8 | A11y | P1 |
| 19 | 13 | A11y | P2 |
| 20 | 14 | Design | P2 |
| 21 | 15 | Design | P2 |
| 22 | 1 | A11y | P0 |
| 23 | 6 | A11y | P1 |
| 24 | 5 | A11y | P1 |
| 25 | 5 | A11y | P1 |
| 26 | 5 | A11y | P1 |
| 27 | 6 | A11y | P1 |
| 28 | 5 | A11y | P1 |
| 29 | 1 | A11y | P0 |
| 30 | 1 | A11y | P0 |
| 31 | 1 | A11y | P0 |
| 32 | 3 | A11y | P0 |
| 33 | 3 | A11y | P0 |
| 34 | 6 | A11y | P1 |
| 35 | 6 | A11y | P1 |
| 36 | 9 | Design | P1 |
| 37 | 10 | Design | P1 |
| 38 | 10 | Design | P1 |
| 39 | 10 | Design | P1 |
| 40 | 10 | Design | P1 |
| 41 | 10 | Design | P1 |
| 42 | 11 | Design | P1 |
| 43 | 14 | Design | P2 |
| 44 | 14 | Design | P2 |
| 45 | 12 | Design | P1 |
| 46 | 15 | Design | P2 |
| 47 | 15 | Design | P2 |
| 48 | 15 | Design | P2 |

---

## Positive Patterns Found

The following accessibility patterns are already correctly implemented:

- Toast container: `aria-live="polite"`
- ConfirmModal: `role="alertdialog"` with `aria-labelledby`
- Dialog modals: `role="dialog"` with `aria-modal="true"` (on some modals)
- Skip navigation link: Present in DashboardLayout
- Honeypot input: `aria-hidden="true"` (bot protection)
- Navigation buttons: `aria-label` attributes present
- Tab components: `role="tablist"` and `role="tab"`
- Setup checklist: `role="progressbar"`
- PasswordInput: `aria-label` on visibility toggle
- Breadcrumb: `aria-label="Breadcrumb"` on `<nav>`
- NotificationBell: `min-width: 44px; min-height: 44px` touch target
- Hamburger button: `min-width: 44px; min-height: 44px` touch target
- `index.html`: `lang="en"` attribute present
- `index.css`: Comprehensive CSS custom property system with 3 theme variants

---

## Methodology

- **Type:** Static code analysis (no runtime/automated scanning)
- **Tools not used:** axe-core, Lighthouse, WAVE (recommended for follow-up)
- **Approach:** Manual review of all React components (.tsx), CSS files (.css), context providers, custom hooks, and HTML entry point
- **Coverage:** All files in `frontend/src/pages/`, `frontend/src/components/`, `frontend/src/context/`, `frontend/src/hooks/`, `frontend/src/api/`, `frontend/index.html`
- **Limitations:** Cannot detect runtime-only issues (actual color contrast ratios, dynamic content timing, browser-specific behavior). Recommend follow-up with axe-core integration testing.
