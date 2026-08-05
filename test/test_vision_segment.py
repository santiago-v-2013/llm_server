from base_runner import TestRunner, PIXEL_B64

if __name__ == "__main__":
    TestRunner.run_test(
        name="Vision (Image Segmentation)",
        config_updates={
            "api.yaml": {"active_engines": {"vision": "huggingface"}},
            "vision.yaml": {"huggingface": {"task": "image-segmentation", "model": "facebook/detr-resnet-50-panoptic"}}
        },
        endpoint="/v1/vision/analyses",
        payload={"image_base64": PIXEL_B64}
    )
