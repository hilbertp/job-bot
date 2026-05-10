"""profile_distiller — turns a corpus of CVs / cover letters / website pages
into a single normalized capabilities document (`data/profile.compiled.yaml`).

PRD references: §7.4 (Profile distillation), §3.1 goal 2.

The corpus is layered:
  data/corpus/cvs/PRIMARY_*       — single source of truth for facts
  data/corpus/cvs/*               — historical / role-specific phrasings
  data/corpus/cover_letters/*     — voice extraction only, never facts
  data/corpus/website/*           — fetched true-north.berlin pages

`distiller.rebuild_compiled_profile()` is the only public entrypoint a CLI
command should call. It is idempotent: running it twice on an unchanged corpus
produces an identical output file (modulo a `compiled_at` timestamp).

The distiller never writes to `data/profile.yaml` — that file is the user's
hand-edited hard preferences and is treated as read-only by the distiller.
"""
from .distiller import rebuild_compiled_profile  # noqa: F401
