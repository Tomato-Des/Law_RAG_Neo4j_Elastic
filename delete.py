# ts_retrieve_main.py
import sys
import time
import os
import re
from typing import List, Dict
import traceback
from dotenv import load_dotenv
from ts_retrieval_system import RetrievalSystem

def extract_calculate_tags(text: str) -> Dict[str, float]:
    """
    Extract and calculate the sum of values inside <calculate> </calculate> tags.
    
    Args:
        text: Text containing <calculate> </calculate> tags
        
    Returns:
        Dictionary mapping plaintiff identifiers to their total compensation amounts
    """
    print(f"\n start of calculate func")
    # Find all <calculate> </calculate> tags
    pattern = r'<calculate>(.*?)</calculate>'
    matches = re.findall(pattern, text)
    print(f"找到 {len(matches)} 個標籤內容")

    sums = {}
    default_count = 0
    
    for match in matches:
        # First try to find "原告X" pattern
        plaintiff_pattern = r'原告(\w+)'
        plaintiff_match = re.search(plaintiff_pattern, match)
        
        plaintiff_id = "default"
        
        if plaintiff_match:
            # Found "原告X" format
            plaintiff_id = plaintiff_match.group(1)
        else:
            # Try to find a name at the beginning (without "原告" prefix)
            name_pattern = r'^(\w+)'
            name_match = re.search(name_pattern, match.strip())
            
            if name_match and not name_match.group(1).isdigit():
                plaintiff_id = name_match.group(1)
            else:
                # This is a default tag
                if "default" in sums:
                    # We already have a default, create a numbered default
                    default_count += 1
                    plaintiff_id = f"原告{default_count}"
                # else use "default" as is
        
        # Extract and sum all numbers
        number_pattern = r'\d+'
        numbers = re.findall(number_pattern, match)
        
        if numbers:
            try:
                total = sum(float(num) for num in numbers)
                
                # Handle case where this plaintiff ID already exists
                if plaintiff_id in sums:
                    default_count += 1
                    plaintiff_id = f"原告{default_count}"
                
                sums[plaintiff_id] = total
                print(f"計算 {plaintiff_id}: {total}")
            except ValueError:
                print(f"警告: 無法計算標籤內的金額: {match}")
    
    # Handle case where all tags are defaults - rename them to 原告1, 原告2, etc.
    if "default" in sums and len(matches) > 1:
        default_value = sums["default"]
        del sums["default"]
        
        # Only add it back if there isn't already an 原告1
        if "原告1" not in sums:
            sums["原告1"] = default_value
        else:
            sums[f"原告{default_count+1}"] = default_value
    
    print(f"最終計算結果: {sums}")
    print(f"\n end of calculate func")
    print("========== DEBUG: 提取計算標籤結束 ==========\n")
    return sums

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
            law_section += "NO LAW"
        
        # Generate first part of compensation with LLM (without the 綜上所陳 and tags)
        print("\n生成第二部分 (損害賠償項目)...")
        compensation_prompt_part1 = f"""你是一個台灣原告律師，你需要幫忙起草車禍起訴狀中的賠償請求部分。請根據以下提供的受傷情形和損失情況，列出所有可能的賠償項目，每個項目需要有明確的金額和原因。
        **不要生成總結或者結論。**

格式要求：
- 使用（一）、（二）等標記不同賠償項目
- 每個項目包含標題、金額和請求原因
- 若涉及多名原告或多名被告，請分別列出各自的賠償項目及原因
- 金額應以數字寫明，勿使用“千”， “萬”等字眼
- 將原告A等替換成原告名字
- 禁止輸出賠償金不相關的原告資訊
- 嚴格按照範本，不要添加額外資訊

多名原告範本：
    [原告A名稱]部分:
    [損害項目名稱1]：[金額]元'\n'
    事實根據：...
    [損害項目名稱2]：[金額]元'\n'
    事實根據：...
    [原告B名稱]部分:
    [損害項目名稱1]：[金額]元'\n'
    事實根據：...
    [損害項目名稱2]：[金額]元'\n'
    事實根據：...
**範本結束**

請根據下列受傷情形和損失情況，列出詳細賠償請求：

受傷情形：
{query_sections['injuries']}

損失情況：
{query_sections['compensation_facts']}
"""
        
        compensation_part1 = retrieval_system.call_llm(compensation_prompt_part1)
        print("\n========== DEBUG: 第一部分賠償生成結果 ==========")
        print(f"前100個字符: {compensation_part1[:100]}...")
        print("========== DEBUG 結束 ==========\n")

        # Generate second part specifically for calculation tags
        print("\n生成計算標籤部分...")
        compensation_prompt_part2 = f"""你是一個台灣原告律師助手，你的任務是幫忙為賠償請求生成計算標籤。請仔細閱讀以下賠償項目清單，然後為每位原告生成一個計算標籤。

賠償項目清單:
{compensation_part1}

請為每個原告生成一個<calculate>標籤，格式如下:
<calculate>原告名稱 金額1 金額2 金額3</calculate>

計算標籤的要求:
1. 標籤內只放數字，不要包含任何文字描述、加號、等號或小計
2. 數字必須是阿拉伯數字，不要使用中文數字
3. 不要在數字中包含逗號或其他分隔符
4. 只列出原始金額，不要自行計算總和
5. 不要在金額后面加上"元"字
6. 若賠償項目清單中有原告名稱請忽略這行，如果原告名稱不明確，請使用"default"作為標籤識別符

範例:
<calculate>原告林某 10000 5000 3000</calculate>
<calculate>原告王某 8000 2000</calculate>

請僅返回計算標籤，不要添加任何其他解釋或說明。
"""

        compensation_part2 = retrieval_system.call_llm(compensation_prompt_part2)
        print("\n========== DEBUG: 計算標籤生成結果 ==========")
        print(compensation_part2)
        calc_tags = re.findall(r'<calculate>.*?</calculate>', compensation_part2)
        print(f"找到的計算標籤數量: {len(calc_tags)}")
        for i, tag in enumerate(calc_tags):
            print(f"標籤 {i+1}: {tag}")
        print("========== DEBUG 結束 ==========\n")

        # Extract and calculate sums from the tags
        print("\n提取並計算賠償金額...")
        compensation_sums = extract_calculate_tags(compensation_part2)

        # Print extracted sums
        for plaintiff, amount in compensation_sums.items():
            if plaintiff == "default":
                print(f"總賠償金額: {amount:.2f} 元")
            else:
                print(f"[原告{plaintiff}]賠償金額: {amount:.2f} 元")

        # Generate third part of compensation (綜上所陳) with LLM
        print("\n生成第三部分 (綜上所陳)...")

        # Format the compensation totals
        summary_totals = []
        for plaintiff, amount in compensation_sums.items():
            if plaintiff == "default":
                summary_totals.append(f"總計{amount:.0f}元")
            else:
                summary_totals.append(f"應賠償[原告{plaintiff}]之損害，總計{amount:.0f}元")

        summary_format = "；".join(summary_totals)

        compensation_prompt_part3 = f"""你是一個台灣原告律師，你需要幫忙完成車禍起訴狀中"綜上所陳"的總結部分。請根據以下提供的賠償項目和總額，生成適當的總結段落。

前面列出的賠償項目:
{compensation_part1}

請使用以下格式範本:
綜上所陳，被告[列出各原告的所有損害項目及對應金額]，{summary_format}。並自起訴狀副本送達翌日起至清償日止，按年息5%計算之利息。
**範本結束**
禁止輸出範本以外的任何東西
數字必須是阿拉伯數字，不要使用中文數字
請確保按照上方原本已列出的賠償項目，列出每一項損害內容及金額，不要自己計算金額，使用提供的總額數字。
"""

        print("\n========== DEBUG: 第三部分賠償提示詞 ==========")
        print(f"提示詞內容: {compensation_prompt_part3}")
        print("========== DEBUG 結束 ==========\n")

        compensation_part3 = retrieval_system.call_llm(compensation_prompt_part3)

        # Combine all parts
        final_response = f"{first_part}\n\n{law_section}\n\n{compensation_part1}\n\n{compensation_part3}"
        
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