import re
import os
from typing import Tuple, Optional, Dict, Any, List, Set

# Attempt to load spacy with resilient fallback
try:
    import spacy
    try:
        _nlp = spacy.load("en_core_web_sm")
    except Exception:
        _nlp = spacy.blank("en")
except ImportError:
    _nlp = None

MAX_USER_MESSAGE_LENGTH = 1000

# Expanded semantic taxonomy of destructive and mutating actions
MUTATION_ACTION_LEMMAS: Set[str] = {
    "delete", "remove", "erase", "purge", "drop", "truncate", "alter",
    "modify", "edit", "insert", "update", "obliterate", "annihilate",
    "wipe", "flush", "expunge", "vanish", "overwrite", "zero",
    "discard", "clear", "strip", "destroy", "eliminate", "override",
    "rewrite", "prune", "expel", "reset"
}

# Semantic entities representing data structures or business records
DATA_TARGET_LEMMAS: Set[str] = {
    "table", "row", "column", "record", "database", "schema", "entry",
    "data", "dataset", "customer", "order", "item", "payment",
    "shipment", "review", "supplier", "field", "cell", "value",
    "catalog", "file"
}

# Prompt injection and jailbreak semantic patterns
PROMPT_INJECTION_PATTERNS = [
    r"\b(?:ignore|disregard|forget|override)\s+(?:all\s+)?(?:previous|prior|above|system|developer)\s+(?:instructions|rules|prompts|guidelines)\b",
    r"\b(?:system\s+override|admin\s+override|developer\s+override)\b",
    r"\b(?:you\s+are\s+now|enter|switch\s+to)\s+(?:in\s+)?(?:developer|dan|unrestricted|jailbreak|god|root)\s+mode\b",
    r"\bact\s+as\s+(?:an?\s+)?(?:unrestricted|unfiltered|jailbroken|evil|dan|autonomous)\s+(?:ai|assistant|model|agent)\b",
    r"\b(?:reveal|repeat|print|output|display|show|leak)\s+(?:your\s+)?(?:system\s+prompt|developer\s+instructions|initial\s+prompt|hidden\s+rules)\b",
    r"\b(?:disable|bypass|circumvent)\s+(?:all\s+)?(?:guardrails|safety|filters|security|restrictions)\b",
]
PROMPT_INJECTION_REGEX = re.compile("|".join(PROMPT_INJECTION_PATTERNS), re.IGNORECASE)

# Fast-path regex for obvious mutation phrases
FAST_MUTATION_REGEX = re.compile(
    r"""(?xi)
    \b(delete|drop|truncate|alter|update|remove|insert|edit|modify)\s+(?:table|database|schema|into|from|set|\d+|[a-zA-Z_]\w*)
    |\b(wipe\s+out|clear\s+out|zero\s+out|get\s+rid\s+of)\b
    |\b(obliterate|annihilate|expunge|purge|vanish)\b.*\b(table|row|record|customer|order|data|database)\b
    """
)

PROMPT_INJECTION_REFUSAL_MESSAGE = (
    "I apologize, but this system operates strictly as an analytical data assistant. "
    "Instructions attempting to alter system prompts, override operational policies, or access internal configurations are not permitted. "
    "Please submit a data analysis question related to your registered datasets."
)

PATH_STRIP_REGEX = re.compile(r"""(?:/|[a-zA-Z]:\\)[\w./\\-]+""")
HEX_STRIP_REGEX = re.compile(r"""0x[0-9a-fA-F]+""")


class NLPGuardrails:
    """
    Senior Security AI Guardrails combining spaCy natural language processing,
    dependency parsing, semantic taxonomy matching, and prompt injection defense.
    """

    @classmethod
    def get_nlp(cls):
        global _nlp
        if _nlp is None:
            try:
                import spacy
                try:
                    _nlp = spacy.load("en_core_web_sm")
                except Exception:
                    _nlp = spacy.blank("en")
            except ImportError:
                _nlp = None
        return _nlp

    @classmethod
    def validate_message_length(cls, message: str) -> str:
        """
        Guards against Denial of Service via buffer flooding or ReDoS (V5).
        """
        if message and len(message) > MAX_USER_MESSAGE_LENGTH:
            raise ValueError(
                f"Query exceeds maximum permitted length of {MAX_USER_MESSAGE_LENGTH} characters. "
                "Please submit a concise analytical question."
            )
        return message

    @classmethod
    def detect_prompt_injection(cls, message: str) -> Tuple[bool, Optional[str]]:
        """
        Detects prompt injection, jailbreak, and system prompt override attempts (V3).
        """
        if not message:
            return False, None

        cleaned = message.strip()

        # 1. Regex-based pattern matching
        if PROMPT_INJECTION_REGEX.search(cleaned):
            return True, PROMPT_INJECTION_REFUSAL_MESSAGE

        # 2. Semantic token analysis with spaCy if available
        nlp = cls.get_nlp()
        if nlp is not None:
            try:
                doc = nlp(cleaned.lower()[:300])
                words = {t.lemma_ for t in doc}

                # Meta-command intent: ignore/override + instruction/prompt/rule
                has_override_verb = bool(words & {"ignore", "override", "bypass", "disregard", "forget", "reveal"})
                has_meta_noun = bool(words & {"instruction", "prompt", "rule", "guideline", "guardrail", "jailbreak"})
                if has_override_verb and has_meta_noun:
                    return True, PROMPT_INJECTION_REFUSAL_MESSAGE
            except Exception:
                pass

        return False, None

    @classmethod
    def analyze_mutation_intent(cls, message: str) -> bool:
        """
        Detects if user natural language message is attempting data mutation or deletion (V1),
        while safely allowing legitimate analytical questions in passive/interrogative voice (V2).
        """
        if not message:
            return False

        cls.validate_message_length(message)
        cleaned = message.strip()
        lower = cleaned.lower()

        # 1. Check for explicit negation: e.g. "do not delete anything"
        if re.search(r"\b(?:do\s+not|don't|never|cannot)\s+(?:delete|drop|modify|alter|remove)\b", lower):
            # Explicitly instructed NOT to delete -> not an attack
            return False

        # 2. Fast-path regex check
        is_fast_hit = bool(FAST_MUTATION_REGEX.search(cleaned))

        # 3. spaCy Semantic & Syntactic Dependency Analysis
        nlp = cls.get_nlp()
        if nlp is not None:
            try:
                doc = nlp(cleaned)

                # Check for interrogative cues indicating analytical questions
                # e.g., "Which orders were deleted?", "What records were removed?", "How many deleted accounts?"
                is_interrogative = any(
                    t.lemma_ in {"which", "what", "how", "who", "when", "where", "why"}
                    or t.text.lower() in {"show", "list", "display", "count", "find", "get", "view", "report"}
                    for t in doc[:4]
                )

                found_mutation_lemma = False
                has_mutation_action = False

                for token in doc:
                    lemma = token.lemma_.lower()

                    # Check if token is in mutation action taxonomy
                    if lemma in MUTATION_ACTION_LEMMAS:
                        found_mutation_lemma = True

                        # Voice & Grammatical role check:
                        # If verb is passive participle or adjectival modifier in an analytical question:
                        # e.g. "Which orders [were deleted] (auxpass)?" or "[deleted] (amod) orders"
                        is_passive = (
                            token.dep_ in {"auxpass", "nsubjpass"}
                            or any(child.dep_ == "auxpass" for child in token.children)
                        )
                        is_adjectival = token.dep_ in {"amod", "acl"} or token.pos_ == "ADJ"

                        if is_interrogative and (is_passive or is_adjectival):
                            # It is an inquiry about past status, NOT an imperative mutation command!
                            continue

                        # Check if token has a direct negative child ("do not delete")
                        if any(child.dep_ == "neg" for child in token.children):
                            continue

                        # If imperative ROOT, compound at start, or governing a data target
                        if (
                            token.dep_ in {"ROOT", "xcomp", "ccomp", "compound", "dep"}
                            or token.pos_ in {"VERB", "NOUN", "PROPN"}
                            or token.i == 0
                        ):
                            has_mutation_action = True
                            break

                if found_mutation_lemma and has_mutation_action:
                    # Verify target context (mentions database entity, target ID, or all/table)
                    has_data_target = any(
                        t.lemma_.lower() in DATA_TARGET_LEMMAS
                        or t.pos_ in {"NUM", "PROPN"}
                        or t.text.lower() in {"all", "everything", "from", "into"}
                        for t in doc
                    )
                    if has_data_target:
                        return True

                # If spaCy did not confirm an active mutation command, but fast regex hit,
                # evaluate if fast hit was an interrogative false positive
                if is_fast_hit and not is_interrogative:
                    return True
                elif is_fast_hit and is_interrogative:
                    # Analytical question containing target word
                    return False

                return False
            except Exception:
                # Fallback to regex if spaCy fails
                return is_fast_hit

        return is_fast_hit

    @classmethod
    def extract_semantic_entities(cls, message: str) -> Dict[str, List[str]]:
        """
        Extracts semantic entities to enrich SQL planning, temporal anchoring,
        and grounding evaluation (V8).
        """
        entities: Dict[str, List[str]] = {
            "dates": [],
            "money": [],
            "percentages": [],
            "quantities": [],
            "locations": [],
        }
        if not message:
            return entities

        nlp = cls.get_nlp()
        if nlp is not None:
            try:
                doc = nlp(message)
                for ent in doc.ents:
                    if ent.label_ in {"DATE", "TIME"}:
                        entities["dates"].append(ent.text)
                    elif ent.label_ == "MONEY":
                        entities["money"].append(ent.text)
                    elif ent.label_ == "PERCENT":
                        entities["percentages"].append(ent.text)
                    elif ent.label_ in {"QUANTITY", "CARDINAL"}:
                        entities["quantities"].append(ent.text)
                    elif ent.label_ in {"GPE", "LOC"}:
                        entities["locations"].append(ent.text)
            except Exception:
                pass

        return entities

    @classmethod
    def sanitize_database_error(cls, error_msg: str) -> str:
        """
        Strips internal server paths, memory hex offsets, and low-level stack details (V7).
        """
        if not error_msg:
            return "An internal database error occurred while executing the query."

        # Strip file paths
        sanitized = PATH_STRIP_REGEX.sub("[PATH]", error_msg)
        # Strip hex memory addresses
        sanitized = HEX_STRIP_REGEX.sub("[ADDR]", sanitized)

        # Simplify common DuckDB syntax messages to business-friendly messages
        if "Binder Error" in sanitized:
            return "The analytical query referenced a column or table that does not exist in the active schema."
        if "Parser Error" in sanitized:
            return "The generated analytical SQL statement contained an unsupported syntax expression."
        if "Out of Memory" in sanitized:
            return "The requested analytical aggregation exceeded memory limits. Please refine your query filters."

        return sanitized
