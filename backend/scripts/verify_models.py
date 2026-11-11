import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

# Lấy key từ môi trường hoặc nhập trực tiếp
api_key = os.getenv("GEMINI_API_KEY")
if not api_key or api_key == "your_gemini_api_key_here":
    api_key = input("Nhập Gemini API Key của bạn để test: ").strip()

if not api_key:
    print("Chưa cung cấp API Key!")
    exit(1)

print("Đang kiểm tra API Key đã cung cấp...")
genai.configure(api_key=api_key)

try:
    print("Danh sách models khả dụng:")
    models = genai.list_models()
    for m in models:
        if 'generateContent' in m.supported_generation_methods:
            print(f" - {m.name}")
    print("\n✓ API Key hoạt động bình thường!")
except Exception as e:
    print(f"\n✗ Lỗi: {e}")
    print("Gợi ý: Kiểm tra xem API Key đã kích hoạt 'Generative Language API' chưa, hoặc tạo key mới tại https://aistudio.google.com/")
