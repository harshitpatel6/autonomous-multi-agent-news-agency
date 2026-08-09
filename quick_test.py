#!/usr/bin/env python3
"""
Quick test: Summarize just 10 clusters to verify pipeline works.
"""
import json
import time
from groq import Groq
from config import GROQ_API_KEY, GROQ_MODEL
from db import get_connection

PROMPT_TEMPLATE = """You are an editor for a daily AI industry newsletter. Below are \
multiple articles covering what may be the same underlying story, from different sources.

Sources:
{sources_block}

Do two things:
1. Write ONE synthesized summary (2-3 sentences, plain language, no hype) that \
combines what's actually new here.
2. Score importance from 1-10 for someone building with AI.

Respond ONLY with valid JSON, no other text:
{{"summary": "...", "importance_score": N}}
"""

def build_sources_block(articles):
    lines = []
    for a in articles:
        snippet = (a["summary_raw"] or "")[:300]
        lines.append(f'- [{a["source"]}] {a["title"][:80]}\n  {snippet}')
    return "\n".join(lines)

def quick_test():
    groq_client = Groq(api_key=GROQ_API_KEY)
    conn = get_connection()
    
    # Get only 10 unsummarized clusters
    clusters = conn.execute(
        "SELECT id FROM clusters WHERE summary IS NULL LIMIT 10"
    ).fetchall()
    
    print(f"Testing with {len(clusters)} clusters...")
    done = 0
    
    for idx, c in enumerate(clusters, 1):
        cluster_id = c["id"]
        articles = conn.execute(
            "SELECT source, title, summary_raw FROM articles WHERE cluster_id = ?",
            (cluster_id,),
        ).fetchall()
        
        if not articles:
            continue
        
        prompt = PROMPT_TEMPLATE.format(sources_block=build_sources_block(articles))
        
        try:
            print(f"[{idx}] Summarizing cluster {cluster_id}... ", end="", flush=True)
            response = groq_client.chat.completions.create(
                model=GROQ_MODEL,
                max_tokens=400,
                messages=[{"role": "user", "content": prompt}],
            )
            text = response.choices[0].message.content.strip()
            text = text.replace("```json", "").replace("```", "").strip()
            parsed = json.loads(text)
            
            conn.execute(
                "UPDATE clusters SET summary = ?, importance_score = ? WHERE id = ?",
                (parsed["summary"], int(parsed["importance_score"]), cluster_id),
            )
            conn.commit()
            done += 1
            print(f"✓ Done (score: {parsed['importance_score']})")
            
        except Exception as e:
            print(f"✗ Error: {str(e)[:60]}")
        
        time.sleep(0.5)  # Rate limit
    
    conn.close()
    print(f"\n✓ Quick test complete: {done}/{len(clusters)} summarized")

if __name__ == "__main__":
    quick_test()
