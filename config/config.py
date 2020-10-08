from decimal import Decimal


# Concervative value, need to be modified when it's more than 0.25% of fees
FEES_COEFFICIENT = Decimal('0.9975')

# Change those value if you want to launch several instance on the same market
SAFETY_BUY_VALUE = Decimal('1E-8')
SAFETY_SELL_VALUE = Decimal('1')
DECIMAL_PRECISION = 8

# Use Decimal('0.001') or near for deploy purpose, but Decimal('1E-5') for testing
MIN_VALUE_ORDER = Decimal('0.00001')
