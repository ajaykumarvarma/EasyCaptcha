/**
 * CanvasCaptcha — React component for EasyCaptcha (client-side canvas variant)
 * -----------------------------------------------------------------------------
 * A purely browser-side captcha drawn on an HTML <canvas> element.
 * No backend or database required — ideal for contact forms or low-risk flows.
 *
 * v1.2.0 additions
 * ----------------
 *   - Audio button: uses the Web Speech API (speechSynthesis) to read aloud
 *     each character individually. No backend call needed — works fully offline.
 *     WCAG 2.1 SC 1.1.1 compliant. Gracefully hidden if browser lacks support.
 *
 * Props
 * -----
 *   length        {number}   Characters per challenge (default 5).
 *   resetTrigger  {number}   Increment to programmatically reset.
 *   externalError {string}   Error message from the parent form.
 *
 * Ref (imperative handle)
 * -----------------------
 *   ref.current.validate()   → boolean
 *   ref.current.refresh()    → void
 *   ref.current.hasInput()   → boolean
 */

import React, {
  useState, useEffect, useRef, useCallback, forwardRef, useImperativeHandle,
} from 'react';

const CAPTCHA_CHARS = 'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghjkmnpqrstuvwxyz23456789';
const CAPTCHA_COLORS = ['#1e3a8a', '#6b21a8', '#9d174d', '#0c4a6e', '#14532d', '#92400e'];

// ── SVG icons ─────────────────────────────────────────────────────────────────
const RefreshIcon = ({ size = 12 }) => (
  <svg xmlns="http://www.w3.org/2000/svg" width={size} height={size}
    viewBox="0 0 24 24" fill="none" stroke="currentColor"
    strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="23 4 23 10 17 10" />
    <polyline points="1 20 1 14 7 14"  />
    <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15" />
  </svg>
);

const SpeakerIcon = ({ size = 12 }) => (
  <svg xmlns="http://www.w3.org/2000/svg" width={size} height={size}
    viewBox="0 0 24 24" fill="none" stroke="currentColor"
    strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
    <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5" />
    <path d="M15.54 8.46a5 5 0 0 1 0 7.07" />
    <path d="M19.07 4.93a10 10 0 0 1 0 14.14" />
  </svg>
);

// ── Component ─────────────────────────────────────────────────────────────────
const CanvasCaptcha = forwardRef(({
  resetTrigger  = 0,
  externalError = '',
  length        = 5,     // Fixed length (backward compat)
  minLength     = null,  // Set both minLength + maxLength to randomise per challenge
  maxLength     = null,
}, ref) => {
  const canvasRef   = useRef(null);
  const captchaRef  = useRef('');
  const [input,       setInput]       = useState('');
  const [error,       setError]       = useState('');
  const [speaking,    setSpeaking]    = useState(false);
  const [shaking,     setShaking]     = useState(false);
  const [activeLength, setActiveLength] = useState(length); // tracks current challenge length

  // Detect Web Speech API support once
  const speechSupported = typeof window !== 'undefined' && 'speechSynthesis' in window;

  // ── Canvas drawing ───────────────────────────────────────────────────
  const draw = useCallback((text) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const W = canvas.width, H = canvas.height;

    ctx.clearRect(0, 0, W, H);

    const grad = ctx.createLinearGradient(0, 0, W, H);
    grad.addColorStop(0, '#eef4fd');
    grad.addColorStop(1, '#f1f5f9');
    ctx.fillStyle = grad;
    ctx.fillRect(0, 0, W, H);

    ctx.strokeStyle = '#cbd5e1'; ctx.lineWidth = 1;
    ctx.strokeRect(0.5, 0.5, W - 1, H - 1);

    // Background noise
    for (let i = 0; i < 14; i++) {
      ctx.beginPath();
      ctx.strokeStyle = `rgba(${Math.random()*120|0},${Math.random()*120|0},${Math.random()*180|0},0.22)`;
      ctx.lineWidth = 1.2;
      ctx.moveTo(Math.random()*W, Math.random()*H);
      ctx.bezierCurveTo(
        Math.random()*W, Math.random()*H,
        Math.random()*W, Math.random()*H,
        Math.random()*W, Math.random()*H
      );
      ctx.stroke();
    }
    for (let i = 0; i < 90; i++) {
      ctx.beginPath();
      ctx.fillStyle = `rgba(${Math.random()*100|0},${Math.random()*100|0},${Math.random()*160|0},0.35)`;
      ctx.arc(Math.random()*W, Math.random()*H, Math.random()*2.5+0.4, 0, Math.PI*2);
      ctx.fill();
    }

    // Characters
    const slotW = (W - 24) / text.length;
    text.split('').forEach((char, i) => {
      ctx.save();
      ctx.translate(14 + i * slotW + slotW / 2 + (Math.random()-0.5)*4, H / 2 + 9 + (Math.random()-0.5)*6);
      ctx.rotate((Math.random() - 0.5) * 0.62);
      ctx.font        = `bold ${23 + (Math.random() * 9 | 0)}px Arial, sans-serif`;
      ctx.fillStyle   = CAPTCHA_COLORS[i % CAPTCHA_COLORS.length];
      ctx.textAlign   = 'center';
      ctx.shadowColor = 'rgba(0,0,0,0.15)';
      ctx.shadowBlur  = 2;
      ctx.fillText(char, 0, 0);
      ctx.restore();
    });

    // Foreground noise — arcs and lines over characters
    for (let i = 0; i < 3; i++) {
      ctx.beginPath();
      const ax = 30 + Math.random() * (W - 60);
      const ay = -10 + Math.random() * (H + 20);
      const ar = 15 + Math.random() * 28;
      ctx.strokeStyle = `rgba(${Math.random()*130|0},${Math.random()*130|0},${Math.random()*180|0},0.32)`;
      ctx.lineWidth = 1.3;
      ctx.arc(ax, ay, ar, 0, Math.PI * (0.6 + Math.random() * 1.2));
      ctx.stroke();
    }
    for (let i = 0; i < 6; i++) {
      ctx.beginPath();
      ctx.strokeStyle = `rgba(${Math.random()*130|0},${Math.random()*130|0},${Math.random()*180|0},0.30)`;
      ctx.lineWidth = 1;
      ctx.moveTo(Math.random()*W*0.3,          H*0.2 + Math.random()*H*0.6);
      ctx.lineTo(W*0.7 + Math.random()*W*0.3,  H*0.2 + Math.random()*H*0.6);
      ctx.stroke();
    }
  }, []);

  // ── Generate new challenge ───────────────────────────────────────────
  const refresh = useCallback(() => {
    // Stop any ongoing speech
    if (speechSupported) window.speechSynthesis.cancel();
    setSpeaking(false);

    // Determine length for this challenge
    const lo  = minLength ?? length;
    const hi  = maxLength ?? length;
    const len = lo === hi ? lo : lo + Math.floor(Math.random() * (hi - lo + 1));
    setActiveLength(len);

    let text = '';
    for (let i = 0; i < len; i++) {
      text += CAPTCHA_CHARS[Math.floor(Math.random() * CAPTCHA_CHARS.length)];
    }
    captchaRef.current = text;
    draw(text);
    setInput('');
  }, [draw, length, minLength, maxLength, speechSupported]);

  useEffect(() => { refresh(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const prevTrigger = useRef(0);
  useEffect(() => {
    if (resetTrigger > 0 && resetTrigger !== prevTrigger.current) {
      prevTrigger.current = resetTrigger;
      refresh();
      setError('');
    }
  }, [resetTrigger, refresh]);

  // ── Audio (Web Speech API) ───────────────────────────────────────────
  const speakCode = useCallback(() => {
    if (!speechSupported || !captchaRef.current) return;

    if (speaking) {
      window.speechSynthesis.cancel();
      setSpeaking(false);
      return;
    }

    window.speechSynthesis.cancel();
    setSpeaking(true);

    const chars = captchaRef.current.split('');
    let finished = 0;

    chars.forEach((char) => {
      const utterance = new SpeechSynthesisUtterance(char);
      utterance.rate   = 0.7;
      utterance.pitch  = 1;
      utterance.volume = 1;
      utterance.onend  = () => {
        finished++;
        if (finished === chars.length) setSpeaking(false);
      };
      utterance.onerror = () => {
        finished++;
        if (finished === chars.length) setSpeaking(false);
      };
      window.speechSynthesis.speak(utterance);
    });
  }, [speaking, speechSupported]);

  // ── Imperative API ───────────────────────────────────────────────────
  useImperativeHandle(ref, () => ({
    validate: () => {
      // Strict case comparison — must match exactly as displayed
      const ok = input.trim() === captchaRef.current;
      if (!ok) {
        setError('Incorrect code — a new image has been loaded. Please try again.');
        setShaking(true);
        refresh();
      } else {
        setError('');
      }
      return ok;
    },
    refresh:  () => { refresh(); setError(''); },
    hasInput: () => !!input.trim(),
  }), [input, refresh]);

  const displayError = externalError || error;

  return (
    <div style={{ fontFamily: 'inherit' }}>
      <style>{`
        @keyframes captcha-shake {
          0%,100% { transform: translateX(0);    }
          15%     { transform: translateX(-9px); }
          30%     { transform: translateX(8px);  }
          45%     { transform: translateX(-6px); }
          60%     { transform: translateX(5px);  }
          75%     { transform: translateX(-3px); }
          90%     { transform: translateX(2px);  }
        }
      `}</style>

      {/* Canvas */}
      <canvas
        ref={canvasRef}
        width={260}
        height={62}
        style={{
          width: '100%', height: '62px', borderRadius: '10px',
          border: `1.5px solid ${displayError ? '#e11d48' : '#e2e8f0'}`,
          display: 'block', userSelect: 'none', boxSizing: 'border-box',
          marginBottom: '6px', transition: 'border-color 0.15s',
          animation: shaking ? 'captcha-shake 0.45s ease-in-out' : 'none',
        }}
        onAnimationEnd={() => setShaking(false)}
        aria-label="Captcha image — type the characters shown, or use the Listen button"
      />

      {/* Controls row: reload + audio */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '10px' }}>
        <button
          type="button"
          onClick={() => { refresh(); setError(''); }}
          style={{
            display: 'flex', alignItems: 'center', gap: '5px',
            background: 'none', border: 'none', cursor: 'pointer',
            color: '#0ea5e9', fontSize: '12px', fontWeight: 600,
            padding: '0', fontFamily: 'inherit',
          }}
        >
          <RefreshIcon size={12} /> New code
        </button>

        {/* Audio button — only rendered if browser supports Web Speech API */}
        {speechSupported && (
          <button
            type="button"
            onClick={speakCode}
            title={speaking ? 'Stop audio' : 'Hear the characters read aloud (accessibility)'}
            aria-label={speaking ? 'Stop audio' : 'Listen to captcha characters'}
            aria-live="polite"
            style={{
              display: 'flex', alignItems: 'center', gap: '5px',
              background: 'none', border: 'none', cursor: 'pointer',
              color: speaking ? '#0ea5e9' : '#64748b',
              fontSize: '12px', fontWeight: 600,
              padding: '0', fontFamily: 'inherit',
              transition: 'color 0.15s',
            }}
          >
            <SpeakerIcon size={12} />
            {speaking ? 'Stop' : 'Listen'}
          </button>
        )}
      </div>

      {/* Text input */}
      <input
        type="text"
        value={input}
        onChange={(e) => {
          setInput(e.target.value.replace(/[^A-Za-z0-9]/g, ''));
          if (error) setError('');
        }}
        onPaste={(e) => e.preventDefault()}
        placeholder={`Type the ${activeLength} characters above`}
        maxLength={activeLength}
        autoComplete="off"
        spellCheck={false}
        aria-label="Captcha answer"
        aria-describedby="canvas-captcha-hint"
        style={{
          width: '100%', padding: '12px 14px',
          border: `1.5px solid ${displayError ? '#e11d48' : '#e2e8f0'}`,
          borderRadius: '8px', fontSize: '18px', fontFamily: 'monospace',
          outline: 'none', letterSpacing: '8px', fontWeight: 700, color: '#0f172a',
          boxSizing: 'border-box', transition: 'border-color 0.15s',
        }}
        onFocus={(e) => (e.target.style.borderColor = '#0ea5e9')}
        onBlur={(e)  => (e.target.style.borderColor = displayError ? '#e11d48' : '#e2e8f0')}
      />

      {/* Character progress dots */}
      <div style={{ display: 'flex', gap: '6px', justifyContent: 'center', margin: '8px 0 2px' }}>
        {Array.from({ length: activeLength }).map((_, i) => (
          <span
            key={i}
            style={{
              display: 'inline-block',
              width: '7px', height: '7px',
              borderRadius: '50%',
              border: `1.5px solid ${i < input.length ? '#0ea5e9' : '#e2e8f0'}`,
              background: i < input.length ? '#0ea5e9' : 'transparent',
              transition: 'all 0.15s',
              flexShrink: 0,
            }}
          />
        ))}
      </div>

      {/* Helper / error */}
      {displayError ? (
        <p id="canvas-captcha-hint" style={{
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
        <p id="canvas-captcha-hint" style={{ fontSize: '11px', color: '#94a3b8', margin: '6px 0 0' }}>
          Case-sensitive &middot; {length} characters
          {speechSupported ? ' · Use the Listen button for audio' : ''}
        </p>
      )}
    </div>
  );
});

CanvasCaptcha.displayName = 'CanvasCaptcha';
export default CanvasCaptcha;
