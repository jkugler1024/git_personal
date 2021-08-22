from .base import *

DEBUG = True

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'finance',
        'USER': 'postgres',
        'PASSWORD':'C4r0l1n3!',
        'HOST':'localhost',
        'PORT':'5432'
    }
}