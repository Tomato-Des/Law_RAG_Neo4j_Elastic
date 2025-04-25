# ts_prompt_check.py
# This file contains all quality check prompts used in the retrieval system

# Fact quality check prompt
def get_fact_quality_check_prompt(generated_fact, summary):
    return f"""請評估生成的事故事實段落是否與摘要一致，並檢查是否遺漏重要資訊。

    摘要：
    {summary}

    生成的事故事實段落：
    {generated_fact}

    評估標準：
    1. 輸入跟摘要內容是否一致，如事故緣由，受傷情形等資訊
    2. 是否遺漏任何重要資訊
    3. 是否符合法律文書的格式和語言要求
    4. 是否包含摘要中的所有關鍵要素
    5. 不可包含赔偿金

    請僅回答 "pass" 或 "fail"，並提供簡短的理由。格式：
    [結果]: [pass/fail]
    [理由]: [簡短說明為何通過或失敗]
    """

# Compensation format check prompt
def get_compensation_format_check_prompt(final_compensation):
    return f"""請評估賠償請求段落是否符合標準法律文書格式。

賠償請求段落:
{final_compensation}

評估標準:
1. 使用（一）、（二）或者1.，2.等標記區分不同賠償項目
2. 每個項目有明確的金額和原因說明
3. 如有多位原告，每位原告的賠償項目分別列出
4. 金額格式統一且清晰（使用阿拉伯數字）
5. 在綜上所陳部分以前并無總和或總計
6. 綜上所陳部分是否有將"賠償請求段落"列出的所有賠償項目包含在内(此項以嚴格標準評估！所有項目都必須包含在内！)

請僅回答 "pass" 或 "fail"，並提供簡短的理由。
"""

# Add this to ts_prompt_check.py
def get_calculation_tags_check_prompt(compensation_part1, compensation_part2):
    return f"""請評估生成的計算標籤是否完整涵蓋所有賠償項目。

評估標準:
1. 是否為每位原告生成一個計算標籤
2. 標籤中的金額是否與賠償項目中的金額一致
3. 計算標籤格式是否正確 (<calculate>原告名稱/代稱 金額1 金額2 金額3</calculate>)，代稱可以是"default"
4. 標籤內是否只包含數字，不包含文字描述、加號、等號、逗號或其他分隔符
5. 一位原告只能有一個標簽，多個原告則多個標簽

賠償項目:
{compensation_part1}

生成的計算標籤:
{compensation_part2}


請僅回答 "pass" 或 "fail"，並提供簡短的理由。格式：
[結果]: [pass/fail]
[理由]: [簡短說明為何通過或失敗]
"""