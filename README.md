
# embedded-serverless-postgresql (ESP)

Self‑contained CLI that boots a **Neon‑based PostgreSQL cluster** inside Docker in seconds.
No Git, no local Rust build — just Docker.

```bash
# install with uv
uv pip install embedded-serverless-postgresql

# local‑disk WAL/layer storage
esp start --path file:///tmp/esp-data

# S3 / MinIO (in‑cluster)
esp start --path s3://neon --with-minio --endpoint http://minio:9000           --access-key minio --secret-key password

# stop the stack (auto‑stops when you Ctrl‑C if you omit --detach)
esp stop
```

---

## Why ESP instead of running Postgres directly?

* **Branching & time‑travel** thanks to Neon.
* No host‑level dependencies: one Docker pull.
* Multiple isolated stacks via `--namespace`.

## Requirements

* Docker **24+** with the *compose* plugin.
* Python **3.9+** (for the CLI itself).

If `esp` doesn’t find `docker` on PATH it aborts with an explicit message.

---

## Development

```bash
git clone <your-fork> esp
cd esp
uv pip install -e '.[dev]'
pytest -v
```

---

### Roadmap

* Kubernetes Helm chart generator
* Optional TLS termination
* Automated nightly upgrade test
