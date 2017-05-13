from django.db import models
from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator

from funds import SchemePlan, FundScheme
from users import Info, Mandate


# Internal transaction table
class Transaction(models.Model):
	'''
	Saves each transaction's details for internal record
	Used to create records of TransactionBSE and TransactionXsipBSE
		that are sent to BSEStar's API endpoints
	'''
	
	# status of the transaction. most imp states are 1, 2 and 6 for bse
	STATUS = (
		('0', 'Requested internally'), # bse order not placed yet
		('1', 'Cancelled/Failed- refer to status_comment for reason'),
		('2', 'Order successfully placed at BSE'),
		('4', 'Redirected after payment'),
		('5', 'Payment provisionally made'),
		('6', 'Order sucessfully completed at BSE'),
		('7', 'Reversed'),	# when investment has been redeemed
		('8', 'Concluded'),	# valid for SIP only when SIP completed/stopped
	)
	TRANSACTIONTYPE = (
		('P', 'Purchase'),
		('R', 'Redemption'),
		('A', 'Additional Purchase'),
	)
	ORDERTYPE = (
		('1', 'Lumpsum'),
		('2', 'SIP'),
	)

	user = models.ForeignKey(Info,\
		on_delete=models.PROTECT,\
		related_name='transactions',\
		related_query_name='transaction')
	scheme_plan = models.ForeignKey(SchemePlan,\
		on_delete=models.PROTECT,\
		related_name='transactions',\
		related_query_name='transaction')
	
	transaction_type = models.CharField(max_length=1, blank=False, choices=TRANSACTIONTYPE, default='P')	##purchase redemption etc
	order_type = models.CharField(max_length=1, blank=False, choices=ORDERTYPE, default='1')	##lumpsum or sip
	
	# track status of transaction and comments if any from bse or rta
	status = models.CharField(max_length=1, choices=STATUS, default='0')
	status_comment = models.CharField(max_length=1000, blank=True)

	amount = models.FloatField(validators=[MinValueValidator(0), MaxValueValidator(1000000)], blank=True, null=True)
	
	# for redeem transactions
	all_redeem = models.NullBooleanField(blank=True, null=True)	## Null means not redeem transaction, True means redeem all, False means redeem 'amount' 

	# for SIP transactions
	sip_num_inst = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(120)], blank=True, null=True)
	sip_start_date = models.DateField(blank=True, null=True)
	## update this field after every instalment of sip
	sip_num_inst_done = models.IntegerField(validators=[MinValueValidator(0), MaxValueValidator(120)], blank=True, null=True, default=0)
	## add datetime_at_mf of each instalment 
	sip_dates = models.CharField(max_length=255, blank=True)
	## add bse order_id of each instalment 
	sip_order_ids = models.CharField(max_length=255, blank=True)
	mandate = models.ForeignKey(Mandate,\
		on_delete=models.PROTECT,\
		null=True,\
		related_name='transactions',\
		related_query_name='transaction')

	# datetimes of importance
	## datetime when order was placed on bsestar
	datetime_at_mf = models.DateTimeField(auto_now=False, auto_now_add=False, blank=True, null=True)	#datetime of purchase of units on mf
	created = models.DateTimeField(auto_now_add=True)
	
	# set these fields after the transaction is successfully PLACED
	## this is the trans_no of the order on bsestar
	## that has successfully placed this transaction
	bse_trans_no = models.CharField(max_length=20, blank=True)

	# set these fields after the transaction is successfully COMPLETED
	folio_number = models.CharField(max_length=25, blank=True)

	# Returns - set these fields daily after transaction is COMPLETED
	return_till_date = models.FloatField(blank=True, null=True)	#annualised compounded annually. make it absolute return
	return_date = models.DateField(auto_now=False, auto_now_add=False, blank=True, null=True) #date as of return calculated
	return_grade = models.CharField(max_length=200, blank=True)


# BSEStar's (lumpsum) order entry
class TransactionBSE(models.Model):
	'''
	Every lumpsum order placed on BSE is first saved in this table 
		using a form ensuring validation. The record from this table
		is then sent to BSEStar SOAP API endpoint using api.create_transaction_bse(). 
		This table was made as per BSEStar API documentation
	- Most fields can be given default values like dp_txn that should to be 
		physical so that user doesnt have to create a dmat account in nsdl or cdsl
	- Only few fields need input when creating a new transaction
	- Defaults are for NEW ORDER for FRESH, PURCHASE transaction
	'''
	TRANSCODE = (
		('NEW', 'New order'),
		('MOD', 'Modification order'),
		('CXL', 'Cancellation order'),
	)
	BUYSELL = (
		('P', 'Purchase'),
		('R', 'Redeem'),
	)
	BUYSELLTYPE = (
		('FRESH', 'Fresh'),
		('ADDITIONAL', 'Additional'),
	)
	DPTXN = (
		('P', 'Physical'),
		('N', 'NSDL'),
		('C', 'CDSL'),
	)
	YESORNO = (
		('Y', 'Yes eg KYC compliant'),
		('N', 'No eg KYC non-compliant'),
	)

	# these fields need input
	trans_no = models.CharField(max_length=19, blank=False, primary_key=True)	#201608201000004
	client_code = models.CharField(max_length=20, blank=False)
	scheme_cd = models.CharField(max_length=20, blank=False)
	order_val = models.CharField(validators=[RegexValidator(r'^[0-9]*$')], max_length=8, blank=True)	#even though limit is 14 digits, restricting to 8 digits
	qty = models.CharField(validators=[RegexValidator(r'^[0-9]*$')], max_length=8, blank=True, default='')
	## needed for redeem transactions only
	all_redeem = models.CharField(max_length=1, blank=False, choices=YESORNO, default='N')
	## needed for redeem and additional purchase transactions only
	folio_no = models.CharField(max_length=20, blank=True, default='')
	
	# auth for placing order on bse - you will get these from bse
	user_id = models.CharField(validators=[RegexValidator(r'^[0-9]*$')], max_length=10, blank=False)
	member_id = models.CharField(max_length=20, blank=False)
	password = models.CharField(max_length=250, blank=False)
	pass_key = models.CharField(max_length=10, blank=False)
	
	# fields with deafults
	trans_code = models.CharField(max_length=3, blank=False, choices=TRANSCODE, default='NEW')
	order_id = models.CharField(validators=[RegexValidator(r'^[0-9]*$')], max_length=8, blank=True, default='')
	buy_sell = models.CharField(max_length=1, blank=False, choices=BUYSELL, default='P')
	buy_sell_type = models.CharField(max_length=10, blank=False, choices=BUYSELLTYPE, default='FRESH')
	dp_txn = models.CharField(max_length=1, editable=False, choices=DPTXN, default='P')
	remarks = models.CharField(max_length=255, blank=True, default='')
	kyc_status = models.CharField(max_length=1, editable=False, choices=YESORNO, default='Y')
	ref_no = models.CharField(max_length=20, blank=True, default='')
	sub_br_code = models.CharField(max_length=15, blank=True, default='')
	## you get this when you register as a mf distributor
	euin = models.CharField(max_length=20, editable=False, default='E000000')
	euin_val = models.CharField(max_length=1, editable=False, choices=YESORNO, default='N')
	min_redeem = models.CharField(max_length=1, blank=False, choices=YESORNO, default='N')
	dpc = models.CharField(max_length=1, editable=False, choices=YESORNO, default='N')
	## some fields that are currently not used by bse
	ip_add = models.CharField(max_length=20, blank=True, default='')
	param1 = models.CharField(max_length=20, blank=True, default='')
	param2 = models.CharField(max_length=10, blank=True, default='')
	param3 = models.CharField(max_length=10, blank=True, default='')
	
	# link to internal transaction
	internal_transaction = models.ForeignKey(Transaction,
		on_delete=models.PROTECT,
		related_name='bselumpsumorders',
		related_query_name='bselumpsumorder',
		null=False
	)
	created = models.DateTimeField(auto_now_add=True)


# BSEStar's xsip order entry
class TransactionXsipBSE(models.Model):
	'''
	Same as TransactionBSE table except this is for SIP transactions
	XSIP is BSEStar's name for SIP done through the eXchange (BSE)
	'''
	TRANSCODE = (
		('NEW', 'New order'),
		('CXL', 'Cancellation order'),
	)
	TRANSMODE = (
		('D', 'Demat'),
		('P', 'Physical'),
		('DP', 'Demat/Physical'),
	)
	DPTXN = (
		('P', 'Physical'),
		('N', 'NSDL'),
		('C', 'CDSL'),
	)
	FREQTYPE = (
		('MONTHLY', 'Monthly'),
		('QUARTERLY', 'Quarterly'),
		('WEEKLY', 'Weekly'),
	)
	YESORNO = (
		('Y', 'Yes eg KYC compliant'),
		('N', 'No eg KYC non-compliant'),
	)

	# these fields need input
	trans_no = models.CharField(max_length=19, blank=False, primary_key=True)
	scheme_cd = models.CharField(max_length=20, blank=False)
	client_code = models.CharField(max_length=20, blank=False)
	start_date = models.CharField(max_length=10, blank=False)
	inst_amt = models.CharField(validators=[RegexValidator(r'^[0-9]*$')], max_length=8, blank=False)	
	num_inst = models.CharField(validators=[RegexValidator(r'^[0-9]*$')], max_length=2, blank=False, default='6') #even though limit is 4 digits, restricting to 2 digits
	mandate_id = models.CharField(validators=[RegexValidator(r'^[0-9]*$')], max_length=8, blank=True)	

	# auth for placing order on bse - you will get these from bse
	user_id = models.CharField(validators=[RegexValidator(r'^[0-9]*$')], max_length=10, blank=False, default='1024601')
	member_id = models.CharField(max_length=20, blank=False, default='10246')
	password = models.CharField(max_length=250, blank=False)
	pass_key = models.CharField(max_length=10, blank=False)
	
	# fields with deafults
	trans_code = models.CharField(max_length=3, blank=False, choices=TRANSCODE, default='NEW')
	int_ref_no = models.CharField(max_length=10, blank=True, default='')
	trans_mode = models.CharField(max_length=2, editable=False, choices=TRANSMODE, default='P')
	dp_txn = models.CharField(max_length=1, editable=False, choices=DPTXN, default='P')
	freq_type = models.CharField(max_length=10, editable=False, choices=FREQTYPE, default='MONTHLY')
	freq_allowed = models.CharField(max_length=1, editable=False, default='1')
	remarks = models.CharField(max_length=100, blank=True, default='')
	folio_no = models.CharField(max_length=20, blank=True, default='')
	first_order_flag = models.CharField(max_length=1, blank=False, choices=YESORNO, default='Y')
	brokerage = models.CharField(validators=[RegexValidator(r'^[0-9]*$')], max_length=8, blank=True, default='')	
	sub_br_code = models.CharField(max_length=15, blank=True, default='')
	## you get this when you register as a mf distributor
	euin = models.CharField(max_length=20, editable=False, default='E153740')
	euin_val = models.CharField(max_length=1, editable=False, choices=YESORNO, default='N')
	dpc = models.CharField(max_length=1, editable=False, choices=YESORNO, default='N')
	xsip_reg_id = models.CharField(validators=[RegexValidator(r'^[0-9]*$')], max_length=10, blank=True, default='')	
	## some fields that are currently not used by bse
	ip_add = models.CharField(max_length=20, blank=True, default='')
	param1 = models.CharField(max_length=20, blank=True, default='')
	param2 = models.CharField(max_length=15, blank=True, default='')
	param3 = models.CharField(max_length=10, blank=True, default='')

	# link to internal transaction
	internal_transaction = models.ForeignKey(Transaction,
		on_delete=models.PROTECT,
		related_name='bsexsiporders',
		related_query_name='xsiporder',
		null=False
	)
	created = models.DateTimeField(auto_now_add=True)


# BSEStar's response to order entry
class TransResponseBSE(models.Model):
	'''
	Saves response sent by BSEStar to api.create_transaction_bse()
	Used to update fields in internal Transaction table
	'''
	TRANSCODE = (
		('NEW', 'New order'),
		('MOD', 'Modification order'),
		('CXL', 'Cancellation order'),
	)
	ORDERTYPE = (
		('L', 'Lumpsum'),
		('S', 'SIP'),
		('X', 'XSIP'),
	)
	trans_code = models.CharField(max_length=3, blank=False, choices=TRANSCODE)
	trans_no = models.CharField(max_length=19, blank=False)
	order_id = models.CharField(validators=[RegexValidator(r'^[0-9]*$')], max_length=10, blank=False)	#order_id for lumpsum order is 8-digit long; xsip_reg_id is 10-digit
	user_id = models.CharField(validators=[RegexValidator(r'^[0-9]*$')], max_length=10, blank=False)
	member_id = models.CharField(max_length=20, blank=False)
	client_code = models.CharField(max_length=20, blank=False)
	bse_remarks = models.CharField(max_length=1000, blank=False)
	success_flag = models.CharField(max_length=1, blank=False)
	
	## Fields not returned by BSEStar
	order_type = models.CharField(max_length=1, blank=False, choices=ORDERTYPE)
	created = models.DateTimeField(auto_now_add=True)


# BSEStar's payment links
class PaymentLinkBSE(models.Model):
	'''
	Saves payment links sent by BSEStar in response to api.get_payment_link_bse()
	'''
	user = models.ForeignKey(Info,
		on_delete=models.PROTECT,
		related_name='paymentlinks',
		related_query_name='paymentlink')
	link = models.CharField(max_length=1000, blank=False)
	created = models.DateTimeField(auto_now_add=True)

