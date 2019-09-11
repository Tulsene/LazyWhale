


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
# {
#         'input':{
#             'buy':[
#                 0
#             ],
#             'sell':[
#                 0,
#             ]
#         },
# },
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
{
        'input':{
            'buy':[
                0,
                1,
                2,
                3,
            ],
            'sell':[
                0,
                1,
                2,
                3,
            ]
        },
},

]




test_case_by_open_orders_number = [
    {
        'input':{
            'buy':[
                0,
            ],
            'sell':[]
        },
        'output_nb':{
            'buy_nb':4,
            'sell_nb':4
        }
},
{
        'input':{
            'buy':[],
            'sell':[
                0,
            ]
        },
        'output_nb':{
            'buy_nb':4,
            'sell_nb':4
        }
},
{
        'input':{
            'buy':[
                0,
            ],
            'sell':[
                0,
            ]
        },
        'output_nb':{
            'buy_nb':4,
            'sell_nb':4
        }
},
{
        'input':{
            'buy':[
                0,
                1,
                2,
                3,
            ],
            'sell':[
            ]
        },
        'output_nb':{
            'buy_nb':4,
            'sell_nb':4
        }
},
{
        'input':{
            'buy':[
            ],
            'sell':[
                0,
                1,
                2,
                3,
            ]
        },
        'output_nb':{
            'buy_nb':4,
            'sell_nb':4
        }
},
{
        'input':{
            'buy':[
                0,
                1,
                2,
                3,
            ],
            'sell':[
                0,
                1,
                2,
                3,
            ]
        },
        'output_nb':{
            'buy_nb':4,
            'sell_nb':4
        }
},
]





test_case_by_price_from_params = [
    {
        'input':{
            'buy':None,
            'sell':
                {'param': 'spread_top', 'type': 'more'}  # 'more','less','equal'
        },
        'output_nb':{
            'buy_nb':4,
            'sell_nb':4
        }
    },
    {
        'input':{
            'buy':{'param': 'spread_bot', 'type': 'less'},  # 'more','less','equal'
            'sell':None
        },
        'output_nb':{
            'buy_nb':4,
            'sell_nb':4
        }
    },
    {
        'input':{
            'buy':None,
            'sell':{'param': 'range_top', 'type': 'more'}  # 'more','less','equal'
        },
        'output_nb':{
            'buy_nb':4,
            'sell_nb':4
        }
    },
{
        'input':{
            'buy':{'param': 'range_bot', 'type': 'less'},  # 'more','less','equal'
            'sell':None
        },
        'output_nb':{
            'buy_nb':4,
            'sell_nb':4
        }
    },
]