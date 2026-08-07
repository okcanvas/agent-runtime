# Query-directed Bounded Project Read-only Inspection Tool

The Tool reads only the server-configured `OKCANVAS_READONLY_WORKSPACE_ROOT`. It follows no
symlinks, excludes generated/dependency/Reference directories, reads text candidates only, runs no
process, uses no network, and writes no file.

Selection is query-directed: rare exact terms and code-registration/definition structure are scored
at line-window level, implementation source is preferred unless the question targets tests/docs or a
client, and the Tool returns at most four repository-relative evidence windows. Aggregate evidence is
bounded to 5,000 characters, each excerpt to 16 lines and 1,600 characters.
