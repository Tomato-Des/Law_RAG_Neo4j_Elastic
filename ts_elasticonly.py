#Only retrieve elastic search part
# ts_retrieve_main.py
import sys
import time
import os
import re
from typing import List, Dict
import traceback
from dotenv import load_dotenv
from ts_elastic_system import RetrievalSystem

def main():
    """Main function to run the legal document retrieval system"""
    start_time = time.time()
    retrieval_system = None
    
    try:
        print("初始化檢索系統...")
        # Initialize retrieval system
        retrieval_system = RetrievalSystem()
        
        # Get user query
        print("\n請輸入 User Query (請貼上完整的律師回覆文本，格式需包含「一、二、三、」三個部分)")
        print("輸入完畢後按 Enter 再輸入 'q' 或 'quit' 結束:")
        user_input_lines = []
        while True:
            line = input()
            if line.lower() in ['q', 'quit']:
                break
            user_input_lines.append(line)
            
        user_query = "\n".join(user_input_lines)
        
        if not user_query.strip():
            print("未輸入查詢內容，程序結束")
            return
        
        # Choose search type
        print("\n請選擇搜尋類型:")
        print("1: 使用 'full' 文本進行搜尋")
        print("2: 使用 'fact' 文本進行搜尋")
        print("3: 使用 'fact+injuries' 文本進行搜尋")
        
        search_type_choice = input("輸入 1, 2 或 3: ").strip()
        
        if search_type_choice == '1':
            search_type = "full"
        elif search_type_choice == '2':
            search_type = "fact"
        elif search_type_choice == '3':
            search_type = "fact+injuries"
        else:
            print("無效選擇，程序結束")
            return
        
        # Choose k for top-k
        try:
            k = int(input("\n請輸入要搜尋的 Top-K 數量: ").strip())
            if k <= 0:
                print("K 必須大於 0，程序結束")
                return
        except ValueError:
            print("無效的 K 值，程序結束")
            return
        
        # Search Elasticsearch
        print(f"\n在 Elasticsearch 中搜索 '{search_type}' 類型的 Top {k} 個文檔...")
        search_results = retrieval_system.search_elasticsearch(user_query, search_type, k)
        
        if not search_results:
            print("未找到相符的文檔，程序結束")
            return
        
        # Print search results with adjusted case IDs
        print("\n搜索結果:")
        for i, result in enumerate(search_results):
            adjusted_case_id = int(result['case_id']) + 1  # Adjust case ID to start from 0
            print(f"{i+1}. Case ID: {adjusted_case_id}, 相似度分數: {result['score']:.4f}")
            print(f"   Chunk ID: {result['chunk_id']}, 類型: {result['text_type']}")
            print(f"\n   匹配的文本片段:")
            print(f"   {result['text']}")
            
            # Get and display the full case text
            full_text = retrieval_system.get_full_case_text(result['case_id'])
            print(f"\n   案件全文:")
            print(f"   {full_text}")
            
            print("\n" + "-" * 80 + "\n")
        
        # Extract case IDs
        case_ids = [int(result['case_id']) + 1 for result in search_results]  # Adjust case IDs
        print(f"找到的 Case IDs: {case_ids}")
        
        print("\n檢索完成，程序結束")
        
    except Exception as e:
        print(f"執行過程中發生錯誤: {str(e)}")
        traceback.print_exc()
    finally:
        if retrieval_system:
            retrieval_system.close()
        
        end_time = time.time()
        elapsed_time = end_time - start_time
        
        hours = int(elapsed_time // 3600)
        minutes = int((elapsed_time % 3600) // 60)
        seconds = int(elapsed_time % 60)
        
        print(f"\n執行時間: {hours}h {minutes}m {seconds}s")

if __name__ == "__main__":
    main()