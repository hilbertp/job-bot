# Corpus

This directory holds the source material the profile distiller reads to build
`data/profile.compiled.yaml`. See PRD §7.4.

## Layout

```
corpus/
├── cvs/
│   ├── PRIMARY_<your-canonical-CV>.pdf    ← exactly one file with PRIMARY_ prefix
│   └── *.{pdf,docx,md,txt}                ← any number of historical / role-specific CVs
├── cover_letters/
│   └── *.{pdf,docx,md,txt}                ← any number of cover letters you've written
└── website/
    └── *.md                                ← snapshots fetched by `jobbot profile fetch-website`
```

## Rules the distiller enforces

1. **Exactly one `PRIMARY_*` file in `cvs/`.** This is the source of truth for
   facts (employers, dates, achievements, titles). If a non-primary CV
   contradicts the primary, the primary wins.

2. **Cover letters contribute only voice signal.** They're never used to
   extract facts about your career, only your tone, sample phrasings, and
   things you would never write.

3. **Website pages contribute voice + domain context** but never override
   CV facts.

4. **Files smaller than 200 characters are ignored** (likely empty or stub
   files).

5. **Hidden files (`.gitkeep`, `.DS_Store`) are skipped silently.**

## Refreshing

- New CV / cover letter? Drop it in the matching folder and run:
    `jobbot profile rebuild`
- Updated your website at true-north.berlin? Run:
    `jobbot profile fetch-website && jobbot profile rebuild`

The compiled output goes to `data/profile.compiled.yaml`. Review it before
the next pipeline run picks it up.

## Privacy

This entire directory is gitignored by default. The corpus contains your
real career history — never commit it.
