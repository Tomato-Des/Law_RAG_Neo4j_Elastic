#Process used_law for input index range,first input is case_id range, second input is the read in excel used law row range

import os
from dotenv import load_dotenv
import pandas as pd
from neo4j_manager import Neo4jManager
from text_processor import TextProcessor

def process_used_laws_only():
    # Load environment variables
    load_dotenv()

    # Initialize Neo4j manager
    neo4j_manager = Neo4jManager(
        uri=os.getenv('NEO4J_URI'),
        user=os.getenv('NEO4J_USER'),
        password=os.getenv('NEO4J_PASSWORD')
    )

    try:
        # Input case ID range
        start_case_id = int(input("Enter the starting case ID: ").strip())
        end_case_id = int(input("Enter the ending case ID: ").strip())
        if start_case_id > end_case_id:
            raise ValueError("Starting case ID must be less than or equal to the ending case ID.")

        # Input Excel file for `used_law`
        excel_filename = input("Enter the filename for the used law Excel file: ").strip()
        xl = pd.ExcelFile(excel_filename)

        # Show available sheets
        print("\nAvailable sheets:", xl.sheet_names)
        sheet_name = input("Enter the sheet name: ").strip()
        if sheet_name not in xl.sheet_names:
            raise ValueError(f"Sheet '{sheet_name}' not found in workbook.")

        # Load sheet and show available columns
        df = pd.read_excel(excel_filename, sheet_name=sheet_name)
        print("\nAvailable columns:", df.columns.tolist())

        column_name = input("Enter the column name containing the used law data: ").strip()
        if column_name not in df.columns:
            raise ValueError(f"Column '{column_name}' not found in the sheet.")

        # Input row range
        print(f"\nAvailable row range: 0 to {len(df[column_name]) - 1}")
        start_row = int(input("Enter the starting row number: ").strip())
        end_row = int(input("Enter the ending row number: ").strip())
        if start_row < 0 or end_row >= len(df[column_name]) or start_row > end_row:
            raise ValueError("Invalid row range.")

        # Ensure the case ID range matches the row range
        num_rows = end_row - start_row + 1
        if num_rows != (end_case_id - start_case_id + 1):
            raise ValueError("The case ID range and row range do not match in length.")

        # Process used law data for each case
        for idx, (_, row) in enumerate(df[column_name][start_row:end_row + 1].items()):
            current_case_id = start_case_id + idx
            print(f"\nProcessing used laws for case ID {current_case_id}...")

            used_laws_str = str(row).strip()
            if used_laws_str:
                law_numbers = TextProcessor.extract_law_numbers(used_laws_str)
                if not law_numbers:
                    print(f"Warning: Case ID {current_case_id} has no valid laws.")
                    continue

                for law_number in law_numbers:
                    neo4j_manager.create_law_relationships(current_case_id, law_number)

                print(f"Processed used laws for case ID {current_case_id}.")
            else:
                print(f"No used laws data for case ID {current_case_id}.")

    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        neo4j_manager.close()

if __name__ == "__main__":
    process_used_laws_only()
