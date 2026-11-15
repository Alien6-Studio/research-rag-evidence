#!/usr/bin/env python3
"""One entry point for identity checks, scientific tests, and offline replay."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
from reproduction import runtime


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['check', 'test', 'verify'])
    parser.add_argument('--offline', action='store_true', help='Require already cached, hash-verified public dataset/tokenizer')
    parser.add_argument('--inputs', type=Path, help='Read-only directory containing the two pinned input files')
    parser.add_argument('--output', type=Path, help='New directory for replay reports; defaults to .cache/reproduction/<timestamp>')
    args = parser.parse_args()
    if args.action == 'check':
        print(json.dumps(runtime.check(), indent=2))
    else:
        runtime.run_science(args.action, inputs=args.inputs, offline=args.offline, output=args.output)
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (ValueError, RuntimeError, OSError, KeyError, subprocess.CalledProcessError) as error:
        print('Reproduction failed: ' + str(error), file=sys.stderr)
        raise SystemExit(1)
