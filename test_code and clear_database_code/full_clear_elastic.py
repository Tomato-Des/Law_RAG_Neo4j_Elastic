from elasticsearch import Elasticsearch
import os
from dotenv import load_dotenv

load_dotenv()
username=os.getenv('ELASTIC_USER')
password=os.getenv('ELASTIC_PASSWORD')

def manage_elasticsearch_indices():
    es = Elasticsearch(
        "https://localhost:9200",
        http_auth=(username, password),  # 替換密碼
        verify_certs=False
    )
    try:
        # 獲取所有索引
        indices = list(es.indices.get_alias().keys())
        
        if not indices:
            print("Elasticsearch 中沒有索引")
            return
            
        # 顯示所有索引
        print("\n當前存在的索引：")
        for i, index in enumerate(indices, 1):
            print(f"{i}. {index}")
        
        # 讓用戶選擇要刪除的索引
        while True:
            choice = input("\n請輸入要刪除的索引編號（輸入 'all' 刪除所有，'q' 退出）: ").strip().lower()
            
            if choice == 'q':
                print("退出程式")
                break
                
            elif choice == 'all':
                confirm = input("確定要刪除所有索引嗎？(y/n): ").strip().lower()
                if confirm == 'y':
                    for index in indices:
                        print(f"刪除索引: {index}")
                        es.indices.delete(index=index, ignore=[400, 404])
                    print("已刪除所有索引")
                break
                
            else:
                try:
                    index_num = int(choice)
                    if 1 <= index_num <= len(indices):
                        index_to_delete = indices[index_num-1]
                        confirm = input(f"確定要刪除索引 {index_to_delete} 嗎？(y/n): ").strip().lower()
                        if confirm == 'y':
                            print(f"刪除索引: {index_to_delete}")
                            es.indices.delete(index=index_to_delete, ignore=[400, 404])
                            print(f"已刪除索引 {index_to_delete}")
                            
                            # 更新索引列表
                            indices = list(es.indices.get_alias().keys())
                            if indices:
                                print("\n剩餘的索引：")
                                for i, index in enumerate(indices, 1):
                                    print(f"{i}. {index}")
                            else:
                                print("所有索引已刪除")
                                break
                    else:
                        print("無效的編號，請重新輸入")
                except ValueError:
                    print("請輸入有效的數字")
                    
    except Exception as e:
        print(f"錯誤: {str(e)}")
    finally:
        es.close()

if __name__ == "__main__":
    manage_elasticsearch_indices()
