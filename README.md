# LazyWhale trading assistant

Easy tool for lazy whale

## Instalation for linux
### Prerequisite
#### Python 3.7
https://solarianprogrammer.com/2017/06/30/building-python-ubuntu-wsl-debian/

Configure it with pip : `./configure --enable-optimizations --with-ensurepip=install` !!!

Have python >= 3.6 installed

**You must have the good version of pytohn or you will get the following error:**

```  File "LazyStarter.py", line 183
    return Decimal(f"{self.exchange.fetchTicker(market)['last']:.8f}")
                                                                    ^
SyntaxError: invalid syntax```

#### Virtual Env

`pip install --user virtualenv`

`cd ~/Path/to/repository`

`virtualenv venv -p python3.7`

`source /path/to/ENV/bin/activate` (only `deactivate` is required to close it, `rm -r /path/to/ENV` do telete it)

`pip install -r requirements.txt`

`https://virtualenv.pypa.io/en/latest/reference/` for a list of commands

#### Download the LW

git clone https://github.com/Tulsene/LazyWhale
cd LazyWhale
git checkout dev

#### Add CCXT

`pip install ccxt`

CCXT must be modified for each marketplace you use : `virutal_env/lib/python*version*/site-package/ccxt`

Modify `def parse_ticker(self, ticker, market=None):` the name of last ticker key to `last`. e.g : last = self.safe_float(ticker, 'last')

### API Keys Configuration

Create key.txt and follow the scheme in keySkeletton.txt

### Run LW

### Read logs

tail -f Lazy.log

## What is it?

LW is a simple script compatible with ccxt marketplaces wich do a simple market making in a preset range. 

Follow the instructions to setup your parameters.

### TODO

requirements.txt -> ccxt==1.18.385
 