from time import time
from copy import deepcopy
from decimal import Decimal, ROUND_HALF_EVEN
from datetime import datetime


def str_to_decimal(value, error_message=None):
    """Convert a string to Decimal or raise an error.
    s: string, element to convert
    error_message: string, error message detail to display if fail.
    return: Decimal."""
    try:
        return Decimal(str(value).replace(",", "."))
    except Exception as e:
        raise ValueError(f"{error_message} {e}")


def str_to_datetime(str_date):
    """Convert a date in string format to a datetime format.
    str_date: string.
    return: datetime object.
    """
    try:
        return datetime.strptime(str_date, "%Y-%m-%d %H:%M:%S.%f")
    except Exception as e:
        raise ValueError(f"{str_date} is not a valid date: {e}")


def datetime_to_string(dt):
    """dt: datetime object.
    return: string."""
    return dt.strftime("%m/%d/%Y, %H:%M:%S")


def str_to_bool(s, error_message=None):
    """Convert a string to boolean or rise an error
    s: string.
    error_message: string, error message detail to display if fail.
    return: bool.
    """
    s = s.lower()
    if s in ["true", "y", "yes", "o", "oui", "j", "ja"]:
        return True
    elif s in ["false", "n", "no", "nein"]:
        return False
    else:
        raise ValueError(f"{error_message} {s}")


def str_to_int(s, error_message=None):
    """Convert a string to an int or rise an error.
    s: string.
    error_message: string, error message detail to display if fail.
    return: int.
    """
    try:
        return int(s)
    except Exception as e:
        raise ValueError(f"{error_message} {e}")


def dict_to_str(a_dict):
    """Format dict into a string.
    return: string, formated string for logfile."""
    b_dict = deepcopy(a_dict)
    for key, value in b_dict.items():
        b_dict[key] = str(value)
    b_dict = str(b_dict)
    return b_dict.replace("'", '"')


def timestamp_formater():
    """Format time.time() into the same format as timestamp.
    used in ccxt: 13 numbers.
    return: string, formated timestamp"""
    timestamp = str(time()).split(".")
    return int(f"{timestamp[0]}{timestamp[1][:3]}")


def multiplier(nb1, nb2, nb3=Decimal("1")):
    """Do a simple multiplication between Decimal.
    nb1: Decimal.
    nb2: Decimal.
    nb3: Decimal, optional.
    return: Decimal.
    """
    return quantizator(nb1 * nb2 * nb3)


def int_multiplier(nb1, nb2, nb3=1):
    return int(nb1) * int(nb2) * int(nb3)


def divider(nb1, nb2):
    """Simple divider."""
    return quantizator(nb1 / nb2)


def quantizator(nb):
    """Format a Decimal object to 8 decimals
    return: Decimal"""
    try:
        if nb < Decimal("1"):
            return nb.quantize(Decimal("1E-8"), rounding=ROUND_HALF_EVEN)
        else:
            whole_part, fractional_part = str(nb).split(".")
            return Decimal(whole_part) + Decimal(f"0.{fractional_part}").quantize(
                Decimal("1E-8"), rounding=ROUND_HALF_EVEN
            )

    except Exception as e:
        if Decimal(str(int(nb))) == nb:
            return nb
        raise SystemExit(f"Quantizator error: {e}, nb: {nb}")
