import json
import os
from datasets import load_dataset

OUTPUT_PATH = "./datasets/raman_agent_interactions.json"

def prepare_dataset():
    print("🧪 Downloading Real Chemistry Dataset: AI4Chem/ChemData700K ...")
    # We load a subset (e.g., the first 5,000 rows) so training on an RTX 4050 doesn't take 3 months
    # In a full supercomputer run, we would use the entire 730,000 row dataset.
    dataset = load_dataset("AI4Chem/ChemData700K", split="train[:5000]")
    
    formatted_data = []
    
    for row in dataset:
        # Convert to ChatML format for Qwen/ChemLLM
        # Assuming the dataset has 'instruction', 'input', 'output' columns
        instruction = row.get("instruction", "")
        input_text = row.get("input", "")
        output = row.get("output", "")
        
        user_prompt = instruction
        if input_text:
            user_prompt += f"\nInput: {input_text}"
            
        chat_text = f"<|im_start|>user\n{user_prompt}<|im_end|>\n<|im_start|>assistant\n{output}<|im_end|>"
        formatted_data.append({"text": chat_text})

    # Save to the JSON file expected by finetune_agent.py
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(formatted_data, f, indent=2)
        
    print(f"✅ Successfully formatted {len(formatted_data)} real chemistry interactions into {OUTPUT_PATH}.")

if __name__ == "__main__":
    prepare_dataset()
