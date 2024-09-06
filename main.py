import asyncio
import os
import struct
import time
from bleak import BleakClient, BleakScanner, BleakError

# UUIDs for the XiaoXiang BMS
BMS_SERVICE_UUID = "0000ff00-0000-1000-8000-00805f9b34fb"
BMS_TX_CHAR_UUID = "0000ff02-0000-1000-8000-00805f9b34fb"
BMS_RX_CHAR_UUID = "0000ff01-0000-1000-8000-00805f9b34fb"


class BMSHandler:
    def __init__(self):
        self.bms_data_received = []
        self.bms_data_length_received = 0
        self.bms_data_length_expected = 0
        self.bms_data_error = False

    def restart_bluetooth(self):
        print("Restarting Bluetooth service...")
        os.system("sudo systemctl restart bluetooth")
        os.system("sudo hciconfig hci0 reset")
        print("Bluetooth service restarted.")
        # Optional: Wait for a few seconds to ensure the Bluetooth service has restarted

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
                    if (
                        self.bms_data_length_received >= 0x18
                    ):  # Ensures there are enough bytes for the following fields
                        chgot = struct.unpack(">H", bytes(data[0x18:0x1A]))[0]
                        charge_overtemp = (chgot - 2731) / 10
                        print(f"Charge Overtemp Threshold: {charge_overtemp:.1f}°C")
        else:
            self.bms_data_error = not self.append_bms_packet(data)

        if not self.bms_data_error:
            if self.bms_data_length_received == self.bms_data_length_expected + 7:
                print("Complete packet received, now must validate checksum")
                self.print_hex(self.bms_data_received, self.bms_data_length_received)

                if self.get_is_checksum_valid_for_received_data(self.bms_data_received):
                    print("Checksums match")
                    self.print_bms_data_received(self.bms_data_received)
                    # Reset the state
                    self.bms_data_received = []
                    self.bms_data_length_received = 0
                    self.bms_data_length_expected = 0
                    self.bms_data_error = False
                else:
                    checksum = self.get_checksum_for_received_data(
                        self.bms_data_received
                    )
                    print(
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
            print(f"{idx:2d} {' ' if i < datalen - 1 else ''}", end="")
        print()
        for i in range(datalen):
            idx = datalen - i - 1 if reverse else i
            print(f"{data[idx]:02X} {' ' if i < datalen - 1 else ''}")

    def print_bms_data_received(self, data):
        if data[1] == 0x03:
            total_volts = struct.unpack(">H", bytes(data[4:6]))[0] / 100
            print(f"Total Volts: {total_volts:.2f}V")

            current = struct.unpack(">H", bytes(data[6:8]))[0] / 100
            print(f"Current: {current:.2f}A")

            remaining_capacity = struct.unpack(">H", bytes(data[8:10]))[0] / 100
            print(f"Remaining Capacity: {remaining_capacity:.2f}Ah")

            nominal_capacity = struct.unpack(">H", bytes(data[10:12]))[0] / 100
            print(f"Nominal Capacity: {nominal_capacity:.2f}Ah")

            total_cycles = struct.unpack(">H", bytes(data[12:14]))[0]
            print(f"Total cycles: {total_cycles}")

            date = struct.unpack(">H", bytes(data[14:16]))[0]
            print(
                f"Production date YYYY/MM/DD: {2000 + (date >> 9):04d}/{(date >> 5) & 0x0F:02d}/{date & 0x1F:02d}"
            )

            # Assuming cells balancing status is in bytes 16-19
            for i in range(4):
                balance_status = data[16 + i]
                print(f"Balance status {i}: {balance_status:02X}")

            protection_status = struct.unpack(">H", bytes(data[20:22]))[0]
            print(f"Protection status: {bin(protection_status)[2:].zfill(16)}")

            software_version = data[22] / 10
            print(f"Software version: {software_version:.1f}")

            soc = data[23]
            print(f"Remaining percent (SOC): {soc}%")

            mosfet_state_charge = "ON" if (data[24] & 0x01) == 1 else "OFF"
            mosfet_state_discharge = "ON" if (data[24] & 0x02) == 2 else "OFF"
            print(
                f"MOSFET state: charge {mosfet_state_charge}, discharge {mosfet_state_discharge}"
            )

            bms_number_of_cells = data[25]
            print(f"Number of battery strings: {bms_number_of_cells}")

            num_temp_sensors = data[26]
            print(f"Number of temperature sensors: {num_temp_sensors}")
            for i in range(num_temp_sensors):
                temp = (
                    struct.unpack(">H", bytes(data[27 + 2 * i : 29 + 2 * i]))[0] - 2731
                ) / 10
                print(f"Temperature sensor {i + 1}: {temp:.1f}°C")

        elif data[1] == 0x04:
            bms_number_of_cells = data[3] // 2
            for i in range(bms_number_of_cells):
                millivolts = struct.unpack(">H", bytes(data[4 + 2 * i : 6 + 2 * i]))[0]
                print(f"Cell {i + 1}: {millivolts / 1000:.3f}V")

        elif data[1] == 0xFC:
            if data[0] == 0xDD and data[2] == 0:
                print("Heating command successfully sent")

        # Add more data handlers as needed

    async def scan_and_connect(self):
        print("Scanning for devices...")
        devices = await BleakScanner.discover()
        target_device = None

        for device in devices:
            if "xiaoxi" in device.name.lower():
                target_device = device
                break

        if not target_device:
            print("No BMS device found.")
            return None

        print(f"Found BMS device: {target_device.address}")
        return target_device

    async def main(self):
        target_device = await self.scan_and_connect()
        if not target_device:
            return

        async with BleakClient(target_device) as client:
            try:
                # Ensure connection
                if not client.is_connected:
                    print("Failed to connect to the device.")
                    return

                print("Connected to the BMS device")

                # Enable notifications
                await client.start_notify(BMS_RX_CHAR_UUID, self.handle_notification)

                ticker = 1
                while True:
                    print(f"Tick {ticker:03d}: ", end="")
                    if client.is_connected:
                        if ticker % 2 == 0:
                            print("bms connected, sending request for overall data")
                            data = bytes([0xDD, 0xA5, 0x03, 0x00, 0xFF, 0xFD, 0x77])
                        else:
                            print("bms connected, sending request for cell data")
                            data = bytes([0xDD, 0xA5, 0x04, 0x00, 0xFF, 0xFC, 0x77])

                        await client.write_gatt_char(BMS_TX_CHAR_UUID, data)
                    else:
                        print("Device disconnected")
                        break

                    ticker += 1
                    await asyncio.sleep(5)

            except BleakError as e:
                print(f"An error occurred: {e}")


if __name__ == "__main__":
    handler = BMSHandler()
    handler.restart_bluetooth()
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(handler.main())
    except KeyboardInterrupt:
        # turn off bluetooth
        os.system("sudo hciconfig hci0 down")
        print("\nBluetooth turned off.")
