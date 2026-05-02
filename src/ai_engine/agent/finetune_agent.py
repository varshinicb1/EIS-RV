import os
import json
import torch
from datasets import load_dataset
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    TrainingArguments,
    TrainerCallback,
)
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
from trl import SFTTrainer

# ── Configuration ────────────────────────────────────────────────────────
MODEL_ID = "Qwen/Qwen1.5-1.8B-Chat"
OUTPUT_DIR = "./models/Raman-Qwen-Agent"
DATASET_PATH = "./datasets/raman_agent_interactions.json"
LOG_FILE = os.path.join(OUTPUT_DIR, "training_logs.json")

# ── Custom Callback for Web Dashboard ────────────────────────────────────
class JsonLogCallback(TrainerCallback):
    def __init__(self):
        self.logs = []
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        # Clear old logs
        with open(LOG_FILE, "w") as f:
            json.dump([], f)

    def on_log(self, args, state, control, logs=None, **kwargs):
        if logs is not None and "loss" in logs:
            log_entry = {
                "step": state.global_step,
                "loss": logs["loss"],
                "learning_rate": logs.get("learning_rate", 0.0)
            }
            self.logs.append(log_entry)
            with open(LOG_FILE, "w") as f:
                json.dump(self.logs, f)

def run_finetuning():
    """
    Fine-tunes ChemLLM-7B using QLoRA specifically for tool-calling and 
    autonomous agent orchestration within RĀMAN Studio.
    """
    print("\n⚠️ WARNING: Detected target GPU: RTX 4050 (6GB VRAM) ⚠️")
    print("Fine-tuning a 7B model natively requires ~12GB VRAM. We have enabled EXTREME memory constraints")
    print("(Gradient Checkpointing, Batch Size 1, 4-bit Quantization).")
    print("If you still encounter a CUDA OutOfMemoryError, you must use a smaller model (e.g., Qwen1.5-1.8B) or a cloud GPU.\n")

    print("Loading tokenizer...")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, trust_remote_code=True)
    tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "right"

    print("Configuring 4-bit quantization for 6GB VRAM constraints...")
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
        bnb_4bit_use_double_quant=True, # Added to save even more memory
    )

    print("Loading base model...")
    try:
        model = AutoModelForCausalLM.from_pretrained(
            MODEL_ID,
            quantization_config=bnb_config,
            device_map="auto",
            trust_remote_code=True,
            low_cpu_mem_usage=True,
            torch_dtype=torch.bfloat16,
        )
    except Exception as e:
        print(f"\n❌ FAILED TO LOAD MODEL INTO MEMORY: {e}")
        return
    
    # Extreme memory savings: enable gradient checkpointing
    model.gradient_checkpointing_enable()
    model = prepare_model_for_kbit_training(model)
    
    # LoRA Config targeting attention layers
    peft_config = LoraConfig(
        r=8, # Reduced rank to save memory
        lora_alpha=16,
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM",
        target_modules=["q_proj", "v_proj"] # Reduced targets to save memory
    )
    # Removed get_peft_model because SFTTrainer wraps it automatically
    
    print("Loading dataset...")
    try:
        dataset = load_dataset("json", data_files=DATASET_PATH, split="train")
    except Exception as e:
        print(f"⚠️ Could not load dataset {DATASET_PATH}. Please create the dataset first. Error: {e}")
        return

    from trl import SFTConfig
    
    # Training arguments optimized for EXTREME LOW VRAM (6GB)
    training_args = SFTConfig(
        output_dir=OUTPUT_DIR,
        per_device_train_batch_size=1,        # Absolute minimum
        gradient_accumulation_steps=16,       # Compensate for batch size 1
        optim="paged_adamw_8bit",             # 8-bit optimizer to save VRAM
        save_steps=50,
        logging_steps=1,                      # Log every step so the dashboard updates quickly
        learning_rate=2e-4,
        bf16=True,
        max_grad_norm=0.3,
        max_steps=500,
        warmup_steps=10,
        lr_scheduler_type="cosine",
        gradient_checkpointing=True,          # Critical for 6GB GPU
        dataset_text_field="text",
        max_length=512,
    )

    print("Initializing SFT Trainer...")
    trainer = SFTTrainer(
        model=model,
        train_dataset=dataset,
        peft_config=peft_config,
        processing_class=tokenizer,
        args=training_args,
        callbacks=[JsonLogCallback()],        # Hook into our Web UI
    )

    print("Starting fine-tuning...")
    try:
        trainer.train()
    except torch.cuda.OutOfMemoryError:
        print("\n💥 CRITICAL: CUDA Out Of Memory. A 7B model simply cannot fit in 6GB VRAM even with extreme optimizations.")
        print("Please switch to a smaller model (e.g., Qwen-1.5B) or use a 12GB+ GPU.\n")
        return
    
    print(f"✅ Fine-tuning complete. Saving adapter to {OUTPUT_DIR}...")
    trainer.model.save_pretrained(OUTPUT_DIR)
    tokenizer.save_pretrained(OUTPUT_DIR)

if __name__ == "__main__":
    run_finetuning()
