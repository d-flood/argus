import asyncio
import json
import os
import struct
import time
from bleak import BleakClient, BleakScanner, BleakError

from mureq import request
from argus_logger import logging

# UUIDs for the XiaoXiang BMS
BMS_SERVICE_UUID = "0000ff00-0000-1000-8000-00805f9b34fb"
BMS_TX_CHAR_UUID = "0000ff02-0000-1000-8000-00805f9b34fb"
BMS_RX_CHAR_UUID = "0000ff01-0000-1000-8000-00805f9b34fb"

START_VOLTAGE_REGISTER = 0x2A


class BMSHandler:
    def __init__(self):
        self.bms_data_received = []
        self.bms_data_length_received = 0
        self.bms_data_length_expected = 0
        self.bms_data_error = False
        self.polling_interval = 60
        self.all_data = {}

    def restart_bluetooth(self):
        logging.info("Restarting Bluetooth service...")
        os.system("sudo systemctl restart bluetooth")
        os.system("sudo hciconfig hci0 reset")
        logging.info("Bluetooth service restarted.")
        time.sleep(5)

    def handle_notification(self, sender: int, data: bytearray):
        data = list(data)
        if self.bms_data_error:
            return

        if self.bms_data_length_received == 0:
            if data[0] == 0xDD:
                self.bms_data_error = data[2] != 0
                self.bms_data_length_expected = data[3]
                if not self.bms_data_error:
                    self.bms_data_error = not self.append_bms_packet(data)
                    if self.bms_data_length_received >= 0x18:
                        chgot = struct.unpack(">H", bytes(data[0x18:0x1A]))[0]
                        charge_overtemp = (chgot - 2731) / 10
                        logging.info(
                            f"Charge Overtemp Threshold: {charge_overtemp:.1f}°C"
                        )
        else:
            self.bms_data_error = not self.append_bms_packet(data)

        if not self.bms_data_error:
            if self.bms_data_length_received == self.bms_data_length_expected + 7:
                logging.info("Complete packet received, now must validate checksum")
                self.print_hex(self.bms_data_received, self.bms_data_length_received)

                if self.get_is_checksum_valid_for_received_data(self.bms_data_received):
                    logging.info("Checksums match")
                    self.print_bms_data_received(self.bms_data_received)
                    sorted_data = {k: self.all_data[k] for k in sorted(self.all_data)}
                    logging.info(json.dumps(sorted_data, indent=4))
                    self.polling_interval = post_data(sorted_data)
                    logging.info(
                        f"Polling interval set to {self.polling_interval} seconds"
                    )
                    time.sleep(self.polling_interval)
                    # Reset the state
                    self.bms_data_received = []
                    self.bms_data_length_received = 0
                    self.bms_data_length_expected = 0
                    self.bms_data_error = False
                else:
                    checksum = self.get_checksum_for_received_data(
                        self.bms_data_received
                    )
                    logging.error(
                        f"Checksum error: received is 0x{checksum:04X}, calculated is 0x{256 * self.bms_data_received[self.bms_data_length_expected + 4] + self.bms_data_received[self.bms_data_length_expected + 5]:04X}"
                    )

    def append_bms_packet(self, data):
        self.bms_data_received.extend(data)
        self.bms_data_length_received += len(data)
        return self.bms_data_length_received < 100

    def get_is_checksum_valid_for_received_data(self, data):
        checksum_index = int(data[3]) + 4
        return self.get_checksum_for_received_data(data) == (
            data[checksum_index] * 256 + data[checksum_index + 1]
        )

    def get_checksum_for_received_data(self, data):
        checksum = 0x10000
        for i in range(data[3] + 1):
            checksum -= data[i + 3]
        return checksum & 0xFFFF

    @staticmethod
    def print_hex(data, datalen, reverse=False):
        for i in range(datalen):
            idx = datalen - i - 1 if reverse else i
            logging.debug(f"{idx:2d} {' ' if i < datalen - 1 else ''}", end="")
        logging.debug("")
        for i in range(datalen):
            idx = datalen - i - 1 if reverse else i
            logging.debug(f"{data[idx]:02X} {' ' if i < datalen - 1 else ''}")

    def print_bms_data_received(self, data):
        if data[1] == 0x03:
            total_volts = struct.unpack(">H", bytes(data[4:6]))[0] / 100
            self.all_data["total_volts"] = f"{total_volts}"

            current = struct.unpack(">h", bytes(data[6:8]))[0] / 100
            self.all_data["current"] = f"{current}"

            remaining_capacity = struct.unpack(">H", bytes(data[8:10]))[0] / 100
            self.all_data["remaining_capacity"] = f"{remaining_capacity}Ah"

            nominal_capacity = struct.unpack(">H", bytes(data[10:12]))[0] / 100
            self.all_data["nominal_capacity"] = f"{nominal_capacity}Ah"

            total_cycles = struct.unpack(">H", bytes(data[12:14]))[0]
            self.all_data["total_cycles"] = total_cycles

            date = struct.unpack(">H", bytes(data[14:16]))[0]
            self.all_data["production_date"] = (
                f"{2000 + (date >> 9):04d}/{(date >> 5) & 0x0F:02d}/{date & 0x1F:02d}"
            )

            self.all_data["balance_status"] = []
            for i in range(4):
                balance_status = data[16 + i]
                self.all_data["balance_status"].append(balance_status)

            protection_status = struct.unpack(">H", bytes(data[20:22]))[0]
            self.all_data["protection_status"] = bin(protection_status)[2:].zfill(16)

            software_version = data[22] / 10
            self.all_data["software_version"] = f"{software_version:.1f}"

            soc = data[23]
            self.all_data["remaining_soc"] = f"{soc}%"

            mosfet_state_charge = "ON" if (data[24] & 0x01) == 1 else "OFF"
            mosfet_state_discharge = "ON" if (data[24] & 0x02) == 2 else "OFF"

            self.all_data["mosfet_state_charge"] = mosfet_state_charge
            self.all_data["mosfet_state_discharge"] = mosfet_state_discharge

            bms_number_of_cells = data[25]
            self.all_data["number_of_battery_strings"] = bms_number_of_cells

            num_temp_sensors = data[26]
            self.all_data["num_temp_sensors"] = num_temp_sensors
            self.all_data["temp_sensors"] = []
            for i in range(num_temp_sensors):
                temp = (
                    struct.unpack(">H", bytes(data[27 + 2 * i : 29 + 2 * i]))[0] - 2731
                ) / 10
                logging.info(f"Temperature sensor {i + 1}: {temp:.1f}°C")
                self.all_data["temp_sensors"].append(f"{temp:.1f}")

        elif data[1] == 0x04:
            bms_number_of_cells = data[3] // 2
            self.all_data["number_of_cells"] = bms_number_of_cells
            self.all_data["cell_voltages"] = []
            for i in range(bms_number_of_cells):
                millivolts = struct.unpack(">H", bytes(data[4 + 2 * i : 6 + 2 * i]))[0]
                self.all_data["cell_voltages"].append(f"{millivolts / 1000:.3f}")

        elif data[1] == 0xFC:
            if data[0] == 0xDD and data[2] == 0:
                self.all_data["heating_command"] = "success"

        elif data[1] == START_VOLTAGE_REGISTER:  # Handle start voltage response
            if data[0] == 0xDD and data[2] == 0:
                start_voltage = struct.unpack(">H", bytes(data[4:6]))[0]
                self.all_data["start_voltage"] = f"{start_voltage / 1000:.3f}V"

    async def scan_and_connect(self):
        logging.info("Scanning for devices...")
        devices = await BleakScanner.discover()
        target_device = None

        for device in devices:
            if "xiaoxi" in device.name.lower():
                target_device = device

        if not target_device:
            logging.warning("No BMS devices found.")
            return None

        logging.info(f"Found BMS device(s): {target_device.name}")

        return target_device

    async def main(self):
        target_device = await self.scan_and_connect()
        if not target_device:
            return

        async with BleakClient(target_device) as client:
            try:
                if not client.is_connected:
                    logging.error("Failed to connect to the device.")
                    return

                logging.info("Connected to the BMS device")
                await client.start_notify(BMS_RX_CHAR_UUID, self.handle_notification)

                ticker = 1
                while True:
                    logging.info(f"Tick {ticker:03d}: ")
                    if client.is_connected:
                        if ticker % 3 == 0:
                            logging.info(
                                "bms connected, sending request for start voltage"
                            )
                            data = bytes(
                                [
                                    0xDD,
                                    0xA5,
                                    0x03,
                                    0x00,
                                    0xFF,
                                    START_VOLTAGE_REGISTER,
                                    0x77,
                                ]
                            )
                        elif ticker % 2 == 0:
                            logging.info(
                                "bms connected, sending request for overall data"
                            )
                            data = bytes([0xDD, 0xA5, 0x03, 0x00, 0xFF, 0xFD, 0x77])
                        else:
                            logging.info("bms connected, sending request for cell data")
                            data = bytes([0xDD, 0xA5, 0x04, 0x00, 0xFF, 0xFC, 0x77])

                        await client.write_gatt_char(BMS_TX_CHAR_UUID, data)
                    else:
                        logging.warning("Device disconnected")
                        break

                    ticker += 1
                    await asyncio.sleep(5)

            except BleakError as e:
                logging.error(f"An error occurred: {e}")


def get_token():
    with open("argus_key", "r") as file:
        return file.read().strip()


def post_data(data: dict):
    logging.info("Posting data to Argus...")
    url = "http://argus.davidaflood.com/v1/bms_data/"
    token = get_token()
    headers = {"Authorization": token}
    response = request("POST", url, headers=headers, json=data)
    if response.status_code == 200:
        resp_data = response.json()
        if polling_interval := resp_data.get("polling_interval"):
            return polling_interval * 60
    return 60


if __name__ == "__main__":
    handler = BMSHandler()
    handler.restart_bluetooth()
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(handler.main())
    except KeyboardInterrupt:
        os.system("sudo hciconfig hci0 down")
        logging.info("\nBluetooth turned off.")
