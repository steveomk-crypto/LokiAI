# Secrets Manifest

This directory is local-only and ignored by Git.
Do not commit secret values.

## Expected files
- `birdeye_api_credentials.env`
- `coinbase_api.env`
- `gmail_credentials.env`
- `google_oauth_client.env`
- `gumroad_api.env`
- `helius_api_credentials.env`
- `solana_wallets.json`
- `x_api_credentials.env`

## Notes
- The presence of a filename matters; the values stay local.
- Reinstall recovery should restore this directory before automation is resumed.
- If a key rotates, update the local file and note the rotation in docs or memory without exposing the value.
