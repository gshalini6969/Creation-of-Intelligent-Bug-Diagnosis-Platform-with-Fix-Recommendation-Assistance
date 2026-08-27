import { useState } from "react";
import type { ReactNode } from "react";
import { NavLink } from "react-router-dom";
import "./Layout.css";

const NAV_ITEMS = [
  { to: "/", label: "Home", end: true },
  { to: "/submit-bug", label: "Submit Bug" },
  { to: "/analyze-bug", label: "Analyze Bug" },
  { to: "/knowledge-base", label: "Knowledge Base" },
  { to: "/dashboard", label: "Dashboard" },
];

interface LayoutProps {
  children: ReactNode;
}

export default function Layout({ children }: LayoutProps) {
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <div className="layout">
      <header className="layout__header">
        <div className="layout__brand">
          <span className="layout__brand-line">Intelligent Bug Diagnosis Platform</span>
          <span className="layout__brand-line layout__brand-line--sub">
            &amp; Fix Advisor
          </span>
        </div>

        <button
          type="button"
          className="layout__menu-toggle"
          aria-label="Toggle navigation menu"
          aria-expanded={menuOpen}
          onClick={() => setMenuOpen((open) => !open)}
        >
          <span />
          <span />
          <span />
        </button>

        <nav className={menuOpen ? "layout__nav layout__nav--open" : "layout__nav"}>
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              onClick={() => setMenuOpen(false)}
              className={({ isActive }) =>
                isActive ? "layout__nav-link layout__nav-link--active" : "layout__nav-link"
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
      </header>

      <main className="layout__main">{children}</main>

      <footer className="layout__footer">
        <p>Intelligent Bug Diagnosis Platform — Intelligent Bug Diagnosis Platform with Fix Recommendation Assistance</p>
      </footer>
    </div>
  );
}
