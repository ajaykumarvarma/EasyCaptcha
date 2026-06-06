/**
 * ServerCaptcha — React component for EasyCaptcha (server-side variant)
 * -----------------------------------------------------------------------
 * Fetches a captcha image from the EasyCaptcha backend, displays it, and
 * calls `onReady({ tokenId, answer })` when the user has typed a full code.
 *
 * Props
 * -----
 *   apiUrl        {string}    Base URL of your EasyCaptcha backend.
 *   onReady       {Function}  Called with { tokenId, answer } or null.
 *   resetTrigger  {number}    Increment to programmatically reset the widget.
 *   externalError {string}    Error message from the parent form.
 *
 * v1.2.0 additions
 * ----------------
 *   - Audio button: calls GET /captcha/audio/{token_id} and plays the WAV.
 *     Only shown when the backend reports audio_available=true.
 *   - Graceful fallback when audio unavailable (button hidden, no errors).
 */

import React, { useState, useEffect, useRef, useCallback } from 'react';

// ── SVG icons ─────────────────────────────────────────────────────────────────
const RefreshIcon = ({ size = 14 }) => (
  <svg xmlns="http://www.w3.org/2000/svg" width={size} height={size}
    viewBox="0 0 24 24" fill="none" stroke="currentColor"
    strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="23 4 23 10 17 10" />
    <polyline points="1 20 1 14 7 14"  />
    <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15" />
  </svg>
);

const SpeakerIcon = ({ size = 14 }) => (
  <svg xmlns="http://www.w3.org/2000/svg" width={size} height={size}
    viewBox="0 0 24 24" fill="none" stroke="currentColor"
    strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5" />
    <path d="M15.54 8.46a5 5 0 0 1 0 7.07" />
    <path d="M19.07 4.93a10 10 0 0 1 0 14.14" />
  </svg>
);

const StopIcon = ({ size = 14 }) => (
  <svg xmlns="http://www.w3.org/2000/svg" width={size} height={size}
    viewBox="0 0 24 24" fill="currentColor">
    <rect x="4" y="4" width="16" height="16" rx="2" />
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
  const onReadyRef  = useRef(onReady);
  useEffect(() => { onReadyRef.current = onReady; });

  const audioRef = useRef(null);   // current HTMLAudioElement

  const [imgB64,         setImgB64]         = useState('');
  const [input,          setInput]          = useState('');
  const [loading,        setLoading]        = useState(false);
  const [error,          setError]          = useState('');
  const [captchaLength,  setCaptchaLength]  = useState(5);
  const [audioAvailable, setAudioAvailable] = useState(false);
  const [audioPlaying,   setAudioPlaying]   = useState(false);
  const [audioLoading,   setAudioLoading]   = useState(false);
  const [audioError,     setAudioError]     = useState('');
  const [shaking,        setShaking]        = useState(false);

  // ── Fetch a fresh captcha ──────────────────────────────────────────
  const refresh = useCallback(async () => {
    // Stop any playing audio
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current = null;
      setAudioPlaying(false);
    }
    setLoading(true);
    setInput('');
    setError('');
    setAudioError('');
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
      setAudioAvailable(data.audio_available === true);
    } catch (err) {
      clearTimeout(timer);
      setError(
        err.name === 'AbortError'
          ? 'Request timed out — tap the reload button to retry.'
          : 'Could not load captcha — tap the reload button to retry.',
      );
    } finally {
      setLoading(false);
    }
  }, [apiUrl]);

  useEffect(() => { refresh(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Shake the image when the parent signals an error (wrong answer from backend)
  const prevExternalError = useRef('');
  useEffect(() => {
    if (externalError && externalError !== prevExternalError.current) {
      setShaking(true);
    }
    prevExternalError.current = externalError;
  }, [externalError]);

  const prevTrigger = useRef(0);
  useEffect(() => {
    if (resetTrigger > 0 && resetTrigger !== prevTrigger.current) {
      prevTrigger.current = resetTrigger;
      refresh();
    }
  }, [resetTrigger, refresh]);

  // ── Audio playback ──────────────────────────────────────────────────
  const playAudio = useCallback(async () => {
    if (audioLoading || !tokenRef.current) return;

    // Toggle — stop if already playing
    if (audioPlaying && audioRef.current) {
      audioRef.current.pause();
      audioRef.current = null;
      setAudioPlaying(false);
      return;
    }

    setAudioLoading(true);
    setAudioError('');

    try {
      const res = await fetch(`${apiUrl}/captcha/audio/${tokenRef.current}`);
      if (res.status === 503) throw new Error('unavailable');
      if (res.status === 404) throw new Error('not_found');
      if (!res.ok) throw new Error('fetch_failed');

      const blob = await res.blob();
      const url  = URL.createObjectURL(blob);
      const audio = new Audio(url);
      audioRef.current = audio;

      audio.onplay  = () => setAudioPlaying(true);
      audio.onended = () => { setAudioPlaying(false); URL.revokeObjectURL(url); };
      audio.onerror = () => { setAudioPlaying(false); setAudioError('Playback error.'); };

      await audio.play();
    } catch (err) {
      if (err.message === 'unavailable') {
        setAudioError('Audio not available on this server.');
      } else if (err.message === 'not_found') {
        setAudioError('Captcha expired — please reload.');
      } else {
        setAudioError('Could not play audio.');
      }
    } finally {
      setAudioLoading(false);
    }
  }, [apiUrl, audioLoading, audioPlaying]);

  // ── Input handling ──────────────────────────────────────────────────
  const handleChange = (val) => {
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
  const btnBase = {
    width: '38px', height: '38px',
    border: '1.5px solid #e2e8f0', borderRadius: '8px', background: '#f8fafc',
    cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center',
    flexShrink: 0, transition: 'color 0.15s, border-color 0.15s',
  };

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

      {/* Image + controls row */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '10px' }}>

        {/* Captcha image */}
        <div
          style={{
            flex: 1, borderRadius: '10px', overflow: 'hidden',
            border: `1.5px solid ${displayError ? '#e11d48' : '#e2e8f0'}`,
            background: '#f8fafc', minHeight: '62px',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            transition: 'border-color 0.15s',
            animation: shaking ? 'captcha-shake 0.45s ease-in-out' : 'none',
          }}
          onAnimationEnd={() => setShaking(false)}
        >
          {loading ? (
            <span style={{ fontSize: '12px', color: '#64748b' }}>Loading captcha…</span>
          ) : imgB64 ? (
            <img
              src={`data:image/png;base64,${imgB64}`}
              alt="Security code — type the characters shown, or use the audio button"
              draggable={false}
              style={{ width: '100%', height: '62px', objectFit: 'fill', display: 'block',
                userSelect: 'none', WebkitUserSelect: 'none' }}
              onContextMenu={(e) => e.preventDefault()}
            />
          ) : (
            <button type="button" onClick={refresh}
              style={{ background: 'none', border: 'none', cursor: 'pointer',
                display: 'flex', flexDirection: 'column', alignItems: 'center',
                gap: '4px', padding: '10px', color: '#64748b', fontFamily: 'inherit' }}>
              <RefreshIcon size={18} />
              <span style={{ fontSize: '11px', fontWeight: 600 }}>Tap to load</span>
            </button>
          )}
        </div>

        {/* Audio button — only shown when backend has espeak-ng */}
        {audioAvailable && (
          <button
            type="button"
            onClick={playAudio}
            disabled={audioLoading || loading || !imgB64}
            title={audioPlaying ? 'Stop audio' : 'Listen to the captcha characters'}
            aria-label={audioPlaying ? 'Stop audio captcha' : 'Play audio captcha'}
            style={{
              ...btnBase,
              color: audioPlaying ? '#0ea5e9' : (audioLoading || loading || !imgB64) ? '#cbd5e1' : '#64748b',
              borderColor: audioPlaying ? '#bae6fd' : '#e2e8f0',
              opacity: (audioLoading || loading || !imgB64) ? 0.5 : 1,
              cursor: (audioLoading || loading || !imgB64) ? 'not-allowed' : 'pointer',
            }}
            onMouseEnter={(e) => {
              if (!audioLoading && !loading && imgB64) {
                e.currentTarget.style.color = '#0ea5e9';
                e.currentTarget.style.borderColor = '#bae6fd';
              }
            }}
            onMouseLeave={(e) => {
              if (!audioPlaying) {
                e.currentTarget.style.color = (audioLoading || loading || !imgB64) ? '#cbd5e1' : '#64748b';
                e.currentTarget.style.borderColor = '#e2e8f0';
              }
            }}
          >
            {audioPlaying ? <StopIcon size={12} /> : <SpeakerIcon size={14} />}
          </button>
        )}

        {/* Reload button */}
        <button
          type="button"
          onClick={refresh}
          disabled={loading}
          title="Get a new captcha image"
          aria-label="Reload captcha"
          style={{
            ...btnBase,
            color: loading ? '#cbd5e1' : '#64748b',
            opacity: loading ? 0.5 : 1,
            cursor: loading ? 'not-allowed' : 'pointer',
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

      {/* Audio error */}
      {audioError && (
        <p style={{ color: '#f59e0b', fontSize: '11px', margin: '0 0 6px', fontWeight: 600 }}>
          {audioError}
        </p>
      )}

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
        aria-label="Captcha answer"
        aria-describedby="captcha-hint"
        style={{
          width: '100%', padding: '10px 14px',
          border: `1.5px solid ${displayError ? '#e11d48' : '#e2e8f0'}`,
          borderRadius: '8px', fontSize: '18px', fontFamily: 'monospace',
          outline: 'none', letterSpacing: '7px', fontWeight: 700, color: '#0f172a',
          background: loading ? '#f8fafc' : '#ffffff', boxSizing: 'border-box',
          transition: 'border-color 0.15s',
          cursor: loading ? 'not-allowed' : 'text',
        }}
        onFocus={(e) => { if (!loading) e.target.style.borderColor = '#0ea5e9'; }}
        onBlur={(e)  => { e.target.style.borderColor = displayError ? '#e11d48' : '#e2e8f0'; }}
      />

      {/* Helper / error */}
      {displayError ? (
        <p id="captcha-hint" style={{
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
        <p id="captcha-hint" style={{ fontSize: '11px', color: '#94a3b8', margin: '4px 0 0' }}>
          Case-sensitive &middot; {captchaLength} chars
          {audioAvailable ? ' · Use the speaker button to hear the characters' : ''}
        </p>
      )}
    </div>
  );
};

export default ServerCaptcha;
