import React, { useEffect, useState } from "react";
import "./styles.css";

export default function GitPage() {
  const [repos, setRepos] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let mounted = true;
    const load = async () => {
      try {
        const res = await fetch("http://localhost:4001/api/git");
        if (!res.ok) throw new Error(`Server returned ${res.status}`);
        const items = await res.json();
        const repoNames = Array.isArray(items) ? items.map(it => it.repo).filter(Boolean) : [];
        if (mounted) {
          setRepos(repoNames);
          setError(null);
        }
      } catch (e) {
        if (mounted) setError("Client likely not running or CORS issue");
      } finally {
        if (mounted) setLoading(false);
      }
    };
    load();
    return () => { mounted = false; };
  }, []);

  return (
    <div className="download-page">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
        <div>
          <h1 className="page-title">Git</h1>
          <p className="page-subtitle">
            Repositories you have access to. If a repo you need is not listed, please raise a ticket.
          </p>
        </div>
      </div>

      {loading && <p>Loading repositories…</p>}
      {error && <p className="error">Error: {error}</p>}

      {!loading && !error && (
        <div className="table-container">
          <table className="packages-table">
            <thead>
              <tr>
                <th>Repository</th>
              </tr>
            </thead>
            <tbody>
              {repos.length ? (
                repos.map((repo, i) => (
                  <tr key={i}>
                    <td>{repo}</td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td>No repositories found.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}