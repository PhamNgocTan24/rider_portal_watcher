"""
Centralised selector definitions for the fake ride portal.

Each entry is a list of fallback selectors tried in order.
Priority: data-testid > ARIA role > stable class > XPath (last resort).
"""

# ---------------------------------------------------------------------------
# Login page
# ---------------------------------------------------------------------------
LOGIN_USERNAME_INPUT = [
    '[data-testid="input-username"]',
    '#username',
    'input[name="username"]',
]

LOGIN_PASSWORD_INPUT = [
    '[data-testid="input-password"]',
    '#password',
    'input[name="password"]',
]

LOGIN_SUBMIT_BUTTON = [
    '[data-testid="btn-login"]',
    'button[type="submit"]',
    '.btn-primary',
]

# ---------------------------------------------------------------------------
# Rides list page
# ---------------------------------------------------------------------------
BOOKING_CARD = [
    '[data-testid="booking-card"]',
    'article.ride-request-card',
    '.booking-card',
    '.job-row',          # Layout B fallback
]

BOOKING_ID_IN_CARD = [
    '[data-testid="booking-id"]',
    '.booking-id',
    '.job-id',           # Layout B fallback
]

# ---------------------------------------------------------------------------
# Ride detail page
# ---------------------------------------------------------------------------
DETAIL_BOOKING_ID = [
    '[data-testid="booking-id"]',
    '.booking-id',
    '.detail-id',        # Layout B fallback
]

DETAIL_PICKUP = [
    '[data-testid="pickup-location"]',
    '.detail-row .value:first-of-type',
    '.detail-pickup',    # Layout B fallback
]

DETAIL_DROPOFF = [
    '[data-testid="dropoff-location"]',
    '.detail-dropoff',   # Layout B fallback
]

DETAIL_VALUE = [
    '[data-testid="booking-value"]',
    '.detail-value',     # Layout B fallback
]

DETAIL_VEHICLE = [
    '[data-testid="vehicle-category"]',
    '.detail-vehicle',   # Layout B fallback
]

DETAIL_CUSTOMER = [
    '[data-testid="customer-category"]',
    '.detail-customer',  # Layout B fallback
]

DETAIL_PICKUP_TIME = [
    '[data-testid="pickup-time"]',
    '.detail-time',      # Layout B fallback
]

DETAIL_ACCEPT_BUTTON = [
    '[data-testid="btn-accept"]',
    'button.btn-accept',
    '.accept-btn',       # Layout B fallback
]
