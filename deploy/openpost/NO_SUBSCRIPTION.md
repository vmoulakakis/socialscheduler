# OpenPost deployment policy

This repository uses **self-hosted OpenPost only** for the zero-subscription publishing path.

- Do not require or link production setup to an OpenPost Hosted plan.
- Do not add OpenPost billing credentials.
- Do not switch `OPENPOST_EDITION` from `selfhost` to `cloud`.
- Do not commit provider client secrets or OpenPost API tokens.
- Keep OpenPost execution downstream of SocialMarket approval/quality gates.

The allowed cost boundary is infrastructure/provider cost chosen by the operator; OpenPost software subscription must remain zero for this deployment path.
