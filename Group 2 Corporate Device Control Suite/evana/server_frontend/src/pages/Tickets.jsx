import React, { useState, useEffect } from "react";
import "./styles.css";

const Tickets = () => {
  // States for managing tickets, loading status, errors, and expanded ticket details
  const [tickets, setTickets] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [expandedTicketId, setExpandedTicketId] = useState(null);

  useEffect(() => {
    const fetchTickets = async () => {
      try {
        const response = await fetch("/api/tickets");

        const data = await response.json();
        setTickets(data);
      } catch (e) {
        setError("Server likely not running or CORS issue");
      } finally {
        setLoading(false);
      }
    };

    fetchTickets();
  }, []);

  const handleResolveTicket = async (ticketId) => {
    if (
      !window.confirm(
        "Are you sure you want to resolve this ticket? This action cannot be undone."
      )
    ) {
      return;
    }

    try {
      // Send PATCH request to the server to update the ticket status to resolved
      const response = await fetch(`/api/tickets/${ticketId}/resolve`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ resolved: true }), // Assuming the body needs this structure
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.error || "Failed to resolve ticket");
      }

      // Update the ticket in local state to reflect the resolved status
      setTickets((prevTickets) =>
        prevTickets.map((ticket) =>
          ticket._id === ticketId ? { ...ticket, resolved: true } : ticket
        )
      );
    } catch (err) {
      setError(err.message); // Set the error message in case of failure
      console.error("Failed to resolve ticket", err);
    }
  };

    return (
    <div className="whitelist-container">
      <div>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
          <div>
            <h1 className="page-title">Tickets</h1>
            <p className="page-subtitle">Tickets submitted by employees.</p>
          </div>
        </div>
        {loading && <p className="loading-message">Loading tickets...</p>}
        {error && <p className="error">Error: {error}</p>}
        <div className="table-container">
          {!loading && !error && (
            <table className="packages-table">
              <thead>
                <tr>
                  <th scope="col">Subject</th>
                  <th scope="col">Category</th>
                  <th scope="col">Priority</th>
                  <th scope="col">Username</th>
                  <th scope="col">Submitted On</th>
                  <th scope="col">Status</th>
                </tr>
              </thead>
              <tbody>
                {tickets.map((ticket) => (
                  <React.Fragment key={ticket._id}>
                    <tr
                      onClick={() =>
                        setExpandedTicketId(
                          expandedTicketId === ticket._id ? null : ticket._id
                        )
                      }
                      className="clickable-row"
                    >
                      <td className="ticket-subject-cell">{ticket.subject}</td>
                      <td>{ticket.category}</td>
                      <td>{ticket.priority}</td>
                      <td>{ticket.username}</td>
                      <td>{new Date(ticket.timestamp).toLocaleString()}</td>
                      <td>
                        <span
                          className={`status-badge ${
                            ticket.resolved
                              ? "resolved"
                              : "open"
                          }`}
                        >
                          {ticket.resolved ? "Resolved" : "Open"}
                        </span>
                      </td>
                    </tr>
                    {expandedTicketId === ticket._id && (
                      <tr>
                        <td colSpan="6" className="expanded-row-content">
                          <div className="description-block">
                            <p>{ticket.description}</p>
                            {!ticket.resolved && (
                              <button
                                onClick={() => handleResolveTicket(ticket._id)}
                                className="request-button"
                              >
                                Resolve
                              </button>
                            )}
                          </div>
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
};

export default Tickets;
