import requests

try:
    response = requests.get('http://localhost:11434/api/version')
    print(f"Status code: {response.status_code}")
    print(f"Response: {response.text}")
except requests.exceptions.ConnectionError as e:
    print(f"Connection error: {e}")
except Exception as e:
    print(f"Other error: {e}")


"""import pandas as pd
from docx import Document

print("Enter filename for case data (XLSX):")
case_file = input().strip()
xl = pd.ExcelFile(case_file)
print("Available sheets:", xl.sheet_names)
sheet_name = input("Enter sheet name: ").strip()
df = pd.read_excel(case_file, sheet_name=sheet_name)
print("Available columns:", df.columns.tolist())
column = input("Enter column name: ").strip()
print(f"Available rows: 0 to {len(df)-1}")
start_row = int(input("Enter start row: ").strip())
end_row = int(input("Enter end row: ").strip())

for new_idx, (original_idx, row) in enumerate(df[column][start_row:end_row+1].items()):
    #print(f"\nProcessing Row {original_idx}:")
    print(f"Index in selection: {new_idx}")
    print(f"Data in row: {row}")
    if isinstance(row, float):
        print(f"Data type: float (will be converted to string)")
    else:
        print(f"Data type: {type(row)}")"""