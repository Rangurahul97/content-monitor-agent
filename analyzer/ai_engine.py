"""AI content analysis engine powered by Google's Gemini API.

Provides structured analysis of social media content including summaries,
topic extraction, sentiment analysis, and importance scoring.
"""

import json
import re
import time
from typing import Any

from google import genai

from utils.logger import get_logger

logger = get_logger(__name__)


class ContentAnalyzer:
    """Analyzes content from various platforms using Google's Gemini API.

    Produces structured analysis including summaries, key topics,
    takeaways, categorization, importance scoring, and sentiment.

    Attributes:
        client: The Google GenAI client instance.
        model: The Gemini model name to use for generation.
        temperature: Sampling temperature for generation (lower = more deterministic).
    """

    # Minimum delay (seconds) between consecutive API calls for rate limiting.
    _RATE_LIMIT_SECONDS: float = 5.0

    _FALLBACK_ANALYSIS: dict[str, Any] = {
        "summary": "",
        "key_topics": [],
        "key_takeaways": [],
        "content_category": "unknown",
        "importance_score": 5,
        "sentiment": "neutral",
    }

    def __init__(
        self,
        api_key: str,
        model: str = "gemini-2.5-flash",
        temperature: float = 0.3,
    ) -> None:
        """Initialize the content analyzer.

        Args:
            api_key: Google API key for Gemini access.
            model: Gemini model identifier. Defaults to ``gemini-2.5-flash``.
            temperature: Sampling temperature (0.0–1.0). Lower values yield
                more deterministic outputs. Defaults to 0.3.
        """
        self.client: genai.Client = genai.Client(api_key=api_key)
        self.model: str = model
        self.temperature: float = temperature
        self._last_call_time: float = 0.0
        logger.info(
            "ContentAnalyzer initialized with model=%s, temperature=%s",
            model,
            temperature,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze(self, content: dict[str, Any]) -> dict[str, Any]:
        """Analyze a piece of content and return structured insights.

        Args:
            content: A dictionary describing the content to analyze.
                Expected keys:
                    - ``platform`` (str): e.g. "youtube", "instagram", "twitter"
                    - ``content_type`` (str): e.g. "video", "post", "reel", "tweet"
                    - ``title`` (str): Title or headline.
                    - ``description`` (str): Description, caption, or tweet text.
                    - ``url`` (str): Link to the original content.
                    - ``transcript`` (str, optional): Full transcript (YouTube).

        Returns:
            A dictionary with the following keys:
                - ``summary`` (str)
                - ``key_topics`` (list[str])
                - ``key_takeaways`` (list[str])
                - ``content_category`` (str)
                - ``importance_score`` (int, 1–10)
                - ``sentiment`` (str)
        """
        prompt = self._build_prompt(content)

        # Rate-limit: ensure at least _RATE_LIMIT_SECONDS between calls.
        self._enforce_rate_limit()

        try:
            logger.debug("Sending analysis request to Gemini (%s)", self.model)
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=genai.types.GenerateContentConfig(
                    temperature=self.temperature,
                ),
            )
            self._last_call_time = time.monotonic()

            raw_text: str = response.text
            logger.debug("Received response (%d chars)", len(raw_text))
            return self._parse_response(raw_text)

        except Exception:
            logger.exception(
                "Gemini API call failed for content: %s",
                content.get("title", "<unknown>"),
            )
            fallback = dict(self._FALLBACK_ANALYSIS)
            fallback["summary"] = (
                f"Analysis failed for: {content.get('title', 'Unknown content')}"
            )
            return fallback

    # ------------------------------------------------------------------
    # Prompt construction
    # ------------------------------------------------------------------

    def _build_prompt(self, content: dict[str, Any]) -> str:
        """Build a platform-aware analysis prompt.

        The prompt varies based on the platform and whether supplementary
        data (e.g. a transcript) is available.

        Args:
            content: Content dictionary (see :meth:`analyze` for schema).

        Returns:
            The fully-rendered prompt string.
        """
        platform: str = content.get("platform", "unknown").lower()
        content_type: str = content.get("content_type", "content").lower()
        title: str = content.get("title", "Untitled")
        description: str = content.get("description", "No description provided.")
        transcript: str | None = content.get("transcript")

        # --- platform-specific context guidance ---
        if platform == "youtube":
            if transcript:
                context_instruction = (
                    "A full transcript is provided. Perform a deep analysis of "
                    "the spoken content, identifying the main arguments, "
                    "supporting evidence, and conclusions drawn by the creator."
                )
                transcript_section = f"\nTranscript:\n{transcript}\n"
            else:
                context_instruction = (
                    "No transcript is available. Analyze the content based on "
                    "the title and description. Infer likely topics and "
                    "takeaways from the metadata."
                )
                transcript_section = ""
        elif platform == "instagram":
            context_instruction = (
                "Analyze the caption and any contextual cues about the media. "
                "Consider visual storytelling elements, hashtag strategy, and "
                "audience engagement signals."
            )
            transcript_section = ""
        elif platform == "twitter":
            context_instruction = (
                "Analyze the tweet text and any thread context. Consider "
                "brevity, rhetorical devices, hashtag usage, and the "
                "conversational context."
            )
            transcript_section = ""
        else:
            context_instruction = (
                "Analyze the content based on all available information."
            )
            transcript_section = ""

        prompt = (
            f"You are a content analysis AI. Analyze the following "
            f"{platform} {content_type} and provide a structured analysis.\n\n"
            f"{context_instruction}\n\n"
            f"Title: {title}\n"
            f"Description/Caption: {description}\n"
            f"{transcript_section}\n"
            "Provide your analysis in the following JSON format:\n"
            "{\n"
            '  "summary": "A detailed summary of the content. CRITICAL INSTRUCTION: If any tools, apps, websites, or software are mentioned, you MUST explicitly name them in this summary and briefly explain how they work or how the creator uses them.",\n'
            '  "key_topics": ["topic1", "topic2", "topic3"],\n'
            '  "key_takeaways": ["takeaway1", "takeaway2", "takeaway3"],\n'
            '  "content_category": "tutorial|announcement|opinion|news|'
            'entertainment|educational|promotional|personal",\n'
            '  "importance_score": 7,\n'
            '  "sentiment": "positive|negative|neutral|mixed"\n'
            "}\n\n"
            "IMPORTANT: Return ONLY valid JSON, no markdown formatting, "
            "no code blocks."
        )
        return prompt

    # ------------------------------------------------------------------
    # Response parsing
    # ------------------------------------------------------------------

    def _parse_response(self, response_text: str) -> dict[str, Any]:
        """Parse a Gemini response into a structured analysis dict.

        Attempts direct JSON parsing first, then falls back to extracting
        JSON from markdown code blocks, and finally returns a fallback
        dict containing the raw text.

        Args:
            response_text: Raw text returned by the Gemini model.

        Returns:
            Parsed analysis dictionary.
        """
        # 1. Try direct JSON parsing.
        try:
            result = json.loads(response_text)
            logger.debug("Parsed response via direct JSON.")
            return self._validate_analysis(result)
        except json.JSONDecodeError:
            pass

        # 2. Try extracting JSON from markdown code fences.
        match = re.search(
            r"```(?:json)?\s*\n?(.*?)\n?\s*```",
            response_text,
            re.DOTALL,
        )
        if match:
            try:
                result = json.loads(match.group(1))
                logger.debug("Parsed response from markdown code block.")
                return self._validate_analysis(result)
            except json.JSONDecodeError:
                pass

        # 3. Fallback: return raw text as the summary.
        logger.warning(
            "Could not parse JSON from Gemini response; using fallback."
        )
        fallback = dict(self._FALLBACK_ANALYSIS)
        fallback["summary"] = response_text.strip()
        return fallback

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_analysis(data: dict[str, Any]) -> dict[str, Any]:
        """Ensure all expected keys are present, filling defaults where needed.

        Args:
            data: Parsed JSON dictionary from the model.

        Returns:
            A dictionary guaranteed to contain all required analysis keys.
        """
        defaults: dict[str, Any] = {
            "summary": "",
            "key_topics": [],
            "key_takeaways": [],
            "content_category": "unknown",
            "importance_score": 5,
            "sentiment": "neutral",
        }
        for key, default_value in defaults.items():
            if key not in data:
                data[key] = default_value

        # Clamp importance score to 1–10.
        try:
            score = int(data["importance_score"])
            data["importance_score"] = max(1, min(10, score))
        except (ValueError, TypeError):
            data["importance_score"] = 5

        return data

    def _enforce_rate_limit(self) -> None:
        """Sleep if necessary to respect the per-call rate limit."""
        elapsed = time.monotonic() - self._last_call_time
        if elapsed < self._RATE_LIMIT_SECONDS:
            wait = self._RATE_LIMIT_SECONDS - elapsed
            logger.debug("Rate-limiting: sleeping %.2f s", wait)
            time.sleep(wait)
