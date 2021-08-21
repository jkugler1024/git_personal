from django.contrib import admin
from django.urls import path, include
from . import views

#should update to give a better variable name - switch pk to loan_id, in most cases
#use include to reduce redundancy of route prefixes
#explore using a single url path for url's at the same level, using a single view to parse out CRUD functions based on response method

urlpatterns = [
    # Main URLs
    path('',                                                        views.home,                     name='home'),
    path('',                                                        views.home,                     name='loans_home'),
    
    path('loan/create/',                                            views.loan_create_view,         name="loan_create"),
    path('loan/loancalc/create/<str:loan_id>/',                     views.loancalc_create_view,     name="loan_loancalc_create"),
    path('loan/loancalc/<str:calc_id>/payment_variation/create/',   views.pmtvariation_create_view, name="pmt_variation_create"),
    
    path('loan/list/',                                              views.loan_list_view,           name="loan_list"),
    path('loan/loancalc/list/',                                     views.loancalc_list_view,       name="loan_loancalc_list"),
    path('loan/loancalc/<str:calc_id>/payment_variation/list/',     views.pmtvariation_list_view,   name="pmt_variation_list"),
    
    path('loan/detail/<str:loan_id>/',                              views.loan_detail_view,         name="loan_detail"),
    path('loan/loancalc/detail/<str:calc_id>/',                     views.loancalc_detail_view,     name="loancalc_detail"),
    path('loan/accounting/',                                        views.accounting_view,          name="accounting_roll"),
    path('loan/accounting/<str:loan_id>/',                          views.loan_accounting_view,     name="loan_accounting_roll"),
    
    path('loan/update/<str:loan_id>/',                              views.loan_update_view,         name="loan_update"),
    # path('loan/loancalc/update/<str:calc_id>/',                     views.loancalc_update_view,     name="loancalc_update"), 
    path('loan/loancalc/payment_variation/<str:pmtvar_id>/update',  views.pmtvar_update_view,       name="pmt_variation_update"),
    
    path('loan/delete/<str:loan_id>/',                              views.loan_delete_view,         name="loan_delete"),
    path('loan/loancalc/delete/<str:loan_id>/<str:calc_id>/',       views.loancalc_delete_view,     name="loancalc_delete"),
    path('loan/loancalc/payment_variation/delete/<str:pmtvar_id>/', views.pmtvar_delete_view,       name="pmt_variation_delete"),
    
    path('loan/detail/<str:loan_id>/excel_export',                  views.xlsx,                     name="export_loansched_excel"),
    path('loan/loancalc/detail/<str:calc_id>/excel_export',         views.xlsx,                     name="export_calcsched_excel"),
    
    path('loan/detail/<str:loan_id>/<str:bal_type>/excel_export',   views.xlsx_roll,                name="export_loan_roll_excel"),
    
    ] 