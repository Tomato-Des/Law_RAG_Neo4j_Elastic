import pandas as pd

# Define file path
file_path = '起訴狀案例測試.xlsx'

try:
    # Load Excel file and get sheet names
    excel_data = pd.ExcelFile(file_path)
    sheet_names = excel_data.sheet_names

    # Debug: Display sheet names
    print("Available sheets:", sheet_names)

    # Let user select a sheet
    selected_sheet = input("Enter the name of the sheet to extract data from: ")
    if selected_sheet not in sheet_names:
        raise ValueError("Invalid sheet name. Please restart the program and choose a valid sheet.")

    # Debug: Confirm selected sheet
    print(f"Selected sheet: {selected_sheet}")

    # Load the selected sheet
    sheet_data = excel_data.parse(sheet_name=selected_sheet)

    # Debug: Display column names
    print("Available columns:", sheet_data.columns.tolist())

    # Let user select columns to extract
    selected_columns = input("Enter the column names to extract (comma-separated): ").split(',')
    for column in selected_columns:
        if column.strip() not in sheet_data.columns:
            raise ValueError(f"Invalid column name: {column.strip()}. Please restart the program and choose valid columns.")

    # Debug: Confirm selected columns
    print(f"Selected columns: {selected_columns}")

    # Let user select row range to extract
    print(f"Row Range: {len(sheet_data)} rows")
    start_row = int(input("Enter the starting row number (1-based index): "))
    end_row = int(input("Enter the ending row number (1-based index): "))

    # Validate row range
    
    if start_row < 1 or end_row > len(sheet_data) or start_row > end_row:
        raise ValueError("Invalid row range. Please restart the program and provide a valid range.")
    # Extract the selected data
    extracted_data = sheet_data.iloc[start_row - 1:end_row, :][selected_columns]

    # Debug: Display extracted data
    #print("Extracted data:")
    #print(extracted_data)

    # Define output file names
    output_excel = "extracted_truth.xlsx"
    output_csv = "extracted_truth.csv"

    # Save to Excel and CSV
    extracted_data.to_excel(output_excel, index=False)
    extracted_data.to_csv(output_csv, index=False)

    # Debug: Confirm files saved
    print(f"Data successfully saved to {output_excel} and {output_csv}.")

except Exception as e:
    print(f"An error occurred: {e}")
