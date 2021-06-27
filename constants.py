from pathlib import Path

CACHE = Path("cache")
GEN_PATH = Path("index")
RX_PROTOCOL = 1 # This should be incremented when breaking changes to the format are implemented
GEN_ERROR_LOG = GEN_PATH / Path(f"{RX_PROTOCOL}-errors.yaml") # Error log
GEN_FILE = GEN_PATH / Path(f"{RX_PROTOCOL}.json") # Pretty, for QA checking
GEN_MIN_FILE = GEN_PATH / Path(f"{RX_PROTOCOL}-min.json") # Minified, for user download
GEN_GZ_FILE = GEN_PATH / Path(f"{RX_PROTOCOL}-min.json.gz") # Gzipped