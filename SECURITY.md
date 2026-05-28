# Security policy

We take security reports seriously. This document tells you how to report a
problem, what to expect, and what is and isn't currently in our threat model.

## Reporting a vulnerability

**Please email <security@vidyuthlabs.co.in>** with the details. Use
"RĀMAN Studio security" in the subject. We will acknowledge within 5 working
days. Please do not open public GitHub issues for security problems.

If you can, include:

- A short description of the issue.
- Steps to reproduce (or a proof-of-concept).
- The version / commit you tested against.
- Any suggested mitigation.

We do not currently run a paid bug-bounty programme. We will credit reporters
in the changelog with their permission.

## Scope

In scope:

- The desktop application (Electron + Python sidecar).
- The C++ physics engine (`engine_core/`).
- The local AI agent (`src/ai_engine/`).
- The build and packaging pipeline (`scripts/`, `Dockerfile`, `package.json`).
- The license server, once it is deployed.

Out of scope:

- Third-party dependencies — please report to those projects directly. We will
  patch and republish once an upstream fix exists.
- The included KiCad hardware project under `EIS-RV/`. That tree is separate.
- Issues that require an attacker to already have full local administrative
  access to the user's machine.

## Current threat-model honesty

This is a young codebase. Several pieces of security infrastructure are still
being built. To set expectations:

| Area | Status today |
|---|---|
| Licensing | Trial-mode for all users. Real Ed25519-signed, hardware-bound licensing is in development. |
| Project files | Stored as plaintext JSON. Encryption-at-rest is in development. |
| Auth on local FastAPI sidecar | Bound to `127.0.0.1` by default; no inter-process auth yet. |
| Auto-updater | Disabled by default. No code-signing verification configured. Do not enable against an untrusted release channel. |
| C++ engine bindings (pybind11) | Memory-safe by virtue of Eigen + std containers. No raw pointer ownership. |
| Secrets | The repository previously committed an NVIDIA API key and TLS private keys. Those have been removed from the working tree, but **may still exist in git history** — see "Historical leaks" below. |
| Crypto in transit | The desktop build uses local IPC only. Any cloud calls (NVIDIA NIM, license server) use HTTPS. |
| Crypto at rest | Not yet implemented for projects. The `cryptography` library (Fernet, AES-128-CBC + HMAC-SHA256) is wired into `src/backend/projects/project_manager.py` but is not currently used by the production project routes. |

If you read marketing copy for this product (in older docs or external sites)
that claims things like "10/10 security", "AES-256 military-grade",
"21 CFR Part 11 compliant", or "hardware-bound licensing": those claims are
not currently true. They were aspirational. We removed them when we found
them. If you see them on any active surface, please tell us.

## Historical leaks (action required by the maintainer)

The following secrets were previously committed and **may still be present in
the git history**:

1. An NVIDIA API key (`nvapi-zZ9R...`).
2. Two TLS private key pairs (self-signed, `CN=localhost`).

These have been removed from the working tree. The maintainer must:

- Revoke the NVIDIA key in the NVIDIA console.
- Treat the self-signed certificates as compromised and never reuse them.
- Decide whether to rewrite git history (`git filter-repo`) to expunge the
  values from old commits. This is a one-way operation that requires
  coordinating with anyone who has cloned the repo.

## Coordinated disclosure

We aim to ship a fix within 30 days for a high-severity report and within 90
days for a medium-severity one. We will tell the reporter when the fix lands
and ask before publishing details.

## Updates to this document

This document will be updated as the threat model changes (real licensing,
encrypted projects, signed releases). The current commit is the source of
truth; older versions in git history may reflect earlier states.
