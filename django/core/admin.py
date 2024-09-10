# add models to admin
from django.contrib import admin

from core import models

admin.site.register(models.BMSDevice)
admin.site.register(models.Dataset)
