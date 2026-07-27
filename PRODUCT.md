# Product

## Register

product

## Users

One person: Philipp, a senior product manager / CFO-background candidate running
his own automated job search. He opens the surfaces (local Flask dashboard,
static GitHub Pages dashboard, email digest) once or twice a day, usually
mid-task ("what came in today, what do I apply to next?"), on a laptop, in
either light or dark OS theme. No other users, no onboarding funnel.

## Product Purpose

job-bot scrapes job boards, scores every posting against Philipp's CV with an
LLM, generates tailored application packages, and surfaces the results for
triage. Success = opening a dashboard and, within seconds, seeing today's
best-scoring postings with a working apply route and ready-to-send documents.
The tool must never overclaim (a link that dead-ends into a paywall, a
"submitted" that wasn't) - honesty of state is a core feature.

## Brand Personality

Pragmatic, dense, trustworthy. Feels like a well-kept operations console, not
a marketing page. Numbers and states over decoration.

## Anti-references

- Generic AI-generated SaaS landing aesthetics (hero metrics, gradient text,
  glassmorphism, card grids for everything).
- Job-board consumer sites (LinkedIn feed noise, promotional banners).
- Anything that hides pipeline failures behind cheerful empty states.

## Design Principles

1. **State honesty first**: errors, missing apply routes, and unscored rows are
   shown plainly; never dress up a broken pipeline as a quiet day.
2. **Triage speed**: the primary read is a scan of a dense table; every design
   choice serves faster scanning (alignment, contrast, filters, sorting).
3. **Earned familiarity**: standard table/filter/console idioms; no invented
   affordances. The tool should disappear into the task.
4. **Self-contained artifacts**: the static dashboard ships as one HTML file
   with zero external assets; design within that constraint.

## Accessibility & Inclusion

WCAG AA contrast for all text, keyboard-operable controls with visible focus,
`prefers-color-scheme` support (both themes first-class),
`prefers-reduced-motion` respected. Single known user, but no shortcuts taken.
