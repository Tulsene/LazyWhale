# LazyWhale trading assistant

- This is a dangerous tools in bad tradings hands. This script is publicly provided without any guarantees, **use it at your own risks**!

- The purpose of this script is to automate sells & buys during range or bullish movement.

- LW is a simple script compatible with ccxt marketplaces, as of now only bittrex and zebitex have been tested.

## Installation for linux
### Prerequisite
#### Python >= 3.6 

**For debian and other debian like linux versions:**
- <https://solarianprogrammer.com/2017/06/30/building-python-ubuntu-wsl-debian/>

- Configure it with pip : `./configure --enable-optimizations --with-ensurepip=install` !!!

**For Windows:**
- Install python >= 3.6 with pip >= 20.0
- Add python to PATH during installation or manually

**You must have python >= 3.6 or you will get the following error:**

```
File "LazyStarter.py", line XXXX
    xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
                                                                    ^
SyntaxError: invalid syntax
```

#### Download the script

- `git clone https://github.com/Tulsene/LazyWhale`

- `cd LazyWhale`

#### Virtual Env

- `pip install --user virtualenv`

- `cd ~/Path/to/repository`

Debian like linux system:
- `virtualenv venv -p python3.X`

- `source /venv/bin/activate` (`deactivate`  to close it, `rm -r /path/to/ENV` to delete it)

- `pip install -r requirements.txt`

Windows:
- `python -m venv venv`

- `venv\Scripts\activate`

- `pip install -r requirements.txt`

Navigate to <https://virtualenv.pypa.io/en/latest/reference/> for a list of commands


## API Keys Configuration

- Create keys.json and follow the scheme in [keySkeletton.json](config/keysSkeletton.json)

## Strategy parameters

- Follow the instruction provided by the script. Please open an issue if you need help or have any suggestion.

- Parameters are stored in `params.json`, backup it before entering new parameters!

## Run LW

- **Your virtualenv need to be properly setup and running!**

- `python main.py` 


## Tests
**There are 2 kind of tests: unit and functional.
Functional main user (LazyWhale or LW) account and second user account (ANOTHER_USER) to check the correctness of 
LW algorithms**

**Disclaimer**: In tests we don't check, if you have enough funds to run them.

*\*keep in mind that tests run ~40 minutes (depends on your internet connection)**
### Running tests:


- Navigate to project root: `cd $project_root` (where $project_root is your project directory)
- Create `keys.py` file following the [keys.py.sample](tests/keys.py.sample) with adding 
- Check manually if you have enough funds to run tests.
- run: `python -m unittest discover tests`


## Project codestyle:
We use Black PyPI as the main project code formatter:
- `python -m black .` - to format all `.py` files
- `python -m black $directory` - to format specific directory
- see <https://pypi.org/project/black/> for the full information


## TODO
- [x] keep orders amount list on a file & allow to restart with it
- [x] Unit tests
- [x] Functional tests
- [x] Switch from lists to classes and dicts
- [x] Open opposite orders even when an order is not yet fulfilled 

### If you want to help

Open an issue on github or do a pull request on the dev branch