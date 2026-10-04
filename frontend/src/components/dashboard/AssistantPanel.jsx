import { useEffect, useRef, useState } from "react";
import { api } from "../../services/api";
import { Icon } from "../ui/Icon";

export default function AssistantPanel({ open, onClose }) {
  const [messages, setMessages] = useState([
    { role: "assistant", text: "Hi, I'm Veya. Ask about your costs, waste findings, forecasts, or emissions." },
  ]);
  const [history, setHistory] = useState([]);
  const [question, setQuestion] = useState("");
  const [error, setError] = useState("");
  const [sending, setSending] = useState(false);
  const inputRef = useRef(null);
  const messagesRef = useRef(null);

  useEffect(() => {
    if (!open) return undefined;
    inputRef.current?.focus();
    const closeOnEscape = (event) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [open, onClose]);

  useEffect(() => {
    messagesRef.current?.scrollTo({ top: messagesRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, sending]);

  async function submitQuestion(event) {
    event.preventDefault();
    const prompt = question.trim();
    if (!prompt || sending) return;

    setQuestion("");
    setError("");
    setMessages((current) => [...current, { role: "user", text: prompt }]);
    setSending(true);
    try {
      const response = await api.askAssistant(prompt, history);
      setMessages((current) => [...current, { role: "assistant", text: response.answer, route: response.route }]);
      setHistory((current) => [...current, { q: prompt, a: response.answer }].slice(-6));
    } catch (requestError) {
      setError(requestError.message || "The assistant request failed.");
    } finally {
      setSending(false);
    }
  }

  if (!open) return null;

  return (
    <div
      className="assistant-backdrop"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <section className="assistant-panel" role="dialog" aria-modal="true" aria-labelledby="assistant-title">
        <header className="assistant-head">
          <div>
            <h2 id="assistant-title">Ask Veya</h2>
            <span>Workspace-grounded assistant</span>
          </div>
          <button type="button" className="assistant-close" onClick={onClose} aria-label="Close assistant">
            <Icon name="close" />
          </button>
        </header>

        <div className="assistant-messages" ref={messagesRef} aria-live="polite">
          {messages.map((message, index) => (
            <div className={`assistant-message ${message.role}`} key={`${message.role}-${index}`}>
              {message.route && <span className="assistant-route">{message.route}</span>}
              <p>{message.text}</p>
            </div>
          ))}
          {sending && (
            <div className="assistant-message assistant">
              <span className="assistant-pending"><Icon name="loading" /> Veya is thinking</span>
            </div>
          )}
        </div>

        {error && <div className="assistant-error" role="alert">{error}</div>}

        <form className="assistant-form" onSubmit={submitQuestion}>
          <label className="sr-only" htmlFor="assistant-question">Message Veya</label>
          <textarea
            id="assistant-question"
            ref={inputRef}
            rows="2"
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            placeholder="Ask about your cloud data"
            disabled={sending}
          />
          <button type="submit" className="btn btn-primary" disabled={sending || !question.trim()} aria-label="Send message">
            <Icon name="send" />
          </button>
        </form>
      </section>
    </div>
  );
}