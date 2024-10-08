import json


def serialize_datasets(qs):
    return json.dumps(
        [{"date": dataset.date.isoformat(), "data": dataset.data} for dataset in qs]
    )
