import csv
import datetime as dt
import io
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_ZIP_PATH = ROOT.parent / 'Lean/Data/equity/usa/daily/spy.zip'
OUTPUT_PATH = ROOT / 'results/spy_daily_2016_2020.json'
START_DATE = dt.datetime(2016, 1, 1)
END_DATE = dt.datetime(2020, 12, 31)


def filter_rows():
    with zipfile.ZipFile(DATA_ZIP_PATH) as zf:
        with zf.open('spy.csv') as raw_file:
            reader = csv.reader(io.TextIOWrapper(raw_file))
            next(reader)  # skip header
            for row in reader:
                date = dt.datetime.strptime(row[0], '%Y%m%d %H:%M')
                if date < START_DATE or date > END_DATE:
                    continue
                yield {
                    'time': date.strftime('%Y-%m-%d'),
                    'open': float(row[1]),
                    'high': float(row[2]),
                    'low': float(row[3]),
                    'close': float(row[4]),
                    'volume': int(float(row[5])),
                }


def main():
    records = list(filter_rows())
    OUTPUT_PATH.write_text(json.dumps(records))


if __name__ == '__main__':
    main()
