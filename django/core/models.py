from django.db import models
import uuid


class BMSDevice(models.Model):
    created_by = models.ForeignKey(
        "auth.User", on_delete=models.CASCADE, related_name="bms_devices"
    )
    name = models.CharField(max_length=255)
    token = models.CharField(max_length=255)
    polling_interval = models.IntegerField(
        default=60, help_text="Minutes between data collection"
    )

    class Meta:
        verbose_name = "BMS Devices"
        indexes = [
            models.Index(fields=["token"]),
        ]

    def generate_token(self):
        self.token = uuid.uuid4().hex
        self.save()

    def __str__(self):
        return f"{self.created_by.username} - {self.name}"


class Dataset(models.Model):
    created_by = models.ForeignKey(
        "auth.User", on_delete=models.CASCADE, related_name="datasets"
    )
    bms = models.ForeignKey(
        BMSDevice, on_delete=models.CASCADE, related_name="datasets"
    )
    data = models.JSONField()
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date"]

    def __str__(self):
        return f"{self.bms.name} - {self.date}"
