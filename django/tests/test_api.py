from mureq import request


def post_data(data: dict):
    print("Posting data to Argus...")
    url = "http://argus.davidaflood.com/v1/bms_data/"
    token = "123456789"
    print(f"Token: {token}")
    headers = {"Authorization": token}
    response = request("POST", url, headers=headers, json=data)
    print(response.body)
    if response.status_code == 200:
        resp_data = response.json()
        print(resp_data)
        if polling_interval := resp_data.get("polling_interval"):
            return polling_interval
    return 60


post_data({"temperature": 25, "humidity": 50})
