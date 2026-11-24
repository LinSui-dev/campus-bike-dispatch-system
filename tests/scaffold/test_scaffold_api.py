"""Opt-in scaffold diagnostics. Never required once business is implemented."""
from fastapi.testclient import TestClient
import pytest

from app.main import app
from scripts.check_baseline import load

pytestmark = pytest.mark.scaffold


def test_scaffold_reports_its_stage():
    with TestClient(app) as client:
        assert client.get('/api/v1/health').json()['stage'] == 'scaffold'


def test_placeholder_business_is_explicit():
    with TestClient(app) as client:
        response = client.post('/api/v1/runs', json=load('contracts/examples/run_request.json'))
        assert response.status_code == 501
        assert response.json()['code'] == 'NOT_IMPLEMENTED'
