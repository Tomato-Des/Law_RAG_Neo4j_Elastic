import pandas as pd
import re
import os

# Modified allowed terms to include 191-2
allowed_terms = ["第184條", "第185條", "第187條", "第188條", 
                "第191-2條", "第193條", "第195條", "第213條", 
                "第216條", "第217條"]

# Modified conversion dictionary to handle 191/191-2 case
trad_to_arabic = {
    "第一百八十四條": "第184條",
    "第一百八十五條": "第185條",
    "第一百八十七條": "第187條",
    "第一百八十八條": "第188條",
    "第一百九十一條": "第191-2條",  # Changed this to map to 191-2
    "第一百九十一之二條": "第191-2條",
    "第191條": "第191-2條",  # Added direct mapping
    "第一百九十三條": "第193條",
    "第一百九十五條": "第195條",
    "第兩百一十三條": "第213條",
    "第兩百十三條": "第213條",
    "第兩百一十六條": "第216條",
    "第兩百十六條": "第216條",
    "第兩百一十七條": "第217條",
    "第兩百十七條": "第217條"
}

def detect_file_type(file_path):
    """Detects the file type (xlsx or csv)."""
    _, ext = os.path.splitext(file_path)
    return ext.lower()

def load_file(file_path):
    """Loads the file based on its type."""
    file_type = detect_file_type(file_path)
    if file_type == ".xlsx":
        pd.set_option('display.max_columns', None)
        pd.set_option('display.max_colwidth', None)
        return pd.ExcelFile(file_path)
    elif file_type == ".csv":
        return pd.read_csv(file_path)
    else:
        raise ValueError("Unsupported file type. Only .xlsx and .csv are supported.")

def extract_legal_terms(text, allowed_terms, trad_to_arabic):
    """Extracts legal terms matching the allowed list, converts traditional terms to Arabic numerals, removes duplicates, and sorts."""
    # Match terms in Arabic numeral format or traditional Chinese
    matches = re.findall(r"第(?:\d+(?:-\d+)?條|[一二三四五六七八九十百千兩]+條)", text)
    
    # Convert traditional terms to Arabic numerals and handle special case for 191
    converted_matches = []
    for match in matches:
        if match in trad_to_arabic:
            converted_matches.append(trad_to_arabic[match])
        elif match == "第191條":  # Special handling for 191
            converted_matches.append("第191-2條")
        else:
            converted_matches.append(match)
    
    # Filter matches based on the allowed terms
    filtered_matches = [term for term in converted_matches if term in allowed_terms]
    
    # Remove duplicates and sort numerically
    # Modified sort key to handle hyphenated numbers
    def sort_key(x):
        nums = re.findall(r'\d+', x)
        return tuple(int(n) for n in nums)
    
    unique_sorted_matches = sorted(set(filtered_matches), key=sort_key)
    return unique_sorted_matches

try:
    # Step 1: Get file input
    file_path = input("Enter the file name (with path): ").strip()
    print(f"Processing file: {file_path}")
    
    # Step 2: Load the file
    file_data = load_file(file_path)
    
    # Step 3: If Excel file, choose a sheet
    if isinstance(file_data, pd.ExcelFile):
        sheets = file_data.sheet_names
        print("Available sheets:", sheets)
        sheet_name = input("Enter the sheet name to extract data from: ").strip()
        if sheet_name not in sheets:
            raise ValueError(f"Sheet '{sheet_name}' does not exist in the file.")
        df = file_data.parse(sheet_name=sheet_name)
    else:
        df = file_data
    
    # Step 4: Display and handle column names with newlines
    print("\nAvailable columns (with index):")
    for idx, col in enumerate(df.columns):
        print(f"{idx}: {repr(col)}")
    
    column_input = input("\nEnter the column index number or full column name: ").strip()
    
    try:
        if column_input.isdigit():
            column_idx = int(column_input)
            if 0 <= column_idx < len(df.columns):
                column_name = df.columns[column_idx]
            else:
                raise ValueError("Invalid column index")
        else:
            if column_input not in df.columns:
                column_input_with_newline = column_input.replace("\\n", "\n")
                if column_input_with_newline in df.columns:
                    column_name = column_input_with_newline
                else:
                    raise ValueError(f"Column '{column_input}' does not exist in the file.")
            else:
                column_name = column_input
    except ValueError as e:
        raise ValueError(f"Invalid column selection: {e}")
    
    print(f"Data contains rows from 1 to {len(df)}.")
    start_row = int(input("Enter the starting row number (1-based index): "))
    end_row = int(input("Enter the ending row number (1-based index): "))
    if start_row < 1 or end_row > len(df) or start_row > end_row:
        raise ValueError("Invalid row range.")
    
    selected_data = df.iloc[start_row - 1:end_row, :][column_name]
    
    results = []
    for row in selected_data:
        if isinstance(row, str):
            legal_terms = extract_legal_terms(row, allowed_terms, trad_to_arabic)
            if legal_terms:
                results.append({"法條": ", ".join(legal_terms), "Original Text": row})
            else:
                results.append({"法條": "0", "Original Text": row})
        else:
            results.append({"法條": "0", "Original Text": row})
    
    output_df = pd.DataFrame(results)
    output_file = "法條_and_oritext(Output)(with漢字).xlsx"
    output_df.to_excel(output_file, index=False)
    
    print(f"Extraction and filtering complete. Data saved to {output_file}.")
    
except Exception as e:
    print(f"An error occurred: {e}")



"""import pandas as pd
import re
import os

# First define all the required constants at the top
allowed_terms = ["第184條", "第185條", "第187條", "第188條", 
                 "第191條", "第193條", "第195條", "第213條", 
                 "第216條", "第217條"]

trad_to_arabic = {
    "第一百八十四條": "第184條",
    "第一百八十五條": "第185條",
    "第一百八十七條": "第187條",
    "第一百八十八條": "第188條",
    "第一百九十一條": "第191條",
    "第一百九十三條": "第193條",
    "第一百九十五條": "第195條",
    "第兩百一十三條": "第213條",
    "第兩百十三條": "第213條",
    "第兩百一十六條": "第216條",
    "第兩百十六條": "第216條",
    "第兩百一十七條": "第217條",
    "第兩百十七條": "第217條"
}

def detect_file_type(file_path):
    """"""Detects the file type (xlsx or csv).""""""
    _, ext = os.path.splitext(file_path)
    return ext.lower()

def load_file(file_path):
    """"""Loads the file based on its type.""""""""
    file_type = detect_file_type(file_path)
    if file_type == ".xlsx":
        # Add display options to show full column names without truncation
        pd.set_option('display.max_columns', None)
        pd.set_option('display.max_colwidth', None)
        return pd.ExcelFile(file_path)
    elif file_type == ".csv":
        return pd.read_csv(file_path)
    else:
        raise ValueError("Unsupported file type. Only .xlsx and .csv are supported.")

def extract_legal_terms(text, allowed_terms, trad_to_arabic):
    """"""Extracts legal terms matching the allowed list, converts traditional terms to Arabic numerals, removes duplicates, and sorts.""""""""
    # Match terms in Arabic numeral format or traditional Chinese
    matches = re.findall(r"第(?:\d+條|[一二三四五六七八九十百千兩]+條)", text)
    
    # Convert traditional terms to Arabic numerals
    converted_matches = []
    for match in matches:
        if match in trad_to_arabic:
            converted_matches.append(trad_to_arabic[match])
        else:
            converted_matches.append(match)
    
    # Filter matches based on the allowed terms
    filtered_matches = [term for term in converted_matches if term in allowed_terms]
    
    # Remove duplicates and sort numerically
    unique_sorted_matches = sorted(set(filtered_matches), key=lambda x: int(re.search(r"\d+", x).group()))
    return unique_sorted_matches

try:
    # Step 1: Get file input
    file_path = input("Enter the file name (with path): ").strip()
    print(f"Processing file: {file_path}")
    
    # Step 2: Load the file
    file_data = load_file(file_path)
    
    # Step 3: If Excel file, choose a sheet
    if isinstance(file_data, pd.ExcelFile):
        sheets = file_data.sheet_names
        print("Available sheets:", sheets)
        sheet_name = input("Enter the sheet name to extract data from: ").strip()
        if sheet_name not in sheets:
            raise ValueError(f"Sheet '{sheet_name}' does not exist in the file.")
        df = file_data.parse(sheet_name=sheet_name)
    else:
        df = file_data
    
    # Step 4: Display and handle column names with newlines
    print("\nAvailable columns (with index):")
    for idx, col in enumerate(df.columns):
        print(f"{idx}: {repr(col)}")
    
    column_input = input("\nEnter the column index number or full column name: ").strip()
    
    try:
        if column_input.isdigit():
            column_idx = int(column_input)
            if 0 <= column_idx < len(df.columns):
                column_name = df.columns[column_idx]
            else:
                raise ValueError("Invalid column index")
        else:
            if column_input not in df.columns:
                column_input_with_newline = column_input.replace("\\n", "\n")
                if column_input_with_newline in df.columns:
                    column_name = column_input_with_newline
                else:
                    raise ValueError(f"Column '{column_input}' does not exist in the file.")
            else:
                column_name = column_input
    except ValueError as e:
        raise ValueError(f"Invalid column selection: {e}")
    
    print(f"Data contains rows from 1 to {len(df)}.")
    start_row = int(input("Enter the starting row number (1-based index): "))
    end_row = int(input("Enter the ending row number (1-based index): "))
    if start_row < 1 or end_row > len(df) or start_row > end_row:
        raise ValueError("Invalid row range.")
    
    selected_data = df.iloc[start_row - 1:end_row, :][column_name]
    
    results = []
    for row in selected_data:
        if isinstance(row, str):
            legal_terms = extract_legal_terms(row, allowed_terms, trad_to_arabic)
            if legal_terms:
                results.append({"法條": ", ".join(legal_terms), "Original Text": row})
            else:
                results.append({"法條": "0", "Original Text": row})
        else:
            results.append({"法條": "0", "Original Text": row})
    
    output_df = pd.DataFrame(results)
    output_file = "法條_and_oritext(Output)(with漢字).xlsx"
    output_df.to_excel(output_file, index=False)
    
    print(f"Extraction and filtering complete. Data saved to {output_file}.")
    
except Exception as e:
    print(f"An error occurred: {e}")
"""
