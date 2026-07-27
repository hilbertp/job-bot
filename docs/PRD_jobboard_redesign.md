# PRD: JobBot Dashboard Redesign

**Author:** Philipp Hilbert

**Date:** 8 June 2026

**Audience:** UX/UI Designer (contract or in-house)

**Status:** Draft for design kickoff

---

## 1. Summary

JobBot is a local job-search operating system. It scrapes postings from eight portals, scores them against the user profile, generates tailored CV and cover-letter packages, and tracks applications through to interview. The backend pipeline is mature. The interface is functional but engineer-built and has never had a design pass.

This PRD briefs a UX/UI designer to redesign the dashboard end to end. The goal is a focused, calm, decision-oriented interface that moves the user through a clear daily workflow: review new matches, decide, generate, apply, track. We are redesigning the experience and visual system, not rebuilding the pipeline.

---

## 2. Problem Statement

The current dashboard works but creates friction at exactly the moments that matter:

- **No single daily action surface.** The user has to mentally reconstruct "what is new and what do I do next" from a funnel of stages and a flat job table.
- **The decision moment is buried.** Scoring, tailored score, apply link, and document package live in different places. Deciding to apply requires stitching them together.
- **Status is opaque.** A job can be scraped, scored, tailored, generated, applied, expired, or failed. The current status chips do not tell a story or guide action.
- **The funnel view is reporting, not workflow.** Stage 1 to Stage 4 cards describe what the system did. They do not help the user act.
- **No sense of progress or momentum.** The user runs many sessions per week. There is no clear "today" and no felt progress.

The interface should make the daily loop obvious and fast, and should make every "apply / skip / generate" decision a one-glance call.

---

## 3. Goals and Non-Goals

### Goals
1. Make the daily review-and-decide loop the centre of the product.
2. Collapse each job into a single scannable unit that carries everything needed to decide: scores, location/salary fit, status, apply link, document package.
3. Give status a clear visual language that maps to "what should I do about this."
4. Surface "what is new since I last looked" without the user asking.
5. Establish a coherent, calm visual system the product can grow into.

### Non-Goals
- No change to the scraping, scoring, or document-generation logic.
- No multi-user, auth, or cloud features. This stays a local, single-user tool.
- No native mobile app. Responsive down to tablet is enough.
- Not a CRM rebuild. The outbound tracking can be refined visually but its data model stays.

---

## 4. Target User

**Primary and only user: the job seeker (Philipp).**

- Senior product professional, high agency, technically fluent, time-pressured.
- Runs the tool in short, frequent bursts (several times a day) rather than long sessions.
- Mental model is a funnel: discover, score, tailor, apply, track, interview.
- Strong preferences that drive every decision: remote or Berlin/Munich, salary floor 125k EUR, seniority at PM/PO/Lead level. Anything failing these should be visually de-prioritised, not hidden.
- Gets frustrated when the tool makes him ask twice for an obvious next step. The design should anticipate the next action.

---

## 5. The Six-Stage Journey the Design Must Support

The product exists to drive a job-search funnel. Every screen should make the user's position in this journey legible:

1. **Onboarding / profile** (interview-style capture of preferences, salary, skills, deal-breakers).
2. **Discovery** (scrape new postings across portals).
3. **Scoring** (heuristic score, then tailored score after CV customisation).
4. **Document generation** (CV + cover letter package, combined PDF).
5. **Application** (apply link or email, mark applied).
6. **CRM tracking** (outbound status, recruiter replies, interviews).

The redesign should make stages 2 through 6 first-class. Stage 1 (onboarding) is currently absent from the UI and should be designed as a proper flow.

---

## 6. Current State (what exists today)

Captured from the running dashboard for reference. The designer should treat this as the inventory to improve, not a layout to preserve.

**Navigation (left sidebar):**
- Workspace: Overview, Jobs, Runs
- Shortcuts: Shortlist, Outbound CRM, Portals
- A "last run" status panel pinned bottom-left

**Overview ("Command Center"):**
- Four KPI cards: Suitable (172), Tailored (86), Applied (32), Interviewed (0)
- Discovery banner: matches found this week vs scanned
- Collapsible funnel sections: Stage 1 Hits per Portal, Stage 2 PO/PM Shortlist, Stage 3 Tailored Shortlist (score >= 70), Stage 4 Application Outcomes
- Recent Runs list
- Primary actions: Run pipeline, Export JSON

**Jobs ("Triage Queue"):**
- Filter tabs: All, Scraped, Scored, Tailored, Applied
- Table columns: Score, Title, Company, Source, Status, Reason
- Per-row expand reveals: open posting link, polished package (HTML/PDF), cv.pdf, cover_letter.pdf, apply-via-email link, rescore, open

**Visual language today:**
- Dark theme, near-black background, green accent, monospace for system/status text
- Score shown as a small rounded green badge
- Status as a coloured dot + label chip

---

## 7. Scope and Requirements

### 7.1 Daily Home ("Today")
The new default screen. Replaces the reporting-style Command Center as the landing surface.

Requirements:
- A clear "New since last visit" section: postings scraped since the user last opened the tool, grouped and counted.
- A single primary call to action that reflects the most valuable next step (for example: "12 new matches to review" or "5 packages ready to send").
- A compact momentum indicator: applications sent this week, replies, interviews, against a felt sense of progress (not just raw counts).
- Quick access to resume an in-progress action (a generated package not yet sent, a scored job not yet decided).

### 7.2 The Job Card (most important single component)
Every job, wherever it appears, should collapse into one scannable card or row carrying:
- Heuristic score and tailored score, shown as a clear before/after when both exist.
- Fit signals at a glance: remote/location, salary vs floor (pass/borderline/fail), seniority match.
- Status mapped to a next action (see 7.3).
- Direct apply link or apply email.
- Document package state: none / generating / ready (with one-click open of the combined PDF).
- A primary action button that changes by state: Score, Generate package, Apply, Mark applied, Skip.

Design the card for fast vertical scanning of a list of 20 to 60 jobs. The user decides apply/skip/generate in one glance per card.

### 7.3 Status as Action Language
Redesign the status system so each status implies a next step. Current raw statuses: scraped, scored, tailored, generated, applied, apply_submitted, listing_expired, apply_failed, discarded. Group and visually code them into action states, for example:
- **Needs decision** (scored/tailored, no package yet)
- **Ready to send** (package generated, not applied)
- **In flight** (applied, awaiting reply)
- **Closed** (expired, failed, skipped) — visually de-emphasised
The exact grouping is open to the designer; the principle is that colour and placement should answer "what do I do about this."

### 7.4 Decision Filters
Replace generic status tabs with intent-driven filters that match how the user actually triages:
- "New today", "Needs decision", "Ready to send", "In flight", "Strong fit (tailored >= 80)"
- Persistent filter for the hard preferences (hide salary-fail and on-site-only by default, with a toggle to reveal).

### 7.5 Job Detail
The expanded view of a single job. Requirements:
- Full job description, scrollable, with the matched skills and the gap reasons highlighted.
- Score breakdown (role, skills, location components are already in the data).
- Document package preview (CV and cover letter) inline.
- Apply path made obvious and copy-friendly (link or email with prefilled subject).
- A clear honest "why this is not a higher match" note when tailored score is below a threshold.

### 7.6 Discovery / Runs
- Make "run a scrape" a calm, obvious action with live progress.
- After a run, route the user straight to the new matches, not to a report.
- Keep run history accessible but secondary.

### 7.7 Outbound CRM
- A pipeline view of applications in flight: applied, replied, interview, rejected, offer.
- Recruiter thread context (who, when, last message) where available.
- Light-touch; this supports stage 6 but is not the daily focus.

### 7.8 Onboarding (new)
- Design a first-run, interview-style flow that captures profile, preferences, salary floor, skills, and deal-breakers.
- Should feel like a conversation, not a settings form.

---

## 8. Design Principles

1. **One glance, one decision.** Every job should be decidable without clicking into it.
2. **Anticipate the next action.** The UI proposes the next step rather than waiting to be asked.
3. **Honesty over hype.** Fit and gaps are shown plainly. No inflated "match" language. A borderline salary or domain gap is visible, not hidden.
4. **Calm density.** Information-rich but never noisy. The user scans many jobs fast; reduce visual cost per item.
5. **Preferences are law.** Salary floor, remote/location, and seniority are filters by default, not afterthoughts.
6. **Momentum is felt.** The user should sense progress across a week of short sessions.

---

## 9. Information Architecture (proposed, open to revision)

- **Today** (new default): new matches, next action, weekly momentum.
- **Jobs**: the full triage queue with intent filters and the redesigned job card.
- **Pipeline / CRM**: applications in flight through to interview/offer.
- **Discovery / Runs**: trigger scrapes, view run history.
- **Profile**: preferences, onboarding, deal-breakers.

Consolidate the current Shortlist / Outbound CRM / Portals shortcuts into this cleaner structure.

---

## 10. Visual and Brand Direction

- Keep the dark, focused aesthetic. It suits a personal operating tool used in frequent bursts.
- Tighten the type system: clear hierarchy between job title, company, scores, and metadata. The current monospace-for-system look can stay as an accent but should not carry primary content.
- Establish a deliberate score colour scale (for example a calm gradient from neutral to strong) rather than a single green badge.
- Define a status colour system tied to the action language in 7.3.
- Provide a light theme as an optional deliverable, not required for v1.

---

## 11. Accessibility

- WCAG AA contrast minimum, verified against the dark theme.
- Full keyboard navigation of the triage queue (the user lives in this list).
- No meaning conveyed by colour alone; pair every status colour with a label or icon.

---

## 12. Deliverables

1. Lo-fi wireframes for: Today, Jobs (queue + card states), Job Detail, Pipeline/CRM, Onboarding.
2. Hi-fi mockups of the same in a defined design file (Figma preferred).
3. A component/design-system starter: type scale, colour tokens, score scale, status system, the job card in all states, buttons, filters.
4. A short interaction spec for the job card state machine and the daily "Today" flow.
5. Redlines or tokens sufficient for a developer to implement against (this is a server-rendered Flask app; deliver CSS-friendly tokens, not platform-specific assets).

---

## 13. Success Metrics

- Time from opening the tool to making the first apply/skip decision drops noticeably.
- The user can clear a day's new matches in one short session without asking the system "what next."
- Every job in the queue communicates its next action without expansion.
- Subjective: the tool feels like a calm cockpit, not a database with a skin.

---

## 14. Constraints

- **Tech:** Python Flask, server-rendered HTML/CSS, runs locally on localhost:5001. No SPA framework assumed. Design should be implementable in plain HTML/CSS with light JS.
- **Document rendering:** CV/CL packages are generated as PDFs via WeasyPrint from an existing HTML/CSS design system (Newsreader/Inter, rust accent). The dashboard visual language can differ from the document language but should not clash.
- **Single user, local data:** SQLite. No network/auth concerns.
- **Scope discipline:** the pipeline and data model are fixed for v1. Design within the existing data (scores, statuses, links, packages already exist).

---

## 15. Open Questions for the Designer

1. Should "Today" fully replace the funnel/reporting view, or should reporting move to a secondary "Insights" screen?
2. How much of the CRM/pipeline deserves daily prominence versus on-demand?
3. What is the right default sort for the triage queue: tailored score, recency, or action-state?
4. Should skipped/expired jobs be archived out of view entirely or kept dimmed for reference?
