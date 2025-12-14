# Security Policy

## Supported Versions

We release patches for security vulnerabilities for the following versions:

| Version | Supported          |
| ------- | ------------------ |
| Latest  | :white_check_mark: |
| < Latest| :x:                |

We recommend always using the latest version of the integration.

## Reporting a Vulnerability

We take the security of the Shell Recharge integration seriously. If you believe you have found a security vulnerability, please report it to us as described below.

### Please do NOT:

- Open a public GitHub issue for security vulnerabilities
- Disclose the vulnerability publicly before it has been addressed

### Please DO:

1. **Report privately via GitHub Security Advisories:**
   - Go to the [Security tab](https://github.com/cyberjunky/home-assistant-shell_recharge_ev/security/advisories) of this repository
   - Click "Report a vulnerability"
   - Provide a detailed description of the vulnerability

2. **Or email directly:**
   - Contact the repository owner through their GitHub profile

### What to include in your report:

- Type of vulnerability
- Full paths of source file(s) related to the vulnerability
- Location of the affected source code (tag/branch/commit or direct URL)
- Any special configuration required to reproduce the issue
- Step-by-step instructions to reproduce the issue
- Proof-of-concept or exploit code (if possible)
- Impact of the issue, including how an attacker might exploit it

### What to expect:

- **Acknowledgment:** We'll acknowledge receipt of your vulnerability report within 48 hours
- **Updates:** We'll provide regular updates on the progress of addressing the vulnerability
- **Timeline:** We aim to address critical vulnerabilities within 30 days
- **Credit:** With your permission, we'll credit you in the security advisory when the fix is published

## Security Considerations

### Credentials Storage

This integration stores Shell Recharge account credentials in Home Assistant's secure credential storage. Please ensure:

- Your Home Assistant instance is properly secured
- You use strong, unique passwords for your Shell Recharge account
- You keep your Home Assistant installation up to date

### API Access

The integration communicates with Shell Recharge APIs. Please be aware:

- API credentials are transmitted over HTTPS
- No credentials are logged or stored in plain text
- Session tokens are managed securely

### Best Practices

When using this integration:

1. Only install it from official sources (HACS or GitHub releases)
2. Review the code before installation if you have security concerns
3. Keep the integration updated to receive security patches
4. Monitor your Shell Recharge account for any suspicious activity
5. Use Home Assistant's authentication and access control features

## Disclosure Policy

When we receive a security bug report, we will:

1. Confirm the problem and determine affected versions
2. Audit code to find similar problems
3. Prepare fixes for all supported versions
4. Release new versions as soon as possible
5. Publish a security advisory on GitHub

Thank you for helping keep this integration and its users safe!
