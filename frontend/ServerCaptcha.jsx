/**
 * ServerCaptcha — React component for EasyCaptcha (server-side variant)
 * -----------------------------------------------------------------------
 * Fetches a captcha image from the EasyCaptcha backend, displays it, and
 * calls `onReady({ tokenId, answer })` when the user has typed a full code.
 *
 * Props
 * -----
 *   apiUrl        {string}    Base URL of your EasyCaptcha backend.
 *                             e.g. "http://localhost:8080"
 *   onReady       {Function}  Called with { tokenId, answer } when the user
 *                             finishes typing, or null when input is cleared.
 *   resetTrigger  {number}    Increment to programmatically reset the widget
 *                             (e.g. after a failed form submission).
 *   externalError {string}    Error message to display from the parent form.
 *
 * Usage
 * -----
 *   import ServerCaptcha from './ServerCaptcha';
 *
 *   function LoginForm() {
 *     const [captchaData, setCaptchaData] = useState(null);
 *     const [resetTrigger, setResetTrigger] = useState(0);
 *     const [captchaError, setCaptchaError] = useState('');
 *
 *     const handleSubmit = async (e) => {
 *       e.preventDefault();
 *       if (!captchaData) {
 *         setCaptchaError('Please complete the security check.');
 *         return;
 *       }
 *       const res = await fetch('/api/login', {
 *         method: 'POST',
 *         headers: { 'Content-Type': 'application/json' },
 *         body: JSON.stringify({
 *           email: '...',
 *           password: '...',
 *           captcha_token_id: captchaData.tokenId,
 *           captcha_answer:   captchaData.answer,
 *         }),
 *       });
 *       if (!res.ok) {
 *         setCaptchaError('Incorrect code — a new image has been loaded.');
 *         setResetTrigger(t => t + 1);  // refresh captcha on failure
 *       }
 *     };
 *
 *     return (
 *       <form onSubmit={handleSubmit}>
 *         ...
 *         <ServerCaptcha
 *           apiUrl={process.env.REACT_APP_CAPTCHA_URL}
 *           onReady={setCaptchaData}
 *           resetTrigger={resetTrigger}
 *           externalError={captchaError}
 *         />
 *         <button type="submit">Login</button>
 *       </form>
 *     );
 *   }
 *
 * Dependencies
 * ------------
 *   - React 17+  (hooks only, no extra packages)
 */

import React, { useState, useEffect, useRef, useCallback } from 'react';

// ── Inline SVG icon — no external icon library needed ────────────────────────
const RefreshIcon = ({ size = 14, style = {} }) => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    width={size}
    height={size}
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
    style={style}
  >
    <polyline points="23 4 23 10 17 10" />
    <polyline points="1 20 1 14 7 14"  />
    <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15" />
  </svg>
);

// ── Component ─────────────────────────────────────────────────────────────────
const ServerCaptcha = ({
  apiUrl        = 'http://localhost:8080',
  onReady,
  resetTrigger  = 0,
  externalError = '',
}) => {
  const tokenRef    = useRef('');
  const lengthRef   = useRef(5);
  // Use a ref for onReady to avoid adding it to useCallback deps
  // (prevents infinite re-render loops when parent passes an inline function)
  const onReadyRef  = useRef(onReady);
  useEffect(() => { onReadyRef.current = onReady; });

  const [imgB64,        setImgB64]        = useState('');
  const [input,         setInput]         = useState('');
  const [loading,       setLoading]       = useState(false);
  const [error,         setError]         = useState('');
  const [captchaLength, setCaptchaLength] = useState(5);

  // ── Fetch a fresh captcha from the backend ──────────────────────────
  const refresh = useCallback(async () => {
    setLoading(true);
    setInput('');
    setError('');
    if (onReadyRef.current) onReadyRef.current(null);

    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 20000);

    try {
      const res = await fetch(`${apiUrl}/captcha`, { signal: controller.signal });
      clearTimeout(timer);
      if (!res.ok) throw new Error(`Server returned ${res.status}`);
      const data = await res.json();
      tokenRef.current  = data.token_id;
      lengthRef.current = data.captcha_length ?? 5;
      setCaptchaLength(data.captcha_length ?? 5);
      setImgB64(data.image_b64);
    } catch (err) {
      clearTimeout(timer);
      setError(
        err.name === 'AbortError'
          ? 'Request timed out — tap ↺ to retry.'
          : 'Could not load captcha — tap ↺ to retry.',
      );
    } finally {
      setLoading(false);
    }
  }, [apiUrl]); // onReady intentionally excluded — handled via ref

  // Load on mount
  useEffect(() => { refresh(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Refresh when parent increments resetTrigger
  const prevTrigger = useRef(0);
  useEffect(() => {
    if (resetTrigger > 0 && resetTrigger !== prevTrigger.current) {
      prevTrigger.current = resetTrigger;
      refresh();
    }
  }, [resetTrigger, refresh]);

  // Notify parent as the user types
  const handleChange = (val) => {
    // Allow uppercase, lowercase, and digits — captcha uses mixed case
    const filtered = val.replace(/[^A-Za-z0-9]/g, '');
    setInput(filtered);
    if (error) setError('');
    if (onReadyRef.current) {
      if (filtered.length === lengthRef.current && tokenRef.current) {
        onReadyRef.current({ tokenId: tokenRef.current, answer: filtered });
      } else {
        onReadyRef.current(null);
      }
    }
  };

  const displayError = externalError || error;

  return (
    <div style={{ fontFamily: 'inherit' }}>

      {/* Image + refresh button row */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '10px' }}>

        {/* Captcha image area */}
        <div
          style={{
            flex: 1,
            borderRadius: '10px',
            overflow: 'hidden',
            border: `1.5px solid ${displayError ? '#e11d48' : '#e2e8f0'}`,
            background: '#f8fafc',
            minHeight: '62px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            transition: 'border-color 0.15s',
          }}
        >
          {loading ? (
            <span style={{ fontSize: '12px', color: '#64748b' }}>Loading captcha…</span>
          ) : imgB64 ? (
            <img
              src={`data:image/png;base64,${imgB64}`}
              alt="Security code — type the characters shown"
              draggable={false}
              style={{
                width: '100%', height: '62px', objectFit: 'fill',
                display: 'block', userSelect: 'none', WebkitUserSelect: 'none',
              }}
              onContextMenu={(e) => e.preventDefault()}
            />
          ) : (
            <button
              type="button"
              onClick={refresh}
              style={{
                background: 'none', border: 'none', cursor: 'pointer',
                display: 'flex', flexDirection: 'column', alignItems: 'center',
                gap: '4px', padding: '10px', color: '#64748b', fontFamily: 'inherit',
              }}
            >
              <RefreshIcon size={18} style={{ color: '#0ea5e9' }} />
              <span style={{ fontSize: '11px', fontWeight: 600 }}>Tap to load</span>
            </button>
          )}
        </div>

        {/* Reload button */}
        <button
          type="button"
          onClick={refresh}
          disabled={loading}
          title="Get a new captcha image"
          aria-label="Reload captcha"
          style={{
            width: '38px', height: '38px',
            border: '1.5px solid #e2e8f0',
            borderRadius: '8px',
            background: '#f8fafc',
            cursor: loading ? 'not-allowed' : 'pointer',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            color: loading ? '#cbd5e1' : '#64748b',
            flexShrink: 0,
            transition: 'color 0.15s, border-color 0.15s',
            opacity: loading ? 0.5 : 1,
          }}
          onMouseEnter={(e) => {
            if (!loading) {
              e.currentTarget.style.color = '#0ea5e9';
              e.currentTarget.style.borderColor = '#bae6fd';
            }
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.color = loading ? '#cbd5e1' : '#64748b';
            e.currentTarget.style.borderColor = '#e2e8f0';
          }}
        >
          <RefreshIcon size={14} />
        </button>
      </div>

      {/* Text input */}
      <input
        type="text"
        value={input}
        onChange={(e) => handleChange(e.target.value)}
        placeholder={`Type the ${captchaLength} characters shown above`}
        maxLength={captchaLength}
        autoComplete="off"
        spellCheck={false}
        disabled={loading}
        style={{
          width: '100%',
          padding: '10px 14px',
          border: `1.5px solid ${displayError ? '#e11d48' : '#e2e8f0'}`,
          borderRadius: '8px',
          fontSize: '18px',
          fontFamily: 'monospace',
          outline: 'none',
          letterSpacing: '7px',
          fontWeight: 700,
          color: '#0f172a',
          background: loading ? '#f8fafc' : '#ffffff',
          boxSizing: 'border-box',
          transition: 'border-color 0.15s',
          cursor: loading ? 'not-allowed' : 'text',
        }}
        onFocus={(e) => { if (!loading) e.target.style.borderColor = '#0ea5e9'; }}
        onBlur={(e)  => { e.target.style.borderColor = displayError ? '#e11d48' : '#e2e8f0'; }}
      />

      {/* Helper / error text */}
      {displayError ? (
        <p style={{
          color: '#e11d48', fontSize: '12px', margin: '5px 0 0', fontWeight: 600,
          display: 'flex', alignItems: 'center', gap: '4px',
        }}>
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor"
            strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/>
            <line x1="12" y1="16" x2="12.01" y2="16"/>
          </svg>
          {displayError}
        </p>
      ) : (
        <p style={{ fontSize: '11px', color: '#94a3b8', margin: '4px 0 0' }}>
          Case-insensitive &middot; {captchaLength} characters &middot; ↺ for a new image
        </p>
      )}
    </div>
  );
};

export default ServerCaptcha;
