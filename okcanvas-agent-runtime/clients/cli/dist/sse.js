import { CliError } from "./config.js";
export async function* parseSseJson(stream) {
    const reader = stream.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let dataLines = [];
    const dispatch = () => {
        if (dataLines.length === 0)
            return null;
        const raw = dataLines.join("\n");
        dataLines = [];
        let payload;
        try {
            payload = JSON.parse(raw);
        }
        catch {
            throw new CliError("CLI_SSE_DATA_INVALID", "Control API persisted SSE returned invalid JSON");
        }
        if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
            throw new CliError("CLI_SSE_DATA_INVALID", "Control API persisted SSE returned a non-object payload");
        }
        return payload;
    };
    while (true) {
        const { done, value } = await reader.read();
        buffer += decoder.decode(value, { stream: !done });
        const lines = buffer.split(/\r?\n/u);
        buffer = done ? "" : (lines.pop() ?? "");
        for (const line of lines) {
            if (line === "") {
                const event = dispatch();
                if (event)
                    yield event;
            }
            else if (line.startsWith("data:")) {
                dataLines.push(line.slice(5).replace(/^ /u, ""));
            }
        }
        if (done)
            break;
    }
    if (buffer) {
        for (const line of buffer.split(/\r?\n/u)) {
            if (line.startsWith("data:"))
                dataLines.push(line.slice(5).replace(/^ /u, ""));
        }
    }
    const event = dispatch();
    if (event)
        yield event;
}
//# sourceMappingURL=sse.js.map