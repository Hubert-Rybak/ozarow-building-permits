"""Real-source adapter package.

Modules municipal, public and private each implement:
    collect(cache: pathlib.Path, prior: dict | None = None) -> dict
The return value has exactly records, sources and warnings list keys.
Collectors must use source-level retained/unavailable metadata on retrieval failure;
missing modules, schema/truncation/loss errors are NOT synthetic empty successes.
The prior argument is the complete validated previous investment artifact.
Do not persist cookies, raw documents, contact fields or credential-bearing URLs.
"""
