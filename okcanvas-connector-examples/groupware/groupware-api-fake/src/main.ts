import { createGroupwareFake } from "./server.js";

const port = Number(process.env.PORT ?? "19080");
const host = process.env.HOST ?? "127.0.0.1";
createGroupwareFake().server.listen(port, host, () => {
  console.log(`groupware-api-fake example listening on http://${host}:${port}`);
});
