# SEC-OPS 2.0 — Security & Compliance Architecture

## 1. Authentication & Session Management
- **Password Hashing:** Passwords are encrypted using `bcrypt` with salt rounds.
- **JWT Authorization:** API access uses OAuth2 Password Bearer workflow issuing signed JWT tokens (`HS256`) with strict expiration windows.
- **Secret Hardening:** Application fails fast at startup if placeholder, short (<32 chars), or default secrets are detected in `.env`.

---

## 2. Network & SSRF Defenses
- **Camera Fleet SSRF Protection:** Input schemas (`src/schemas/cameras.py`) strictly validate IP addresses:
  - Rejects link-local cloud metadata addresses (`169.254.0.0/16`).
  - Rejects multicast addresses (`224.0.0.0/4`).
  - Restricts stream paths to valid RTSP formats.
- **CORS Protection:** Strict origin whitelisting in production (`CORS_ORIGINS`). Rejects wildcard `*` origins in production mode.

---

## 3. Rate Limiting
- **Sliding-Window Limiter (`src/core/rate_limit.py`):** Protects sensitive routes against brute-force and resource-exhaustion attacks.
- Supported backends: Distributed Redis with automatic memory fallback.
- Enforced on:
  - Authentication login & token creation
  - Camera snapshot & manual scan triggers
  - Forensic search & export routes

---

## 4. Audit Logging
- **Immutable Audit Trail:** Sensitive mutations (camera registration, token generation, user creation, manual overrides) are committed to the `audit_logs` table with actor IDs, timestamp, and before/after states.

