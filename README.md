# LazyWhale trading assistant

Easy tool for lazy whale

## Instalation for linux
### Prerequisite
#### Python >= 3.6
https://solarianprogrammer.com/2017/06/30/building-python-ubuntu-wsl-debian/

Configure it with pip : `./configure --enable-optimizations --with-ensurepip=install` !!!

**You must have python >= 3.6 or you will get the following error:**

```
File "LazyStarter.py", line 183
    return Decimal(f"{self.exchange.fetchTicker(market)['last']:.8f}")
                                                                    ^
SyntaxError: invalid syntax
```

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

`git checkout dev`

### API Keys Configuration

Create key.txt and follow the scheme in `keySkeletton.txt`

### Run LW

**Your virtualenv need to be properly setup and running!**

`python LazyStarter.py` 

### Read logs

`tail -f Lazy.log`

## What is it?

LW is a simple script compatible with ccxt marketplaces wich do a simple market making in a preset range. 

Follow the instructions to setup your parameters.
 