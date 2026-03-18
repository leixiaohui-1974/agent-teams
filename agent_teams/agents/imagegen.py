"""ImageGen agent - image generation via Nano Banana (Gemini)."""
from __future__ import annotations

import base64
import os
from datetime import datetime
from pathlib import Path

from agent_teams.agents.base import BaseAgent
from agent_teams.config import get_settings
from agent_teams.core.client import get_client
from agent_teams.core.message import AgentAction, AgentResult, TaskContext


IMAGEGEN_PROMPT = """You are an expert image prompt engineer. Your job is to take a description
and create an optimized, detailed prompt for Nano Banana (Gemini's image generation model).

When given a description, create a detailed image generation prompt that includes:
- Subject and composition
- Style and artistic direction
- Lighting and atmosphere
- Color palette
- Important details and quality modifiers

Output ONLY the optimized prompt text, nothing else."""


class ImageGenAgent(BaseAgent):
    name = "imagegen"
    role_description = IMAGEGEN_PROMPT

    async def execute(self, context: TaskContext, instruction: str) -> AgentResult:
        """Generate an image using Nano Banana via Gemini API through CLIProxyAPI."""
        settings = get_settings()
        client = get_client()

        # Step 1: Refine the prompt using an LLM
        refined = await super().execute(context, f"Create an image generation prompt for: {instruction}")
        optimized_prompt = refined.content.strip()

        # Step 2: Call Gemini image generation through CLIProxyAPI
        image_model = settings.imagegen.model
        generation_prompt = (
            f"Generate a high-quality image based on this description:\n\n{optimized_prompt}\n\n"
            "Please create the image."
        )

        try:
            resp = await client.generate_image_via_gemini(
                prompt=generation_prompt,
                model=image_model,
            )
            response_content = resp["choices"][0]["message"]["content"]

            # Save output (could be base64 image data or a description)
            output_dir = Path(settings.output.default_dir) / "images"
            output_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

            # Check if response contains base64 image data
            if "data:image" in response_content or _looks_like_base64(response_content):
                # Extract and save base64 image
                img_data = _extract_base64(response_content)
                if img_data:
                    img_path = output_dir / f"nanobana_{timestamp}.png"
                    with open(img_path, "wb") as f:
                        f.write(base64.b64decode(img_data))
                    context.image_paths.append(str(img_path))
                    result_text = f"Image saved to: {img_path}\nPrompt used: {optimized_prompt}"
                else:
                    result_text = f"Image generation response:\n{response_content}\nPrompt: {optimized_prompt}"
            else:
                # Save the text response with the prompt info
                txt_path = output_dir / f"nanobana_{timestamp}.md"
                txt_path.write_text(
                    f"# Image Generation\n\n**Prompt:** {optimized_prompt}\n\n**Response:**\n{response_content}",
                    encoding="utf-8",
                )
                result_text = f"Response saved to: {txt_path}\nPrompt: {optimized_prompt}\n\nResponse:\n{response_content}"

        except Exception as e:
            result_text = f"Image generation failed: {e}\nOptimized prompt was: {optimized_prompt}"

        context.agent_log.append(AgentAction(
            agent_name=self.name,
            action="generate_image",
            model=image_model,
            input_summary=instruction[:200],
            output_summary=result_text[:200],
        ))

        return AgentResult(
            agent_name=self.name,
            content=result_text,
            model_used=image_model,
            metadata={"prompt": optimized_prompt},
        )


def _looks_like_base64(text: str) -> bool:
    """Heuristic check if text looks like base64 image data."""
    clean = text.strip()
    if len(clean) > 1000 and all(c in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=\n\r" for c in clean[:200]):
        return True
    return False


def _extract_base64(text: str) -> str | None:
    """Extract base64 image data from text."""
    if "data:image" in text:
        try:
            return text.split("base64,")[1].split('"')[0].strip()
        except IndexError:
            pass
    clean = text.strip()
    if _looks_like_base64(clean):
        return clean.replace("\n", "").replace("\r", "")
    return None
