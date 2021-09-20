from django.db import models
from django.contrib.auth.models import User

class Company(models.Model):
    company_name = models.CharField(max_length=30)
    abbreviation = models.CharField(max_length=10)
    def __str__(self):
        return self.company_name

class BusinessUnit(models.Model):
    unit_name = models.CharField(max_length=30)
    abbreviation = models.CharField(max_length=10)
    company_id = models.ForeignKey(Company, on_delete=models.CASCADE)
    opened_date = models.DateField()
    def __str__(self):
        return self.unit_name