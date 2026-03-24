import React, { useEffect, useState } from "react";
import { Send } from "lucide-react";
import "./styles.css";

const Tickets = () => {
  const [subject, setSubject] = useState("");
  const [description, setDescription] = useState("");
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    const checkClientAgent = async () => {
      try {
        setLoading(true);
        setError(null);

        const response = await fetch("http://localhost:4001/api/available-packages");
        if (!response.ok) {
          throw new Error(`Client agent responded with status ${response.status}`);
        }
      } catch (err) {
        setError("Client likely not running or CORS issue");
      } finally {
        setLoading(false);
      }
    };

    checkClientAgent();
  }, []);

  const submit = async (e) => {
    e.preventDefault();
    setError(null);

    if (!subject.trim() || !description.trim()) {
      setError("Subject and description are required");
      return;
    }

    setSending(true);

    try {
      const res = await fetch("http://localhost:4001/api/ticket", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          subject: subject.trim(),
          description: description.trim(),
        }),
      });

      alert("Ticket submitted.");
      setSubject("");
      setDescription("");
    } catch (err) {
      setError("Failed to submit ticket");
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="download-page">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
        <div>
          <h1 className="page-title">Tickets</h1>
          <p className="page-subtitle">Submit a ticket if you're facing any technical issues.</p>
        </div>
      </div>

      {loading && <p>Loading tickets…</p>}
      {error && <p className="error">Error: {error}</p>}

      {!loading && !error && (
        <div className="table-container form-container">
          <form className="ticket-form" onSubmit={submit}>
            <div className="form-group">
              <label>Subject</label>
              <input
                type="text"
                value={subject}
                onChange={(e) => setSubject(e.target.value)}
                placeholder="Enter subject"
              />
            </div>

            <div className="form-group">
              <label>Description</label>
              <textarea
                rows="4"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Describe your issue"
              />
            </div>

            <button
              type="submit"
              disabled={sending}
              className="submit-button"
            >
              <Send size={16} />
              {sending ? "Sending…" : "Submit"}
            </button>
          </form>
        </div>
      )}
    </div>
  );
};

export default Tickets;