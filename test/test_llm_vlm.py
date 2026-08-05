from base_runner import TestRunner, PIXEL_B64

if __name__ == "__main__":
    TestRunner.run_test(
        name="LLM Visión (VLM - HuggingFace)",
        config_updates={
            "api.yaml": {"active_engines": {"llm": "huggingface"}},
            "llm.yaml": {"huggingface": {"task": "image-text-to-text", "model": "bczhou/tiny-llava-v1-hf"}}
        },
        endpoint="/v1/chat/completions",
        payload={"messages": [{"role": "user", "content": [
            {"type": "text", "text": "Describe esta imagen."},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{PIXEL_B64}"}}
        ]}]}
    )
