from django.db import models
from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator


class Info(models.Model):
	'''
	Internal User table
	'''
	email = models.CharField(max_length=255, unique=True)


class KycDetail(models.Model):
	'''
	Stores all kyc details of user
	Written as per BSEStar API documentation for user creation endpoint
	'''
	user = models.OneToOneField(Info, on_delete=models.PROTECT, related_name='kycdetail',  related_query_name="kycdetail")

	OCCUPATION = (
		('01', 'Business'),
		('02', 'Services'),
	)
	GENDER = (
		('M', 'Male'),
		('F', 'Female'),
	)
	STATE = (
		('AN', 'Andaman & Nicobar'),
		('AR', 'Arunachal Pradesh'),
		('AP', 'Andhra Pradesh'),
		('AS', 'Assam'),
		('BH', 'Bihar'),
		('CH', 'Chandigarh'),
		('CG', 'Chhattisgarh'),
		('DL', 'Delhi'),
		('GO', 'GOA'),
		('GU', 'Gujarat'),
		('HA', 'Haryana'),
		('HP', 'Himachal Pradesh'),
		('JM', 'Jammu & Kashmir'),
		('JK', 'Jharkhand'),
		('KA', 'Karnataka'),
		('KE', 'Kerala'),
		('MP', 'Madhya Pradesh'),
		('MA', 'Maharashtra'),
		('MN', 'Manipur'),
		('ME', 'Meghalaya'),
		('MI', 'Mizoram'),
		('NA', 'Nagaland'),
		('ND', 'New Delhi'),
		('OR', 'Orissa'),
		('PO', 'Pondicherry'),
		('PU', 'Punjab'),
		('RA', 'Rajasthan'),
		('SI', 'Sikkim'),
		('TG', 'Telengana'),
		('TN', 'Tamil Nadu'),
		('TR', 'Tripura'),
		('UP', 'Uttar Pradesh'),
		('UC', 'Uttaranchal'),
		('WB', 'West Bengal'),
		('DN', 'Dadra and Nagar Haveli'),
		('DD', 'Daman and Diu'),
	)
	INCOMESLAB = (
		(31, 'Below 1 Lakh'),
		(32, '> 1 <=5 Lacs'),
		(33, '>5 <=10 Lacs'),
		(34, '>10 <= 25 Lacs'),
		(35, '> 25 Lacs < = 1 Crore'),
		(36, 'Above 1 Crore'),
	)
	pan_regex = RegexValidator(regex=r'^[A-Za-z]{5}[0-9]{4}[A-Za-z]{1}$', message="Pan number must be entered in the format: AAAAA1111A")
	dob_regex = RegexValidator(regex=r'^[0-9]{2}\/[0-9]{2}\/[0-9]{4}$', message="Date of birth must be entered in the format: 'DD/MM/YYYY'")
	pincode_regex = RegexValidator(regex=r'^\d{6}$', message="Pin code must be entered in the format: 110049")
	phone_regex = RegexValidator(regex=r'^\d{10}$', message="Phone number must be entered in the format: 9999999999")

	# most imp field
	pan = models.CharField(max_length=10,validators=[pan_regex], help_text='', blank=True)

	# fields required by bsestar client creation
	tax_status = models.CharField(max_length=2, default='01', blank=True)
	occ_code = models.CharField(max_length=2, default='02', choices= OCCUPATION, blank=True)
	first_name = models.CharField(max_length=70, blank=True)
	middle_name = models.CharField(max_length=70, blank=True)
	last_name = models.CharField(max_length=70, blank=True)
	dob = models.CharField(max_length=10, validators=[dob_regex], blank=True)
	gender = models.CharField(max_length=2, choices= GENDER, blank=True)
	address = models.CharField(max_length=120, help_text='sample: 10, Mg Road, New Delhi - 11001', blank=True)
	city = models.CharField(max_length=35, blank=True)
	state = models.CharField(max_length=2, choices= STATE, blank=True)
	pincode = models.CharField(max_length=6, validators=[pincode_regex], help_text='sample: 110049', blank=True)
	phone = models.CharField(max_length=10, validators=[phone_regex], help_text='sample: 9999999999', blank=True)
	
	# Addl KYC and fatca details
	## there are a bunch of fields that can be filled based on above fields or hard-coded which
	## have not been included here like country of citizenship, politically exposed etc
	income_slab = models.CharField(max_length=2, default='34', choices= INCOMESLAB, blank=True)
	
	updated = models.DateTimeField(auto_now=True, auto_now_add=False)
	created = models.DateTimeField(auto_now_add=True)


class BankRepo(models.Model):
	'''
	Repository of bank names for user's bank detail model
	Used by BranchRepo
	'''
	name = models.CharField(max_length=100, blank=False, unique=True)


class BranchRepo(models.Model):
	'''
	Repository of branch details for user's bank detail model
	Used by BankDetail
	'''
	ifsc_code_regex = RegexValidator(regex=r'^[^\w]{11}$', message="IFSC code must be in the format: HDFC0000291")
	micr_code_regex = RegexValidator(regex=r'^\w{9}$', message="MICR code must be entered in the format: 110240212")

	bank = models.ForeignKey(BankRepo, on_delete=models.PROTECT, related_name='branchrepos', related_query_name="branchrepo")
	branch_name = models.CharField(max_length=100, blank=False)
	branch_city = models.CharField(max_length=35, blank=False)
	branch_address = models.CharField(max_length=250, blank=True)
	ifsc_code = models.CharField(max_length=11, validators=[ifsc_code_regex], blank=False, unique=True)
	micr_code = models.CharField(max_length=9, validators=[micr_code_regex], blank=True)


class BankDetail(models.Model):
	'''
	Stores bank details of user
	Written as per BSEStar API documentation for user creation endpoint
	'''
	user = models.ForeignKey(Info, on_delete=models.PROTECT, related_name='bankdetail', related_query_name="bankdetail")
	branch = models.ForeignKey(BranchRepo, on_delete=models.PROTECT, related_name='bankdetails', related_query_name="bankdetail", blank=True, null=True)

	account_number_regex = RegexValidator(regex=r'^\d{9,16}$', message="Account number must be between 9 and 16 chars long")
	ACCOUNTTYPE = (
		('SB', 'Savings'),
		('CB', 'Current'),
		('NE', 'NRE'),
		('NO', 'NRO'),
	)

	account_number = models.CharField(max_length=20, validators=[account_number_regex], blank=False)
	account_type_bse = models.CharField(max_length=2, choices=ACCOUNTTYPE, default='SB', blank=False)
	
	updated = models.DateTimeField(auto_now=True, auto_now_add=False)
	created = models.DateTimeField(auto_now_add=True)


class Mandate(models.Model):
	'''
	Stores mandates registered in BSE for user
	Written as per BSEStar API documentation for mandate creation endpoint
	Entry created in table only after calling endpoint
	'''
	user = models.ForeignKey(Info, on_delete=models.PROTECT, related_name='mandate',  related_query_name="mandate")
	bank = models.ForeignKey(BankDetail, on_delete=models.PROTECT, related_name='mandate',  related_query_name="mandate")
	id = models.CharField(max_length=10, blank=False, primary_key=True)

	STATUS = (
		(0, 'Created'),
		(1, 'Cancelled'),
		(2, 'Registered in BSE'),
		(3, 'Form submitted to BSE'),
		(4, 'Received by BSE'),
		(5, 'Accepted by BSE'),
		(6, 'Rejected by BSE'),
		(7, 'Exhausted'),
	)
	
	status = models.CharField('Journey Status', max_length=2, choices=STATUS, null=False, default='0')
	amount = models.FloatField(validators=[MinValueValidator(0), MaxValueValidator(1000000)], blank=True, null=True)
	
	updated = models.DateTimeField(auto_now=True, auto_now_add=False)
	created = models.DateTimeField(auto_now_add=True)

