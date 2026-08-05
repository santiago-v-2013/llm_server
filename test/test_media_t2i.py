from base_runner import TestRunner

if __name__ == "__main__":
    TestRunner.run_test(
        name="Media (Text-to-Image)",
        config_updates={
            "api.yaml": {"active_engines": {"media": "diffusers"}},
            "media.yaml": {"diffusers": {"task": "text-to-image", "model": "segmind/tiny-sd"}}
        },
        endpoint="/v1/media/generations",
        payload={"prompt": "un punto rojo", "num_inference_steps": 1}
    )
