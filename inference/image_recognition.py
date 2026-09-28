import torch
import base64
import json
import requests
import os
from PIL import Image
from transformers import ViTForImageClassification, ViTImageProcessor

# --- GLOBAL MODEL LOADING (Runs once on import) ---
PRELIMINARY_MODEL_PATH = './preliminary_ai_detector'
OLLAMA_URL = "http://localhost:11434/api/generate"

print("[*] Loading ViT Preliminary Model...")
try:
    processor = ViTImageProcessor.from_pretrained('google/vit-base-patch16-224-in21k')
    prelim_model = ViTForImageClassification.from_pretrained(PRELIMINARY_MODEL_PATH)
    prelim_model.eval()
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    prelim_model.to(device)
    MODEL_LOADED = True
except Exception as e:
    print(f"[!] Warning: Could not load ViT model. Ensure it is trained/saved at {PRELIMINARY_MODEL_PATH}. Error: {e}")
    MODEL_LOADED = False
    device = torch.device('cpu')

def _encode_image(image_path):
    """Helper: Converts image to base64."""
    with open(image_path, "rb") as img_file:
        return base64.b64encode(img_file.read()).decode('utf-8')

def _query_llm(image_path, config):
    """Helper: Queries the configured LLM (Ollama or OpenAI) for arbitration/reasoning."""
    b64_image = _encode_image(image_path)
    provider = config.get("llm_provider", "ollama")
    
    prompt = """Analyze this image for signs of AI generation. Look specifically for:
    1. Gibberish, warped, or misspelled text.
    2. Anatomical errors (fingers, eyes, limbs).
    3. Physics/Lighting errors (shadows, reflections).
    4. Background details that melt or blur unnaturally.
    Respond ONLY in valid JSON format: {"verdict": "AI" or "Real", "confidence": 0.0 to 1.0, "reasoning": "brief explanation"}"""

    if provider == "openai":
        try:
            from openai import OpenAI
            client = OpenAI(api_key=config.get("openai_api_key"))
            response = client.chat.completions.create(
                model=config.get("openai_model", "gpt-4o-mini"),
                messages=[{"role": "user", "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_image}"}}
                ]}],
                response_format={"type": "json_object"}
            )
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            return {"verdict": "Unknown", "confidence": 0.5, "reasoning": f"OpenAI Error: {str(e)}"}
            
    else: # Default to Ollama
        try:
            payload = {
                "model": config.get("ollama_model", "llava:7b"),
                "prompt": prompt,
                "images": [b64_image],
                "stream": False,
                "format": "json"
            }
            response = requests.post(OLLAMA_URL, json=payload, timeout=60)
            response.raise_for_status()
            return json.loads(response.json()['response'])
        except Exception as e:
            return {"verdict": "Unknown", "confidence": 0.5, "reasoning": f"Ollama Error: {str(e)}"}

def analyze_image(image_path, config):
    """
    Main library function. Analyzes an image using the tiered approach.
    
    Args:
        image_path (str): Path to the image file.
        config (dict): Configuration dictionary (see email_pipeline.py for example).
        
    Returns:
        dict: Analysis report for this specific image.
    """
    filename = os.path.basename(image_path)
    result = {
        "filename": filename,
        "preliminary_score": 0.5,
        "final_verdict": "Unknown",
        "final_confidence": 0.5,
        "source": "Fallback",
        "reasoning": "Model not loaded or error occurred."
    }

    # Step 1: Preliminary ViT Analysis
    if MODEL_LOADED:
        image = Image.open(image_path).convert('RGB')
        inputs = processor(images=image, return_tensors="pt").to(device)
        with torch.no_grad():
            logits = prelim_model(**inputs).logits
            probs = torch.nn.functional.softmax(logits, dim=1)
            ai_prob = probs[0][1].item() # Assuming index 1 is 'AI'
            
        result["preliminary_score"] = round(ai_prob, 3)
    else:
        return result # Bail out if model isn't loaded

    ai_score = result["preliminary_score"]
    low_thresh = config.get("confidence_low", 0.20)
    high_thresh = config.get("confidence_high", 0.80)
    use_llm = config.get("use_llm", True)
    always_explain = config.get("always_explain", False)

    # Step 2: Confidence Gate
    if ai_score >= high_thresh:
        result.update({"final_verdict": "AI", "final_confidence": ai_score, "source": "Preliminary_ViT", "reasoning": "High confidence ViT detection."})
        return result
    elif ai_score <= low_thresh and not always_explain:
        result.update({"final_verdict": "Real", "final_confidence": 1.0 - ai_score, "source": "Preliminary_ViT", "reasoning": "High confidence ViT detection of authentic image."})
        return result

    # Step 3: LLM Arbiter (Grey zone OR forced explanation)
    if use_llm:
        print(f"      -> Invoking LLM Arbiter ({config.get('llm_provider')}) for {filename}...")
        arbiter_result = _query_llm(image_path, config)
        
        # Combine scores (weighted average: trust LLM slightly more in grey zones)
        final_conf = (ai_score * 0.4) + (arbiter_result.get("confidence", 0.5) * 0.6)
        
        result.update({
            "final_verdict": arbiter_result.get("verdict", "Unknown"),
            "final_confidence": round(final_conf, 3),
            "source": f"LLM_Arbiter_{config.get('llm_provider')}",
            "reasoning": arbiter_result.get("reasoning", "No reasoning provided.")
        })
    else:
        result.update({"reasoning": "LLM disabled in config."})

    return result