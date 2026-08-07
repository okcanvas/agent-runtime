# Product-owned Skill Package V1

## Purpose

A Product Skill is a server-installed immutable capability package. It changes Agent behavior only by
adding authenticated instructions and bounded UTF-8 static resources to an Agent that explicitly
names the Skill. It is not an executable plugin, client extension, Shell package, or dependency
installer.

## Package layout

```text
specs/skills/<skill-id>/
  skill.json
  instructions.md
  resources/
    <declared UTF-8 text resources>
```

Every file must be declared. Symbolic paths, undeclared files, executable files, hidden resources,
path escape, binary data, and invalid UTF-8 are rejected.

## Immutable identity

The Runtime calculates and exposes:

- manifest SHA-256;
- instructions SHA-256 and byte length;
- each resource path, media type, SHA-256, and byte length;
- one package SHA-256 over the exact file inventory.

The package identity is included in the Agent Runtime binding. Any package change requires a new
governed preflight and exact confirmation.

## Agent binding

An Agent declares at most one Skill through `skills`. The Skill manifest contains:

- allowed Agent IDs;
- allowed input modes;
- allowed output contracts;
- required Function Tools;
- required MCP servers;
- required Hosted Tools;
- required workspace mode.

A Skill cannot add a capability. Every required capability must already be declared by the Agent.
The initial V1 package requires no Tool, MCP, Hosted Tool, workspace, Session, Shell, or executable
code.

## Runtime behavior

The Product Runtime composes base Agent instructions, Skill instructions, and declared static
resources in a deterministic authenticated block. The model receives no package filesystem path.
Service clients receive metadata and hashes only, not instruction or resource contents.

## Explicitly excluded

- user-uploaded Skill packages;
- ZIP installation or marketplace installation;
- arbitrary Python or JavaScript;
- Shell or filesystem execution;
- dynamic dependency installation;
- Tool Search or model-selected Skill discovery;
- client-side execution;
- tenant-specific mutable Skill versions;
- automatic permission expansion.
