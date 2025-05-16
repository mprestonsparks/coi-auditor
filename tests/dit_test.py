from transformers.pipelines import pipeline

object_detector = pipeline("object-detection", model="nielsr/dit-base-finetuned-publaynet")
results = object_detector("debug_page_image.png")
print(results)