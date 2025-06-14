
import shutil, subprocess, sys, time, socket, os, pathlib

def has_docker():
    return shutil.which("docker") is not None

def wait_port(host, port, timeout=30):
    import socket, time
    t0 = time.time()
    while time.time() - t0 < timeout:
        with socket.socket() as s:
            if s.connect_ex((host, port)) == 0:
                return True
        time.sleep(1)
    return False

def test_help():
    proc = subprocess.run([sys.executable, "-m", "esp.cli", "--help"],
                          capture_output=True, text=True)
    assert proc.returncode == 0
    assert "start" in proc.stdout

def test_start_stop_cycle(tmp_path):
    if not has_docker():
        import pytest
        pytest.skip("Docker not available")
    ns = "pytest"
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    proc = subprocess.Popen([sys.executable, "-m", "esp.cli", "start",
                             "--namespace", ns,
                             "--path", f"file://{data_dir}",
                             "--detach"])
    proc.wait(timeout=300)
    assert proc.returncode == 0

    assert wait_port("127.0.0.1", 55432, 120)

    # stop
    subprocess.check_call([sys.executable, "-m", "esp.cli", "stop",
                           "--namespace", ns])
