'''
Author: utkarshohm
Description: update status of all transactions that need a status update (i.e. not completed or failed), using 
    (1) BSEStar api - only payment status has an API endpoint currently
    (2) by crawling BSEStar web portal (bsestarmf.in) for all other transaction statuses after payment
'''

from django.core.management.base import BaseCommand
from django.core.management.base import CommandError

from models.transactions import Transaction

from web import crawl_to_update_transaction_status
from api import get_payment_status_bse


class Command(BaseCommand):
    help = 'Update status of transactions using BSEStar api and by crawling its web portal'

    def update_payment_status(self):
        '''
        Updates payment status of all transactions whose payment status is not updated internally
        Uses api.get_payment_status_bse() as BSEStar offers API endpoint for this
        '''
        tr_list = Transaction.objects.filter(
                order_type='1',
                status__in=('2','4'),
            )
        status_list = []
        for tr in tr_list:
            try:
                status_list.append(get_payment_status_bse(tr.user_id, tr.id))
            except:
                status_list.append('-1')
        
        ## this is a good place to put in a slack alert


    def handle(self, *args, **options):
        
        # Update payment stautus of transactions with pending payment using api
        self.update_payment_status()
        
        # Update transaction status of transactions by crawling web
        crawl_to_update_transaction_status()

