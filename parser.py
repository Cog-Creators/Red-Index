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
    return sha1(url.encode('utf-8')).hexdigest()

def get_name(url):
    name = url.split("/")[4]
    if "@" in name:
        name, _ = name.split("@")
    if name.endswith("/"):
        name = name[:-1]
    return name

def get_clean_url(url):
    branch = ""
    if "@" in url:
        url, branch = url.split("@")
    if url.endswith("/"):
        url = url[:-1]
    return url, branch

if __name__ == "__main__":
    infile = sys.argv[1]
    outfile = sys.argv[2]

    with open(infile) as f:
        data = yaml.safe_load(f.read())

    sh = "mkdir -p cache\n"

    repos = []

    if data["approved"]:
        repos.extend(data["approved"])
    if data["unapproved"]:
        repos.extend(data["unapproved"])

    for r in repos:
        name = get_name(r)
        url, branch = get_clean_url(r)
        safe_name = re.sub(r"[^a-zA-Z0-9_\-\.]", "", name).strip(".")
        prefix = f"{safe_name}_" if safe_name else ""
        if branch:
            sha = sha1_digest(f"{url}@{branch}")
            dest = CACHE / Path(f"{prefix}{sha}")
            sh += f"./git-retry.sh clone --depth=1 {url} --branch {branch} --single-branch {dest}\n"
        else:
            sha = sha1_digest(url)
            dest = CACHE / Path(f"{prefix}{sha}")
            sh += f"./git-retry.sh clone --depth=1 {url} {dest}\n"

    with open(outfile, "w", opener=executable_opener) as f:
        f.write(sh)
