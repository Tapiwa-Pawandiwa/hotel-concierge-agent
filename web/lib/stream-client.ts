// Parses ADK's raw SSE event stream (forwarded unchanged by /api/chat) and
// yields just the text increments the guest should see -- skipping
// functionCall/functionResponse events, which are implementation detail
// (FR-004: confirmation prompts are just normal assistant text, nothing
// special to render for tool calls themselves).

export async function* streamChat(sessionId: string, message: string): AsyncGenerator<string> {

    const res = await fetch("/api/chat", {
        method: "POST",
        headers: {"Content-Type": "application/json"}, 
        body: JSON.stringify({ session_id: sessionId, message }),
    });


    if (!res.ok) {
        const body = await res.json().catch(() => ({ error: "Something went wrong." }));
        throw new Error(body.error || `Request failed with status ${res.status}`);
    }

    if (!res.body) {
        throw new Error("No response stream from the server.");
    }
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
    
        // SSE events are separated by a blank line; each event's payload is
        // on a line starting with "data: ".
        const events = buffer.split("\n\n");
        buffer = events.pop() ?? ""; // last, possibly-incomplete event stays buffered
    
        for (const rawEvent of events) {
          const line = rawEvent.split("\n").find((l) => l.startsWith("data: "));
          if (!line) continue;
    
          let parsed: any;
          try {
            parsed = JSON.parse(line.slice("data: ".length));
          } catch {
            continue; // skip anything that doesn't parse -- don't crash the stream over it
          }
    
          // Only text parts from the model, in order -- ADK sends each
          // partial event as just the NEW text increment, not the full
          // message so far (confirmed empirically against the local agent),
          // so appending each one as it arrives is correct.
          if (parsed?.content?.role === "model" && parsed?.partial === true) {
              for (const part of parsed.content.parts ?? []) {
              if (typeof part.text === "string" && part.text.length > 0) {
                yield part.text;
              }
            }
          }
        }
      }

}