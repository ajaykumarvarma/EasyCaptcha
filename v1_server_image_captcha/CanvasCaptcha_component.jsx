/*
 * LEGACY v1 — Canvas-drawn client-side captcha.
 * Had NO server-side verification. Replaced by TurnstileWidget (Cloudflare Turnstile v2). Archive only.
 */

import React, { useState, useEffect, useRef, useCallback, forwardRef, useImperativeHandle } from 'react';

const CanvasCaptcha = forwardRef(({ resetTrigger = 0, externalError = '' }, ref) => {
  const canvasRef  = useRef(null);
  const captchaRef = useRef('');
  const [input, setInput] = useState('');
  const [error, setError] = useState('');

  const draw = useCallback((text) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const W = canvas.width, H = canvas.height;
    ctx.clearRect(0, 0, W, H);
    const grad = ctx.createLinearGradient(0, 0, W, H);
    grad.addColorStop(0, '#e8f0fe'); grad.addColorStop(1, '#f1f5f9');
    ctx.fillStyle = grad; ctx.fillRect(0, 0, W, H);
    ctx.strokeStyle = '#cbd5e1'; ctx.lineWidth = 1; ctx.strokeRect(0, 0, W, H);
    for (let i = 0; i < 6; i++) {
      ctx.beginPath();
      ctx.strokeStyle = `rgba(${Math.floor(Math.random()*120)},${Math.floor(Math.random()*120)},${Math.floor(Math.random()*180)},0.28)`;
      ctx.lineWidth = 1.2;
      ctx.moveTo(Math.random()*W, Math.random()*H);
      ctx.bezierCurveTo(Math.random()*W, Math.random()*H, Math.random()*W, Math.random()*H, Math.random()*W, Math.random()*H);
      ctx.stroke();
    }
    for (let i = 0; i < 40; i++) {
      ctx.beginPath();
      ctx.fillStyle = `rgba(${Math.floor(Math.random()*100)},${Math.floor(Math.random()*100)},${Math.floor(Math.random()*160)},0.45)`;
      ctx.arc(Math.random()*W, Math.random()*H, Math.random()*2+0.4, 0, Math.PI*2);
      ctx.fill();
    }
    const cw = (W - 24) / text.length;
    text.split('').forEach((char, i) => {
      ctx.save();
      ctx.translate(14 + i * cw + cw / 2, H / 2 + 9);
      ctx.rotate((Math.random() - 0.5) * 0.55);
      ctx.font = `bold ${22 + Math.floor(Math.random()*6)}px Arial, sans-serif`;
      ctx.fillStyle = CAPTCHA_COLORS[i % CAPTCHA_COLORS.length];
      ctx.textAlign = 'center';
      ctx.shadowColor = 'rgba(0,0,0,0.18)'; ctx.shadowBlur = 3;
      ctx.fillText(char, 0, 0);
      ctx.restore();
    });
  }, []);

  const refresh = useCallback(() => {
    let text = '';
    for (let i = 0; i < 5; i++) text += CAPTCHA_CHARS[Math.floor(Math.random() * CAPTCHA_CHARS.length)];
    captchaRef.current = text;
    draw(text);
    setInput('');
    // Note: error state is managed explicitly by callers (validate() or onChange)
    // so refresh() doesn't compete with subsequent setError() calls in the same batch.
  }, [draw]);

  useEffect(() => { refresh(); }, []); // eslint-disable-line

  // Auto-refresh when parent signals an error (also clears any local error message)
  const prevTrigger = useRef(0);
  useEffect(() => {
    if (resetTrigger > 0 && resetTrigger !== prevTrigger.current) {
      prevTrigger.current = resetTrigger;
      refresh();
      setError('');
    }
  }, [resetTrigger, refresh]);

  // Expose imperative handle so parent can validate on form submit
  useImperativeHandle(ref, () => ({
    validate: () => {
      const ok = input.trim().toUpperCase() === captchaRef.current;
      if (!ok) {
        // Set error FIRST so it renders in the same batch as the input clear/redraw
        setError('Incorrect security code — a new image has been loaded. Please try again.');
        refresh();
      } else {
        setError('');
      }
      return ok;
    },
    refresh: () => { refresh(); setError(''); },
    hasInput: () => !!input.trim(),
  }), [input, refresh]);

  // Manual refresh button click — clears any existing error
  const handleManualRefresh = () => { refresh(); setError(''); };

  const displayError = externalError || error;

  return (
    <div>
      <canvas
        ref={canvasRef}
        width={260}
        height={62}
        style={{
          width: '100%',
          height: '62px',
          borderRadius: '10px',
          border: '1.5px solid #cbd5e1',
          display: 'block',
          userSelect: 'none',
          boxSizing: 'border-box',
          marginBottom: '6px',
        }}
      />

      <button
        type="button"
        onClick={handleManualRefresh}
        data-testid="canvas-captcha-refresh-btn"
        style={{
          display: 'flex', alignItems: 'center', gap: '5px',
          background: 'none', border: 'none', cursor: 'pointer',
          color: '#0ea5e9', fontSize: '12px', fontWeight: '600',
          padding: '0', marginBottom: '10px', fontFamily: 'inherit',
        }}
      >
        <RefreshCw size={12} /> Get a new code
      </button>

      <input
        value={input}
        onChange={e => { setInput(e.target.value.toUpperCase()); if (error) setError(''); }}
        placeholder="Type the 5 characters above"
        maxLength={5}
        autoComplete="off"
        data-testid="canvas-captcha-input"
        style={{
          width: '100%', padding: '12px 14px',
          border: `1.5px solid ${displayError ? '#e11d48' : '#e2e8f0'}`, borderRadius: '8px',
          fontSize: '18px', fontFamily: 'monospace',
          outline: 'none', letterSpacing: '8px', fontWeight: '700',
          color: '#0f172a', boxSizing: 'border-box',
          textTransform: 'uppercase',
        }}
        onFocus={e => e.target.style.borderColor = '#0ea5e9'}
        onBlur={e => e.target.style.borderColor = displayError ? '#e11d48' : '#e2e8f0'}
      />
      {displayError ? (
        <p style={{ color: '#e11d48', fontSize: '12px', margin: '6px 0 0', fontWeight: '600' }} data-testid="canvas-captcha-error">{displayError}</p>
      ) : (
        <p style={{ fontSize: '11px', color: '#94a3b8', margin: '6px 0 0' }}>Case-insensitive · 5 characters</p>
      )}
    </div>
  );
});
CanvasCaptcha.displayName = 'CanvasCaptcha';
