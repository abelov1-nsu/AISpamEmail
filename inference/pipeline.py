# email_pipeline.py
import os
import email
import email.policy
import re
import base64
import tempfile
import shutil
import json
from image_analyzer import analyze_image

# ==========================================
# CONFIGURATION TOGGLES
# ==========================================
CONFIG = {
    # --- LLM TOGGLES ---
    "use_llm": True,             # Master switch. False = 100% offline, ViT only.
    "llm_provider": "ollama",    # Options: "ollama" or "openai"
    
    # --- PROVIDER SPECIFIC ---
    "ollama_model": "llava:7b",
    "openai_api_key": "sk-YOUR-API-KEY-HERE",
    "openai_model": "gpt-4o-mini",
    
    # --- BEHAVIOR ---
    "always_explain": False,     # Force LLM to give a reason even if ViT is 99% sure
    "confidence_low": 0.20,      # Below this = Real
    "confidence_high": 0.80      # Above this = AI
}

def _extract_inline_base64(html_content, temp_dir):
    """Helper: Finds base64 encoded images inside HTML and saves them."""
    image_paths = []
    pattern = re.compile(r'data:image/(png|jpeg|jpg|gif);base64,([A-Za-z0-9+/=]+)')
    for i, match in enumerate(pattern.finditer(html_content)):
        ext = match.group(1)
        b64_data = match.group(2)
        img_path = os.path.join(temp_dir, f"inline_b64_{i}.{ext}")
        with open(img_path, 'wb') as f:
            f.write(base64.b64decode(b64_data))
        image_paths.append(img_path)
    return image_paths

def parse_eml(eml_path):
    """Parses .eml, extracts metadata, text, and all images (attached + inline)."""
    with open(eml_path, 'rb') as f:
        msg = email.message_from_binary_file(f, policy=email.policy.default)

    parsed = {
        "metadata": {"subject": msg.get("subject", ""), "from": msg.get("from", ""), "to": msg.get("to", ""), "date": msg.get("date", "")},
        "text_body": "",
        "html_body": "",
        "image_paths": []
    }

    temp_dir = tempfile.mkdtemp(prefix="eml_forensics_")
    parsed["temp_dir"] = temp_dir

    for part in msg.walk():
        content_type = part.get_content_type()
        
        # Extract Text
        if content_type == "text/plain" and not parsed["text_body"]:
            parsed["text_body"] = part.get_content()
        elif content_type == "text/html" and not parsed["html_body"]:
            parsed["html_body"] = part.get_content()
            
        # Extract Image Attachments
        if part.get_content_maintype() == "image":
            filename = part.get_filename() or f"attachment_{len(parsed['image_paths'])}.jpg"
            img_data = part.get_payload(decode=True)
            img_path = os.path.join(temp_dir, filename)
            with open(img_path, 'wb') as img_file:
                img_file.write(img_data)
            parsed["image_paths"].append(img_path)

    # Catch inline base64 images missed by the MIME walker
    if parsed["html_body"]:
        parsed["image_paths"].extend(_extract_inline_base64(parsed["html_body"], temp_dir))

    return parsed

def process_email(eml_path, output_json_path):
    """Main pipeline orchestrator."""
    print(f"[*] Starting Forensic Pipeline for: {eml_path}")
    
    # 1. Parse Email
    email_data = parse_eml(eml_path)
    
    report = {
        "email_metadata": email_data["metadata"],
        "text_analysis": "Skipped in this draft (add NLP module here)",
        "images_analyzed": [],
        "overall_verdict": "Pending"
    }
    
    # 2. Analyze Images via Library
    image_paths = email_data["image_paths"]
    if not image_paths:
        print("[*] No images found in email.")
    else:
        print(f"[*] Found {len(image_paths)} images. Analyzing...")
        for img_path in image_paths:
            print(f"   -> Processing {os.path.basename(img_path)}")
            img_report = analyze_image(img_path, CONFIG)
            report["images_analyzed"].append(img_report)
            
    # 3. Cleanup Temp Files
    shutil.rmtree(email_data["temp_dir"])
    
    # 4. Determine Overall Verdict
    if report["images_analyzed"]:
        max_score = max(img["final_confidence"] for img in report["images_analyzed"] if img["final_verdict"] == "AI")
        # Fallback if no AI was detected
        max_score = max_score if max_score > 0 else 0.0 
        
        if max_score >= 0.75:
            report["overall_verdict"] = "HIGH LIKELIHOOD OF AI"
        elif max_score >= 0.40:
            report["overall_verdict"] = "SUSPICIOUS / MIXED"
        else:
            report["overall_verdict"] = "LIKELY AUTHENTIC"
    else:
        report["overall_verdict"] = "NO IMAGES TO ANALYZE"

    # 5. Save JSON Report
    with open(output_json_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=4)
        
    print(f"\n[+] Pipeline complete. Report saved to: {output_json_path}")
    return report

if __name__ == "__main__":
    INPUT_EML = "test_email.eml" 
    OUTPUT_JSON = "forensic_report.json"
    
    if not os.path.exists(INPUT_EML):
        print(f"Error: {INPUT_EML} not found. Please provide a valid .eml file.")
    else:
        process_email(INPUT_EML, OUTPUT_JSON)