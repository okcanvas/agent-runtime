"""Reference import is intentionally disabled after STEP000.

A future reference refresh must be a new reviewed STEP that records source URL,
archive SHA-256, extracted tree SHA-256, license, and code findings.
"""

raise SystemExit("Reference refresh requires an explicit reviewed STEP; do not mutate the baseline in place.")
