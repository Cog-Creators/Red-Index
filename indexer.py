import datetime
import hmac
import json
import yaml
import re
import sys
from gzip import GzipFile
from pathlib import Path
import hashlib

CACHE = Path("cache")

RX_PROTOCOL = 1 # This should be incremented when breaking changes to the format are implemented
GEN_PATH = Path("index") # exposed Index endpoints
GEN_FILE = GEN_PATH / Path(f"{RX_PROTOCOL}.json") # Pretty, for QA checking
GEN_MIN_FILE = GEN_PATH / Path(f"{RX_PROTOCOL}-min.json") # Minified, for user download
GEN_GZ_FILE = GEN_PATH / Path(f"{RX_PROTOCOL}-min.json.gz") # Gzipped
GEN_ERROR_LOG = GEN_PATH / Path(f"{RX_PROTOCOL}-errors.yaml") # Error log
METADATA_FILE = Path("metadata.json") # internal metadata, used for e.g. last_updated_at dates
NOW = datetime.datetime.now(datetime.timezone.utc)


class CustomEncoder(json.JSONEncoder):
    def default(self, obj):
        if hasattr(obj, "__json__"):
            return obj.__json__()
        else:
            return json.JSONEncoder.default(self, obj)

class Repo:
    def __init__(self, metadata, category: str):
        """Anything exposed here will be serialized later

        Attributes starting with rx_ deviate from the info.json spec
        and as such they have this prefix to avoid future conflicts"""
        self.rx_category = category # approved / unapproved
        self._owner_repo = ""
        self._error = ""
        self._path = None
        self.rx_cogs = []
        self.author = []
        self.description = ""
        self.short = ""
        self._metadata = metadata
        self._url = metadata.url
        self.name = ""
        self.rx_branch = ""
        try:
            self.parse_name_branch_url(metadata.url)
        except:
            self._error = ("Something went wrong while parsing the url. "
                            "Is it a valid address?")

    def parse_name_branch_url(self, url):
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

    def folder_check_and_get_info(self):
        if self._error:
            return

        safe_name = re.sub(r"[^a-zA-Z0-9_\-\.]", "", self.name).strip(".")
        prefix = f"{safe_name}_" if safe_name else ""
        base_path = CACHE / Path(f"{prefix}{sha1_digest(self._url)}")
        if not base_path.is_dir():
            self._error = "Repo path does not exist. Cloning failed?"
            return

        self._path = base_path

        infofile = base_path / Path("info.json")
        if not infofile.is_file():
            self._error = "No repo info.json found."
            return

        try:
            with open(str(infofile)) as f:
                info = json.load(f)
        except:
            self._error = "Error reading repo info.json. Possibly invalid."
            return

        self.author = info.get("author", [])
        self.description = info.get("description", "")
        self.short = info.get("short", "")

    def populate_cogs(self):
        if self._error:
            return
        sub_dirs = [p for p in self._path.iterdir() if p.is_dir() and not p.name.startswith(".")]

        for d in sub_dirs:
            path = d / Path("info.json")
            if path.is_file(): # Dirs with no info.json inside are simply ignored
                self.rx_cogs.append(Cog(d.name, d))

        if not self.rx_cogs:
            self._error = "Repo contains no valid cogs"

    def process_cogs(self):
        if self._error:
            return

        for cog in self.rx_cogs:
            cog.get_info(self._metadata)
            cog.check_cog_validity()

    def __json__(self):
        return {k:v for (k, v) in self.__dict__.items() if not k.startswith("_") and not callable(k)}

class Cog:
    def __init__(self, name: str, path: Path):
        """Anything exposed here will be serialized later

        Attributes starting with rx_ deviate from the info.json spec
        and as such they have this prefix to avoid future conflicts"""
        self._name = name
        self._path = path
        self.author = []
        self.description = ""
        self.end_user_data_statement = ""
        self.permissions = []
        self.short = ""
        self.min_bot_version = ""
        self.max_bot_version = ""
        self.min_python_version = ""
        self.hidden = False
        self.disabled = False
        self.required_cogs = {}
        self.requirements = []
        self.tags = []
        self.type = "" # Still a thing?
        self.rx_added_at = ""
        self.rx_last_updated_at = ""
        self._error = ""

    def check_cog_validity(self):
        if self._error:
            return

        initpath = self._path / Path("__init__.py")
        if not initpath.exists():
            self._error = "Info.json is present but no __init__.py was found. Invalid cog package."

    def get_info(self, repo_metadata):
        if self._error:
            return
        info_path = self._path / Path("info.json")

        try:
            with open(str(info_path)) as f:
                data = json.load(f)
        except:
            self._error = "Error reading cog info.json. Possibly invalid."
            return

        self.author = data.get("author", [])
        self.description = data.get("description", "")
        self.end_user_data_statement = data.get("end_user_data_statement", "")
        self.short = data.get("short", "")
        self.permissions = data.get("permissions", [])
        self.min_bot_version = data.get("min_bot_version", "")
        self.max_bot_version = data.get("max_bot_version", "")
        self.min_python_version = data.get("min_python_version", "")
        self.hidden = data.get("hidden", False)
        self.disabled = data.get("disabled", False)
        self.required_cogs = data.get("required_cogs", {})
        self.requirements = data.get("requirements", [])
        self.tags = data.get("tags", [])
        self.type = data.get("type", "")
        if self._name in repo_metadata.cogs:
            cog_metadata = repo_metadata.cogs[self._name]
            cog_metadata.update_from_path(self._path)
        else:
            cog_metadata = InternalCogMetadata.from_path(self._name, self._path)
            repo_metadata.cogs[self._name] = cog_metadata
        self.rx_added_at = cog_metadata.added_at.isoformat()
        self.rx_last_updated_at = cog_metadata.last_updated_at.isoformat()

    def __json__(self):
        return {k:v for (k, v) in self.__dict__.items() if not k.startswith("_") and not callable(k)}

class InternalRepoMetadata:
    def __init__(self, url, cogs=None):
        self.url = url
        self.cogs = cogs or {}

    @classmethod
    def from_dict(cls, url, data):
        cogs = {
            name: InternalCogMetadata.from_dict(name, cog_metadata)
            for name, cog_metadata in data["cogs"].items()
        }
        return cls(url, cogs)

    def __json__(self):
        return {
            "cogs": self.cogs,
        }

class InternalCogMetadata:
    _BUFFER_SIZE = 2**18
    _PREFERRED_ALGORITHMS = ("sha256",)

    def __init__(self, name, *, added_at, last_updated_at, deleted_at, hashes):
        self.name = name
        self.added_at = added_at
        self.last_updated_at = last_updated_at
        self.deleted_at = deleted_at
        self.hashes = hashes
        self._still_exists = False

    @classmethod
    def from_dict(cls, name, data):
        return cls(
            name=name,
            added_at=get_datetime(data["added_at"]),
            last_updated_at=get_datetime(data["last_updated_at"]),
            deleted_at=get_datetime(data["deleted_at"]),
            hashes=data["hashes"],
        )

    @classmethod
    def from_path(cls, name, path):
        obj = cls(
            name=name,
            added_at=NOW,
            last_updated_at=NOW,
            deleted_at=None,
            hashes=cls.get_file_hashes(path),
        )
        obj._still_exists = True
        return obj

    def __json__(self):
        return {
            "added_at": self.added_at.timestamp(),
            "last_updated_at": self.last_updated_at.timestamp(),
            "deleted_at": self.deleted_at and self.deleted_at.timestamp(),
            "hashes": self.hashes,
        }

    def update_from_path(self, path):
        self._still_exists = True
        self.deleted_at = None
        hashes = self.get_file_hashes(path)
        if not self.verify_hashes(hashes):
            self.last_updated_at = NOW

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

    def verify_hashes(self, hashes):
        for algorithm in self._PREFERRED_ALGORITHMS:
            try:
                a = self.hashes[algorithm]
                b = hashes[algorithm]
            except KeyError:
                continue
            else:
                return hmac.compare_digest(a, b)

        for algorithm in self.hashes.keys() & hashes.keys():
            try:
                a = self.hashes[algorithm]
                b = hashes[algorithm]
            except KeyError:
                continue
            else:
                return hmac.compare_digest(a, b)

        raise RuntimeError("No matching hashes were found.")

def get_datetime(timestamp: int = None):
    if timestamp is None:
        return None
    return datetime.datetime.fromtimestamp(timestamp).astimezone(datetime.timezone.utc)

def sha1_digest(url):
    return hashlib.sha1(url.encode('utf-8')).hexdigest()

def make_error_log(repos):
    log = {}

    for r in repos:
        if r._error:
            log[r._url] = r._error
            continue
        for c in r.rx_cogs:
            if not c._error:
                continue
            if r._url not in log:
                log[r._url] = {}
            log[r._url][c._name] = c._error

    if log:
        return yaml.safe_dump(log, sort_keys=True, default_flow_style=False)
    else:
        return ""

def main():
    yamlfile = sys.argv[1]

    with open(yamlfile) as f:
        data = yaml.safe_load(f.read())

    try:
        with open(METADATA_FILE, "r") as fp:
            raw_metadata = json.load(fp)
    except FileNotFoundError:
        metadata = {}
    else:
        metadata = {
            url: InternalRepoMetadata.from_dict(url, repo_metadata)
            for url, repo_metadata in raw_metadata.items()
        }
    repos = []

    for k in ("approved", "unapproved"):
        if data[k]: # Can be None if empty
            for url in data[k]:
                if url in metadata:
                    repo_metadata = metadata[url]
                else:
                    repo_metadata = InternalRepoMetadata(url)
                    metadata[url] = repo_metadata
                repos.append(Repo(repo_metadata, k))

    for r in repos:
        r.folder_check_and_get_info()
        r.populate_cogs()
        r.process_cogs()

    # Remove errored repos and cogs.
    error_log = make_error_log(repos)
    repos = [r for r in repos if not r._error]

    for r in repos:
        r.rx_cogs = [c for c in r.rx_cogs if not c._error]

    for repo_metadata in metadata.values():
        for cog_metadata in repo_metadata.cogs.values():
            if not cog_metadata._still_exists:
                cog_metadata.deleted_at = NOW

    with open(METADATA_FILE, "w") as fp:
        json.dump(metadata, fp, indent=4, sort_keys=True, cls=CustomEncoder)

    if data["flagged-cogs"]:
        for url, flagged_cogs in data["flagged-cogs"].items():
            for r in repos:
                # I'm doing this instead of comparing URLs in case of
                # slashes and such. Owner/Reponame is close enough.
                if r._owner_repo not in url:
                    continue
                to_remove = []
                for c in r.rx_cogs:
                    if c._name in flagged_cogs:
                        to_remove.append(c)
                if to_remove:
                    r.rx_cogs = [c for c in r.rx_cogs if c not in to_remove]

    if repos:
        # Final format URL : Repo...
        repos_index = {}

        for r in repos:
            cogs_dict = {}
            for c in r.rx_cogs:
                cogs_dict[c._name] = c

            # ... and CogName : Cog
            r.rx_cogs = cogs_dict
            repos_index[r._url] = r

        if not GEN_PATH.exists():
            GEN_PATH.mkdir()

        minified_str = json.dumps(repos_index, separators=(',', ':'), sort_keys=True, cls=CustomEncoder)

        # Minified json file
        with open(str(GEN_MIN_FILE), "w") as f:
            f.write(minified_str)

        # Gzipped minified json file
        with open(str(GEN_GZ_FILE), "wb") as f:
            gz = GzipFile(GEN_MIN_FILE.name, "wb", 9, f, 0.)
            gz.write(minified_str.encode())
            gz.close()

        # Pretty json file
        with open(str(GEN_FILE), "w") as f:
            json.dump(repos_index, f, indent=4, sort_keys=True, cls=CustomEncoder)

        # YAML error log
        with open(str(GEN_ERROR_LOG), "w") as f:
            f.write(error_log)


if __name__ == "__main__":
    main()
