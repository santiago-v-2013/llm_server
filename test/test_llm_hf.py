from base_runner import TestRunner

if __name__ == "__main__":
    TestRunner.run_test(
        name="LLM Texto (HuggingFace)",
        config_updates={
            "api.yaml": {"active_engines": {"llm": "huggingface"}},
            "llm.yaml": {"huggingface": {"task": "text-generation", "model": "HuggingFaceTB/SmolLM-135M-Instruct"}}
        },
        endpoint="/v1/chat/completions",
        payload={"messages": [{"role": "user", "content": "Di hola"}]}
    )
