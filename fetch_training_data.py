#!/usr/bin/env python3
"""
Fetch and process training data from BDStall API with chunking
"""
import requests
import json
import logging
import csv
from time import sleep

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def fetch_training_data_chunked():
    """Fetch the dataset in chunks due to API limits"""
    print("Fetching BDStall dataset in chunks...")
    print("=" * 60)
    
    all_items = []
    limits = [1000, 500, 200]  # Try different sizes
    
    for limit in limits:
        try:
            url = f'https://ai.bdstall.com/rest_api/item/chatbot_grouped?limit={limit}'
            
            print(f"\n📤 Fetching {limit} items...")
            response = requests.get(url, timeout=60)
            
            if response.status_code == 200:
                data = response.json()
                
                # Extract items based on response format
                if isinstance(data, dict) and 'data' in data:
                    items = data['data']
                elif isinstance(data, list):
                    items = data
                else:
                    items = []
                
                print(f"✅ Got {len(items)} items")
                all_items.extend(items)
                
                # Show first sample
                if items and len(all_items) == len(items):
                    print(f"\n📋 Sample item structure:")
                    sample = items[0]
                    if isinstance(sample, dict):
                        print(f"Fields: {list(sample.keys())}")
                
                sleep(2)  # Be respectful to API
                
            else:
                print(f"⚠️ Status {response.status_code}, trying smaller limit...")
                
        except requests.exceptions.Timeout:
            print(f"⏱️ Timeout with limit {limit}, trying smaller...")
        except Exception as e:
            print(f"❌ Error: {e}")
    
    return all_items

def process_training_data(items):
    """Convert items to Q&A training pairs"""
    print(f"\n🔄 Processing {len(items)} items...")
    print("=" * 60)
    
    qa_pairs = []
    categories = {}
    
    for idx, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        
        title = item.get('title', item.get('name', ''))
        desc = item.get('description', item.get('desc', ''))
        price = item.get('price', item.get('selling_price', 'Check website'))
        category = item.get('category', 'General')
        
        if not title:
            continue
        
        categories[category] = categories.get(category, 0) + 1
        
        # Create Q&A pairs
        qa_pairs.append({
            'question': f'{title}',
            'answer': f'{title} - Price: {price}' if desc else f'{title}',
            'category': category,
            'source': 'bdstall_api'
        })
        
        if (idx + 1) % 500 == 0:
            print(f"✓ Processed {idx + 1} items...")
    
    print(f"\n✅ Created {len(qa_pairs)} Q&A pairs")
    print(f"Top categories: {dict(sorted(categories.items(), key=lambda x: x[1], reverse=True)[:5])}")
    
    return qa_pairs

def save_training_data(qa_pairs):
    """Save processed training data"""
    print(f"\n💾 Saving {len(qa_pairs)} training pairs...")
    
    # Save JSON
    json_file = 'processed_training_data.json'
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(qa_pairs, f, ensure_ascii=False, indent=2)
    print(f"✅ Saved to {json_file}")
    
    # Save CSV
    csv_file = 'processed_training_data.csv'
    with open(csv_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['Question', 'Answer', 'Category', 'Source'])
        for pair in qa_pairs:
            writer.writerow([
                pair['question'],
                pair['answer'],
                pair['category'],
                pair['source']
            ])
    print(f"✅ Also saved as {csv_file}")
    
    return json_file

if __name__ == "__main__":
    items = fetch_training_data_chunked()
    if items:
        qa_pairs = process_training_data(items)
        if qa_pairs:
            save_training_data(qa_pairs)
            print(f"\n🎉 Training data ready with {len(qa_pairs)} pairs!")
    else:
        print("\n❌ No data fetched")