from base_runner import TestRunner

if __name__ == "__main__":
    TestRunner.run_test(
        name="Media (Text-to-Video)",
        config_updates={
            "api.yaml": {"active_engines": {"media": "diffusers"}},
            "media.yaml": {"diffusers": {"task": "text-to-video", "model": "damo-vilab/text-to-video-ms-1.7b"}}
        },
        endpoint="/v1/media/generations",
        payload={"prompt": "un pez nadando", "num_inference_steps": 1, "num_frames": 2}
    )
