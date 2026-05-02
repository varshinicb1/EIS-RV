import os
import sqlite3
import json
import torch
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
from peft import PeftModel

# ── Configuration ────────────────────────────────────────────────────────
BASE_MODEL_ID = "Qwen/Qwen1.5-1.8B-Chat"
ADAPTER_DIR = "./models/Raman-Qwen-Agent"
CACHE_DB = "./datasets/materials_cache.db"

# ── Setup DB ─────────────────────────────────────────────────────────────
def init_db():
    os.makedirs(os.path.dirname(CACHE_DB), exist_ok=True)
    conn = sqlite3.connect(CACHE_DB)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS materials (
            id TEXT PRIMARY KEY,
            properties JSON,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# ── Load Model ───────────────────────────────────────────────────────────
print("🧪 Initializing Alchemist Agent...")
print("Loading tokenizer...")
tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL_ID, trust_remote_code=True)

print("Loading 4-bit Base Model...")
bnb_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_compute_dtype=torch.bfloat16,
)

base_model = AutoModelForCausalLM.from_pretrained(
    BASE_MODEL_ID,
    quantization_config=bnb_config,
    device_map="auto",
    trust_remote_code=True
)

print(f"Loading Fine-Tuned Adapter from {ADAPTER_DIR}...")
if os.path.exists(ADAPTER_DIR):
    model = PeftModel.from_pretrained(base_model, ADAPTER_DIR)
    print("✅ Custom Agent loaded successfully!")
else:
    print("⚠️ Warning: Adapter not found! Falling back to base model.")
    model = base_model

model.eval()

# ── FastAPI App ──────────────────────────────────────────────────────────
app = FastAPI(title="RĀMAN Alchemist API", version="1.0.0")

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    temperature: float = 0.7

@app.post("/api/synthesize")
async def generate_synthesis(request: ChatRequest):
    """
    Primary endpoint for the Alchemist Canvas to request protocols.
    Uses the locally fine-tuned Qwen model.
    """
    # 1. Format messages into ChatML prompt
    messages_dict = [{"role": msg.role, "content": msg.content} for msg in request.messages]
    
    # Check cache first for "context"
    last_msg = request.messages[-1].content.lower()
    conn = sqlite3.connect(CACHE_DB)
    cursor = conn.cursor()
    cursor.execute("SELECT properties FROM materials WHERE id=?", ("mock_material",))
    row = cursor.fetchone()
    conn.close()

    text = tokenizer.apply_chat_template(
        messages_dict,
        tokenize=False,
        add_generation_prompt=True
    )

    model_inputs = tokenizer([text], return_tensors="pt").to(model.device)

    # 2. Run Inference
    with torch.no_grad():
        generated_ids = model.generate(
            **model_inputs,
            max_new_tokens=512,
            temperature=request.temperature,
            do_sample=True,
            pad_token_id=tokenizer.eos_token_id
        )

    # 3. Decode Response
    generated_ids = [
        output_ids[len(input_ids):] for input_ids, output_ids in zip(model_inputs.input_ids, generated_ids)
    ]
    response_text = tokenizer.batch_decode(generated_ids, skip_special_tokens=True)[0]

    # Try to parse the response as JSON if the model generated a Tool Call
    # We fallback to returning it as text if it failed to output valid JSON
    tool_calls = []
    try:
        # Extract everything between ```json and ```
        if "```json" in response_text:
            json_str = response_text.split("```json")[1].split("```")[0].strip()
            tool_calls = [json.loads(json_str)]
    except Exception as e:
        print("Failed to parse tool call:", e)

    return {
        "status": "success",
        "agent_response": response_text,
        "tool_calls": tool_calls
    }

if __name__ == "__main__":
    import uvicorn
    print("🚀 Starting Production Alchemist Backend on port 8001...")
    uvicorn.run(app, host="127.0.0.1", port=8001)
