def prepare_bms_data_context(data: dict):
    if not data.get("current"):
        data["current"] = "Unknown"
        data["current_class"] = "bg-secondary"
    else:
        if data["current"] == "0.0":
            data["current_class"] = "bg-secondary"
            data["current_label"] = "No current"
        elif float(data.get("current", 0)) > 0:  # charging
            data["current_label"] = "Charging"
            data["current_class"] = (
                "progress-bar-striped progress-bar-animated bg-success"
            )
        else:  # discharging
            data["current_label"] = "Discharging"
            data["current_class"] = (
                "progress-bar-striped progress-bar-animated bg-warning"
            )
        data["current"] = f"{data['current']}A"

    # get percentage of 24 total volts is
    if not data.get("total_volts"):
        data["total_volts"] = None
    else:
        data["total_volts_percentage"] = round(
            (float(data["total_volts"]) / 24) * 100, 2
        )
        if data["total_volts_percentage"] > 90:
            data["total_volts_class"] = "bg-success"
        elif data["total_volts_percentage"] > 50:
            data["total_volts_class"] = "bg-warning"
        else:
            data["total_volts_class"] = "bg-danger"
    # split cell_voltages into two lists
    if not data.get("cell_voltages"):
        data["cell_voltages"] = None
    else:
        cells = []
        for i, v in enumerate(data["cell_voltages"], 1):
            volts = float(v)
            percentage = (volts / 3.5) * 100
            if percentage > 90:
                cell_class = "bg-success"
            elif percentage > 50:
                cell_class = "bg-warning"
            else:
                cell_class = "bg-danger"
            cells.append(
                {
                    "volts": volts,
                    "percentage": round(percentage, 2),
                    "class": cell_class,
                    "index": i,
                }
            )
        data["cell_voltages_a"] = cells[:4]
        data["cell_voltages_b"] = cells[4:]
    temps = []
    for i, temp in enumerate(data.get("temp_sensors", []), 1):
        temp = float(temp)
        if temp > 40:
            temp_class = "bg-danger"
        elif temp > 30:
            temp_class = "bg-warning"
        else:
            temp_class = "bg-success"
        percentage = (temp / 50) * 100
        temps.append(
            {
                "temp": temp,
                "percentage": round(percentage, 2),
                "class": temp_class,
                "index": i,
            }
        )
    data["temp_sensors"] = temps
    return data
