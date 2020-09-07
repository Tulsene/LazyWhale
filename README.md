# LazyWhale trading assistant

This is a dangerous tools in bad tradings hands. This script is publicly provided without any garantees, **use it at your own risks**!

The purpose of this script is to automate sells & buys during range or bullish movement.

LW is a simple script compatible with ccxt marketplaces, as of now only bittrex and zebitex have been tested.

**Disclaimer** : extensive tests have been made by hand. There is no unit tests or functional tests.

## Installation for linux
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

#### Download the script

`git clone https://github.com/Tulsene/LazyWhale`

`cd LazyWhale`

#### Virtual Env

`pip install --user virtualenv`

`cd ~/Path/to/repository`

`virtualenv venv -p python3.X`

`source /venv/bin/activate` (`deactivate`  to close it, `rm -r /path/to/ENV` to delete it)

`pip install -r requirements.txt`

`https://virtualenv.pypa.io/en/latest/reference/` for a list of commands


## API Keys Configuration

Create keys.json and follow the scheme in `keySkeletton.json`

## Strategy parameters

Follow the instruction provided by the script. Please open an issue if you need help or have any suggestion.

Parameters are stored in params.txt, backup it before entering new parameters!

## Run LW

**Your virtualenv need to be properly setup and running!**

`python main.py` 


## TODO
- [ ] keep orders amount list on a file & allow to restart with it
- [ ] Unit tests
- [ ] Functionnal tests
- [ ] Switch from lists to pandas
- [ ] Open opposite orders even when an order is not yet fulfilled 

### If you want to help

Open an issue on github or do a pull request on the dev branch