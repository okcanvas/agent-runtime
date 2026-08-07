# EXAMPLE-ISSUE-002 — Import side effect kept the test process alive

The first implementation started the HTTP listener from `server.ts` during module import. Node tests
passed but the process remained alive until the external timeout. The server factory and executable
entrypoint are now separated: `server.ts` exports only `createGroupwareFake`, while `main.ts` owns
listener startup. A regression test imports the module without opening a port.
