# Data model and revision guide

A term contains canonical name, definition, classification, scoped aliases, external-system
capability bindings, provenance, status, term revision, and row version. Each successful mutation
increments one tenant catalog revision and appends one immutable change record. Deletion retires the
term so historical evidence remains explainable.
