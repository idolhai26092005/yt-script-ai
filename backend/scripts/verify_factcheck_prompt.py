import os
import sys
import json
import asyncio

sys.path.append(os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

from app.core.production_prompts import HISTORICAL_FACT_CHECK_PROMPT
from app.services.gemini.base import BaseGeminiService

# Sample inaccurate script data (Ramses II and Tutankhamun co-existing in KV62)
sample_script = {
    "topic_type": "historical",
    "overview_analysis_vi": "Phân tích kịch bản lịch sử Ai Cập.",
    "characters": [
        {
            "character_name": "Ramses II",
            "description_en": "Pharaoh of the 19th Dynasty, wearing Nemes",
            "key_identifiers_en": "Nemes headcloth"
        },
        {
            "character_name": "Tutankhamun",
            "description_en": "Pharaoh of the 18th Dynasty, wearing Uraeus",
            "key_identifiers_en": "Uraeus crown"
        }
    ],
    "environment_master_prompt_en": "Ancient Egyptian tomb KV62.",
    "scenes": [
        {
            "scene_number": 1,
            "title": "Scene 1 [00:00 - 00:08]",
            "action_detail_vi": "Ramses II thảo luận chiến thuật với Tutankhamun trong lăng mộ KV62.",
            "emotion_gesture_vi": "Cả hai đều nghiêm trang.",
            "camera_movement_vi": "Dolly in.",
            "transition_to_next_vi": "Chuyển cảnh.",
            "veo3_prompt_en": "Ramses II and Tutankhamun standing side by side in KV62 tomb, anime style, 9:16."
        }
    ],
    "reference_images": {
        "character_ref_prompt_en": "Character ref",
        "background_ref_prompt_en": "Background ref",
        "thumbnail_ref_prompt_en": "Thumbnail ref"
    }
}

async def main():
    # 1. Print verification of the prompt content
    print("=== Verification 1: Inspecting Prompt Content ===")
    assert "TIMELINE CROSS-CHECK" in HISTORICAL_FACT_CHECK_PROMPT
    assert "CHARACTER ROLE ACCURACY" in HISTORICAL_FACT_CHECK_PROMPT
    print("Success: HISTORICAL_FACT_CHECK_PROMPT contains the new rules!")
    
    # 2. Check if a live API key is available
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key or api_key == "your_gemini_api_key_here":
        # Check if we can extract the key from backend config or use a mock
        print("\nNo active GEMINI_API_KEY environment variable found.")
        print("Live Fact-Check test skipped. Prompt rules verification succeeded!")
        return

    print(f"\nActive GEMINI_API_KEY found. Running live Fact-Check with Gemini...")
    service = BaseGeminiService(api_key=api_key)
    prompt = HISTORICAL_FACT_CHECK_PROMPT.format(script_json=json.dumps(sample_script, ensure_ascii=False))
    
    try:
        raw_res = await service._call_gemini_with_retry(
            prompt=prompt,
            model_name="gemini-2.5-flash",
            generation_config={"response_mime_type": "application/json"}
        )
        res = json.loads(raw_res)
        print("\n=== Live Fact-Check Result ===")
        print(f"Has issues detected: {res.get('has_issues')}")
        print(f"Fact-check notes: {res.get('fact_check_notes')}")
        for scene in res.get("scenes", []):
            print(f"\nScene {scene.get('scene_number')} audit:")
            print(f"- Needs fact check: {scene.get('needs_fact_check')}")
            print(f"- Fact check note: {scene.get('fact_check_note_vi')}")
            print(f"- Action detail: {scene.get('action_detail_vi')}")
    except Exception as e:
        print(f"Error calling live Gemini API: {str(e)}")

if __name__ == "__main__":
    asyncio.run(main())
