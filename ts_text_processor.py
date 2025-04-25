# ts_text_processor.py
import re
import requests
from typing import List, Dict
from sklearn.metrics.pairwise import cosine_similarity

class TextProcessor:
    @staticmethod
    def extract_law_numbers(law_text: str) -> List[str]:
        law_numbers = []
        for law in law_text.split(','):
            match = re.search(r'第(\d+(?:-\d+)?)\s*條', law.strip())
            if match:
                law_numbers.append(match.group(1))
        return law_numbers

    @staticmethod
    def classify_chunk(chunk: str) -> str:
        try:
            # Call Ollama with llama3.1 model
            response = requests.post('http://localhost:11434/api/generate', 
                                   json={
                                       "model": "kenneth85/llama-3-taiwan:8b-instruct-dpo",
                                       "prompt": f"""將以下文本分類成3類中的一類: 
                                        'fact' (若文本是描述事故經過或事實背景), 
                                        'injuries' (若文本描述受傷情況或醫療後果), 
                                        'compensation' (若文本涉及賠償請求、金錢損失或相關事宜).
                                        範例文本：’一、事故發生緣由: 被告丙○○於96年6月30日晚間9時20分許，騎乘牌照號碼TUF-983號輕型機車，沿彰化縣二林鎮○○路由東往西行駛，途經彰化縣二林鎮○○里○○路○○路口時，欲左轉南安路口時，本應注意車前狀況，隨時採取必要之安全措施，且應遵守車輛同為幹線道或支線道者，轉彎車應暫停讓直行車先行之交通規則，而依當時之情形，天候為晴，夜間有照明，視距良好，且柏油路面乾燥，無缺陷及障礙物，並無不能注意之情形，竟疏未注意貿然左轉，適有原告騎乘牌照號碼BLB-756號重型機車，沿斗苑路由西往東行駛，途經上開路口閃避不及，兩車因而相撞。二、原告受傷情形: 原告因本件車禍受有頭部外傷合併腦內血腫之傷害，經財團法人彰化基督教醫院緊急實施開顱清除血塊及顱內監測等手術，始暫時挽救垂危之生命，但仍留有言語不清、無法思考，記憶仍嚴重退化等後遺症，經診斷原告患有⑴外傷性蜘蛛網膜下腔出血及硬網膜下血腫⑵延遲性左側顱內出血⑶疑脾臟挫傷。三、請求賠償的事實根據: 原告因本件車禍受傷住院期間支出醫療費用47,764元，有相關醫療收據可以證明。原告於車禍前每月平均收入為31,000元，有薪資憑單及扣繳憑單可以證明。因本件車禍造成顱內重大手術，需要長期休養才能完全康復投入職場工作，請求7個月不能工作之損失共計21萬元。’
                                        例子1：‘被告丙○○於96年6月30日晚間9時20分許，騎乘牌照號碼TUF-983號輕型機車，沿彰化縣二林鎮○○路由東往西行駛，途經彰化縣二林鎮○○里○○路○○路口時，欲左轉南安路口時，本應注意車前狀況，隨時採取必要之安全措施，且應遵守車輛同為幹線道或支線道者，轉彎車應暫停讓直行車先行之交通規則，而依當時之情形，天候為晴，夜間有照明，視距良好，且柏油路面乾燥，無缺陷及障礙物，並無不能注意之情形，竟疏未注意貿然左轉，適有原告騎乘牌照號碼BLB-756號重型機車，沿斗苑路由西往東行駛，途經上開路口閃避不及，兩車因而相撞。’ 是 'fact'
                                        例子2：‘原告因本件車禍受有頭部外傷合併腦內血腫之傷害，經財團法人彰化基督教醫院緊急實施開顱清除血塊及顱內監測等手術，始暫時挽救垂危之生命，但仍留有言語不清、無法思考，記憶仍嚴重退化等後遺症，經診斷原告患有⑴外傷性蜘蛛網膜下腔出血及硬網膜下血腫⑵延遲性左側顱內出血⑶疑脾臟挫傷。’ 是 'injuries'
                                        例子3：‘原告因本件車禍受傷住院期間支出醫療費用47,764元，有相關醫療收據可以證明。原告於車禍前每月平均收入為31,000元，有薪資憑單及扣繳憑單可以證明。因本件車禍造成顱內重大手術，需要長期休養才能完全康復投入職場工作，請求7個月不能工作之損失共計21萬元。’ 是 'compensation'

                                       Text: {chunk}
                                       
                                       Respond with only one word - either 'fact', 'injuries', or 'compensation'.
                                       
                                       Category:""",
                                       "stream": False
                                   })
            
            if response.status_code == 200:
                result = response.json()['response'].strip().lower()
                if 'fact' in result:
                    return 'fact'
                elif 'injuries' in result:
                    return 'injuries'
                elif 'compensation' in result:
                    return 'compensation'
                else:
                    print(f"Unclear classification result: {result}, defaulting to 'fact'")
                    return 'fact'
            else:
                print(f"Error calling Ollama API: {response.status_code}")
                return 'fact'
                
        except Exception as e:
            print(f"Exception in classify_chunk: {str(e)}")
            return 'fact'