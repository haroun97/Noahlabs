# Development Plan — Noah Labs Frontend Challenge

> Status: Planning only. No application code is written yet. This document is the
> implementation guide for the frontend challenge located in
> `noah-labs-challenge-classroom-frontend-challenge-frontend-challenge/`.
>
> Hard constraint from the challenge: **only React primitives + MUI** are allowed.
> No data-fetching/state libraries (React Query, SWR, Redux, Zustand, etc.).

---

## 1. Goals & Constraints

**Functional goals (from `src/App.tsx`):**
- **Task #1** — Pixel-match `public/table_screenshot.png`:
  1. Remove padding from the table section so the scrollbar hugs the right green border.
  2. Align the "No Data" text with the temperature text.
- **Task #2** — Per-row button that fetches `getPersonDetails(id)` and renders it in a
  `PersonDetails` component, handling **loading / error / not-found / success** states
  and guarding against **race conditions** from variable network latency.
- **Task #3** — Answer the three written questions in-page.

**Non-functional goals (explicitly requested):**
- **Scalable** — components stay small, composable, and reusable; logic separated from
  presentation; adding a new column/action/detail field is a local change.
- **Simple & easy to understand** — minimal abstractions, clear names, no over-engineering.
- **Commented** — comments explain *why* (intent, trade-offs, the race-condition guard),
  not *what*.
- **Optimized** — no needless re-renders or re-fetches; stable callbacks; render only
  what changed.
- **Type-safe** — leverage TypeScript fully; no `any`; discriminated unions for async state.

**Special requirement — keep the old page for comparison:**
- The original challenge page must remain viewable **unchanged** alongside the new
  solution, with an in-app switcher so a reviewer can toggle "Original" vs "Solution".

---

## 2. Strategy: Old vs New Side-by-Side

The original components (`DataTable`, `StatusPill`, `Section`, `PersonDetails`) are
shared and imported by `App.tsx`. If we edit them in place, the "old" page changes too.
To preserve a true before/after, we **freeze a snapshot** of the originals and build the
solution in the main tree.

**Approach:** a `legacy/` snapshot + a root-level version switcher.

- `src/legacy/` — byte-for-byte copies of the original files (the "before"). **Never
  modified after the snapshot.** This is the old version page.
- `src/components/`, `src/App.tsx` — the improved "after" (Solution).
- `src/main.tsx` renders a new `Root` that provides a switcher (MUI `ToggleButtonGroup`
  or `Tabs`) between **Original** and **Solution**.

This satisfies "keep the old version to compare" using only React + MUI, with zero
external routing. The switcher uses local `useState` (no router needed); optionally
persist the choice in `localStorage` `[Optional]`.

> Alternative considered: a URL hash route (`#/legacy`). Rejected — a simple toggle is
> less code and meets the requirement; routing adds no value for two static views.

---

## 3. Proposed File Structure

```
src/
  main.tsx                      # EDIT: render <Root/> instead of <App/>
  Root.tsx                      # NEW: version switcher (Original | Solution)

  App.tsx                       # EDIT: the Solution page (tasks implemented, Q&A filled)

  legacy/                       # NEW: frozen snapshot of the ORIGINAL (do not modify)
    LegacyApp.tsx               #   = original App.tsx, verbatim
    components/
      DataTable.tsx             #   = original, verbatim
      StatusPill.tsx            #   = original, verbatim
      Section.tsx               #   = original, verbatim
      PersonDetails.tsx         #   = original, verbatim
    # legacy imports point to ../api and ../utils (shared, unchanged)

  components/                   # Solution components
    DataTable.tsx               # EDIT: add actions column + alignment fix
    StatusPill.tsx              # (unchanged unless needed)
    Section.tsx                 # (unchanged — keep default padding; override per-use)
    PersonDetails.tsx           # EDIT/keep: success-state presentation
    PersonDetailsPanel.tsx      # NEW: stateful container (loading/error/not-found/success)
    StatusCell.tsx              # NEW (optional): extracted status cell for alignment + reuse

  hooks/
    usePersonDetails.ts         # NEW: encapsulates fetch + async state + race guard

  api/index.ts                  # UNCHANGED (given mock backend)
  utils/index.ts                # UNCHANGED (sleep, getRandomInt)
```

Rationale: presentation (`PersonDetails`) stays dumb/pure; the **container**
(`PersonDetailsPanel`) owns UI state; the **hook** (`usePersonDetails`) owns async
logic + the race guard. Each piece is independently testable and reusable.

---

## 4. Task #1 — Layout Fixes

### 4.1 Remove table-section padding (scrollbar hugs the green border)
- File: `src/App.tsx` (Solution).
- The shared `Section` applies `padding: "1rem"`. **Do not** change the shared default
  (that would affect every section and is exactly the "fragility" the brief warns about).
- Override only the table's section:
  ```tsx
  <Section sx={{ padding: 0 }}>
    <DataTable />
  </Section>
  ```
- Reasoning to record for Q3.1: per-instance `sx` override keeps the component’s default
  intact and the change local.

### 4.2 Align "No Data" with the temperature text
- File: `src/components/DataTable.tsx` (Solution), ideally extracted into
  `components/StatusCell.tsx`.
- Root cause: the pill renders conditionally
  (`{row.temperature && <StatusPill .../>}`), so rows without a temperature lose the
  pill’s width and the text shifts left.
- Fix options (plan picks **A** for simplicity + robustness):
  - **A. Always reserve the pill’s slot.** Render the pill wrapper always; when there is
    no temperature, hide it with `visibility: "hidden"` (keeps layout box) instead of
    omitting it. The text column then starts at the same x for every row.
  - B. Give the pill a fixed-width container and the text a separate flex cell.
- Keep `getStatus`/`getTemperatureText` pure helpers (unchanged logic).
- Verification: compare against `public/table_screenshot.png` — "No Data" left edge
  aligns with `36.7°C` etc.

---

## 5. Task #2 — Fetch & Display Person Details

### 5.1 Async state model (type-safe)
Use a **discriminated union** so impossible states are unrepresentable:

```ts
type PersonDetailsState =
  | { status: "idle" }
  | { status: "loading"; id: number }
  | { status: "success"; id: number; details: PersonDetails }
  | { status: "notFound"; id: number }
  | { status: "error"; id: number; message: string };
```

This directly maps to the four required UI states (+ idle), and the compiler forces us
to handle each branch.

### 5.2 The hook: `hooks/usePersonDetails.ts`
Responsibilities:
- Expose `{ state, fetchDetails(id) }`.
- Manage the union state above.
- **Race-condition guard (core requirement):** because `getPersonDetails` resolves in
  500–1500ms, a later click can resolve *before* an earlier one. Guard with a
  monotonic **request token** (ref counter): each call captures `const token = ++ref`;
  when it resolves, ignore the result unless `token === ref.current`. Equivalent:
  compare the resolved `id` to the latest requested `id`.
- Cleanup on unmount: a `mountedRef`/flag so we never `setState` after unmount
  (avoids the StrictMode double-invoke warning and leaks).
- Map outcomes: value → `success`; `undefined` → `notFound`; thrown → `error` (store a
  bounded, sanitized message).

Comment focus: explain *why* the token exists (out-of-order responses) — this is the
"network effects" question the challenge calls out.

> Note on `AbortController`: `getPersonDetails` doesn’t accept a signal and isn’t a real
> `fetch`, so we cannot truly cancel it. The token guard is the correct primitive here.
> Mention `AbortController` in Q3.2 as what we’d use with a real HTTP client.

### 5.3 Components
- `components/PersonDetails.tsx` — keep as the **pure success view** (already exists).
  Optionally fix the typo `adress`→`address` in a *new* type without touching the given
  `api` (or note it; the API type spells it `adress`, so keep field mapping consistent).
- `components/PersonDetailsPanel.tsx` (NEW) — receives `state` (or the hook result) and
  renders:
  - `idle` → hint text ("Select a person to view details").
  - `loading` → MUI `CircularProgress` + "Loading…".
  - `error` → error message (MUI `Alert` severity="error").
  - `notFound` → "No details found for this person." (MUI `Alert` severity="info").
  - `success` → `<PersonDetails details={...} />`.
- `components/DataTable.tsx` — add an **actions column** with a per-row button
  ("View details") that calls an `onViewDetails(id)` prop. The table stays presentational
  and does not own fetch state (keeps it reusable/scalable).

### 5.4 Wiring in `App.tsx`
- Call `usePersonDetails()` at the `App` (Solution) level.
- Pass `onViewDetails={fetchDetails}` to `DataTable`.
- Replace the placeholder section (`TODO: Add PersonDetails component here`) with
  `<PersonDetailsPanel state={state} />`.
- Wrap the row callback in `useCallback` and `columns` in `useMemo` so the grid doesn’t
  rebuild every render (optimization).

### 5.5 Requirement → mechanism map (for Q3.2)
| Requirement | Mechanism |
|---|---|
| Loading state | `status: "loading"` → spinner |
| Error state | try/catch → `status: "error"` → Alert |
| Not found | `undefined` result → `status: "notFound"` |
| Success | value → `status: "success"` → `PersonDetails` |
| Network race | request-token guard in `usePersonDetails` |

---

## 6. Task #3 — Written Answers

Filled inline in `src/App.tsx` (Solution), replacing the three `"Your Answer"`
placeholders. Draft direction (to finalize during implementation):

- **Q1 (styling choice):** per-instance `sx` override for the table section + reserved
  layout slot for the pill. Alternatives: editing the shared `Section`/`StatusPill`
  defaults (rejected — global side effects/fragility), a dedicated styled wrapper
  (heavier than needed), or `styled-components` (extra layer; MUI `sx` is already
  idiomatic here).
- **Q2 (Task 2 requirements):** walk through the state union + token guard table in §5.5.
  With external libs: React Query (`useQuery` keyed by `id` gives caching, dedupe,
  built-in loading/error, and request cancellation via `AbortController`), eliminating
  the manual guard.
- **Q3 (production readiness):** tests (Vitest + RTL), error boundary, a real API layer
  with cancellation/retry/caching, env config, accessibility (aria on buttons/table),
  i18n, design tokens/theme instead of literal colors (`green`/`red`), CI (typecheck +
  Biome + tests), loading skeletons, pagination wired to a real backend, and removing
  hardcoded mock data.

---

## 7. Quality Conventions (applied throughout)

- **Types:** no `any`; discriminated unions for async; props typed explicitly; reuse
  `Person`/`PersonDetails` from `api`.
- **Comments:** only where intent is non-obvious — primarily the race guard and the
  layout-slot trick. No narrating comments.
- **Performance:** `useMemo` for `columns`, `useCallback` for row handlers, stable hook
  identity; avoid inline object props that bust memoization.
- **Scalability:** table is data-agnostic (columns config-driven); panel/hook reusable
  for any entity; switcher pattern generic.
- **No regressions:** all changes are additive or `sx`-local; shared defaults untouched;
  `legacy/` proves the before-state.

---

## 8. Verification Plan

- **Task 1:** visual diff against `public/table_screenshot.png` (scrollbar flush to
  green border; "No Data" aligned). Toggle to Original to confirm the before/after.
- **Task 2:** click rows rapidly to confirm only the last selection’s result shows
  (race guard); force errors (50% chance) to see the error state; pick ids with no
  details to see not-found; confirm spinner during latency.
- **Tooling:** `pnpm lint` (Biome) clean, `pnpm build` (tsc) passes with no type errors.
- **Optional `[Optional]`:** add Vitest + React Testing Library tests for the hook
  (race guard, not-found, error) and the panel’s state rendering.

---

## 9. Implementation Phases

| Phase | Goal | Files | Done when |
|---|---|---|---|
| P1 | Snapshot original + switcher | `legacy/**` (copies), `Root.tsx`, `main.tsx` | Toggle shows untouched Original page |
| P2 | Task 1 layout fixes | `App.tsx`, `components/DataTable.tsx` (+`StatusCell.tsx`) | Matches screenshot |
| P3 | Task 2 hook + panel | `hooks/usePersonDetails.ts`, `components/PersonDetailsPanel.tsx`, `components/PersonDetails.tsx` | All 4 states + race guard work |
| P4 | Task 2 wiring | `components/DataTable.tsx` (actions col), `App.tsx` | Button per row drives panel |
| P5 | Task 3 answers | `App.tsx` | Three answers written |
| P6 | Polish | all | `pnpm lint` + `pnpm build` clean; optional tests |

Dependencies: P2–P5 depend on P1 (snapshot first so the original is preserved before any
edits). P4 depends on P3.

---

## 10. Acceptance-Criteria Traceability

| Requirement | Implementation | Verification |
|---|---|---|
| Remove table padding | `sx={{padding:0}}` on table `Section` | visual vs screenshot |
| Align "No Data" | reserved pill slot in status cell | visual vs screenshot |
| Per-row details button | actions column → `onViewDetails(id)` | click → panel updates |
| Loading state | `usePersonDetails` `loading` | spinner shown |
| Error state | try/catch → `error` | Alert shown |
| Not-found state | `undefined` → `notFound` | message shown |
| Success state | value → `success` → `PersonDetails` | details shown |
| Race condition guard | request-token in hook | rapid clicks show last only |
| Typescript safety | discriminated unions, no `any` | `pnpm build` passes |
| Old page comparison | `legacy/` snapshot + switcher | toggle shows before/after |
| Q&A | filled in `App.tsx` | answers present |

---

## 11. Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Editing shared `Section`/`StatusPill` breaks other sections | use per-instance `sx`; keep defaults; legacy snapshot proves no regression |
| StrictMode double-invokes effects/handlers | hook is idempotent; token + mounted guards |
| Stale async response overwrites newer one | request-token guard (core of Task 2) |
| Grid re-renders cost | memoized `columns` + `useCallback` handlers |
| Drift between legacy copy and "original" | snapshot once in P1, then never edit `legacy/` |

---

## 12. Definition of Done

- Switcher toggles between an **untouched Original** page and the **Solution** page.
- Task 1 matches `table_screenshot.png` (padding + alignment).
- Task 2 handles loading/error/not-found/success and is race-safe; table stays
  presentational, logic lives in the hook.
- Task 3 answered.
- `pnpm lint` and `pnpm build` pass with no `any` and no warnings.
- Code is small, commented where intent matters, and free of global side effects.
