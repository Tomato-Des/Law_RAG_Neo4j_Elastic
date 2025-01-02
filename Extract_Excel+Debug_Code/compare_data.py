import pandas as pd
import os

def get_file_type(file_path):
    """Determine the file type based on its extension."""
    _, ext = os.path.splitext(file_path)
    return ext.lower()

def load_file(file_path):
    """Load a file based on its type (Excel or CSV)."""
    file_type = get_file_type(file_path)
    if file_type == '.xlsx':
        return pd.ExcelFile(file_path)
    elif file_type == '.csv':
        return pd.read_csv(file_path)
    else:
        raise ValueError("Unsupported file type. Only .xlsx and .csv are supported.")

def get_data_from_file(file_path):
    """Interactively get data from the file."""
    file_data = load_file(file_path)
    
    if isinstance(file_data, pd.ExcelFile):
        # Excel file: Get sheet names and let user choose a sheet
        sheets = file_data.sheet_names
        print("Available sheets:", sheets)
        sheet_name = input("Enter the sheet name to extract data from: ")
        if sheet_name not in sheets:
            raise ValueError(f"Sheet '{sheet_name}' does not exist in the file.")
        df = file_data.parse(sheet_name=sheet_name)
    else:
        # CSV file: No sheet, directly read data
        df = file_data
    
    print("Available columns:", df.columns.tolist())
    selected_columns = input("Enter column names to extract (comma-separated): ").split(',')
    selected_columns = [col.strip() for col in selected_columns if col.strip() in df.columns]
    if not selected_columns:
        raise ValueError("No valid columns selected.")
    #print row range and get input
    print(f"Row Range: {len(df)} rows")
    start_row = int(input("Enter the starting row number (1-based index): "))
    end_row = int(input("Enter the ending row number (1-based index): "))
    if start_row < 1 or end_row > len(df) or start_row > end_row:
        raise ValueError("Invalid row range.")
    
    extracted_data = df.iloc[start_row - 1:end_row, :][selected_columns]
    return extracted_data

try:
    # Input and process the first file
    file1 = input("Enter the first file name (with path): ")
    print(f"Processing file: {file1}")
    data1 = get_data_from_file(file1)
    print("Data from file 1 extracted successfully.")
    
    # Input and process the second file
    file2 = input("Enter the second file name (with path): ")
    print(f"Processing file: {file2}")
    data2 = get_data_from_file(file2)
    print("Data from file 2 extracted successfully.")

    # Reset the index for both DataFrames
    data1_reset = data1.reset_index(drop=True)
    data2_reset = data2.reset_index(drop=True)

    print(data1_reset)
    print(data2_reset)
    # Compare the content
    are_equal = data1_reset.equals(data2_reset)
    print(f"Comparison result (ignoring index): {are_equal}")

    # Compare the extracted data
    #print(data1)
    #print(data2)
    #are_equal = data1.equals(data2)
    #print(f"Comparison result: {are_equal}")
    
except Exception as e:
    print(f"An error occurred: {e}")
