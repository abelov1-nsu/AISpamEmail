"""
image_analyzer.py

Small AI-image detection library for use in an email/attachment analysis pipeline.

The detector is intentionally independent from the optional Qwen explanation layer:
- ImageDetector performs the actual binary classification.
- QwenImageExplainer can inspect the image + detector result and provide reasons.
- Qwen is optional; detector results remain usable when the API is unavailable.

Dependencies:
    pip install torch torchvision pillow

Optional Qwen dependency:
    pip install openai
"""

from __future__ import annotations

import base64
import io
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import torch
from PIL import Image
from torchvision import models, transforms


@dataclass
class DetectionResult:
    """Result produced by the local image detector."""

    label: str
    score: float
    threshold: float
    model: str

    @property
    def is_ai(self) -> bool:
        return self.label == "ai"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ImageDetector:
    """
    Lightweight binary AI/real image classifier.

    The model checkpoint is expected to contain a torchvision-compatible
    classifier whose final layer outputs one logit.

    Label convention:
        sigmoid(logit) >= threshold -> AI
        sigmoid(logit) < threshold  -> real

    The exact training architecture must match `architecture`.
    """

    def __init__(
        self,
        checkpoint: str | Path,
        architecture: str = "mobilenet_v3_small",
        threshold: float = 0.5,
        device: str | None = None,
        image_size: int = 224,
    ) -> None:
        self.checkpoint = Path(checkpoint)
        self.threshold = threshold
        self.image_size = image_size
        self.device = torch.device(
            device or ("cuda" if torch.cuda.is_available() else "cpu")
        )

        self.model = self._build_model(architecture)
        self._load_checkpoint()
        self.model.to(self.device)
        self.model.eval()

        self.transform = transforms.Compose(
            [
                transforms.Resize((image_size, image_size)),
                transforms.ToTensor(),
                transforms.Normalize(
                    mean=(0.485, 0.456, 0.406),
                    std=(0.229, 0.224, 0.225),
                ),
            ]
        )

    @staticmethod
    def _build_model(architecture: str) -> torch.nn.Module:
        if architecture == "mobilenet_v3_small":
            model = models.mobilenet_v3_small(weights=None)
            model.classifier[-1] = torch.nn.Linear(
                model.classifier[-1].in_features, 1
            )
            return model

        if architecture == "efficientnet_b0":
            model = models.efficientnet_b0(weights=None)
            model.classifier[-1] = torch.nn.Linear(
                model.classifier[-1].in_features, 1
            )
            return model

        raise ValueError(f"Unsupported architecture: {architecture}")

    def _load_checkpoint(self) -> None:
        checkpoint = torch.load(
            self.checkpoint,
            map_location=self.device,
            weights_only=False,
        )

        # Support either a raw state_dict or a checkpoint dictionary.
        state_dict = checkpoint.get("model_state_dict", checkpoint)
        self.model.load_state_dict(state_dict)

    @torch.inference_mode()
    def predict(self, image: Image.Image | str | Path) -> DetectionResult:
        """Classify an image as AI-generated or real."""

        if not isinstance(image, Image.Image):
            image = Image.open(image)

        image = image.convert("RGB")
        tensor = self.transform(image).unsqueeze(0).to(self.device)

        logit = self.model(tensor).squeeze().item()
        score = float(torch.sigmoid(torch.tensor(logit)).item())

        label = "ai" if score >= self.threshold else "real"

        return DetectionResult(
            label=label,
            score=score,
            threshold=self.threshold,
            model=self.checkpoint.stem,
        )


class QwenImageExplainer:
    """
    Optional OpenAI-compatible vision API client.

    Qwen receives:
      1. the original image
      2. the local detector's numerical result

    It does NOT replace the local detector's classification.
    """

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        timeout: float = 60.0,
    ) -> None:
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise ImportError(
                "QwenImageExplainer requires the 'openai' package. "
                "Install it with: pip install openai"
            ) from exc

        self.client = OpenAI(
            base_url=base_url,
            api_key=api_key,
            timeout=timeout,
        )
        self.model = model

    @staticmethod
    def _image_data_url(image: Image.Image) -> str:
        buffer = io.BytesIO()
        image.convert("RGB").save(buffer, format="JPEG", quality=90)
        encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
        return f"data:image/jpeg;base64,{encoded}"

    def analyze(
        self,
        image: Image.Image | str | Path,
        detector_result: DetectionResult,
    ) -> dict[str, Any]:
        """Ask Qwen for visual evidence supporting or contradicting the detector."""

        if not isinstance(image, Image.Image):
            image = Image.open(image)

        result_json = json.dumps(
            detector_result.to_dict(),
            ensure_ascii=False,
        )

        prompt = f"""
You are an image-forensics assistant.

A local AI-image detector produced this result:
{result_json}

Inspect the supplied image independently for visible characteristics that
may support or contradict that result. Pay particular attention to:
- malformed or inconsistent text
- hands, fingers, teeth, eyes, ears and other anatomy
- object geometry and repeated structures
- lighting, reflections and shadows
- perspective and physical inconsistencies
- textures and unnatural fine detail
- background objects and their relationships
- other visible generation artifacts

Do not claim that an image is AI-generated solely because it looks unusual.
Do not invent hidden metadata or provenance.

Return ONLY valid JSON with this structure:
{{
  "verdict": "supports_detector" | "does_not_support_detector" | "inconclusive",
  "reasons": [
    {{
      "category": "string",
      "observation": "specific visible observation"
    }}
  ],
  "explanation": "short overall explanation"
}}
""".strip()

        response = self.client.chat.completions.create(
            model=self.model,
            temperature=0.1,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": self._image_data_url(image),
                            },
                        },
                    ],
                }
            ],
        )

        content = response.choices[0].message.content
        if not content:
            raise RuntimeError("Qwen returned an empty response.")

        return json.loads(content)


def analyze_image(
    detector: ImageDetector,
    image: Image.Image | str | Path,
    qwen: QwenImageExplainer | None = None,
) -> dict[str, Any]:
    """
    Convenience function for the future main pipeline.

    The detector always runs. Qwen runs only when supplied and available.
    A Qwen failure does not invalidate the detector's ruling.
    """

    detector_result = detector.predict(image)

    output: dict[str, Any] = {
        "classification": detector_result.to_dict(),
        "qwen": None,
    }

    if qwen is not None and detector_result.is_ai:
        try:
            output["qwen"] = qwen.analyze(image, detector_result)
        except Exception as exc:
            output["qwen"] = {
                "available": False,
                "error": str(exc),
            }

    return output


__all__ = [
    "DetectionResult",
    "ImageDetector",
    "QwenImageExplainer",
    "analyze_image",
]