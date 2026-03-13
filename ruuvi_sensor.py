import argparse
import asyncio
import csv
import datetime
import os
import sys

from ruuvitag_sensor.ruuvi import RuuviTagSensor

CSV_FIELDS = [
    "timestamp",
    "mac_address",
    "data_format",
    "humidity",
    "temperature",
    "pressure",
    "acceleration",
    "acceleration_x",
    "acceleration_y",
    "acceleration_z",
    "tx_power",
    "battery",
    "movement_counter",
    "measurement_sequence_number",
    "mac",
    "rssi",
]


def parse_args():
    parser = argparse.ArgumentParser(
        description="Stream RuuviTag BLE sensor data to console and CSV file."
    )
    parser.add_argument(
        "--output",
        default="ruuvi_readings.csv",
        help="CSV output file path (default: ruuvi_readings.csv)",
    )
    parser.add_argument(
        "--macs",
        nargs="+",
        metavar="MAC",
        default=None,
        help="Filter by MAC addresses (e.g. AA:BB:CC:DD:EE:FF). Default: all tags.",
    )
    return parser.parse_args()


def get_csv_writer(filepath):
    file_exists = os.path.exists(filepath) and os.path.getsize(filepath) > 0
    csv_file = open(filepath, "a", newline="", encoding="utf-8")
    writer = csv.DictWriter(
        csv_file,
        fieldnames=CSV_FIELDS,
        extrasaction="ignore",
        restval="",
    )
    if not file_exists:
        writer.writeheader()
    return csv_file, writer


def _fmt(val):
    return val if val is not None else "N/A"


def format_reading(mac, data, ts_str):
    lines = [
        f"[{ts_str}]  {mac}",
        f"  Temperature : {_fmt(data.get('temperature'))} °C",
        f"  Humidity    : {_fmt(data.get('humidity'))} %",
        f"  Pressure    : {_fmt(data.get('pressure'))} hPa",
        f"  Battery     : {_fmt(data.get('battery'))} mV   TX Power: {_fmt(data.get('tx_power'))} dBm",
        f"  Accel (xyz) : {_fmt(data.get('acceleration_x'))} / {_fmt(data.get('acceleration_y'))} / {_fmt(data.get('acceleration_z'))} mg"
        f"   Total: {_fmt(data.get('acceleration'))} mg",
        f"  Seq #       : {_fmt(data.get('measurement_sequence_number'))}"
        f"   Movement: {_fmt(data.get('movement_counter'))}"
        f"   Format: {_fmt(data.get('data_format'))}"
        f"   RSSI: {_fmt(data.get('rssi'))} dBm",
        "-" * 50,
    ]
    return "\n".join(lines)


async def main(args):
    csv_file, writer = get_csv_writer(args.output)
    macs = args.macs
    print(f"Streaming RuuviTag data. Output: {args.output}. Press Ctrl+C to stop.\n")
    try:
        async for mac, data in RuuviTagSensor.get_data_async(macs):
            ts = datetime.datetime.now(datetime.timezone.utc)
            ts_str = ts.strftime("%Y-%m-%d %H:%M:%S UTC")

            print(format_reading(mac, data, ts_str))

            row = {"timestamp": ts_str, "mac_address": mac, **data}
            writer.writerow(row)
            csv_file.flush()
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    finally:
        csv_file.close()
        print(f"\nStopped. Data saved to: {args.output}")


if __name__ == "__main__":
    args = parse_args()
    try:
        asyncio.run(main(args))
    except KeyboardInterrupt:
        pass
