# Security Policy

## Supported Versions

The following versions of Calculus Animator are currently supported with security updates:

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | :white_check_mark: |
| < 1.0   | :x:                |

## Reporting a Vulnerability

We take security seriously. If you discover a security vulnerability, please follow these steps:

### Please DO NOT

- **Do not** open a public issue for security vulnerabilities
- **Do not** discuss the vulnerability in public forums or chat
- **Do not** submit a pull request with the fix (until coordinated)

### Please DO

1. **Report privately** via GitHub Security Advisories:
   - Go to: https://github.com/Rsan0948/calculus_animator/security/advisories/new
   - Or email: rubmatsan2001@gmail.com

2. **Include details**:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)
   - Your contact information for follow-up

3. **Allow time for response**:
   - We will acknowledge receipt within 48 hours
   - We aim to provide an initial assessment within 5 business days
   - We will work with you to coordinate disclosure timeline

## Response Process

1. **Acknowledgment**: We confirm receipt of your report
2. **Investigation**: We assess the vulnerability and determine impact
3. **Fix Development**: We develop and test a fix
4. **Disclosure**: We coordinate public disclosure with you
5. **Release**: We release the fix and publish a security advisory

## Security Best Practices

When using Calculus Animator:

### AI Tutor

- **API Keys**: Store API keys in environment variables, never commit to version control
- **Student Data**: The AI tutor may process student work; ensure compliance with educational privacy laws (FERPA, GDPR)
- **Screenshot Privacy**: Screenshots sent to AI providers should not contain personally identifiable information

### Local Development

- **Virtual Environment**: Always use a virtual environment to isolate dependencies
- **Dependency Scanning**: Run `pip-audit` periodically to check for vulnerable dependencies

### Distribution

- **Packaged Builds**: Download releases only from official GitHub releases
- **Checksum Verification**: Verify SHA256 checksums when available

## Known Security Considerations

### Subprocess Workers

The application uses subprocess workers for rendering isolation. While this provides fault tolerance, ensure:
- Worker processes cannot access files outside the project directory
- Input validation prevents injection attacks via LaTeX expressions

### AI Provider Integration

When using external AI providers:
- Data is sent to third-party services (DeepSeek, Google, OpenAI, etc.)
- Review their privacy policies for educational data handling
- Consider local-only options (Ollama) for sensitive environments

## Security Updates

Security updates will be:
- Released as patch versions (e.g., 1.0.1)
- Documented in the [CHANGELOG.md](CHANGELOG.md)
- Announced via GitHub Security Advisories

## Acknowledgments

We thank the following individuals for responsible disclosure:

- *No security researchers acknowledged yet*

## Contact

For security concerns: rubmatsan2001@gmail.com
For general questions: Open a [Discussion](https://github.com/Rsan0948/calculus_animator/discussions)
