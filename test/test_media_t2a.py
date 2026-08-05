from base_runner import TestRunner

if __name__ == "__main__":
    TestRunner.run_test(
        name="Media (Text-to-Audio)",
        config_updates={
            "api.yaml": {"active_engines": {"media": "diffusers"}},
            "media.yaml": {"diffusers": {"task": "text-to-audio", "model": "cvssp/audioldm-s-full-v2"}}
        },
        endpoint="/v1/media/generations",
        payload={"prompt": "un aplauso", "num_inference_steps": 1, "audio_length_in_s": 1.0}
    )
