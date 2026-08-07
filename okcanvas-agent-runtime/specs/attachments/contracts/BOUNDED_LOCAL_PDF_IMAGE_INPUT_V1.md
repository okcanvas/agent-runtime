# Bounded Local PDF and Image Input V1

- One required text instruction and at most one local attachment.
- Supported signatures: PDF, PNG, JPEG.
- Maximum encrypted ingress payload: 8 MiB raw bytes.
- PDF: unencrypted, explicit EOF, structural `/Type /Page` count 1..50. PDFs whose page objects are available only through unsupported compressed object streams fail closed.
- Images: at most 10,000 x 10,000 and 20,000,000 pixels; animated PNG is rejected.
- Raw bytes never enter SQLite, Product Events, or Artifacts.
- Remote URLs, provider file IDs, OpenAI Files, File Search, Vector Stores, multiple attachments, Sessions, MCP, Handoffs, Agent-as-Tool, and orchestration composition are disabled.
