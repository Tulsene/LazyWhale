


test_case_by_open_orders_ids = [
#     {
#         'input':{
#             'buy':[
#                 0,  #order book index
#             ],
#             'sell':[]
#         },
# },
#     {
#         'input':{
#             'buy':[
#             ],
#             'sell':[
#                 0,
#             ]
#         },
# },
{
        'input':{
            'buy':[
                0
            ],
            'sell':[
                0,
            ]
        },
},
# {
#         'input':{
#             'buy':[
#             ],
#             'sell':[
#                 0,
#                 1,
#                 2,
#                 3,
#             ]
#         },
# },
# {
#         'input':{
#             'sell':[
#             ],
#             'buy':[
#                 0,
#                 1,
#                 2,
#                 3,
#             ]
#         },
# },
]




test_case_by_open_orders_number = [
    {
        'input':{
            'buy':{
                0:{'order_book_index':0, 'amount_percent':1}
            },
            'sell':{}
        },
        'output_nb':{
            'buy_nb':5,
            'sell_nb':5
        }
},
{
        'input':{
            'buy':{},
            'sell':{
                0: {'order_book_index': 0, 'amount_percent': 1}
            }
        },
        'output_nb':{
            'buy_nb':5,
            'sell_nb':5
        }
},
{
        'input':{
            'buy':{
                0:{'order_book_index':0, 'amount_percent':1}
            },
            'sell':{
                0: {'order_book_index': 0, 'amount_percent': 1}
            }
        },
        'output_nb':{
            'buy_nb':5,
            'sell_nb':5
        }
},
{
        'input':{
            'buy':{
                0:{'order_book_index':0, 'amount_percent':1},
                1:{'order_book_index': 0, 'amount_percent':1},
                2:{'order_book_index': 0, 'amount_percent':1},
                3:{'order_book_index':0, 'amount_percent':1},
            },
            'sell':{
            }
        },
        'output_nb':{
            'buy_nb':5,
            'sell_nb':5
        }
},
{
        'input':{
            'buy':{
            },
            'sell':{
                0: {'order_book_index': 0, 'amount_percent': 1},
                1: {'order_book_index': 0, 'amount_percent': 1},
                2: {'order_book_index': 0, 'amount_percent': 1},
                3: {'order_book_index': 0, 'amount_percent': 1},
            }
        },
        'output_nb':{
            'buy_nb':5,
            'sell_nb':5
        }
},
]
