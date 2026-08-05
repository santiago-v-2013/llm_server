from base_runner import TestRunner, PIXEL_B64

if __name__ == "__main__":
    TestRunner.run_test(
        name="Media (Image-to-Video)",
        config_updates={
            "api.yaml": {"active_engines": {"media": "diffusers"}},
            "media.yaml": {"diffusers": {"task": "image-to-video", "model": "stabilityai/stable-video-diffusion-img2vid"}}
        },
        endpoint="/v1/media/generations",
        payload={"image_b64": PIXEL_B64, "num_inference_steps": 1}
    )
