from django.db import models
from django.core.exceptions import ValidationError
from django.utils.timezone import timedelta, now

class Sid(models.Model):
    phone_number = models.CharField(max_length=20, primary_key=True)
    callsid = models.CharField(max_length=40)


class Table(models.Model):
    phone_number = models.CharField(max_length=20)
    name = models.CharField(max_length=100)
    date = models.DateTimeField()
    guest_count = models.PositiveIntegerField()

    def __str__(self):
        return f"Reservation for {self.name} on {self.date}"

    def clean(self):
        current_time = now()

        # Ensure reservation is in the future
        if self.date <= current_time:
            raise ValidationError("Reservations must be for a future time.")

        # Ensure reservation time is between 5 PM and 9 PM
        if not (17 <= self.date.hour < 21):
            raise ValidationError("Reservations are only allowed between 5:00 PM and 9:00 PM.")

        # Check for overlapping reservations (within 1 to 1.5 hours)
        time_window_start = self.date - timedelta(hours=1)
        time_window_end = self.date + timedelta(hours=1, minutes=30)

        overlapping_reservations = Table.objects.filter(
            date__range=(time_window_start, time_window_end)
        ).exclude(id=self.id)  # Exclude the current instance during updates

        if overlapping_reservations.exists():
            raise ValidationError("A reservation already exists within 1 to 1.5 hours.")

    def save(self, *args, **kwargs):
        self.full_clean()  # Ensure all validations run before saving
        super().save(*args, **kwargs)
