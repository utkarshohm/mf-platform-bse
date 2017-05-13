# mutual-fund-platform
Python library to programmaticaly purcahse/redeem mutual funds in India using the Bombay Stock Exchange StarMF platform's API and web portal

## Context
### Real-life application of library
I built and operated a mutual fund investing platform as an AMFI licensed mutual fund distributor for a year. I used the library to programmatically make and track over Rs 50 lacs of investment for several investors. It was built over a week in Sep 2016 and works as of May 2017. Since my investing website was built on django, you will see some parts of that in the code though django is an optional requirement. You can build this platform without or with any other framework of your choice.

### Open source in fintech?!
The finance industry believes that differentiation in fintech can come from building an execution/transaction platform. I believe on the contrary that execution will soon be commoditized and differentiation will come from better products, ease of their use and large-scale distribution. This is why I am open-sourcing my mutual fund execution platform.

### About BSE Star MF
Bombay Stock Exchange runs a MF execution platform called StarMF. Distributors like me can plug into it and place transactions in any mutual fund without setting up a payment gateway, settlement system or signing agreements directly with MF companies. BSEStarMF offers
* a SOAP API for placing transactions. I used [their latest API guide](https://drive.google.com/open?id=0B14TggftWFLzZE9SUUdXa1VaUDA) when building this library.
* a [web portal](https://bsestarmf.in) which has comprehensive capabilities including those that the API doesn't offer like tracking status of transactions. Each transaction depends on multiple stakeholders - RTA (tech provider of MF company), KRA (user KYC verified?), bank (payment received?) and BSE (all necessary data about user received?), hence tracking status is critical for building a mutual fund investing platform.

## Code
### Critical code
Meat of the library is in 2 files:
* `api.py` has all functions necessary to transact in mutual funds using its SOAP API
  1. `create_user_bse()` registers a user on BSEStarMF corresponding to your user with kyc and bank details. Pre-requisite for all other API endpoints
  2. `create_mandate_bse()` registers a mandate (instruction given to debit bank account periodically for a specific amount) for a user. Pre-requisite for creating SIP transaction. 
  3. `create_transaction_bse()` creates a purchase/redeem one-time/SIP transaction
  4. `cancel_transaction_bse()` cancels a transaction
  5. `get_payment_link_bse()` gets a link that can be used by user to pay for his/her investments
  6. `get_payment_status_bse()` gets whether payment for a transaction was approved by the user's bank or not
* `web.py` crawls the web portal to update transaction status
  1. `update_transaction_status()` updates status of all transactions that need a status update (i.e. not completed or failed). Importantly this includes SIP transactions which have an instalment order due today. Once an SIP transaction was succesfully processed, BSEStarMF keeps auto-trigerring each instalment on the right date and this status updater keeps tracking these auto-trigerred instalment orders. 

### Supporting code
#### Models
3 key data structures are necessary for a mutual fund transaction platform. Regulations require to carefully archive this data for 5 years. 
* `funds.py` stores mutual fund schemes' official SID details, ratings, returns, owner, rta, managers, benchmark indices, portfolio and history.
* `graphs.py` stores time series data of funds and indices (like BSE Sensex, SBI fixed deposit rate), at daily frequency. 
* `users.py` stores kyc, bank, fatca and mandate details for each investor.
* `transactions.py` stores each purcahse/redeem transaction's key details incl status, datetime stamps, payment details,  corresponding API queries made to BSEStarMF and corresponding responses received.
You can find more detailed models in a [separate repo](https://github.com/utkarshohm/mutual-fund-models) with discussion on [choice of database](https://github.com/utkarshohm/mutual-fund-models#models) for these models. Note that several models in this repo are not directly used for placing transactions through BSE but are required for a mutual fund platform.

#### Requirements
##### Necessary
* `market_dates.csv` stores all the dates on which BSE was open for financial transactions
* [zeep](https://github.com/mvantellingen/python-zeep) used as a python SOAP client
* [selenium](https://github.com/SeleniumHQ/selenium) used to automate browsing of web portal
* [pyvirtualdisplay](https://github.com/ponty/PyVirtualDisplay) used to create a virtual display necessary for a headless browser
##### Optional
* django, mysql and mongo - for models and management commands. Note that you DON'T need it. I have kept parts of django because I used it originally in my website. Feel free to remove it or replace it with 
* [chromedriver](https://sites.google.com/a/chromium.org/chromedriver/downloads) used with selenium for browsing using chrome browser. Its executable must be downloaded separately.

#### How to use the API and web crawler?
These 2 files show how to use `api.py` and `web.py` in your code. I have used [django management commands](http://janetriley.net/2014/11/quick-how-to-custom-django-management-commands.html) for easy demonstration, but treat them as simple python files  
* `transact_using_api.py` shows how to use the api functions to transact
* `update_transaction_status.py` shows how to use api functions and web crawling to periodically update status of transactions. It should be run using a cron job on every day that the market is open, at 10:05 am (after market opens), 3:05 pm (after market closes for MF transactions) and 6:05 pm (after transactions have been processed).

## Need help setting this up or want to contribute?
Feel free to raise an issue and I will get back asap
