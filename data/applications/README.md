# Application Knowledge Base

Living knowledge base for Philipp's job applications. Goal: no fact, story, claim, or
preference ever has to be re-explained in a new session.

## Files

| File | Contents |
|---|---|
| [PROFILE.md](PROFILE.md) | Full fact base: ventures, stations, deep facts per employer, claim inventory with canonical phrasing, constraints, known hard gaps |
| [STORIES_AND_VOICE.md](STORIES_AND_VOICE.md) | Document rules, voice/style preferences (with verbatim feedback), story bank for screeners and interviews |
| [APPLICATIONS.md](APPLICATIONS.md) | Ledger: every package built (PDF ↔ sources ↔ angle ↔ rate), DB status tables, channel notes |
| `cv_*.md`, `cl_*.md`, `email_*.md`, `anschreiben_*.md` | Tailored document sources, reusable as templates |
| `general_cv_clean.md` | The clean general CV source (rebuilt 2026-06-08 after the projuncta/lovable incident) |

## Operating rules

1. **Read PROFILE.md and STORIES_AND_VOICE.md before scoring or writing anything.**
2. **Extend as you go:** every new application appends a row + angle note to APPLICATIONS.md
   in the same turn the package is built. Every newly learned fact about Philipp goes into
   PROFILE.md (or STORIES_AND_VOICE.md if it is voice/story material) immediately.
3. **Never** put credentials, API keys, or passwords in these files.
4. Scores and statuses live in `data/jobbot.db` (source of truth); APPLICATIONS.md tables
   are regenerated snapshots, not hand-maintained.
5. Document hard rules (no lovable URLs, www.true-north.berlin, no em-dashes) are in
   STORIES_AND_VOICE.md and are non-negotiable.
