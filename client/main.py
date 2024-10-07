import asyncio
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
        self.bms_data_received = {}
        self.bms_data_length_received = {}
        self.bms_data_length_expected = {}
        self.bms_data_error = {}
        self.polling_interval = 60
        self.all_data = {}

    def restart_bluetooth(self):
        logging.info("Restarting Bluetooth service...")
        os.system("sudo systemctl restart bluetooth")
        os.system("sudo hciconfig hci0 reset")
        logging.info("Bluetooth service restarted.")
        time.sleep(5)

    def handle_notification(self, sender: int, data: bytearray, address: str):
        data = list(data)
        if self.bms_data_error.get(address):
            return

        if self.bms_data_length_received[address] == 0:
            if data[0] == 0xDD:
                self.bms_data_error[address] = data[2] != 0
                self.bms_data_length_expected[address] = data[3]
                if not self.bms_data_error[address]:
                    self.bms_data_error[address] = not self.append_bms_packet(
                        data, address
                    )
                    if self.bms_data_length_received[address] >= 0x18:
                        chgot = struct.unpack(">H", bytes(data[0x18:0x1A]))[0]
                        charge_overtemp = (chgot - 2731) / 10
                        logging.info(
                            f"Charge Overtemp Threshold for {address}: {charge_overtemp:.1f}°C"
                        )
        else:
            self.bms_data_error[address] = not self.append_bms_packet(data, address)

        if not self.bms_data_error[address]:
            if (
                self.bms_data_length_received[address]
                == self.bms_data_length_expected[address] + 7
            ):
                logging.info(
                    f"Complete packet received for {address}, now must validate checksum"
                )
                self.print_hex(
                    self.bms_data_received[address],
                    self.bms_data_length_received[address],
                )

                if self.get_is_checksum_valid_for_received_data(
                    self.bms_data_received[address]
                ):
                    logging.info(f"Checksums match for {address}")
                    self.print_bms_data_received(
                        self.bms_data_received[address], address
                    )
                else:
                    checksum = self.get_checksum_for_received_data(
                        self.bms_data_received[address]
                    )
                    logging.error(
                        f"Checksum error for {address}: received is 0x{checksum:04X}, calculated is 0x{256 * self.bms_data_received[address][self.bms_data_length_expected[address] + 4] + self.bms_data_received[address][self.bms_data_length_expected[address] + 5]:04X}"
                    )

    def append_bms_packet(self, data, address):
        self.bms_data_received[address].extend(data)
        self.bms_data_length_received[address] += len(data)
        return self.bms_data_length_received[address] < 100

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

    def print_bms_data_received(self, data, address):
        device_data = {
            "address": address,
            "name": self.all_data[address]["name"],  # Store the device name
        }
        if data[1] == 0x03:
            total_volts = struct.unpack(">H", bytes(data[4:6]))[0] / 100
            device_data["total_volts"] = f"{total_volts}"

            current = struct.unpack(">h", bytes(data[6:8]))[0] / 100
            device_data["current"] = f"{current}"

            remaining_capacity = struct.unpack(">H", bytes(data[8:10]))[0] / 100
            device_data["remaining_capacity"] = f"{remaining_capacity}Ah"

            nominal_capacity = struct.unpack(">H", bytes(data[10:12]))[0] / 100
            device_data["nominal_capacity"] = f"{nominal_capacity}Ah"

            total_cycles = struct.unpack(">H", bytes(data[12:14]))[0]
            device_data["total_cycles"] = total_cycles

            date = struct.unpack(">H", bytes(data[14:16]))[0]
            device_data["production_date"] = (
                f"{2000 + (date >> 9):04d}/{(date >> 5) & 0x0F:02d}/{date & 0x1F:02d}"
            )

            device_data["balance_status"] = []
            for i in range(4):
                balance_status = data[16 + i]
                device_data["balance_status"].append(balance_status)

            protection_status = struct.unpack(">H", bytes(data[20:22]))[0]
            device_data["protection_status"] = bin(protection_status)[2:].zfill(16)

            software_version = data[22] / 10
            device_data["software_version"] = f"{software_version:.1f}"

            soc = data[23]
            device_data["remaining_soc"] = f"{soc}%"

            mosfet_state_charge = "ON" if (data[24] & 0x01) == 1 else "OFF"
            mosfet_state_discharge = "ON" if (data[24] & 0x02) == 2 else "OFF"

            device_data["mosfet_state_charge"] = mosfet_state_charge
            device_data["mosfet_state_discharge"] = mosfet_state_discharge

            bms_number_of_cells = data[25]
            device_data["number_of_battery_strings"] = bms_number_of_cells

            num_temp_sensors = data[26]
            device_data["num_temp_sensors"] = num_temp_sensors
            device_data["temp_sensors"] = []
            for i in range(num_temp_sensors):
                temp = (
                    struct.unpack(">H", bytes(data[27 + 2 * i : 29 + 2 * i]))[0] - 2731
                ) / 10
                logging.info(f"Temperature sensor {i + 1}: {temp:.1f}°C")
                device_data["temp_sensors"].append(f"{temp:.1f}")

        elif data[1] == 0x04:
            bms_number_of_cells = data[3] // 2
            device_data["number_of_cells"] = bms_number_of_cells
            device_data["cell_voltages"] = []
            logging.info(f"Number of cells: {bms_number_of_cells}")
            for i in range(bms_number_of_cells):
                millivolts = struct.unpack(">H", bytes(data[4 + 2 * i : 6 + 2 * i]))[0]
                device_data["cell_voltages"].append(f"{millivolts / 1000:.3f}")
                logging.info(f"Cell {i + 1}: {millivolts / 1000:.3f}V")

        elif data[1] == 0xFC:
            if data[0] == 0xDD and data[2] == 0:
                device_data["heating_command"] = "success"

        elif data[1] == START_VOLTAGE_REGISTER:  # Handle start voltage response
            if data[0] == 0xDD and data[2] == 0:
                start_voltage = struct.unpack(">H", bytes(data[4:6]))[0]
                device_data["start_voltage"] = f"{start_voltage / 1000:.3f}V"

        # Store data in all_data dictionary with device address as key
        self.all_data[address] = device_data

    async def scan_and_connect(self):
        logging.info("Scanning for devices...")
        devices = await BleakScanner.discover()
        target_devices = []

        for device in devices:
            if "xiaoxi" in device.name.lower():
                target_devices.append(device)

        if not target_devices:
            logging.warning("No BMS devices found.")
            return []

        logging.info(
            "Found BMS device(s): " + ", ".join([d.name for d in target_devices])
        )

        for device in target_devices:
            # Initialize the data dictionary with the device's name and address
            self.all_data[device.address] = {
                "name": device.name,
                "address": device.address,
            }

        return target_devices

    async def process_device(self, device):
        async with BleakClient(device) as client:
            try:
                if not client.is_connected:
                    logging.error(f"Failed to connect to the device {device.address}.")
                    return

                logging.info(f"Connected to BMS device {device.address}")
                self.bms_data_received[device.address] = []
                self.bms_data_length_received[device.address] = 0
                self.bms_data_error[device.address] = False

                # Subscribe to notifications
                await client.start_notify(
                    BMS_RX_CHAR_UUID,
                    lambda sender, data: self.handle_notification(
                        sender, data, device.address
                    ),
                )

                # Use ticker or similar mechanism to cycle requests
                ticker = 1
                while ticker <= 12:
                    logging.info(f"Tick {ticker} for {device.address}: ")
                    if client.is_connected:
                        # Sending requests similar to the old version
                        if ticker % 3 == 0:
                            logging.info(
                                f"Sending request for start voltage to {device.address}"
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
                                f"Sending request for overall data to {device.address}"
                            )
                            data = bytes([0xDD, 0xA5, 0x03, 0x00, 0xFF, 0xFD, 0x77])
                        else:
                            logging.info(
                                f"Sending request for cell data to {device.address}"
                            )
                            data = bytes([0xDD, 0xA5, 0x04, 0x00, 0xFF, 0xFC, 0x77])

                        await client.write_gatt_char(BMS_TX_CHAR_UUID, data)
                    else:
                        logging.warning(f"Device {device.address} disconnected.")
                        break

                    ticker += 1
                    await asyncio.sleep(5)

            except BleakError as e:
                logging.error(f"An error occurred with device {device.address}: {e}")

    async def main(self):
        while True:
            target_devices = await self.scan_and_connect()
            if not target_devices:
                logging.warning("Retrying to scan devices...")
                await asyncio.sleep(self.polling_interval)
                continue

            tasks = [self.process_device(device) for device in target_devices]
            await asyncio.gather(*tasks)

            # Post the collected data to the server after completing all devices processing
            data_to_post = [self.all_data[device.address] for device in target_devices]
            self.polling_interval = post_data(data_to_post)
            logging.info(f"Polling interval set to {self.polling_interval} seconds")

            # Wait for the polling interval before the next iteration
            await asyncio.sleep(self.polling_interval)


def get_token():
    with open("argus_key", "r") as file:
        return file.read().strip()


def post_data(data: list):
    logging.info("Posting data to Argus...")
    url = "http://argus.davidaflood.com/v1/bms_data/"
    token = get_token()
    headers = {"Authorization": token}
    response = request("POST", url, headers=headers, json={"devices": data})
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
