"""Bounded network retries and validated, staged SVG publication."""
import os
from pathlib import Path
import tempfile
import time
import xml.etree.ElementTree as ET

import requests

ATTEMPTS = 3
TIMEOUT = (10, 90)  # connection, socket read; workflow also bounds total runtime


def retry_network(operation):
    for attempt in range(ATTEMPTS):
        try:
            return operation()
        except (requests.ConnectionError, requests.Timeout, requests.HTTPError) as exc:
            response = getattr(exc, "response", None)
            status = response.status_code if response is not None else None
            transient = status is None or status in (408, 429, 500, 502, 503, 504)
            if not transient or attempt == ATTEMPTS - 1:
                raise
            # Never log response bodies, request headers, or credentials.
            print(f"Transient network failure ({type(exc).__name__}); retry {attempt + 2}/{ATTEMPTS}", flush=True)
            time.sleep(2 ** (attempt + 1))


def publish_svgs(render, names):
    """Render everything in staging; leave existing assets untouched on failure."""
    destination = Path.cwd()
    with tempfile.TemporaryDirectory(dir=destination, prefix=".svg-stage-") as stage:
        try:
            os.chdir(stage)
            render()
            for name in names:
                root = ET.parse(name).getroot()
                if root.tag != "{http://www.w3.org/2000/svg}svg" or not root.get("viewBox"):
                    raise ValueError(f"Invalid SVG: {name}")
        finally:
            os.chdir(destination)
        for name in names:
            os.replace(Path(stage) / name, destination / name)
