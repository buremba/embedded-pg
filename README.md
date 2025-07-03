# py-embedded-pg

Self‑contained CLI that boots a **Neon‑based PostgreSQL cluster** inside Docker in seconds.
No Git, no local Rust build — just Docker.

```bash
# install with uv
uv pip install py-embedded-pg

# local‑disk WAL/layer storage
py-embedded-pg start --path file:///tmp/esp-data

# S3 / MinIO (in‑cluster)
py-embedded-pg start --path s3://neon --with-minio --endpoint http://minio:9000 --access-key minio --secret-key password

# stop the stack (auto‑stops when you Ctrl‑C if you omit --detach)
py-embedded-pg stop
```

---

## How it works

py-embedded-pg leverages **Neon's architecture** to provide a serverless PostgreSQL experience with advanced features:

### Neon Architecture
- **Compute-Storage Separation**: PostgreSQL compute nodes are separated from storage layers
- **Copy-on-Write Storage**: Efficient branching and point-in-time recovery using a custom storage engine
- **Serverless Scaling**: Compute nodes can be started/stopped independently without data loss

### Supported Storage Schemes

#### File-based Storage (`file://`)
- **Local Development**: Store WAL segments and page files on local filesystem
- **Fast Setup**: No external dependencies, perfect for testing and development
- **Example**: `file:///tmp/esp-data` or `file://./project-data`

#### S3-compatible Storage (`s3://`)
- **Production Ready**: Use AWS S3, MinIO, or any S3-compatible service
- **Scalable**: Handle large datasets with cloud storage
- **Configurable**: Custom endpoints, regions, and credentials
- **Examples**: 
  - AWS S3: `s3://my-bucket/neon-data`
  - MinIO: `s3://neon --with-minio --endpoint http://minio:9000`
  - Custom S3: `s3://bucket --endpoint https://custom-s3.example.com`

### Key Benefits
- **Branching**: Create database branches like Git branches
- **Time Travel**: Access historical data states
- **Instant Snapshots**: Zero-downtime backups
- **Resource Efficiency**: Only pay for compute when active

---

## Why py-embedded-pg instead of running Postgres directly?

* **Branching & time‑travel** thanks to Neon.
* No host‑level dependencies: one Docker pull.
* Multiple isolated stacks via `--namespace`.

## Requirements

* Docker **24+** with the *compose* plugin.
* Python **3.9+** (for the CLI itself).

If `py-embedded-pg` doesn't find `docker` on PATH it aborts with an explicit message.

---

## Development

```bash
git clone <your-fork> py-embedded-pg
cd py-embedded-pg
uv pip install -e '.[dev]'
pytest -v
```

---

### Roadmap

* Kubernetes Helm chart generator
* Optional TLS termination
* Automated nightly upgrade test
