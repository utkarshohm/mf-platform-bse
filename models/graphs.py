from django.db import models
from mongoengine import *


class FundTimeSeries(Document):
	'''
	Stores time series of nav data of funds
	'''
	scheme_id = IntField()
	scheme_name =  StringField()

	nav_data = ListField()
	start_date = DateTimeField()
	end_date = DateTimeField()


class IndexTimeSeries(Document):
	'''
	Stores time series of daily value of indices like BSE Sensex, NSE Nifty, SBI 
	fixed deposit etc
	'''
	index_id = IntField()
	index_name = StringField()

	data = ListField()
	start_date = DateTimeField()
	end_date = DateTimeField()

