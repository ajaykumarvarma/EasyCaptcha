/**
 * CanvasCaptcha — React component for EasyCaptcha (client-side canvas variant)
 * -----------------------------------------------------------------------------
 * A purely browser-side captcha drawn on an HTML <canvas> element.
 * No backend or database required — ideal for contact forms or low-risk flows.
 *
 * Character pool: uppercase + lowercase + digits (ambiguous glyphs excluded).
 * Validation is case-insensitive.
 *
 * ⚠️  Security trade-off
 * The generated code is held in a React ref, so a sophisticated attacker who
 * inspects the JS runtime can bypass it.  For high-risk flows (login, signup,
 * payment) use the server-side ServerCaptcha component instead.
 *
 * Props
 * -----
 *   length        {number}   Number of characters (default 5).
 *   resetTrigger  {number}   Increment to programmatically reset the captcha.
 *   externalError {string}   Error message to display from the parent form.
 *
 * Ref (imperative handle)
 * -----------------------
 *   ref.current.validate()   → boolean  (clears + redraws on wrong answer)
 *   ref.current.refresh()    → void
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
 *   - React 17+  (hooks, forwardRef — no extra packages)
 */

import React, {
  useState,
  useEffect,
  useRef,
  useCallback,
  forwardRef,
  useImperativeHandle,
} from 'react';

// ── Character pool ────────────────────────────────────────────────────────────
// Mixed case + digits; ambiguous glyphs excluded:
//   Uppercase: no I, O   (look like 1 and 0)
//   Lowercase: no i, l, o (look like 1, 1, and 0)
//   Digits:    no 0, 1   (look like O/o and I/l)
const CAPTCHA_CHARS = 'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghjkmnpqrstuvwxyz23456789';

const CAPTCHA_COLORS = [
  '#1e3a8a', // deep blue
  '#6b21a8', // purple
  '#9d174d', // rose
  '#0c4a6e', // sky
  '#14532d', // green
  '#92400e', // amber
];

// ── Inline SVG icon ───────────────────────────────────────────────────────────
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
  const captchaRef = useRef('');    // stores current challenge code
  const [input, setInput] = useState('');
  const [error, setError] = useState('');

  // ── Canvas drawing ──────────────────────────────────────────────────
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

    // Background noise — curved lines
    for (let i = 0; i < 10; i++) {
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

    // Background noise — dots
    for (let i = 0; i < 60; i++) {
      ctx.beginPath();
      ctx.fillStyle = `rgba(${Math.floor(Math.random() * 100)},${Math.floor(Math.random() * 100)},${Math.floor(Math.random() * 160)},0.35)`;
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

    // Foreground noise — lines over characters to hinder OCR
    for (let i = 0; i < 4; i++) {
      ctx.beginPath();
      ctx.strokeStyle = `rgba(${Math.floor(Math.random() * 130)},${Math.floor(Math.random() * 130)},${Math.floor(Math.random() * 180)},0.30)`;
      ctx.lineWidth   = 1;
      ctx.moveTo(Math.random() * W * 0.3,       H * 0.2 + Math.random() * H * 0.6);
      ctx.lineTo(W * 0.7 + Math.random() * W * 0.3, H * 0.2 + Math.random() * H * 0.6);
      ctx.stroke();
    }
  }, []);

  // ── Generate new challenge ──────────────────────────────────────────
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

  // ── Imperative API ──────────────────────────────────────────────────
  useImperativeHandle(ref, () => ({
    /** Validate the current input.  Returns true if correct. */
    validate: () => {
      // Case-insensitive comparison — user can type either case
      const ok = input.trim().toUpperCase() === captchaRef.current.toUpperCase();
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
    /** Whether the user has typed anything. */
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
          border: `1.5px solid ${displayError ? '#e11d48' : '#e2e8f0'}`,
          display: 'block',
          userSelect: 'none',
          boxSizing: 'border-box',
          marginBottom: '6px',
          transition: 'border-color 0.15s',
        }}
        aria-label="Captcha image — type the characters shown into the field below"
      />

      {/* Reload button */}
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
          // Allow uppercase + lowercase + digits; strip everything else
          setInput(e.target.value.replace(/[^A-Za-z0-9]/g, ''));
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
          transition: 'border-color 0.15s',
        }}
        onFocus={(e) => (e.target.style.borderColor = '#0ea5e9')}
        onBlur={(e)  => (e.target.style.borderColor = displayError ? '#e11d48' : '#e2e8f0')}
      />

      {/* Helper / error text */}
      {displayError ? (
        <p style={{
          color: '#e11d48', fontSize: '12px', margin: '6px 0 0', fontWeight: 600,
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
        <p style={{ fontSize: '11px', color: '#94a3b8', margin: '6px 0 0' }}>
          Case-insensitive &middot; {length} characters
        </p>
      )}
    </div>
  );
});

CanvasCaptcha.displayName = 'CanvasCaptcha';

export default CanvasCaptcha;
