# Workspace Boundary Constitution

The workspace root is a management and integration boundary, not an executable product package.
Runtime, Product CLI, Connector, and Example remain independently installable and packageable.
A shared workspace must not create shared virtual environments, source imports, hidden relative-path
runtime dependencies, or production dependence on examples.
