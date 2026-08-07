# STEP003 eval

The canonical acceptance case starts with one failing quantity test, permits modification only of
`src/inventory/pricing.py`, requires a non-empty patch, and accepts only when the independent pytest
validator changes from one failing test to at least one passing test while the source fixture remains
unchanged.
