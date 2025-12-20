import pytest
import httpx
import threading
import time
import os
import signal
import subprocess
import sys
import base64
import json
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import List, Tuple

# Configuration
WORKFLOW_PORT = 4501
WORKFLOW_ENDPOINT = f"http://127.0.0.1:{WORKFLOW_PORT}"
CALLBACK_TIMEOUT = 10  # Seconds to wait for the callback

class CallbackHandler(BaseHTTPRequestHandler):
    """
    Simple HTTP handler to capture callback requests from the workflow.
    """
    received_requests = []

    def do_POST(self):
        # Read content length to capture body if needed
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length)
        
        # Store details about the request
        CallbackHandler.received_requests.append({
            'path': self.path,
            'body': body,
            'headers': self.headers
        })
        
        # Respond 200 OK to the workflow
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Callback received")

    def log_message(self, format, *args):
        # Silence server logs during tests
        pass

@pytest.fixture(scope="module")
def workflow_server():
    """
    Fixture to start the workflow server in a subprocess.
    """
    # Start server process
    env = os.environ.copy()
    env["PORT"] = str(WORKFLOW_PORT)
    # Ensure we use the same python interpreter
    cmd = [sys.executable, "-m", "src.basic.server"]
    
    print(f"\n[Fixture] Starting workflow server on port {WORKFLOW_PORT}...")
    process = subprocess.Popen(
        cmd,
        env=env,
        cwd=os.getcwd(), # Ensure we are in project root
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    # Wait a bit for server to start
    time.sleep(5)
    
    # Check if process died immediately
    if process.poll() is not None:
        stdout, stderr = process.communicate()
        pytest.fail(f"Workflow server failed to start:\nStdout: {stdout}\nStderr: {stderr}")

    yield process
    
    # Cleanup
    print("\n[Fixture] Stopping workflow server...")
    process.terminate()
    try:
        process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        process.kill()

@pytest.fixture(scope="function")
def callback_server():
    """
    Fixture to start a background HTTP server to receive callbacks.
    Returns the server URL.
    """
    # Reset received requests for each test
    CallbackHandler.received_requests = []
    
    # Port 0 lets the OS pick a free port
    server = HTTPServer(('127.0.0.1', 0), CallbackHandler)
    server_thread = threading.Thread(target=server.serve_forever)
    server_thread.daemon = True
    server_thread.start()
    
    host, port = server.server_address
    base_url = f"http://{host}:{port}"
    
    yield base_url
    
    server.shutdown()
    server.server_close()

def wait_for_callback(timeout: int = 10) -> bool:
    """Waits for the callback server to receive a request."""
    start_time = time.time()
    while time.time() - start_time < timeout:
        if len(CallbackHandler.received_requests) > 0:
            return True
        time.sleep(0.5)
    return False

def generate_json_payload(callback_url: str, attachment_count: int) -> dict:
    """
    Constructs a JSON payload matching EmailStartEvent.
    """
    # 1. Generate a "Long Body" (approx 5KB)
    long_body = "This is a long email body for testing purposes. " * 200
    
    # 2. Generate Attachments (Base64 encoded)
    attachments = []
    for i in range(attachment_count):
        filename = f"test_doc_{i}.txt"
        content = f"This is the content of attachment {i}".encode('utf-8')
        content_b64 = base64.b64encode(content).decode('utf-8')
        
        attachments.append({
            "id": f"att-{i}",
            "name": filename,
            "type": "text/plain",
            "content": content_b64,
            "file_id": None
        })

    # 3. Construct Event JSON
    # IMPORTANT: Wrapped in 'start_event' based on previous 400 error analysis
    payload = {
        "start_event": {
            "email_data": {
                "from_email": "test-sender@example.com",
                "to_email": "agent@myworkflow.com",
                "subject": f"Integration Test with {attachment_count} attachments",
                "text": long_body,
                "html": f"<html><body><p>{long_body}</p></body></html>",
                "attachments": attachments
            },
            "callback": {
                "callback_url": callback_url,
                "auth_token": "test-token"
            }
        }
    }

    return payload

@pytest.mark.parametrize("attachment_count", [0, 1, 5])
def test_workflow_execution_flow(workflow_server, callback_server, attachment_count):
    """
    Tests the full loop using JSON payload:
    1. POST JSON data to Workflow Endpoint.
    2. Expect 200 OK immediately.
    3. Expect Callback URL to be hit subsequently.
    """
    
    # Prepare payload
    payload = generate_json_payload(callback_server, attachment_count)
    
    print(f"\n[Test] Sending request with {attachment_count} attachments...")

    # Action: Send POST request
    with httpx.Client(timeout=300.0) as client:
        try:
            response = client.post(
                f"{WORKFLOW_ENDPOINT}/deployments/basic/workflows/email/run", 
                json=payload,
            )
        except httpx.ConnectError:
            pytest.fail("Could not connect to workflow server. Is it running?")

    # Check 1: Immediate HTTP 200 Response
    # The server might return 200 if it accepts the run, or 500 if it crashes immediately.
    if response.status_code != 200:
        print(f"[Test Error] Status: {response.status_code}")
        print(f"[Test Error] Body: {response.text}")
    
    assert response.status_code == 200, f"Workflow endpoint returned {response.status_code}: {response.text}"
    print(f"[Test] Immediate response received: {response.status_code}")
    print(f"[Test] Response body: {response.text}")

    # Check 2: Asynchronous Callback Verification
    # Since we set timeout=360s in the workflow code, we should wait long enough for it to finish.
    # However, for 0/1 attachments it should be fast. 5 attachments might take longer.
    # We'll use a generous timeout for the test to avoid flakiness.
    wait_time = 30 if attachment_count < 2 else 60
    print(f"[Test] Waiting up to {wait_time}s for callback to {callback_server}...")
    callback_received = wait_for_callback(timeout=wait_time)

    assert callback_received is True, "Workflow did not call the callback URL within the timeout period."
    
    last_request = CallbackHandler.received_requests[-1]
    print(f"[Test] Callback received successfully from path: {last_request['path']}")
