import React, { useState, useRef, useEffect } from "react";
import { sendChatMessage } from "./api";
import type { Message } from "./types";

export function App() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const question = input.trim();
    if (!question || isLoading) return;

    setInput("");
    setError(null);

    const userMessage: Message = { role: "user", content: question };
    const updatedMessages = [...messages, userMessage];
    setMessages(updatedMessages);
    setIsLoading(true);

    try {
      const response = await sendChatMessage({
        messages: updatedMessages.map((m) => ({
          role: m.role,
          content: m.content,
        })),
      });

      const choice = response.choices?.[0];
      if (choice) {
        const assistantMessage: Message = {
          role: "assistant",
          content: choice.message.content,
          sources: choice.sources,
        };
        setMessages([...updatedMessages, assistantMessage]);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "An error occurred");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="app">
      <header className="app-header">
        <h1>Documentation Q&A</h1>
        <p>Ask questions about your documentation</p>
      </header>

      <main className="chat-container">
        <div className="messages">
          {messages.length === 0 && (
            <div className="empty-state">
              <p>Ask a question to get started.</p>
            </div>
          )}

          {messages.map((msg, idx) => (
            <div key={idx} className={`message message-${msg.role}`}>
              <div className="message-role">
                {msg.role === "user" ? "You" : "Assistant"}
              </div>
              <div className="message-content">{msg.content}</div>

              {msg.sources && msg.sources.length > 0 && (
                <div className="sources">
                  <div className="sources-header">Sources</div>
                  {msg.sources.map((source, sIdx) => (
                    <div key={sIdx} className="source-item">
                      <span className="source-path">{source.doc_source}</span>
                      <span className="source-score">
                        {(source.relevance_score * 100).toFixed(0)}% relevant
                      </span>
                      <details className="source-details">
                        <summary>Show excerpt</summary>
                        <p>{source.chunk_text}</p>
                      </details>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}

          {isLoading && (
            <div className="message message-assistant">
              <div className="message-role">Assistant</div>
              <div className="message-content loading">Thinking...</div>
            </div>
          )}

          {error && <div className="error-message">{error}</div>}

          <div ref={messagesEndRef} />
        </div>

        <form className="input-form" onSubmit={handleSubmit}>
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask a question about the documentation..."
            disabled={isLoading}
            autoFocus
          />
          <button type="submit" disabled={isLoading || !input.trim()}>
            Send
          </button>
        </form>
      </main>
    </div>
  );
}
