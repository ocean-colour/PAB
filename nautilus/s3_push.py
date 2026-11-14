"""Push a local directory tree to Nautilus S3 (`s3://pab`), idempotently.

Runs inside a pod that mounts the PVC and the `prp-s3-credentials` secret. The
image ships no `aws`/`rclone` CLI, so this uses boto3 directly.

Idempotent by design: an object whose key already exists with the same byte size
is skipped, so a re-run after an interruption only uploads what is missing.
Uploads run in a thread pool (the work is network-bound).

    python s3_push.py <local_dir> <bucket> <key_prefix> [--jobs N] [--dry-run]

Environment:
    ENDPOINT_URL    S3 endpoint (default https://s3-west.nrp-nautilus.io)
    AWS_PROFILE     credentials profile (default "default")
"""

from __future__ import annotations

import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ENDPOINT = os.environ.get("ENDPOINT_URL", "https://s3-west.nrp-nautilus.io")


def existing_sizes(client, bucket: str, prefix: str) -> dict[str, int]:
    """`{key: size}` for everything already under ``prefix`` (one paginated pass)."""
    out: dict[str, int] = {}
    token = None
    while True:
        kw = {"Bucket": bucket, "Prefix": prefix}
        if token:
            kw["ContinuationToken"] = token
        resp = client.list_objects_v2(**kw)
        for obj in resp.get("Contents", []):
            out[obj["Key"]] = obj["Size"]
        if not resp.get("IsTruncated"):
            return out
        token = resp.get("NextContinuationToken")


def main(argv: list[str]) -> int:
    import boto3

    if len(argv) < 3:
        print(__doc__)
        return 2
    local = Path(argv[0]).resolve()
    bucket, prefix = argv[1], argv[2].strip("/")
    jobs = 8
    dry = "--dry-run" in argv
    if "--jobs" in argv:
        jobs = int(argv[argv.index("--jobs") + 1])

    client = boto3.session.Session(
        profile_name=os.environ.get("AWS_PROFILE", "default")
    ).client("s3", endpoint_url=ENDPOINT)

    files = sorted(p for p in local.rglob("*") if p.is_file())
    total_bytes = sum(p.stat().st_size for p in files)
    print(
        f"local: {local}  files={len(files)}  bytes={total_bytes / 1e6:.0f} MB\n"
        f"target: s3://{bucket}/{prefix}/  endpoint={ENDPOINT}  jobs={jobs}",
        flush=True,
    )

    have = existing_sizes(client, bucket, prefix + "/")
    print(f"already in bucket under prefix: {len(have)} objects", flush=True)

    todo = []
    skipped = 0
    for path in files:
        key = f"{prefix}/{path.relative_to(local).as_posix()}"
        if have.get(key) == path.stat().st_size:
            skipped += 1
            continue
        todo.append((path, key))
    print(f"to upload: {len(todo)}   already current (skipped): {skipped}", flush=True)
    if dry:
        for _path, key in todo[:20]:
            print(f"  would upload {key}")
        print("(dry run)")
        return 0

    done = failed = 0
    sent_bytes = 0

    def _upload(item):
        path, key = item
        client.upload_file(str(path), bucket, key)
        return path.stat().st_size

    with ThreadPoolExecutor(max_workers=jobs) as ex:
        futs = {ex.submit(_upload, item): item for item in todo}
        for fut in as_completed(futs):
            path, key = futs[fut]
            try:
                sent_bytes += fut.result()
                done += 1
            except Exception as exc:  # noqa: BLE001 — report and keep going
                failed += 1
                print(f"  FAILED {key}: {type(exc).__name__}: {exc}", flush=True)
            if (done + failed) % 200 == 0:
                print(
                    f"  progress {done + failed}/{len(todo)} "
                    f"({sent_bytes / 1e6:.0f} MB, {failed} failed)",
                    flush=True,
                )

    after = existing_sizes(client, bucket, prefix + "/")
    print(
        f"\nuploaded={done} failed={failed} sent={sent_bytes / 1e6:.0f} MB\n"
        f"objects now under s3://{bucket}/{prefix}/: {len(after)} "
        f"({sum(after.values()) / 1e6:.0f} MB)",
        flush=True,
    )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
