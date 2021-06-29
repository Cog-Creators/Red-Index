import asyncio
import yaml
import sys
import aiohttp
import os
import json
from constants import CACHE, GEN_PATH, GEN_ERROR_LOG
from hashlib import sha1
from pathlib import Path

HEADERS = {'Authorization': 'token ' + os.environ["GITHUB_TOKEN"]}
BASE_GH = "https://api.github.com"
GET_REPO = BASE_GH + "/repos/{owner}/{repo}"
GET_SHA = BASE_GH + "/repos/{owner}/{repo}/branches"
GET_TREE = BASE_GH + "/repos/{owner}/{repo}/git/trees/{tree_sha}"
RAW_CONTENT = "https://raw.githubusercontent.com/{owner}/{repo}/{branch}/"
IGNORED_FOLDERS = (".github", )

tasks = []

class FailedGHParse(Exception):
    pass

def sha1_digest(url):
    return sha1(url.encode('utf-8')).hexdigest()

def get_clean_url(url):
    branch = ""
    if "@" in url:
        url, branch = url.split("@")
    if url.endswith("/"):
        url = url[:-1]
    return url, branch

async def get_gh_branch(url):
    # https://docs.github.com/en/rest/reference/repos#get-a-repository
    repo, owner = url.split("/")[-1], url.split("/")[-2]
    async with aiohttp.ClientSession() as session:
        async with session.get(GET_REPO.format(repo=repo, owner=owner), headers=HEADERS) as resp:
            if resp.status != 200:
                raise FailedGHParse(f"Could not get repo for {url}. Status: {resp.status}")
            data = await resp.json()

    return data["default_branch"]

async def get_sha(url, branch):
    # https://docs.github.com/en/rest/reference/repos#branches
    repo, owner = url.split("/")[-1], url.split("/")[-2]
    async with aiohttp.ClientSession() as session:
        async with session.get(GET_SHA.format(repo=repo, owner=owner), headers=HEADERS) as resp:
            if resp.status != 200:
                raise FailedGHParse(f"Could not get branches for {url}. Status: {resp.status}")
            data = await resp.json()

    for repo_branch in data:
        if repo_branch["name"] == branch:
            return repo_branch["commit"]["sha"]

    raise FailedGHParse(f"Could not find branch {branch} for {url}")

async def get_tree_and_build_cache(url, branch, sha, original_url):
    # https://docs.github.com/en/rest/reference/git#get-a-tree
    repo, owner = url.split("/")[-1], url.split("/")[-2]
    raw_content_url = RAW_CONTENT.format(owner=owner, repo=repo, branch=branch)
    async with aiohttp.ClientSession() as session:
        async with session.get(GET_TREE.format(repo=repo, owner=owner, tree_sha=sha), headers=HEADERS) as resp:
            if resp.status != 200:
                raise FailedGHParse(f"Could not get file tree for {url}. Status: {resp.status}")
            tree = await resp.json()

    has_repo_info = False
    cog_folders = []
    for _file in tree["tree"]:
        # check for folders here, type 'tree', ignore obvious non-cog stuff like '.github'
        if _file["path"] == "info.json" and _file["type"] == "blob":
            has_repo_info = True
        elif _file["type"] == "tree" and not _file["path"] in IGNORED_FOLDERS:
            cog_folders.append(_file["path"])

    if not has_repo_info:
        raise FailedGHParse(f"Repo {url} has no repo-level info.json")
    elif not cog_folders:
        raise FailedGHParse(f"Repo {url} has no cogs")

    if "@" in original_url:
        folder_name = sha1_digest(original_url)
    else:
        folder_name = sha1_digest(url)
    main_folder = CACHE / Path(folder_name)
    main_folder.mkdir(parents=True)

    async with aiohttp.ClientSession() as session:
        async with session.get(raw_content_url + "info.json") as resp:
            if resp.status != 200:
                raise FailedGHParse(f"Could not get fetch repo-level info.json for {url}. Status: {resp.status}")
            data = await resp.read()

    info_json_path = main_folder / "info.json"
    with open(str(info_json_path), "wb") as f:
        f.write(data)

    try:
        with open(str(info_json_path)) as f:
            json.load(f)
    except json.JSONDecodeError:
        raise FailedGHParse(f"Repo level info.json has invalid json for {url}")

    for folder_name in cog_folders:
        async with aiohttp.ClientSession() as session:
            async with session.get(raw_content_url + folder_name + "/info.json") as resp:
                if resp.status == 404:
                    continue
                elif resp.status != 200:
                    continue # log?
                data = await resp.read()

        try:
            json.loads(data)
        except json.JSONDecodeError:
            #raise FailedGHParse(f"Cog {folder_name}'s info.json for {url} has invalid json")
            continue

        cog_info_json_path = main_folder / folder_name
        cog_info_json_path.mkdir(parents=True)

        with open(str(cog_info_json_path / "info.json"), "wb") as f:
            f.write(data)

async def process_gh_repo(url):
    # - Get the main branch (if not specified)
    # - Get the current sha for the branch
    # - Get the recursive file tree using the sha
    # - Get the repo's info.json's blob
    # - Get the blob for each info.json of each cog, so N calls
    original_url = url
    url, branch = get_clean_url(url)
    if not branch:
        branch = await get_gh_branch(url)
    sha = await get_sha(url, branch)
    await get_tree_and_build_cache(url, branch, sha, original_url)
    return f"{original_url} has been processed."

if __name__ == "__main__":
    infile = sys.argv[1]
    outfile = sys.argv[2]

    with open(infile) as f:
        data = yaml.safe_load(f.read())

    repos = []

    if data["approved"]:
        repos.extend(data["approved"])
    if data["unapproved"]:
        repos.extend(data["unapproved"])

    # Github repos will be fetched through the API
    for r in repos:
        if "github.com" not in r:
            continue
        tasks.append(process_gh_repo(r))

    loop = asyncio.get_event_loop()
    group = asyncio.gather(*tasks, return_exceptions=True)
    results = loop.run_until_complete(group)
    logs = []
    for r in results:
        if isinstance(r, FailedGHParse):
            logs.append(str(r))
        elif isinstance(r, Exception):
            raise r
        else:
            print(r)

    if not GEN_PATH.exists():
        GEN_PATH.mkdir()
    with open(str(GEN_ERROR_LOG), "w") as f:
        f.write("\n".join(logs)) # This will also empty the error log of the previous runs

    # Non-github repos will be cloned later
    sh = ""
    for r in repos:
        if "github.com" in r:
            continue
        url, branch = get_clean_url(r)
        if branch:
            sha = sha1_digest(f"{url}@{branch}")
            dest = CACHE / Path(sha)
            sh += f"./git-retry.sh clone --depth=1 {url} --branch {branch} --single-branch {dest}\n"
        else:
            sha = sha1_digest(url)
            dest = CACHE / Path(sha)
            sh += f"./git-retry.sh clone --depth=1 {url} {dest}\n"

    with open(outfile, "w") as f:
        f.write(sh)
