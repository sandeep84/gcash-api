import piecash

def populateAccountChildrenRecords(account, rootCurrency):
    account_entry = {
        "guid": account.guid,
        "name": account.name,
        "currency": account.commodity.mnemonic,
        "balance": 0.0,
        "balanceGBP": 0.0,
        "numChildren": len(account.children),
        "children": list()
    }

    for child in account.children:
        child_entry = {
            "guid": child.guid,
            "name": child.name,
            "numChildren": len(child.children),
        }

        try:
            child_entry['balance'] = float(child.get_balance(recurse=True))
            child_entry['currency'] = child.commodity.mnemonic
            child_entry['balanceGBP'] = float(child.get_balance(recurse=True, commodity=rootCurrency))
        except Exception as e:
            child_entry['balance'] = 0.0
            child_entry['currency'] = "N/A"
            child_entry['balanceGBP'] = 0.0
            print(e)

        account_entry['children'].append(child_entry)

    return account_entry

def getAccounts(account_url):
    book = piecash.open_book(uri_conn=account_url, readonly=True)
    root = book.root_account
    rootCurrency = book.currencies[0]
    accounts = populateAccountChildrenRecords(root, rootCurrency)
    book.close()
    return accounts

def getAccount(account_url, **kwargs):
    book = piecash.open_book(uri_conn=account_url, readonly=True)
    root = book.root_account
    rootCurrency = book.currencies[0]
    account = populateAccountChildrenRecords(book.get(piecash.Account, **kwargs), rootCurrency)
    book.close()
    return account

def shutdown():
    pass

if __name__ == "__main__":
    print(getAccounts())
    shutdown()
