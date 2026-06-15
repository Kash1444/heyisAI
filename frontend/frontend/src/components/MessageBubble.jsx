import React from "react";

export default function MessageBubble({ message }) {
  const isUser = message.role === "user";
  const isError = message.is_error;
  const isModelExhausted = message.error_type === "model_exhausted";

  return (
    <div
      style={{
        display: "flex",
        justifyContent: isUser ? "flex-end" : "flex-start",
      }}
    >
      <div
        style={{
          maxWidth: "75%",
          padding: "12px 14px",
          borderRadius: "12px",
          fontSize: "14px",
          lineHeight: "1.5",
          whiteSpace: "pre-wrap",

          // Fix long URLs / long strings overflowing
          wordBreak: "break-word",
          overflowWrap: "anywhere",

          background: isUser
            ? "#4285f4"
            : isError
            ? "rgba(255, 77, 79, 0.12)"
            : "#1a1a1a",

          color: isUser ? "#fff" : isError ? "#ffb3b3" : "#eaeaea",

          border: isError
            ? "1px solid #ff4d4f"
            : "1px solid #2a2a2a",
        }}
      >
        {/* MESSAGE TEXT */}
        <div>{message.content}</div>

        {/* MODEL EXHAUSTED EXTRA UI */}
        {isModelExhausted && (
          <div
            style={{
              marginTop: "10px",
              paddingTop: "10px",
              borderTop: "1px solid rgba(255,255,255,0.1)",
              fontSize: "12px",
              color: "#ff8080",
            }}
          >
            ⚠️ All AI models are currently exhausted.

            <div style={{ marginTop: "6px" }}>
              <a
                href="/model-status"
                style={{
                  color: "#ff8080",
                  textDecoration: "underline",
                }}
              >
                Check model status →
              </a>
            </div>
          </div>
        )}

        {/* SOURCES */}
        {message.sources && message.sources.length > 0 && (
          <div
            style={{
              marginTop: "10px",
              paddingTop: "10px",
              borderTop: "1px solid #333",
              fontSize: "12px",
              color: "#aaa",
            }}
          >
            <div
              style={{
                marginBottom: "6px",
                fontWeight: "600",
              }}
            >
              Sources:
            </div>

            {message.sources.slice(0, 3).map((src, i) => (
              <div
                key={i}
                style={{
                  marginBottom: "6px",
                }}
              >
                <div>{src.subject}</div>

                <div
                  style={{
                    color: "#777",
                    wordBreak: "break-word",
                    overflowWrap: "anywhere",
                  }}
                >
                  {src.sender}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}