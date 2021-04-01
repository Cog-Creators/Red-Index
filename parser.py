import yaml
import sys
from hashlib import sha1
from pathlib import Path

CACHE = Path("cache")

def sha1_digest(url):
    return sha1(url.encode('utf-8')).hexdigest()

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

    sh = ""

    repos = []

    if data["approved"]:
        repos.extend(data["approved"])
    if data["unapproved"]:
        repos.extend(data["unapproved"])

    for r in repos:
        url, branch = get_clean_url(r)
        if branch:
            sha = sha1_digest(f"{url}@{branch}")
            dest = CACHE / Path(sha)
            sh += f"./git-retry.sh clone {url} --branch {branch} --single-branch {dest}\n"
        else:
            sha = sha1_digest(url)
            dest = CACHE / Path(sha)
            sh += f"./git-retry.sh clone {url} {dest}\n"

    with open(outfile, "w") as f:
        f.write(sh)
