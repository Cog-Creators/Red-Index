import datetime
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

import yaml

CACHE = Path("cache")
METADATA_FILE = Path("metadata.json")


class CustomEncoder(json.JSONEncoder):
    def default(self, obj):
        if hasattr(obj, "__json__"):
            return obj.__json__()
        else:
            return json.JSONEncoder.default(self, obj)


class RepoNotCloned(Exception):
    pass


class InternalRepoMetadata:
    def __init__(self, url):
        self.url = url
        self.cogs = {}
        self._parse_name_branch_url(url)
        self._folder_check_and_get_info()
        approved_at = None
        for version_date, repositories in REPOSITORY_VERSIONS.items():
            if approved_at is None:
                if url in (repositories["approved"] or []):
                    approved_at = version_date
            elif url not in (repositories["approved"] or []):
                approved_at = None
        self.approved_at = approved_at
        added_at = None
        for version_date, repositories in REPOSITORY_VERSIONS.items():
            exists = url in (repositories["approved"] or []) or url in (
                repositories["unapproved"] or []
            )
            if added_at is None:
                if exists:
                    added_at = version_date
            elif not exists:
                added_at = None
        if added_at is None:
            raise RuntimeError("Could not find the repo url in later versions")
        self.added_at = added_at
        self.deleted_at = None

    def _parse_name_branch_url(self, url):
        branch = ""
        name = url.split("/")[4]
        # Owner/RepoName will be useful when it's time to exclude cogs
        self._owner_repo = url.split("/")[3] + "/" + url.split("/")[4]
        if "@" in name:
            name, branch = name.split("@")
        if name.endswith("/"):
            name = name[:-1]

        url = url.replace("/@", "@")
        if url.endswith("/"):
            url = url[:-1]

        self.name = name
        self.rx_branch = branch
        self._url = url

    def _folder_check_and_get_info(self):
        safe_name = re.sub(r"[^a-zA-Z0-9_\-\.]", "", self.name).strip(".")
        prefix = f"{safe_name}_" if safe_name else ""
        base_path = CACHE / Path(f"{prefix}{sha1_digest(self._url)}")
        if not base_path.is_dir():
            raise RepoNotCloned("Repo path does not exist. Cloning failed?")

        self._path = base_path

    def __json__(self):
        return {
            "cogs": self.cogs,
            "added_at": self.added_at.timestamp(),
            "approved_at": self.approved_at and self.approved_at.timestamp(),
            "deleted_at": self.deleted_at and self.deleted_at.timestamp(),
        }


class InternalCogMetadata:
    _BUFFER_SIZE = 2**18
    _PREFERRED_ALGORITHMS = ("sha256",)

    def __init__(self, repo_url, name, *, hashes, last_updated_at, added_to_repo_at):
        self.name = name
        self.hashes = hashes
        self.last_updated_at = last_updated_at
        added_at = None
        deleted_at = None
        for version_date, repositories in INDEX_VERSIONS.items():
            rx_cogs = repositories.get(repo_url, {}).get("rx_cogs", {})
            if name in rx_cogs:
                deleted_at = None
                if added_at is None:
                    added_at = version_date
            elif deleted_at is None:
                deleted_at = version_date
        if added_at is None:
            raise RuntimeError(
                f"Cog {name!r} does not exist in later index versions of the repo {repo_url}"
            )
        self.added_at = (
            min(added_to_repo_at, added_at)
            if added_at < datetime.datetime(2020, 9, 1, tzinfo=datetime.timezone.utc)
            else added_at
        )
        self.deleted_at = None

    @classmethod
    def from_path(cls, repo_url, name, path):
        obj = cls(
            repo_url=repo_url,
            name=name,
            hashes=cls.get_file_hashes(path),
            last_updated_at=cls.get_last_updated_at(path),
            added_to_repo_at=cls.get_added_to_repo_at(path),
        )
        return obj

    def __json__(self):
        return {
            "added_at": self.added_at.timestamp(),
            "last_updated_at": self.last_updated_at.timestamp(),
            "deleted_at": self.deleted_at and self.deleted_at.timestamp(),
            "hashes": self.hashes,
        }

    @classmethod
    def get_file_hashes(cls, path):
        buffer = bytearray(cls._BUFFER_SIZE)
        view = memoryview(buffer)
        digests = {algorithm: hashlib.new(algorithm) for algorithm in ("sha256",)}
        for path in sorted(path.rglob("**/*")):
            if not path.is_file():
                continue
            with path.open("rb") as fp:
                while True:
                    size = fp.readinto(buffer)
                    if not size:
                        break
                    for digestobj in digests.values():
                        digestobj.update(view[:size])
        return {algorithm: digestobj.hexdigest() for algorithm, digestobj in digests.items()}

    @classmethod
    def get_last_updated_at(cls, path):
        return datetime.datetime.fromisoformat(
            subprocess.check_output(
                ("git", "log", "-1", "--pretty=format:%ci", "."), text=True, cwd=path
            ).strip()
        )

    @classmethod
    def get_added_to_repo_at(cls, path):
        return datetime.datetime.fromisoformat(
            subprocess.check_output(
                ("git", "log", "--pretty=format:%ci", "."), text=True, cwd=path
            ).splitlines()[-1]
        )


def sha1_digest(url):
    return hashlib.sha1(url.encode("utf-8")).hexdigest()


REPOSITORY_VERSIONS: dict[datetime.datetime, dict[str, list[str]]] = {}
INDEX_VERSIONS: dict[datetime.datetime, dict[str, dict[str, dict[str, str]]]] = {}


def _get_repository_versions():
    global REPOSITORY_VERSIONS
    stdout = subprocess.check_output(
        ("git", "log", "--pretty=format:%H %ci", "--", "repositories.yaml"), text=True
    )
    for line in reversed(stdout.splitlines()):
        commit, _, date_string = line.partition(" ")
        REPOSITORY_VERSIONS[datetime.datetime.fromisoformat(date_string)] = yaml.safe_load(
            subprocess.check_output(("git", "cat-file", "-p", f"{commit}:repositories.yaml"))
        )


def _get_index_versions():
    global INDEX_VERSIONS
    stdout = subprocess.check_output(
        ("git", "log", "--pretty=format:%H %ci", "--since=2020-08-28", "--", "index/1-min.json"),
        text=True,
    )
    for line in reversed(stdout.splitlines()):
        commit, _, date_string = line.partition(" ")
        INDEX_VERSIONS[datetime.datetime.fromisoformat(date_string)] = json.loads(
            subprocess.check_output(("git", "cat-file", "-p", f"{commit}:index/1-min.json"))
        )


def main():
    print("Processing repo versions")
    _get_repository_versions()
    print("Processing index versions")
    _get_index_versions()
    print("Processing repositories.yaml")
    yamlfile = sys.argv[1]

    with open(yamlfile) as f:
        data = yaml.safe_load(f.read())

    metadata = {}

    with open("index/1-min.json") as f:
        current_index = json.load(f)

    idx = 0
    total = len(data["approved"]) + len(data["unapproved"])
    for k in ("approved", "unapproved"):
        idx += 1
        for idx, url in enumerate(data[k], start=idx):
            print("Processing", k, "repo", idx, "out of", total, "total:", url)
            try:
                repo_metadata = InternalRepoMetadata(url)
            except RepoNotCloned:
                print("FAIL: Repo not cloned!")
                continue
            index_repo = current_index.get(repo_metadata._url)
            if not index_repo:
                continue
            metadata[url] = repo_metadata

            for cog_name in index_repo["rx_cogs"]:
                cog_metadata = InternalCogMetadata.from_path(
                    repo_metadata._url, cog_name, repo_metadata._path / cog_name
                )
                repo_metadata.cogs[cog_name] = cog_metadata

    with open(METADATA_FILE, "w") as fp:
        json.dump(metadata, fp, indent=4, sort_keys=True, cls=CustomEncoder)


if __name__ == "__main__":
    main()
