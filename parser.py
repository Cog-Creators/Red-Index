import yaml
import sys

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
        if "@" in r:
            repo, branch = r.split("@")
            branch = branch.replace("/", "") # In case of leading /
            sh += f"git clone {repo} --branch {branch} --single-branch\n"
        else:
            sh += f"git clone {r}\n"

    with open(outfile, "w") as f:
        f.write(sh)
