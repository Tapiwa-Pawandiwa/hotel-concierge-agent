// Parses ADK's raw SSE event stream (forwarded unchanged by /api/chat) and
// yields just the text increments the guest should see -- skipping
// functionCall/functionResponse events, which are implementation detail
// (FR-004: confirmation prompts are just normal assistant text, nothing
// special to render for tool calls themselves).
export type StreamEvent =
  | { type: "text"; text: string }
  | { type: "confirmation_request"; id: string; hint: string };

// `input` is either a normal typed message, OR an answer to a pending
// confirmation -- exactly one of these two shapes, never both at once.
export async function* streamChat(
  sessionId: string,
  input: { message: string } | { confirmationId: string; confirmed: boolean }
): AsyncGenerator<StreamEvent> {
  // "message" in input checks WHICH of the two shapes we were given --
  // TypeScript then knows which fields are safe to read in each branch.
  const body =
    "message" in input
      ? { session_id: sessionId, message: input.message }
      : { session_id: sessionId, confirmation: { id: input.confirmationId, confirmed: input.confirmed } };

  const res = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    const errBody = await res.json().catch(() => ({ error: "Something went wrong." }));
    throw new Error(errBody.error || `Request failed with status ${res.status}`);
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

    const events = buffer.split("\n\n");
    buffer = events.pop() ?? "";

    for (const rawEvent of events) {
      const line = rawEvent.split("\n").find((l) => l.startsWith("data: "));
      if (!line) continue;

      let parsed: any;
      try {
        parsed = JSON.parse(line.slice("data: ".length));
      } catch {
        continue;
      }

      if (parsed?.content?.role !== "model") continue;

      for (const part of parsed.content.parts ?? []) {
        if (typeof part.text === "string" && part.text.length > 0 && parsed.partial === true) {
          yield { type: "text", text: part.text };
        }
        if (part.functionCall?.name === "adk_request_confirmation") {
          yield {
            type: "confirmation_request",
            id: part.functionCall.id,
            hint: part.functionCall.args?.toolConfirmation?.hint ?? "Please confirm to proceed.",
          };
        }
      }
    }
  }
}