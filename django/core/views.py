import json

from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_safe, require_POST

from core import models
from core.utilities import prepare_bms_data_context


@require_safe
def home(request: HttpRequest) -> HttpResponse:
    return render(request, "home.html")


@require_safe
def dashboard(request: HttpRequest, bms_device_pk: int) -> HttpResponse:
    bms = get_object_or_404(models.BMSDevice, pk=bms_device_pk)
    bms_data = bms.datasets.first()
    bms_data = prepare_bms_data_context(bms_data.data)
    context = {
        "data": bms_data,
        "bms_data": bms,
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
    data = json.loads(request.body)
    if not isinstance(data, dict):
        return HttpResponse(status=400)
    dataset = models.Dataset(bms=bms, data=data)
    dataset.save()
    response_data = {
        "id": dataset.pk,
        "message": "Data saved successfully",
        "polling_interval": bms.polling_interval,
    }
    return HttpResponse(json.dumps(response_data), content_type="application/json")
