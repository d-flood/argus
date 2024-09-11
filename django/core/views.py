import json

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_safe, require_POST

from core import models


@require_safe
def home(request: HttpRequest) -> HttpResponse:
    return render(request, "home.html")


@require_safe
def dashboard(request: HttpRequest) -> HttpResponse:
    return render(request, "dashboard.html")


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
        "time": dataset.date,
        "polling_interval": bms.polling_interval,
    }
    return HttpResponse(json.dumps(response_data), content_type="application/json")
