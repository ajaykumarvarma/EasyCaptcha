# EasyCaptcha

**Self-hosted, open-source captcha service — no third-party vendor required.**

> **Live demo →** [your-username.github.io/easycaptcha](https://your-username.github.io/easycaptcha)  
> Try both variants live (CanvasCaptcha works instantly; ServerCaptcha connects to your own instance).

Two ready-to-use variants:

| Variant | How it works | Best for |
|---------|-------------|----------|
| **ServerCaptcha** | Backend generates a distorted PNG image; answer verified server-side in MongoDB | Sign up, sign in, password reset — any high-risk form |
| **CanvasCaptcha** | Canvas drawn entirely in the browser; no backend needed | Contact forms, newsletter subscribe, low-risk forms |

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
│   ├── .env.example         — Copy to .env and fill in values
│   ├── Dockerfile
│   ├── test_captcha.py      — Automated tests (26 tests, no server needed)
│   └── conftest.py          — pytest configuration
├── frontend/
│   ├── ServerCaptcha.jsx    — React component (server-side variant)
│   └── CanvasCaptcha.jsx    — React component (canvas / client-side variant)
├── docker/
│   └── docker-compose.yml   — One-command local setup (service + MongoDB)
├── docs/
│   └── index.html           — GitHub Pages live demo (both variants, works in-browser)
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
https://your-username.github.io/easycaptcha
```

Replace `your-username` with your actual GitHub username.

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
git clone https://github.com/your-username/easycaptcha.git
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
| `RATE_LIMIT_PER_MIN` | No | `15` | Max `/captcha` calls per IP per minute |
| `CAPTCHA_LENGTH` | No | `5` | Number of characters per challenge |
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
```

> **Tip — changing `CAPTCHA_LENGTH`**: The API response always includes
> `captcha_length` as a field, so the `ServerCaptcha` React component adapts
> automatically without any prop changes.  For `CanvasCaptcha` pass the
> `length` prop (e.g. `<CanvasCaptcha length={6} />`).

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
  "token_id":       "550e8400-e29b-41d4-a716-446655440000",
  "image_b64":      "<base64-encoded PNG>",
  "captcha_length": 5
}
```

Render the image:

```html
<img src="data:image/png;base64,PASTE_image_b64_HERE" alt="Security code" />
```

The `captcha_length` field tells the frontend exactly how many characters to
expect.  The `ServerCaptcha` React component reads this automatically; in
vanilla JS, set `input.maxLength = data.captcha_length`.

**Error — 429** Rate limit exceeded.

---

### `POST /captcha/verify` — Verify an answer

**Headers**

```
X-API-Key: <your API_SECRET_KEY>
Content-Type: application/json
```

**Body**

```json
{ "token_id": "...", "answer": "AB3K9" }
```

**Response — 200**

```json
{ "valid": true }
```

Returns `valid: false` for: wrong answer, expired token, already-used token,
unknown token ID.  Details intentionally withheld to prevent enumeration.

**Error — 401** Missing or wrong `X-API-Key`.

---

### `GET /stats` — Token statistics

Requires the same `X-API-Key` header.

**Response — 200**

```json
{
  "tokens_in_db":    42,
  "active_unused":   8,
  "verified":        34,
  "service_version": "1.0.0"
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
{ "status": "ok", "version": "1.0.0", "service": "EasyCaptcha" }
```

No authentication needed.  Use for load balancer health probes and uptime monitoring.

---

## Running the tests

The test suite covers image generation, character set correctness, and rate limiting logic — all without needing a running server or MongoDB.

```bash
cd backend

# Install Python dependencies (if not already done)
pip install -r requirements.txt

# Install test-only extras (not in requirements.txt)
pip install pytest httpx

# Run all unit tests (21 tests, ~0.5 s)
MONGODB_URL=mongodb://localhost:27017 API_SECRET_KEY=test \
  pytest test_captcha.py -v
```

Expected output:

```
test_captcha.py::TestImageGeneration::test_returns_nonempty_string PASSED
test_captcha.py::TestImageGeneration::test_output_is_valid_base64  PASSED
test_captcha.py::TestImageGeneration::test_output_is_valid_png     PASSED
test_captcha.py::TestImageGeneration::test_different_codes_...     PASSED
test_captcha.py::TestImageGeneration::test_same_code_produces_...  PASSED
test_captcha.py::TestImageGeneration::test_various_lengths         PASSED
test_captcha.py::TestImageGeneration::test_single_character        PASSED
test_captcha.py::TestCharacterSet::test_excludes_ambiguous_chars   PASSED
test_captcha.py::TestCharacterSet::test_contains_expected_chars    PASSED
test_captcha.py::TestCharacterSet::test_all_uppercase_or_digit     PASSED
test_captcha.py::TestCharacterSet::test_no_duplicates              PASSED
test_captcha.py::TestCharacterSet::test_minimum_pool_size          PASSED
test_captcha.py::TestRateLimiter::test_allows_requests_under_limit PASSED
test_captcha.py::TestRateLimiter::test_blocks_requests_over_limit  PASSED
test_captcha.py::TestRateLimiter::test_different_ips_are_independent PASSED
test_captcha.py::TestRateLimiter::test_window_resets_after_60_secs PASSED
test_captcha.py::TestRateLimiter::test_allows_new_requests_after...PASSED
test_captcha.py::TestFontDetection::test_returns_string_or_none    PASSED
test_captcha.py::TestFontDetection::test_path_exists_if_found      PASSED
test_captcha.py::TestConfig::test_captcha_length_is_positive       PASSED
test_captcha.py::TestConfig::test_rate_limit_is_positive           PASSED
test_captcha.py::TestIntegration::test_health                      SKIPPED
test_captcha.py::TestIntegration::test_generate_and_verify         SKIPPED
test_captcha.py::TestIntegration::test_verify_missing_api_key      SKIPPED
test_captcha.py::TestIntegration::test_stats_requires_api_key      SKIPPED
test_captcha.py::TestIntegration::test_stats_with_valid_key        SKIPPED

21 passed, 5 skipped
```

### Integration tests (requires running service)

```bash
# First start the service (Docker or manual)
docker compose -f ../docker/docker-compose.yml up -d

# Then run with the --integration flag
MONGODB_URL=mongodb://localhost:27017 API_SECRET_KEY=your-secret \
  pytest test_captcha.py -v --integration
```

---

## Security notes

### Built-in protections

| Protection | Detail |
|-----------|--------|
| Code never sent to browser | Only the PNG image is returned.  The answer is stored in MongoDB only. |
| Single-use tokens | Marked used immediately after first correct verification — replay is impossible. |
| TTL expiry | MongoDB TTL index auto-deletes tokens after `TOKEN_TTL_MINUTES` (default 5). |
| Per-IP rate limiting | Sliding 60-second window.  Configurable via `RATE_LIMIT_PER_MIN`. |
| Security headers | `X-Content-Type-Options`, `X-Frame-Options`, `Cache-Control: no-store` on every response. |
| API key guard | `/captcha/verify` and `/stats` require `X-API-Key` — only your backend can call them. |
| Constant-time comparison | `secrets.compare_digest` prevents timing attacks on the API key check. |

### Limitations

| Concern | Recommendation |
|---------|---------------|
| Advanced OCR/ML | Combine with login attempt rate limiting (lock after N failures per IP/account). |
| CanvasCaptcha | Client-side only — do not use for high-value flows like login or payment. |
| In-memory rate limiter | Resets on restart; not shared across multiple instances. Swap to Redis for multi-instance deployments. |
| HTTPS | Always serve EasyCaptcha over HTTPS in production. |

### Production checklist

- [ ] `API_SECRET_KEY` is a strong random value (32+ hex chars)
- [ ] `ALLOWED_ORIGINS` is set to your exact frontend domain (not `*`)
- [ ] Service is behind a reverse proxy (nginx / Caddy) with TLS
- [ ] `TOKEN_TTL_MINUTES` is 5 or lower
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
