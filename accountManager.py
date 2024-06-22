import argparse
import datetime
import logging
import re
from qif_parser import QIFParser
from data_table_parser import XLSParser, XLSXParser, HTMLParser, CSVParser, JSONParser

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

def getAccountRecords(account_url):
    book = piecash.open_book(uri_conn=account_url, readonly=True)
    root = book.root_account
    rootCurrency = book.currencies[0]
    accounts = populateAccountChildrenRecords(root, rootCurrency)
    book.close()
    return accounts

def getAccountRecord(account_url, **kwargs):
    book = piecash.open_book(uri_conn=account_url, readonly=True)
    root = book.root_account
    rootCurrency = book.currencies[0]
    account = populateAccountChildrenRecords(book.get(piecash.Account, **kwargs), rootCurrency)
    book.close()
    return account

def shutdown():
    pass

def readRules(filename):
    '''Read the rules file.
    Populate an list with results. The list contents are:
    ([pattern], [account name]), ([pattern], [account name]) ...
    Note, this is in reverse order from the file.
    '''
    rules = []

    if filename is not None:
        with open(filename, 'r') as fd:
            for line in fd:
                line = line.strip()
                if line and not line.startswith('#'):
                    result = re.match(r"^(.+);(.+)", line)
                    if result:
                        ac = result.group(1)
                        pattern = result.group(2)
                        compiled = re.compile(pattern)  # Makesure RE is OK
                        rules.append((compiled, ac))
                    else:
                        logging.warn('Ignoring line: (incorrect format): "%s"', line)

    return rules

def importFile(fn, default_account_name):
    logging.debug('Reading %s..', fn)
    if fn.endswith('.xlsx'):
        dt_parser = XLSXParser(fn)
    if fn.endswith('.xls'):
        dt_parser = XLSParser(fn)
    elif fn.endswith('.csv'):
        dt_parser = CSVParser(fn)
    elif fn.endswith('.json'):
        dt_parser = JSONParser(fn)
    elif fn.endswith('.qif'):
         dt_parser = QIFParser(fn)
    elif fn.endswith('.html') or fn.endswith('.htm'):
        dt_parser = HTMLParser(fn)

    items = dt_parser.get_entries()

    for item in items:
        if item.account is None:
            item.account = default_account_name
        if item.split_amount is None:
            item.split_amount = item.amount

    logging.debug('Read %s items from %s', len(items), fn)
    return items

def lookupAccountByName(search_str, rules, book=None, split_account=None):
    for pattern, acpath in rules:
        if pattern.search(search_str):
            return acpath

    return None

def getCurrency(account):
    p = account
    while p.commodity.namespace != 'CURRENCY':
        p = p.parent
    
    return  p.commodity

def getAccount(item, book, default_account):
    account = None

    if book is not None:
        try:
            account = book.accounts(fullname=item.split_category)
        except:
            try:
                account = book.accounts(name=item.split_category)
            except:
                pass

    if account is None:
        # The Imbalance account is returned if we can't find the requested account
        account = book.accounts(name="Imbalance-" + getCurrency(default_account).mnemonic)

    return account

def addTransaction(book, default_account, item, currency, rules, dry_run):
    if item.split_category is None:
        item.split_category = lookupAccountByName(item.payee, rules, book, item.account)
    if item.split_category == "IGNORE":
        logging.debug('Skipping entry %s (%s) : %s', item.date.strftime('%Y-%m-%d'), item.split_amount, str(item))
        return

    acc2 = getAccount(item, book, default_account)
    amount = item.split_amount
    today = datetime.datetime.now()

    for split in default_account.splits:
        if split.transaction.description == item.payee and split.transaction.post_date == item.date.date() and split.value == amount:
            logging.debug("    - Skipping since transaction aready exists...")
            return

    logging.info('Adding %s', str(item))

    if not dry_run:
        default_account_split = piecash.Split(account=default_account, value=amount)
        if item.units is not None:
            default_account_split.quantity = item.units

        acc2_split = piecash.Split(account=acc2, value=-amount)
        tx = piecash.Transaction(
                post_date=item.date.date(),
                enter_date=today,
                currency=getCurrency(default_account),
                description = item.payee,
                splits = [default_account_split, acc2_split],
        )

def writeTransactions(account_url, currency, all_items, default_account_name, rules, dry_run=False):
    logging.debug('Opening GnuCash URL %s..', account_url)
    book = piecash.open_book(uri_conn=account_url, readonly=False, do_backup=False)
    default_account = book.accounts(fullname=default_account_name)
    currency = book.currencies(mnemonic=currency)

    try:
        for item in all_items:
            addTransaction(book, default_account, item, currency, rules, dry_run)
        book.flush()

    finally:
        if dry_run:
            logging.debug('** DRY-RUN **')
        else:
            logging.debug('Saving GnuCash file..')
            book.save()

    book.close()


def processFiles(args):
    if args.verbose:
        lvl = logging.DEBUG
    elif args.quiet:
        lvl = logging.WARN
    else:
        lvl = logging.INFO

    logging.basicConfig(level=lvl)

    rules = readRules(args.rulesfile)

    for fn in args.file:
        print("Processing file: " + fn)
        default_account_name = args.default_account
        if default_account_name is None:
            default_account_name = lookupAccountByName(fn, rules)
            print("Setting default import account to " + default_account_name)

        all_items = importFile(fn, default_account_name)
        writeTransactions(args.book, args.currency, all_items, default_account_name, rules, dry_run=args.dry_run)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('-v', '--verbose', help='Verbose (debug) logging', action='store_true')
    parser.add_argument('-q', '--quiet', help='Silent mode, only log warnings', action='store_true')
    parser.add_argument('--dry-run', help='Noop, do not write anything', action='store_true')
    parser.add_argument('-c', '--currency', metavar='ISOCODE', help='Currency ISO code (default: GBP)', default='GBP')
    parser.add_argument('-a', '--default-account', help='Gnucash default account')
    parser.add_argument('-f', '--book', help='Gnucash data file', default="sqlite://HomeAccounts.gnucash")
    parser.add_argument("-r", "--rulesfile", help="Rules file", default="rules.txt")
    parser.add_argument('file', nargs='+',
                        help='Input file(s) to be imported')

    args = parser.parse_args()
    processFiles(args)

