
import os, re, shutil, signal, socket, subprocess, sys, textwrap, time
from pathlib import Path

import click, yaml
from importlib import resources

PACKAGE_DATA = resources.files(__package__) / "data"

def which(cmd: str) -> str | None:
    from shutil import which as _w
    return _w(cmd)

def die(msg: str):
    click.echo(click.style(f"ERROR: {msg}", fg="red"), err=True)
    sys.exit(1)

# ───────────────────────── Helpers ──────────────────────────────────────────
def sh(cmd, **kw):
    subprocess.run(cmd, check=True, **kw)

def wait_port(host: str, port: int, timeout=60):
    t0 = time.time()
    while time.time() - t0 < timeout:
        with socket.socket() as s:
            if s.connect_ex((host, port)) == 0:
                return True
        time.sleep(1)
    return False

def comp_paths(ns: str):
    root = Path.home() / ".esp" / ns
    return {
        "root": root,
        "override": root / "docker-compose.override.yml",
        "pages_toml": root / "pageserver.toml"
    }

def remote_storage_block(path: str, region: str, endpoint: str | None):
    if path.startswith("file://"):
        host_dir = Path(path[7:]).expanduser().resolve()
        return "[remote_storage]\nlocal_path = '/remote_storage'\n", {}, [f"{host_dir}:/remote_storage"]
    m = re.match(r"s3://([^/]+)(/.*)?", path)
    if m:
        bucket, prefix = m.group(1), (m.group(2) or "")
        block = textwrap.dedent(f"""
            [remote_storage]
            bucket_name   = '{bucket}'
            bucket_region = '{region}'
            prefix_in_bucket = '{prefix}'
        """)
        extra_env = {}
        if endpoint:
            block += f"endpoint = '{endpoint}'\n"
            extra_env["NEON_S3_ENDPOINT"] = endpoint
        return block, extra_env, []
    die("path must start with file:// or s3://")

MINIO_YAML = """
  minio:
    image: quay.io/minio/minio:latest
    restart: always
    ports: ["9000:9000", "9001:9001"]
    environment:
      - MINIO_ROOT_USER=minio
      - MINIO_ROOT_PASSWORD=password
    command: server /data --address :9000 --console-address ":9001"

  minio_create_buckets:
    image: minio/mc
    environment:
      - MINIO_ROOT_USER=minio
      - MINIO_ROOT_PASSWORD=password
    entrypoint: ["/bin/sh", "-c"]
    command: |
      until (mc alias set minio http://minio:9000 $MINIO_ROOT_USER $MINIO_ROOT_PASSWORD) do
        echo 'Waiting for MinIO…' && sleep 1;
      done;
      mc mb minio/neon --region=us-east-1; exit 0;
    depends_on: [minio]
"""

# ───────────────────────── CLI ──────────────────────────────────────────────
@click.group()
def cli():
    """Embedded Serverless PostgreSQL (Neon-in-Docker)."""
    if which("docker") is None:
        die("Docker binary not found on PATH. Install Docker and try again.")

@cli.command()
@click.option("-n", "--namespace", default="main", show_default=True)
@click.option("--path", required=True, help="file://… or s3://…")
@click.option("--region", default="us-east-1", show_default=True)
@click.option("--endpoint")
@click.option("--access-key")
@click.option("--secret-key")
@click.option("--port", default=55432, show_default=True, type=int)
@click.option("--with-minio", is_flag=True, help="Embed MinIO in the stack")
@click.option("--detach", is_flag=True, help="Don't block; leave containers running")
def start(namespace, path, region, endpoint, access_key, secret_key,
          port, with_minio, detach):
    """Start a Neon cluster."""

    paths = comp_paths(namespace)
    paths["root"].mkdir(parents=True, exist_ok=True)

    base_compose = PACKAGE_DATA / "base-compose.yml"

    toml, extra_env, extra_vols = remote_storage_block(path, region, endpoint)
    paths["pages_toml"].write_text(toml)

    override = {
        "services": {
            "pageserver": {
                "volumes": [f"{paths['pages_toml']}:/home/neon/.neon/pageserver.toml:ro"] + extra_vols,
                "environment": {**({"AWS_ACCESS_KEY_ID": access_key, "AWS_SECRET_ACCESS_KEY": secret_key}
                                   if access_key and secret_key else {}),
                                **extra_env}
            },
            "compute": {"ports": [f"{port}:55432"]}
        }
    }
    if with_minio:
        override["services"].update(yaml.safe_load(MINIO_YAML))

    paths["override"].write_text(yaml.safe_dump(override, sort_keys=False))

    compose_base = ["docker", "compose", "-p", namespace,
                    "-f", base_compose, "-f", paths["override"]]

    try:
        sh(compose_base + ["pull"])
        sh(compose_base + ["up", "-d"])
    except subprocess.CalledProcessError as e:
        die(f"docker compose failed ({e.returncode})")

    if not wait_port("127.0.0.1", port, 120):
        die("PostgreSQL did not start in time. Check container logs.")

    click.echo(click.style(f"✓ Neon ({namespace}) is ready on port {port}", fg="green"))
    if detach:
        return
    click.echo("Press Ctrl-C to stop…")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        stop_callback(namespace)

def stop_callback(namespace):
    base_compose = PACKAGE_DATA / "base-compose.yml"
    paths = comp_paths(namespace)
    if not paths["override"].exists():
        click.echo("Stack not running.")
        return
    sh(["docker", "compose", "-p", namespace,
        "-f", base_compose, "-f", paths["override"], "down"])

@cli.command()
@click.option("-n", "--namespace", default="main", show_default=True)
def stop(namespace):
    """Stop containers, keep data."""
    stop_callback(namespace)

@cli.command()
@click.option("-n", "--namespace", default="main", show_default=True)
def destroy(namespace):
    """Stop containers & delete generated files."""
    stop_callback(namespace)
    shutil.rmtree(comp_paths(namespace)["root"], ignore_errors=True)
    click.echo(f"Namespace '{namespace}' removed.")
