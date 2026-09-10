"use client";
import { useState, useRef, useEffect } from "react";
import MessageBubble from "./MessageBubble";
import { streamChat } from "@/lib/stream-client";

type Message = {
    role: "user" | "assistant";
    text: string;
};


export default function ChatWindow({ sessionId }: { sessionId: string }) {
    const [messages, setMessages] = useState<Message[]>([]);
    const [input, setInput] = useState("");
    const [isSending, setIsSending] = useState(false);
    const [pendingConfirmation, setPendingConfirmation] = useState<{ id: string; hint: string } | null>(null);
    const bottomRef = useRef<HTMLDivElement>(null);

    // Starts as "Welcome" (same on server and first client paint, so there's
    // no hydration mismatch), then corrected to a real time-of-day greeting
    // right after mount -- server clock and visitor's local clock can be in
    // different timezones, so computing this during render itself (instead
    // of in an effect) would risk React warning about mismatched SSR output.
    const [greeting, setGreeting] = useState("Welcome");
    useEffect(() => {
        const hour = new Date().getHours();
        // Clock-correct isn't the same as human-correct: 1am is technically
        // "morning" by the calendar but reads as late evening/night to an
        // actual guest, so that window gets its own branch instead of
        // falling into the plain hour < 12 check.
        let label: string;
        if (hour < 5) label = "Good Evening";
        else if (hour < 12) label = "Good Morning";
        else if (hour < 18) label = "Good Afternoon";
        else label = "Good Day";
        setGreeting(label);
    }, []);
    function isPositiveResponse(s: string): boolean {
        const v = s.trim().toLowerCase();
        return v === "y" || v === "yes" || v === "true" || v === "confirm";
    }

    useEffect(() => {
        bottomRef.current?.scrollIntoView({ behavior: "smooth" });
    }, [messages]);

    async function handleSend() {
        const text = input.trim();
        if (!text || isSending) return;

        setInput("");
        setIsSending(true);

        setMessages((prev) => [...prev, { role: "user", text }, { role: "assistant", text: "" }]);

        const wasPending = pendingConfirmation;
        setPendingConfirmation(null);

        try {
            const source = wasPending
                ? streamChat(sessionId, { confirmationId: wasPending.id, confirmed: isPositiveResponse(text) })
                : streamChat(sessionId, { message: text });

            let gotText = false;
            for await (const event of source) {
                if (event.type === "text") {
                    gotText = true;
                    setMessages((prev) => {
                        const updated = [...prev];
                        const last = updated[updated.length - 1];
                        updated[updated.length - 1] = { ...last, text: last.text + event.text };
                        return updated;
                    });
                } else if (event.type === "confirmation_request") {
                    setPendingConfirmation({ id: event.id, hint: event.hint });
                    if (!gotText) {
                        setMessages((prev) => {
                            const updated = [...prev];
                            const last = updated[updated.length - 1];
                            updated[updated.length - 1] = {
                                ...last,
                                text: 'Please reply "yes" to confirm, or anything else to cancel.',
                            };
                            return updated;
                        });
                        gotText = true;
                    }
                }
            }
        } catch (err) {
            console.error("Chat request failed:", err);
            const message =
                err instanceof Error && err.message
                    ? err.message
                    : "Sorry, something went wrong. Please try again.";
            setMessages((prev) => {
                const updated = [...prev];
                updated[updated.length - 1] = { role: "assistant", text: message };
                return updated;
            });
        } finally {
            setIsSending(false);
        }
    }

    return (
        <div className={`flex flex-col h-full max-w-2xl mx-auto p-4 ${messages.length === 0 ? "justify-center" : ""}`}>
            <div className={messages.length === 0 ? "mb-6" : "flex-1 overflow-y-auto mb-4"}>
                {messages.length === 0 ? (
                    <div className="flex flex-col items-center text-center px-6">
                        <h1 className="font-display text-4xl text-janet-ink mb-2">{greeting}.</h1>
                        <p className="text-text-secondary text-base">How may I help you today?</p>
                    </div>
                ) : (
                    <>
                        {messages.map((m, i) => (
                            <MessageBubble key={i} role={m.role} text={m.text} />
                        ))}
                        <div ref={bottomRef} />
                    </>
                )}
            </div>
            <div className="flex gap-2 items-center bg-janet-cream border border-border-subtle rounded-2xl p-3 shadow-elevation">
                <input
                    className="flex-1 bg-transparent text-janet-ink placeholder-text-muted focus:outline-none px-2"
                    placeholder="Type a message..."
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyDown={(e) => {
                        if (e.key === "Enter") handleSend();
                    }}
                    disabled={isSending}
                />
                <button
                    className="bg-janet-espresso text-janet-cream rounded-full px-5 py-2 hover:bg-janet-espresso-elevated disabled:opacity-50"
                    onClick={handleSend}
                    disabled={isSending}
                >
                    Send
                </button>
            </div>
        </div>
    );
}
