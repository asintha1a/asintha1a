"""Cache the rembg u2netp model, verifying rembg's published checksum."""
import hashlib
import os
from pathlib import Path
import tempfile

import requests
from reliability import TIMEOUT, retry_network

MODEL_URL = "https://github.com/danielgatis/rembg/releases/download/v0.0.0/u2netp.onnx"
MODEL_MD5 = "8e83ca70e441ab06c318d82300c84806"


def valid_model(path):
    return path.is_file() and hashlib.md5(path.read_bytes()).hexdigest() == MODEL_MD5


def prepare_model():
    home = Path(os.environ.get("U2NET_HOME", Path.home() / ".u2net")).expanduser()
    home.mkdir(parents=True, exist_ok=True)
    target = home / "u2netp.onnx"
    if valid_model(target):
        print("Using checksum-verified cached u2netp model", flush=True)
        return target

    def download():
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=home, suffix=".part", delete=False) as output:
                temporary = Path(output.name)
                with requests.get(MODEL_URL, stream=True, timeout=TIMEOUT) as response:
                    response.raise_for_status()
                    for chunk in response.iter_content(1024 * 1024):
                        output.write(chunk)
            if not valid_model(temporary):
                raise ValueError("Downloaded u2netp model checksum mismatch")
            os.replace(temporary, target)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    retry_network(download)
    return target


if __name__ == "__main__":
    prepare_model()
