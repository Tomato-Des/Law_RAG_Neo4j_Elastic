# text_processor_temp.py
import re
import requests
from typing import List

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
            # Using the new model but keeping the same prompt structure
            response = requests.post('http://localhost:11434/api/generate', 
                                   json={
                                       "model": "kenneth85/llama-3-taiwan:8b-instruct-dpo-q6_K",
                                       "prompt": f"""將以下文本分類成3類中的一類: 
                                        'fact' (若文本是對案件的描述或解釋), 
                                        'law' (法條使用), 
                                        'compensation' (所有賠償及金錢相關事宜).
                                        範例文本：' 一、緣被告甲○○於民國93年8月2日上午11時8分許，駕駛車號P8-6386自用小貨車，行經臺北縣板橋市○○路○段36之1號前時，因未保持安全車距及違規超車，從後方撞及原告丙○○所騎乘之重型機車右側車身，致原告人車倒地，導致原告右腳大姆趾粉碎性骨折斷碎截肢之傷害。 二、按「因故意或過失，不法侵害他人之權利者，負損害賠償責任。」民法第184條第1項前段定有明文。又「汽車、機車或其他非依軌道行駛之動力車輛，在使用中加損害於他人者，駕駛人應賠償因此所生之損害。但於防止損害之發生，已盡相當之注意者，不在此限。」民法第191條之2亦有明文規定。復按「不法侵害他人之身體、健康、名譽、自由、信用、隱私、貞操，或不法侵害其他人格法益而情節重大者，被害人雖非財產上之損害，亦得請求賠償相當之金額。」民法第195條第1項前段亦有明文。查被告因上開侵權行為，致原告受有下列損害，依前揭規定，被告應負損害賠償責任： （一）醫療費用：83,947元 原告因本次事故受有右足壓碎傷合併大腳趾撕脫傷、近端趾骨粉碎性骨折、右足背撕脫傷及血腫之傷害，為治療上開傷勢而就醫，支出醫療費用（自付額）83,947元。 （二）旅費損失：32,000元 原告原定於事發當日（93年8月2日）下午3時出發前往大陸蘇杭旅遊，因受重傷無法成行，損失已預繳之旅費32,000元。 （三）精神慰撫金：200,000元 原告因本次車禍造成右腳大姆趾粉碎性骨折斷碎截肢，造成往後無法正常行走且上下樓梯右腳無法施力行動遲緩。侵權行為造成原告四肢無法健全，足趾殘缺，自尊心受創身心痛苦萬分，爰依民法第195條請求被告支付精神慰撫金200,000元。 （四）綜上所陳，被告應賠償原告之損害，包含醫療費用83,947元、旅費損失32,000元及精神慰撫金200,000元，總計315,947元。惟原告已自被告所駕駛之車輛汽車強制責任險領取保險金47,609元，是以，原告請求被告賠償之金額應為268,338元。'
		                                 例子1：'一、緣被告甲○○於民國93年8月2日上午11時8分許，駕駛車號P8-6386自用小貨車，行經臺北縣板橋市○○路○段36之1號前時，因未保持安全車距及違規超車，從後方撞及原告丙○○所騎乘之重型機車右側車身，致原告人車倒地，導致原告右腳大姆趾粉碎性骨折斷碎截肢之傷害。' 是 'fact'
		                                 例子2：'二、按「因故意或過失，不法侵害他人之權利者，負損害賠償責任。」民法第184條第1項前段定有明文。又「汽車、機車或其他非依軌道行駛之動力車輛，在使用中加損害於他人者，駕駛人應賠償因此所生之損害。但於防止損害之發生，已盡相當之注意者，不在此限。」民法第191條之2亦有明文規定。復按「不法侵害他人之身體、健康、名譽、自由、信用、隱私、貞操，或不法侵害其他人格法益而情節重大者，被害人雖非財產上之損害，亦得請求賠償相當之金額。」民法第195條第1項前段亦有明文。查被告因上開侵權行為，致原告受有下列損害，依前揭規定，被告應負損害賠償責任：' 是 'law'
			                             例子3：' （一）醫療費用：83,947元 原告因本次事故受有右足壓碎傷合併大腳趾撕脫傷、近端趾骨粉碎性骨折、右足背撕脫傷及血腫之傷害，為治療上開傷勢而就醫，支出醫療費用（自付額）83,947元。 （二）旅費損失：32,000元 原告原定於事發當日（93年8月2日）下午3時出發前往大陸蘇杭旅遊，因受重傷無法成行，損失已預繳之旅費32,000元。 （三）精神慰撫金：200,000元 原告因本次車禍造成右腳大姆趾粉碎性骨折斷碎截肢，造成往後無法正常行走且上下樓梯右腳無法施力行動遲緩。侵權行為造成原告四肢無法健全，足趾殘缺，自尊心受創身心痛苦萬分，爰依民法第195條請求被告支付精神慰撫金200,000元。 （四）綜上所陳，被告應賠償原告之損害，包含醫療費用83,947元、旅費損失32,000元及精神慰撫金200,000元，總計315,947元。惟原告已自被告所駕駛之車輛汽車強制責任險領取保險金47,609元，是以，原告請求被告賠償之金額應為268,338元。' 是 'compensation'

                                       Text: {chunk}
                                       
                                       Respond with only one word - either 'fact', 'law', or 'compensation'.
                                       
                                       Category:""",
                                       "stream": False
                                   })
            
            if response.status_code == 200:
                result = response.json()['response'].strip().lower()
                if 'fact' in result:
                    return 'fact'
                elif 'law' in result:
                    return 'law'
                elif 'compensation' in result:
                    return 'compensation'
                else:
                    print(f"Unclear classification result: {result}, defaulting to 'fact'")
                    return 'fact'  # Default to fact if unclear
            else:
                print(f"Error calling Ollama API: {response.status_code}")
                return 'fact'  # Default to fact if error
                
        except Exception as e:
            print(f"Exception in classify_chunk: {str(e)}")
            return 'fact'  # Default to fact if exception occurs