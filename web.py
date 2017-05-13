''' 
Author: utkarshohm
Description: crawl BSEStar web portal (bsestrmf.in) to update transaction status
    because API endpoints are not provided for this. These crawling functions are resilient to handle
    common crawling exceptions because crawling often encounters errors in html rendering or data loading
'''

from django.db.models import Q

# for crawling
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException, 
    ErrorInResponseException, ElementNotVisibleException, UnexpectedAlertPresentException, NoAlertPresentException
from httplib import BadStatusLine

# for datetime processing
from pytz import timezone
from datetime import datetime, timedelta, date
from time import strptime, sleep
from dateutil.relativedelta import relativedelta

from models.users import Info
from models.funds import FundScheme
from models.transactions import Transaction, TransResponseBSE
import settings


################### MAIN FUNCTIONS - called by management commands transact_using_api and track_status_using_api_and_web

def crawl_to_update_transaction_status():
    '''
    Sets up webdriver and selenium for crawling to update_transaction_status()
    '''
    driver = init_driver()     
    try:
        driver = login(driver)
        driver = update_transaction_status(driver)
    finally:
        quit_driver(driver)


################### Crawling setup functions

def init_driver():
    '''
    Initialize driver based on headless or chrome browser
    For automated crawling on a linux server, prefer headless
    '''
    return init_driver_headless()
    # return init_driver_chrome()


def init_driver_headless():
    '''
    Initialize headless browser. it needs a virtual display
    '''
    from pyvirtualdisplay import Display
    global Display  # global variable because its needed in quit_driver()
    display = Display(visible = 0, size = (1024, 768))
    display.start()
    print "display initialized for headless browser"
    
    driver = webdriver.Firefox()
    return driver


def init_driver_chrome():
    '''
    Initialize chrome browser. it needs a webdriver service
    '''
    import selenium.webdriver.chrome.service as service
    global service  # global variable because its needed in quit_driver()
    service = service.Service('chromedriver')
    service.start()
    print "service initialized for chrome browser"
    
    capabilities = {'chrome.loadAsync': 'true'}
    driver = webdriver.Remote(service.service_url, capabilities)
    driver.wait = WebDriverWait(driver, 5)
    driver.implicitly_wait(10)
    return driver


def login(driver):
    '''
    Logs into the BSEStar web portal using login credentials defined in settings
    '''
    try:
        line = "https://www.bsestarmf.in/Index.aspx"
        driver.get(line)
        print("Opened login page")
        
        # enter credentials
        userid = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "txtUserId")))
        memberid = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "txtMemberId")))
        password = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "txtPassword")))
        userid.send_keys(settings.USERID[settings.LIVE])
        memberid.send_keys(settings.MEMBERID[settings.LIVE])
        password.send_keys(settings.PASSWORD[settings.LIVE])
        submit = driver.find_element_by_id("btnLogin")
        submit.click()
        print("Logged in")
        return driver

    except (TimeoutException, NoSuchElementException, StaleElementReferenceException, 
        ErrorInResponseException, ElementNotVisibleException):
        print("Retrying in login")
        return login(driver)

    except (BadStatusLine):
        print("Retrying for BadStatusLine in login")
        driver = init_driver()
        return login(driver)


def quit_driver(driver):
    driver.quit()
    
    # when using headless browser
    display.stop()
        
    # when using chrome browser
    # service.stop()
    

def make_ready(driver):
    '''
    Waits for dom to be rendered before returning
    Useful when crawling BSEStar because it has dynamic pages that refresh page without changing url 
    '''
    while driver.execute_script('return document.readyState;') != 'complete':
        pass


###################### helper functions for crawling bsestar   

def update_transaction_status(self, driver):
    '''
    Updates status of all transactions that need a status update (i.e. not completed or failed)
    incl SIP transactions which have instalment order due today
    '''
    try:
        # order_id (identifier of each transaction on BSEStar) is necessary to check status on web portal
        # its returned by create_transaction_bse() api call but
        # SIP investments constitute of several instalments each of which has an order_id
        # so, save order_id of all sip instalment orders that are due today
        dt = date.today()
        find_sip_order_id(driver, dt)
        
        # update status of all orders incl sip instalment orders
        update_order_status(driver)
        return driver

    except (TimeoutException, StaleElementReferenceException, ErrorInResponseException, ElementNotVisibleException):
        print("Retrying")
        return update_transaction_status(driver)

    except (BadStatusLine):
        print("Retrying for BadStatusLine in login")
        driver = init_driver()     
        driver = login(driver)
        return update_transaction_status(driver)


def calculate_order_date(self, order_dt):
    '''
    Checks if BSE was open for MF transactions at the datetime when order was placed (order_dt)
    If it was not, then which is the next date when market was open and order would get placed
    Uses market_dates.csv which has list of all dates when BSE was open for MF transactions
    Uses 1500 hours as cut off time when BSE closes for MF transactions
    '''
    if order_dt.hour >= 15:
        order_dt += timedelta(days=1)
    order_d = order_dt.date()
    lines = open('requirements/market_dates.csv', 'r').read().splitlines()
    for line in lines:
        market_date = date(*(strptime(line.strip(), '%d/%m/%y')[0:3]))
        if market_date >= order_d:
            return market_date
    # error 
    return False


def update_order_status(self, driver):
    '''
    Updates status (see field status in Transaction model in transactions) of transactions
    BSEStar hasn't implemented this as an API endpoint so it needs crawling of bsestarmf.in
    '''

    ## fetch the transactions that need to be updated
    tr_queryset = Transaction.objects.filter(
            Q(status__in=('2','4','5')) |
            Q(status='6', order_type='2')
        ).order_by(
            'created'
        )
    tr_list = []
    for tr in tr_queryset:
        ## remove sip transactions whose instalment is not under process
        if tr.order_type == '2' and tr.sip_num_inst_done == len(tr.sip_dates.split(',')):
            pass
        else:
            tr_list.append(tr) 

    ## process transaction time to find order date
    date_dict_list = []
    date_dict = None
    prev_order_d = date(2016, 1, 1)
    for tr in tr_list:
        ## get date of order
        order_dt = tr.created.replace(tzinfo=timezone('UTC')).astimezone(timezone('Asia/Calcutta'))
        if tr.order_type == '1':
            ## get order_id of the transaction  
            order_id = TransResponseBSE.objects.get(trans_no=tr.bse_trans_no).order_id
        else:
            order_ids = tr.sip_order_ids.split(',')
            if len(order_ids) > tr.sip_num_inst_done: 
                order_id = order_ids[tr.sip_num_inst_done]
                if len(order_ids) > 1:
                    ## update order_dt because its a sip instalment
                    order_dt = datetime(*(strptime(tr.sip_dates.split(',')[tr.sip_num_inst_done], "%d%m%y")[0:3]))
                    print order_dt
            else:
                ## problem in sip_order_ids field
                raise Exception(
                    "Update order status: order id not found in Transaction table"
                )
        
        ## dont check for orders/instalments which will be placed in future
        if order_dt.date() > date.today():
            continue
        order_d = self.calculate_order_date(order_dt)
        
        ## raise exception as no order date found
        if not order_d:
            raise Exception(
                "Update order status: order date could not be found"
            )
        
        ## dont check for orders/instalments which are offline currently
        elif order_d > date.today():
            continue
        
        ## save order id and date
        if prev_order_d != order_d:
            date_dict = {
                'date': order_d,
                'ids': [tr.id],
                'order_ids': [order_id],
                'status': ['0'],
                'folio': [''],
            }
            date_dict_list.append(date_dict)
            prev_order_d = order_d
        else: 
            date_dict['ids'].append(tr.id)
            date_dict['order_ids'].append(order_id)
            date_dict['status'].append('0')
            date_dict['folio'].append('')
    
    ## crawl to get orders by date
    for date_dict in date_dict_list:
        ## navigate to page
        line = "https://www.bsestarmf.in/RptOrderStatusReportNew.aspx"
        driver.get(line)
        print (driver.title)
        date = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, 'txtToDate')))
        date.clear()
        date.send_keys(date_dict['date'].strftime("%d-%b-%Y"))
        sleep(2)    # needed as page refreshes after setting date
        # make_ready(driver)

        submit = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "btnSubmit")))
        submit.click()
        sleep(2)
        # make_ready(driver)
        
        ## parse the table- find orders for this date
        table = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, "//table[@class='glbTableD']/tbody")))
        print ('html loading done')
        rows = table.find_elements(By.XPATH, "tr[@class='tblERow'] | tr[@class='tblORow']")

        for row in rows:
            fields = row.find_elements(By.XPATH, "td")
            order_id = fields[3].text
            status = fields[18].text
            if status == "ALLOTMENT DONE":
                status = '6'
            elif status == "SENT TO RTA FOR VALIDATION":
                status = '5'
            elif status == "ORDER CANCELLED BY USER":
                status = '1'
            elif status == "PAYMENT NOT RECEIVED TILL DATE":
                status = '-1'

            # match with list of order ids
            for i in range(0, len(date_dict['ids'])):
                if order_id == date_dict['order_ids'][i]:
                    date_dict['status'][i] = status
                    date_dict['folio'][i] = fields[15].text
                    print "found", order_id, status
                    break
            
    ## save status in db
    for date_dict in date_dict_list:
        for i in range(0, len(date_dict['ids'])):
            if date_dict['status'][i] != '0':
                tr = Transaction.objects.get(id=date_dict['ids'][i])
                ## one-time or 1st isnt of sip transaction 
                if tr.status in ['2','4','5']:
                    ## update status and status_comment
                    if date_dict['status'][i] == '-1':
                        if tr.status == '2':
                            tr.status_comment = 'Failed due to no payment'
                        else:
                            tr.status_comment = 'Failed due to error in payment'
                        tr.status = '1'
                    ## update status, folio, datetime
                    elif date_dict['status'][i] == '6':
                        tr.status = date_dict['status'][i]
                        if date_dict['folio'][i] != '':
                            tr.folio_number = date_dict['folio'][i]
                        if tr.order_type == '2':
                            tr.sip_num_inst_done = 1
                        tr.datetime_at_mf = datetime(date_dict['date'].year, date_dict['date'].month, date_dict['date'].day, 12, 0, 0, tzinfo=timezone('UTC'))
                    else:
                        tr.status = date_dict['status'][i]
                
                ## 2nd or later inst of sip transaction 
                elif tr.status == '6' and tr.order_type == '2':
                    if date_dict['status'][i] == '6':
                        ## update sip_num_inst_done as instalment successful
                        tr.sip_num_inst_done += 1
                        if tr.sip_num_inst_done == tr.sip_num_inst:
                            ## update to sip concluded 
                            tr.status = '8'
                    elif date_dict['status'][i] in ['-1', '1']:
                        ## update sip_dates and sip_order_ids as instalment was unsuccessful
                        last_pos = tr.sip_dates.rfind(',')
                        tr.sip_dates = tr.sip_dates[:last_pos]
                        last_pos = tr.sip_order_ids.rfind(',')
                        tr.sip_order_ids = tr.sip_order_ids[:last_pos]     
                tr.save()

    ## this is a good place to put in a slack alert
    
    
def find_sip_order_id(self, driver, today):
    '''
    Finds order ID (identifier of each transaction on BSEStar) for all sip instalments due today
    Order ID is necessary to check status on web portal
    SIP investments constitute of several instalments each of which has an order ID
    BSEStar hasn't implemented this as an API endpoint so it needs crawling of bsestarmf.in
    '''

    ## fetch sip transactions due today
    sip_list = Transaction.objects.filter(
            order_type='2',
            status__in=('2','4','5','6'),
        )

    tr_list = []
    for sip in sip_list:
        ## first instalment
        if sip.status != '6':
            order_dt = sip.created.replace(tzinfo=timezone('UTC')).astimezone(timezone('Asia/Calcutta'))
            ## use below line if sip order was placed with first order not today
            # order_dt = datetime.strptime(str(sip.sip_start_date), "%Y-%m-%d").replace(tzinfo=timezone('UTC')).astimezone(timezone('Asia/Calcutta'))
        ## second or later instalment
        ## filtering for those that are not already populated
        elif len(sip.sip_dates.split(',')) == sip.sip_num_inst_done:
            order_dt = datetime.strptime(str(sip.sip_start_date), "%Y-%m-%d") + relativedelta(months=sip.sip_num_inst_done - 1)
            ## dont check for orders/instalments which will be placed in future
            if order_dt.date() > today:
                continue
        ## order id and date already populated
        else:
            continue
        ## find exact order date 
        order_d = self.calculate_order_date(order_dt)
        if not order_d:
            # raise exception as no order date found
            raise Exception(
                "Find sip order id: order date not found for transaction %d" % sip.id
            )
        if order_d == today:
            tr_list.append(sip)
    print "%d sip orders to be placed today" % len(tr_list)

    if len(tr_list) > 0:
        ## navigate to page
        # line = "https://www.bsestarmf.in/ViewOrder.aspx"
        line = "https://www.bsestarmf.in/RptProvisionalOrderReportNew.aspx"
        driver.get(line)
        print (driver.title)
        dt = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, 'txtToDate')))
        dt.clear()
        dt.send_keys(today.strftime("%d-%b-%Y"))
        sleep(2)    # needed as page refreshes after setting date
        # make_ready(driver)
        
        submit = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "btnSubmit")))
        submit.click()
        sleep(2)
        # make_ready(driver)
        
        ## parse table of orders to get order id
        table = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, "//table[@class='glbTableD']/tbody")))
        print ('html loading done')
        rows = table.find_elements(By.XPATH, "tr[@class='tblERow'] | tr[@class='tblORow']")
        print len(rows)
        for row in rows:
            fields = row.find_elements(By.XPATH, "td")
            order_id = fields[5].text
            if order_id == '':
                continue
            # isin = fields[6].text
            # user_id = fields[8].text
            # amount = fields[12].text
            sip_reg_no = fields[24].text

            # match orders with list of sip transactions
            for tr in tr_list:
                try:
                    # if isin == tr.scheme_plan.isin and user_id== tr.user_id and amount == tr.amount and len(tr.sip_dates) == tr.sip_num_inst_done:
                    if sip_reg_no == TransResponseBSE.objects.get(trans_no=tr.bse_trans_no).order_id:
                        ## save order id and date in table
                        if tr.status != '6':
                            tr.sip_dates = today.strftime("%d%m%y")
                            tr.sip_order_ids = order_id
                        else:
                            tr.sip_dates += "," + today.strftime("%d%m%y")
                            tr.sip_order_ids += "," + order_id
                        tr.save()
                        print "found and saved", tr.id, sip_reg_no, order_id
                        break
                except Exception as e:
                    print e, tr.id, today, len(tr.sip_order_ids)

    ## this is a good place to put in a slack alert
