from main.lazy_whale import LazyWhale
from config import config

if __name__ == "__main__":
    lw = LazyWhale()
    params = lw.ui.ask_for_params()  # f'{self.root_path}config/params.json'
    if isinstance(params, LazyWhale):
        config.PRICE_RANDOM_PRECISION = params.params["price_random_precision"]
        config.AMOUNT_RANDOM_PRECISION = params.params["amount_random_precision"]
        lw = params
    else:
        lw.params = params
        lw.lw_initialisation()

    lw.main()
