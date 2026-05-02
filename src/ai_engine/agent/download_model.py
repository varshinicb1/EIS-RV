import os
import argparse
from huggingface_hub import snapshot_download

def download_chemllm(model_id="AI4Chem/ChemLLM-7B-Chat", dest_dir="./models/ChemLLM-7B-Chat"):
    """
    Downloads the ChemLLM 7B Chat model from HuggingFace.
    """
    print(f"Starting download of {model_id}...")
    print(f"Destination: {os.path.abspath(dest_dir)}")
    
    os.makedirs(dest_dir, exist_ok=True)
    
    # We download ignoring huge safetensors if user wants to use GGUF, but by default we get the PyTorch weights for fine-tuning
    snapshot_download(
        repo_id=model_id,
        local_dir=dest_dir,
        local_dir_use_symlinks=False,
        resume_download=True,
    )
    
    print("✅ Download complete! Model weights are ready for fine-tuning.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="AI4Chem/ChemLLM-7B-Chat", help="HuggingFace model ID")
    parser.add_argument("--dest", default="./models/ChemLLM-7B-Chat", help="Destination folder")
    args = parser.parse_args()
    
    download_chemllm(args.model, args.dest)
