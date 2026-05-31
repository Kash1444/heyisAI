# app/services/rag_service.py

import logging
import google.generativeai as genai
from app.core.config import settings
from app.services.retrieval_service import retrieval_service, RetrievedChunk

logger = logging.getLogger(__name__)

# Configure Gemini once at module level
genai.configure(api_key=settings.gemini_api_key)


class RAGService:
    """
    Retrieval-Augmented Generation pipeline.

    Connects retrieval → generation into one cohesive flow.

    The name says it all:
    - Retrieval: find relevant email chunks
    - Augmented: add those chunks to the prompt as context
    - Generation: Gemini generates a grounded answer

    This service is the brain of your AI assistant.
    """

    def __init__(self):
        self.model = genai.GenerativeModel(settings.gemini_model)

    def answer(
        self,
        question: str,
        n_chunks: int = 5,
    ) -> dict:
        """
        Full RAG pipeline: question → retrieved context → answer.

        Returns a dict with:
        - answer: Gemini's response
        - sources: which emails were used
        - retrieved_count: how many chunks were found
        - has_context: whether we had relevant emails
        """
        logger.info(f"RAG pipeline started for: '{question}'")

        # ── Step 1: Retrieve ───────────────────────────────────────────────
        chunks = retrieval_service.retrieve(
            question=question,
            n_results=n_chunks,
        )

        # Deduplicate so we get diverse email sources
        chunks = retrieval_service.deduplicate_by_email(chunks)

        # ── Step 2: Handle no results ──────────────────────────────────────
        # This is where most RAG systems fail — they hallucinate when
        # they have no context. We handle it explicitly.
        if not chunks:
            return self._no_context_response(question)

        # ── Step 3: Build the prompt ───────────────────────────────────────
        prompt = self._build_prompt(question, chunks)

        # ── Step 4: Generate ───────────────────────────────────────────────
        logger.info(
            f"Sending to Gemini with {len(chunks)} context  chunks..."
        )

        try:
            response = self.model.generate_content(prompt)
            answer_text = response.text

        except Exception as e:
            logger.error(f"Gemini generation failed: {e}")
            return {
                "answer": "I encountered an error generating the answer. Please try again.",
                "sources": [],
                "retrieved_count": len(chunks),
                "has_context": True,
                "error": str(e),
            }

        # ── Step 5: Build source references ───────────────────────────────
        sources = self._format_sources(chunks)

        logger.info("RAG pipeline complete")

        return {
            "answer": answer_text,
            "sources": sources,
            "retrieved_count": len(chunks),
            "has_context": True,
        }

    def _build_prompt(
        self,
        question: str,
        chunks: list[RetrievedChunk]
    ) -> str:
        """
        Build the RAG prompt that Gemini will receive.

        Prompt engineering is a real engineering skill.
        The structure here follows these principles:

        1. Role: tell the model what it is
        2. Context: provide the retrieved emails
        3. Instructions: tell it exactly how to behave
        4. Question: the actual user question
        5. Constraints: what NOT to do (hallucinate)

        The order matters. Context before question lets the model
        'load' the information before being asked about it.
        """
        # Build the context block from retrieved chunks
        context_parts = []

        for i, chunk in enumerate(chunks):
            context_parts.append(
                f"--- Email {i+1} ---\n"
                f"Subject : {chunk.subject}\n"
                f"From    : {chunk.sender}\n"
                f"Date    : {chunk.date}\n"
                f"Content : {chunk.text}\n"
            )

        context_block = "\n".join(context_parts)

        #Here is where the mag'ic happens (idha improve panlaama nu paaru in future)
        prompt = f"""You are a personal AI email assistant. 
Your job is to help the user find information from their emails.

You have access to the following relevant emails retrieved from the user's Gmail:

{context_block}

Instructions:
- Answer the user's question based ONLY on the emails provided above
- Be specific — mention email subjects, dates, and senders when relevant  
- If the emails don't fully answer the question, say what you found and what's missing
- Do NOT make up information that isn't in the emails
- If you're unsure, ask a clarifying question
- Keep your answer concise and helpful
- Format dates and names clearly

User Question: {question}

Answer:"""

        return prompt

    def _no_context_response(self, question: str) -> dict:
        """
        Handle the case where no relevant emails were found.

        Instead of returning an empty response, we ask Gemini
        to generate a helpful clarification question.
        This is the 'clarification questioning system' from your requirements.
        A good AI assistant never just says 'I don't know' — it asks
        a follow-up that helps the user refine their search.
        """
        logger.info("No relevant chunks found. Generating clarification.")

        clarification_prompt = f"""You are a personal AI email assistant.
        
The user asked: "{question}"

You searched their Gmail but couldn't find relevant emails.

Generate a helpful, specific clarification question to help narrow the search.
For example, ask about:
- Approximate time period (which month/year?)
- Sender (which company or person?)
- Specific keywords they might remember

Keep it to one short, friendly question.
Do not say you couldn't find anything — just ask the clarification."""

        try:
            response = self.model.generate_content(clarification_prompt)
            clarification = response.text
        except Exception:
            clarification = (
                "I couldn't find relevant emails. "
                "Could you give me more details — "
                "like the approximate date or who sent it?"
            )

        return {
            "answer": clarification,
            "sources": [],
            "retrieved_count": 0,
            "has_context": False,
        }

    def _format_sources(
        self,
        chunks: list[RetrievedChunk]
    ) -> list[dict]:
        """
        Format source references to return alongside the answer.

        This lets the frontend show 'Based on these emails:'
        with clickable references. Transparency about sources
        is critical in any RAG system — users need to verify answers.
        """
        return [
            {
                "email_id": chunk.email_id,
                "subject": chunk.subject,
                "sender": chunk.sender,
                "date": chunk.date,
                "relevance_score": chunk.similarity_score,
            }
            for chunk in chunks
        ]


# Singleton
rag_service = RAGService()