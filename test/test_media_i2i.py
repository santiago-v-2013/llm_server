from base_runner import TestRunner, PIXEL_B64

if __name__ == "__main__":
    TestRunner.run_test(
        name="Media (Image-to-Image)",
        config_updates={
            "api.yaml": {"active_engines": {"media": "diffusers"}},
            "media.yaml": {"diffusers": {"task": "image-to-image", "model": "segmind/tiny-sd"}}
        },
        endpoint="/v1/media/generations",
        payload={"prompt": "hazlo azul", "image_b64": PIXEL_B64, "num_inference_steps": 2, "strength": 0.5}
    )
