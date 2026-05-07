# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 0.x.x   | ✅ (development) |

## Reporting a Vulnerability

If you discover a security vulnerability in Anukriti Swarm, please report it responsibly.

**Do NOT open a public issue for security vulnerabilities.**

### How to Report

1. Email the maintainers with a description of the vulnerability
2. Include steps to reproduce, if possible
3. Allow reasonable time for a fix before public disclosure

### What to Expect

- Acknowledgment within 48 hours
- Status update within 7 days
- Fix or mitigation plan within 30 days for confirmed vulnerabilities

## Security Considerations

### Genomic Data

- This system processes sensitive genomic information
- No patient-identifiable data should be used in development or testing
- Use synthetic or publicly available reference datasets only
- All genomic data handling must comply with applicable data protection regulations

### API Keys and Secrets

- Never commit API keys, tokens, or credentials to the repository
- Use `.env` files (excluded via `.gitignore`) for local secrets
- Rotate any key that is accidentally exposed

### LLM Security

- Prompt injection risks are acknowledged and mitigated through input validation
- Agent outputs are never trusted as authoritative medical information
- All generative outputs are labeled as research-only

## Scope

This policy covers the Anukriti Swarm codebase and its direct dependencies. Third-party services (LLM providers, vector databases) are governed by their own security policies.
