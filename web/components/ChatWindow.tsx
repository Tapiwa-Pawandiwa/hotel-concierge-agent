"use client"; // this component runs in the visitor's browser, not on our
// server -- required because it reacts to typing/clicking.

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
                        // Some turns raise the confirmation with no narrated text
                        // at all -- make sure the guest sees something.
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
            setMessages((prev) => {
                const updated = [...prev];
                updated[updated.length - 1] = {
                    role: "assistant",
                    text: "Sorry, something went wrong. Please try again.",
                };
                return updated;
            });
            console.error("Chat request failed:", err);
        } finally {
            setIsSending(false);
        }
    }

    return (
        <div className="flex flex-col h-full max-w-2xl mx-auto p-4">
            <div className="flex-1 overflow-y-auto mb-4">
                {messages.map((m, i) => (
                    <MessageBubble key={i} role={m.role} text={m.text} />
                ))}
                <div ref={bottomRef} />
            </div>
            <div className="flex gap-2">
                <input
                    className="flex-1 border rounded-full px-4 py-2 bg-white text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="Type a message..."
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyDown={(e) => {
                        if (e.key === "Enter") handleSend();
                    }}
                    disabled={isSending}
                />
                <button
                    className="bg-blue-600 text-white rounded-full px-5 py-2 disabled:opacity-50"
                    onClick={handleSend}
                    disabled={isSending}
                >
                    Send
                </button>
            </div>
        </div>
    );

}