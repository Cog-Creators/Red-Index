import json
import yaml
import re
import sys
from gzip import GzipFile
from pathlib import Path
from hashlib import sha1

CACHE = Path("cache")

RX_PROTOCOL = 1 # This should be incremented when breaking changes to the format are implemented
GEN_PATH = Path("index")
GEN_FILE = GEN_PATH / Path(f"{RX_PROTOCOL}.json") # Pretty, for QA checking
GEN_MIN_FILE = GEN_PATH / Path(f"{RX_PROTOCOL}-min.json") # Minified, for user download
GEN_GZ_FILE = GEN_PATH / Path(f"{RX_PROTOCOL}-min.json.gz") # Gzipped
GEN_ERROR_LOG = GEN_PATH / Path(f"{RX_PROTOCOL}-errors.yaml") # Error log


class CustomEncoder(json.JSONEncoder):
    def default(self, obj):
        if hasattr(obj, "__json__"):
            return obj.__json__()
        else:
            return json.JSONEncoder.default(self, obj)

class Repo:
    def __init__(self, url: str, category: str):
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
        self._url = url
        self.name = ""
        self.rx_branch = ""
        try:
            self.parse_name_branch_url(url)
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
            cog.get_info()
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
        self._error = ""

    def check_cog_validity(self):
        if self._error:
            return

        initpath = self._path / Path("__init__.py")
        if not initpath.exists():
            self._error = "Info.json is present but no __init__.py was found. Invalid cog package."

    def get_info(self):
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

    def __json__(self):
        return {k:v for (k, v) in self.__dict__.items() if not k.startswith("_") and not callable(k)}

def sha1_digest(url):
    return sha1(url.encode('utf-8')).hexdigest()

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

    repos = []

    for k in ("approved", "unapproved"):
        if data[k]: # Can be None if empty
            for url in data[k]:
                repos.append(Repo(url, k))

    for r in repos:
        r.folder_check_and_get_info()
        r.populate_cogs()
        r.process_cogs()

    # Remove errored repos and cogs.
    error_log = make_error_log(repos)
    repos = [r for r in repos if not r._error]

    for r in repos:
        r.rx_cogs = [c for c in r.rx_cogs if not c._error]

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
