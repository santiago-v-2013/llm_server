from base_runner import TestRunner, PIXEL_B64

if __name__ == "__main__":
    TestRunner.run_test(
        name="Vision (Object Detection - GroundingDINO)",
        config_updates={
            "api.yaml": {"active_engines": {"vision": "huggingface"}},
            "vision.yaml": {"huggingface": {"task": "zero-shot-object-detection", "model": "IDEA-Research/grounding-dino-base"}}
        },
        endpoint="/v1/vision/analyses",
        payload={"prompt": "persona, perro", "image_base64": PIXEL_B64}
    )
