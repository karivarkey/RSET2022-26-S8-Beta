import React from "react";
import { NavLink } from "react-router-dom";
import {
  Download,
  MessageSquare,
  GitBranch
} from "lucide-react";

import "./Sidebar.css";

const Sidebar = () => {
  // Returns the 'active' class if the link is active, otherwise it returns an empty string.
  const getNavLinkClass = ({ isActive }) => (isActive ? "active" : "");

  return (
    // Use the 'sidebar' class from Sidebar.css
    <aside className="sidebar">
      <div className="sidebar-header">Dashboard</div>

      <nav className="sidebar-nav">
        <NavLink to="/" className={getNavLinkClass} end>
          <Download />
          <span>Downloads</span>
        </NavLink>

        <NavLink to="/git" className={getNavLinkClass}>
          <GitBranch />
          <span>Git</span>
        </NavLink>

        <NavLink to="/tickets" className={getNavLinkClass}>
          <MessageSquare />
          <span>Tickets</span>
        </NavLink>
      </nav>
    </aside>
  );
};

export default Sidebar;