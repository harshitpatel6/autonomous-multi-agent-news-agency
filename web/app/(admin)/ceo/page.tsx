"use client";

import { useState } from "react";
import { api } from "@/lib/api";

type Msg = { role: "user" | "ceo"; text: string };

export default function CEOChatPage() {
  const [messages, setMessages] = useState<Msg[]>([
    { role: "ceo", text: "Hi, I'm ALEX, the CEO Agent. Ask me about status, metrics, or issue a strategic command (e.g. \"switch to weekly mode\")." },
  ]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [mode, setMode] = useState<"ask" | "command">("ask");

  async function send() {
    const question = input.trim();
    if (!question || busy) return;
    setMessages((m) => [...m, { role: "user", text: question }]);
    setInput("");
    setBusy(true);
    try {
      const result = mode === "ask" ? await api.ceoChat(question) : await api.ceoCommand(question);
      const text = "answer" in result ? result.answer : result.response;
      setMessages((m) => [...m, { role: "ceo", text }]);
    } catch (e) {
      setMessages((m) => [...m, { role: "ceo", text: `Error reaching ALEX: ${e}` }]);
    } finally {
      setBusy(false);
    }
  }

  async function loadStatus() {
    setBusy(true);
    try {
      const { report } = await api.ceoStatus(true);
      setMessages((m) => [...m, { role: "ceo", text: report }]);
    } catch (e) {
      setMessages((m) => [...m, { role: "ceo", text: `Error reaching ALEX: ${e}` }]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <h2>CEO Chat — ALEX</h2>
      <div className="mode-toggle">
        <button className={mode === "ask" ? "" : "secondary"} onClick={() => setMode("ask")}>Ask</button>
        <button className={mode === "command" ? "" : "secondary"} onClick={() => setMode("command")}>Command</button>
        <button className="secondary" onClick={loadStatus} disabled={busy}>Get status report</button>
      </div>

      <div className="chat" style={{ marginTop: 20 }}>
        {messages.map((m, i) => (
          <div key={i} className={`chat-msg ${m.role === "user" ? "user" : "ceo"}`}>
            <strong>{m.role === "user" ? "You" : "ALEX"}:</strong> {m.text}
          </div>
        ))}
      </div>

      <div className="chat-input">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && send()}
          placeholder={mode === "ask" ? "Ask ALEX a question..." : "Issue a strategic command..."}
          disabled={busy}
        />
        <button onClick={send} disabled={busy || !input.trim()}>{busy ? "…" : "Send"}</button>
      </div>
    </div>
  );
}
