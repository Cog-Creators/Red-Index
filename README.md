# Red-Index
Auto-indexer of repositories and cogs for [Red Discord bot](https://github.com/Cog-Creators/Red-DiscordBot/).  
Scheduled to run every 15 minutes and provide an up-to-date [index list](https://github.com/Cog-Creators/Red-Index/tree/master/index) of every repo listed in [repositories.yaml](repositories.yaml)  
See [repositories-example.yaml](repositories-example.yaml) to learn how to compile it  

## FAQ
### What services are using this?
[https://index.discord.red/](https://index.discord.red/), web interface for Red-Index  
[Index](https://github.com/Twentysix26/x26-Cogs/tree/master/index), cog to search Red-Index and easily install repos / cogs directly from your Red instance (NOTE: **QA approval pending!**)  

Made a service that uses Red-Index as a source? [Make a PR](https://github.com/Cog-Creators/Red-Index/pulls) and we'll add it here!

### Can I use this as a source for my project and provide a new service to browse repos / cogs?
Yes! This is exactly the point of this project. Fetch the [minified version](https://raw.githubusercontent.com/Cog-Creators/Red-Index/master/index/1-min.json) from whatever website / service you're building and parse it. In case of substantial changes to the data format we'll increase the version number and the link will change.

### Can I add my repo to the list?
Yes! You can create a [Cog Creator application](https://cogboard.red/c/apps/12) to become a Cog Creator and have your repo added to the approved category (along with a few other perks). If you're still waiting for your application to be reviewed or you're not quite ready to apply, you can [make a PR](https://github.com/Cog-Creators/Red-Index/pulls) to have your repo potentially added to the unapproved category.

### How does this work?
[Github Actions](https://github.com/features/actions) are what makes this possible. Every 15 minutes, or on manual trigger, the workflow takes care of parsing the repositories list, cloning each one of them and compiling a [JSON file](https://github.com/Cog-Creators/Red-Index/tree/master/index) with all the current metadata of each repository and repo.

### I want to run my own Red-Index. Is it possible?
Sure. Fork this project, edit the repositories list, enable the actions and it will be good to go.
