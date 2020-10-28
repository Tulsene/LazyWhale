from main.lazy_whale import LazyWhale

if __name__ == "__main__":
    lw = LazyWhale()
    params = lw.ui.ask_for_params()  # f'{self.root_path}config/params.json'
    if isinstance(params, LazyWhale):
        lw = params
    else:
        lw.params = params
        lw.lw_initialisation()

    lw.main()
