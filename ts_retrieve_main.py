# ts_retrieve_main.py
import sys
import time
import os
from typing import List, Dict
import traceback
from dotenv import load_dotenv
from ts_retrieval_system import RetrievalSystem

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
        
        search_type_choice = input("輸入 1 或 2: ").strip()
        
        if search_type_choice == '1':
            search_type = "full"
        elif search_type_choice == '2':
            search_type = "fact"
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
        
        # Choose whether to include conclusion
        print("\n請選擇要抓取的內容:")
        print("1: 只抓取 'used_law'")
        print("2: 抓取 'used_law' 和 'conclusion'")
        
        include_conclusion_choice = input("輸入 1 或 2: ").strip()
        
        if include_conclusion_choice == '1':
            include_conclusion = False
        elif include_conclusion_choice == '2':
            include_conclusion = True
        else:
            print("無效選擇，程序結束")
            return
        
        # Search Elasticsearch
        print(f"\n在 Elasticsearch 中搜索 '{search_type}' 類型的 Top {k} 個文檔...")
        search_results = retrieval_system.search_elasticsearch(user_query, search_type, k)
        
        if not search_results:
            print("未找到相符的文檔，程序結束")
            return
        
        # Print search results
        print("\n搜索結果:")
        for i, result in enumerate(search_results):
            print(f"{i+1}. Case ID: {result['case_id']}, 相似度分數: {result['score']:.4f}")
            print(f"   Chunk ID: {result['chunk_id']}, 類型: {result['text_type']}")
            # Print a preview of the text
            preview = result['text'][:100].replace('\n', ' ') + "..." if len(result['text']) > 100 else result['text'].replace('\n', ' ')
            print(f"   Text: {preview}")
            print()
        
        # Extract case IDs
        case_ids = [result['case_id'] for result in search_results]
        print(f"找到的 Case IDs: {case_ids}")
        
        # Get laws from Neo4j
        print("\n從 Neo4j 獲取相關法條...")
        laws = retrieval_system.get_laws_from_neo4j(case_ids)
        
        if not laws:
            print("警告: 未找到相關法條")
            laws = []
        
        # Count law occurrences
        law_counts = retrieval_system.count_law_occurrences(laws)
        print("\n法條出現頻率:")
        for law, count in sorted(law_counts.items(), key=lambda x: x[1], reverse=True):
            print(f"法條 {law}: 出現 {count} 次")
        
        # Choose threshold j
        try:
            j = int(input(f"\n請輸入法條保留閾值 (出現次數 >= j): ").strip())
            if j <= 0:
                print("閾值必須大於 0，設置為 1")
                j = 1
        except ValueError:
            print("無效的閾值，設置為 1")
            j = 1
        
        # Filter laws by occurrence threshold
        filtered_law_numbers = retrieval_system.filter_laws_by_occurrence(law_counts, j)
        print(f"\n符合出現次數 >= {j} 的法條: {filtered_law_numbers}")
        
        # Get law contents
        law_contents = []
        if filtered_law_numbers:
            law_contents = retrieval_system.get_law_contents(filtered_law_numbers)
            print("\n獲取到的法條內容:")
            for law in law_contents:
                print(f"法條 {law['number']}: {law['content']}")
        
        # Get conclusions if requested
        conclusions = []
        average_compensation = 0.0
        
        if include_conclusion:
            print("\n從 Neo4j 獲取結論文本...")
            conclusions = retrieval_system.get_conclusions_from_neo4j(case_ids)
            
            if not conclusions:
                print("警告: 未找到結論文本")
            else:
                # Calculate average compensation
                average_compensation = retrieval_system.calculate_average_compensation(conclusions)
                print(f"\n平均賠償金額: {average_compensation:.2f} 元")
                print("提取的賠償金額:")
                for i, conclusion in enumerate(conclusions):
                    amount = retrieval_system.extract_compensation_amount(conclusion["conclusion_text"])
                    if amount:
                        print(f"Case ID {conclusion['case_id']}: {amount:.2f} 元")
                    else:
                        print(f"Case ID {conclusion['case_id']}: 無法提取賠償金額")
        
        # Process user query
        print("\n處理用戶查詢...")
        query_sections = retrieval_system.split_user_query(user_query)
        
        # Check if query was split correctly
        if not query_sections["accident_facts"]:
            print("警告: 無法正確分割查詢中的事故事實部分")
        if not query_sections["injuries"]:
            print("警告: 無法正確分割查詢中的受傷情形部分")
        if not query_sections["compensation_facts"]:
            print("警告: 無法正確分割查詢中的賠償事實部分")
        
        # Generate first part with LLM
        print("\n生成第一部分 (事故事實)...")
        facts_prompt = f"""你是一個台灣原告律師，你現在要幫忙完成車禍起訴狀裏的案件事實陳述的部分，你只需要根據下列格式進行輸出，並確保每個段落內容完整** 禁止輸出格式以外的任何東西 **： 
        一、事實概述：完整描述事故經過，案件過程盡量越詳細越好，要使用"緣被告"做開頭，並且在這段中都要以"原告""被告"作人物代稱，如果我給你的案件事實中沒有出現原告或被告的姓名，則請直接使用"原告""被告"作為代稱，請絕對不要自己憑空杜撰被告的姓名 
        備註:請記得在"事實概述"前面加上"一、", ** 禁止輸出格式以外的任何東西 **   
        ###  案件事實：  {query_sections['accident_facts']}"""
        
        first_part = retrieval_system.call_llm(facts_prompt)
        
        # Generate hardcoded law section
        law_section = "二、按「"
        if law_contents:
            for i, law in enumerate(law_contents):
                content = law["content"]
                if "：" in content:
                    content = content.split("：")[1].strip()
                elif ":" in content:
                    content = content.split(":")[1].strip()
                
                if i > 0:
                    law_section += "、「"
                law_section += content
                law_section += "」"
            
            law_section += "民法第"
            for i, law in enumerate(law_contents):
                if i > 0:
                    law_section += "、第"
                law_section += law["number"]
                law_section += "條"
            
            law_section += "分別定有明文。查被告因上開侵權行為，使原告受有下列損害，依前揭規定，被告應負損害賠償責任："
        else:
            law_section += "NO LAW"#"因故意或過失，不法侵害他人之權利者，負損害賠償責任。」、「汽車、機車或其他非依軌道行駛之動力車輛，在使用中加損害於他人者，駕駛人應賠償因此所生之損害。」民法第184條第1項前段、第191條之2本文分別定有明文。查被告因上開侵權行為，使原告受有下列損害，依前揭規定，被告應負損害賠償責任："
        
        # Generate second part with LLM
        print("\n生成第二部分 (損害賠償)...")
        compensation_prompt = f"""你是一個台灣原告律師，你需要幫忙起草車禍起訴狀中的賠償請求部分。請根據以下提供的受傷情形和損失情況，列出所有可能的賠償項目，每個項目需要有明確的金額和原因。最後需要有一個"綜上所陳"的總結，列出總賠償金額。

格式要求：
- 使用（一）、（二）等標記不同賠償項目
- 每個項目包含標題、金額和請求原因
-若涉及多名原告或多名被告,請分別列出各自的賠償項目及原因。
- 最後使用僅一個"綜上所陳"進行總結，多名原告也應該只有一個"綜上所陳"

多名原告範本：
    原告A部分:
    [損害項目名稱1]：[金額]元
    事實根據：...
    [損害項目名稱2]：[金額]元
    事實根據：...
    [原告B]部分:
    [損害項目名稱1]：[金額]元
    事實根據：...
    [損害項目名稱2]：[金額]元
    事實根據：...

    
綜上所陳，被告應賠償[原告A]之損害，包含[損害項目名稱1]...元、[損害項目名稱2]...元、[損害項目名稱]... ...元、總計...元；應賠償[原告B]之損害，包含[損害項目名稱1]...元、[損害項目名稱2]...元及[損害項目名稱]... ...元，總計...元。並自起訴狀副本送達翌日起至清償日止，按年息5%計算之利息。 

請根據下列受傷情形和損失情況，列出詳細賠償請求：

受傷情形：
{query_sections['injuries']}

損失情況：
{query_sections['compensation_facts']}
"""
#""" 若有平均賠償金額參考，可以考慮接近 {average_compensation:.2f} 元，但應根據實際案情調整。"""
        
        second_part = retrieval_system.call_llm(compensation_prompt)
        
        # Combine all parts
        final_response = f"{first_part}\n\n{law_section}\n\n{second_part}"
        
        # Print final response
        print("\n========== 最終起訴狀 ==========\n")
        print(final_response)
        print("\n========== 起訴狀結束 ==========\n")
        
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