# ts_gradio_app.py
import gradio as gr
import re
import time
import traceback
from queue import Queue
import numpy as np
from ts_retrieve_main import RetrievalSystem, get_case_type

# Create global variables to store search results between steps
search_results_global = []
query_sections_global = {}
case_type_global = ""
plaintiffs_info_global = ""
case_info_global = ""
llm_model_options = ["gemma3:27b", "kenneth85/llama-3-taiwan:8b-instruct-dpo"]

def search_cases(user_query, k_value, model_name):
    """First step: Process the user query to search for similar cases"""
    global search_results_global, query_sections_global, case_type_global, plaintiffs_info_global, case_info_global
    
    try:
        # Initialize retrieval system
        retrieval_system = RetrievalSystem(modelname=model_name)
        progress_text = "初始化檢索系統...\n"
        reference_options = ["默認（最相似案件）"]
        # Split user query
        query_sections = retrieval_system.split_user_query(user_query)
        query_sections_global = query_sections
        
        # Get case type
        case_type, plaintiffs_info, case_info_global = get_case_type(user_query, 1)
        case_type_global = case_type
        plaintiffs_info_global = plaintiffs_info
        
        progress_text += f"判斷案件類型: {case_info_global}\n"
        
        # Search Elasticsearch
        search_type = "fact"
        progress_text += f"在 Elasticsearch 中搜索 '{search_type}' 類型的 Top {k_value} 個文檔...\n"
        
        search_results = retrieval_system.search_elasticsearch(user_query, search_type, k_value, case_type)
        
        if not search_results:
            progress_text += "未找到相符的文檔，請嘗試修改查詢或減少 Top-K 數量\n"
            retrieval_system.close()
            return progress_text, case_type, "未找到相符的文檔", gr.update(visible=True, choices=reference_options)
        
        # Store search results for later use
        search_results_global = search_results
        
        # Format search results for display with full text
        top_k_text = "搜索結果:\n"
        for i, result in enumerate(search_results):
            top_k_text += f"{i+1}. Case ID: {result['case_id']}, 相似度分數: {result['score']:.4f}\n"
            #top_k_text += f"   Chunk ID: {result['chunk_id']}, 類型: {result['text_type']}\n"
            #preview = result['text']
            full_text = retrieval_system.get_full_text_from_elasticsearch(result['case_id'])
            top_k_text += f"{full_text}\n\n"
            top_k_text += f"{'='*55}\n"
            
        
        # Extract case IDs
        case_ids = [result['case_id'] for result in search_results]
        progress_text += f"找到的 Case IDs: {case_ids}\n"
        progress_text += "請從搜索結果中選擇一個參考案件，然後點擊「生成起訴狀」按鈕\n"
        
        # Prepare dropdown options for reference cases
        reference_options = [f"{i+1}: Case ID {result['case_id']}" for i, result in enumerate(search_results)]
        reference_options.insert(0, "默認（最相似案件）")
        
        retrieval_system.close()
        
        return progress_text, case_type, top_k_text, gr.update(visible=True, choices=reference_options)
    
    except Exception as e:
        error_message = f"搜索過程中發生錯誤: {str(e)}\n{traceback.format_exc()}"
        return error_message, "", "", gr.update(visible=True, choices=reference_options)

def generate_document(reference_choice, model_name):
    """Second step: Generate the legal document based on the selected reference case"""
    global search_results_global, query_sections_global, case_type_global, plaintiffs_info_global, case_info_global
    
    if not search_results_global:
        yield [
            "請先執行搜索步驟", 
            "",
            "",
            "",
            "",
            "",
            ""
        ]
        return
    
    try:
        # Initialize retrieval system
        from ts_retrieve_main import extract_calculate_tags
        retrieval_system = RetrievalSystem(modelname=model_name)
        # Determine reference case ID from dropdown selection
        if reference_choice == "默認（最相似案件）" or not reference_choice:
            most_similar_case_id = search_results_global[0]['case_id']
        else:
            # Extract index from dropdown text (Format: "1: Case ID 123")
            choice_index = int(reference_choice.split(":")[0]) - 1
            most_similar_case_id = search_results_global[choice_index]['case_id']
        
        progress_text = f"案件資訊: {case_info_global}\n案件類型: {case_type_global}\n\n使用案件 ID: {most_similar_case_id} 作為參考起訴狀...\n"
        compensation_text = ''
        first_part = ''
        law_section = ''
        compensation_part1 = ''
        conclusion_output = ''
        final_response = ''
            # Define a helper function that returns the current state array
        def current_state():
            return [
                progress_text,
                compensation_text,
                first_part,
                law_section,
                compensation_part1,
                conclusion_output,
                final_response
            ]
        yield current_state()
        
        # Get full indictment text from Neo4j for the reference case
        reference_indictment = retrieval_system.get_indictment_from_neo4j(most_similar_case_id)
        
        if not reference_indictment:
            progress_text += "警告: 無法獲取參考案件的起訴狀，將使用標準生成流程\n"
            reference_parts = {
                "fact_text": "",
                "law_text": "",
                "compensation_text": "",
                "conclusion_text": ""
            }
        else:
            # Split the indictment into parts
            progress_text += "分割參考案件起訴狀...\n"
            reference_parts = retrieval_system.split_indictment_text(reference_indictment)
            progress_text += "參考案件分割完成\n\n"
        
        yield current_state()
        
        # Extract case IDs and get laws from Neo4j
        case_ids = [result['case_id'] for result in search_results_global]
        progress_text += f"從 Neo4j 獲取相關法條...\n"
        
        yield current_state()
        
        laws = retrieval_system.get_laws_from_neo4j(case_ids)
        
        if not laws:
            progress_text += "警告: 未找到相關法條\n"
            laws = []
        
        # Count law occurrences
        law_counts = retrieval_system.count_law_occurrences(laws)
        progress_text += "法條出現頻率:\n"
        for law, count in sorted(law_counts.items(), key=lambda x: x[1], reverse=True):
            progress_text += f"法條 {law}: 出現 {count} 次\n"
        
        # Determine j based on k value
        k_value = len(search_results_global)
        j_values = {1: 1, 2: 1, 3: 2, 4: 2, 5: 2}
        j = j_values.get(k_value, 1)
        
        progress_text += f"根據 k={k_value} 設置法條保留閾值 j={j}\n"
        
        # Filter laws by occurrence threshold
        filtered_law_numbers = retrieval_system.filter_laws_by_occurrence(law_counts, j)
        progress_text += f"符合出現次數 >= {j} 的法條: {filtered_law_numbers}\n"
        
        yield current_state()
        # Add law check logic from original code
        progress_text += "\n進行法條適用性檢查...\n"
        progress_text += "使用關鍵詞映射生成可能適用的法條...\n"
        yield current_state()
        keyword_laws = retrieval_system.get_laws_by_keyword_mapping(
            query_sections_global['accident_facts'], 
            query_sections_global['injuries'],
            query_sections_global['compensation_facts']
        )
        progress_text += f"關鍵詞映射生成的法條: {keyword_laws}\n"
        # Compare with filtered laws
        missing_laws = [law for law in keyword_laws if law not in filtered_law_numbers]
        extra_laws = [law for law in filtered_law_numbers if law not in keyword_laws]
        progress_text += f"可能缺少的法條: {missing_laws}\n"
        progress_text += f"可能多餘的法條: {extra_laws}\n"
        yield current_state()
        # Check each missing law
        for law_number in missing_laws:
            progress_text += f"\n檢查缺少的法條 {law_number}...\n"
            
            yield current_state()
            
            # Get law content from Neo4j
            law_content = ""
            with retrieval_system.neo4j_driver.session() as session:
                query = """
                MATCH (l:law_node {number: $number})
                RETURN l.content AS content
                """
                result = session.run(query, number=law_number)
                record = result.single()
                if record and record.get("content"):
                    law_content = record["content"]
            
            if not law_content:
                progress_text += f"無法獲取法條 {law_number} 的內容，跳過檢查\n"
                continue
            
            # Check if the law is applicable
            check_result = retrieval_system.check_law_content(
                query_sections_global['accident_facts'],
                query_sections_global['injuries'],
                law_number,
                law_content
            )
            
            progress_text += f"法條 {law_number} 檢查結果: {check_result['result']}\n"
            progress_text += f"原因: {check_result['reason']}\n"
            
            # Add to filtered laws if applicable
            if check_result['result'] == 'pass':
                progress_text += f"添加法條 {law_number} 到適用法條列表\n"
                filtered_law_numbers.append(law_number)
                # Sort the list again
                filtered_law_numbers = sorted(filtered_law_numbers)
        # Check each extra law
        for law_number in extra_laws:
            progress_text += f"\n檢查可能多餘的法條 {law_number}...\n"
            
            yield current_state()
            
            # Get law content
            law_content = ""
            with retrieval_system.neo4j_driver.session() as session:
                query = """
                MATCH (l:law_node {number: $number})
                RETURN l.content AS content
                """
                result = session.run(query, number=law_number)
                record = result.single()
                if record and record.get("content"):
                    law_content = record["content"]
            
            if not law_content:
                progress_text += f"無法獲取法條 {law_number} 的內容，跳過檢查\n"
                continue
            
            # Check if the law is applicable
            check_result = retrieval_system.check_law_content(
                query_sections_global['accident_facts'],
                query_sections_global['injuries'],
                law_number,
                law_content
            )
            
            progress_text += f"法條 {law_number} 檢查結果: {check_result['result']}\n"
            progress_text += f"原因: {check_result['reason']}\n"
            
            # Remove from filtered laws if not applicable
            if check_result['result'] == 'fail':
                progress_text += f"從適用法條列表中移除法條 {law_number}\n"
                filtered_law_numbers.remove(law_number)
        # Filter out duplicates and sort
        filtered_law_numbers = sorted(list(set(filtered_law_numbers)))
        progress_text += f"\n最終適用法條列表: {filtered_law_numbers}\n\n"
        yield current_state()
        
        # Get conclusions and calculate compensation amounts
        progress_text += "從 Neo4j 獲取結論文本...\n"
        
        yield current_state()
        
        conclusions = retrieval_system.get_conclusions_from_neo4j(case_ids)
        
        compensation_text = "賠償金額:\n"
        average_compensation = 0.0
        
        if not conclusions:
            progress_text += "警告: 未找到結論文本\n"
            compensation_text += "未找到結論文本，無法計算賠償金額"
        else:
            # Calculate average compensation
            average_compensation = retrieval_system.calculate_average_compensation(conclusions)
            progress_text += f"平均賠償金額: {average_compensation:.2f} 元\n\n"
            
            # Format compensation amounts for display
            for i, conclusion in enumerate(conclusions):
                amount = retrieval_system.extract_compensation_amount(conclusion["conclusion_text"])
                if amount:
                    compensation_text += f"Case ID {conclusion['case_id']}: {amount:.2f} 元\n"
                else:
                    compensation_text += f"Case ID {conclusion['case_id']}: 無法提取賠償金額\n"
            
            compensation_text += f"\n平均賠償金額: {average_compensation:.2f} 元"
        
        yield current_state()
        
        # Generate summary for quality check
        progress_text += "生成案件摘要以供質量檢查...\n"
        
        yield current_state()
        
        case_summary = retrieval_system.generate_case_summary(
            query_sections_global['accident_facts'], 
            query_sections_global['injuries']
        )
        progress_text += f"案件摘要:\n{case_summary}\n\n"
        
        yield current_state()
        
        # Generate facts part
        progress_text += "生成第一部分 (事故事實)...\n"
        
        yield current_state()
        
        max_attempts = 5
        first_part = None
        
        for attempt in range(1, max_attempts + 1):
            progress_text += f"正在進行第 {attempt} 次嘗試生成事故事實...\n"
            progress_text += f"參考案件事實陳述部分:\n{reference_parts['fact_text']}\n\n"
            
            yield current_state()
            
            first_part = retrieval_system.generate_facts(
                query_sections_global['accident_facts'],
                reference_parts['fact_text']
            )
            
            progress_text += f"生成的事故事實:\n{first_part}\n\n"
            first_part = retrieval_system.clean_facts_part(first_part)
            #progress_text += f"清理後的事故事實:\n{first_part}\n"
            
            # Check quality
            progress_text += "檢查生成質量...\n"
            quality_check = retrieval_system.check_fact_quality(first_part, case_summary)
            progress_text += f"質量檢查結果: {quality_check['result']}\n"
            progress_text += f"原因: {quality_check['reason']}\n"
            
            yield current_state()
            
            if quality_check['result'] == 'pass':
                progress_text += "質量檢查通過，繼續下一步\n\n"
                break
                
            if attempt == max_attempts:
                progress_text += f"警告: 達到最大嘗試次數 ({max_attempts})，使用最後一次生成的結果\n\n"
        
        # Generate law section
        progress_text += "生成法條部分...\n"
        
        law_section = "二、按「"
        if filtered_law_numbers:
            # Get law contents
            law_contents = retrieval_system.get_law_contents(filtered_law_numbers)
            
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
        
        progress_text += f"生成的法條部分:\n{law_section}\n\n"
        
        yield current_state()
        
        # Generate compensation part 1
        progress_text += "生成第一部分 (損害賠償項目)...\n"
        
        yield current_state()
        
        compensation_part1 = None
        for part1_attempt in range(1, 6):
            progress_text += f"正在進行第 {part1_attempt} 次嘗試生成賠償項目...\n"
            
            yield current_state()
            
            compensation_part1 = retrieval_system.generate_compensation_part1(
                query_sections_global['injuries'],
                query_sections_global['compensation_facts'],
                True,  # include_conclusion
                average_compensation,
                case_type_global,
                plaintiffs_info_global
            )
            
            progress_text += f"生成的賠償項目:\n{compensation_part1}\n\n"
            compensation_part1 = retrieval_system.clean_compensation_part(compensation_part1)
            #progress_text += f"清理後的賠償項目:\n{compensation_part1}\n"
            
            # Check quality
            progress_text += "檢查賠償項目質量...\n"
            quality_check = retrieval_system.check_compensation_part1(
                compensation_part1, 
                query_sections_global['injuries'],
                query_sections_global['compensation_facts'],
                plaintiffs_info_global
            )
            
            progress_text += f"質量檢查結果: {quality_check['result']}\n"
            progress_text += f"原因: {quality_check['reason']}\n"
            
            yield current_state()
            
            if quality_check['result'] == 'pass':
                progress_text += "質量檢查通過，繼續下一步\n\n"
                break
                
            if part1_attempt == 5:
                progress_text += "警告: 達到最大嘗試次數 (5)，使用最後一次生成的賠償項目\n\n"
        
        # Generate part 2 (calculation tags)
        progress_text += "生成第二部分 (計算標籤)...\n"
        
        yield current_state()
        
        compensation_part2 = None
        for part2_attempt in range(1, 4):
            progress_text += f"正在進行第 {part2_attempt} 次嘗試生成計算標籤...\n"
            
            yield current_state()
            
            compensation_part2 = retrieval_system.generate_compensation_part2(compensation_part1, plaintiffs_info_global)
            
            progress_text += f"生成的計算標籤:\n{compensation_part2}\n"
            
            # Check quality
            progress_text += "檢查計算標籤質量...\n"
            quality_check = retrieval_system.check_calculation_tags(compensation_part1, compensation_part2)
            progress_text += f"質量檢查結果: {quality_check['result']}\n"
            progress_text += f"原因: {quality_check['reason']}\n"
            
            if quality_check['result'] == 'pass':
                progress_text += "質量檢查通過，繼續下一步\n\n"
                break
                
            if part2_attempt == 3:
                progress_text += "警告: 達到最大嘗試次數 (3)，使用最後一次生成的計算標籤\n\n"
        
        # Extract and calculate sums from the tags
        progress_text += "提取並計算賠償金額...\n"
        
        yield current_state()
        
        compensation_sums = extract_calculate_tags(compensation_part2)
        
        progress_text += "計算的賠償金額:\n"
        for plaintiff, amount in compensation_sums.items():
            if plaintiff == "default":
                progress_text += f"總賠償金額: {amount:.2f} 元\n"
            else:
                progress_text += f"[原告{plaintiff}]賠償金額: {amount:.2f} 元\n"
        
        # Format the compensation totals for part 3
        summary_totals = []
        for plaintiff, amount in compensation_sums.items():
            if plaintiff == "default":
                summary_totals.append(f"總計{amount:.0f}元")
            else:
                summary_totals.append(f"應賠償[原告{plaintiff}]之損害，總計{amount:.0f}元")
        summary_format = "；".join(summary_totals)
        
        # Generate part 3 (conclusion)
        progress_text += "\n生成第三部分 (綜上所陳)...\n"
        
        yield current_state()
        
        compensation_part3 = None
        for part3_attempt in range(1, 6):
            progress_text += f"正在進行第 {part3_attempt} 次嘗試生成總結...\n"
            
            yield current_state()
            
            compensation_part3 = retrieval_system.generate_compensation_part3(compensation_part1, summary_format, plaintiffs_info_global)
            
            progress_text += f"生成的總結:\n{compensation_part3}\n\n"
            compensation_part3 = retrieval_system.clean_conclusion_part(compensation_part3)
            #progress_text += f"清理後的總結:\n{compensation_part3}\n"
            conclusion_output = compensation_part3
            
            # Extract the part after "綜上所陳" or "綜上所述"
            summary_section = ""
            if "綜上所陳" in compensation_part3:
                summary_section = compensation_part3[compensation_part3.find("綜上所陳"):]
            elif "綜上所述" in compensation_part3:
                summary_section = compensation_part3[compensation_part3.find("綜上所述"):]
            
            # Check if all amounts from compensation_sums appear in the summary section
            progress_text += "檢查總結中是否包含所有賠償金額...\n"
            check_result = retrieval_system.check_amounts_in_summary(summary_section, compensation_sums)
            progress_text += f"檢查結果: {check_result['result']}\n"
            progress_text += f"原因: {check_result['reason']}\n"
            
            yield current_state()
            
            if check_result['result'] == 'pass':
                progress_text += "檢查通過，總結中包含所有賠償金額\n"
                break
            
            if part3_attempt == 5:
                progress_text += "警告: 達到最大嘗試次數 (5)，使用最後一次生成的總結\n"
        
        # Combine all parts for final output
        final_response = f"{first_part}\n\n{law_section}\n\n{compensation_part1}\n\n{compensation_part3}"
        final_response = retrieval_system.remove_special_chars(final_response)
        
        progress_text += "\n========== 最終起訴狀 ==========\n"
        progress_text += final_response
        progress_text += "\n========== 起訴狀結束 ==========\n"
        
        yield current_state()
        
        # Close connections
        retrieval_system.close()
        
    except Exception as e:
        error_message = f"生成過程中發生錯誤: {str(e)}\n{traceback.format_exc()}"
        yield [
            error_message,  # Use error_message instead of undefined progress_text
            "",
            "",
            "",
            "",
            "",
            ""
        ]

# Add these functions before the Gradio Blocks creation, but after importing RetrievalSystem

# Create case type mapping for dropdown display
case_type_mapping = {
    range(1, 9): "單純原被告各一",
    range(9, 16): "數名原告",
    range(16, 23): "數名被告",
    range(23, 30): "原被告皆數名",
    range(30, 37): "未成年案型",
    range(37, 44): "僱用人案型",
    range(44, 51): "動物案型"
}

def get_case_type_for_dropdown(case_num):
    """Get case type description for a case number"""
    for r, case_type in case_type_mapping.items():
        if case_num in r:
            return case_type
    return "未知案型"

# Prepare dropdown options for case selection
case_dropdown_options = [f"{i}: {get_case_type_for_dropdown(i)}" for i in range(1, 51)]

def load_query_from_neo4j(dropdown_value):
    """Load user query from Neo4j based on dropdown selection"""
    if not dropdown_value:
        return ""
    
    # Extract case number from dropdown value (format: "1: 單純原被告各一")
    case_num = int(dropdown_value.split(":")[0])
    
    # Map to Neo4j query_id (0-49)
    neo4j_query_id = case_num - 1
    
    # Initialize retrieval system to use its Neo4j connection
    retrieval_system = RetrievalSystem()
    
    # Get query text from Neo4j
    with retrieval_system.neo4j_driver.session() as session:
        result = session.run("""
            MATCH (q:user_query)
            WHERE q.query_id = $query_id
            RETURN q.query_text as query_text
            """, query_id=neo4j_query_id)
        
        record = result.single()
        query_text = record["query_text"] if record else f"未找到 ID 為 {neo4j_query_id} 的查詢"
    
    # Close connections
    retrieval_system.close()
    
    return query_text

# Create the Gradio interface
with gr.Blocks(title="法律文書生成系統") as demo:
    gr.Markdown("# 車禍起訴狀生成系統")
    
    with gr.Row():
        with gr.Column(scale=2):
            # Input components - add dropdown and button for case selection
            with gr.Row():
                case_dropdown = gr.Dropdown(
                    label="選擇預設案例",
                    choices=case_dropdown_options,
                    value=None,
                    container=True
                )
                load_query_button = gr.Button("載入案例", variant="primary")
            
            user_query = gr.Textbox(
                label="請輸入案件事實 (格式需包含「一、二、三、」三個部分)",
                placeholder="一、事故經過...\n二、受傷情形...\n三、損失情況...",
                lines=10
            )
            
            k_slider = gr.Slider(
                minimum=1,
                maximum=5,
                value=5,
                step=1,
                label="Top-K 數量",
                info="選擇要檢索的相似案件數量 (1-5)"
            )
            
            model_dropdown = gr.Dropdown(
                label="選擇LLM模型",
                choices=llm_model_options,
                value=llm_model_options[0],  # Default to the first model
                container=True
            )

            search_button = gr.Button("搜索相似案件", variant="primary")
            
            case_type_output = gr.Textbox(label="案件類型", lines=1)         
            # Reference case selection - initially hidden
            reference_selector = gr.Dropdown(
                label="選擇參考案件",
                choices=[],
                value="默認（最相似案件）",
                visible=False,
                container=True,
                scale=2,  # Make it larger
                min_width=400  # Force minimum width
            )
            
            generate_button = gr.Button("生成起訴狀", variant="primary")
            
        with gr.Column(scale=3):
            # Output components
            progress_output = gr.Textbox(
                label="處理進度與詳細資訊",
                lines=50,
                autoscroll=True
            )
    
    with gr.Row():
        top_k_results = gr.Textbox(label="Top-K 搜索結果", lines=10)
        compensation_amounts = gr.Textbox(label="賠償金額資訊", lines=10)
    
    with gr.Row():
        fact_output = gr.Textbox(label="一、事實概述", lines=10)
        law_output = gr.Textbox(label="二、法條適用", lines=10)
        
    with gr.Row():
        compensation_part1_output = gr.Textbox(label="損害賠償項目", lines=10)
        conclusion_output = gr.Textbox(label="綜上所陳 (總結)", lines=10)
    
    final_output = gr.Textbox(label="完整起訴狀", lines=20, visible=True)
    
    load_query_button.click(
        fn=load_query_from_neo4j,
        inputs=[case_dropdown],
        outputs=[user_query]
    )
    # Set up event handlers
    search_button.click(
        fn=search_cases,
        inputs=[user_query, k_slider, model_dropdown],
        outputs=[progress_output, case_type_output, top_k_results, reference_selector]
    )
    
    generate_button.click(
        fn=generate_document,
        inputs=[reference_selector, model_dropdown],
        outputs=[
            progress_output,
            compensation_amounts,
            fact_output,
            law_output, 
            compensation_part1_output,
            conclusion_output,
            final_output
        ]
    )

if __name__ == "__main__":
    demo.queue()
    demo.launch(server_port=8899, server_name="0.0.0.0", share=True)