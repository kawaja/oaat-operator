#!/usr/bin/env python3
"""Delete GitHub Container Registry (GHCR) image versions that have 0 downloads.

By default only *untagged* versions are considered (leftover multi-arch
manifests/layers that are no longer referenced by any tag). Pass
--include-tagged to also consider tagged versions with 0 downloads.

GitHub's Packages REST API does not expose a download count for container
image versions (confirmed: no `download_count` field on the versions
endpoint). The only place this number is shown is the per-version HTML page
on github.com ("Download activity" -> "Total downloads"), so this script
scrapes that page for each candidate version. That makes count-fetching
best-effort: if GitHub changes that page's markup, or the package is private
and the token can't render the web UI for it, the count comes back as
"unknown" and the version is skipped rather than risk deleting something
we're not sure about.

Auth: reads a token from the $GHCR_CLEANUP_TOKEN env var (override the name
with --token-env). Use a classic PAT scoped to ONLY read:packages and
delete:packages - nothing else, so it can't touch your repos or your orgs'
resources even if leaked. Fine-grained PATs don't currently cover the
package-version endpoints at all, so a classic token is the only option:

    https://github.com/settings/tokens/new?scopes=read:packages,delete:packages&description=ghcr-cleanup

If $GHCR_CLEANUP_TOKEN isn't set, falls back to `gh auth token` - but that's
whatever broad-scoped token `gh auth login` set up (usually includes repo,
workflow, read:org, ...), so it's printed as a loud warning rather than used
quietly.

Usage:
    scripts/ghcr-cleanup.py --owner kawaja --dry-run
    scripts/ghcr-cleanup.py --owner kawaja --package oaat-operator
    scripts/ghcr-cleanup.py --owner kawaja --include-tagged --protect-tags latest,dev --dry-run
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

API_BASE = "https://api.github.com"
WEB_BASE = "https://github.com"
USER_AGENT = "ghcr-cleanup-script"

DOWNLOAD_RE = re.compile(r'Total downloads</span>\s*<span[^>]*>([\d,]+)</span>', re.S)


def get_token(token_env: str) -> str:
    token = os.environ.get(token_env)
    if token:
        return token.strip()

    print(f"Warning: ${token_env} is not set - falling back to `gh auth token`, "
          "which is likely scoped far beyond packages (repo, workflow, read:org, "
          "...). For a token that can't touch your repos/orgs, create a classic "
          f"PAT with only read:packages+delete:packages and export it as "
          f"${token_env}.", file=sys.stderr)
    try:
        result = subprocess.run(
            ["gh", "auth", "token"], capture_output=True, text=True, check=True)
    except FileNotFoundError:
        msg = f"`gh` CLI not found. Install it and run `gh auth login`, or set ${token_env}."
        sys.exit(msg)
    except subprocess.CalledProcessError as exc:
        msg = f"`gh auth token` failed - run `gh auth login`, or set ${token_env}.\n{exc.stderr}"
        sys.exit(msg)
    return result.stdout.strip()


def api_request(path: str, token: str, method: str = "GET"):
    url = f"{API_BASE}/{path}"
    req = urllib.request.Request(url, method=method, headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": USER_AGENT,
    })
    try:
        with urllib.request.urlopen(req) as resp:
            body = resp.read()
            return (json.loads(body) if body else None), resp.headers.get("Link")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")
        sys.exit(f"GitHub API error {exc.code} for {method} {url}: {detail}")


def paginated(path: str, token: str) -> list:
    items = []
    next_path = f"{path}{'&' if '?' in path else '?'}per_page=100"
    while next_path:
        data, link_header = api_request(next_path, token)
        items.extend(data)
        next_path = None
        if link_header:
            for part in link_header.split(","):
                segment = part.split(";")
                if len(segment) == 2 and 'rel="next"' in segment[1]:
                    next_path = segment[0].strip().strip("<>")[len(API_BASE) + 1:]
    return items


def owner_prefix(owner: str, token: str) -> str:
    data, _ = api_request(f"users/{owner}", token)
    return "orgs" if data.get("type") == "Organization" else "users"


def list_packages(prefix: str, owner: str, token: str) -> list:
    return paginated(f"{prefix}/{owner}/packages?package_type=container", token)


def list_versions(prefix: str, owner: str, package: str, token: str) -> list:
    name = urllib.parse.quote(package, safe="")
    return paginated(f"{prefix}/{owner}/packages/container/{name}/versions", token)


def delete_version(prefix: str, owner: str, package: str, version_id: int, token: str) -> None:
    name = urllib.parse.quote(package, safe="")
    api_request(f"{prefix}/{owner}/packages/container/{name}/versions/{version_id}",
                token, method="DELETE")


def fetch_download_count(prefix: str, owner: str, package: str, version_id: int, token: str):
    name = urllib.parse.quote(package, safe="")
    url = f"{WEB_BASE}/{prefix}/{owner}/packages/container/{name}/{version_id}"
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (compatible; ghcr-cleanup-script)",
        "Authorization": f"Bearer {token}",
    })
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode("utf-8", errors="replace")
    except (urllib.error.HTTPError, urllib.error.URLError):
        return None
    match = DOWNLOAD_RE.search(html)
    return int(match.group(1).replace(",", "")) if match else None


def parse_args():
    parser = argparse.ArgumentParser(
        description="Delete GHCR container image versions with 0 downloads.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__)
    parser.add_argument(
        "--owner", required=True,
        help="GitHub username or organization that owns the packages")
    parser.add_argument(
        "--package",
        help="Only operate on this package (default: all container "
             "packages owned by --owner)")
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Show what would be deleted without deleting anything")
    parser.add_argument(
        "--include-tagged", action="store_true",
        help="Also consider tagged versions with 0 downloads (default: untagged only)")
    parser.add_argument(
        "--protect-tags", default="latest",
        help="Comma-separated tags never deleted, even with --include-tagged "
             "(default: latest)")
    parser.add_argument(
        "--min-age-hours", type=float, default=24,
        help="Only consider versions at least this old, so something just pushed "
             "isn't deleted before anyone has pulled it (default: 24)")
    parser.add_argument(
        "--yes", action="store_true",
        help="Don't prompt for confirmation before deleting")
    parser.add_argument(
        "--token-env", default="GHCR_CLEANUP_TOKEN",
        help="Env var holding a classic PAT scoped to read:packages+delete:packages "
             "only. Falls back to `gh auth token` (with a warning) if unset "
             "(default: GHCR_CLEANUP_TOKEN)")
    return parser.parse_args()


def main():
    args = parse_args()
    token = get_token(args.token_env)
    prefix = owner_prefix(args.owner, token)

    if args.package:
        packages = [args.package]
    else:
        packages = [p["name"] for p in list_packages(prefix, args.owner, token)]
        if not packages:
            print(f"No container packages found for {args.owner}.")
            return
        print(f"Found {len(packages)} container package(s): {', '.join(packages)}")

    protected_tags = {t.strip() for t in args.protect_tags.split(",") if t.strip()}
    cutoff = datetime.now(timezone.utc).timestamp() - args.min_age_hours * 3600

    candidates = []
    for package in packages:
        for version in list_versions(prefix, args.owner, package, token):
            tags = version.get("metadata", {}).get("container", {}).get("tags", [])
            if tags:
                if not args.include_tagged:
                    continue
                if protected_tags & set(tags):
                    continue
            created = datetime.fromisoformat(version["created_at"].replace("Z", "+00:00"))
            if created.timestamp() > cutoff:
                continue
            candidates.append((package, version, tags))

    if not candidates:
        print("No candidate versions found.")
        return

    print(f"Checking download counts for {len(candidates)} candidate version(s)...")
    to_delete = []
    unknown = []
    for package, version, tags in candidates:
        count = fetch_download_count(prefix, args.owner, package, version["id"], token)
        time.sleep(0.2)
        if count is None:
            unknown.append((package, version, tags))
        elif count == 0:
            to_delete.append((package, version, tags, count))

    if unknown:
        print(f"\nCould not determine download count for {len(unknown)} version(s); "
              f"skipping them to be safe:")
        for package, version, tags in unknown:
            print(f"  {package} id={version['id']} digest={version['name']}")

    if not to_delete:
        print("\nNothing to delete.")
        return

    print(f"\n{'DRY RUN - ' if args.dry_run else ''}"
          f"{len(to_delete)} version(s) with 0 downloads:")
    header = f"{'PACKAGE':<20} {'ID':<12} {'TAGS':<20} {'DIGEST':<14} " \
             f"{'CREATED':<21} DOWNLOADS"
    print(header)
    for package, version, tags, count in to_delete:
        digest = version["name"]
        short_digest = digest.split(":", 1)[-1][:12]
        tag_str = ",".join(tags) if tags else "<untagged>"
        print(f"{package:<20} {version['id']:<12} {tag_str:<20} {short_digest:<14} "
              f"{version['created_at']:<21} {count}")

    if args.dry_run:
        print("\nDry run: no versions were deleted.")
        return

    if not args.yes:
        answer = input(f"\nDelete these {len(to_delete)} version(s)? Type 'yes' to confirm: ")
        if answer.strip().lower() != "yes":
            print("Aborted.")
            return

    for package, version, tags, count in to_delete:
        print(f"Deleting {package} id={version['id']}...")
        delete_version(prefix, args.owner, package, version["id"], token)
    print("Done.")


if __name__ == "__main__":
    main()
