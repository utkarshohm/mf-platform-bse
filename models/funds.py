from django.db import models
from django.core.validators import MaxValueValidator, MinValueValidator


class RTA(models.Model):
    '''
    Stores RTA (agency that processes transactions for a FundHouse) details
    Like CAMS, KARVY etc
    '''
    rta_name = models.CharField(max_length=100, blank=True, unique=True)
    rta_address = models.CharField(max_length=500, blank=True)
    rta_email = models.EmailField(max_length=50, blank=True)
    rta_website = models.URLField(max_length=50, blank=True)
    rta_phone = models.CharField(max_length=100, blank=True)
    rta_fax = models.CharField(max_length=100, blank=True)


class FundHouse(models.Model):
    '''
    Stores mutual fund company (called AMC in jargon) details
    Like HDFC MF, ICICI MF, Birla Sun Life MF, Reliance MF etc
    '''
    rta = models.ForeignKey(RTA, on_delete=models.PROTECT, blank=True, null=True)
    
    # key details
    amc_code = models.CharField(max_length=3, blank=False, verbose_name='AMC Code')
    name = models.CharField(max_length=100, unique=True)
    launch_date = models.DateField(auto_now=False, auto_now_add=False, blank=True, null=True)
    total_aum = models.FloatField(blank=True, null=True)  # in Rs cr
    
    # rank based on key metrics
    rank_aum = models.IntegerField(validators=[MinValueValidator(1)], blank=True, null=True)
    rank_fund_ratings = models.IntegerField(validators=[MinValueValidator(1)], blank=True, null=True)
    
    # metadata
    address = models.CharField(max_length=500, blank=True)
    email = models.EmailField(max_length=50, blank=True)
    website = models.URLField(max_length=50, blank=True)
    phone = models.CharField(max_length=100, blank=True)
    fax = models.CharField(max_length=100, blank=True)
    
    # available for transaction through BSEStar
    bse_open = models.BooleanField(default=False)


class FundCategory(models.Model):
    '''
    Stores mutual fund category details. you can classify funds as you like
    Like liquid, debt, large cap equity, small cap equity, tax saver (jargon: ELSS), etc
    '''
    name = models.CharField(max_length=100, unique=True, blank=True)
    num_funds = models.IntegerField(null=True)

    
class FundManager(models.Model):
    '''
    Stores mutual fund manager details. each FundScheme has a manager
    Like HDFC MF, ICICI MF, Birla Sun Life MF, Reliance MF, Mirae Asset MF etc
    '''
    name = models.CharField(max_length=100, unique=True)
    education = models.CharField(max_length=200, blank=True)
    experience = models.CharField(max_length=500, blank=True)
    scheme_history = models.TextField(blank=True)
    date_history = models.TextField(blank=True)
    num_fund_ratings = models.IntegerField(null=True)
    avg_fund_ratings = models.FloatField(null=True)
    rank_fund_ratings = models.IntegerField(validators=[MinValueValidator(1)], blank=True, null=True)


class Exchange(models.Model):
    '''
    Stores Exchange details. every Exchange has multiple BenchmarkIndex
    Like BSE, NSE etc
    '''
    name = models.CharField(max_length=100, blank=True)


class BenchmarkIndex(models.Model):
    '''
    Stores Benchmark Index details. every FundScheme declares a BenchmarkIndex that it tries to beat
    Like BSE Sensex, NSE Nifty, NSE Nifty Junior etc
    '''
    exchange = models.ForeignKey(Exchange, on_delete=models.PROTECT, blank=True, null=True)
    name = models.CharField(max_length=100, blank=True)
    avg_return = models.FloatField(null=True)
    min_return = models.FloatField(null=True)
    max_return = models.FloatField(null=True)


# Most imp model
class FundScheme(models.Model):
    '''
    Stores a mutual fund's details
    Like Mirae Asset Emerging Bluechip Fund, Axis Long Term Equity etc
    '''
    name = models.CharField(max_length=100, unique=True)
    fund_category = models.ForeignKey(FundCategory, on_delete=models.PROTECT, blank=True, null=True, related_name='fund_category_list')
    fund_house = models.ForeignKey(FundHouse, on_delete=models.PROTECT, blank=True, null=True, related_name='fund_house_list')

    # key details
    objective = models.CharField(max_length=1000, blank=True)
    aum = models.FloatField(blank=True, null=True)  # in Rs cr
    aum_date = models.DateField(auto_now=False, auto_now_add=False, blank=True, null=True)

    # metadata- fund category of fund as per popular sources
    category_vro = models.CharField(max_length=50, blank=True)
    category_ms = models.CharField(max_length=50, blank=True)
    category_crisil = models.CharField(max_length=50, blank=True)

    # investment styles
    inv_style_debt_vro = models.CharField(max_length=50, blank=True)
    inv_style_equity_vro = models.CharField(max_length=50, blank=True)
    inv_style_debt_ms = models.CharField(max_length=50, blank=True)
    inv_style_equity_ms = models.CharField(max_length=50, blank=True)
    
    last_updated = models.DateTimeField(auto_now=True, auto_now_add=False)


# Most imp model
class SchemePlan(models.Model):
    '''
    Stores the details of a scheme. every FundScheme has multiple SchemePlans
    Like Mirae Asset Emerging Bluechip Fund Direct Growth, Mirae Asset Emerging Bluechip Fund Direct Dividend, 
        Mirae Asset Emerging Bluechip Fund Regular Growth, Mirae Asset Emerging Bluechip Fund Regular Dividend etc
    '''
    name = models.CharField(max_length=100, unique=True)  
    fund_scheme = models.ForeignKey(FundScheme, on_delete=models.PROTECT, null=True, related_name="scheme_plan_list")
    
    # imp codes for doing transaction 
    bse_code = models.CharField(max_length=15, blank=True)
    rta_code = models.CharField(max_length=10, blank=True)
    amc_code = models.CharField(max_length=10, blank=True)
    isin = models.CharField(max_length=15, blank=True)

    # schemeplan type; figured out by parsing name of SchemePlan
    # regular, growth is most commonly transacted
    ## set true if 'direct' in name; false means regular
    if_direct = models.NullBooleanField(default=False, null=True)
    ## set false for dividend i.e. if 'dividend' in name but 'dividend yield' not in name
    if_growth = models.NullBooleanField(default=False, null=True)
    if_open = models.NullBooleanField(default=True, null=True)

    # key details
    launch_date = models.DateField(auto_now=False, auto_now_add=False, blank=True, null=True)
    asset_size = models.FloatField(blank=True, null=True)  # stale data- of direct plan  # in Rs cr
    asset_size_date = models.DateField(auto_now=False, auto_now_add=False, blank=True, null=True)
    expense_ratio = models.FloatField(validators=[MinValueValidator(0), MaxValueValidator(100)], blank=True, null=True)  # in %
    expense_ratio_date = models.DateField(auto_now=False, auto_now_add=False, blank=True, null=True)
    nav_latest = models.FloatField(blank=True, null=True)
    nav_latest_date = models.DateField(auto_now=False, auto_now_add=False, blank=True, null=True)
    
    # dividend details
    dividend_history = models.CharField(max_length=1000, blank=True)

    # ratings and other data from popular sources
    ## rating = 6 - crisil ranking
    rating_crisil = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)], default=0, blank=True, null=True)
    rating_vro = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)], default=0, blank=True, null=True)
    rating_ms = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)], default=0, blank=True, null=True)
    riskometer_crisil = models.CharField(max_length=50, blank=True)
    risk_grade_vro = models.CharField(max_length=50, blank=True)
    return_grade_vro = models.CharField(max_length=50, blank=True)

    # aggregates
    rating_average = models.FloatField(default=0, blank=True, null=True)
    rating_rank = models.FloatField(validators=[MinValueValidator(1)], default=0, blank=True, null=True)
    aum_rank = models.FloatField(validators=[MinValueValidator(1)], default=0, blank=True, null=True)
    avg_return = models.FloatField(null=True)
    min_return = models.FloatField(null=True)
    max_return = models.FloatField(null=True)   

    # min amount details
    min_inv = models.IntegerField(validators=[MinValueValidator(0)], blank=True, null=True)
    min_addl_inv = models.IntegerField(validators=[MinValueValidator(0)], blank=True, null=True)
    min_sip_inv = models.IntegerField(validators=[MinValueValidator(0)], blank=True, null=True)
    min_sip_inst = models.IntegerField(validators=[MinValueValidator(0)], blank=True, null=True)
    min_wit = models.IntegerField(validators=[MinValueValidator(0)], blank=True, null=True)
    min_sip_wit = models.IntegerField(validators=[MinValueValidator(0)], blank=True, null=True)
    min_swp_wit = models.IntegerField(validators=[MinValueValidator(0)], blank=True, null=True)
    min_bal = models.IntegerField(validators=[MinValueValidator(0)], blank=True, null=True)
    
    # sip fields
    ## available for sip?
    if_sip = models.BooleanField(default=False)
    ## list of dates of a month on which monthly sip can start
    sip_start_dates = models.CharField(max_length=200, blank=True)
    
    # exit load details
    exit_load = models.FloatField(validators=[MinValueValidator(0), MaxValueValidator(100)], blank=True, null=True)  # in %
    exit_load_comment = models.CharField(max_length=200, blank=True)

    # meta data- useful for getting rating data from popular sources
    code_ms = models.CharField(max_length=20, blank=True)
    code_vro = models.CharField(max_length=20, blank=True)
    name_crisil = models.CharField(max_length=200, blank=True)
    name_ms = models.CharField(max_length=200, blank=True)
    name_vro = models.CharField(max_length=200, blank=True)
    
    last_updated = models.DateTimeField(auto_now=True, auto_now_add=False)


class FundManagerHistory(models.Model):
    '''
    Stores which manager managed which funds from when to when
    '''
    manager = models.ForeignKey(FundManager, on_delete=models.PROTECT)
    scheme = models.ForeignKey(FundScheme, on_delete=models.PROTECT, related_name='fund_manager_list')
    start_date = models.DateField(auto_now=False, auto_now_add=False, blank=True, null=True)
    # insert start_date as date, but show only month, year
    end_date = models.DateField(auto_now=False, auto_now_add=False, blank=True, null=True)

    class Meta:
        unique_together = ("manager", "scheme")


class FundBenchmarkIndex(models.Model):
    '''
    Stores benchmark indices for a fund along with % weights as several funds follow a composition 
    of multiple indices
    '''
    fund_scheme = models.ForeignKey(FundScheme, on_delete=models.PROTECT, blank=True, null=True, related_name='fund_benchmark_list')
    benchmark_index = models.ForeignKey(BenchmarkIndex, on_delete=models.PROTECT, blank=True, null=True)
    percentage = models.FloatField(validators=[MinValueValidator(0.0), MaxValueValidator(100.0)])

    class Meta:
        unique_together = ("fund_scheme", "benchmark_index")


class DebtAsset(models.Model):
    '''
    Stores a bond's details
    Like Govt of India Bond (7% interest expiry 2020), Sriram Auto bond
    '''
    name = models.CharField(max_length=200)
    interest_rate = models.FloatField(validators=[MinValueValidator(0), MaxValueValidator(100)], blank=True,
                                      null=True)  # annual
    expiry_date = models.DateField(auto_now=False, auto_now_add=False, blank=True, null=True)
    debt_type = models.CharField(max_length=50, blank=True)
    credit_rating = models.CharField(max_length=50, blank=True)

    class Meta:
        unique_together = ("name", "expiry_date", "interest_rate")


class EquityAsset(models.Model):
    '''
    Stores a stock's details
    Like Reliance, Infosys, TCS etc
    '''
    exchange = models.ForeignKey(Exchange, on_delete=models.PROTECT, blank=True, null=True)
    name = models.CharField(max_length=200)
    market_cap = models.FloatField(blank=True, null=True)  # in Rs cr
    cap_type = models.CharField(max_length=50, blank=True)
    equity_sector = models.CharField(max_length=50, blank=True)
    dividend_history = models.CharField(max_length=1000, blank=True)


class EquityAssetIndex(models.Model):
    '''
    Stores relationship between stock and index
    Like Infosys stock is part of BSE Sensex etc
    '''
    benchmark_index = models.ForeignKey(BenchmarkIndex, on_delete=models.PROTECT)
    equity_asset = models.ForeignKey(EquityAsset, on_delete=models.PROTECT)


class AssetPortfolio(models.Model):
    '''
    Stores overall portoflio details for a fund scheme or benchmark index or fund category. 
    in every row, any one foreign key is filled while the other two are empty
    '''
    fund_scheme = models.ForeignKey(FundScheme, on_delete=models.PROTECT, blank=True, null=True)
    benchmark_index = models.ForeignKey(BenchmarkIndex, on_delete=models.PROTECT, blank=True, null=True)
    fund_category = models.ForeignKey(FundCategory, on_delete=models.PROTECT, blank=True, null=True)
    
    # composition of portfolio
    num_assets = models.IntegerField(validators=[MinValueValidator(0)], blank=True, null=True)
    debt_pc = models.FloatField(default=0)
    equity_pc = models.FloatField(default=0)
    cash_pc = models.FloatField(default=0)
    other_pc = models.FloatField(default=0)
    
    # detailed composition as per credit rating of debt asset or cap size of equity
    debt_aaa_pc = models.FloatField(default=0)
    debt_aa_pc = models.FloatField(default=0)
    debt_a_pc = models.FloatField(default=0)
    debt_bbb_pc = models.FloatField(default=0)
    debt_bb_pc = models.FloatField(default=0)
    debt_b_pc = models.FloatField(default=0)
    debt_belowb_pc = models.FloatField(default=0)
    debt_unrated_pc = models.FloatField(default=0)
    equity_giant_pc = models.FloatField(default=0)
    equity_large_pc = models.FloatField(default=0)
    equity_medium_pc = models.FloatField(default=0)
    equity_small_pc = models.FloatField(default=0)
    equity_micro_pc = models.FloatField(default=0)


class EquityPortfolio(models.Model):
    '''
    Stores relationship between stock and mutual fund 
    Like SBI Bluechip Fund has invested 7% of its AUM in Infosys 
    '''
    fund_scheme = models.ForeignKey(FundScheme, on_delete=models.PROTECT)
    equity_asset = models.ForeignKey(EquityAsset, on_delete=models.PROTECT)
    percentage = models.FloatField(validators=[MaxValueValidator(100.0)], null=True)
    for_date = models.DateField(auto_now=False, auto_now_add=False, blank=True, null=True)

    class Meta:
        unique_together = ("fund_scheme", "equity_asset")


class DebtPortfolio(models.Model):
    '''
    Stores relationship between bond and mutual fund 
    Like SBI Short Term Fund has invested 10% of its AUM in GOI bond (7% 2020) 
    '''
    fund_scheme = models.ForeignKey(FundScheme, on_delete=models.PROTECT)
    debt_asset = models.ForeignKey(DebtAsset, on_delete=models.PROTECT)
    percentage = models.FloatField(validators=[MaxValueValidator(100.0)], null=True)
    for_date = models.DateField(auto_now=False, auto_now_add=False, blank=True, null=True)

    class Meta:
        unique_together = ("fund_scheme", "debt_asset")


class SchemePlanHistory(models.Model):
    '''
    Stores monthly snapshots of key fund data that changes every month
    Useful in hsitorical analysis of funds
    '''
    starting_date = models.DateField(blank=False, null=False)
    scheme = models.ForeignKey(SchemePlan, on_delete=models.PROTECT, related_name='scheme_plan_history')
    
    ## key details of fund that change
    rating_crisil = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)], default=0, blank=True, null=True)
    rating_vro = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)], default=0, blank=True, null=True)
    rating_ms = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)], default=0, blank=True, null=True)
    aum = models.FloatField(blank=True, null=True)  # in Rs cr
    expense_ratio = models.FloatField(validators=[MinValueValidator(0), MaxValueValidator(100)], blank=True, null=True)  # in %

    # annualised returns in %
    avg_return = models.FloatField(null=True)
    min_return = models.FloatField(null=True)
    max_return = models.FloatField(null=True)

    # risk measures in decimal
    std_dev = models.FloatField(blank=True, null=True)
    sortino_ratio = models.FloatField(blank=True, null=True)
    alpha = models.FloatField(blank=True, null=True)
    beta = models.FloatField(blank=True, null=True)
    sharpe_ratio = models.FloatField(blank=True, null=True)

    created = models.DateTimeField(auto_now_add=True)

