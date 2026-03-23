# Atlas Loop Gmail Account

- **Address:** `lokiclips12@gmail.com`
- **Purpose:** External comms for Atlas Pulse packs (receiving inquiries, optional distribution of briefs, backup contact channel for Gumroad/Substack buyers).
- **Login:** Credentials stored in `secrets/gmail_credentials.env` (plain exports for now). Consider enabling 2FA + an app password if we start sending mail programmatically.
- **Next steps:**
  1. Decide whether the trading stack should send briefs directly via SMTP. If yes, add OAuth/app-password support in the automation scripts.
  2. Capture any signature / canned response text once you set it in the Gmail UI.
  3. Mirror key emails into the repo (redacted) when they contain process decisions we need to remember.

## OAuth Client
- **Client ID:** 571905616361-jknlfo4ga6lprl36gqnlj6hjfo3309jk.apps.googleusercontent.com
- **Secret:** stored in `secrets/google_oauth_client.env`
- **Created:** 2026-03-23 10:43 PDT (status: enabled)
- Download JSON? Not yet; if you generate one, drop it under `secrets/google_oauth_client.json`.
