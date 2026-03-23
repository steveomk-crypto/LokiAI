# Gumroad Account

- **Application name:** Loki AI
- **Application ID:** `RVEeUAeIEsgqe5CgUKedDxAhcw_WT_CHsT7Ev2Hz3t0`
- **Application secret:** stored in `secrets/gumroad_api.env`
- **Access token:** stored in `secrets/gumroad_api.env`
- **Advanced settings page:** https://gumroad.com/settings/advanced
- **Use cases:** automate product listings, fetch sales data, send fulfillment pings.

## Files to know
- Product copy & deliverables: `docs/gumroad/atlas_pulse_pro_pack.md`
- Pack artifacts: `artifacts/gumroad/atlas_pulse/`

## Next steps
1. Decide whether we need webhooks (Ping endpoint) for automatic fulfillment.
2. If we plan to hit the Gumroad API, wire these credentials into a helper module and keep rate limits in mind.
3. Document pricing/plan details once we finalize them.
