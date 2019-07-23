# LazyWhale trading assistant

This is a dangerous tools in bad tradings hands. Anyway, **use it at your own risks**!

The purpose of this script is to automate sells & buys during range or bullish movement.

LW is a simple script compatible with ccxt marketplaces wich simply buy and sell in a preset range. 

## Instalation for linux
### Prerequisite
#### Python >= 3.6 

For debian and other debian like linux versions:
`https://solarianprogrammer.com/2017/06/30/building-python-ubuntu-wsl-debian/`

Configure it with pip : `./configure --enable-optimizations --with-ensurepip=install` !!!

**You must have python >= 3.6 or you will get the following error:**

```
File "LazyStarter.py", line XXXX
    xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
                                                                    ^
SyntaxError: invalid syntax
```

For other OS do a PR if you want it!

#### Virtual Env

`pip install --user virtualenv`

`cd ~/Path/to/repository`

`virtualenv venv -p python3.6` or 3.7

`source /path/to/ENV/bin/activate` (only `deactivate` is required to close it, `rm -r /path/to/ENV` do telete it)

`pip install -r requirements.txt`

`https://virtualenv.pypa.io/en/latest/reference/` for a list of commands

#### Download the LW

`git clone https://github.com/Tulsene/LazyWhale`

`cd LazyWhale`

### API Keys Configuration

Create key.txt and follow the scheme in `keySkeletton.txt`

### Strategy parameters

Are in params.txt file and are not kept forever. Backup it before entering new parameters!

### Run LW

**Your virtualenv need to be properly setup and running!**

`python LazyStarter.py` 


## TODO
- [ ] Send slack message.
- [ ] Improve marketplace selection by adding it into params.
- [ ] Organize this mess!

### If you want to help

Open an issue on github or do a pull request on the dev branch