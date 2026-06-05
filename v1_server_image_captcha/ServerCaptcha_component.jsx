/*
 * LEGACY v1 — Image-based server captcha component.
 * Replaced by TurnstileWidget (Cloudflare Turnstile v2). Archive only — do not import.
 */

import React, { useState, useEffect, useRef, useCallback } from 'react';
import { RefreshCw } from 'lucide-react';

/* ── Image-based server captcha ─────────────────────────────── */
export const ServerCaptcha = ({ onReady, t = DT, resetTrigger = 0, externalError = '' }) => {
  const tokenRef = useRef('');
  const [imgB64,  setImgB64]  = useState('');
  const [input,   setInput]   = useState('');
  const [loading, setLoading] = useState(false);
  const [error,   setError]   = useState('');

  const refresh = useCallback(async () => {
    setLoading(true); setInput(''); setError(''); onReady(null);
    const controller = new AbortController();
    const tid = setTimeout(() => controller.abort(), 25000);
    try {
      const res = await fetch(`${BACKEND}/api/auth/captcha`, { signal: controller.signal });
      clearTimeout(tid);
      if (!res.ok) throw new Error(`${res.status}`);
      const data = await res.json();
      tokenRef.current = data.token_id;
      setImgB64(data.image_b64);
      setError('');
    } catch (e) {
      clearTimeout(tid);
      setError(e.name === 'AbortError' ? 'Server warming up — tap Retry.' : 'Could not load captcha. Tap ↺');
    } finally { setLoading(false); }
  }, [onReady]);

  useEffect(() => { refresh(); }, []); // eslint-disable-line

  const prevTrigger = useRef(0);
  useEffect(() => {
    if (resetTrigger > 0 && resetTrigger !== prevTrigger.current) {
      prevTrigger.current = resetTrigger;
      refresh();
    }
  }, [resetTrigger, refresh]);

  const handleChange = (val) => {
    const upper = val.toUpperCase();
    setInput(upper);
    if (upper.trim().length === 5 && tokenRef.current) onReady({ tokenId: tokenRef.current, answer: upper.trim() });
    else onReady(null);
  };

  const displayError = externalError || error;

  return (
    <div>
      <div style={{ display:'flex', alignItems:'center', gap:'8px', marginBottom:'10px' }}>
        <div style={{ flex:1, borderRadius:'10px', overflow:'hidden', border:'1px solid rgba(255,255,255,0.1)', background:'rgba(255,255,255,0.03)', minHeight:'62px', display:'flex', alignItems:'center', justifyContent:'center' }}>
          {loading ? (
            <span style={{ fontSize:'12px', color:'#475569' }}>Loading captcha...</span>
          ) : imgB64 ? (
            <img src={`data:image/png;base64,${imgB64}`} alt="Security code" draggable={false}
              style={{ width:'100%', height:'62px', objectFit:'fill', display:'block', userSelect:'none', WebkitUserSelect:'none' }}
              onContextMenu={e => e.preventDefault()} />
          ) : (
            <button type="button" onClick={refresh} data-testid="captcha-load-btn"
              style={{ display:'flex', flexDirection:'column', alignItems:'center', gap:'4px', background:'none', border:'none', cursor:'pointer', padding:'10px', color:'#475569', fontFamily:'inherit' }}>
              <RefreshCw size={18} style={{ color:'#0ea5e9' }}/>
              <span style={{ fontSize:'11px', fontWeight:'600' }}>Tap to load captcha</span>
            </button>
          )}
        </div>
        <button type="button" onClick={refresh} title="New code" data-testid="captcha-refresh-btn"
          style={{ width:'38px', height:'38px', border:'1px solid rgba(255,255,255,0.1)', borderRadius:'8px', backgroundColor:'rgba(255,255,255,0.04)', cursor:'pointer', display:'flex', alignItems:'center', justifyContent:'center', color:'#64748b', flexShrink:0, transition:'all 0.15s' }}
          onMouseEnter={e => { e.currentTarget.style.color='#0ea5e9'; e.currentTarget.style.borderColor='rgba(14,165,233,0.4)'; }}
          onMouseLeave={e => { e.currentTarget.style.color='#64748b'; e.currentTarget.style.borderColor='rgba(255,255,255,0.1)'; }}
        ><RefreshCw size={14}/></button>
      </div>
      <input value={input} onChange={e => handleChange(e.target.value)}
        placeholder="5 characters" maxLength={5} autoComplete="off" spellCheck={false}
        data-testid="captcha-input"
        style={{ width:'100%', padding:'10px 14px', border:`1.5px solid ${displayError?'#f87171':'rgba(255,255,255,0.1)'}`, borderRadius:'8px', fontSize:'18px', fontFamily:'monospace', outline:'none', letterSpacing:'7px', fontWeight:'700', color:'#f1f5f9', backgroundColor:'rgba(255,255,255,0.05)', boxSizing:'border-box', transition:'border-color 0.15s' }}
        onFocus={e => e.target.style.borderColor='#0ea5e9'}
        onBlur={e  => e.target.style.borderColor = displayError ? '#f87171' : 'rgba(255,255,255,0.1)'}
      />
      {displayError
        ? <p style={{ color:'#f87171', fontSize:'12px', margin:'5px 0 0', fontWeight:'600' }} data-testid="captcha-error">{displayError}</p>
        : <p style={{ fontSize:'11px', color:'#475569', margin:'4px 0 0' }}>Case-insensitive · 5 chars · ↺ for new image</p>
      }
    </div>
  );
};
