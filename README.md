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

## TODO
- [ ] Add Fees coef in params
- [ ] add market depth (actually limited to BTC markets)
- [ ] Send email
- [x] Use f'' to format strings

## TOTEST
- [ ] logger_setup
- [ ] self.stratlog
- [ ] self.applog
- [ ] select_marketplace
- [ ] select_market
- [ ] ask_for_logfile
- [ ] log_file_reader
- [ ] params_checker
- [ ] dict_to_str
- [ ] check_for_enough_funds
- [ ] buy funds
- [ ] not enough
- [ ] Check maths when the whole strategy is under actual price
- [ ] look for moar funds
- [ ] sell funds
- [ ] not enough
- [ ] look for moar funds
- [ ] display_user_trades
- [ ] strat_init
- [ ] remove open orders outside the strategy
- [ ] Create lists with all remaining orders price
- [ ] set_first_orders
- [ ] Open an order if needed or move an already existing order
- [ ] remove_safety_order
- [ ] set_safety_orders
- [ ] remove_orders_off_strat
- [ ] check_if_no_orders
- [ ] Create a fake buy order if needed or stop LW
- [ ] Create orders
- [ ] Create a fake sell order if needed or stop LW
- [ ] Create orders
- [ ] compare_orders
- [ ] Buys
- [ ] set_several_buy maths
- [ ] Sells
- [ ] update_open_orders
- [ ] limit_nb_orders
- [ ] When there is too much buy orders on the order book
- [ ] When there is not enough buy order in the order book
- [ ] When there is too much sell orders on the order book
- [ ] When there is not enough sell order in the order book