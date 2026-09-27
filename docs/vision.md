# Vision — Career Growth Engine

## Goal

A personal system focused on growing a student's professional profile:

```
profile → goals → gaps → best next actions → progress measurement
```

It is **not** primarily a job board or freelancing tool. It optimizes:
competitions, olympiads, hackathons, internships, research programs, scholarships,
summer schools, certifications, credentials and high-quality technical projects.

Opportunity Radar is just one module.

## Differentiation

A typical opportunity radar (e.g. Argus) does:

```
internet → opportunities → relevance → reminder
```

growthOS does:

```
current profile → target profile → gaps → possible actions → their value → optimal next step → updated profile
```

Example — goal: strong AI internship application.

- Strengths: ML competitions, Python, CV
- Gaps: deployment, research evidence, production backend
- Recommendation:
  1. apply to competition X
  2. finish project Y
  3. skip certification Z — low incremental CV value
  4. try program W — high reputational value

## Core concepts

- **Profile** — skills, projects, competitions, results, certifications, technologies, experience, interests.
- **Goal** — e.g. AI/ML internship, university abroad, stronger competition profile, research experience.
- **Opportunity** — competition / internship / hackathon / scholarship / program / certification,
  with deadline, eligibility, cost, location, difficulty, estimated time, source and evidence.
- **Growth Action** — not only external opportunities: take a certification, build a project,
  learn a skill, enter a competition, publish work, obtain a credential.
- **Ranking** — separate, explainable factors → Priority Score. See [scoring.md](scoring.md).
- **Credential Intelligence** — distinguish industry certification, practical skill badge,
  course certificate and participation badge; tier them S / A / B / C / Ignore for a given profile.

## Versions

| Version | Scope |
|---|---|
| **V1** | Dashboard (Do next · Opportunities · Profile gaps), manual profile, 5–10 quality sources, "best 3 things to do now" |
| **V2** | Automatic gap analysis, CV import, GitHub/project analysis, calendar/deadlines, decision history, learning/cert recommendations |
| **V3** | Gmail as a source adapter: `mail → extraction → opportunity / deadline / achievement`. Not the source of truth for the profile. |
| **V4** | Career Strategist: long-horizon roadmap ("competitive for AI internship in 9 months") that re-plans on new results, opportunities and rejections |

## First milestone

Vertical slice: user creates profile + goal → system loads real opportunities from 2–3 sources →
normalizes → computes priorities → shows Top 5 with explanations.

Until this works well: **no** Gmail, certification crawler, project generator or extra AI features.

## Success criterion (V1)

Not "many features". Success = **once a week I open the dashboard and it finds at least one thing
I didn't know about that is genuinely worth my time.**
