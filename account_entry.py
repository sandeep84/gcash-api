"""
Simple class to represent a single account entry
"""

class AccountEntry:
    fields = {
        'type': ['debitCreditCode'],
        'date': ['date', 'Date', 'Transaction Date', 'Completed Date', 'TrDate', 'TRADE_DATE', 'TransactionDate'],
        'account': [],
        'amount': ['Value'],
        'units': ['No of units', 'Units', 'UNITS'],
        'price': ['Price', 'NAV', 'PRICE'],
        'cleared': [],
        'num': [],
        'payee': ['description', 'Description', 'TrDesc', 'Transaction Remarks', 'Remarks', 'Transaction Type', 'Details', 'TRANSACTION_TYPE'],
        'memo': [],
        'address': [],
        'category': [],
        'split_category': ['SCHEME_NAME'],
        'split_memo': [],
        'split_amount': [],
        'withdrawal': ['Withdrawals', 'Withdrawal Amount (INR )', 'amount', 'Amount(GBP)', 'Amount', 'Paid Out (GBP)', 'What\'s gone out', 'AMOUNT'],
        'deposit': ['Deposits', 'Deposit Amount (INR )', 'Paid In (GBP)', 'What\'s gone in'],
    }

    def __init__(self):
        for field in AccountEntry.fields:
            self.__setattr__(field, None)

    def as_tuple(self):
        return tuple([self.__dict__[field] for field in AccountEntry.fields])

    def __str__(self):
        tmpstring = []
        for field in AccountEntry.fields:
            if self.__getattribute__(field) is not None:
                tmpstring.append(f'{field}: {self.__getattribute__(field)}')
        return ', '.join(tmpstring)



