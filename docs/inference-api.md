# Vehicle Detection API

`GET /api/inference/status` returns weight availability, model loading state, device and upload limits. The model loads on the first detection request and is reused. Dataset analysis keeps its existing detector configuration.

`POST /api/inference/detect` accepts JPEG or PNG bytes as the request body. Send `Content-Type: image/jpeg` or `image/png`. Optional query parameters: `confidence` (default 0.3), `iou` (default 0.7). Class IDs 0–3 match `model/YOLO_eval.py`.

```powershell
curl.exe -X POST "http://localhost:8000/api/inference/detect" -H "Content-Type: image/jpeg" --data-binary "@C:\images\frame.jpg"
```

Response includes image dimensions, processing time and detections with `label`, `confidence`, `bbox: [x, y, width, height]` in original image pixels. Uploaded images and results are not saved or added to the dataset. Swagger: `/docs`, Vehicle Detection section.

Install dependencies with `.venv\Scripts\python.exe -m pip install -r requirements-inference.txt`. Default weights: `model/yolo26x_custom.pt`; override using `INFERENCE_WEIGHTS`. Default device is CPU; `INFERENCE_DEVICE` configures another device. The evaluation script is not imported because it initializes a model and contains batch output operations.

One inference request is processed at a time per API worker; overlapping requests return 429 with Retry-After. Upload limit: 15 MB, image limit: 16 megapixels. Unsupported format: 415; corrupted/empty image: 422; missing/unloadable model: 503. Model initialization may take additional time on the first request. Use one API worker to avoid duplicating model memory.
