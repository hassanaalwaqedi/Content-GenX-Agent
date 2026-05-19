import { useState } from 'react';
import { Navigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import './Login.css';

export default function Login() {
  const { user, login, loading: authLoading } = useAuth();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  // Already authenticated — redirect to dashboard
  if (authLoading) {
    return (
      <div className="login-page">
        <div className="login-loading">
          <div className="login-spinner" />
          <p>Initializing…</p>
        </div>
      </div>
    );
  }
  if (user) return <Navigate to="/" replace />;

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      await login(username, password);
    } catch (err) {
      setError(err.message || 'Invalid credentials');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-page">
      {/* Animated background grid */}
      <div className="login-bg-grid" />
      <div className="login-bg-glow" />

      <div className="login-container">
        {/* Logo & Branding */}
        <div className="login-brand">
          <img src="/logo.png" alt="GenX" className="login-logo" />
          <h1 className="login-title">GenX</h1>
          <p className="login-subtitle">Intelligence Platform</p>
        </div>

        {/* Login Form */}
        <form className="login-form" onSubmit={handleSubmit}>
          <div className="login-field">
            <label htmlFor="login-username">Username</label>
            <div className="login-input-wrap">
              <span className="login-input-icon">👤</span>
              <input
                id="login-username"
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="Enter username"
                autoComplete="username"
                autoFocus
                required
              />
            </div>
          </div>

          <div className="login-field">
            <label htmlFor="login-password">Password</label>
            <div className="login-input-wrap">
              <span className="login-input-icon">🔒</span>
              <input
                id="login-password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Enter password"
                autoComplete="current-password"
                required
              />
            </div>
          </div>

          {error && (
            <div className="login-error">
              <span className="login-error-icon">⚠</span>
              {error}
            </div>
          )}

          <button
            type="submit"
            className="login-btn"
            disabled={loading || !username || !password}
          >
            {loading ? (
              <>
                <span className="login-btn-spinner" />
                Authenticating…
              </>
            ) : (
              <>🚀 Access Platform</>
            )}
          </button>
        </form>

        <p className="login-footer">
          Secured access · Single-operator mode
        </p>
      </div>
    </div>
  );
}
