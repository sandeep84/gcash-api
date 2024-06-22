#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
A simple class to represent a Quicken (QIF) file, and a parser to
load a QIF file into a sequence of those classes.

It's enough to be useful for writing conversions.

Original source from http://code.activestate.com/recipes/306103-quicken-qif-file-class-and-conversion/
"""

import sys
import datetime
from decimal import Decimal
from account_entry import AccountEntry

class QIFParser:
    def __init__(self, filename) -> None:
        self.filename = filename

    def get_entries(self):
        """
        Parse a qif file and return a list of entries.
        infile should be open file-like object (supporting readline() ).
        """
        account = None
        items = []
        curItem = AccountEntry()

        with open(self.filename) as infile:
            for line in infile:
                firstchar = line[0]
                data = line[1:].strip()
                if firstchar == '\n':  # blank line
                    pass
                elif firstchar == '^':
                                    # end of item
                    if curItem.type != 'Account':
                        # save the item
                        items.append(curItem)
                    curItem = AccountEntry()
                    curItem.account = account
                elif firstchar == 'D':
                    day, month, year = map(int, data.split('/'))
                    curItem.date = datetime.datetime(year=year, month=month, day=day)
                elif firstchar == 'T':
                    curItem.amount = Decimal(data.replace(',', ''))
                elif firstchar == 'C':
                    curItem.cleared = data
                elif firstchar == 'P':
                    curItem.payee = data
                elif firstchar == 'M':
                    curItem.memo = data
                elif firstchar == 'A':
                    curItem.address = data
                elif firstchar == 'L':
                    curItem.category = data
                elif firstchar == 'S':
                    curItem.split_category = data
                elif firstchar == 'E':
                    curItem.split_memo = data
                elif firstchar == '$':
                    curItem.split_amount = Decimal(data.replace(',', ''))
                elif firstchar == 'N':
                    if curItem.type == 'Account':
                        account = data
                elif firstchar == '!':
                    curItem.type = data
                else:
                    # don't recognise this line; ignore it
                    print >> sys.stderr, 'Skipping unknown line:\n', line

        return items


