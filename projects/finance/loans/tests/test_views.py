from django.test import TestCase, Client
from unittest import TestCase as tc
from django.urls import reverse
from django.contrib.auth.models import User
from loans.models import Loan, LoanCalc, Frequency, InterestMethod, Allocation
import json
import pdb

#class BaseTest(TestCase):
    

class TestViews(TestCase):
    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="test2", email="test@test.com")
        self.user.set_password('test')
        self.user.save()
        self.logged_in = self.client.login(username='test2', password='test')
        
        self.loan = Loan.objects.create(loan_name = 'test_loan')
        self.frequency1 = Frequency.objects.create(frequency_name='Monthly', months=1)
        self.frequency2 = Frequency.objects.create(frequency_name='Quarterly', months=3)
        self.frequency3 = Frequency.objects.create(frequency_name='Annually', months=12)
        self.intmeth1 = InterestMethod.objects.create(interest_method_name='30/360', month_counting='30', year_counting='360')
        self.intmeth2 = InterestMethod.objects.create(interest_method_name='30/365', month_counting='30', year_counting='365')
        self.intmeth3 = InterestMethod.objects.create(interest_method_name='actual/360', month_counting='actual', year_counting='360')
        self.intmeth4 = InterestMethod.objects.create(interest_method_name='actual/365', month_counting='actual', year_counting='365')
        self.intmeth5 = InterestMethod.objects.create(interest_method_name='actual/actual', month_counting='actual', year_counting='actual')
        self.alloc1 = Allocation.objects.create(allocation_name='Interest First')
        self.alloc2 = Allocation.objects.create(allocation_name='Principal First')
        
        
        self.loan_create_url = reverse('loan_create')
        self.loancalc_create_url = reverse('loan_loancalc_create', args=[self.loan.id]) 


    def test_GET_loan_create_view(self):
        response = self.client.get(self.loan_create_url)
        
        self.assertEquals(response.status_code, 200)
        self.assertTemplateUsed(response,'loans/loan_create.html')
        
    def test_POST_loan_create_view(self):
        myloan = 'test_loan2'
        
        post = {'loan_name': myloan}
        response = self.client.post(self.loan_create_url, post)
        new_obj = Loan.objects.filter(loan_name=myloan).first()
        
        self.assertEquals(response.status_code, 302) #verify the response code
        self.assertEquals(new_obj.loan_name, 'test_loan2') #verify that a new object by the proper name was created in the db


    def test_GET_loancalc_create_view(self):
        response = self.client.get(self.loancalc_create_url)
        
        self.assertEquals(response.status_code, 200)
        self.assertTemplateUsed(response,'loans/loancalc_create.html')       
        
    def test_POST_loancalc_create_view_seq1(self):
        
        # new_loan = Loan.objects.create(loan_name = 'test_loan3')
        url = reverse('loan_loancalc_create', args=[self.loan.id]) 
        
        post = {
            # 'loan': new_loan.id, #should not have to fill this
            # 'sequence': 1,
            'loan_amt': '100000',
            'loan_date': '1/1/2020',
            'first_pmt_date': '2/28/2020',
            'nbr_of_pmts': '12',
            'int_rate': '.05',
            'int_method': self.intmeth1.id,
            'pmt_frequency': self.frequency1.id,
            'allocation': self.alloc1.id,
            # 'rewritten_int': 0
            }
        
        response = self.client.post(url, post)
        new_obj = LoanCalc.objects.filter(loan=self.loan).first()
        pdb.set_trace()
        self.assertEquals(response.status_code, 200) #verify the response code
        self.assertEquals(new_obj.loan_amt, 100000) #verify that a new object by the proper name was created in the db
        
        