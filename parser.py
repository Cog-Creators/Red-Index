import itertools
import os
import re
import sys
from hashlib import sha1
from pathlib import Path

import yaml

CACHE = Path("cache")


def executable_opener(path, flags):
    return os.open(path, flags, 0o755)


def sha1_digest(url):
    # this is only used with URLs from repositories.yaml list, there's no risk of collision attacks
    return sha1(url.encode("utf-8")).hexdigest()  # noqa: S324


def get_name(url):
    name = url.split("/")[4]
    if "@" in name:
        name, _ = name.split("@")
    name = name.removesuffix("/")
    return name


def get_clean_url(url):
    branch = ""
    if "@" in url:
        url, branch = url.split("@")
    url = url.removesuffix("/")
    return url, branch


if __name__ == "__main__":
    infile = sys.argv[1]
    outfile = sys.argv[2]

    with open(infile) as f:
        data = yaml.safe_load(f.read())

    sh = "mkdir -p cache\n"

    repos = []

    for repo_info in itertools.chain(data["approved"] or (), data["unapproved"] or ()):
        if isinstance(repo_info, str):
            repos.append(repo_info)
        else:
            repos.append(repo_info["url"])

    for r in repos:
        name = get_name(r)
        url, branch = get_clean_url(r)
        safe_name = re.sub(r"[^a-zA-Z0-9_\-\.]", "", name).strip(".")
        prefix = f"{safe_name}_" if safe_name else ""
        if branch:
            sha = sha1_digest(f"{url}@{branch}")
            dest = CACHE / Path(f"{prefix}{sha}")
            sh += (
                f"./git-retry.sh clone --depth=1 {url} --branch {branch} --single-branch {dest}\n"
            )
        else:
            sha = sha1_digest(url)
            dest = CACHE / Path(f"{prefix}{sha}")
            sh += f"./git-retry.sh clone --depth=1 {url} {dest}\n"

    with open(outfile, "w", opener=executable_opener) as f:
        f.write(sh)
