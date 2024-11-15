import json
from datetime import timedelta

from django.utils import timezone
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_safe, require_POST
from django.contrib.auth.decorators import login_required

from core import models
from core.utilities import prepare_bms_data_context
from core.serializers import serialize_datasets


@require_safe
def home(request: HttpRequest) -> HttpResponse:
    return render(request, "home.html")


@require_safe
def dashboard(request: HttpRequest, bms_device_pk: int) -> HttpResponse:
    bms = get_object_or_404(models.BMSDevice, pk=bms_device_pk)
    which = int(request.GET.get("which", 0))
    try:
        which = int(which)
    except ValueError:
        which = 0
    if which == 0:
        bms_data = bms.datasets.first()
    else:
        bms_data = bms.datasets.all()[which]
    devices = [
        prepare_bms_data_context(device) for device in bms_data.data.get("devices", [])
    ]
    devices = sorted(devices, key=lambda x: x["address"])
    context = {
        "devices": devices,
        "bms": bms,
        "date": bms_data.date,
        "newer": which - 1 if which > 0 else None,
        "older": which + 1 if which < bms.datasets.count() - 1 else None,
    }
    return render(request, "dashboard.html", context)


@csrf_exempt
@require_POST
def bms_data(request: HttpRequest) -> HttpResponse:
    token = request.headers.get("Authorization")
    if not token:
        return HttpResponse(status=401)
    try:
        bms = models.BMSDevice.objects.get(token=token)
    except models.BMSDevice.DoesNotExist:
        return HttpResponse(status=404)
    user = bms.created_by
    data = json.loads(request.body)
    if not isinstance(data, dict):
        return HttpResponse(status=400)
    dataset = models.Dataset(bms=bms, data=data, created_by=user)
    dataset.save()
    response_data = {
        "id": dataset.pk,
        "message": "Data saved successfully",
        "polling_interval": bms.polling_interval,
    }
    return HttpResponse(json.dumps(response_data), content_type="application/json")


@require_safe
@login_required
def chart(request: HttpRequest, bms_device_pk: int) -> HttpResponse:
    five_days_ago = timezone.now() - timedelta(days=5)
    datasets = models.Dataset.objects.filter(
        created_by=request.user, bms__pk=bms_device_pk, date__gte=five_days_ago
    )
    context = {
        "data": serialize_datasets(datasets),
        "bms_device_pk": bms_device_pk,
    }
    return render(request, "chart.html", context)
