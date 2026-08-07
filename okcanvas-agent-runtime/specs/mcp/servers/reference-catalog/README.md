# Reference Catalog MCP server

This built-in stdio server exposes only `search_reference` and `read_reference_file`.
It delegates to the immutable STEP006 Reference Catalog Service. It cannot write, execute,
import, install, fetch, or mutate `/reference` content.
