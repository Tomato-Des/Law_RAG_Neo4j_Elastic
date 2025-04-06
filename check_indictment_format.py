#!/usr/bin/env python
# -*- coding: utf-8 -*-

import pandas as pd
import re
import sys
import os
import time
from typing import List, Tuple, Dict, Optional, Union

def validate_indictment_format(text: str) -> Tuple[bool, str]:
    """
    Validate if the indictment follows the required format:
    1. Contains "一、" (no space requirement)
    2. Contains "二、" (with whitespace or newline before it)
    3. Contains "（一）" (with whitespace or newline before it)
    4. Contains "綜上所陳" or "綜上所述" (no space requirement)
    5. These markers appear in the correct order
    
    Args:
        text: The text to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    # Check if text is a string
    if not isinstance(text, str):
        return False, "不是文字類型"
    
    # Trim any leading/trailing whitespace
    text = text.strip()
    
    # Check if text is empty
    if not text:
        return False, "空文本"
    
    # Find positions of required markers
    pos_1 = text.find("一、")
    
    # For the second marker and "（一）"/"(一)", we'll use regex to ensure there's whitespace before them
    matches_2 = list(re.finditer(r'(?:\s)二、', text))
    matches_section_1 = list(re.finditer(r'(?:\s)[（(]一[）)]', text))
    
    # For the conclusion, find either "綜上所陳" or "綜上所述"
    pos_conclusion_1 = text.find("綜上所陳")
    pos_conclusion_2 = text.find("綜上所述")
    
    # Use the one that appears in the text (prefer "綜上所陳" if both appear)
    if pos_conclusion_1 != -1:
        pos_conclusion = pos_conclusion_1
        conclusion_text = "綜上所陳"
    elif pos_conclusion_2 != -1:
        pos_conclusion = pos_conclusion_2
        conclusion_text = "綜上所述"
    else:
        pos_conclusion = -1
        conclusion_text = None
    
    # Check if all required markers exist
    if pos_1 == -1:
        return False, "缺少「一、」標記"
    
    if not matches_2:
        return False, "缺少「二、」標記或其前面沒有空格或換行"
    
    if not matches_section_1:
        return False, "缺少「（一）」或「(一)」標記或其前面沒有空格或換行"
    
    if pos_conclusion == -1:
        return False, "缺少「綜上所陳」或「綜上所述」標記"
    
    # Get positions
    pos_2 = matches_2[0].start() + 1  # +1 to point to the actual "二" character
    pos_section_1 = matches_section_1[0].start() + 1  # +1 to point to the actual "（" character
    
    # Check if they are in correct order
    if not (pos_1 < pos_2 < pos_section_1 < pos_conclusion):
        # 取得實際的括號格式用於錯誤消息
        section_marker = text[pos_section_1:pos_section_1+3] if pos_section_1 != -1 else "（一）或(一)"
        return False, f"標記順序錯誤：一、({pos_1}) 二、({pos_2}) {section_marker}({pos_section_1}) {conclusion_text}({pos_conclusion})"
    
    # Additional check: Make sure "一、" is at the beginning (or very close)
    if pos_1 > 3:  # Allow some flexibility for potential whitespace or quotes
        return False, f"「一、」不在開頭附近，位置在 {pos_1}"
    
    # Capture the content of the different parts
    part1 = text[pos_1:pos_2-1].strip()
    part2 = text[pos_2:pos_section_1-1].strip()
    part3 = text[pos_section_1:pos_conclusion].strip()
    part4 = text[pos_conclusion:].strip()
    
    # Basic check to ensure parts aren't empty
    if not part1:
        return False, "第一部分（一、）內容為空"
    if not part2:
        return False, "第二部分（二、）內容為空"
    if not part3:
        # 取得實際的括號格式用於錯誤消息
        section_marker = text[pos_section_1:pos_section_1+3] if pos_section_1 != -1 else "（一）或(一)"
        return False, f"第三部分（{section_marker}）內容為空"
    if not part4:
        return False, f"第四部分（{conclusion_text}）內容為空"
    
    return True, "格式正確"

def main():
    """Main function to validate Excel file formats"""
    start_time = time.time()
    
    try:
        print("=== 起訴狀格式驗證工具 ===")
        
        # Ask for Excel file path
        file_path = input("\n請輸入 Excel 文件路徑: ").strip()
        
        if not os.path.exists(file_path):
            print(f"錯誤: 找不到文件 '{file_path}'")
            return
        
        # Load Excel file
        print(f"\n正在讀取 Excel 文件 '{file_path}'...")
        try:
            xl = pd.ExcelFile(file_path)
            print("文件讀取成功!")
        except Exception as e:
            print(f"錯誤: 無法讀取 Excel 文件: {str(e)}")
            return
        
        # Display and select sheet
        print("\n可用的工作表:")
        for i, sheet in enumerate(xl.sheet_names):
            print(f"{i+1}: {sheet}")
        
        sheet_index = int(input("\n請選擇工作表 (輸入數字): ").strip()) - 1
        
        if sheet_index < 0 or sheet_index >= len(xl.sheet_names):
            print("錯誤: 無效的工作表選擇")
            return
        
        selected_sheet = xl.sheet_names[sheet_index]
        print(f"已選擇工作表: {selected_sheet}")
        
        # Load the selected sheet
        try:
            df = pd.read_excel(file_path, sheet_name=selected_sheet)
            print(f"工作表 '{selected_sheet}' 加載成功，共 {len(df)} 行")
        except Exception as e:
            print(f"錯誤: 無法加載工作表 '{selected_sheet}': {str(e)}")
            return
        
        # Display and select column
        print("\n可用的列:")
        for i, col in enumerate(df.columns):
            print(f"{i+1}: {col}")
        
        col_index = int(input("\n請選擇要驗證的列 (輸入數字): ").strip()) - 1
        
        if col_index < 0 or col_index >= len(df.columns):
            print("錯誤: 無效的列選擇")
            return
        
        selected_col = df.columns[col_index]
        print(f"已選擇列: {selected_col}")
        
        # Select row range
        print(f"\n可用行範圍: 0 到 {len(df)-1}")
        start_row = int(input("請輸入起始行 (預設為 0): ").strip() or "0")
        end_row = int(input(f"請輸入結束行 (預設為 {len(df)-1}): ").strip() or str(len(df)-1))
        
        if start_row < 0 or start_row >= len(df) or end_row < start_row or end_row >= len(df):
            print("錯誤: 無效的行範圍")
            return
        
        # Validate texts
        print(f"\n正在驗證從第 {start_row} 行到第 {end_row} 行的資料...")
        
        invalid_rows = []
        total_rows = end_row - start_row + 1
        processed = 0
        
        for row_idx in range(start_row, end_row + 1):
            text = df.iloc[row_idx][selected_col]
            is_valid, error_msg = validate_indictment_format(text)
            
            if not is_valid:
                invalid_rows.append((row_idx, error_msg))
            
            processed += 1
            if processed % 100 == 0 or processed == total_rows:
                print(f"已處理 {processed}/{total_rows} 行 ({processed/total_rows*100:.1f}%)")
        
        # Report results
        print("\n=== 驗證結果 ===")
        print(f"總行數: {total_rows}")
        print(f"格式正確: {total_rows - len(invalid_rows)}")
        print(f"格式錯誤: {len(invalid_rows)}")
        
        if invalid_rows:
            print("\n格式錯誤的行:")
            for row_idx, error_msg in invalid_rows:
                print(f"行 {row_idx}: {error_msg}")
        else:
            print("\n所有文本格式正確!")
    
    except Exception as e:
        print(f"\n執行過程中發生錯誤: {str(e)}")
        import traceback
        traceback.print_exc()
    
    finally:
        end_time = time.time()
        elapsed_time = end_time - start_time
        
        minutes = int(elapsed_time // 60)
        seconds = int(elapsed_time % 60)
        
        print(f"\n總執行時間: {minutes}m {seconds}s")

if __name__ == "__main__":
    main()