"""Real TCP HTTP/WebSocket transport using explicit test ports, isolated DB and server process."""
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
import httpx
from websockets.sync.client import connect
from .conftest import request, assert_state


def test_real_uvicorn_http_websocket_transport(tmp_path):
    root=Path(__file__).resolve().parents[3]
    with socket.socket() as candidate:
        candidate.bind(('127.0.0.1',0))
        port=candidate.getsockname()[1]
    env=os.environ.copy()
    env.update(PYTHONPATH=str(root)+os.pathsep+str(root/'backend'),DATA_PROFILE='fixture',
               DATABASE_URL='sqlite:///'+(tmp_path/'transport.db').as_posix())
    process=subprocess.Popen([sys.executable,'-m','uvicorn','backend.tests.owner_a.socket_app:create_socket_app',
        '--factory','--host','127.0.0.1','--port',str(port)],cwd=root,env=env,
        stdout=subprocess.PIPE,stderr=subprocess.STDOUT, text=True,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
    base=f'http://127.0.0.1:{port}'
    try:
        deadline=time.monotonic()+15
        with httpx.Client(base_url=base,timeout=3) as client:
            while True:
                try:
                    response=client.get('/api/v1/health')
                    if response.status_code==200:
                        break
                except httpx.TransportError:
                    pass
                if process.poll() is not None or time.monotonic()>deadline:
                    raise AssertionError('Uvicorn did not become ready')
                time.sleep(0.05)
            created=client.post('/api/v1/runs',json=request())
            assert created.status_code==201,created.text
            state=created.json()
            assert_state(state)
            run=state['run_id']
            with connect(f'ws://127.0.0.1:{port}/ws/runs/{run}',open_timeout=3) as ws:
                first=json.loads(ws.recv(timeout=3))
                assert first['type']=='state' and first['seq']==state['seq']
                paused=client.post(f'/api/v1/runs/{run}/control',json={'action':'pause'}).json()
                pushed=json.loads(ws.recv(timeout=3))
                assert pushed['seq']==paused['seq']>first['seq']
                assert pushed['status']=='paused' and pushed['context']['seed']==42
                reset=client.post(f'/api/v1/runs/{run}/control',json={'action':'reset','save':False})
                assert reset.status_code==200
                final=json.loads(ws.recv(timeout=3))
                assert final['status']=='stopped'
            assert client.get('/api/v1/runtime').json()['mode']=='idle'
    finally:
        process.terminate()
        try:
            output=process.communicate(timeout=10)[0]
        except subprocess.TimeoutExpired:
            process.kill()
            output=process.communicate(timeout=5)[0]
        if process.returncode not in (0,1,-15):
            # Windows terminate may use exit code 1. Logs are attached to assertion failures only.
            assert process.returncode is not None, output
