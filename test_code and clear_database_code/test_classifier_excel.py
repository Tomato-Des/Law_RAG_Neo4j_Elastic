import re
import torch
import numpy as np
import requests
import pandas as pd
from typing import List
from transformers import AutoTokenizer, AutoModel
from sklearn.metrics.pairwise import cosine_similarity

class TextChunkClassifier:
    def __init__(self):
        # Initialize the tokenizer and model for embeddings
        self.tokenizer = AutoTokenizer.from_pretrained('TencentBAC/Conan-embedding-v1')
        self.model = AutoModel.from_pretrained('TencentBAC/Conan-embedding-v1')

    def embed_texts(self, texts: List[str]) -> np.ndarray:
        inputs = self.tokenizer(texts, padding=True, truncation=True, return_tensors='pt')
        with torch.no_grad():
            outputs = self.model(**inputs)
        return outputs.last_hidden_state[:, 0, :].numpy()

    def chunk_text(self, text: str, percentage: int = 80) -> List[str]:
        # Split into sentences
        sentences = re.split(r'[，。]', text)
        sentences = [{'sentence': x.strip(), 'index': i} for i, x in enumerate(sentences) if x.strip()]
        
        if not sentences:  # Return empty list if no valid sentences
            return []
            
        # Get embeddings
        embeddings = self.embed_texts([x['sentence'] for x in sentences])
        
        # Calculate distances
        distances = []
        for i in range(len(sentences) - 1):
            similarity = cosine_similarity([embeddings[i]], [embeddings[i + 1]])[0][0]
            distances.append(similarity)
            sentences[i]['distance_to_next'] = similarity

        # If only one sentence, return it as a single chunk
        if not distances:
            return [sentences[0]['sentence'] + '。']

        # Calculate threshold
        sorted_distances = sorted(distances)
        cutoff_index = int(len(sorted_distances) * (100 - percentage) / 100)
        threshold = sorted_distances[cutoff_index]
        
        # Find breakpoints
        indices_above_thresh = [i for i, x in enumerate(distances) if x < threshold]
        
        # Create chunks
        chunks = []
        start_index = 0
        for index in indices_above_thresh:
            group = sentences[start_index:index + 1]
            combined_text = '。'.join([d['sentence'] for d in group]) + '。'
            chunks.append(combined_text)
            start_index = index + 1
            
        if start_index < len(sentences):
            combined_text = '。'.join([d['sentence'] for d in sentences[start_index:]]) + '。'
            chunks.append(combined_text)
            
        return chunks

    def classify_chunk(self, chunk: str) -> str:
        response = requests.post('http://localhost:11434/api/generate', 
                               json={
                                   "model": "llama3.1:latest",
                                   "prompt": f"""將以下文本分類成3類中的一類: 
                                   'fact' (若文本是對案件的描述或解釋), 
                                   'law' (法條使用), 
                                   'compensation' (所有賠償及金錢相關事宜).
                                   範例文本：' 一、緣被告甲○○於民國93年8月2日上午11時8分許，駕駛車號P8-6386自用小貨車，行經臺北縣板橋市○○路○段36之1號前時，因未保持安全車距及違規超車，從後方撞及原告丙○○所騎乘之重型機車右側車身，致原告人車倒地，導致原告右腳大姆趾粉碎性骨折斷碎截肢之傷害。 二、按「因故意或過失，不法侵害他人之權利者，負損害賠償責任。」民法第184條第1項前段定有明文。又「汽車、機車或其他非依軌道行駛之動力車輛，在使用中加損害於他人者，駕駛人應賠償因此所生之損害。但於防止損害之發生，已盡相當之注意者，不在此限。」民法第191條之2亦有明文規定。復按「不法侵害他人之身體、健康、名譽、自由、信用、隱私、貞操，或不法侵害其他人格法益而情節重大者，被害人雖非財產上之損害，亦得請求賠償相當之金額。」民法第195條第1項前段亦有明文。查被告因上開侵權行為，致原告受有下列損害，依前揭規定，被告應負損害賠償責任：'
		                            例子1：'一、緣被告甲○○於民國93年8月2日上午11時8分許，駕駛車號P8-6386自用小貨車，行經臺北縣板橋市○○路○段36之1號前時，因未保持安全車距及違規超車，從後方撞及原告丙○○所騎乘之重型機車右側車身，致原告人車倒地，導致原告右腳大姆趾粉碎性骨折斷碎截肢之傷害。' 是 'fact'
		                            例子2：'二、按「因故意或過失，不法侵害他人之權利者，負損害賠償責任。」民法第184條第1項前段定有明文。又「汽車、機車或其他非依軌道行駛之動力車輛，在使用中加損害於他人者，駕駛人應賠償因此所生之損害。但於防止損害之發生，已盡相當之注意者，不在此限。」民法第191條之2亦有明文規定。' 是 'law'
			                        例子3：' （一）醫療費用：83,947元 原告因本次事故受有右足壓碎傷合併大腳趾撕脫傷、近端趾骨粉碎性骨折、右足背撕脫傷及血腫之傷害，為治療上開傷勢而就醫，支出醫療費用（自付額）83,947元。' 是 'compensation'
                                   Text: {chunk}
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
                return 'fact'  # Default to fact if unclear
        else:
            print(f"Error calling Llama model: {response.status_code}")
            return 'fact'  # Default to fact if error

def process_excel_data(classifier: TextChunkClassifier):
    try:
        # Get Excel filename
        excel_file = input("Please enter the Excel filename (including .xlsx extension): ")
        
        # Read Excel file
        excel = pd.ExcelFile(excel_file)
        
        # Print available sheets
        print("\nAvailable sheets:")
        for sheet in excel.sheet_names:
            print(f"- {sheet}")
        
        # Get sheet name
        sheet_name = input("\nEnter the sheet name to process: ")
        
        # Read the specified sheet
        df = pd.read_excel(excel_file, sheet_name=sheet_name)
        
        # Print available columns
        print("\nAvailable columns:")
        for col in df.columns:
            print(f"- {col}")
        
        # Get column name
        column_name = input("\nEnter the column name containing the text to process: ")
        
        # Print available row range
        print(f"\nAvailable rows: 0 to {len(df) - 1}")
        
        # Get row range
        start_row = int(input("Enter start row number: "))
        end_row = int(input("Enter end row number: "))
        
        # Process each row in the range
        for idx in range(start_row, end_row + 1):
            text = str(df.iloc[idx][column_name])
            print(f"\nProcessing row {idx}:")
            print("-" * 50)
            print(f"Original text: {text}")
            print("-" * 50)
            
            # Get chunks
            chunks = classifier.chunk_text(text)
            
            # Classify each chunk and print results
            print("Results:")
            for i, chunk in enumerate(chunks):
                chunk_type = classifier.classify_chunk(chunk)
                print(f"\nChunk {i + 1}:")
                print(f"Text: {chunk}")
                print(f"Classification: {chunk_type}")
            print("-" * 50)
            
    except FileNotFoundError:
        print(f"Error: File '{excel_file}' not found")
    except KeyError:
        print(f"Error: Sheet or column not found")
    except ValueError as e:
        print(f"Error: Invalid input - {str(e)}")
    except Exception as e:
        print(f"An unexpected error occurred: {str(e)}")

def main():
    classifier = TextChunkClassifier()
    process_excel_data(classifier)

if __name__ == "__main__":
    main()