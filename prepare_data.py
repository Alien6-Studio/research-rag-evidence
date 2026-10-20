"""Fetch the public, pinned study inputs without downloading model weights."""
from pathlib import Path
import hashlib
import json
import urllib.request

ROOT = Path(__file__).resolve().parent


def main():
    sources = json.loads((ROOT / "sources.json").read_text())
    data = ROOT / "data"
    data.mkdir(exist_ok=True)
    for key, filename in [("dataset", "hotpot-validation.parquet"), ("tokenizer", "qwen-tokenizer.json")]:
        source = sources[key]
        path = data / filename
        if not path.exists() or hashlib.sha256(path.read_bytes()).hexdigest() != source["sha256"]:
            with urllib.request.urlopen(source["url"], timeout=90) as response:
                content = response.read()
            if hashlib.sha256(content).hexdigest() != source["sha256"]:
                raise RuntimeError(f"Unexpected source hash: {key}")
            path.write_bytes(content)
        (data / f"{key}-source.json").write_text(json.dumps(source, indent=2))
        print(f"Verified {key}: {source['sha256']}")


if __name__ == "__main__":
    main()
