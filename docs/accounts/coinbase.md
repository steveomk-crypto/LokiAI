# Coinbase API Credentials

- **API key name:** `organizations/938ed93c-4db1-4276-b70d-535316eefe56/apiKeys/f91ef35a-34d7-45bc-8f89-77a8ee1837ee`
- **Private key location:** `secrets/coinbase_api.env`
- **Status:** stored only; not wired into any automation yet

## Notes
- This appears to be a Coinbase developer/exchange-style API credential using an EC private key.
- Before using it in code, confirm the intended target (Coinbase Advanced Trade, CDP, or another Coinbase surface) and the required signing flow.
- Do not commit this key or paste it into public logs.
