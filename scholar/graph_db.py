"""
Scholar Studio — Graph Database Layer (Neo4j)

Handles:
  1. Citation Network: papers → CITES → papers (36003 edges)
  2. Concept Graph:    papers → HAS_CONCEPT → concepts, concepts → RELATED_TO → concepts
  3. Innovation Graph: innovations → REPLACES → innovations (from Lean4)

All three graphs live in the same Neo4j instance, connected via Paper nodes.
"""
import json
import re
from pathlib import Path
from typing import Optional
from collections import Counter

from . import config


# ===================================================================
# Neo4j Connection
# ===================================================================

def _try_import_neo4j():
    try:
        from neo4j import GraphDatabase
        return GraphDatabase
    except ImportError:
        return None


class GraphDB:
    """Neo4j graph database interface."""

    def __init__(self):
        self.GraphDatabase = _try_import_neo4j()
        self._driver = None

    @property
    def available(self) -> bool:
        if self.GraphDatabase is None:
            return False
        try:
            driver = self._connect()
            with driver.session() as session:
                session.run("RETURN 1")
            return True
        except Exception:
            return False

    def _connect(self):
        if self._driver is None:
            self._driver = self.GraphDatabase.driver(
                config.NEO4J_URI,
                auth=(config.NEO4J_USER, config.NEO4J_PASS),
            )
        return self._driver

    def run(self, query: str, **params):
        """Execute a Cypher query and return results."""
        driver = self._connect()
        with driver.session() as session:
            result = session.run(query, **params)
            return [record.data() for record in result]

    def close(self):
        if self._driver:
            self._driver.close()
            self._driver = None


# ===================================================================
# 1. Citation Network Builder
# ===================================================================

def _normalize_title(title: str) -> str:
    """Normalize a title for fuzzy matching."""
    if not title:
        return ""
    title = title.lower()
    title = re.sub(r"[^a-z0-9\s]", "", title)
    return re.sub(r"\s+", " ", title).strip()


def resolve_ref_keys(gdb: GraphDB, parsed_dir: Path = None) -> dict:
    """
    Resolve citation ref_keys (e.g. 'vaswani2017') to actual Paper ULIDs.

    The original build_citation_network creates edges where to_paper.ulid = ref_key,
    but real papers use ULID format (01KT6MT...). This function:
    1. Builds a title -> ULID map from all parsed papers
    2. Matches each ref_key to a paper by normalized title
    3. Re-maps the CITES edge to point to the correct ULID node
    """
    if parsed_dir is None:
        parsed_dir = config.PARSED_DIR

    # Build title -> ULID map
    title_to_ulid = {}
    for json_file in parsed_dir.glob("*.json"):
        data = json.loads(json_file.read_text(encoding="utf-8"))
        title = data.get("title", "")
        if title:
            norm = _normalize_title(title)
            title_to_ulid[norm] = data["paper_id"]

    # Get all unresolved CITES edges
    edges = gdb.run("""
        MATCH (from:Paper)-[c:CITES]->(to:Paper)
        WHERE NOT to.ulid STARTS WITH '01K'
        RETURN from.ulid AS from_ulid, to.ulid AS ref_key, id(c) AS rel_id
        LIMIT 50000
    """)

    resolved = 0
    unresolved = 0
    batch_size = 100
    resolve_batch = []

    for edge in edges:
        ref_key = edge["ref_key"]
        ref_lower = _normalize_title(ref_key.replace("_", " "))

        # Try exact match — exact hits should get the highest score (1.0)
        matched_ulid = title_to_ulid.get(ref_lower)
        best_score = 1.0 if matched_ulid else 0.0

        # Try fuzzy match: only run if no exact match
        if not matched_ulid:
            for norm_title, ulid in title_to_ulid.items():
                if ref_lower in norm_title or norm_title in ref_lower:
                    score = min(len(ref_lower), len(norm_title))
                    if score > best_score:
                        best_score = score
                        matched_ulid = ulid
                # Word overlap
                words_a = set(ref_lower.split())
                words_b = set(norm_title.split())
                if words_a and words_b:
                    overlap = len(words_a & words_b) / max(len(words_a), len(words_b))
                    if overlap > 0.7 and overlap > best_score:
                        best_score = overlap
                        matched_ulid = ulid

        if matched_ulid and best_score > 0.3:
            resolve_batch.append({
                "from_ulid": edge["from_ulid"],
                "ref_key": ref_key,
                "to_ulid": matched_ulid,
            })
            resolved += 1
        else:
            unresolved += 1

    # Re-create resolved edges
    for i in range(0, len(resolve_batch), batch_size):
        batch = resolve_batch[i:i + batch_size]
        gdb.run("""
            UNWIND $batch AS e
            MATCH (from:Paper {ulid: e.from_ulid})
            MATCH (old_to:Paper {ulid: e.ref_key})
            MATCH (from)-[r:CITES]->(old_to)
            DELETE r
            WITH e, from
            MATCH (new_to:Paper {ulid: e.to_ulid})
            MERGE (from)-[:CITES {ref_key: e.ref_key, resolved: true}]->(new_to)
        """, batch=batch)

    # Clean up orphaned ref_key nodes (nodes not starting with 01K and no incoming edges)
    gdb.run("""
        MATCH (p:Paper)
        WHERE NOT p.ulid STARTS WITH '01K'
        AND NOT (p)<-[:CITES]-()
        DETACH DELETE p
    """)

    return {"resolved": resolved, "unresolved": unresolved}


def compute_centrality(gdb: GraphDB) -> dict:
    """
    Compute centrality metrics for all Paper nodes.

    Calculates:
    - in_degree: number of papers citing this paper
    - out_degree: number of papers this paper cites
    - bridge_score: in_degree * out_degree / (in_degree + out_degree)
    """
    gdb.run("""
        MATCH (p:Paper)
        OPTIONAL MATCH (p)<-[:CITES]-(:Paper)
        WITH p, count(*) AS in_deg
        OPTIONAL MATCH (p)-[:CITES]->(:Paper)
        WITH p, in_deg, count(*) AS out_deg
        SET p.in_degree = in_deg,
            p.out_degree = out_deg,
            p.bridge_score = CASE
                WHEN (in_deg + out_deg) > 0
                THEN (in_deg * out_deg * 1.0) / (in_deg + out_deg)
                ELSE 0.0
            END
    """)

    # Get top papers by in-degree
    top_cited = gdb.run("""
        MATCH (p:Paper)
        WHERE p.in_degree > 0
        RETURN p.ulid AS ulid, p.title AS title, p.in_degree AS in_degree
        ORDER BY in_degree DESC LIMIT 10
    """)

    # Get top bridge papers
    top_bridge = gdb.run("""
        MATCH (p:Paper)
        WHERE p.bridge_score > 0
        RETURN p.ulid AS ulid, p.title AS title,
               p.bridge_score AS bridge_score,
               p.in_degree AS in_deg, p.out_degree AS out_deg
        ORDER BY bridge_score DESC LIMIT 10
    """)

    return {"top_cited": top_cited, "top_bridge": top_bridge}


def build_citation_network(gdb: GraphDB, parsed_dir: Path = None):
    """
    Build the citation network in Neo4j from parsed JSON files.

    Creates:
      (:Paper {ulid, title, year, venue}) nodes
      (:Paper)-[:CITES {ref_key}]->(:Paper) edges
    """
    if parsed_dir is None:
        parsed_dir = config.PARSED_DIR

    # Step 1: Create all Paper nodes
    papers = []
    for json_file in parsed_dir.glob("*.json"):
        data = json.loads(json_file.read_text(encoding="utf-8"))
        papers.append({
            "ulid": data["paper_id"],
            "title": data.get("title", ""),
            "year": data.get("year"),
            "venue": data.get("venue", ""),
            "formula_count": len(data.get("formulas", [])),
            "citation_count": len(data.get("citations", [])),
        })

    # Batch create Paper nodes (MERGE to avoid duplicates)
    batch_size = 100
    for i in range(0, len(papers), batch_size):
        batch = papers[i:i + batch_size]
        gdb.run("""
            UNWIND $batch AS p
            MERGE (paper:Paper {ulid: p.ulid})
            SET paper.title = p.title,
                paper.year = p.year,
                paper.venue = p.venue,
                paper.formula_count = p.formula_count,
                paper.citation_count = p.citation_count
        """, batch=batch)

    # Step 2: Create CITES edges
    edges = []
    for json_file in parsed_dir.glob("*.json"):
        data = json.loads(json_file.read_text(encoding="utf-8"))
        from_ulid = data["paper_id"]
        for ref in data.get("citations", []):
            edges.append({"from": from_ulid, "ref": ref})

    for i in range(0, len(edges), batch_size):
        batch = edges[i:i + batch_size]
        gdb.run("""
            UNWIND $batch AS e
            MERGE (from:Paper {ulid: e.from})
            MERGE (to:Paper {ulid: e.ref})
            MERGE (from)-[:CITES {ref_key: e.ref}]->(to)
        """, batch=batch)

    return {"papers": len(papers), "edges": len(edges)}


# ===================================================================
# Citation Network Queries
# ===================================================================

def get_citation_stats(gdb: GraphDB) -> dict:
    """Get citation network statistics."""
    results = {}

    r = gdb.run("MATCH (p:Paper) RETURN count(p) AS count")
    results["total_papers"] = r[0]["count"] if r else 0

    r = gdb.run("MATCH ()-[c:CITES]->() RETURN count(c) AS count")
    results["total_citations"] = r[0]["count"] if r else 0

    # Most cited papers (in-degree)
    top_cited = gdb.run("""
        MATCH (p:Paper)<-[:CITES]-()
        RETURN p.ulid AS ulid, p.title AS title, count(*) AS cited_by
        ORDER BY cited_by DESC LIMIT 20
    """)
    results["most_cited"] = top_cited

    # Papers that cite the most (out-degree)
    top_citers = gdb.run("""
        MATCH (p:Paper)-[:CITES]->()
        RETURN p.ulid AS ulid, p.title AS title, count(*) AS cites_count
        ORDER BY cites_count DESC LIMIT 20
    """)
    results["most_active_citers"] = top_citers

    return results


def get_forward_citations(gdb: GraphDB, paper_ulid: str) -> list:
    """Get papers that this paper cites (forward citations)."""
    return gdb.run("""
        MATCH (p:Paper {ulid: $ulid})-[:CITES]->(cited:Paper)
        RETURN cited.ulid AS ulid, cited.title AS title, cited.year AS year
        ORDER BY cited.year DESC
    """, ulid=paper_ulid)


def get_backward_citations(gdb: GraphDB, paper_ulid: str) -> list:
    """Get papers that cite this paper (backward citations)."""
    return gdb.run("""
        MATCH (citer:Paper)-[:CITES]->(p:Paper {ulid: $ulid})
        RETURN citer.ulid AS ulid, citer.title AS title, citer.year AS year
        ORDER BY citer.year DESC
    """, ulid=paper_ulid)


def get_citation_path(gdb: GraphDB, from_ulid: str, to_ulid: str) -> list:
    """Find the shortest citation path between two papers."""
    return gdb.run("""
        MATCH path = shortestPath(
            (a:Paper {ulid: $from_ulid})-[:CITES*]-(b:Paper {ulid: $to_ulid})
        )
        RETURN [n IN nodes(path) | n.ulid] AS path_nodes,
               [n IN nodes(path) | n.title] AS path_titles
    """, from_ulid=from_ulid, to_ulid=to_ulid)


def get_bridge_papers(gdb: GraphDB, limit: int = 20) -> list:
    """
    Find bridge papers that connect different research communities.
    These are papers with high betweenness centrality.
    Uses a simplified approximation: papers that appear on many
    shortest paths between other papers.
    """
    return gdb.run("""
        MATCH (p:Paper)
        WHERE p.year IS NOT NULL
        OPTIONAL MATCH (p)<-[:CITES]-(citer:Paper)
        OPTIONAL MATCH (p)-[:CITES]->(cited:Paper)
        WITH p, count(DISTINCT citer) AS in_deg, count(DISTINCT cited) AS out_deg
        WHERE in_deg > 0 AND out_deg > 0
        WITH p, in_deg, out_deg,
             (in_deg * out_deg * 1.0) / (in_deg + out_deg) AS bridge_score
        RETURN p.ulid AS ulid, p.title AS title, p.year AS year,
               in_deg, out_deg, bridge_score
        ORDER BY bridge_score DESC LIMIT $limit
    """, limit=limit)


# ===================================================================
# 2. Concept Graph Builder
# ===================================================================

def load_innovations_from_lean(lean_file: Path = None) -> list:
    """
    Dynamically load all 125 innovation nodes from LEAN/AiEvolution/Database.lean.
    Falls back to hardcoded seed data if file not found.
    """
    if lean_file is None:
        lean_file = config.LEAN_DIR / "AiEvolution" / "Database.lean"

    if not lean_file.exists():
        return _FALLBACK_INNOVATIONS

    content = lean_file.read_text(encoding="utf-8")
    pattern = re.compile(
        r'def\s+\w+\s*:\s*Innovation\s*:=\s*\{'
        r'\s*id\s*:=\s*"([^"]+)"\s*,'
        r'\s*line\s*:=\s*ResearchLine\.(\w+)\s*,'
        r'\s*core\s*:=\s*(true|false)\s*,'
        r'\s*year\s*:=\s*(\d{4})\s*,'
        r'\s*properties\s*:=\s*\{'
        r'\s*scalability\s*:=\s*(\d+)\s*,'
        r'\s*simplicity\s*:=\s*(\d+)\s*,'
        r'\s*stability\s*:=\s*(\d+)\s*'
        r'\}\s*\}'
    )
    innovations = []
    for m in pattern.finditer(content):
        innovations.append({
            "id": m.group(1),
            "line": m.group(2),
            "year": int(m.group(4)),
            "scalability": int(m.group(5)),
            "simplicity": int(m.group(6)),
            "stability": int(m.group(7)),
        })
    return innovations or _FALLBACK_INNOVATIONS


# Fallback: 15 seed innovations (used when Database.lean not found)
_FALLBACK_INNOVATIONS = [
    {"id": "Transformer", "line": "SequenceModeling", "year": 2017,
     "scalability": 5, "simplicity": 2, "stability": 5},
    {"id": "RNN", "line": "SequenceModeling", "year": 2014,
     "scalability": 1, "simplicity": 3, "stability": 5},
    {"id": "LSTM", "line": "SequenceModeling", "year": 2015,
     "scalability": 1, "simplicity": 3, "stability": 5},
    {"id": "Decoder_Only", "line": "SequenceModeling", "year": 2019,
     "scalability": 5, "simplicity": 4, "stability": 5},
    {"id": "GAN_Architecture", "line": "GenerativeModels", "year": 2015,
     "scalability": 3, "simplicity": 2, "stability": 1},
    {"id": "Diffusion_Architecture", "line": "GenerativeModels", "year": 2020,
     "scalability": 4, "simplicity": 3, "stability": 5},
    {"id": "DPO_Loss", "line": "AlignmentPreference", "year": 2023,
     "scalability": 5, "simplicity": 5, "stability": 5},
    {"id": "PPO_Objective", "line": "AlignmentPreference", "year": 2017,
     "scalability": 4, "simplicity": 1, "stability": 3},
    {"id": "LoRA_Algorithm", "line": "EfficiencyCompression", "year": 2021,
     "scalability": 5, "simplicity": 5, "stability": 5},
    {"id": "MoE", "line": "EfficiencyCompression", "year": 2021,
     "scalability": 3, "simplicity": 3, "stability": 3},
    {"id": "Chain_of_Thought", "line": "AgentReasoning", "year": 2022,
     "scalability": 3, "simplicity": 3, "stability": 3},
    {"id": "Mamba", "line": "SequenceModeling", "year": 2023,
     "scalability": 4, "simplicity": 3, "stability": 4},
    {"id": "Flow_Matching_Objective", "line": "GenerativeModels", "year": 2023,
     "scalability": 5, "simplicity": 4, "stability": 5},
    {"id": "Flash_Attention", "line": "EfficiencyCompression", "year": 2023,
     "scalability": 3, "simplicity": 3, "stability": 3},
    {"id": "Speculative_Decoding", "line": "EfficiencyCompression", "year": 2024,
     "scalability": 3, "simplicity": 3, "stability": 3},
]

# Concept name variants for matching (expanded for 125 innovations)
CONCEPT_ALIASES = {
    # SequenceModeling
    "Transformer": ["transformer", "self-attention", "multi-head attention",
                     "attention is all you need", "attention mechanism"],
    "RNN": ["recurrent neural network", "rnn", "recurrent network"],
    "LSTM": ["long short-term memory", "lstm"],
    "GRU": ["gated recurrent unit", "gru"],
    "Seq2Seq": ["sequence to sequence", "seq2seq", "encoder-decoder"],
    "Bahdanau_Attention": ["bahdanau attention", "additive attention"],
    "Decoder_Only": ["decoder-only", "autoregressive transformer", "causal transformer"],
    "Mamba": ["mamba", "state space model", "ssm", "selective state space"],
    # GenerativeModels
    "GAN_Architecture": ["generative adversarial", "gan", "adversarial training",
                         "generator discriminator"],
    "VAE": ["variational autoencoder", "vae", "latent variable model"],
    "Diffusion_Architecture": ["diffusion model", "denoising diffusion", "ddpm",
                                "score-based", "diffusion process"],
    "StyleGAN": ["stylegan", "style-based generator"],
    "Latent_Diffusion": ["latent diffusion", "ldm"],
    "Stable_Diffusion": ["stable diffusion", "sd model"],
    "Flow_Matching_Objective": ["flow matching", "continuous normalizing flow"],
    "Consistency_Model": ["consistency model", "consistency training"],
    "Classifier_Free_Guidance": ["classifier-free guidance", "cfg", "guidance scale"],
    "Score_Matching": ["score matching", "score-based generative"],
    # AlignmentPreference
    "DPO_Loss": ["direct preference optimization", "dpo"],
    "PPO_Objective": ["proximal policy optimization", "ppo"],
    "RLHF": ["reinforcement learning from human feedback", "rlhf"],
    "Constitutional_AI": ["constitutional ai", "self-critique"],
    "KTO": ["kahneman-tversky optimization", "kto"],
    "ORPO": ["odds ratio preference optimization", "orpo"],
    "Reward_Modeling": ["reward model", "reward modeling"],
    "Instruct_Tuning": ["instruction tuning", "instruct tuning", "instruction-following"],
    # EfficiencyCompression
    "LoRA_Algorithm": ["low-rank adaptation", "lora"],
    "QLoRA": ["qlora", "quantized lora"],
    "MoE": ["mixture of experts", "moe", "sparse experts", "expert routing"],
    "Flash_Attention": ["flash attention", "flashattention", "io-aware attention"],
    "Speculative_Decoding": ["speculative decoding", "speculative generation"],
    "Pruning": ["network pruning", "weight pruning", "structured pruning"],
    "Quantization": ["quantization", "int8", "int4", "model quantization"],
    "Knowledge_Distillation": ["knowledge distillation", "model distillation", "teacher student"],
    "Switch_Transformer": ["switch transformer", "sparse transformer"],
    "INT8_Quantization": ["int8 quantization", "8-bit quantization"],
    # AgentReasoning
    "Chain_of_Thought": ["chain-of-thought", "chain of thought", "cot prompting",
                         "step-by-step reasoning"],
    "ReAct": ["react", "reasoning and acting"],
    "Tree_of_Thought": ["tree of thought", "tree-of-thought", "tot"],
    "Tool_Use": ["tool use", "tool calling", "function calling"],
    "Multi_Agent": ["multi-agent", "multi agent", "agent collaboration"],
    "Reflexion": ["reflexion", "self-reflection agent"],
    "Self_Consistency": ["self-consistency", "self consistency"],
    # VisionRepresentation
    "CNN": ["convolutional neural network", "cnn", "convnet"],
    "ResNet": ["residual network", "resnet", "skip connection"],
    "ViT": ["vision transformer", "vit", "image transformer"],
    "DINOv2": ["dinov2", "dino v2", "self-supervised vision"],
    "SAM": ["segment anything", "sam model"],
    "YOLO": ["yolo", "you only look once", "real-time detection"],
    "ConvNeXt": ["convnext", "modernized convnet"],
    "EfficientNet": ["efficientnet", "compound scaling"],
    # SelfSupervised
    "Word2Vec": ["word2vec", "word embedding", "skip-gram", "cbow"],
    "BERT": ["bert", "masked language model", "bidirectional encoder"],
    "GPT": ["gpt", "generative pre-training"],
    "GPT2": ["gpt-2", "gpt2"],
    "GPT3": ["gpt-3", "gpt3", "few-shot learner"],
    "MAE": ["masked autoencoder", "mae"],
    "SimCLR": ["simclr", "contrastive learning"],
    "BYOL": ["byol", "bootstrap your own latent"],
    "DeBERTa": ["deberta", "disentangled attention"],
    "T5": ["t5", "text-to-text transfer"],
    # RetrievalAugmented
    "BM25": ["bm25", "okapi bm25", "sparse retrieval"],
    "Dense_Passage_Retrieval": ["dense passage retrieval", "dpr", "dense retrieval"],
    "ColBERT": ["colbert", "late interaction retrieval"],
    "RAG_Framework": ["retrieval augmented generation", "rag"],
    "E5_Embedding": ["e5 embedding", "e5 model"],
    "BGE_Embedding": ["bge embedding", "baidu general embedding"],
    "Sentence_Transformers": ["sentence transformer", "sentence-bert", "sbert"],
    "Cross_Encoder": ["cross-encoder", "cross encoder reranker"],
    # MultimodalFusion
    "CLIP": ["clip", "contrastive language image", "vision-language pretraining"],
    "Flamingo": ["flamingo", "perceiver resampler"],
    "LLaVA": ["llava", "large language and vision assistant"],
    "BLIP2": ["blip-2", "blip2"],
    "GPT4V": ["gpt-4v", "gpt-4 vision"],
    "Qwen_VL": ["qwen-vl", "qwen vision language"],
    "CogVLM": ["cogvlm", "cognitive vlm"],
    # ReinforcementLearning
    "DQN": ["deep q-network", "dqn", "q-learning"],
    "Policy_Gradient": ["policy gradient", "reinforce"],
    "A3C": ["a3c", "asynchronous advantage actor-critic"],
    "SAC": ["soft actor-critic", "sac"],
    "TD3": ["td3", "twin delayed ddpg"],
    "MuZero": ["muzero", "model-based planning"],
    "Dreamer": ["dreamer", "world model rl"],
    "Rainbow_DQN": ["rainbow dqn", "rainbow agent"],
    # MetaLearning
    "MAML": ["maml", "model-agnostic meta-learning"],
    "Prototypical_Networks": ["prototypical network", "few-shot classification"],
    "Matching_Networks": ["matching network", "attention over support set"],
    # GraphNeuralNetworks
    "GCN": ["graph convolutional network", "gcn"],
    "GAT": ["graph attention network", "gat"],
    "GraphSAGE": ["graphsage", "inductive graph representation"],
    "GIN": ["graph isomorphism network", "gin"],
    # OptimizationMethods
    "Adam": ["adam optimizer", "adaptive moment estimation"],
    "AdamW": ["adamw", "decoupled weight decay"],
    "LAMB": ["lamb optimizer", "layer-wise adaptive"],
    "Lion": ["lion optimizer", "evolutionary optimizer"],
    "Cosine_Annealing": ["cosine annealing", "cosine learning rate"],
    "LR_Warmup": ["learning rate warmup", "warmup schedule"],
    # ScalingLaw
    "Kaplan_Law": ["scaling law", "kaplan law", "power law scaling"],
    "Chinchilla": ["chinchilla", "compute-optimal training"],
    "Emergent_Abilities": ["emergent abilities", "emergent behavior", "emergence"],
    "Grokking": ["grokking", "delayed generalization"],
    "Double_Descent": ["double descent", "benign overfitting"],
    # SafetyRobustness
    "Adversarial_Training": ["adversarial training", "adversarial example", "fgsm"],
    "Red_Teaming": ["red teaming", "red team", "adversarial evaluation"],
    "Guardrails": ["guardrails", "output filtering", "safety filter"],
    "Watermarking": ["watermarking", "text watermark", "llm watermark"],
    # SpeechAudio
    "WaveNet": ["wavenet", "autoregressive audio"],
    "Wav2Vec2": ["wav2vec", "wav2vec 2", "speech representation"],
    "Whisper": ["whisper", "openai whisper", "speech recognition"],
    "EnCodec": ["encodec", "neural audio codec"],
    # CodingLLM
    "Copilot": ["copilot", "code generation", "ai coding assistant"],
    "CodeLLaMA": ["codellama", "code llama"],
    "StarCoder": ["starcoder", "bigcode"],
}


def extract_concepts_tfidf(parsed_dir: Path = None, top_k: int = 5) -> dict:
    """
    Extract key concepts from papers using TF-IDF-like scoring.

    For each paper, extracts terms from title + abstract + headings,
    matches them against known innovation aliases, and returns
    a mapping of paper_id -> set of concept_ids.
    """
    if parsed_dir is None:
        parsed_dir = config.PARSED_DIR

    # Build inverse document frequency: count how many papers mention each concept
    doc_freq = Counter()
    paper_concepts = {}
    total_papers = 0

    for json_file in parsed_dir.glob("*.json"):
        data = json.loads(json_file.read_text(encoding="utf-8"))
        pid = data["paper_id"]
        text_parts = [
            data.get("title") or "",
            data.get("abstract") or "",
        ]
        for s in data.get("sections", []):
            text_parts.append(s.get("heading") or "")
        full_text = " ".join(text_parts).lower()

        matched = set()
        for concept_id, aliases in CONCEPT_ALIASES.items():
            for alias in aliases:
                if alias.lower() in full_text:
                    matched.add(concept_id)
                    break

        paper_concepts[pid] = matched
        for c in matched:
            doc_freq[c] += 1
        total_papers += 1

    # Compute TF-IDF scores: tf = count in text, idf = log(N/df)
    import math
    tfidf_concepts = {}
    for pid, concepts in paper_concepts.items():
        tfidf_concepts[pid] = {
            c: math.log(total_papers / max(doc_freq[c], 1))
            for c in concepts
        }

    return {
        "paper_concepts": paper_concepts,
        "doc_freq": dict(doc_freq),
        "total_papers": total_papers,
    }


def build_concept_graph(gdb: GraphDB, parsed_dir: Path = None):
    """
    Build the concept graph in Neo4j.

    1. Create Innovation nodes from Lean4 seed data (dynamically loaded)
    2. Match innovations to papers by text search + TF-IDF
    3. Build concept co-occurrence edges
    """
    if parsed_dir is None:
        parsed_dir = config.PARSED_DIR

    # Load innovations dynamically from Database.lean
    innovations = load_innovations_from_lean()

    # Step 1: Create Innovation nodes
    for innov in innovations:
        gdb.run("""
            MERGE (i:Innovation {id: $id})
            SET i.line = $line, i.year = $year,
                i.scalability = $scalability,
                i.simplicity = $simplicity,
                i.stability = $stability
        """, **innov)

    # Step 2: Load all parsed papers and match concepts
    paper_concepts = {}  # paper_id -> set of concept names
    all_papers = {}

    for json_file in parsed_dir.glob("*.json"):
        data = json.loads(json_file.read_text(encoding="utf-8"))
        pid = data["paper_id"]
        # Build searchable text from title + abstract + sections
        text_parts = [
            data.get("title") or "",
            data.get("abstract") or "",
        ]
        for s in data.get("sections", []):
            text_parts.append(s.get("heading") or "")
        full_text = " ".join(text_parts).lower()

        all_papers[pid] = data
        matched = set()

        for concept_id, aliases in CONCEPT_ALIASES.items():
            for alias in aliases:
                if alias.lower() in full_text:
                    matched.add(concept_id)
                    break

        paper_concepts[pid] = matched

    # Step 3: Create HAS_CONCEPT edges
    batch = []
    for pid, concepts in paper_concepts.items():
        for concept_id in concepts:
            batch.append({"paper": pid, "concept": concept_id})

    batch_size = 100
    for i in range(0, len(batch), batch_size):
        b = batch[i:i + batch_size]
        gdb.run("""
            UNWIND $batch AS e
            MATCH (p:Paper {ulid: e.paper})
            MATCH (c:Innovation {id: e.concept})
            MERGE (p)-[:HAS_CONCEPT]->(c)
        """, batch=b)

    # Step 4: Build concept co-occurrence (RELATED_TO edges)
    cooccurrence = Counter()
    for concepts in paper_concepts.values():
        concept_list = sorted(concepts)
        for i in range(len(concept_list)):
            for j in range(i + 1, len(concept_list)):
                pair = (concept_list[i], concept_list[j])
                cooccurrence[pair] += 1

    # Only keep edges with weight >= 2
    co_edges = [
        {"from": a, "to": b, "weight": w}
        for (a, b), w in cooccurrence.items() if w >= 2
    ]

    for i in range(0, len(co_edges), batch_size):
        b = co_edges[i:i + batch_size]
        gdb.run("""
            UNWIND $batch AS e
            MATCH (a:Innovation {id: e.from})
            MATCH (b:Innovation {id: e.to})
            MERGE (a)-[r:RELATED_TO]-(b)
            SET r.weight = e.weight
        """, batch=b)

    return {
        "papers_with_concepts": sum(1 for v in paper_concepts.values() if v),
        "total_links": len(batch),
        "cooccurrence_edges": len(co_edges),
    }


# ===================================================================
# Concept Graph Queries
# ===================================================================

def find_papers_by_concept(gdb: GraphDB, concept_id: str) -> list:
    """Find all papers related to a concept."""
    return gdb.run("""
        MATCH (p:Paper)-[:HAS_CONCEPT]->(c:Innovation {id: $concept_id})
        RETURN p.ulid AS ulid, p.title AS title, p.year AS year, p.venue AS venue
        ORDER BY p.year DESC
    """, concept_id=concept_id)


def find_related_concepts(gdb: GraphDB, concept_id: str) -> list:
    """Find concepts related to the given concept."""
    return gdb.run("""
        MATCH (c:Innovation {id: $concept_id})-[r:RELATED_TO]-(other:Innovation)
        RETURN other.id AS id, other.line AS line, r.weight AS weight
        ORDER BY weight DESC
    """, concept_id=concept_id)


def get_concept_timeline(gdb: GraphDB, concept_id: str) -> list:
    """Get papers about a concept ordered by year (for evolution tracking)."""
    return gdb.run("""
        MATCH (p:Paper)-[:HAS_CONCEPT]->(c:Innovation {id: $concept_id})
        WHERE p.year IS NOT NULL
        RETURN p.year AS year, p.ulid AS ulid, p.title AS title, p.venue AS venue
        ORDER BY year ASC
    """, concept_id=concept_id)


def get_concept_subgraph(gdb: GraphDB, concept_ids: list) -> dict:
    """Get a subgraph of concepts and their relationships."""
    nodes = []
    edges = []
    for cid in concept_ids:
        r = gdb.run("""
            MATCH (c:Innovation {id: $cid})
            RETURN c.id AS id, c.line AS line, c.year AS year
        """, cid=cid)
        if r:
            nodes.append(r[0])

        related = gdb.run("""
            MATCH (c:Innovation {id: $cid})-[r:RELATED_TO]-(other:Innovation)
            WHERE other.id IN $other_ids
            RETURN other.id AS target, r.weight AS weight
        """, cid=cid, other_ids=concept_ids)
        for rel in related:
            edges.append({"from": cid, "to": rel["target"], "weight": rel["weight"]})

    return {"nodes": nodes, "edges": edges}


# ===================================================================
# 3. Lean4 Innovation Sync
# ===================================================================

def sync_lean4_replacements(gdb: GraphDB):
    """
    Import REPLACES relationships from Lean4 Database.lean.
    Falls back to hardcoded relations if file not found.
    """
    # Try to load from Database.lean
    lean_file = config.LEAN_DIR / "AiEvolution" / "Database.lean"
    replaces = []

    if lean_file.exists():
        content = lean_file.read_text(encoding="utf-8")
        # Match: { from := "XXX", to := "YYY" } in replacesDb
        in_replaces = False
        for line in content.splitlines():
            if "replacesDb" in line:
                in_replaces = True
                continue
            if in_replaces and "]" in line:
                break
            if in_replaces:
                m = re.search(r'from\s*:=\s*"([^"]+)"\s*,\s*to\s*:=\s*"([^"]+)"', line)
                if m:
                    replaces.append((m.group(1), m.group(2)))

    # Fallback if nothing loaded
    if not replaces:
        replaces = [
            ("Transformer", "RNN"),
            ("Transformer", "LSTM"),
            ("Decoder_Only", "Encoder_Decoder"),
            ("Diffusion_Architecture", "GAN_Architecture"),
            ("Diffusion_Architecture", "VAE_Architecture"),
            ("DPO_Loss", "RLHF_Reward_Model"),
            ("DPO_Loss", "PPO_Objective"),
            ("LoRA_Algorithm", "Adapter_Tuning"),
            ("LoRA_Algorithm", "Prefix_Tuning"),
        ]

    for from_id, to_id in replaces:
        gdb.run("""
            MERGE (a:Innovation {id: $from_id})
            MERGE (b:Innovation {id: $to_id})
            MERGE (a)-[:REPLACES]->(b)
        """, from_id=from_id, to_id=to_id)

    return {"replacements": len(replaces)}


# ===================================================================
# Incremental upsert helpers (used by `ingest` for single-paper updates)
# ===================================================================

def upsert_paper_node(gdb: GraphDB, paper_data: dict) -> None:
    """Create or update a single Paper node from parsed JSON data."""
    ulid = paper_data.get("paper_id")
    if not ulid:
        return
    gdb.run("""
        MERGE (p:Paper {ulid: $ulid})
        SET p.title = $title,
            p.year  = $year,
            p.venue = $venue
    """, ulid=ulid,
       title=paper_data.get("title", ""),
       year=paper_data.get("year") or 0,
       venue=paper_data.get("venue", ""))


def upsert_paper_citations(gdb: GraphDB, ulid: str, paper_data: dict) -> None:
    """Recreate CITES edges for a single paper from its parsed citations list."""
    citations = paper_data.get("citations", [])
    if isinstance(citations, str):
        import ast as _ast
        try:
            citations = _ast.literal_eval(citations)
        except Exception:
            citations = []

    # Wipe existing edges from this paper, then re-create
    gdb.run("MATCH (p:Paper {ulid: $ulid})-[c:CITES]->() DELETE c", ulid=ulid)

    edges = []
    for ref in citations:
        if isinstance(ref, dict):
            ref_key = ref.get("ref_key") or ref.get("title") or ""
        else:
            ref_key = str(ref) if ref else ""
        if not ref_key:
            continue
        # Use a placeholder node if we can't resolve the ref yet
        target = f"ref_{ref_key.replace(' ', '_')[:80]}"
        edges.append({"from": ulid, "to": target, "ref_key": ref_key})

    if edges:
        for i in range(0, len(edges), 100):
            batch = edges[i:i + 100]
            gdb.run("""
                UNWIND $batch AS e
                MERGE (from:Paper {ulid: e.from})
                MERGE (to:Paper {ulid: e.to})
                MERGE (from)-[c:CITES]->(to)
                SET c.ref_key = e.ref_key, c.resolved = false
            """, batch=batch)


def upsert_paper_concepts(gdb: GraphDB, ulid: str, paper_data: dict) -> None:
    """Create HAS_CONCEPT edges for a single paper based on its tag fields."""
    tags = paper_data.get("tags", {})
    if isinstance(tags, str):
        import ast as _ast
        try:
            tags = _ast.literal_eval(tags)
        except Exception:
            tags = {}

    methods = tags.get("methods", []) or []
    sub_directions = tags.get("sub_directions", []) or []
    concepts = list(set(methods + sub_directions))
    if not concepts:
        return

    edges = [{"from": ulid, "to": c} for c in concepts]
    gdb.run("""
        UNWIND $batch AS e
        MERGE (p:Paper {ulid: e.from})
        MERGE (c:Innovation {id: e.to})
        MERGE (p)-[:HAS_CONCEPT]->(c)
    """, batch=edges)
