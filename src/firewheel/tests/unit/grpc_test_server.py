"""
Shared helpers for running a real, in-process FIREWHEEL gRPC server in tests.

The server binds an ephemeral localhost port and keeps all state in memory, so
no external FIREWHEEL infrastructure is required.
"""

import shutil
import tempfile
import contextlib
from concurrent import futures
from unittest.mock import patch

import grpc

from firewheel.lib.grpc import firewheel_grpc_pb2_grpc
from firewheel.lib.grpc.firewheel_grpc_server import FirewheelServicer


def build_servicer(cache_root):
    """
    Create a servicer using its real constructor.

    Using the real ``__init__`` (rather than ``object.__new__``) ensures that any
    state the server sets up, such as its synchronization primitives, exists in
    tests exactly as it does in production.

    Args:
        cache_root (str): Directory to use as the gRPC ``root_dir``.

    Returns:
        FirewheelServicer: A servicer ready to be attached to a gRPC server.
    """
    grpc_config = {"root_dir": cache_root, "cache_dir": "cache"}
    with patch(
        "firewheel.lib.grpc.firewheel_grpc_server.Config.get_config",
        return_value={"grpc": grpc_config},
    ):
        return FirewheelServicer()


@contextlib.contextmanager
def running_grpc_server(max_workers=2):
    """
    Run a real gRPC server on an ephemeral localhost port.

    Args:
        max_workers (int): Size of the server's request thread pool.

    Yields:
        tuple[FirewheelServicer, int]: The servicer and the bound port.
    """
    cache_root = tempfile.mkdtemp(prefix="fw-grpc-test-")
    try:
        servicer = build_servicer(cache_root)
        server = grpc.server(futures.ThreadPoolExecutor(max_workers=max_workers))
        firewheel_grpc_pb2_grpc.add_FirewheelServicer_to_server(servicer, server)
        port = server.add_insecure_port("127.0.0.1:0")
        server.start()
        try:
            yield servicer, port
        finally:
            server.stop(grace=None)
    finally:
        shutil.rmtree(cache_root, ignore_errors=True)
