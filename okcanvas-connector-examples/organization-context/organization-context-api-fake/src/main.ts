import { createOrganizationContextFake } from "./server.js";

const port = Number(process.env.PORT ?? "19081");
const host = process.env.HOST ?? "127.0.0.1";
createOrganizationContextFake().server.listen(port, host, () => {
  console.log(`organization-context-api-fake example listening on http://${host}:${port}`);
});
