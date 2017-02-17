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

In the File apiInterface put your API key & secret for poloniex

In the file Lazy.py setup setup globals variables for your strategy

## What is it?

LW is a simple script for poloniex marketplace wich do market making in a preset range. 

You choose your trading pair then setup buy & sell pair too.

amount = the amount of sell pair wich will be used every times

increment = price between 2 order of the same type

buy_price_min & sell_price_max = the trading range for the script

buy_price_max & sell_price_min = your spread between your buy & sell orders

nb_orders_to_display = number of orders displayed in each side of the order book


