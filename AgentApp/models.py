from django.db import models
from django.core.exceptions import ValidationError
from django.utils.timezone import timedelta, now

class Sid(models.Model):
    phone_number = models.CharField(max_length=20, primary_key=True)
    callsid = models.CharField(max_length=40)


class Table(models.Model):
    phone = models.CharField(max_length=20)
    name = models.CharField(max_length=100)
    date = models.DateField()
    time = models.TimeField()
    guests = models.PositiveIntegerField()

    def __str__(self):
        return f"Reservation for {self.name} on {self.date}"

