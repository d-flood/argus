from mureq import request


def post_data(data: dict):
    # url = "http://argus.davidaflood.com/v1/bms_data/"
    url = "http://localhost:8000/v1/bms_data/"
    token = "123456789"
    headers = {"Authorization": token}
    response = request("POST", url, headers=headers, json=data)
    print(response.json())


post_data({"temperature": 25, "humidity": 50})
