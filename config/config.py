from decimal import Decimal


# Conservative value, need to be modified when it's more than 0.25% of fees
FEES_COEFFICIENT = Decimal("0.9975")

# Change those value if you want to launch several instance on the same market
SAFETY_BUY_VALUE = Decimal("1E-8")
SAFETY_SELL_VALUE = Decimal("1")
DECIMAL_PRECISION = Decimal("1E-8")

# may be changed during runtime
PRICE_RANDOM_PRECISION = Decimal("1E-8")
AMOUNT_RANDOM_PRECISION = Decimal("1E-8")

# Use Decimal('0.0001') or near for deploy purpose, but Decimal('1E-5') for testing
MIN_VALUE_ORDER = Decimal("0.00001")

# to calculate max_amount for linear/curved allocation
MAX_AMOUNT_COEFFICIENT = Decimal("2")

# to calculate lowest, middle and highest amount for linear/curved allocation
LOWEST_AMOUNT_COEFFICIENT = Decimal("1")
MIDDLE_AMOUNT_COEFFICIENT = Decimal("0.8")
HIGHEST_AMOUNT_COEFFICIENT = Decimal("1.2")

LW_CYCLE_SLEEP_TIME = 5  # seconds
