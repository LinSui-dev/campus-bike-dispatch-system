"""Test-only Uvicorn factory. Never imported by app/ production modules."""
from app.main import create_app
from .conftest import NetworkDouble, DispatchDouble


def create_socket_app():
    return create_app(network_factory=NetworkDouble, dispatch_factory=DispatchDouble,
                      auto_advance=False)
