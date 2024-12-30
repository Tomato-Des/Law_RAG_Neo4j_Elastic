import pandas as pd
from typing import Tuple, Any

class ExcelReader:
    @staticmethod
    def read_excel_file() -> Tuple[Any, str, int, int]:
        try:
            # 讀取文件
            file_path = input("請輸入 Excel 文件路徑: ").strip()
            xl = pd.ExcelFile(file_path)
            print("\n可用的工作表:", xl.sheet_names)
            
            # 選擇工作表
            sheet_name = input("請輸入工作表名稱: ").strip()
            df = pd.read_excel(file_path, sheet_name=sheet_name)
            print("\n可用的列名:", df.columns.tolist())
            
            # 選擇列
            column = input("請輸入要讀取的列名: ").strip()
            if column not in df.columns:
                raise ValueError(f"找不到列名 '{column}'")
            
            # 選擇行範圍
            print(f"\n可用的行數範圍: 0 到 {len(df)-1}")
            start_row = int(input("請輸入起始行號: ").strip())
            end_row = int(input("請輸入結束行號: ").strip())
            
            # 驗證行範圍
            if start_row < 0 or end_row >= len(df) or start_row > end_row:
                raise ValueError("無效的行範圍")

            # 讀取指定範圍的數據
            selected_data = df[column][start_row:end_row+1]
            
            return selected_data, column, start_row, end_row

        except Exception as e:
            print(f"讀取 Excel 文件時發生錯誤: {str(e)}")
            raise

    @staticmethod
    def print_data(data: Any, column: str, start_row: int, end_row: int):
        print("\n讀取到的數據:")
        print(f"列名: {column}")
        print(f"行範圍: {start_row} 到 {end_row}")
        print("\n內容:")
        for idx, value in enumerate(data, start=start_row):
            print(f"行 {idx}: {value}")

def main():
    try:
        reader = ExcelReader()
        data, column, start_row, end_row = reader.read_excel_file()
        reader.print_data(data, column, start_row, end_row)
    except Exception as e:
        print(f"程式執行失敗: {str(e)}")

if __name__ == "__main__":
    main()