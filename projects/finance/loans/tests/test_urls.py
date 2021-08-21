from django.test import SimpleTestCase
from django.urls import reverse, resolve
from loans.views import home, loan_create_view, loancalc_create_view, pmtvariation_create_view
from loans.models import Frequency

class TestUrls(SimpleTestCase):
    
    def test_home_url_resolves(self):
        url = reverse('home')
        self.assertEquals(resolve(url).func, home)

    def test_loans_home_url_resolves(self):
        url = reverse('loans_home')
        self.assertEquals(resolve(url).func, home)

    def test_loan_create_url_resolves(self):
        url = reverse('loan_create')
        self.assertEquals(resolve(url).func, loan_create_view)

    def test_loan_loancalc_create_url_resolves(self):
        url = reverse('loan_loancalc_create', args=['1'])
        self.assertEquals(resolve(url).func, loancalc_create_view)

    def test_pmt_variation_create_url_resolves(self):
        url = reverse('pmt_variation_create', args=['10'])
        self.assertEquals(resolve(url).func, pmtvariation_create_view)