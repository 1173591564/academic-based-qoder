"""
Scholar Studio — Paper Classification & Tagging

Multi-level tag system:
  Level 1: Domain (NLP, CV, RL, ML, Systems, Safety, Audio, Multimodal)
  Level 2: Sub-direction (Language Modeling, Object Detection, Policy Optimization, etc.)
  Level 3: Specific method tags (Transformer, ResNet, DQN, etc.)

Uses rule engine + keyword matching + venue inference.
Output: paper JSON `tags` field.
"""
import json
import re
import ast
from pathlib import Path
from typing import Optional
from collections import Counter

from . import config


# ===================================================================
# Taxonomy definition
# ===================================================================

DOMAINS = {
    "NLP": {
        "Language Modeling": [
            "language model", "lm", "text generation", "next token", "autoregressive",
            "gpt", "bert", "t5", "decoder", "encoder-decoder", "seq2seq",
            "language modeling", "perplexity",
        ],
        "Machine Translation": [
            "machine translation", "translation", "bleu", "multilingual", "parallel corpus",
        ],
        "Information Extraction": [
            "named entity", "ner", "relation extraction", "information extraction",
            "slot filling", "event extraction",
        ],
        "Summarization": [
            "summarization", "summary", "rouge", "abstractive", "extractive",
        ],
        "Question Answering": [
            "question answering", "qa", "reading comprehension", "squad",
        ],
        "Sentiment Analysis": [
            "sentiment", "emotion", "opinion mining", "text classification",
        ],
    },
    "CV": {
        "Image Classification": [
            "image classification", "imagenet", "visual recognition", "resnet", "vit",
        ],
        "Object Detection": [
            "object detection", "yolo", "bounding box", "r-cnn", "detection",
        ],
        "Image Segmentation": [
            "segmentation", "semantic segmentation", "instance segmentation",
            "segment anything", "panoptic",
        ],
        "Image Generation": [
            "image generation", "image synthesis", "style transfer", "inpainting",
            "text-to-image", "image editing",
        ],
        "Video Understanding": [
            "video", "temporal", "action recognition", "video understanding",
        ],
        "3D Vision": [
            "3d", "point cloud", "depth estimation", "radiance field", "nerf",
            "gaussian splatting", "novel view", "reconstruction",
        ],
    },
    "RL": {
        "Policy Optimization": [
            "policy gradient", "ppo", "a3c", "sac", "td3", "actor-critic", "reinforce",
        ],
        "Model-Based RL": [
            "world model", "model-based", "dreamer", "muzero", "planning",
        ],
        "Multi-Agent RL": [
            "multi-agent", "cooperative", "competitive", "marl",
        ],
    },
    "ML": {
        "Optimization": [
            "optimizer", "sgd", "adam", "learning rate", "convergence",
            "gradient descent", "optimization",
        ],
        "Generalization": [
            "generalization", "overfitting", "regularization", "double descent",
            "grokking", "scaling law",
        ],
        "Meta-Learning": [
            "meta-learning", "few-shot", "maml", "prototypical", "matching network",
        ],
        "Graph Learning": [
            "graph neural", "gcn", "gat", "graphsage", "message passing",
            "graph representation",
        ],
        "Efficiency": [
            "pruning", "quantization", "distillation", "compression", "efficient",
            "lora", "moe", "sparse",
        ],
    },
    "Safety": {
        "Alignment": [
            "alignment", "rlhf", "dpo", "preference", "constitutional",
            "human feedback", "reward model", "instruction tuning",
        ],
        "Robustness": [
            "adversarial", "robustness", "attack", "defense", "perturbation",
            "certified",
        ],
        "Red Teaming": [
            "red team", "jailbreak", "safety", "guardrail", "toxic",
            "harmful", "watermark",
        ],
    },
    "Multimodal": {
        "Vision-Language": [
            "vision-language", "multimodal", "clip", "vlm", "image-text",
            "visual question", "vqa", "grounding",
        ],
        "Audio": [
            "speech", "audio", "whisper", "wav2vec", "tts", "voice",
            "sound", "acoustic",
        ],
    },
    "Systems": {
        "Training Systems": [
            "distributed training", "parallel", "pipeline parallel", "tensor parallel",
            "deepspeed", "megatron", "fairscale",
        ],
        "Inference Systems": [
            "inference", "serving", "latency", "throughput", "batching",
            "speculative decoding", "kv cache", "flash attention",
        ],
        "Retrieval": [
            "retrieval", "search", "bm25", "dense retrieval", "rag",
            "embedding", "index",
        ],
    },
}

# Venue-based domain hints
VENUE_HINTS = {
    "ACL": "NLP", "EMNLP": "NLP", "NAACL": "NLP", "COLING": "NLP",
    "CVPR": "CV", "ICCV": "CV", "ECCV": "CV",
    "NeurIPS": "ML", "ICML": "ML", "ICLR": "ML", "AAAI": "ML", "IJCAI": "ML",
    "ICRA": "RL", "CoRL": "RL",
    "USENIX": "Safety", "S&P": "Safety",
    "Interspeech": "Multimodal", "ICASSP": "Multimodal",
    "OSDI": "Systems", "SOSP": "Systems", "MLSys": "Systems",
}


# ===================================================================
# Classification logic
# ===================================================================

def classify_paper(data: dict) -> dict:
    """
    Classify a paper into multi-level tags.

    Returns:
        {
            "domains": [str],
            "sub_directions": [str],
            "methods": [str],
            "tags": [str],  # flat list of all tags
        }
    """
    # Build searchable text
    sections = data.get("sections", [])
    if isinstance(sections, str):
        try:
            sections = ast.literal_eval(sections)
        except Exception:
            sections = []

    text_parts = [
        data.get("title", ""),
        data.get("abstract", ""),
    ]
    for s in sections[:5]:
        text_parts.append(s.get("heading", ""))
        content = s.get("content", "")
        if content:
            text_parts.append(content[:500])
    full_text = " ".join(text_parts).lower()

    venue = (data.get("venue") or "").upper()

    # Score each domain and sub-direction
    domain_scores = Counter()
    sub_scores = Counter()
    method_tags = []

    for domain, subdirs in DOMAINS.items():
        for subdir, keywords in subdirs.items():
            hits = sum(1 for kw in keywords if kw in full_text)
            if hits > 0:
                domain_scores[domain] += hits
                sub_scores[f"{domain}/{subdir}"] = hits
                # Extract matching methods
                for kw in keywords:
                    if kw in full_text and len(kw) > 3:
                        method_tags.append(kw)

    # Venue hint boost
    if venue in VENUE_HINTS:
        domain_scores[VENUE_HINTS[venue]] += 5

    # Select top domains (those with score >= 3 or top 2)
    top_domains = [d for d, _ in domain_scores.most_common(2) if domain_scores[d] >= 3]
    if not top_domains and domain_scores:
        top_domains = [domain_scores.most_common(1)[0][0]]

    # Select sub-directions (those in selected domains)
    top_subs = [
        s for s, _ in sub_scores.most_common(3)
        if s.split("/")[0] in top_domains
    ]

    # Deduplicate method tags
    seen = set()
    unique_methods = []
    for m in method_tags:
        if m not in seen:
            seen.add(m)
            unique_methods.append(m)

    return {
        "domains": top_domains,
        "sub_directions": top_subs,
        "methods": unique_methods[:10],
        "tags": top_domains + top_subs + unique_methods[:10],
    }


# ===================================================================
# Batch processing
# ===================================================================

def classify_all_papers(parsed_dir: Path = None) -> dict:
    """
    Classify all parsed papers and write tags to JSON.

    Returns statistics.
    """
    if parsed_dir is None:
        parsed_dir = config.PARSED_DIR

    results = {"classified": 0, "failed": 0, "domain_counts": Counter()}

    for json_file in sorted(parsed_dir.glob("*.json")):
        try:
            data = json.loads(json_file.read_text(encoding="utf-8"))
            classification = classify_paper(data)

            # Write tags to paper JSON
            data["tags"] = classification
            json_file.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            results["classified"] += 1
            for d in classification["domains"]:
                results["domain_counts"][d] += 1
        except Exception:
            results["failed"] += 1

    results["domain_counts"] = dict(results["domain_counts"])
    return results


def classify_single_paper(ulid: str) -> Optional[dict]:
    """Classify a single paper and write tags."""
    from . import db as dbmod

    data = dbmod.load_parsed(ulid)
    if data is None:
        return None

    classification = classify_paper(data)
    data["tags"] = classification
    json_file = config.PARSED_DIR / f"{ulid}.json"
    json_file.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return classification


def list_all_tags(parsed_dir: Path = None) -> dict:
    """
    Scan all parsed papers and aggregate tag statistics.

    Returns:
        {domains: Counter, sub_directions: Counter, methods: Counter}
    """
    if parsed_dir is None:
        parsed_dir = config.PARSED_DIR

    domain_counts = Counter()
    sub_counts = Counter()
    method_counts = Counter()

    for json_file in parsed_dir.glob("*.json"):
        try:
            data = json.loads(json_file.read_text(encoding="utf-8"))
            tags = data.get("tags", {})
            for d in tags.get("domains", []):
                domain_counts[d] += 1
            for s in tags.get("sub_directions", []):
                sub_counts[s] += 1
            for m in tags.get("methods", []):
                method_counts[m] += 1
        except Exception:
            pass

    return {
        "domains": dict(domain_counts.most_common()),
        "sub_directions": dict(sub_counts.most_common()),
        "methods": dict(method_counts.most_common(30)),
    }
