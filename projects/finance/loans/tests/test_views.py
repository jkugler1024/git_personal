from django.test import TestCase, Client
from django.urls import reverse
import json


class TestViews(TestCase):
    
    def setUp(self):
        self.client = Client()
        self.loan_create_url = reverse('loan_create')
    
    def test_loan_create_view_GET(self):
        response = self.client.get(self.loan_create_url)
        
        self.assertEquals(response.status_code, 199)
        self.assertTemplateUsed(response,'loans/loan_create.html')