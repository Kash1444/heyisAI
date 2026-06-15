import { useState, useRef, useEffect } from "react";
import MessageBubble from "./MessageBubble";

const SUGGESTED = [
  "What was my last Amazon order?",
  "Show internship emails from the last year",
  "Have I received any emails from NASA?",
  "What subscriptions am I paying for?",
  "Find emails mentioning hackathons",
];

export default function ChatWindow({ onLogout }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);

  const bottomRef = useRef(null);

  // Session memory ID
  const sessionId = useRef(`session-${Date.now()}`);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const sendMessage = async (text) => {
      const question = text || input.trim();
      if (!question || loading) return;

      setInput("");
      setMessages(prev => [...prev, { role: "user", content: question }]);
      setLoading(true);

      try {
        const res = await fetch("/chat", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            message: question,
            session_id: sessionId.current,
          }),
        });

        // Handle non-200 responses explicitly — this was the missing piece
        if (!res.ok) {
          const errorData = await res.json().catch(() => ({}));
          const detail = errorData.detail || "";

          setMessages(prev => [...prev, {
            role: "assistant",
            content: res.status === 504
              ? "That query took too long. Try a more specific question — mention a sender name, company, or date range."
              : res.status === 401
                ? "Your Gmail session expired. Please logout and login again."
                : `Something went wrong (${res.status}). Please try again.`,
            sources: [],
            has_results: false,
            is_error: true,
          }]);
          return;  // ← this was missing — was falling through to data.answer
        }

        const data = await res.json();

        if (data.error_type === "model_exhausted") {
          setMessages(prev => [...prev, {
            role: "assistant",
            content: data.answer,
            is_error: true,
            error_type: "model_exhausted",
            sources: [],
            has_results: false,
          }]);
          return;
        }

        setMessages(prev => [...prev, {
          role: "assistant",
          content: data.answer,
          sources: data.sources || [],
          has_results: data.has_results,
          email_count: data.email_count,
        }]);

      } catch (err) {
        setMessages(prev => [...prev, {
          role: "assistant",
          content: "Connection error. Make sure the backend is running on port 8000.",
          sources: [],
          has_results: false,
          is_error: true,
        }]);
      } finally {
        setLoading(false);  // ← always runs, clears the spinner
      }
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        height: "100vh",
        maxWidth: "900px",
        margin: "0 auto",
      }}
    >
      {/* Header */}
      <div
        style={{
          padding: "16px 24px",
          borderBottom: "1px solid #222",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          <span style={{ fontSize: "20px" }}>✉️</span>

          <span style={{ fontWeight: "600", fontSize: "16px" }}>
            Gmail AI Assistant
          </span>
        </div>

        <button
          onClick={() => {
            fetch("/auth/logout", {
              method: "POST",
            }).then(() => onLogout());
          }}
          style={{
            background: "none",
            border: "1px solid #333",
            color: "#888",
            padding: "6px 12px",
            borderRadius: "6px",
            cursor: "pointer",
            fontSize: "13px",
          }}
        >
          Logout
        </button>
      </div>

      {/* Messages */}
      <div
        style={{
          flex: 1,
          overflowY: "auto",
          padding: "24px",
          display: "flex",
          flexDirection: "column",
          gap: "16px",
        }}
      >
        {messages.length === 0 && (
          <div style={{ textAlign: "center", marginTop: "60px" }}>
            <div style={{ fontSize: "36px", marginBottom: "16px" }}>✉️</div>

            <h2 style={{ fontSize: "22px", fontWeight: "600", marginBottom: "8px" }}>
              Ask anything about your Gmail
            </h2>

            <p style={{ color: "#666", marginBottom: "32px" }}>
              I can search your entire email history instantly
            </p>

            <div
              style={{
                display: "flex",
                flexDirection: "column",
                gap: "8px",
                maxWidth: "480px",
                margin: "0 auto",
              }}
            >
              {SUGGESTED.map((s, i) => (
                <button
                  key={i}
                  onClick={() => sendMessage(s)}
                  style={{
                    background: "#1a1a1a",
                    border: "1px solid #2a2a2a",
                    color: "#ccc",
                    padding: "10px 16px",
                    borderRadius: "8px",
                    cursor: "pointer",
                    textAlign: "left",
                    fontSize: "14px",
                  }}
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg, i) => (
          <MessageBubble key={i} message={msg} />
        ))}

        {loading && (
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "10px",
              padding: "10px 14px",
              background: "#1a1a1a",
              borderRadius: "12px",
              width: "fit-content",
              color: "#aaa",
              marginBottom: "10px",
            }}
          >
            <div
              style={{
                width: "8px",
                height: "8px",
                borderRadius: "50%",
                background: "#4285f4",
              }}
            />
            Searching your Gmail...
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div
        style={{
          padding: "16px 24px",
          borderTop: "1px solid #222",
        }}
      >
        <div
          style={{
            display: "flex",
            gap: "12px",
            background: "#1a1a1a",
            border: "1px solid #2a2a2a",
            borderRadius: "12px",
            padding: "12px 16px",
          }}
        >
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask about your emails... (Press Enter to send)"
            rows={1}
            style={{
              flex: 1,
              background: "none",
              border: "none",
              color: "#ececec",
              fontSize: "15px",
              outline: "none",
              resize: "none",
              fontFamily: "inherit",
            }}
          />

          <button
            onClick={() => sendMessage()}
            disabled={!input.trim() || loading}
            style={{
              background: input.trim() && !loading ? "#4285f4" : "#2a2a2a",
              border: "none",
              borderRadius: "8px",
              padding: "8px 16px",
              color: input.trim() && !loading ? "white" : "#555",
              cursor: input.trim() && !loading ? "pointer" : "default",
              fontSize: "14px",
              fontWeight: "600",
            }}
          >
            Send
          </button>
        </div>
      </div>
    </div>
  );
}