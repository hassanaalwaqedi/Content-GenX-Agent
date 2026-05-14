import { NavLink, Outlet, useLocation } from 'react-router-dom';
import { useState, useEffect } from 'react';
import DatasetSwitcher from './DatasetSwitcher';

const navItems = [
  { to: '/', icon: '📊', label: 'Dashboard' },
  { to: '/videos', icon: '🎬', label: 'Top Videos' },
  { to: '/trending', icon: '🔥', label: 'Trending' },
  { to: '/creators', icon: '👤', label: 'Creators' },
  { to: '/pipeline', icon: '⚙️', label: 'Pipeline' },
];

function getInitialTheme() {
  const saved = localStorage.getItem('genx-theme');
  if (saved) return saved;
  return 'dark';
}

export default function Layout() {
  const [theme, setTheme] = useState(getInitialTheme);
  const [menuOpen, setMenuOpen] = useState(false);
  const location = useLocation();

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('genx-theme', theme);
  }, [theme]);

  // Close mobile menu on navigation
  useEffect(() => {
    setMenuOpen(false);
  }, [location.pathname]);

  const toggleTheme = () => {
    setTheme((prev) => (prev === 'dark' ? 'light' : 'dark'));
  };

  return (
    <div className="app-layout">
      {/* Mobile hamburger button */}
      <button
        className="mobile-menu-toggle"
        onClick={() => setMenuOpen(!menuOpen)}
        aria-label="Toggle menu"
      >
        {menuOpen ? '✕' : '☰'}
      </button>

      {/* Mobile overlay */}
      <div
        className={`sidebar-overlay${menuOpen ? ' show' : ''}`}
        onClick={() => setMenuOpen(false)}
      />

      <aside className={`sidebar${menuOpen ? ' open' : ''}`}>
        <div className="sidebar-brand">
          <div className="brand-logo-row">
            <img src="/logo.png" alt="GenX Logo" className="brand-logo" />
            <div>
              <h1>GenX</h1>
              <span>Leadership Academy</span>
            </div>
          </div>
        </div>
        <DatasetSwitcher />
        <nav className="sidebar-nav">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/'}
              className={({ isActive }) =>
                `nav-link${isActive ? ' active' : ''}`
              }
            >
              <span className="nav-icon">{item.icon}</span>
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div style={{ padding: '0 1.5rem', marginTop: 'auto', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
          <button className="theme-toggle" onClick={toggleTheme}>
            <span className="theme-toggle-icon">
              {theme === 'dark' ? '☀️' : '🌙'}
            </span>
            {theme === 'dark' ? 'Light Mode' : 'Dark Mode'}
          </button>
          <div className="status-bar">
            <span className="health-dot online"></span>
            System Online
          </div>
        </div>
      </aside>
      <main className="main-content">
        <Outlet />
      </main>
    </div>
  );
}
