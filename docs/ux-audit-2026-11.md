# UX audit — November 2026

Goal: make growthOS clearly better to use — fewer steps, clearer reasons, clearer screens — without
adding features.

## How it was tested

- `main` at `3852503`, backend on SQLite (seeded profile, curated + live Devpost data: 45
  opportunities, 50 candidates), Next.js dev server.
- Walked every journey below as a first-time user (fresh seed) and as a returning user (decisions,
  plans and imports already made), at 360 px and 1280 px, with the OS in light and in dark mode.
- Google Calendar and Gmail were not exercised: their tokens use Windows DPAPI, which does not run on
  the Linux test machine.
- Measurements come from the DOM (element sizes, positions, page heights), not from eyeballing.
- Baseline screenshots: [docs/screenshots/ux-audit/](screenshots/ux-audit/).

## Journeys and step counts (before)

| Journey | Steps today | Notes |
|---|---|---|
| First run: see Top 5 | 0 (seed makes a profile and an active goal) | In light OS mode the page is white with dark cards and the headline is unreadable (#1). |
| Set skill levels on the profile | blocked | Skill names are 0 px wide; 16 dropdowns without a visible name (#2). |
| Ranked list → why is this #1? | 1 (open "Proč právě tohle?") | Two of three reasons repeat the same skills (#5). On a phone the factor bars are 0 px wide (#7). |
| Decide on an item | 1 | Card vanishes with no confirmation (#3). |
| Undo an accidental "Přeskočit" | 3 + scroll | Scroll past the remaining cards, open "Rozhodnuté a skryté", click "Vrátit" (#3). |
| Plan an item for this week | 2 (Naplánovat → Uložit plán) | Then the dashboard still shows it as untouched; checking it is planned needs the Týden tab (+1) (#4). |
| Filter opportunities by kind | 1 chip | On a phone the list starts 4,443 px down the page. No text search. |
| Import a CV (paste text) | 1 + 3 per proposal | Headings like "Projekty" become proposals, bullets stay in titles, no way to dismiss (#6). |
| Edit profile basics | 1 save | Works. |
| No active goal | 3 (link → Nastavit jako aktivní → back) | Rare: the seed always activates a goal. |
| Backend down | 0 | Dashboard says which command to run. Good. |

## Friction points, ranked

Impact counts how often a user hits the problem and how badly it blocks them. Effort: S (< 1 h,
one or two files), M (half a day, backend + frontend or a new test), L (new feature or redesign).

| # | Problem | Evidence | Impact | Effort |
|---|---|---|---|---|
| 1 | **Light OS theme breaks every page.** `globals.css` sets `body { background: var(--background) }`, which is unlayered and beats Tailwind's `bg-zinc-950`; in light mode the body turns white while cards and text stay dark-theme colours. | Headline "Co mě posune nejvíc?" (zinc-50 on white), the goal switcher and the novelty line are unreadable. Windows defaults to light mode. [before](screenshots/ux-audit/dash-desktop-light.png) | High | S |
| 2 | **Skill names are invisible on the profile.** `w-full` from the shared input class wins over `w-32`, so each select takes the whole row and the `truncate` label shrinks to 0 px. | All 16 labels measure 0 px at 360 px and at 1280 px; the selects also overflow the card at 360 px. [before](screenshots/ux-audit/profile-360-dark.png) | High | S |
| 3 | **Decisions give no feedback and undo is buried.** "Přeskočit", "Nezajímá mě" and "Už znám" remove the card silently; "Užitečné" just removes its own button. | Undo needs 3 actions and a scroll to the collapsed "Rozhodnuté a skryté" list at the end of Do next (2,500 px down on a phone). | High | M |
| 4 | **Planning an item does not mark it as planned.** `POST /plans` with a target records no `planned` decision, so the "Naplánováno" badge on the dashboard never appears. | After planning the #1 item it is still #1, unmarked; the badge exists in code but nothing sets it since V2 replaced the button with the plan form. | Med-high | M |
| 5 | **Reasons repeat themselves.** "Pokrývá tvoje mezery: A, B, C" and "Sedí k cíli: B, D, A, C" list the same skills. | In 4 of the 5 Top-5 cards both reasons name the same skills, so the third reason slot is wasted. | Medium | S |
| 6 | **CV text import creates junk proposals.** Every non-empty line is a proposal: section headings ("Projekty", "Soutěže") and bullet markers stay; there is no dismiss. | 5-line CV → 5 proposals, 2 of them headings; titles start with "- ". | Medium | S (cleanup) / M (dismiss) |
| 7 | **Factor bars are 0 px on phones.** Grid `9rem 1fr 3.5rem` inside a 212 px column leaves nothing for the bar. | All 8 bars 0 px at 360 px; only the numbers remain. | Medium (narrow windows) | S |
| 8 | **Touch targets below 44 px.** | 73 of 101 interactive elements on the dashboard at 360 px; decision buttons 26 px, nav links 20 px tall. | Medium | S |
| 9 | **Low-contrast helper text.** `text-zinc-500` on `zinc-900` is about 3.9:1 for 11–14 px text (WCAG AA needs 4.5:1). | Goal subtitles, "Rozhodnuté a skryté", source warnings, history dates. | Medium | S |
| 10 | **Workspace feedback appears off-screen on phones.** Messages render above the tabs while the buttons are at the bottom of long forms. | "Uložit plán" sits at 1,574 px; its confirmation appears at 459 px. The message also tells the user to sync Google even when no calendar is connected. | Low-med | S |

Also noted, not in the top 10:
- The dashboard heading "Do next" is English in a Czech UI; "API ok · sqlite" is developer detail on
  the main screen and duplicates nothing the user acts on.
- Plan form always shows the autumn DST selector, a rare edge case, as a full field.
- Workspace tabs do not update the URL, so Back and reload lose the tab.
- No deadline-sorted view ("what closes soon") and no text search across 45 opportunities.
- The "Podklady zůstávají lokálně" heading describes privacy, not the task (importing a CV).

## Plan

Implement the top five that are S or M, one PR per item or small related group:

1. #1 Light-mode theme fix.
2. #2 + #7 Layout breaks: visible skill names, factor bars on phones.
3. #3 Decision confirmation with one-click undo.
4. #4 Planning marks the item as planned (backend, test first).
5. #5 Reasons without repeated skills (backend, test first).
