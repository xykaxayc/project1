import os

BASE_PATH = os.path.join(os.path.dirname(__file__), 'payment_messages')

def _read_message(filename):
    with open(os.path.join(BASE_PATH, filename), encoding='utf-8') as f:
        return f.read()

NO_ACCOUNTS = _read_message('no_accounts.txt')
SELECT_ACCOUNT = _read_message('select_account.txt')
PAYMENT_PLANS_TITLE = _read_message('payment_plans_title.txt')
PAYMENT_PLANS_FOR_ACCOUNT = _read_message('payment_plans_for_account.txt')
PAYMENT_DETAILS = _read_message('payment_details.txt')
PAYMENT_REQUEST_CREATED = _read_message('payment_request_created.txt')

# ... add other payment-related messages here
