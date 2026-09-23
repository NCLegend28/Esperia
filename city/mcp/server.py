"""Thin launcher so `python server.py` works; the server lives in voxkit/server.py (entry point: voxkit.server:main)."""

from voxkit.server import main

if __name__ == "__main__":
    main()
