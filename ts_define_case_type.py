#ts_define_case_type.py
import re
from ts_input_filter import generate_filter
def get_case_type(sim_input: str, cinfo = 0) -> str:
    """
    根據模擬輸入文本 sim_input 判斷案件的類型。
    會依據原被告的人數，以及是否涉及未成年人、僱用人責任或動物責任等因素來組合案型說明。

    Args:
        sim_input (str): 用戶輸入的案件描述文字。

    Returns:
        tuple: (案件的類型描述, 原告資訊)
    """
    case_info, plaintiffs_info = generate_filter(sim_input)
    print(f"CASE INFO: {case_info}\n")
    # 分割姓名列表
    # 正則表達式提取原告和被告姓名
    pattern = r"原告:([\u4e00-\u9fa5A-Za-z0-9○·．,、]+)"
    plaintiff_match = re.search(pattern, case_info)
    pattern = r"被告:([\u4e00-\u9fa5A-Za-z0-9○·．,、]+)"
    defendant_match = re.search(pattern, case_info)

    plaintiffs = re.split(r"[,、]", plaintiff_match.group(1)) if plaintiff_match else []
    defendants = re.split(r"[,、]", defendant_match.group(1)) if defendant_match else []

    # 去除空格
    plaintiffs = [name.strip() for name in plaintiffs]
    defendants = [name.strip() for name in defendants]

    #print("原告:", plaintiffs)
    #print("被告:", defendants)

    case_type=""
    p=len(plaintiffs)
    d=len(defendants)
    # 根據人數分類基本案型
    if p<=1 and d<=1:
        case_type="單純原被告各一"
    elif p>1 and d<=1:
        case_type="數名原告"
    elif p<=1 and d>1:
        case_type="數名被告"
    elif p>1 and d>1:
        case_type="原被告皆數名"

    match = re.search(r'被告是否為未成年人(.*?)被告是否為受僱人(.*?)車禍是否由動物造成(.*)', case_info, re.S)

    if match.group(1).strip()[1] =="是":
        case_type += "+§187未成年案型"
        if cinfo == 1:
            return case_type, plaintiffs_info, case_info
        return case_type, plaintiffs_info
    if match.group(2).strip()[1] =="是":
        case_type += "+§188僱用人案型"
        if cinfo == 1:
            return case_type, plaintiffs_info, case_info
        return case_type, plaintiffs_info
    if match.group(3).strip()[1] =="是":
        case_type += "+§190動物案型"
        if cinfo == 1:
            return case_type, plaintiffs_info, case_info
        return case_type, plaintiffs_info
    
    if cinfo == 1:
            return case_type, plaintiffs_info, case_info
    return case_type, plaintiffs_info