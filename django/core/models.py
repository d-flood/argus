from django.db import models


class BMSDevice(models.Model):
    user = models.ForeignKey(
        "auth.User", on_delete=models.CASCADE, related_name="bms_devices"
    )
    name = models.CharField(max_length=255)
    token = models.CharField(max_length=255)

    class Meta:
        verbose_name = "BMS Devices"
        indexes = [
            models.Index(fields=["token"]),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.name}"


class Dataset(models.Model):
    bms = models.ForeignKey(
        BMSDevice, on_delete=models.CASCADE, related_name="datasets"
    )
    data = models.JSONField()
    date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.bms.name} - {self.date}"
