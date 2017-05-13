'''
Author: utkarshohm
Description: Transact on BSEStar using functions of api. Can use for testing api.py
'''

from django.core.management.base import BaseCommand
from django.core.management.base import CommandError

from datetime import date

from models.transactions import Transaction
from models.users import KycDetail, BankDetail
import api


class Command(BaseCommand):
    help = 'Transact on BSEStar using its api'
    
    def create_dummy_user(self, user_id):
        kyc, created = KycDetail.objects.get_or_create(
            user_id=user_id,
            defaults={
                'pan':'NIGHT1996W',
                'tax_status':'01',
                'occ_code':'01',
                'first_name':'Jon',
                'last_name':'Snow',
                'dob':'01/01/1000',
                'gender':'M',
                'address':"Squire to the Lord Commander of the Night's Watch",
                'city':'The Wall',
                'state':'Winterfell',
                'pincode':'110001',
                'phone':'9167783870',
                'income_slab':'31',
            },
            
        )
        
        bank, created = BankDetail.objects.get_or_create(
            user_id=user_id,
            defaults={
                'bank_name':'Iron Bank of Braavos',
                'account_number':'BASTARDNIGHT1996W',
                'account_type_bse':'SB',
                'ifsc_code':'NIGHT110001',
            },
        )
        

    def create_dummy_invest(self, user_id, scheme_id, amount):
        transaction = Transaction(
            user_id=user_id,
            scheme_plan_id=scheme_id,
            amount=amount,
            transaction_type='P',
            order_type='1',
            status='0',
        )
        transaction.save()
        return transaction


    def create_dummy_invest_sip(self, user_id, scheme_id, amount):
        transaction = Transaction(
            user_id=user_id,
            scheme_plan_id=scheme_id,
            amount=amount,
            transaction_type='A',
            order_type='2',
            sip_num_inst=6,
            sip_start_date=date(2017, 2, 21),
            status='0',
        )
        transaction.save()
        return transaction
    

    def create_dummy_invest_additional(self, user_id, scheme_id, amount):
        transaction = Transaction(
            user_id=user_id,
            scheme_plan_id=scheme_id,
            amount=amount,
            transaction_type='A',
            order_type='1',
            status='0',
        )
        transaction.save()
        return transaction

    
    def create_dummy_redeem(self, user_id, scheme_id):
        transaction = Transaction(
            user_id=user_id,
            scheme_plan_id=scheme_id,
            transaction_type='R',
            all_redeem='Y',
            order_type='1',
            status='0',
        )
        transaction.save()
        return transaction


    def handle(self, *args, **options):

        # set up values
        ## id for Info table in models.users
        user_id = 1
        ## id for FundScheme table in models.funds
        scheme_id = 1
        amount = 1000

        # user api 
        self.create_dummy_user(user_id)
        api.create_user_bse(user_id)

        # create transaction api
        transaction = self.create_dummy_invest(user_id, scheme_id, amount)
        api.create_transaction_bse(transaction)
        api.get_payment_link_bse(user_id, transaction.id)

        # cancel transaction api
        cancel_transaction_bse(transaction.id)

        # create mandate api
        create_mandate_bse(user_id, amount)

