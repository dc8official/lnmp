# Security Policy

## Supported Versions

| Version   | Supported          | Security Notes |
| --------- | ------------------ | -------------- |
| v3.3.0    | :white_check_mark: | Active production standard with Flow Exporter & Interface Telemetry |
| v3.1.35s  | :white_check_mark: | Supported long-term maintenance track (v3.1.35s) |
| <= v3.2.0 | :x:                | Legacy release — upgrade to v3.3.0 recommended |
| < v3.1    | :x:                | End of Life (EOL) |

## Reporting a Vulnerability

The LNMP engineering and security team takes the security of our network monitoring platform seriously. If you discover a vulnerability, we appreciate your responsible disclosure.

### How to Report

- **Email:** Send details to `dagera07@gmail.com`
- **GitHub:** Use [Private Vulnerability Reporting](https://github.com/dc8official/noop/security/advisories/new) on the repository.

Please include:
1. Description of the vulnerability and its potential impact.
2. Step-by-step instructions or proof-of-concept to reproduce the issue.
3. Affected components and environment details.

Please **do not** report security vulnerabilities through public GitHub issues.

### Response Timeline

- **Initial Response:** Within 24 hours
- **Triage & Status Update:** Within 48 hours
- **Remediation & Patch Target:** Within 72 hours for critical/high vulnerabilities

## Security Architecture & Threat Model

For the full technical security specification, threat models, cryptographic algorithms, perimeter port policies, and Linux capability isolation, see the comprehensive [LNMP Security Model & Defense Specification](docs/security.md).
