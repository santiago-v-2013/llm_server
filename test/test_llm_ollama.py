from base_runner import TestRunner

if __name__ == "__main__":
    TestRunner.run_test(
        name="LLM Texto (Ollama)",
        config_updates={
            "api.yaml": {"active_engines": {"llm": "ollama"}}
        },
        endpoint="/v1/chat/completions",
        payload={"messages": [{"role": "user", "content": "Di hola"}]}
    )
