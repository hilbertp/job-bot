"""Document generators (CV + cover letter), Sonnet-driven, Markdown out, HTML rendered."""
from .pipeline import (  # noqa: F401
    generate_application_package, generate_documents, load_existing_docs,
)
