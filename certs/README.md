# certs/

This directory is intentionally empty in version control. TLS certificates and
private keys MUST NOT be committed to the repository.

For local development with the docker-compose nginx service, generate a
self-signed pair:

```bash
./make-dev-certs.sh
```

For production deployment, use Let's Encrypt (`certbot`) or your CA of choice
and mount the resulting `fullchain.pem` / `privkey.pem` into the nginx
container at `/etc/nginx/certs/`.
