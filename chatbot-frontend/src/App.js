import React, { useState, useRef, useEffect } from "react";
import parse from 'html-react-parser';

const BOT_AVATAR = "🤖";
const USER_AVATAR = "🧑";

function App() {
  const [messages, setMessages] = useState([
    { sender: "bot", text: "Ciao! Come posso aiutarti oggi?", timestamp: new Date() }
  ]);
  const [history, setHistory]= useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const chatEndRef = useRef(null);
  const chatContainerRef = useRef(null);

  // Scroll solo se siamo quasi in fondo
  const scrollToBottomIfNeeded = () => {
    const el = chatContainerRef.current;
    if (!el) return;
    const isNearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 100;
    if (isNearBottom) {
      chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  };

  useEffect(() => {
    scrollToBottomIfNeeded();
  }, [messages]);

  const sendMessage = async () => {
    if (!input.trim()) return;

    const userMessage = {
      sender: "user",
      text: input.trim(),
      timestamp: new Date()
    };
    setMessages((msgs) => [...msgs, userMessage]);
    setInput("");
    setLoading(true);

    try {
      const res = await fetch("http://localhost:5000/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: userMessage.text }),
      });

      const data = await res.json();
      setMessages((msgs) => [
        ...msgs,
        { sender: "bot", text: data.response, timestamp: new Date() },
      ]);
      setHistory((h) =>[ ...h,input.trim()])
    } catch (error) {
      setMessages((msgs) => [
        ...msgs,
        { sender: "bot", text: "Errore di connessione con il server.", timestamp: new Date() },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === "Enter" && !loading) {
      sendMessage();
    }
  };

  const formatTime = (date) => {
    return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  };

  return (
    <div style={styles.container}>
      <h2 style={{ textAlign: "center" }}>Chatbot FAQ</h2>
      <div ref={chatContainerRef} style={styles.chatbox}>
        {messages.map((m, i) => (
          <div
            key={i}
            style={{
              ...styles.messageContainer,
              flexDirection: m.sender === "user" ? "row-reverse" : "row",
            }}
          >
            <div style={styles.avatar}>{m.sender === "user" ? USER_AVATAR : BOT_AVATAR}</div>
            <div
              style={{
                ...styles.message,
                backgroundColor: m.sender === "user" ? "#DCF8C6" : "#ECECEC",
                alignItems: "center",
              }}
            >
              <span>{parse(m.text)}</span>
              <div style={styles.timestamp}>{formatTime(m.timestamp)}</div>
            </div>
          </div>
        ))}

        {loading && (
          <div style={styles.messageContainer}>
            <div style={styles.avatar}>{BOT_AVATAR}</div>
            <div style={{ ...styles.message, backgroundColor: "#ECECEC", fontStyle: "italic" }}>
              Bot sta scrivendo...
            </div>
          </div>
        )}
        <div ref={chatEndRef} />
      </div>

      <div style={styles.inputContainer}>
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyPress}
          placeholder="Scrivi qui..."
          style={styles.input}
          disabled={loading}
          autoFocus
        />
        <button
          onClick={sendMessage}
          style={{
            ...styles.button,
            backgroundColor: input.trim() && !loading ? "#4CAF50" : "#9CCC9C",
            cursor: input.trim() && !loading ? "pointer" : "default",
          }}
          disabled={!input.trim() || loading}
        >
          Invia
        </button>
      </div>
    </div>
  );
}

const styles = {
  container: {
    maxWidth: 600,
    margin: "30px auto",
    fontFamily: "'Segoe UI', Tahoma, Geneva, Verdana, sans-serif",
    display: "flex",
    flexDirection: "column",
    height: "90vh",
  },
  chatbox: {
    flexGrow: 1,
    border: "1px solid #ccc",
    borderRadius: 10,
    padding: 10,
    overflowY: "auto",
    display: "flex",
    flexDirection: "column",
    gap: 10,
    backgroundColor: "#f9f9f9",
    marginBottom: 10,
  },
  messageContainer: {
    display: "flex",
    alignItems: "flex-end",
    gap: 10,
  },
  avatar: {
    fontSize: 28,
    userSelect: "none",
  },
  message: {
    maxWidth: "70%",
    padding: "10px 15px",
    borderRadius: 20,
    boxShadow: "0 1px 3px rgba(0,0,0,0.1)",
    display: "flex",
    flexDirection: "column",
  },
  timestamp: {
    alignSelf: "flex-end",
    fontSize: 10,
    color: "#555",
    marginTop: 5,
  },
  inputContainer: {
    display: "flex",
  },
  input: {
    flexGrow: 1,
    padding: 12,
    fontSize: 16,
    borderRadius: 20,
    border: "1px solid #ccc",
    outline: "none",
  },
  button: {
    marginLeft: 10,
    padding: "12px 25px",
    fontSize: 16,
    borderRadius: 20,
    border: "none",
    color: "white",
  },
};

export default App;
