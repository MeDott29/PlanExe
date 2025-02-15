"""
Clean up the raw json pitch.

PROMPT> python -m src.pitch.cleanup_pitch
"""
import os
import json
import time
import logging
from math import ceil
from typing import List, Optional
from uuid import uuid4
from dataclasses import dataclass
from pydantic import BaseModel, Field
from llama_index.core.llms.llm import LLM
from llama_index.core.llms import ChatMessage, MessageRole
from src.format_json_for_use_in_query import format_json_for_use_in_query

logger = logging.getLogger(__name__)

class OutputDocument(BaseModel):
    draft_markdown: str = Field(
        description="Markdown format."
    )
    final_markdown: str = Field(
        description="Markdown format."
    )

SYSTEM_PROMPT = """
You are a content formatter. Transform a JSON object containing project pitch sections into a compelling Markdown document.

# Instructions

1.  **Input:** JSON with section titles as keys and content as values.

2.  **Draft Markdown:** Iterate through all sections in the JSON object and perform the following steps:
    - Convert suitable text into markdown with bulleted lists.
    - Rewrite sentences to be more impactful and persuasive.
    - You are encouraged to move sentences around to improve the flow of the text.

3.  **Draft Markdown Restrictions:**
    - Use ONLY the provided text. Do not add external information (website addresses, contact details, dates, etc.)
    - Do not remove any sections or section text unless it is irrelevant.
    - The reformatted pitch must cover the same topics as the original JSON object.
    - Use newlines before and after headings.

4. **Tone:**
    - For short, everyday tasks: Use an informal, energetic tone, fewer paragraphs, shorter bullet points.
	- For big, strategic projects: Adopt a formal, detailed style, multiple sections, more thorough risk/benefit analysis.

5.  **Final Markdown:**
    - Take the draft markdown and refine it further.
    - Bold important keywords or phrases, like **very important words**.
    - Repair invalid markdown syntax.
    - Ensure the final markdown is well-structured.

6.  **Final Markdown Restrictions:**
    - Markdown headings: Use `# Top Level` for the document title. Use `## Second Level` for section titles. Do NOT use more than two levels of headings.
    - Don't bold headings or subheadings, since they are already formatted.

# Example of markdown formatting

```markdown
# Document title

## Section Title

Paragraph with text. Use bullet points for lists.
- I'm a bullet point
- Another bullet point
- Yet another bullet point

## Another Section Title

etc.

```
"""

@dataclass
class CleanupPitch:
    system_prompt: Optional[str]
    user_prompt: str
    response: dict
    metadata: dict

    @classmethod
    def execute(cls, llm: LLM, user_prompt: str) -> 'CleanupPitch':
        """
        Invoke LLM with a json document that is the raw pitch.
        """
        if not isinstance(llm, LLM):
            raise ValueError("Invalid LLM instance.")
        if not isinstance(user_prompt, str):
            raise ValueError("Invalid query.")


        system_prompt = SYSTEM_PROMPT.strip()
        chat_message_list = [
            ChatMessage(
                role=MessageRole.SYSTEM,
                content=system_prompt,
            ),
            ChatMessage(
                role=MessageRole.USER,
                content=user_prompt,
            )
        ]
        
        logger.debug(f"User Prompt:\n{user_prompt}")

        sllm = llm.as_structured_llm(OutputDocument)

        logger.debug("Starting LLM chat interaction.")
        start_time = time.perf_counter()
        chat_response = sllm.chat(chat_message_list)
        end_time = time.perf_counter()
        duration = int(ceil(end_time - start_time))
        response_byte_count = len(chat_response.message.content.encode('utf-8'))
        logger.info(f"LLM chat interaction completed in {duration} seconds. Response byte count: {response_byte_count}")

        metadata = dict(llm.metadata)
        metadata["llm_classname"] = llm.class_name()
        metadata["duration"] = duration
        metadata["response_byte_count"] = response_byte_count

        try:
            json_response = json.loads(chat_response.message.content)
        except json.JSONDecodeError as e:
            logger.error("Failed to parse LLM response as JSON.", exc_info=True)
            raise ValueError("Invalid JSON response from LLM.") from e

        result = CleanupPitch(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response=json_response,
            metadata=metadata,
        )
        logger.debug("CleanupPitch instance created successfully.")
        return result    

    def to_dict(self, include_metadata=True, include_system_prompt=True, include_user_prompt=True) -> dict:
        d = self.response.copy()
        if include_metadata:
            d['metadata'] = self.metadata
        if include_system_prompt:
            d['system_prompt'] = self.system_prompt
        if include_user_prompt:
            d['user_prompt'] = self.user_prompt
        return d

    def save_raw(self, file_path: str) -> None:
        with open(file_path, 'w') as f:
            f.write(json.dumps(self.to_dict(), indent=2))

if __name__ == "__main__":
    from src.llm_factory import get_llm

    basepath = os.path.join(os.path.dirname(__file__), 'test_data')

    def load_json(relative_path: str) -> dict:
        path = os.path.join(basepath, relative_path)
        print(f"loading file: {path}")
        with open(path, 'r', encoding='utf-8') as f:
            the_json = json.load(f)
        return the_json

    pitch_json = load_json('lunar_base-pitch.json')

    model_name = "ollama-llama3.1"
    # model_name = "ollama-qwen2.5-coder"
    llm = get_llm(model_name)

    query = format_json_for_use_in_query(pitch_json)
    print(f"Query: {query}")
    result = CleanupPitch.execute(llm, query)

    print("\nResponse:")
    json_response = result.to_dict(include_system_prompt=False, include_user_prompt=False)
    print(json.dumps(json_response, indent=2))

    print(f"\n\nMarkdown:\n{result.response['final_markdown']}")
