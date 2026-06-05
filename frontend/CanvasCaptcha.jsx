/**
 * CanvasCaptcha — React component for EasyCaptcha (client-side canvas variant)
 * -----------------------------------------------------------------------------
 * A purely browser-side captcha drawn on an HTML <canvas> element.
 * No backend or database required — ideal for simple contact forms or
 * situations where you cannot run a server.
 *
 * ⚠️  Security trade-off
 * The generated code is held in a React ref, which means a sophisticated
 * attacker who inspects the JS runtime can bypass it.  For higher-risk flows
 * (login, signup, payment) prefer the server-side ServerCaptcha component.
 *
 * Props
 * -----
 *   resetTrigger  {number}   Increment to programmatically reset the captcha.
 *   externalError {string}   Error message to display from the parent form.
 *
 * Ref (imperative handle)
 * -----------------------
 * Attach a ref to access:
 *   ref.current.validate()   → boolean  (clears + redraws on wrong answer)
 *   ref.current.refresh()    → void     (manually refresh)
 *   ref.current.hasInput()   → boolean
 *
 * Usage
 * -----
 *   import CanvasCaptcha from './CanvasCaptcha';
 *
 *   function ContactForm() {
 *     const captchaRef = useRef(null);
 *
 *     const handleSubmit = (e) => {
 *       e.preventDefault();
 *       if (!captchaRef.current.validate()) return; // shows error + redraws
 *       // proceed...
 *     };
 *
 *     return (
 *       <form onSubmit={handleSubmit}>
 *         ...
 *         <CanvasCaptcha ref={captchaRef} />
 *         <button type="submit">Send</button>
 *       </form>
 *     );
 *   }
 *
 * Dependencies
 * ------------
 *   - React 17+ (uses hooks, forwardRef)
 *   No other dependencies required.
 */

import React, {
  useState,
  useEffect,
  useRef,
  useCallback,
  forwardRef,
  useImperativeHandle,
} from 'react';

// ── Constants ─────────────────────────────────────────────────────────────────

// Omit visually confusing characters: I, O, 0, 1
const CAPTCHA_CHARS = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789';

const CAPTCHA_COLORS = [
  '#1e3a8a', // deep blue
  '#6b21a8', // purple
  '#9d174d', // rose
  '#0c4a6e', // sky
  '#14532d', // green
  '#92400e', // amber
];

// ── Inline SVG icon — no external icon library needed ────────────────────────
const RefreshIcon = ({ size = 12 }) => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    width={size}
    height={size}
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2.5"
    strokeLinecap="round"
    strokeLinejoin="round"
  >
    <polyline points="23 4 23 10 17 10" />
    <polyline points="1 20 1 14 7 14"  />
    <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15" />
  </svg>
);

// ── Component ─────────────────────────────────────────────────────────────────
const CanvasCaptcha = forwardRef(({ resetTrigger = 0, externalError = '', length = 5 }, ref) => {
  const canvasRef  = useRef(null);
  const captchaRef = useRef('');
  const [input, setInput] = useState('');
  const [error, setError] = useState('');

  // ── Canvas drawing ─────────────────────────────────────────────────────
  const draw = useCallback((text) => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    const W   = canvas.width;
    const H   = canvas.height;

    // Clear
    ctx.clearRect(0, 0, W, H);

    // Background gradient
    const grad = ctx.createLinearGradient(0, 0, W, H);
    grad.addColorStop(0, '#eef4fd');
    grad.addColorStop(1, '#f1f5f9');
    ctx.fillStyle = grad;
    ctx.fillRect(0, 0, W, H);

    // Border
    ctx.strokeStyle = '#cbd5e1';
    ctx.lineWidth   = 1;
    ctx.strokeRect(0.5, 0.5, W - 1, H - 1);

    // Noise — curved lines
    for (let i = 0; i < 7; i++) {
      ctx.beginPath();
      ctx.strokeStyle = `rgba(${Math.floor(Math.random() * 120)},${Math.floor(Math.random() * 120)},${Math.floor(Math.random() * 180)},0.22)`;
      ctx.lineWidth   = 1.2;
      ctx.moveTo(Math.random() * W, Math.random() * H);
      ctx.bezierCurveTo(
        Math.random() * W, Math.random() * H,
        Math.random() * W, Math.random() * H,
        Math.random() * W, Math.random() * H,
      );
      ctx.stroke();
    }

    // Noise — dots
    for (let i = 0; i < 50; i++) {
      ctx.beginPath();
      ctx.fillStyle = `rgba(${Math.floor(Math.random() * 100)},${Math.floor(Math.random() * 100)},${Math.floor(Math.random() * 160)},0.40)`;
      ctx.arc(Math.random() * W, Math.random() * H, Math.random() * 2 + 0.4, 0, Math.PI * 2);
      ctx.fill();
    }

    // Characters — each rotated and differently coloured
    const slotW = (W - 24) / text.length;
    text.split('').forEach((char, i) => {
      ctx.save();
      ctx.translate(14 + i * slotW + slotW / 2, H / 2 + 9);
      ctx.rotate((Math.random() - 0.5) * 0.55);
      ctx.font        = `bold ${22 + Math.floor(Math.random() * 7)}px Arial, sans-serif`;
      ctx.fillStyle   = CAPTCHA_COLORS[i % CAPTCHA_COLORS.length];
      ctx.textAlign   = 'center';
      ctx.shadowColor = 'rgba(0,0,0,0.15)';
      ctx.shadowBlur  = 2;
      ctx.fillText(char, 0, 0);
      ctx.restore();
    });
  }, []);

  // ── Generate new challenge ────────────────────────────────────────────
  const refresh = useCallback(() => {
    let text = '';
    for (let i = 0; i < length; i++) {
      text += CAPTCHA_CHARS[Math.floor(Math.random() * CAPTCHA_CHARS.length)];
    }
    captchaRef.current = text;
    draw(text);
    setInput('');
  }, [draw, length]);

  // Initial draw on mount
  useEffect(() => { refresh(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Respond to external reset trigger
  const prevTrigger = useRef(0);
  useEffect(() => {
    if (resetTrigger > 0 && resetTrigger !== prevTrigger.current) {
      prevTrigger.current = resetTrigger;
      refresh();
      setError('');
    }
  }, [resetTrigger, refresh]);

  // ── Imperative API (used by parent via ref) ───────────────────────────
  useImperativeHandle(ref, () => ({
    /** Validate the current input.  Returns true if correct, false otherwise. */
    validate: () => {
      const ok = input.trim().toUpperCase() === captchaRef.current;
      if (!ok) {
        setError('Incorrect code — a new image has been loaded. Please try again.');
        refresh();
      } else {
        setError('');
      }
      return ok;
    },
    /** Reset the captcha without validation. */
    refresh: () => { refresh(); setError(''); },
    /** Check whether the user has typed anything. */
    hasInput: () => !!input.trim(),
  }), [input, refresh]);

  const handleManualRefresh = () => { refresh(); setError(''); };

  const displayError = externalError || error;

  return (
    <div style={{ fontFamily: 'inherit' }}>

      {/* Canvas */}
      <canvas
        ref={canvasRef}
        width={260}
        height={62}
        style={{
          width: '100%',
          height: '62px',
          borderRadius: '10px',
          border: '1.5px solid #e2e8f0',
          display: 'block',
          userSelect: 'none',
          boxSizing: 'border-box',
          marginBottom: '6px',
        }}
        aria-label="Captcha image — type the characters shown into the field below"
      />

      {/* Refresh link */}
      <button
        type="button"
        onClick={handleManualRefresh}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '5px',
          background: 'none',
          border: 'none',
          cursor: 'pointer',
          color: '#0ea5e9',
          fontSize: '12px',
          fontWeight: 600,
          padding: '0',
          marginBottom: '10px',
          fontFamily: 'inherit',
        }}
      >
        <RefreshIcon size={12} /> Get a new code
      </button>

      {/* Text input */}
      <input
        type="text"
        value={input}
        onChange={(e) => {
          setInput(e.target.value.toUpperCase().replace(/[^A-Z0-9]/g, ''));
          if (error) setError('');
        }}
        placeholder={`Type the ${length} characters above`}
        maxLength={length}
        autoComplete="off"
        spellCheck={false}
        style={{
          width: '100%',
          padding: '12px 14px',
          border: `1.5px solid ${displayError ? '#e11d48' : '#e2e8f0'}`,
          borderRadius: '8px',
          fontSize: '18px',
          fontFamily: 'monospace',
          outline: 'none',
          letterSpacing: '8px',
          fontWeight: 700,
          color: '#0f172a',
          boxSizing: 'border-box',
          textTransform: 'uppercase',
          transition: 'border-color 0.15s',
        }}
        onFocus={(e) => (e.target.style.borderColor = '#0ea5e9')}
        onBlur={(e) => (e.target.style.borderColor = displayError ? '#e11d48' : '#e2e8f0')}
      />

      {/* Helper / error text */}
      {displayError ? (
        <p style={{ color: '#e11d48', fontSize: '12px', margin: '6px 0 0', fontWeight: 600 }}>
          {displayError}
        </p>
      ) : (
        <p style={{ fontSize: '11px', color: '#94a3b8', margin: '6px 0 0' }}>
          Case-insensitive &middot; {length} characters
        </p>
      )}
    </div>
  );
});

CanvasCaptcha.displayName = 'CanvasCaptcha';

export default CanvasCaptcha;
