# LazyWhale trading assistant

Easy tool for lazy whale

## Instalation for linux
### Prerequisite

Have python 2.7 installed

git clone https://github.com/Tulsene/LazyWhale
cd LazyWhale
git checkout dev
python Lazy.py

### Configuration

Proposal for handling API Keys in ENV_VARS
Exemple usage on windows (on a .bat file)

```
SET API_KEY="7JDLBZMI-HPWMRUVZ-D968SXSP-RJ92NSQK"&& SET API_SECRET="f745921a6e73eef13b9f72a4ab05f0a77a311f4cfa40a5b968e0ce3229626471cf4b832627791eb1c5e4352e7770dbd684d75d78f2acf3aa8fdb9ed21b63119"&& python Lazy.py
```

Equivalent for Debian (in a .sh for exemple)

```
#!/bin/sh
export API_KEY=7JDLBZMI-HPWMRUVZ-D968SXSP-RJ92NSQK
export API_SECRET=f745921a6e73eef13b9f72a4ab05f0a77a311f4cfa40a5b968e0ce3229626471cf4b832627791eb1c5e4352e7770dbd684d75d78f2acf3aa8fdb9ed21b63119
python Lazy.py
```

In the file Lazy.py setup setup globals variables for your strategy

### Read logs

tail -f Lazy.log

## What is it?

LW is a simple script for poloniex marketplace wich do market making in a preset range. 

You choose your trading pair then setup buy & sell pair too.

amount = the amount of sell pair wich will be used every times

increment = price between 2 order of the same type

buy_price_min & sell_price_max = the trading range for the script

buy_price_max & sell_price_min = your spread between your buy & sell orders

nb_orders_to_display = number of orders displayed in each side of the order book

remove_orders_during_init = if you want to remove all of your order in the order book during initialisation

stop_at_bottom, stop_at_top = if you want to stop the script and remove all orders as soon as it hit buy_price_min or sell_price_max

don_t_touch : as it called

### Connard proof implem :

Now LW don't care of any order you can add. If you manually remove an order of LW, it will consider as executed and will put the opposite.
