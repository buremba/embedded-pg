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

def test_data_persistence_across_restarts(tmp_path):
    """Test that data persists across server restarts using psycopg2."""
    if not has_docker():
        import pytest
        pytest.skip("Docker not available")
    
    try:
        import psycopg2
    except ImportError:
        import pytest
        pytest.skip("psycopg2 not available")
    
    ns = "pytest_persistence"
    data_dir = tmp_path / "persistence_data"
    data_dir.mkdir()
    port = 55433  # Use different port to avoid conflicts
    
    # Start first server instance
    proc1 = subprocess.Popen([sys.executable, "-m", "esp.cli", "start",
                              "--namespace", ns,
                              "--path", f"file://{data_dir}",
                              "--port", str(port),
                              "--detach"])
    proc1.wait(timeout=300)
    assert proc1.returncode == 0
    assert wait_port("127.0.0.1", port, 120)
    
    # Connect and create table with test data
    conn = psycopg2.connect(
        host="127.0.0.1",
        port=port,
        database="postgres",
        user="postgres",
        password="postgres"
    )
    
    with conn.cursor() as cur:
        # Create test table
        cur.execute("""
            CREATE TABLE test_persistence (
                id SERIAL PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                value INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Insert test data
        test_data = [
            ("Alice", 100),
            ("Bob", 200),
            ("Charlie", 300),
            ("Diana", 400)
        ]
        
        for name, value in test_data:
            cur.execute(
                "INSERT INTO test_persistence (name, value) VALUES (%s, %s)",
                (name, value)
            )
        
        conn.commit()
        
        # Verify data was inserted
        cur.execute("SELECT COUNT(*) FROM test_persistence")
        count = cur.fetchone()[0]
        assert count == 4
        
        # Get the inserted data for later comparison
        cur.execute("SELECT name, value FROM test_persistence ORDER BY id")
        original_data = cur.fetchall()
    
    conn.close()
    
    # Stop the first server
    subprocess.check_call([sys.executable, "-m", "esp.cli", "stop",
                           "--namespace", ns])
    
    # Wait a moment to ensure clean shutdown
    time.sleep(2)
    
    # Start second server instance (should use same data)
    proc2 = subprocess.Popen([sys.executable, "-m", "esp.cli", "start",
                              "--namespace", ns,
                              "--path", f"file://{data_dir}",
                              "--port", str(port),
                              "--detach"])
    proc2.wait(timeout=300)
    assert proc2.returncode == 0
    assert wait_port("127.0.0.1", port, 120)
    
    # Connect to the second server and verify data persistence
    conn2 = psycopg2.connect(
        host="127.0.0.1",
        port=port,
        database="postgres",
        user="postgres",
        password="postgres"
    )
    
    with conn2.cursor() as cur:
        # Check if table exists
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'test_persistence'
            )
        """)
        table_exists = cur.fetchone()[0]
        assert table_exists, "Table should exist after restart"
        
        # Verify data is the same
        cur.execute("SELECT name, value FROM test_persistence ORDER BY id")
        persisted_data = cur.fetchall()
        
        assert len(persisted_data) == 4, "Should have 4 records after restart"
        assert persisted_data == original_data, "Data should be identical after restart"
        
        # Insert additional data to verify write functionality
        cur.execute(
            "INSERT INTO test_persistence (name, value) VALUES (%s, %s)",
            ("Eve", 500)
        )
        conn2.commit()
        
        # Verify new data was inserted
        cur.execute("SELECT COUNT(*) FROM test_persistence")
        final_count = cur.fetchone()[0]
        assert final_count == 5, "Should have 5 records after new insert"
    
    conn2.close()
    
    # Clean up: stop the second server
    subprocess.check_call([sys.executable, "-m", "esp.cli", "stop",
                           "--namespace", ns])
