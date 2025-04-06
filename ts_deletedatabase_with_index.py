#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import time
from dotenv import load_dotenv
from elasticsearch import Elasticsearch
from neo4j import GraphDatabase
import traceback

def main():
    """
    Main function to delete cases from Elasticsearch or Neo4j
    based on case_id threshold
    """
    start_time = time.time()
    es = None
    neo4j_driver = None
    
    try:
        print("=== 資料庫清理工具 ===")
        
        # Load environment variables
        load_dotenv()
        
        # Initialize connections
        try:
            # Setup Elasticsearch connection
            es = Elasticsearch(
                "https://localhost:9200",
                http_auth=(os.getenv('ELASTIC_USER'), os.getenv('ELASTIC_PASSWORD')),
                verify_certs=False
            )
            
            # Test Elasticsearch connection
            es.ping()
            
            # Setup Neo4j connection
            neo4j_driver = GraphDatabase.driver(
                os.getenv('NEO4J_URI'),
                auth=(os.getenv('NEO4J_USER'), os.getenv('NEO4J_PASSWORD'))
            )
            
            # Test Neo4j connection
            with neo4j_driver.session() as session:
                session.run("RETURN 1")
                
            print("成功連接到 Elasticsearch 和 Neo4j 資料庫")
        except Exception as e:
            print(f"錯誤: 無法連接到資料庫: {str(e)}")
            return
        
        # Choose database
        print("\n請選擇要清理的資料庫:")
        print("1: Elasticsearch")
        print("2: Neo4j")
        
        db_choice = input("\n輸入選項 (1 或 2): ").strip()
        
        if db_choice not in ['1', '2']:
            print("錯誤: 無效選項")
            return
        
        # Get max case_id in the selected database
        max_case_id = -1
        
        if db_choice == '1':
            # Get max case_id from Elasticsearch
            try:
                max_query = {
                    "aggs": {
                        "max_case_id": {
                            "max": {
                                "field": "case_id"
                            }
                        }
                    },
                    "size": 0
                }
                
                max_result = es.search(index="ts_text_embeddings", body=max_query)
                max_case_id = int(max_result['aggregations']['max_case_id']['value'])
                print(f"\nElasticsearch 中的最大 case_id: {max_case_id}")
            except Exception as e:
                print(f"無法獲取 Elasticsearch 中的最大 case_id: {str(e)}")
        else:
            # Get max case_id from Neo4j
            try:
                with neo4j_driver.session() as session:
                    result = session.run("""
                        MATCH (n)
                        WHERE exists(n.case_id)
                        RETURN coalesce(max(n.case_id), -1) as max_id
                        """)
                    max_case_id = result.single()["max_id"]
                    print(f"\nNeo4j 中的最大 case_id: {max_case_id}")
            except Exception as e:
                print(f"無法獲取 Neo4j 中的最大 case_id: {str(e)}")
        
        # Get case_id threshold
        try:
            case_id_threshold = int(input("\n請輸入要刪除的起始 case_id (將刪除大於或等於此 ID 的所有案例): ").strip())
            if case_id_threshold < 0:
                print("錯誤: case_id 必須是非負數")
                return
        except ValueError:
            print("錯誤: 請輸入有效的數字")
            return
        
        # Confirm deletion
        if db_choice == '1':
            # Get count from Elasticsearch
            count_query = {
                "query": {
                    "range": {
                        "case_id": {
                            "gte": case_id_threshold
                        }
                    }
                }
            }
            count_result = es.count(index="ts_text_embeddings", body=count_query)
            count = count_result.get('count', 0)
            
            print(f"\n將從 Elasticsearch 刪除 {count} 筆文檔 (case_id >= {case_id_threshold})")
        else:
            # Get count from Neo4j
            with neo4j_driver.session() as session:
                count_result = session.run("""
                    MATCH (n)
                    WHERE n.case_id >= $threshold
                    RETURN count(n) as count
                    """, threshold=case_id_threshold)
                count = count_result.single()["count"]
                
                print(f"\n將從 Neo4j 刪除 {count} 個節點 (case_id >= {case_id_threshold})")
        
        confirmation = input("\n確定要進行刪除操作? (yes/no): ").strip().lower()
        
        if confirmation != 'yes':
            print("操作已取消")
            return
        
        # Perform deletion
        if db_choice == '1':
            # Delete from Elasticsearch
            delete_query = {
                "query": {
                    "range": {
                        "case_id": {
                            "gte": case_id_threshold
                        }
                    }
                }
            }
            
            print("\n正在從 Elasticsearch 刪除數據...")
            response = es.delete_by_query(
                index="ts_text_embeddings",
                body=delete_query,
                refresh=True
            )
            
            deleted = response.get('deleted', 0)
            print(f"成功從 Elasticsearch 刪除 {deleted} 筆文檔")
            
        else:
            # Delete from Neo4j
            with neo4j_driver.session() as session:
                print("\n正在從 Neo4j 刪除數據...")
                
                # Delete relationships first
                rel_result = session.run("""
                    MATCH (n)-[r]-(m)
                    WHERE n.case_id >= $threshold OR m.case_id >= $threshold
                    DELETE r
                    RETURN count(r) as deleted_relationships
                    """, threshold=case_id_threshold)
                
                deleted_relationships = rel_result.single()["deleted_relationships"]
                
                # Then delete nodes
                node_result = session.run("""
                    MATCH (n)
                    WHERE n.case_id >= $threshold
                    DELETE n
                    RETURN count(n) as deleted_nodes
                    """, threshold=case_id_threshold)
                
                deleted_nodes = node_result.single()["deleted_nodes"]
                
                print(f"成功從 Neo4j 刪除 {deleted_relationships} 個關係和 {deleted_nodes} 個節點")
        
    except Exception as e:
        print(f"\n執行過程中發生錯誤: {str(e)}")
        traceback.print_exc()
    
    finally:
        # Close connections
        if neo4j_driver:
            neo4j_driver.close()
        
        end_time = time.time()
        elapsed_time = end_time - start_time
        
        minutes = int(elapsed_time // 60)
        seconds = int(elapsed_time % 60)
        
        print(f"\n總執行時間: {minutes}m {seconds}s")

if __name__ == "__main__":
    main()