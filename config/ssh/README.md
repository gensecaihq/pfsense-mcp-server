# SSH Configuration Directory

Place your SSH private key files here for SSH-based pfSense connections.

## Setup Instructions

1. Generate an SSH key pair (if you don't have one):
```bash
ssh-keygen -t rsa -b 4096 -f id_rsa -C "pfsense-mcp"
```

2. Copy the public key to your pfSense server:
```bash
ssh-copy-id -i id_rsa.pub admin@your-pfsense-host
```

3. Set proper permissions:
```bash
chmod 600 id_rsa
chmod 644 id_rsa.pub
```

## Security Notes

- Never commit private keys to version control
- Use strong passphrases for production keys
- Rotate keys periodically
- Consider using SSH certificates for enhanced security

## File Naming

- `id_rsa` - Default private key
- `id_rsa.pub` - Default public key
- Custom keys can be named differently and specified in environment variables