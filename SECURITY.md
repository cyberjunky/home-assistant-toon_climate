# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in this integration, please report it privately by creating a [security advisory](https://github.com/cyberjunky/home-assistant-toon_climate/security/advisories) on GitHub.

**Please do NOT open a public issue for security vulnerabilities.** This allows us to address the issue before it becomes public knowledge.

## Security Considerations

### Network Communication

This integration communicates with rooted Toon thermostats over your local network (HTTP):

- Ensure your Toon device is only accessible from trusted networks
- Keep your Home Assistant instance on a secure network
- Consider using firewall rules to restrict access to your Toon device

### Credential Storage

Toon device connection details (IP, port) are stored in Home Assistant's configuration:

- Keep your `configuration.yaml` and Home Assistant configuration secure
- Do not share your Home Assistant backups without sanitizing sensitive data
- Rooted Toon devices may have default or weak passwords—change them if applicable

### Best Practices

1. **Keep Home Assistant updated** - Security patches are released regularly
2. **Install from official sources** - Use HACS or official GitHub releases
3. **Review the code** - As an open-source project, you can audit the code before use
4. **Secure your network** - Restrict access to your Home Assistant instance
5. **Use strong authentication** - Enable Home Assistant's user authentication

## Disclosure Timeline

When a vulnerability is confirmed:

1. We will assess the severity and impact
2. A fix will be prepared for the latest version
3. A new release will be published
4. A security advisory will be published on GitHub (with credit to the reporter if desired)

Thank you for helping keep this project secure!
