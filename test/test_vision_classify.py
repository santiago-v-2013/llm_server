from base_runner import TestRunner, PIXEL_B64

if __name__ == "__main__":
    TestRunner.run_test(
        name="Vision (Image Classification)",
        config_updates={
            "api.yaml": {"active_engines": {"vision": "huggingface"}},
            "vision.yaml": {"huggingface": {"task": "zero-shot-image-classification", "model": "openai/clip-vit-base-patch32"}}
        },
        endpoint="/v1/vision/analyses",
        payload={"image_base64": PIXEL_B64, "prompt": "punto, perro, gato"}
    )
