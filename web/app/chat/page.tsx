"use client"; // needs to run in the browser, since it creates a random ID
              // and passes it to ChatWindow.

import { useState } from "react";
import ChatWindow from "@/components/ChatWindow";

export default function ChatPage() {
  // Generate ONE random ID per visit, the moment the page loads, and keep
  // it in memory only for this browser tab -- this IS the "session" that
  // ties all of this visitor's messages together (FR-009: never saved to
  // localStorage/cookies, so it's gone the moment the tab closes).
  //
  // useState(() => crypto.randomUUID()) -- passing a FUNCTION to useState
  // (instead of a plain value) means "only run this once, the very first
  // time," rather than generating a brand-new random ID on every redraw.
  const [sessionId] = useState(() => crypto.randomUUID());

  return (
    <main className="h-screen bg-white">
      <ChatWindow sessionId={sessionId} />
    </main>
  );
}