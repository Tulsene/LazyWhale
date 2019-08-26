


def singleton(cls):
    instances = {}

    def getinstance():
        if cls not in instances:
            instances[cls] = cls()
        return instances[cls]

    return getinstance
    # _instance = None
    #
    # def __new__(cls, *args, **kwargs):
    #     if not cls._instance:
    #         cls._instance = super(BotConfiguration, cls).__new__(cls, *args, **kwargs)
    #     return cls._instance
