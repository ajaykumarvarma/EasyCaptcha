# EasyCaptcha

**Self-hosted, open-source captcha service — no third-party vendor required.**

> **Live demo →** [ajaykumarvarma.github.io/EasyCaptcha](https://ajaykumarvarma.github.io/EasyCaptcha)  
> Try both variants live (CanvasCaptcha works instantly; ServerCaptcha connects to your own instance).

Two ready-to-use variants:

| Variant | How it works | Best for |
|---------|-------------|----------|
| **ServerCaptcha** | Backend generates a distorted PNG image; answer verified server-side in MongoDB | Sign up, sign in, password reset — any high-risk form |
| **CanvasCaptcha** | Canvas drawn entirely in the browser; no backend needed | Contact forms, newsletter subscribe, low-risk forms |

---

## What's new

### v1.3.0 (Security hardening + UX polish)
- **Minimum solve time** — answers arriving in under `CAPTCHA_MIN_SOLVE_MS` ms (default 1500) are automatically rejected. Automated solvers answer in < 50 ms; humans take ≥ 2 s. Zero false positives for real users.
- **Honeypot hidden field** — `ServerCaptcha` includes a CSS-hidden `name="website"` input. Bots fill it; humans never see it. Any non-empty value triggers instant rejection before any DB lookup.
- **Enhanced image distortion** — 180 background dots (was 130), arc noise arcs over characters, variable character spacing, and 8 foreground interference lines (was 5). Significantly harder for batch OCR.
- **Strict case-sensitive comparison** — both React components and the demo page now compare answers exactly as displayed (mixed upper/lower/digit).
- **Character progress dots** — filling dots below the input show how many characters have been typed (●●●○○ style). Available in all three frontends.
- **Auto-validate** — canvas variant auto-submits 700 ms after the last character is typed.
- **New error code** — `too_fast` in `VerifyResponse.error_code` when timing check fails.
- **Per-request length randomisation** — `CAPTCHA_LENGTH_MIN=4` / `CAPTCHA_LENGTH_MAX=6` vary the challenge length on every request. Makes length-based pattern attacks impossible. `CanvasCaptcha` accepts `minLength`/`maxLength` props; the demo page uses `CANVAS_MIN_LEN` / `CANVAS_MAX_LEN` JS constants.
- **HTTPS/TLS production guide** — new README section with Caddy (automatic TLS), nginx + Certbot, Docker Compose nginx, and forwarded-IP/IP-binding notes.

### v1.2.0 (MongoDB auth + IP binding + Audio CAPTCHA)
- MongoDB authentication with dedicated least-privilege `captcha_svc` user.
- IP binding: `ENFORCE_IP_BINDING=true` ties each token to the requesting IP.
- Audio CAPTCHA: `GET /captcha/audio/{token_id}` via `espeak-ng` (WCAG 2.1 SC 1.1.1).

### v1.1.0 (Bug fixes + Security baseline)
- Wave distortion + foreground noise for OCR resistance.
- Single-use tokens (consumed on any attempt, not just correct ones).
- Mixed-case character pool (upper + lower + digits, no ambiguous glyphs).
- Per-IP sliding-window rate limiter on all three endpoints.

---

## Table of contents

1. [How it works](#how-it-works)
2. [Repository layout](#repository-layout)
3. [Live demo page](#live-demo-page)
4. [Quick start — Docker](#quick-start--docker-recommended)
5. [Manual setup](#manual-setup-without-docker)
6. [Configuration reference](#configuration-reference)
7. [Step-by-step integration guide](#step-by-step-integration-guide)
   - [Step 1 — Prepare your project](#step-1--prepare-your-project)
   - [Step 2 — Sign Up form](#step-2--sign-up-form)
   - [Step 3 — Sign In / Login form](#step-3--sign-in--login-form)
   - [Step 4 — Forgot Password form](#step-4--forgot-password-form)
   - [Step 5 — Contact form (CanvasCaptcha)](#step-5--contact--submit-form-canvascaptcha)
   - [Plain HTML — no React](#plain-html--no-react)
8. [Backend verification examples](#backend-verification-examples)
   - [FastAPI (Python)](#fastapi-python)
   - [Express.js (Node.js)](#expressjs-nodejs)
   - [Django (Python)](#django-python)
   - [PHP](#php)
9. [API reference](#api-reference)
10. [Running the tests](#running-the-tests)
11. [Security notes](#security-notes)
12. [Troubleshooting](#troubleshooting)
13. [FAQ](#faq)
14. [Contributing](#contributing)
15. [License](#license)

---

## How it works

### ServerCaptcha flow (sign up, sign in, etc.)

```
Browser                    Your App Backend         EasyCaptcha Service
   |                              |                        |
   |--- GET /captcha -------------------------------------> |
   |<-- { token_id, image_b64,                             |
   |      captcha_length } ------------------------------ |
   |                              |                        |
   | (user sees image, types)     |                        |
   |                              |                        |
   |--- POST /your-signup ------> |                        |
   |    { email, password,        |                        |
   |      captcha_token_id,       |                        |
   |      captcha_answer }        |                        |
   |                              |--- POST /captcha/verify ->|
   |                              |    { token_id, answer }   |
   |                              |<-- { valid: true } ------- |
   |                              |                        |
   |                              | (create account)       |
   |<-- { success } ------------- |                        |
```

Key points:
- The browser **never** sends the answer directly to EasyCaptcha — your backend does.
- Each token is **single-use** and expires after 5 minutes (configurable).
- The correct code is **never** sent to the browser — only the image.
- The API response includes `captcha_length` so the React components automatically
  adapt when you change `CAPTCHA_LENGTH` in the backend config.

### CanvasCaptcha flow (contact form, newsletter, etc.)

```
Browser
   |
   | (page loads — canvas draws random characters)
   | (user reads and types the code)
   | (JS validates locally before submit)
   |
   |--- POST /contact ---------> Your App Backend
        { name, email, message }
```

No EasyCaptcha service needed. The check happens entirely in the browser.

---

## Repository layout

```
easycaptcha/
├── backend/
│   ├── captcha_service.py   — Complete FastAPI service (single file, runs standalone)
│   ├── requirements.txt     — Python dependencies
│   ├── requirements-dev.txt — Test dependencies
│   ├── .env.example         — Copy to .env and fill in values
│   ├── Dockerfile           — Python + espeak-ng environment
│   ├── test_captcha.py      — Automated tests (41 unit tests, 9 integration/audio skipped)
│   └── conftest.py          — pytest configuration
├── frontend/
│   ├── ServerCaptcha.jsx    — React component (server-side variant, v1.3.0)
│   └── CanvasCaptcha.jsx    — React component (canvas / client-side variant, v1.3.0)
├── docker/
│   ├── docker-compose.yml   — One-command local setup (service + MongoDB with auth)
│   ├── mongo-init.js        — Creates dedicated captcha_svc MongoDB user (least privilege)
│   └── .env.example         — Docker secrets template
├── docs/
│   └── index.html           — GitHub Pages live demo (both variants, v1.3.0)
├── README.md
└── LICENSE                  — MIT
```

---

## Live demo page

The `docs/` folder contains a fully self-contained demo page you can host for free on **GitHub Pages**.

### Enable GitHub Pages (one-time setup)

1. Push this repository to GitHub (repo name: `easycaptcha`).
2. Go to **Settings → Pages**.
3. Under "Build and deployment", set **Source → Deploy from a branch**.
4. Set **Branch → `main`** and **Folder → `/docs`**.
5. Click **Save** — the demo is live at:

```
https://ajaykumarvarma.github.io/EasyCaptcha
```

Replace `your-username` with `ajaykumarvarma` (already configured).

### What the demo shows

| Section | Works without a backend? |
|---------|--------------------------|
| **CanvasCaptcha** tab | Yes — loads instantly, validates in-browser |
| **ServerCaptcha** tab | No — enter your backend URL (e.g. `http://localhost:8080`) and click **Load** |

The ServerCaptcha tab is intentionally designed for developers to point at their own running instance, so the backend verification flow can be verified end-to-end.

---

## Quick start — Docker (recommended)

### Prerequisites
- [Docker Desktop](https://docs.docker.com/get-docker/) (includes Docker Compose)

### Steps

```bash
# 1. Clone / download this repository
git clone https://github.com/ajaykumarvarma/EasyCaptcha.git
cd easycaptcha

# 2. Set a real API secret before starting
#    Open docker/docker-compose.yml and replace the placeholder value for API_SECRET_KEY.
#    Generate a strong key with:
python -c "import secrets; print(secrets.token_hex(32))"

# 3. Start the service — MongoDB is included, nothing else to install
docker compose -f docker/docker-compose.yml up --build
```

The service is now running at **http://localhost:8080**.

Open **http://localhost:8080/docs** in your browser to explore the interactive API.

Test it immediately with curl:

```bash
# Generate a captcha — returns token_id, base64 image, and captcha_length
curl http://localhost:8080/captcha
```

---

## Manual setup (without Docker)

### Prerequisites
- Python 3.9 or newer
- MongoDB 6 or newer — [local download](https://www.mongodb.com/try/download/community)
  or [MongoDB Atlas (free tier)](https://www.mongodb.com/atlas)

### 1 — Start the backend

```bash
cd backend

# Copy and fill in the env file
cp .env.example .env
# Edit .env — set MONGODB_URL and API_SECRET_KEY at minimum

# Install Python dependencies
pip install -r requirements.txt

# Start the service
uvicorn captcha_service:app --host 0.0.0.0 --port 8080 --reload
```

Service is live at **http://localhost:8080**  
Interactive API docs: **http://localhost:8080/docs**  
Alternative docs (ReDoc): **http://localhost:8080/redoc**

### 2 — Copy the frontend components

```bash
cp frontend/ServerCaptcha.jsx   your-project/src/components/
cp frontend/CanvasCaptcha.jsx   your-project/src/components/
```

No `npm install` needed — the components have **zero external dependencies**.

---

## Configuration reference

All settings live in `backend/.env` (or as Docker environment variables).

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `MONGODB_URL` | **Yes** | — | MongoDB connection string |
| `API_SECRET_KEY` | **Yes** | — | Secret key your backend uses to call `/captcha/verify` and `/stats` |
| `DB_NAME` | No | `easycaptcha` | MongoDB database name |
| `ALLOWED_ORIGINS` | No | `*` | Comma-separated CORS-allowed origins |
| `TOKEN_TTL_MINUTES` | No | `5` | Minutes before an unused token auto-expires |
| `RATE_LIMIT_PER_MIN` | No | `15` | Max `GET /captcha` calls per IP per minute |
| `VERIFY_LIMIT_PER_MIN` | No | `60` | Max `POST /captcha/verify` calls per IP per minute |
| `AUDIO_LIMIT_PER_MIN` | No | `20` | Max `GET /captcha/audio/{id}` calls per IP per minute |
| `CAPTCHA_LENGTH` | No | `5` | Fixed length when min/max not set (kept for backward compat) |
| `CAPTCHA_LENGTH_MIN` | No | `CAPTCHA_LENGTH` | Minimum challenge length for per-request randomisation |
| `CAPTCHA_LENGTH_MAX` | No | `CAPTCHA_LENGTH` | Maximum challenge length for per-request randomisation |
| `CAPTCHA_MIN_SOLVE_MS` | No | `1500` | Minimum ms between token creation and verify (0 = disabled) |
| `ENFORCE_IP_BINDING` | No | `false` | Reject verify if `client_ip` doesn't match token origin IP |
| `LOG_LEVEL` | No | `INFO` | `DEBUG` / `INFO` / `WARNING` / `ERROR` |

**Example `.env` for production:**

```env
MONGODB_URL=mongodb+srv://user:pass@cluster.mongodb.net
API_SECRET_KEY=a4f8c2e1d9b3a7f0c5e2d8b4a1f7c3e6d9b2a8f5c1e4d7b0a3f6c9e2d5b8a1
DB_NAME=easycaptcha
ALLOWED_ORIGINS=https://yourdomain.com
TOKEN_TTL_MINUTES=5
RATE_LIMIT_PER_MIN=15
CAPTCHA_LENGTH=5
CAPTCHA_LENGTH_MIN=4
CAPTCHA_LENGTH_MAX=6
CAPTCHA_MIN_SOLVE_MS=1500
ENFORCE_IP_BINDING=false
```

> **Tip — changing `CAPTCHA_LENGTH`**: The API response always includes
> `captcha_length` as a field, so the `ServerCaptcha` React component adapts
> automatically without any prop changes.  For `CanvasCaptcha` pass the
> `length` prop (e.g. `<CanvasCaptcha length={6} />`).

> `length` prop (e.g. `<CanvasCaptcha length={6} />`).

---

## HTTPS in production

Running EasyCaptcha without TLS exposes the `X-API-Key` header and active token IDs in plain text — treat HTTPS as mandatory, not optional.

Choose the proxy that fits your stack:

---

### Option A — Caddy (recommended; automatic TLS)

Caddy obtains and renews Let's Encrypt certificates with **zero configuration**.

**Install** (Debian/Ubuntu):

```bash
sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https curl
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' \
  | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' \
  | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt update && sudo apt install caddy
```

**`/etc/caddy/Caddyfile`:**

```
captcha.yourdomain.com {
    # Automatic TLS via Let's Encrypt — no config needed

    reverse_proxy localhost:8080 {
        header_up X-Real-IP {remote_host}
    }

    # HSTS — force browsers to use HTTPS for 1 year
    header Strict-Transport-Security "max-age=31536000; includeSubDomains; preload"
}
```

```bash
sudo systemctl enable --now caddy
sudo systemctl reload caddy
```

Done. Caddy handles certificate issuance and auto-renewal.

---

### Option B — nginx + Let's Encrypt (Certbot)

**Install:**

```bash
sudo apt install -y nginx certbot python3-certbot-nginx
```

**Obtain a certificate:**

```bash
sudo certbot --nginx -d captcha.yourdomain.com
```

**`/etc/nginx/sites-available/easycaptcha`:**

```nginx
# Redirect HTTP → HTTPS
server {
    listen 80;
    server_name captcha.yourdomain.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name captcha.yourdomain.com;

    ssl_certificate     /etc/letsencrypt/live/captcha.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/captcha.yourdomain.com/privkey.pem;

    # Modern TLS only
    ssl_protocols       TLSv1.2 TLSv1.3;
    ssl_prefer_server_ciphers off;

    # HSTS — tell browsers to always use HTTPS
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

    # Pass real client IP to EasyCaptcha (required for IP binding and rate limiting)
    proxy_set_header  X-Real-IP        $remote_addr;
    proxy_set_header  X-Forwarded-For  $proxy_add_x_forwarded_for;
    proxy_set_header  X-Forwarded-Proto https;
    proxy_set_header  Host             $host;

    # Tighten upload body size (captcha images are small)
    client_max_body_size 64k;

    location / {
        proxy_pass http://localhost:8080;
        proxy_read_timeout 30s;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/easycaptcha /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

Auto-renewal is enabled by `certbot install` — verify with:

```bash
sudo certbot renew --dry-run
```

---

### Option C — Docker Compose with nginx

Add a `nginx` service to your `docker-compose.yml` that handles TLS and proxies to the `captcha` service:

```yaml
services:
  captcha:
    build: ../backend
    env_file: .env
    expose:
      - "8080"          # internal only — not published to the host

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/conf.d/default.conf:ro
      - /etc/letsencrypt:/etc/letsencrypt:ro
    depends_on:
      - captcha
```

`nginx.conf` (same content as Option B, but `proxy_pass http://captcha:8080`).

---

### Forwarded IP and IP binding

When EasyCaptcha is behind a proxy, the real client IP arrives in `X-Forwarded-For` or `X-Real-IP`. The service reads the first untrusted IP from `X-Forwarded-For` automatically.

> If you enable `ENFORCE_IP_BINDING=true`, make sure your proxy always sets `X-Real-IP $remote_addr` (nginx) or `header_up X-Real-IP {remote_host}` (Caddy) so the token IP matches the verify IP.

---

### Environment variables to update for production

```env
# Lock CORS to your exact frontend origin — never use * in production
ALLOWED_ORIGINS=https://yourdomain.com

# Use HTTPS in your service URL when calling from the frontend
# (nothing to set here — just make sure your API_BASE in the frontend points to https://)
```

---

## Step-by-step integration guide

This section walks through adding EasyCaptcha to every common form on your website.

---

### Step 1 — Prepare your project

**1a. Copy the components** (already done above)

**1b. Store the EasyCaptcha URL in your frontend environment**

React (`.env` in your React project root):
```env
REACT_APP_CAPTCHA_URL=http://localhost:8080
```

Next.js (`.env.local`):
```env
NEXT_PUBLIC_CAPTCHA_URL=http://localhost:8080
```

**1c. Store the API secret key in your backend environment**

```env
# .env in YOUR app backend
CAPTCHA_API_SECRET=same-value-as-API_SECRET_KEY-in-EasyCaptcha
CAPTCHA_SERVICE_URL=http://localhost:8080
```

> **Never** put the API secret in your frontend code or any `.env` file that
> gets bundled with the browser.  It belongs only in your backend.

---

### Step 2 — Sign Up form

#### 2a — Frontend (React)

```jsx
// src/pages/SignupPage.jsx
import { useState } from 'react';
import ServerCaptcha from '../components/ServerCaptcha';

export default function SignupPage() {
  const [form, setForm] = useState({ firstName: '', email: '', password: '' });
  const [captcha, setCaptcha]           = useState(null);  // { tokenId, answer }
  const [resetTrigger, setResetTrigger] = useState(0);
  const [captchaError, setCaptchaError] = useState('');
  const [submitting, setSubmitting]     = useState(false);
  const [message, setMessage]           = useState('');

  const handleChange = (e) =>
    setForm((prev) => ({ ...prev, [e.target.name]: e.target.value }));

  const handleSubmit = async (e) => {
    e.preventDefault();

    // 1. Ensure the user completed the captcha
    if (!captcha) {
      setCaptchaError('Please complete the security check before continuing.');
      return;
    }

    setSubmitting(true);
    setCaptchaError('');

    try {
      const res = await fetch('/api/auth/signup', {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          first_name:       form.firstName,
          email:            form.email,
          password:         form.password,
          // 2. Include the captcha data
          captcha_token_id: captcha.tokenId,
          captcha_answer:   captcha.answer,
        }),
      });

      const data = await res.json();

      if (!res.ok) {
        setMessage(data.message || 'Signup failed. Please try again.');
        // 3. Always refresh the captcha on failure — tokens are single-use
        setResetTrigger((t) => t + 1);
      } else {
        setMessage('Account created! Please check your email to verify.');
      }
    } catch {
      setMessage('Network error — please try again.');
      setResetTrigger((t) => t + 1);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} style={{ maxWidth: 420, margin: '40px auto' }}>
      <h2>Create account</h2>

      <label>First name
        <input name="firstName" value={form.firstName}
          onChange={handleChange} required />
      </label>

      <label>Email
        <input name="email" type="email" value={form.email}
          onChange={handleChange} required />
      </label>

      <label>Password
        <input name="password" type="password" value={form.password}
          onChange={handleChange} minLength={8} required />
      </label>

      {/* captcha_length is read from the API automatically — no extra props needed */}
      <ServerCaptcha
        apiUrl={process.env.REACT_APP_CAPTCHA_URL}
        onReady={setCaptcha}
        resetTrigger={resetTrigger}
        externalError={captchaError}
      />

      {message && <p>{message}</p>}

      <button type="submit" disabled={submitting}>
        {submitting ? 'Creating account…' : 'Sign up'}
      </button>
    </form>
  );
}
```

#### 2b — What your backend must do

```
1. Receive { first_name, email, password, captcha_token_id, captcha_answer }
2. Call EasyCaptcha  POST /captcha/verify  →  { valid: true/false }
3. If valid == false  →  return 400 "Invalid security code"
4. Proceed with normal signup logic
```

See [Backend verification examples](#backend-verification-examples) for complete code.

---

### Step 3 — Sign In / Login form

#### 3a — Frontend (React)

```jsx
// src/pages/LoginPage.jsx
import { useState } from 'react';
import ServerCaptcha from '../components/ServerCaptcha';

export default function LoginPage() {
  const [identifier, setIdentifier] = useState('');
  const [password, setPassword]     = useState('');
  const [captcha, setCaptcha]           = useState(null);
  const [resetTrigger, setResetTrigger] = useState(0);
  const [captchaError, setCaptchaError] = useState('');
  const [error, setError]           = useState('');
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (!captcha) {
      setCaptchaError('Please complete the security check.');
      return;
    }

    setSubmitting(true);
    setError('');
    setCaptchaError('');

    const res = await fetch('/api/auth/login', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        identifier,
        password,
        captcha_token_id: captcha.tokenId,
        captcha_answer:   captcha.answer,
      }),
    });

    if (res.ok) {
      const { token } = await res.json();
      localStorage.setItem('token', token);
      window.location.href = '/dashboard';
    } else {
      const data = await res.json();
      setError(data.message || 'Incorrect credentials.');
      // Refresh captcha — tokens are single-use even on wrong answers
      setResetTrigger((t) => t + 1);
    }

    setSubmitting(false);
  };

  return (
    <form onSubmit={handleSubmit} style={{ maxWidth: 400, margin: '40px auto' }}>
      <h2>Sign in</h2>

      <label>Email or username
        <input value={identifier} onChange={(e) => setIdentifier(e.target.value)}
          required autoComplete="username" />
      </label>

      <label>Password
        <input type="password" value={password}
          onChange={(e) => setPassword(e.target.value)} required />
      </label>

      <ServerCaptcha
        apiUrl={process.env.REACT_APP_CAPTCHA_URL}
        onReady={setCaptcha}
        resetTrigger={resetTrigger}
        externalError={captchaError}
      />

      {error && <p style={{ color: 'red' }}>{error}</p>}

      <button type="submit" disabled={submitting}>
        {submitting ? 'Signing in…' : 'Sign in'}
      </button>
    </form>
  );
}
```

#### 3b — Backend minimum logic

```
1. Receive { identifier, password, captcha_token_id, captcha_answer }
2. Call EasyCaptcha  POST /captcha/verify  →  { valid: true/false }
3. If valid == false  →  return 400 "Invalid security code"
4. Look up user, verify password
5. If credentials wrong  →  return 401 "Incorrect credentials"
6. Return JWT / session cookie
```

---

### Step 4 — Forgot Password form

#### 4a — Frontend (React)

```jsx
// src/pages/ForgotPasswordPage.jsx
import { useState } from 'react';
import ServerCaptcha from '../components/ServerCaptcha';

export default function ForgotPasswordPage() {
  const [email, setEmail]               = useState('');
  const [captcha, setCaptcha]           = useState(null);
  const [resetTrigger, setResetTrigger] = useState(0);
  const [captchaError, setCaptchaError] = useState('');
  const [message, setMessage]           = useState('');
  const [submitting, setSubmitting]     = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (!captcha) {
      setCaptchaError('Please complete the security check.');
      return;
    }

    setSubmitting(true);
    setCaptchaError('');

    await fetch('/api/auth/forgot-password', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        email,
        captcha_token_id: captcha.tokenId,
        captcha_answer:   captcha.answer,
      }),
    });

    // Always show the same message — prevents email enumeration
    setMessage('If that email is registered, a reset link has been sent.');
    setResetTrigger((t) => t + 1);
    setSubmitting(false);
  };

  return (
    <form onSubmit={handleSubmit} style={{ maxWidth: 400, margin: '40px auto' }}>
      <h2>Reset your password</h2>
      <p>Enter your email and we will send you a reset link.</p>

      <label>Email address
        <input type="email" value={email}
          onChange={(e) => setEmail(e.target.value)} required />
      </label>

      <ServerCaptcha
        apiUrl={process.env.REACT_APP_CAPTCHA_URL}
        onReady={setCaptcha}
        resetTrigger={resetTrigger}
        externalError={captchaError}
      />

      {message && <p style={{ color: 'green' }}>{message}</p>}

      <button type="submit" disabled={submitting}>
        {submitting ? 'Sending…' : 'Send reset link'}
      </button>
    </form>
  );
}
```

#### 4b — Backend minimum logic

```
1. Receive { email, captcha_token_id, captcha_answer }
2. Call EasyCaptcha  POST /captcha/verify  →  { valid: true/false }
3. If valid == false  →  return 400 "Invalid security code"
4. Look up user by email silently (do NOT reveal if email exists — prevents enumeration)
5. If found  →  generate reset token, send email link
6. Always return the same success message regardless of whether email exists
```

---

### Step 5 — Contact / Submit form (CanvasCaptcha)

Use `CanvasCaptcha` when you cannot run a backend service.
Validation happens entirely in the browser — no API calls needed.

#### 5a — Frontend (React) with imperative ref

```jsx
// src/pages/ContactPage.jsx
import { useRef, useState } from 'react';
import CanvasCaptcha from '../components/CanvasCaptcha';

export default function ContactPage() {
  const captchaRef              = useRef(null);
  const [name, setName]         = useState('');
  const [email, setEmail]       = useState('');
  const [message, setMessage]   = useState('');
  const [status, setStatus]     = useState('');
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();

    // validate() returns true/false, auto-shows error + redraws canvas on failure
    if (!captchaRef.current.validate()) return;

    setSubmitting(true);

    const res = await fetch('/api/contact', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, email, message }),
    });

    if (res.ok) {
      setStatus('Message sent!');
      setName(''); setEmail(''); setMessage('');
      captchaRef.current.refresh();
    } else {
      setStatus('Something went wrong. Please try again.');
    }

    setSubmitting(false);
  };

  return (
    <form onSubmit={handleSubmit} style={{ maxWidth: 480, margin: '40px auto' }}>
      <h2>Get in touch</h2>

      <label>Name
        <input value={name} onChange={(e) => setName(e.target.value)} required />
      </label>

      <label>Email
        <input type="email" value={email}
          onChange={(e) => setEmail(e.target.value)} required />
      </label>

      <label>Message
        <textarea value={message} onChange={(e) => setMessage(e.target.value)}
          rows={5} required />
      </label>

      {/* No apiUrl prop — fully client-side */}
      {/* Use length={6} if you want 6 characters instead of the default 5 */}
      <CanvasCaptcha ref={captchaRef} />

      {status && <p>{status}</p>}

      <button type="submit" disabled={submitting}>
        {submitting ? 'Sending…' : 'Send message'}
      </button>
    </form>
  );
}
```

The `/api/contact` backend route needs **no captcha code** — the check already happened in the browser.

---

### Plain HTML — no React

#### ServerCaptcha (vanilla JS)

```html
<!DOCTYPE html>
<html>
<body>

<form id="loginForm">
  <h2>Sign In</h2>
  <input type="email"    id="email"    placeholder="Email"    required />
  <input type="password" id="password" placeholder="Password" required />

  <div id="captchaImageWrap"
    style="border:1px solid #e2e8f0;border-radius:8px;overflow:hidden;min-height:62px;
           display:flex;align-items:center;justify-content:center;">
    <span id="captchaLoading" style="font-size:12px;color:#64748b;">Loading…</span>
    <img id="captchaImg" style="display:none;width:100%;height:62px;object-fit:fill;"
      alt="Security code" />
  </div>
  <button type="button" id="captchaRefresh">↺ New image</button>
  <input type="text" id="captchaInput" placeholder="Type the characters above"
    autocomplete="off" style="letter-spacing:6px;font-size:18px;font-family:monospace;width:100%;" />
  <p id="captchaError" style="color:red;font-size:12px;display:none;"></p>

  <button type="submit">Sign in</button>
  <p id="formMessage"></p>
</form>

<script>
  const CAPTCHA_URL  = 'http://localhost:8080';  // ← your EasyCaptcha URL
  let currentTokenId = null;
  let captchaLength  = 5;

  async function loadCaptcha() {
    document.getElementById('captchaImg').style.display    = 'none';
    document.getElementById('captchaLoading').style.display = 'block';
    document.getElementById('captchaInput').value          = '';
    document.getElementById('captchaError').style.display  = 'none';
    currentTokenId = null;

    try {
      const res  = await fetch(`${CAPTCHA_URL}/captcha`);
      const data = await res.json();
      currentTokenId = data.token_id;
      captchaLength  = data.captcha_length ?? 5;

      document.getElementById('captchaInput').maxLength    = captchaLength;
      document.getElementById('captchaInput').placeholder  = `Type the ${captchaLength} characters above`;

      const img = document.getElementById('captchaImg');
      img.src = `data:image/png;base64,${data.image_b64}`;
      img.style.display = 'block';
      document.getElementById('captchaLoading').style.display = 'none';
    } catch {
      document.getElementById('captchaLoading').textContent = 'Failed — click ↺';
    }
  }

  document.getElementById('captchaRefresh').addEventListener('click', loadCaptcha);

  document.getElementById('loginForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const answer = document.getElementById('captchaInput').value.trim();

    if (!answer || answer.length < captchaLength) {
      document.getElementById('captchaError').textContent   = 'Please complete the security check.';
      document.getElementById('captchaError').style.display = 'block';
      return;
    }

    const res = await fetch('/api/auth/login', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        email: document.getElementById('email').value,
        password: document.getElementById('password').value,
        captcha_token_id: currentTokenId,
        captcha_answer: answer,
      }),
    });

    const data = await res.json();
    document.getElementById('formMessage').textContent =
      res.ok ? 'Signed in!' : (data.message || 'Login failed.');

    if (!res.ok) loadCaptcha();
  });

  loadCaptcha();
</script>
</body>
</html>
```

#### CanvasCaptcha (vanilla JS — no backend at all)

```html
<!DOCTYPE html>
<html>
<body>

<form id="contactForm">
  <h2>Contact us</h2>
  <input type="text"  id="name"    placeholder="Name"    required />
  <input type="email" id="email"   placeholder="Email"   required />
  <textarea id="message" placeholder="Message" required></textarea>

  <canvas id="captchaCanvas" width="260" height="62"
    style="border:1px solid #e2e8f0;border-radius:8px;display:block;"></canvas>
  <button type="button" onclick="refreshCanvas()">↺ New code</button>
  <input type="text" id="captchaAnswer" placeholder="Type the 5 characters above"
    maxlength="5" autocomplete="off"
    style="letter-spacing:6px;font-size:18px;font-family:monospace;width:100%;" />
  <p id="captchaErr" style="color:red;font-size:12px;"></p>

  <button type="submit">Send</button>
</form>

<script>
  const CHARS  = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789';
  const COLORS = ['#1e3a8a','#6b21a8','#9d174d','#0c4a6e','#14532d','#92400e'];
  let   currentCode = '';

  function refreshCanvas() {
    const canvas = document.getElementById('captchaCanvas');
    const ctx    = canvas.getContext('2d');
    const W = canvas.width, H = canvas.height;

    currentCode = '';
    for (let i = 0; i < 5; i++)
      currentCode += CHARS[Math.floor(Math.random() * CHARS.length)];

    const g = ctx.createLinearGradient(0, 0, W, H);
    g.addColorStop(0, '#eef4fd'); g.addColorStop(1, '#f1f5f9');
    ctx.fillStyle = g; ctx.fillRect(0, 0, W, H);

    for (let i = 0; i < 6; i++) {
      ctx.beginPath();
      ctx.strokeStyle = `rgba(${Math.random()*120|0},${Math.random()*120|0},${Math.random()*180|0},0.25)`;
      ctx.moveTo(Math.random()*W, Math.random()*H);
      ctx.bezierCurveTo(Math.random()*W,Math.random()*H,Math.random()*W,Math.random()*H,Math.random()*W,Math.random()*H);
      ctx.stroke();
    }

    const sw = (W - 24) / currentCode.length;
    currentCode.split('').forEach((ch, i) => {
      ctx.save();
      ctx.translate(14 + i * sw + sw / 2, H / 2 + 9);
      ctx.rotate((Math.random() - 0.5) * 0.55);
      ctx.font      = `bold ${22 + Math.random()*7|0}px Arial,sans-serif`;
      ctx.fillStyle = COLORS[i % COLORS.length];
      ctx.textAlign = 'center';
      ctx.fillText(ch, 0, 0);
      ctx.restore();
    });

    document.getElementById('captchaAnswer').value = '';
    document.getElementById('captchaErr').textContent = '';
  }

  document.getElementById('contactForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const answer = document.getElementById('captchaAnswer').value.trim().toUpperCase();

    if (answer !== currentCode) {
      document.getElementById('captchaErr').textContent = 'Incorrect — a new image has loaded.';
      refreshCanvas();
      return;
    }

    await fetch('/api/contact', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name:    document.getElementById('name').value,
        email:   document.getElementById('email').value,
        message: document.getElementById('message').value,
      }),
    });
    alert('Message sent!');
  });

  refreshCanvas();
</script>
</body>
</html>
```

---

## Backend verification examples

These go inside **your own application's backend** — not in EasyCaptcha itself.
Replace the placeholder values:
- `http://localhost:8080` → your EasyCaptcha service URL
- `your-api-secret` → value of `API_SECRET_KEY` in EasyCaptcha

---

### FastAPI (Python)

```python
# routers/auth.py in your app
import os, httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()

CAPTCHA_URL    = os.environ["CAPTCHA_SERVICE_URL"]  # http://localhost:8080
CAPTCHA_SECRET = os.environ["CAPTCHA_API_SECRET"]


async def verify_captcha(token_id: str, answer: str) -> bool:
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            res = await client.post(
                f"{CAPTCHA_URL}/captcha/verify",
                json={"token_id": token_id, "answer": answer},
                headers={"X-API-Key": CAPTCHA_SECRET},
            )
        return res.status_code == 200 and res.json().get("valid", False)
    except Exception:
        return False  # fail closed on service errors


class SignupRequest(BaseModel):
    first_name:       str
    email:            str
    password:         str
    captcha_token_id: str
    captcha_answer:   str


@router.post("/auth/signup")
async def signup(payload: SignupRequest):
    if not await verify_captcha(payload.captcha_token_id, payload.captcha_answer):
        raise HTTPException(400, "Invalid security code. Please try again.")

    # ... your normal signup logic
    return {"message": "Account created."}


@router.post("/auth/login")
async def login(payload: dict):
    if not await verify_captcha(
        payload.get("captcha_token_id", ""),
        payload.get("captcha_answer", ""),
    ):
        raise HTTPException(400, "Invalid security code. Please try again.")

    # ... verify credentials, return token
```

---

### Express.js (Node.js)

```javascript
// routes/auth.js in your app
const express = require('express');
const router  = express.Router();

const CAPTCHA_URL    = process.env.CAPTCHA_SERVICE_URL;
const CAPTCHA_SECRET = process.env.CAPTCHA_API_SECRET;

async function verifyCaptcha(tokenId, answer) {
  try {
    const res = await fetch(`${CAPTCHA_URL}/captcha/verify`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-API-Key': CAPTCHA_SECRET },
      body:   JSON.stringify({ token_id: tokenId, answer }),
    });
    return (await res.json()).valid === true;
  } catch { return false; }
}

router.post('/signup', async (req, res) => {
  const { firstName, email, password, captcha_token_id, captcha_answer } = req.body;

  if (!await verifyCaptcha(captcha_token_id, captcha_answer))
    return res.status(400).json({ message: 'Invalid security code.' });

  // ... create user
  res.status(201).json({ message: 'Account created.' });
});

router.post('/login', async (req, res) => {
  const { identifier, password, captcha_token_id, captcha_answer } = req.body;

  if (!await verifyCaptcha(captcha_token_id, captcha_answer))
    return res.status(400).json({ message: 'Invalid security code.' });

  // ... verify credentials
});

module.exports = router;
```

---

### Django (Python)

```python
# views/auth.py in your app
import os, json, requests
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

CAPTCHA_URL    = os.getenv("CAPTCHA_SERVICE_URL", "http://localhost:8080")
CAPTCHA_SECRET = os.environ["CAPTCHA_API_SECRET"]


def verify_captcha(token_id: str, answer: str) -> bool:
    try:
        r = requests.post(
            f"{CAPTCHA_URL}/captcha/verify",
            json={"token_id": token_id, "answer": answer},
            headers={"X-API-Key": CAPTCHA_SECRET},
            timeout=10,
        )
        return r.status_code == 200 and r.json().get("valid", False)
    except Exception:
        return False


@csrf_exempt
def signup(request):
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    data     = json.loads(request.body)
    token_id = data.get("captcha_token_id", "")
    answer   = data.get("captcha_answer", "")

    if not verify_captcha(token_id, answer):
        return JsonResponse({"message": "Invalid security code."}, status=400)

    # ... create user
    return JsonResponse({"message": "Account created."}, status=201)
```

---

### PHP

```php
<?php
define('CAPTCHA_URL',    getenv('CAPTCHA_SERVICE_URL') ?: 'http://localhost:8080');
define('CAPTCHA_SECRET', getenv('CAPTCHA_API_SECRET'));

function verifyCaptcha(string $tokenId, string $answer): bool {
    $ctx = stream_context_create(['http' => [
        'method'  => 'POST',
        'header'  => "Content-Type: application/json\r\nX-API-Key: " . CAPTCHA_SECRET,
        'content' => json_encode(['token_id' => $tokenId, 'answer' => $answer]),
        'timeout' => 10,
    ]]);
    $result = @file_get_contents(CAPTCHA_URL . '/captcha/verify', false, $ctx);
    return $result && (json_decode($result, true)['valid'] ?? false) === true;
}

// POST /api/signup
$body    = json_decode(file_get_contents('php://input'), true);
$tokenId = $body['captcha_token_id'] ?? '';
$answer  = $body['captcha_answer']   ?? '';

if (!verifyCaptcha($tokenId, $answer)) {
    http_response_code(400);
    echo json_encode(['message' => 'Invalid security code.']);
    exit;
}
// ... create user
http_response_code(201);
echo json_encode(['message' => 'Account created.']);
```

---

## API reference

### `GET /captcha` — Generate a challenge

**Response — 200**

```json
{
  "token_id":        "550e8400-e29b-41d4-a716-446655440000",
  "image_b64":       "<base64-encoded PNG>",
  "captcha_length":  5,
  "audio_available": true
}
```

`audio_available` is `true` when `espeak-ng` is installed on the server — show the audio button only when this is `true`.

The `captcha_length` field tells the frontend exactly how many characters to expect. The `ServerCaptcha` React component reads this automatically; in vanilla JS, set `input.maxLength = data.captcha_length`.

**Error — 429** Rate limit exceeded.

---

### `GET /captcha/audio/{token_id}` — Audio accessibility (WCAG 2.1)

Returns a WAV file that spells out each character with a clear pause between them. Designed for visually impaired users.

- Does **not** consume the token — user still types the answer.
- Requires `espeak-ng` on the server (included in the Docker image).
- Returns `503` if `espeak-ng` is not installed.
- Returns `404` if the token doesn't exist or is already used.
- Rate limited to `AUDIO_LIMIT_PER_MIN` (default 20) per IP/min.

---

### `POST /captcha/verify` — Verify an answer

**Headers**

```
X-API-Key: <your API_SECRET_KEY>
Content-Type: application/json
```

**Body**

```json
{ "token_id": "...", "answer": "Ab3Kz", "client_ip": "1.2.3.4", "honeypot": "" }
```

`client_ip` is optional — only required when `ENFORCE_IP_BINDING=true`. Pass the end-user's IP as seen by your backend.

`honeypot` is always `""` for real users. Pass the value from `onReady` payload directly: `{ token_id: data.tokenId, answer: data.answer, honeypot: data.honeypot }`. The backend rejects any non-empty value with `error_code: "bot_suspected"` before touching the DB.

**Response — 200**

```json
{ "valid": true }
```

```json
{ "valid": false, "error_code": "wrong_answer" }
```

Possible `error_code` values (for your backend logs only — never surface to users):

| Code | Meaning |
|------|---------|
| `not_found` | Token ID doesn't exist or was already used |
| `expired` | Token TTL has elapsed |
| `wrong_answer` | Case-sensitive answer mismatch |
| `too_fast` | Answer arrived faster than `CAPTCHA_MIN_SOLVE_MS` ms |
| `bot_suspected` | Honeypot field was non-empty |
| `ip_missing` | `ENFORCE_IP_BINDING=true` but `client_ip` not provided |
| `ip_mismatch` | `ENFORCE_IP_BINDING=true` and IPs don't match |

**Error — 401** Missing or wrong `X-API-Key`.
**Error — 429** Rate limit exceeded.

---

### `GET /stats` — Token statistics

Requires the same `X-API-Key` header.

**Response — 200**

```json
{
  "tokens_in_db":    42,
  "active_unused":   8,
  "verified":        34,
  "service_version": "1.3.0"
}
```

Use this endpoint for monitoring dashboards or uptime checks.
Note: `tokens_in_db` reflects documents currently in MongoDB — the TTL index
automatically removes expired tokens approximately every 60 seconds, so this
number stays low in production.

**Error — 401** Missing or wrong `X-API-Key`.

---

### `GET /health` — Health check

```json
{ "status": "ok", "version": "1.3.0", "service": "EasyCaptcha", "audio_available": true }
```

No authentication needed.  Use for load balancer health probes and uptime monitoring.

---

## Running the tests

The test suite covers image generation, character set correctness, rate limiting logic, minimum solve time configuration, and audio availability — all without needing a running server or MongoDB.

```bash
cd backend

# Install Python dependencies (if not already done)
pip install -r requirements.txt

# Install test-only extras (not in requirements.txt)
pip install -r requirements-dev.txt

# Run all unit tests (41 tests, ~0.6 s)
MONGODB_URL=mongodb://localhost:27017 API_SECRET_KEY=test \
  pytest test_captcha.py -v
```

Expected output:

```
...
41 passed, 9 skipped
```

Skipped tests require either:
- A live running service (integration tests) — add `--integration` flag
- `espeak-ng` installed (audio WAV generation tests)

---

## Security notes

### Built-in protections

| Protection | Detail |
|-----------|--------|
| Code never sent to browser | Only the PNG image is returned. The answer is stored in MongoDB only. |
| Single-use tokens | Marked used immediately after the first verify call — replay is impossible. |
| TTL expiry | MongoDB TTL index auto-deletes tokens after `TOKEN_TTL_MINUTES` (default 5). |
| Per-IP rate limiting | Sliding 60-second window on all three endpoints. Configurable. |
| **Minimum solve time** | Answers arriving faster than `CAPTCHA_MIN_SOLVE_MS` (default 1500 ms) are rejected. Automated solvers typically answer in < 50 ms; real humans take ≥ 2 s. |
| **Honeypot hidden field** | `ServerCaptcha` renders a CSS-hidden `name="website"` input (not `type="hidden"`, which bots skip). Bots fill every visible input field, humans don't. Non-empty value = immediate rejection, no DB hit. |
| **Strict case-sensitivity** | Answer must match the displayed characters exactly (upper/lower/digit). |
| **Enhanced image distortion** | Wave distortion, variable rotation (±33°), arc noise, variable character spacing, foreground lines, and 180 background dots. Hard to batch-OCR. |
| Security headers | `X-Content-Type-Options`, `X-Frame-Options`, `Cache-Control: no-store` on every response. |
| API key guard | `/captcha/verify` and `/stats` require `X-API-Key` — only your backend can call them. |
| Constant-time comparison | `secrets.compare_digest` prevents timing attacks on the API key check. |
| **IP binding (optional)** | When `ENFORCE_IP_BINDING=true`, the verify IP must match the generate IP. Prevents token-theft attacks. |
| **MongoDB auth (optional)** | `docker-compose.yml` supports dedicated `captcha_svc` user with least-privilege `readWrite` on the `easycaptcha` DB only. |
| **Audio CAPTCHA (WCAG 2.1)** | `GET /captcha/audio/{token_id}` reads characters aloud via `espeak-ng`. Screen-reader accessible. Does not consume the token. |

### Limitations

| Concern | Recommendation |
|---------|---------------|
| Advanced OCR/ML | Combine with login attempt rate limiting (lock after N failures per IP/account). |
| CanvasCaptcha | Client-side only — do not use for high-value flows like login or payment. |
| In-memory rate limiter | Resets on restart; not shared across multiple instances. Swap to Redis for multi-instance deployments. |
| HTTPS | Always serve EasyCaptcha over HTTPS in production. |
| Audio CAPTCHA | Inherently less OCR-resistant than images. Use as accessibility supplement, not the primary channel. |

### Production checklist

- [ ] `API_SECRET_KEY` is a strong random value (32+ hex chars)
- [ ] `ALLOWED_ORIGINS` is set to your exact frontend domain (not `*`)
- [ ] Service is behind a reverse proxy (nginx / Caddy) with TLS
- [ ] `TOKEN_TTL_MINUTES` is 5 or lower
- [ ] `CAPTCHA_MIN_SOLVE_MS` is at least 1500 (the default)
- [ ] `/health` is monitored by your uptime tool
- [ ] Login/signup endpoints also have their own rate limiting

---

## Troubleshooting

### Captcha image not loading

1. Is EasyCaptcha running?  Check: `curl http://localhost:8080/health`
2. Is the `apiUrl` prop / `CAPTCHA_URL` variable correct?
3. Does the browser console show a CORS error?
   - Fix: set `ALLOWED_ORIGINS=http://localhost:3000` (your frontend origin) in `.env`, restart.

### `/captcha/verify` always returns `{ "valid": false }`

1. Does `API_SECRET_KEY` in EasyCaptcha exactly match `CAPTCHA_API_SECRET` in your app?
2. Are you sending `token_id` (snake_case) in the JSON body?
3. Has the token expired?  Increase `TOKEN_TTL_MINUTES` if your forms take a long time.
4. Was the token already used?  Each token is single-use.  Refresh the captcha after each attempt.

### 429 Too Many Requests

Increase `RATE_LIMIT_PER_MIN` in `.env` (default 15/min).  For development use `100`.

### Captcha image is blurry / uses a tiny font

The Dockerfile installs `fonts-dejavu-core` which provides a clear bold font.  
Rebuild: `docker compose -f docker/docker-compose.yml up --build`  
Manual: `sudo apt-get install fonts-dejavu-core` (Ubuntu/Debian)

### `ServerCaptcha` fires `onReady` at the wrong character count

The component reads `captcha_length` from the API response automatically.
If you changed `CAPTCHA_LENGTH` in `.env`, restart the service so the new value
is returned in the API response.  No frontend code changes needed.

### `CanvasCaptcha` shows wrong character count

Pass the `length` prop to match your preference:
```jsx
<CanvasCaptcha ref={captchaRef} length={6} />
```

---

## FAQ

**Can I use this without MongoDB?**  
Use `CanvasCaptcha` — fully browser-side, no database needed.

**Does this work with Next.js?**  
Yes.  Use `NEXT_PUBLIC_CAPTCHA_URL` as the `apiUrl` prop.  Call `/captcha/verify` from a Next.js API Route.

**Does this work with Vue or Angular?**  
The backend API is plain HTTP JSON.  Copy the `fetch` calls from `ServerCaptcha.jsx` and adapt them to your framework.

**How do I monitor how many captchas are being solved?**  
Use `GET /stats` (requires `X-API-Key`). Returns `tokens_in_db`, `active_unused`, `verified`, and `service_version`.

**How do I change the number of characters?**  
Set `CAPTCHA_LENGTH` in `.env` and restart.  `ServerCaptcha` adapts via `captcha_length` in the API response.  For `CanvasCaptcha` pass `length={N}`.

**Can I run multiple EasyCaptcha instances?**  
Yes — all share the same MongoDB.  For cross-instance rate limiting, replace `_check_rate_limit` with a Redis-backed implementation.

**How do I run the tests?**  
See [Running the tests](#running-the-tests) above.

---

## Contributing

Pull requests are welcome.  
Please open an issue first for large changes.

---

## License

MIT — see [LICENSE](./LICENSE).
