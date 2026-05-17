# Docker Deployment

```bash
cp .env.example .env
# edit .env

docker compose up -d --build

docker compose ps
docker compose logs -f
```

## Production notes

- Use read/write trading keys only; never enable withdrawal permission.
- Start with minimal size and verify behavior.
- Rotate logs or route logs to a host volume.
- Consider adding health checks and restart policies.
