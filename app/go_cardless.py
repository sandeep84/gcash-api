from requests import HTTPError
from uuid import uuid4
from nordigen import NordigenClient
import json
import dateutil.parser
from decimal import Decimal
import os.path

from app.account_entry import AccountEntry
import app.accountManager

class GoCardlessClient:
    def __init__(self, account_url):
        self.account_url = account_url

        self.__secrets = app.accountManager.readSecrets()

        if os.path.isfile('rules.txt'):
            self.rules = app.accountManager.readRules('rules.txt')
        elif os.path.isfile('/data/rules.txt'):
            self.rules = app.accountManager.readRules('/data/rules.txt')

        self.client = NordigenClient(
            secret_id=self.__secrets['nordigen_secret_id'],
            secret_key=self.__secrets['nordigen_secret_key']
        )
        self.client.token = self.__secrets['nordigen_client_token']



    def write_secrets(self):
        with open("secrets.json", "w") as f:
            f.write(json.dumps(self.__secrets))

    def get_transactions(self, account_name, account):
        print(f'Processing account {account_name} ...')

        # Initialize bank session
        self.connection_retry_count = 0
        self.client_init = None

        while self.client_init is None and self.connection_retry_count < 2:
            try:
                self.client_init = self.client.initialize_session(
                    # institution id
                    institution_id=account['institution_id'],
                    # redirect url after successful authentication
                    redirect_uri="https://gocardless.com",
                    # additional layer of unique ID defined by you
                    reference_id=str(uuid4())
                )
            except HTTPError as e:
                print(f'Exception: {e}')
                self.connection_retry_count += 1

                if e.response.json()['summary'] == 'Invalid token':
                    print(f'Updating token')
                    # Create new access and refresh token
                    # Parameters can be loaded from .env or passed as a string
                    # Note: access_token is automatically injected to other requests after you successfully obtain it
                    token_data = self.client.generate_token()
                    new_token = self.client.exchange_token(token_data["refresh"])

                    self.__secrets['nordigen_client_token'] = self.client.token
                    self.__secrets['nordigen_client_refresh_token'] = token_data['refresh']

                    # Update secrets for next use
                    self.write_secrets()

        if self.connection_retry_count >= 2:
            raise Exception(f'Connection refused')

        if 'requisition_id' not in account:
            # Get requisition_id and link to initiate authorization process with a bank
            account['requisition_id'] = self.client_init.requisition_id
            input(f'Open the following link in your browser: {self.client_init.link} and follow the prompts to authorise access. Press ENTER once complete.')
            self.write_secrets()

        self.client_init.requisition_id = account['requisition_id']
        print(f'{account_name}: requisition_id={self.client_init.requisition_id}')

        # Get account id after you have completed authorization with a bank
        # requisition_id can be gathered from initialize_session response
        accounts = self.client.requisition.get_requisition_by_id(
            requisition_id=self.client_init.requisition_id
        )

        # Get account id from the list.
        account_id = accounts["accounts"][0]

        # Create account instance and provide your account id from previous step
        account = self.client.account_api(id=account_id)

        # Fetch transactions
        transactions = account.get_transactions()['transactions']

        # print(transactions)

        # with open(f'{account_name.replace(":", "_")}_transactions.json', "w") as f:
        #     f.write(json.dumps(transactions))

        return transactions

    # with open("transactions.json", "r") as f:
    #     transactions = json.loads(f.read())['transactions']

    def update_account(self, account_name, transactions):
        items = []
        for transaction in transactions['booked'] + transactions["pending"]:
            item = AccountEntry()
            item.account = account_name
            item.date = dateutil.parser.isoparse(transaction['bookingDate'])
            item.split_amount = Decimal(transaction['transactionAmount']['amount'])
            if 'remittanceInformationUnstructured' in transaction:
                item.payee = transaction['remittanceInformationUnstructured']
            elif 'remittanceInformationUnstructuredArray' in transaction:
                item.payee = ' '.join(transaction['remittanceInformationUnstructuredArray'])
            elif 'creditorName' in transaction:
                item.payee = transaction['creditorName']

            items.append(item)

        app.accountManager.writeTransactions(
            self.account_url,
            'GBP',
            items,
            account_name,
            self.rules,
            False
        )

    def update_accounts(self):
        for account_name, account in self.__secrets['accounts'].items():
            transactions = self.get_transactions(account_name, account)
            self.update_account(account_name, transactions)

if __name__ == '__main__':
    client = GoCardlessClient()
    client.update_accounts()



