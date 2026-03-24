import React, { useEffect, useState } from 'react';
// Import download icon for install button
import { HardDriveDownload, RefreshCw } from 'lucide-react';
import "./styles.css";

const DownloadPage = () => {
    // List of packages to display
    const [packages, setPackages] = useState([]);
    // Flag to manage loading state
    const [loading, setLoading] = useState(true);
    // Track which package is being installed
    const [installing, setInstalling] = useState(null);
    // Flag to manage system update state
    const [updating, setUpdating] = useState(false);
    // Error state to handle issues
    const [error, setError] = useState(null);

    useEffect(() => {
        const fetchPackages = async () => {
            try {
                setLoading(true);
                setError(null);

                // Localhost because client runs on same device as frontend
                const clientAgentBase = `http://localhost:4001`;
                const agentEndpoint = `${clientAgentBase}/api/available-packages`;

                // Fetch list of available packages from the client agent
                // The agent is responsible for getting the master list and filtering
                // out packages that are already installed
                const agentRes = await fetch(agentEndpoint);
                if (!agentRes.ok) {
                    const errorText = await agentRes.text();
                    throw new Error(`Client agent responded with status ${agentRes.status}: ${errorText}`);
                }
                const agentData = await agentRes.json();

                // The agent now returns the full package objects that are available for download
                setPackages(agentData.packages || []);
            } catch (err) {
                setError("Client likely not running or CORS issue");
            } finally {
                setLoading(false);
            }
        };

        fetchPackages();
    }, []);

    const installPackage = async (pkg) => {
        // Prevent starting installation if another package is being installed
        if (installing) {
            window.alert(`Currently installing ${installing}...`);
            return;
        }

        // Mark the package as being installed
        setInstalling(pkg.name);
        setError(null);

        // Localhost because client runs on same device as frontend
        const clientAgentBase = `http://localhost:4001`;
        const installEndpoint = `${clientAgentBase}/api/install`;

        try {
            const headers = { "Content-Type": "application/json" };
            const res = await fetch(installEndpoint, {
                method: "POST",
                headers,
                body: JSON.stringify({ packageName: pkg.name }),
            });

            await res.json().catch(() => ({}));
            window.alert(`Completed installing ${pkg.name}.`);
            window.location.reload();
        } catch (e) {
            setError(`Failed to send installation request`);
        } finally {
            setInstalling(null);
        }
    };

    const handleSystemUpdate = async () => {
        if (installing || updating) return;

        if (!window.confirm("Are you sure you want to update all system packages? This process may take some time.")) {
            return;
        }

        setUpdating(true);
        setError(null);

        // Localhost because client runs on same device as frontend
        const clientAgentBase = `http://localhost:4001`;
        const updateEndpoint = `${clientAgentBase}/api/update-system`;

        try {
            const res = await fetch(updateEndpoint, {
                method: "POST",
                headers: { "Content-Type": "application/json" }
            });

            if (!res.ok) {
                const data = await res.json().catch(() => ({}));
                throw new Error(data.error || `Server error: ${res.status}`);
            }

            window.alert("System update completed successfully.");
        } catch (e) {
            setError(`Failed to update system`);
        } finally {
            setUpdating(false);
        }
    };

    return (
        <div className="download-page">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
                <div>
                    <h1 className="page-title">Downloads</h1>
                    <p className="page-subtitle">Packages available for download. If a package you need is not listed, please raise a ticket.</p>
                </div>
                <button 
                    className="request-button" 
                    onClick={handleSystemUpdate} 
                    disabled={updating || !!installing}
                    style={{ display: 'flex', alignItems: 'center', gap: '8px' }}
                >
                    <RefreshCw size={18} className={updating ? "spin" : ""} />
                    {updating ? 'Updating...' : 'Update system'}
                </button>
            </div>

            {loading && <p>Loading packages…</p>}
            {error && <p className="error">Error: {error}</p>}

            {!loading && !error && (
                <div className="table-container">
                    <table className="packages-table">
                        <thead>
                            <tr>
                                <th>Package Name</th>
                                <th>Action</th>
                            </tr>
                        </thead>
                        <tbody>
                            {packages.map((pkg) => (
                                <tr key={pkg._id || pkg.id || pkg.file || pkg.name}>
                                    <td>{pkg.name}</td>
                                    <td className="action-cell">
                                        <button className="request-button install-button" onClick={() => installPackage(pkg)} disabled={installing === pkg.name || updating}>
                                            <HardDriveDownload />
                                            {installing === pkg.name ? 'Installing...' : 'Install'}
                                        </button>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}
        </div>
    );
};

export default DownloadPage;
