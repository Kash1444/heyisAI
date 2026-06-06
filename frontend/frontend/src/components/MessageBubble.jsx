import ReactMarkdown from "react-markdown";

export default function MessageBubble({ message }) {
  const isUser = message.role === "user";

  return (
    <div style={{
      display: "flex",
      flexDirection: "column",
      alignItems: isUser ? "flex-end" : "flex-start",
      gap: "8px",
    }}>
      {/* Message bubble */}
      <div style={{
        maxWidth: "85%",
        padding: "12px 16px",
        borderRadius: isUser ? "18px 18px 4px 18px" : "18px 18px 18px 4px",
        background: isUser ? "#4285f4" : "#1a1a1a",
        color: isUser ? "white" : "#ececec",
        fontSize: "15px",
        lineHeight: "1.6",
      }}>
        {isUser ? (
          <span>{message.content}</span>
        ) : (
          <ReactMarkdown>{message.content}</ReactMarkdown>
        )}
      </div>

      {/* Source citations */}
      {message.sources && message.sources.length > 0 && (
        <div style={{
          maxWidth: "85%",
          display: "flex",
          flexDirection: "column",
          gap: "6px",
        }}>
          <div style={{ color: "#555", fontSize: "12px", marginLeft: "4px" }}>
            Sources ({message.email_count} emails searched)
          </div>
          {message.sources.map((src, i) => (
            <div
              key={i}
              style={{
                background: "#111",
                border: "1px solid #2a2a2a",
                borderRadius: "8px",
                padding: "10px 12px",
                fontSize: "13px",
              }}
            >
              <div style={{
                fontWeight: "600",
                color: "#ccc",
                marginBottom: "2px",
                whiteSpace: "nowrap",
                overflow: "hidden",
                textOverflow: "ellipsis",
              }}>
                {src.subject}
              </div>
              <div style={{ color: "#666", fontSize: "12px" }}>
                {src.sender} · {src.date?.slice(0, 16)}
              </div>
              {src.snippet && (
                <div style={{
                  color: "#555",
                  fontSize: "12px",
                  marginTop: "4px",
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  whiteSpace: "nowrap",
                }}>
                  {src.snippet}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}