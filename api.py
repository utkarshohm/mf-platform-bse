'''
Author: utkarshohm
Description: All functions necessary to transact in mutual funds on BSEStar using its SOAP API
'''

from django import forms
from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator 

import settings
from models.transactions import TransactionBSE, TransactionXsipBSE, TransResponseBSE, Transaction, PaymentLinkBSE
from models.users import Info, KycDetail, BankDetail

import zeep


################ MAIN FUNCTIONS - called by transact_using_api.py

def create_transaction_bse(transaction):
	'''
	Creates a transaction on BSEStar for a given transaction
	- Initializes SOAP client zeep
	- Gets one-time password from BSEStar to query its endpoint
	- Prepares fields to be sent to BSEStar transaction creation endpoint
	- Posts the requests
	- Updates internal Transaction record based on response from endpoint
	'''

	## initialise the zeep client for order wsdl
	client = zeep.Client(wsdl=WSDL_ORDER_URL[settings.LIVE])
	set_soap_logging()

	## get the password for posting order
	pass_dict = soap_get_password_order(client)
	
	## prepare order, post it to BSE and save response
	## for lumpsum transaction 
	if (transaction.order_type == '1'):
		## prepare the transaction record
		bse_order = prepare_order(transaction, pass_dict)
		## post the transaction
		order_id = soap_post_order(client, bse_order)
	
	## for SIP transaction 
	elif (transaction.order_type == '2'):
		## for basanti-2: since xsip orders cannot be placed in off-market hours, 
		## placing a lumpsum order instead 
		bse_order = prepare_xsip_order(transaction, pass_dict)
		## post the transaction
		order_id = soap_post_xsip_order(client, bse_order)

	else:
		raise Exception(
			"Internal error 630: Invalid order_type in transaction table"
		)

	## update internal's transaction table to have a foreign key to TransactionBSE or TransactionXsipBSE table
	transaction.bse_trans_no = bse_order.trans_no
	transaction.save()

	## TODO: MANUALLY update folio number & status assigned to a transaction after the mf is allotted to user
	## have added it here for purpose of testing only
	transaction.status = '2'
	transaction.save()
	if (transaction.transaction_type == 'R'):
		## TODO: make changes to purchase transactions corresponding to the redeem transaction
		pass

	return order_id


def get_payment_link_bse(client_code, transaction_id):
	'''
	Gets the payment link corresponding to a client
	Called immediately after creating transaction 
	'''

	## get the payment link and store it
	client = zeep.Client(wsdl=WSDL_UPLOAD_URL[settings.LIVE])
	set_soap_logging()
	pass_dict = soap_get_password_upload(client)
	payment_url = soap_create_payment(client, str(client_code), transaction_id, pass_dict)
	PaymentLinkBSE.objects.create(
		user_id=client_code, 
		link=payment_url, 
	)
	return payment_url


def create_user_bse(client_code):
	'''
	Creates a user on BSEStar (called client in bse lingo)
	- Initializes SOAP client zeep
	- Gets one-time password from BSEStar to query its endpoints
	- Prepares fields to be sent to BSEStar user creation and fatca endpoints
	- Posts the requests
	'''

	## initialise the zeep client for order wsdl
	client = zeep.Client(wsdl=WSDL_UPLOAD_URL[settings.LIVE])
	set_soap_logging()

	## get the password 
	pass_dict = soap_get_password_upload(client)
	## prepare the user record 
	bse_user = prepare_user_param(client_code)
	## post the user creation request
	user_response = soap_create_user(client, bse_user, pass_dict)
	## TODO: Log the soap request and response post the user creation request

	pass_dict = soap_get_password_upload(client)
	bse_fatca = prepare_fatca_param(client_code)
	fatca_response = soap_create_fatca(client, bse_fatca, pass_dict)
	## TODO: Log the soap request and response post the fatca creation request


def cancel_transaction_bse(transaction):
	'''
	Cancels a transaction created earlier on BSEStar
	Note that this can be done only till 3pm on day when order is sent by BSEStar to RTA
	'''

	## initialise the zeep client for order wsdl
	client = zeep.Client(wsdl=WSDL_ORDER_URL[settings.LIVE])
	set_soap_logging()

	## get the password for posting order
	pass_dict = soap_get_password_order(client)
	
	## get trans_no of the order to be cancelled
	trans_no_of_order = transaction.bse_trans_no

	## get order_id of the transaction to be cancelled 
	## trans_no is of the type 2016080110000011 
	order_type = trans_no_of_order[8]
	order_id = TransResponseBSE.objects.get(trans_no=trans_no_of_order).order_id

	## prepare cancellation order
	bse_order = prepare_order_cxl(transaction, order_id, pass_dict)

	## for lumpsum order 
	if (order_type == '1'):
		## post the order
		order_id = soap_post_order(client, bse_order)
	## for XSIP order 
	elif (order_type == '2'):
		order_id = soap_post_xsip_order(client, bse_order)

	## update internal's transaction table to have a foreign key to cancellation order
	transaction.bse_trans_no = bse_order.trans_no
	transaction.status = '1'	## status 'canceled'
	transaction.save()


def create_mandate_bse(client_code, amount):
	'''
	Creates mandate for user for a specific amount 
	Called before creating an SIP transaction on BSEStar because 
		every SIP transaction requires a mandate
	'''

	## initialise the zeep client for wsdl
	client = zeep.Client(wsdl=WSDL_UPLOAD_URL[settings.LIVE])
	set_soap_logging()

	## get the password
	pass_dict = soap_get_password_upload(client)
	
	## prepare the mandate record 
	bse_mandate = prepare_mandate_param(client_code, amount)

	## post the mandate creation request
	mandate_id = soap_create_mandate(client, bse_mandate, pass_dict)
	return mandate_id


def get_payment_status_bse(client_code, transaction_id):
	'''
	Gets whether user has paid for a transaction created on BSEStar
	'''

	## initialise the zeep client for wsdl
	client = zeep.Client(wsdl=WSDL_UPLOAD_URL[settings.LIVE])
	set_soap_logging()

	## get the password
	pass_dict = soap_get_password_upload(client)
	
	## get payment status
	payment_status = soap_get_payment_status(client, client_code, transaction_id, pass_dict)
	return payment_status


################ SOAP FUNCTIONS to get/post data - called by MAIN FUNCTIONS

## fire SOAP query to get password for Order API endpoint
## used by create_transaction_bse() and cancel_transaction_bse()
def soap_get_password_order(client):
	method_url = METHOD_ORDER_URL[settings.LIVE] + 'getPassword'
	svc_url = SVC_ORDER_URL[settings.LIVE]
	header_value = soap_set_wsa_headers(method_url, svc_url)
	response = client.service.getPassword(
		UserId=settings.USERID[settings.LIVE], 
		Password=settings.PASSWORD[settings.LIVE], 
		PassKey=settings.PASSKEY[settings.LIVE], 
		_soapheaders=[header_value]
	)
	print
	response = response.split('|')
	status = response[0]
	if (status == '100'):
		# login successful
		pass_dict = {'password': response[1], 'passkey': settings.PASSKEY[settings.LIVE]}
		return pass_dict
	else:
		raise Exception(
			"BSE error 640: Login unsuccessful for Order API endpoint"
		)


## fire SOAP query to get password for Upload API endpoint
## used by all functions except create_transaction_bse() and cancel_transaction_bse()
def soap_get_password_upload(client):
	method_url = METHOD_UPLOAD_URL[settings.LIVE] + 'getPassword'
	svc_url = SVC_UPLOAD_URL[settings.LIVE]
	header_value = soap_set_wsa_headers(method_url, svc_url)
	response = client.service.getPassword(
		MemberId=settings.MEMBERID[settings.LIVE], 
		UserId=settings.USERID[settings.LIVE],
		Password=settings.PASSWORD[settings.LIVE], 
		PassKey=settings.PASSKEY[settings.LIVE], 
		_soapheaders=[header_value]
	)
	print
	response = response.split('|')
	status = response[0]
	if (status == '100'):
		# login successful
		pass_dict = {'password': response[1], 'passkey': settings.PASSKEY[settings.LIVE]}
		return pass_dict
	else:
		raise Exception(
			"BSE error 640: Login unsuccessful for upload API endpoint"
		)


## fire SOAP query to post the order 
def soap_post_order(client, bse_order):
	method_url = METHOD_ORDER_URL[settings.LIVE] + 'orderEntryParam'
	header_value = soap_set_wsa_headers(method_url, SVC_ORDER_URL[settings.LIVE])
	response = client.service.orderEntryParam(
		bse_order.trans_code,
		bse_order.trans_no,
		bse_order.order_id,
		bse_order.user_id,
		bse_order.member_id,
		bse_order.client_code,
		bse_order.scheme_cd,
		bse_order.buy_sell,
		bse_order.buy_sell_type,
		bse_order.dp_txn,
		bse_order.order_val,
		bse_order.qty,
		bse_order.all_redeem,
		bse_order.folio_no,
		bse_order.remarks,
		bse_order.kyc_status,
		bse_order.ref_no,
		bse_order.sub_br_code,
		bse_order.euin,
		bse_order.euin_val,
		bse_order.min_redeem,
		bse_order.dpc,
		bse_order.ip_add,
		bse_order.password,
		bse_order.pass_key,
		bse_order.param1,
		bse_order.param2,
		bse_order.param3,
		_soapheaders=[header_value]
	)
	
	## this is a good place to put in a slack alert
	
	response = response.split('|')
	## store the order response in a table
	order_id = store_order_response(response, '1')
	status = response[7]
	if (status == '0'):
		# order successful
		return order_id
	else:
		raise Exception(
			"BSE error 641: %s" % response[6]
		)


## fire SOAP query to post the XSIP order 
def soap_post_xsip_order(client, bse_order):
	method_url = METHOD_ORDER_URL[settings.LIVE] + 'xsipOrderEntryParam'
	header_value = soap_set_wsa_headers(method_url, SVC_ORDER_URL[settings.LIVE])
	response = client.service.xsipOrderEntryParam(
		bse_order.trans_code,
		bse_order.trans_no,
		bse_order.scheme_cd,
		bse_order.member_id,
		bse_order.client_code,
		bse_order.user_id,
		bse_order.int_ref_no,
		bse_order.trans_mode,
		bse_order.dp_txn,
		bse_order.start_date,
		bse_order.freq_type,
		bse_order.freq_allowed,
		bse_order.inst_amt,
		bse_order.num_inst,
		bse_order.remarks,
		bse_order.folio_no,
		bse_order.first_order_flag,
		bse_order.brokerage,
		bse_order.mandate_id,
		# '',
		bse_order.sub_br_code,
		bse_order.euin,
		bse_order.euin_val,
		bse_order.dpc,
		bse_order.xsip_reg_id,
		bse_order.ip_add,
		bse_order.password,
		bse_order.pass_key,
		bse_order.param1,
		# bse_order.mandate_id,
		bse_order.param2,
		bse_order.param3,
		_soapheaders=[header_value]
	)
	
	## this is a good place to put in a slack alert

	response = response.split('|')
	## store the order response in a table
	order_id = store_order_response(response, '2')
	status = response[7]
	if (status == '0'):
		# order successful
		return order_id
	else:
		raise Exception(
			"BSE error 642: %s" % response[6]
		)


## fire SOAP query to get the payment url 
def soap_create_payment(client, client_code, transaction_id, pass_dict):
	method_url = METHOD_UPLOAD_URL[settings.LIVE] + 'MFAPI'
	header_value = soap_set_wsa_headers(method_url, SVC_UPLOAD_URL[settings.LIVE])
	logout_url = settings.FRONTEND[settings.FB_LIVE] + 'payment/' + str(transaction_id)
	response = client.service.MFAPI(
		'03',
		settings.USERID[settings.LIVE],
		pass_dict['password'],
		settings.MEMBERID[settings.LIVE]+'|'+client_code+'|'+logout_url,
		_soapheaders=[header_value]
	)
	print
	response = response.split('|')
	status = response[0]
	
	if (status == '100'):
		# getting payment url successful
		payment_url = response[1]
		return payment_url
	else:
		raise Exception(
			"BSE error 646: Payment link creation unsuccessful: %s" % response[1]
		)


## fire SOAP query to create a new user on bsestar
def soap_create_user(client, user_param, pass_dict):
	method_url = METHOD_UPLOAD_URL[settings.LIVE] + 'MFAPI'
	header_value = soap_set_wsa_headers(method_url, SVC_UPLOAD_URL[settings.LIVE])
	response = client.service.MFAPI(
		'02',
		settings.USERID[settings.LIVE],
		pass_dict['password'],
		user_param,
		_soapheaders=[header_value]
	)
	
	## this is a good place to put in a slack alert

	response = response.split('|')
	status = response[0]
	if (status == '100'):
		# User creation successful
		pass
	else:
		raise Exception(
			"BSE error 644: User creation unsuccessful: %s" % response[1]
		)


## fire SOAP query to craete fatca record of user on bsestar
def soap_create_fatca(client, fatca_param, pass_dict):
	method_url = METHOD_UPLOAD_URL[settings.LIVE] + 'MFAPI'
	header_value = soap_set_wsa_headers(method_url, SVC_UPLOAD_URL[settings.LIVE])
	response = client.service.MFAPI(
		'01',
		settings.USERID[settings.LIVE],
		pass_dict['password'],
		fatca_param,
		_soapheaders=[header_value]
	)
	
	## this is a good place to put in a slack alert

	response = response.split('|')
	status = response[0]
	if (status == '100'):
		# Fatca creation successful
		pass
	else:
		raise Exception(
			"BSE error 645: Fatca creation unsuccessful: %s" % response[1]
		)


## fire SOAP query to create a new mandate on bsestar
def soap_create_mandate(client, mandate_param, pass_dict):
	method_url = METHOD_UPLOAD_URL[settings.LIVE] + 'MFAPI'
	header_value = soap_set_wsa_headers(method_url, SVC_UPLOAD_URL[settings.LIVE])
	response = client.service.MFAPI(
		'06',
		settings.USERID[settings.LIVE],
		pass_dict['password'],
		mandate_param,
		_soapheaders=[header_value]
	)
	
	## this is a good place to put in a slack alert

	response = response.split('|')
	status = response[0]
	if (status == '100'):
		# Mandate creation successful, so save it in table
		from users.models import Mandate, BankDetail
		mandate_values = mandate_param.split('|')
		mandate_id = int(response[2])
		bank = BankDetail.objects.get(user_id=int(mandate_values[1]))

		mandate = Mandate.objects.create(
            user = Info.objects.get(id=int(mandate_values[1])),
            bank = bank,
            id = mandate_id,
            amount = int(mandate_values[2]),
            status = '2',
        )
		if (bank.branch.ifsc_code != mandate_values[3]):
			# raise error that banks dont match
			raise Exception(
				"BSE error 651: Mandate created for a bank that doesnt match with user's bank"
			)
		return mandate_id
	else:
		raise Exception(
			"BSE error 651: Mandate creation unsuccessful: %s" % response[1]
		)


## fire SOAP query to create a new mandate on bsestar
def soap_get_payment_status(client, client_code, transaction_id, pass_dict):
	# find order_id for transaction
	transaction = Transaction.objects.get(id=transaction_id)
	if transaction.transaction_type == 'R':
		raise Exception(
			"Error 630: Cannot get payment status for redeem transactions"
		)
	order_id = TransResponseBSE.objects.get(
			trans_no=transaction.bse_trans_no
		).order_id
	# TODO: handle case when order_id not found
	
	method_url = METHOD_UPLOAD_URL[settings.LIVE] + 'MFAPI'
	header_value = soap_set_wsa_headers(method_url, SVC_UPLOAD_URL[settings.LIVE])
	response = client.service.MFAPI(
		'11',
		settings.USERID[settings.LIVE],
		pass_dict['password'],
		str(client_code)+'|'+str(order_id)+'|BSEMF',
		_soapheaders=[header_value]
	)
	
	## this is a good place to put in a slack alert

	response = response.split('|')
	status = response[0]
	if (status == '100'):
		if response[1] == 'PAYMENT NOT INITIATED FOR GIVEN ORDER' or 'REJECTED' in response[1]:
			# payment unsucessful
			if transaction.status in ['4', '5', '6']:
				transaction.status = '2'
				transaction.save()
				return '2'
			else:
				# no change
				return '0'
		else:
			# payment successful- update in db
			transaction.status = '5'
			transaction.save()
			return '5'
	else:		
		raise Exception(
			"BSE error 644: Get payment status unsuccessful: %s" % response[1]
		)


################ PREPARE FUNCTIONS to post data- called by MAIN FUNCTIONS


def prepare_trans_no(client_code, bse_order_type):
	'''
	trans_no is a unique number sent with every transaction creation request sent to BSE
	If it is not unique transaction creation request is rejected by BSE
	I follow this form for trans_no: eg. 20160801L0000011
		- digit 1 to 8: today's date in YYYYMMDD
		- digit 9: '1' for lumpsum order and '2' for Xsip
		- digit 10 to 15: client_code(bse) or user_id(internal) padded with 0s to make it 6 digit long
		- digit 16 onwards: counter starting from 1, gets incremented with every order in 
			TransactionBse or TransactionXsipBse table. counter reset to 1 every day 
	'''

	# pad client code with 0s till it is CC_LEN digits 
	CC_LEN = 6
	
	# pad client_code with 0s
	cc_str = str(client_code)
	cc_str = '0'* (CC_LEN - len(cc_str)) + cc_str 

	# prepare unique trans_no by looking for the last transaction made by the client today
	import datetime
	now = datetime.datetime.now()
	# If this is testing environment, replace first digit of year with 1
	if settings.LIVE == 0:
		today_str = '00' + now.strftime('%y%m%d') + bse_order_type
	else:
		today_str = now.strftime('%Y%m%d') + bse_order_type

	try:
		if (bse_order_type == '1'):
			relevant_trans = TransactionBSE.objects.filter(client_code=client_code, trans_no__contains=today_str)
		elif (bse_order_type == '2'):
			## for basanti-2: since xsip orders cannot be placed in off-market hours, placing a lumpsum order instead 
			relevant_trans = TransactionXsipBSE.objects.filter(client_code=client_code, trans_no__contains=today_str)
		max_trans_no = 0
		for trans in relevant_trans:
			prev_trans_no = int(trans.trans_no[CC_LEN+9:])
			if (prev_trans_no > max_trans_no):
				max_trans_no = prev_trans_no
		if (max_trans_no >= 99):
			raise Exception(
				"BSE error 647: 99 transactions already placed today for this user"
			)
		trans_no = today_str + cc_str + str(max_trans_no + 1)
	except (TransactionBSE.DoesNotExist, TransactionXsipBSE.DoesNotExist) as e :
		trans_no = today_str + cc_str + '1'
	
	# print 'trans_no', trans_no
	return trans_no


# get previous purchase transactions 
def get_previous_trans(transaction):
	try:
		trans_l = Transaction.objects.filter(
			user_id=transaction.user_id,
			scheme_plan_id=transaction.scheme_plan_id,
			transaction_type='P',	## folio must have been allotted in a purchase transaction only
			status='6',	## status is 'completed'
			folio_number__gt='',	## folio is not blank
		)
	except Transaction.DoesNotExist:
		raise Exception(
			"Internal error 632: No existing purchase found such that an additional purchase or redeem transaction be made"
		)
	return trans_l


# prepare the TransactionBSE record
def prepare_order(transaction, pass_dict):
	
	trans_no = prepare_trans_no(transaction.user_id, transaction.order_type)

	# Fill all fields for a FRESH PURCHASE
	# Change fields if its a redeem or addl purchase
	data_dict = {
		'trans_code': 'NEW',
		'trans_no': trans_no,
		'user_id': settings.USERID[settings.LIVE],
		'member_id': settings.MEMBERID[settings.LIVE],
		'client_code': transaction.user_id,
		'scheme_cd': transaction.scheme_plan.bse_code,
		'buy_sell': 'P',
		'buy_sell_type': 'FRESH',
		'all_redeem': 'N',
		'min_redeem': 'N',
		'password': pass_dict['password'],
		'pass_key': pass_dict['passkey'],
		'internal_transaction': transaction.id, 
	}

	if (transaction.transaction_type == 'P'):
		# FRESH PURCHASE transaction
		data_dict['order_val'] = int(transaction.amount)

	else:
		# ADDITIONAL PURCHASE OR REDEEM transaction
		## set folio_no by looking at previous transactions
		trans_l = get_previous_trans(transaction)

		### assumption: pick the first relevant transaction's folio number if there are multiple transactions 
		# data_dict['folio_no'] = '123456789012345'
		data_dict['folio_no'] = trans_l[0].folio_number

		if (transaction.transaction_type == 'A'):
			# ADDITIONAL PURCHASE order
			data_dict['buy_sell_type'] = 'ADDITIONAL'
			data_dict['order_val'] = int(transaction.amount)
		
		elif (transaction.transaction_type == 'R'):
			# REDEEM order
			data_dict['buy_sell'] = 'R'

			## set all_redeem flag in case entire investment is being redeemed, else 
			if (transaction.all_redeem):
				data_dict['all_redeem'] = 'Y'
				data_dict['order_val'] = ''
			elif (transaction.all_redeem == None):
				raise Exception(
					"Internal error 634: all_redeem field of internal transaction table is not set for a redeem transaction"
				)

	form = NewOrderForm(data_dict)
	# form.is_valid() calls form.clean() as well as model.full_clean()
	# so validators on model are also applied
	if form.is_valid():
		bse_transaction = form.save()
		return bse_transaction
	else:
		raise Exception(
			'BSE error 648: %s' % form.errors
		)


# prepare the TransactionXsipBSE record
def prepare_xsip_order(transaction, pass_dict):
	
	if (transaction.order_type != '2'):
		raise Exception(
			"Internal error 630: XSIP Order entry cannot be prepared because Transaction argument passed is not SIP"
		)

	trans_no = prepare_trans_no(transaction.user_id, transaction.order_type)
	
	# find mandate id; if not found then create one
	from users.models import Mandate
	mandates = Mandate.objects.filter(
		user = transaction.user,
		status__in = (2,3,4,5), 
	)
	create_new = True
	# check if any of the mandates is valid
	for mandate in mandates:
		tr_list = Transaction.objects.filter(
			user = transaction.user,
			order_type = '2',
			status__in = ('2','5','6'),
			mandate = mandate.id,
		)
		amount_exhausted = 0
		for tr in tr_list:
			amount_exhausted += tr.amount
		if (mandate.amount >= amount_exhausted + transaction.amount):
			# use this mandate
			transaction.mandate_id = mandate.id
			create_new = False
			break
	if create_new:
		# decide amount of mandate
		mandate_amount = 100000
		if transaction.amount > mandate_amount:
			mandate_amount = transaction.amount
		# query bse for new mandate
		transaction.mandate_id = create_mandate_bse(transaction.user_id, mandate_amount)
	# in either case save the mandate_id in transaction entry
	transaction.save()

	# Internally, SIP transactions will necessarly have first instalment on day of placing xsip order itself and xsip start date (2nd instalment) will be atleast 30 days away
	import datetime
	now = datetime.date.today()
	num_days = (transaction.sip_start_date - now).days
	if (num_days < 30 and num_days >= 0):
		raise Exception(
			"BSE error 649: XSIP start date must be atleast 30 days from today"
		)
	elif (num_days > 60):
		raise Exception(
			"BSE error 649: XSIP start date must be at most 60 days from today"
		)

	data_dict = {
		'trans_code': 'NEW',
		'trans_no': trans_no,
		'user_id': settings.USERID[settings.LIVE],
		'member_id': settings.MEMBERID[settings.LIVE],
		'client_code': transaction.user_id,
		'scheme_cd': transaction.scheme_plan.bse_code,
		'start_date': transaction.sip_start_date.strftime('%d/%m/%Y'),
		'inst_amt': int(transaction.amount),
		'num_inst': int(transaction.sip_num_inst),
		'first_order_flag': 'Y',
		# 'first_order_flag': 'N',
		'mandate_id': transaction.mandate_id,
		'password': pass_dict['password'],
		'pass_key': pass_dict['passkey'],
		'internal_transaction': transaction.id, 
	}

	# ADDITIONAL PURCHASE order
	if (transaction.transaction_type == 'A'):
		## set folio_no by looking at previous transactions
		trans_l = get_previous_trans(transaction)
		## assumption: pick the first relevant transaction's folio number if there are multiple transactions 
		data_dict['folio_no'] = trans_l[0].folio_number
		transaction.folio_number = trans_l[0].folio_number
		transaction.save()

	form = NewXsipOrderForm(data_dict)
	# form.is_valid() calls form.clean() as well as model.full_clean()
	# so validators on model are also applied
	if form.is_valid():
		bse_transaction = form.save()
		# print bse_transaction
		return bse_transaction
	else:
		raise Exception(
			'BSE error 649: %s' % form.errors
		)


# prepare the TransactionBSE record
def prepare_order_cxl(transaction, order_id, pass_dict):
	
	trans_no = prepare_trans_no(transaction.user_id, transaction.order_type)

	data_dict = {
		'trans_code': 'CXL',
		'trans_no': trans_no,
		'user_id': settings.USERID[settings.LIVE],	
		'password': pass_dict['password'],
		'pass_key': pass_dict['passkey'],
		'internal_transaction': transaction.id, 
		## not reqd by BSE. added for easier tracking internally
		'client_code': transaction.user_id,
		'member_id': settings.MEMBERID[settings.LIVE], 
	}
	## depening on whether lumpsum order or xsip order, change data_dict and apply different form 
	if (transaction.order_type == '2'):
		data_dict['xsip_reg_id'] = order_id
		form = CxlXsipOrderForm(data_dict)
	elif (transaction.order_type == '1'):
		data_dict['order_id'] = order_id
		form = CxlOrderForm(data_dict)
	else:
		raise Exception(
			"Internal error 630: Invalid order_type in transaction table: "
		)

	# form.is_valid() calls form.clean() as well as model.full_clean()
	# so validators on model are also applied
	if form.is_valid():
		bse_transaction = form.save()
		# print bse_transaction
		return bse_transaction
	else:
		raise Exception(
			'BSE error 650: %s' % form.errors
		)


# store response to order entry from bse 
def store_order_response(response, order_type):
	## lumpsum order 
	if (order_type == '1'):
		trans_response = TransResponseBSE(
			trans_code = response[0],
			trans_no = response[1],
			order_id = response[2],
			user_id = response[3],
			member_id = response[4],
			client_code = response[5],
			bse_remarks = response[6],
			success_flag = response[7],
			order_type = '1',
		)
	## SIP order  
	elif (order_type == '2'):
		trans_response = TransResponseBSE(
			trans_code = response[0],
			trans_no = response[1],
			member_id = response[2],
			client_code = response[3],
			user_id = response[4],
			order_id = response[5],
			bse_remarks = response[6],
			success_flag = response[7],
			order_type = '2',
		)
	trans_response.save()
	return trans_response.order_id


# prepare the string that will be sent as param for user creation in bse
def prepare_user_param(client_code):
	# extract the records from the table
	info = Info.objects.get(id=client_code)
	kyc = KycDetail.objects.get(user=client_code)
	bank = BankDetail.objects.get(user=client_code)
	
	# some fields require processing
	## address field can be 40 chars as per BSE but RTA is truncating it to 30 chars and showing that in account statement which is confusing customers, so reducing the length to 30 chars
	add1 = kyc.address[:30]
	if (len(kyc.address) > 30):
		add2 = kyc.address[30:60]
		if (len(kyc.address) > 60):
			add3 = kyc.address[60:90]
		else:
			add3 = ''
	else:
		add2 = add3 = ''
	appname1 = kyc.first_name
	if (kyc.middle_name != ''):
		appname1 = appname1 + ' ' + kyc.middle_name
	if (kyc.last_name != ''):
		appname1 = appname1 + ' ' + kyc.last_name
	appname1 = appname1[:70]
	
	ifsc_code = bank.branch.ifsc_code

	# make the list that will be used to create param
	param_list = [
		('CODE', client_code),
		('HOLDING', 'SI'),
		('TAXSTATUS', kyc.tax_status),
		('OCCUPATIONCODE', kyc.occ_code),
		('APPNAME1', appname1),
		('APPNAME2', ''),
		('APPNAME3', ''),
		('DOB', kyc.dob),
		('GENDER', kyc.gender),
		('FATHER/HUSBAND/gurdian', ''),
		('PAN', kyc.pan),
		('NOMINEE', ''),
		('NOMINEE_RELATION', ''),
		('GUARDIANPAN', ''),
		('TYPE', 'P'),
		('DEFAULTDP', ''),
		('CDSLDPID', ''),
		('CDSLCLTID', ''),
		('NSDLDPID', ''),
		('NSDLCLTID', ''),
		('ACCTYPE_1', bank.account_type_bse),
		('ACCNO_1', bank.account_number),
		('MICRNO_1', ''),
		('NEFT/IFSCCODE_1', ifsc_code),
		('default_bank_flag_1', 'Y'),
		('ACCTYPE_2', ''),
		('ACCNO_2', ''),
		('MICRNO_2', ''),
		('NEFT/IFSCCODE_2', ''),
		('default_bank_flag_2', ''),
		('ACCTYPE_3', ''),
		('ACCNO_3', ''),
		('MICRNO_3', ''),
		('NEFT/IFSCCODE_3', ''),
		('default_bank_flag_3', ''),
		('ACCTYPE_4', ''),
		('ACCNO_4', ''),
		('MICRNO_4', ''),
		('NEFT/IFSCCODE_4', ''),
		('default_bank_flag_4', ''),
		('ACCTYPE_5', ''),
		('ACCNO_5', ''),
		('MICRNO_5', ''),
		('NEFT/IFSCCODE_5', ''),
		('default_bank_flag_5', ''),
		('CHEQUENAME', ''),
		('ADD1', add1),
		('ADD2', add2),
		('ADD3', add3),
		('CITY', kyc.city),
		('STATE', kyc.state),
		('PINCODE', kyc.pincode),
		('COUNTRY', 'India'),
		('RESIPHONE', ''),
		('RESIFAX', ''),
		('OFFICEPHONE', ''),
		('OFFICEFAX', ''),
		('EMAIL', info.email),
		('COMMMODE', 'M'),
		('DIVPAYMODE', '02'),
		('PAN2', ''),
		('PAN3', ''),
		('MAPINNO', ''),
		('CM_FORADD1', ''),
		('CM_FORADD2', ''),
		('CM_FORADD3', ''),
		('CM_FORCITY', ''),
		('CM_FORPINCODE', ''),
		('CM_FORSTATE', ''),
		('CM_FORCOUNTRY', ''),
		('CM_FORRESIPHONE', ''),
		('CM_FORRESIFAX', ''),
		('CM_FOROFFPHONE', ''),
		('CM_FOROFFFAX', ''),
		('CM_MOBILE', kyc.phone),
	]

	# prepare the param field to be returned
	user_param = ''
	for param in param_list:
		user_param = user_param + '|' + str(param[1])
	# print user_param
	return user_param[1:]


# prepare the string that will be sent as param for fatca creation in bse
def prepare_fatca_param(client_code):
	# extract the records from the table
	kyc = KycDetail.objects.get(user=client_code)
	
	# some fields require processing
	inv_name = kyc.first_name
	if (kyc.middle_name != ''):
		inv_name = inv_name + ' ' + kyc.middle_name
	if (kyc.last_name != ''):
		inv_name = inv_name + ' ' + kyc.last_name
	inv_name = inv_name[:70]
	if kyc.occ_code == '01':
		srce_wealt = '02'
		occ_type = 'B'
	else:
		srce_wealt = '01'
		occ_type = 'S'

	# make the list that will be used to create param
	param_list = [
		('PAN_RP', kyc.pan),
		('PEKRN', ''),
		('INV_NAME', inv_name),
		('DOB', ''),
		('FR_NAME', ''),
		('SP_NAME', ''),
		('TAX_STATUS', kyc.tax_status),
		('DATA_SRC', 'E'),
		('ADDR_TYPE', '1'),
		('PO_BIR_INC', 'IN'),
		('CO_BIR_INC', 'IN'),
		('TAX_RES1', 'IN'),
		('TPIN1', kyc.pan),
		('ID1_TYPE', 'C'),
		('TAX_RES2', ''),
		('TPIN2', ''),
		('ID2_TYPE', ''),
		('TAX_RES3', ''),
		('TPIN3', ''),
		('ID3_TYPE', ''),
		('TAX_RES4', ''),
		('TPIN4', ''),
		('ID4_TYPE', ''),
		('SRCE_WEALT', srce_wealt),
		('CORP_SERVS', ''),
		('INC_SLAB', kyc.income_slab),
		('NET_WORTH', ''),
		('NW_DATE', ''),
		('PEP_FLAG', 'N'),
		('OCC_CODE', kyc.occ_code),
		('OCC_TYPE', occ_type),
		('EXEMP_CODE', ''),
		('FFI_DRNFE', ''),
		('GIIN_NO', ''),
		('SPR_ENTITY', ''),
		('GIIN_NA', ''),
		('GIIN_EXEMC', ''),
		('NFFE_CATG', ''),
		('ACT_NFE_SC', ''),
		('NATURE_BUS', ''),
		('REL_LISTED', ''),
		('EXCH_NAME', 'O'),
		('UBO_APPL', 'N'),
		('UBO_COUNT', ''),
		('UBO_NAME', ''),
		('UBO_PAN', ''),
		('UBO_NATION', ''),
		('UBO_ADD1', ''),
		('UBO_ADD2', ''),
		('UBO_ADD3', ''),
		('UBO_CITY', ''),
		('UBO_PIN', ''),
		('UBO_STATE', ''),
		('UBO_CNTRY', ''),
		('UBO_ADD_TY', ''),
		('UBO_CTR', ''),
		('UBO_TIN', ''),
		('UBO_ID_TY', ''),
		('UBO_COB', ''),
		('UBO_DOB', ''),
		('UBO_GENDER', ''),
		('UBO_FR_NAM', ''),
		('UBO_OCC', ''),
		('UBO_OCC_TY', ''),
		('UBO_TEL', ''),
		('UBO_MOBILE', ''),
		('UBO_CODE', ''),
		('UBO_HOL_PC', ''),
		('SDF_FLAG', ''),
		('UBO_DF', ''),
		('AADHAAR_RP', ''),
		('NEW_CHANGE', 'N'),
		('LOG_NAME', kyc.user_id),
		('DOC1', ''),
		('DOC2', ''),
	]

	# prepare the param field to be returned
	fatca_param = ''
	for param in param_list:
		fatca_param = fatca_param + '|' + str(param[1])
	# print fatca_param
	return fatca_param[1:]


# prepare the string that will be sent as param for user creation in bse
def prepare_mandate_param(client_code, amount):
	# extract the records from the table
	info = Info.objects.get(id=client_code)
	bank = BankDetail.objects.get(user=client_code)
	
	# make the list that will be used to create param
	param_list = [
		('MEMBERCODE', settings.MEMBERID[settings.LIVE]),
		('CLIENTCODE', client_code),
		('AMOUNT', amount),
		('IFSCCODE', bank.branch.ifsc_code),
		('ACCOUNTNUMBER', bank.account_number),
		('MANDATETYPE', 'X'),
	]

	# prepare the param field to be returned
	mandate_param = ''
	for param in param_list:
		mandate_param = mandate_param + '|' + str(param[1])
	# print user_param
	return mandate_param[1:]


################ FORMS to prepare data- called by PREPARE FUNCTIONS

# Used in validating fields when preparing new order entry
class NewOrderForm(forms.ModelForm):
	class Meta:
		model =  TransactionBSE
		exclude = 'dp_txn','kyc_status','euin','euin_val','dpc'


# Used in validating fields when preparing cancellation order entry
class CxlOrderForm(forms.ModelForm):
	order_id = forms.CharField(validators=[RegexValidator(r'^[0-9]*$')], max_length=8)
	class Meta:
		model =  TransactionBSE
		fields = 'trans_code','trans_no','order_id','user_id','password','pass_key','internal_transaction','client_code','member_id'


# Used in validating fields when preparing new XSIP order entry
class NewXsipOrderForm(forms.ModelForm):
	class Meta:
		model =  TransactionXsipBSE
		exclude = 'trans_mode','dp_txn','freq_type','freq_allowed','euin','euin_val','dpc'


# Used in validating fields when preparing cancellation XSIP order entry
class CxlXsipOrderForm(forms.ModelForm):
	xsip_reg_id = forms.CharField(validators=[RegexValidator(r'^[0-9]*$')], max_length=10)
	class Meta:
		model =  TransactionXsipBSE
		fields = 'trans_code','trans_no','xsip_reg_id','user_id','password','pass_key','internal_transaction','client_code','member_id'


################ HELPER SOAP FUNCTIONS

# every soap query to bse must have wsa headers set 
def soap_set_wsa_headers(method_url, svc_url):
	from zeep import xsd
	header = xsd.Element(None, xsd.ComplexType([
        xsd.Element('{http://www.w3.org/2005/08/addressing}Action', xsd.String()),
        xsd.Element('{http://www.w3.org/2005/08/addressing}To', xsd.String())
        ])
    )
	header_value = header(Action=method_url, To=svc_url)
	# print header_value
	return header_value


# set logging such that its easy to debug soap queries
def set_soap_logging():
	import logging.config
	logging.config.dictConfig({
	    'version': 1,
	    'formatters': {
	        'verbose': {
	            'format': '%(name)s: %(message)s'
	        }
	    },
	    'handlers': {
	        'console': {
	            'level': 'DEBUG',
	            'class': 'logging.StreamHandler',
	            'formatter': 'verbose',
	        },
	    },
	    'loggers': {
	        'zeep.transports': {
	            'level': 'DEBUG',
	            'propagate': True,
	            'handlers': ['console'],
	        },
	    }
	})

