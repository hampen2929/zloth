# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |

## Reporting a Vulnerability

We take the security of dursor seriously. If you believe you have found a security vulnerability, please report it to us as described below.

### How to Report

**Please do not report security vulnerabilities through public GitHub issues.**

Instead, please report them via email to:
- **Email**: [Create a private security advisory](https://github.com/hampen2929/dursor/security/advisories/new)

You can also use GitHub's private vulnerability reporting feature:
1. Go to the [Security tab](https://github.com/hampen2929/dursor/security) of this repository
2. Click "Report a vulnerability"
3. Fill in the details

### What to Include

Please include the following information in your report:

- Type of vulnerability (e.g., SQL injection, XSS, authentication bypass)
- Full paths of source file(s) related to the vulnerability
- Location of the affected source code (tag/branch/commit or direct URL)
- Step-by-step instructions to reproduce the issue
- Proof-of-concept or exploit code (if possible)
- Impact of the issue, including how an attacker might exploit it

### What to Expect

1. **Acknowledgment**: You will receive an acknowledgment of your report within 48 hours
2. **Investigation**: We will investigate and validate the vulnerability
3. **Fix Development**: We will develop a fix for the vulnerability
4. **Coordinated Disclosure**: We will work with you on the timing of public disclosure
5. **Credit**: We will credit you in the security advisory (unless you prefer anonymity)

## Security Best Practices for Users

### API Key Storage
- API keys are encrypted at rest using Fernet (AES-128)
- Set a strong `DURSOR_ENCRYPTION_KEY` environment variable
- Never commit `.env` files to version control

### Self-Hosting
- Keep your dursor installation updated
- Use HTTPS in production
- Restrict network access to the API server
- Regularly rotate your encryption keys

### GitHub Integration
- Use GitHub App authentication instead of Personal Access Tokens when possible
- Grant minimal required permissions to the GitHub App
- Regularly audit GitHub App installations

## Known Security Considerations

### v0.1 Limitations
- **No authentication**: The API server does not have built-in authentication. Use a reverse proxy with authentication in production.
- **Single-user design**: The current version is designed for single-user use. Multi-user support with proper access control is planned for v0.3.

### Forbidden Paths
The following paths are blocked by default to prevent accidental exposure:
- `.git/`
- `.env`
- `*.secret`
- `*.key`
- `credentials.*`

## Security Updates

Security updates will be released as patch versions (e.g., 0.1.1) and announced via:
- GitHub Security Advisories
- Release notes

We recommend subscribing to repository notifications to stay informed about security updates.
