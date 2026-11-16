"""CLI for bundle verification; the verifier itself lives in resolveit_core.model.bundle_verify.

Pin --expected-id from a trusted release channel. Hashes do not authenticate a publisher.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from resolveit_core.model.bundle_verify import (  # noqa: F401  (re-exported for scripts and tests)
    HEX,
    MAX_FILE_BYTES,
    REQUIRED,
    BundleError,
    file_digest,
    json_object,
    no_links,
    read_file,
    verify_bundle,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--expected-id")
    args = parser.parse_args()
    try:
        print(json.dumps(verify_bundle(args.directory, args.expected_id), sort_keys=True))
    except (OSError, ValueError):
        parser.exit(1, "Bundle verification failed; artifact details withheld.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
