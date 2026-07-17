import { NavLink, Outlet } from 'react-router-dom';
import { useState, useEffect } from 'react';
import DatasetSwitcher from './DatasetSwitcher';
import PlatformIcon from './PlatformIcon';
import { useAuth } from '../context/AuthContext';

const navItems = [
  { to: '/', icon: '📊', label: 'Dashboard' },
  { to: '/videos', icon: '🎬', label: 'Top Content' },
  { to: '/trending', icon: '🔥', label: 'Trending' },
  { to: '/creators', icon: '👤', label: 'Creators' },
  { to: '/pipeline', icon: '🚀', label: 'Intelligence' },
];

const platformItems = [
  { to: '/videos', icon: '▦', label: 'All Platforms' },
  { to: '/platforms/reddit', platform: 'reddit', label: 'Reddit Intelligence' },
];

function getInitialTheme() {
  const saved = localStorage.getItem('genx-theme');
  if (saved) return saved;
  return 'dark';
}

export default function Layout() {
  const [theme, setTheme] = useState(getInitialTheme);
  const [menuOpen, setMenuOpen] = useState(false);
  const { user, logout } = useAuth();

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('genx-theme', theme);
  }, [theme]);

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
              onClick={() => setMenuOpen(false)}
            >
              <span className="nav-icon">{item.icon}</span>
              {item.label}
            </NavLink>
          ))}
        </nav>
        <nav className="sidebar-platforms" aria-label="Platform Intelligence">
          <p>Platform Intelligence</p>
          {platformItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/videos'}
              className={({ isActive }) => `nav-link platform-nav-link${isActive ? ' active' : ''}`}
              onClick={() => setMenuOpen(false)}
            >
              <span className="nav-icon">{item.platform ? <PlatformIcon platform={item.platform} size={17} /> : item.icon}</span>
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
          {user && (
            <button
              className="theme-toggle"
              onClick={logout}
              style={{ color: 'var(--color-accent-red)', borderColor: 'rgba(239,68,68,0.2)' }}
            >
              <span className="theme-toggle-icon">🚪</span>
              Logout
            </button>
          )}
          <div className="sidebar-profile">
            <span className="health-dot online" aria-hidden="true"></span>
            <div>
              <strong>{user ? user.username : 'System Online'}</strong>
              <span>{user ? 'Administrator' : 'Connected'}</span>
            </div>
            <span className="sidebar-profile-chevron" aria-hidden="true">⌄</span>
          </div>
        </div>
      </aside>
      <main className="main-content">
        <Outlet />
      </main>
    </div>
  );
}
