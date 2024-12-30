#星狀neo4j，沒有對應的use_law_node relationship，只有10條法條對10個解釋
#沒有elastic search建立

import pandas as pd
from docx import Document
from neo4j import GraphDatabase
import re
from sklearn.metrics.pairwise import cosine_similarity
from transformers import AutoTokenizer, AutoModel
import torch
import numpy as np
import os
from typing import List, Dict, Any
import requests
from dotenv import load_dotenv

class LegalRAGSystem:
    def __init__(self):
         # Load environment variables
        load_dotenv()
        
        # Neo4j connection details from environment variables
        self.uri = os.getenv('NEO4J_URI')
        self.user = os.getenv('NEO4J_USER')
        self.password = os.getenv('NEO4J_PASSWORD')
        
        if not all([self.uri, self.user, self.password]):
            raise ValueError("Missing required environment variables. Please check your .env file.")
        
        self.driver = None
        
        # Initialize the tokenizer and model for embeddings
        self.tokenizer = AutoTokenizer.from_pretrained('TencentBAC/Conan-embedding-v1')
        self.model = AutoModel.from_pretrained('TencentBAC/Conan-embedding-v1')

    def connect_to_neo4j(self):
        try:
            self.driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))
            print("Successfully connected to Neo4j")
        except Exception as e:
            print(f"Error connecting to Neo4j: {str(e)}")
            raise

    def close_neo4j_connection(self):
        if self.driver:
            self.driver.close()

    def read_docx(self, filename: str) -> str:
        try:
            doc = Document(filename)
            full_text = []
            for para in doc.paragraphs:
                full_text.append(para.text)
            return '\n'.join(full_text)
        except Exception as e:
            print(f"Error reading DOCX file {filename}: {str(e)}")
            raise

    def create_law_nodes(self, law_text: str, law_explanation: str):
        def extract_laws(text: str) -> List[Dict[str, str]]:
            laws = []
            pattern = r'第\s*(\d+(?:-\d+)?)\s*條[：:]\s*([^第]+)'
            matches = re.finditer(pattern, text)
            for match in matches:
                laws.append({
                    'number': match.group(1),
                    'content': f'第{match.group(1)}條：{match.group(2).strip()}'
                })
            return laws

        with self.driver.session() as session:
            # Extract and create law nodes
            laws = extract_laws(law_text)
            law_explanations = extract_laws(law_explanation)

            # Create law nodes and explanations
            for law in laws:
                session.run("""
                    MERGE (l:law_node {number: $number, content: $content})
                    """, number=law['number'], content=law['content'])

            for explanation in law_explanations:
                session.run("""
                    MERGE (e:law_explain_node {number: $number, explanation: $content})
                    """, number=explanation['number'], content=explanation['content'])

            # Create relationships
            for law in laws:
                session.run("""
                    MATCH (l:law_node {number: $number})
                    MATCH (e:law_explain_node {number: $number})
                    MERGE (l)-[:law_explain_relation]->(e)
                    """, number=law['number'])

    def embed_texts(self, texts: List[str]) -> np.ndarray:
        inputs = self.tokenizer(texts, padding=True, truncation=True, return_tensors='pt')
        with torch.no_grad():
            outputs = self.model(**inputs)
        return outputs.last_hidden_state[:, 0, :].numpy()

    def chunk_text(self, text: str, percentage: int = 90) -> List[str]:
        # Split into sentences
        sentences = re.split(r'[，。]', text)
        sentences = [{'sentence': x.strip(), 'index': i} for i, x in enumerate(sentences) if x.strip()]
        
        # Get embeddings
        embeddings = self.embed_texts([x['sentence'] for x in sentences])
        
        # Calculate distances
        distances = []
        for i in range(len(sentences) - 1):
            similarity = cosine_similarity([embeddings[i]], [embeddings[i + 1]])[0][0]
            distances.append(similarity)
            sentences[i]['distance_to_next'] = similarity

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
        try:
            # Call Ollama with llama3.1 model
            response = requests.post('http://localhost:11434/api/generate', 
                                   json={
                                       "model": "llama3.1:latest",
                                       "prompt": f"""將以下文本分類成3類中的一類: 
                                        'fact' (若文本是對案件的描述或解釋), 
                                        'law' (法條使用), 
                                        'compensation' (所有賠償及金錢相關事宜).
                                        範例文本：’ 一、緣被告甲○○於民國93年8月2日上午11時8分許，駕駛車號P8-6386自用小貨車，行經臺北縣板橋市○○路○段36之1號前時，因未保持安全車距及違規超車，從後方撞及原告丙○○所騎乘之重型機車右側車身，致原告人車倒地，導致原告右腳大姆趾粉碎性骨折斷碎截肢之傷害。 二、按「因故意或過失，不法侵害他人之權利者，負損害賠償責任。」民法第184條第1項前段定有明文。又「汽車、機車或其他非依軌道行駛之動力車輛，在使用中加損害於他人者，駕駛人應賠償因此所生之損害。但於防止損害之發生，已盡相當之注意者，不在此限。」民法第191條之2亦有明文規定。復按「不法侵害他人之身體、健康、名譽、自由、信用、隱私、貞操，或不法侵害其他人格法益而情節重大者，被害人雖非財產上之損害，亦得請求賠償相當之金額。」民法第195條第1項前段亦有明文。查被告因上開侵權行為，致原告受有下列損害，依前揭規定，被告應負損害賠償責任： （一）醫療費用：83,947元 原告因本次事故受有右足壓碎傷合併大腳趾撕脫傷、近端趾骨粉碎性骨折、右足背撕脫傷及血腫之傷害，為治療上開傷勢而就醫，支出醫療費用（自付額）83,947元。 （二）旅費損失：32,000元 原告原定於事發當日（93年8月2日）下午3時出發前往大陸蘇杭旅遊，因受重傷無法成行，損失已預繳之旅費32,000元。 （三）精神慰撫金：200,000元 原告因本次車禍造成右腳大姆趾粉碎性骨折斷碎截肢，造成往後無法正常行走且上下樓梯右腳無法施力行動遲緩。侵權行為造成原告四肢無法健全，足趾殘缺，自尊心受創身心痛苦萬分，爰依民法第195條請求被告支付精神慰撫金200,000元。 （四）綜上所陳，被告應賠償原告之損害，包含醫療費用83,947元、旅費損失32,000元及精神慰撫金200,000元，總計315,947元。惟原告已自被告所駕駛之車輛汽車強制責任險領取保險金47,609元，是以，原告請求被告賠償之金額應為268,338元。’
		                                 例子1：‘一、緣被告甲○○於民國93年8月2日上午11時8分許，駕駛車號P8-6386自用小貨車，行經臺北縣板橋市○○路○段36之1號前時，因未保持安全車距及違規超車，從後方撞及原告丙○○所騎乘之重型機車右側車身，致原告人車倒地，導致原告右腳大姆趾粉碎性骨折斷碎截肢之傷害。’ 是 'fact'
		                                 例子2：‘二、按「因故意或過失，不法侵害他人之權利者，負損害賠償責任。」民法第184條第1項前段定有明文。又「汽車、機車或其他非依軌道行駛之動力車輛，在使用中加損害於他人者，駕駛人應賠償因此所生之損害。但於防止損害之發生，已盡相當之注意者，不在此限。」民法第191條之2亦有明文規定。復按「不法侵害他人之身體、健康、名譽、自由、信用、隱私、貞操，或不法侵害其他人格法益而情節重大者，被害人雖非財產上之損害，亦得請求賠償相當之金額。」民法第195條第1項前段亦有明文。查被告因上開侵權行為，致原告受有下列損害，依前揭規定，被告應負損害賠償責任：’ 是 ’law’
			                             例子3：’ （一）醫療費用：83,947元 原告因本次事故受有右足壓碎傷合併大腳趾撕脫傷、近端趾骨粉碎性骨折、右足背撕脫傷及血腫之傷害，為治療上開傷勢而就醫，支出醫療費用（自付額）83,947元。 （二）旅費損失：32,000元 原告原定於事發當日（93年8月2日）下午3時出發前往大陸蘇杭旅遊，因受重傷無法成行，損失已預繳之旅費32,000元。 （三）精神慰撫金：200,000元 原告因本次車禍造成右腳大姆趾粉碎性骨折斷碎截肢，造成往後無法正常行走且上下樓梯右腳無法施力行動遲緩。侵權行為造成原告四肢無法健全，足趾殘缺，自尊心受創身心痛苦萬分，爰依民法第195條請求被告支付精神慰撫金200,000元。 （四）綜上所陳，被告應賠償原告之損害，包含醫療費用83,947元、旅費損失32,000元及精神慰撫金200,000元，總計315,947元。惟原告已自被告所駕駛之車輛汽車強制責任險領取保險金47,609元，是以，原告請求被告賠償之金額應為268,338元。’ 是 ‘compensation’

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

    def process_case_data(self, case_text: str, case_id: int):
        chunks = self.chunk_text(case_text)
        
        with self.driver.session() as session:
            # Create case node
            session.run("""
                MERGE (c:case_node {case_id: $case_id, case_text: $case_text})
                """, case_id=case_id, case_text=case_text)

            # Process chunks
            for chunk in chunks:
                chunk_type = self.classify_chunk(chunk)
                
                if chunk_type == 'fact':
                    session.run("""
                        MERGE (f:fact_text {case_id: $case_id, chunk: $chunk})
                        WITH f
                        MATCH (c:case_node {case_id: $case_id})
                        MERGE (c)-[:fact_text_relation]->(f)
                        """, case_id=case_id, chunk=chunk)

                elif chunk_type == 'law':
                    session.run("""
                        MERGE (l:law_text {case_id: $case_id, chunk: $chunk})
                        WITH l
                        MATCH (c:case_node {case_id: $case_id})
                        MERGE (c)-[:law_text_relation]->(l)
                        """, case_id=case_id, chunk=chunk)

                elif chunk_type == 'compensation':
                    session.run("""
                        MERGE (comp:compensation_text {case_id: $case_id, chunk: $chunk})
                        WITH comp
                        MATCH (c:case_node {case_id: $case_id})
                        MERGE (c)-[:compensation_text_relation]->(comp)
                        """, case_id=case_id, chunk=chunk)

    def process_used_laws(self, case_id: int, used_laws: str):
        with self.driver.session() as session:
            # Create used_law_node
            session.run("""
                MERGE (u:used_law_node {case_id: $case_id, used_laws: $used_laws})
                WITH u
                MATCH (c:case_node {case_id: $case_id})
                MERGE (c)-[:used_law_node_relation]->(u)
                """, case_id=case_id, used_laws=used_laws)

            # Update used_law property in other nodes
            session.run("""
                MATCH (n)
                WHERE n.case_id = $case_id AND 
                      (n:fact_text OR n:law_text OR n:compensation_text)
                SET n.used_law = $used_laws
                """, case_id=case_id, used_laws=used_laws)
                
    def check_ollama_service(self):
        """Check if Ollama service is running"""
        try:
            response = requests.get('http://localhost:11434/api/version')
            return response.status_code == 200
        except:
            return False

    def main(self):
        try:
            self.connect_to_neo4j()

            # Validate Ollama service
            if not self.check_ollama_service():
                raise RuntimeError("Ollama service is not running")

            # Read law documents //DOCX
            print("Enter filename for law text (DOCX):")
            law_file = input().strip()
            law_text = self.read_docx(law_file)

            print("Enter filename for law explanations (DOCX):")
            explanation_file = input().strip()
            law_explanation = self.read_docx(explanation_file)

            # Create law nodes and relationships
            self.create_law_nodes(law_text, law_explanation)

            # Process case data
            print("Enter filename for case data (XLSX):")
            case_file = input().strip()
            xl = pd.ExcelFile(case_file)
            print("Available sheets:", xl.sheet_names)
            
            sheet_name = input("Enter sheet name: ").strip()
            df = pd.read_excel(case_file, sheet_name=sheet_name)
            print("Available columns:", df.columns.tolist())
            
            column = input("Enter column name: ").strip()
            print(f"Available rows: 0 to {len(df)-1}")
            
            start_row = int(input("Enter start row: ").strip())
            end_row = int(input("Enter end row: ").strip())

            # Process each case
            for new_idx, (original_idx, row) in enumerate(df[column][start_row:end_row+1].items()):
                self.process_case_data(row, new_idx)  # use new_idx if you want 0-based
                # original_idx is also available if needed

            # Process used laws
            print("Enter filename for used laws (XLSX):")
            laws_file = input().strip()
            xl = pd.ExcelFile(laws_file)
            print("Available sheets:", xl.sheet_names)
            
            sheet_name = input("Enter sheet name: ").strip()
            laws_df = pd.read_excel(laws_file, sheet_name=sheet_name)
            print("Available columns:", laws_df.columns.tolist())
            
            column = input("Enter column name: ").strip()
            print(f"Available rows: 0 to {len(laws_df)-1}")
            
            start_row = int(input("Enter start row: ").strip())
            end_row = int(input("Enter end row: ").strip())

            # Process each law reference
            for new_idx, (original_idx, row) in enumerate(laws_df[column][start_row:end_row+1].items()):
                self.process_used_laws(new_idx, row)

        except Exception as e:
            print(f"An error occurred: {str(e)}")
        finally:
            self.close_neo4j_connection()

if __name__ == "__main__":
    #Load enviroment variables from .env file
    load_dotenv()
    rag_system = LegalRAGSystem()
    rag_system.main()