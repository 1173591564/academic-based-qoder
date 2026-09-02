"""
Scholar Studio - Concept vocabulary (data-only module, v0.2.0).

Extracted verbatim from the retired Neo4j layer (graph_db.py): the alias
table used to tag papers with concepts, the word-boundary matcher, title
normalisation, and the Lean4 innovation seeds. No I/O, no drivers.
"""
import re

def _normalize_title(title: str) -> str:
    """Normalize a title for fuzzy matching."""
    if not title:
        return ""
    title = title.lower()
    title = re.sub(r"[^a-z0-9\s]", "", title)
    return re.sub(r"\s+", " ", title).strip()


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


_CONCEPT_PATTERNS: dict[str, list[re.Pattern]] = {}


def _get_concept_patterns(concept_id: str, aliases: list[str]) -> list[re.Pattern]:
    """Get or compile word-boundary regex patterns for a concept's aliases."""
    if concept_id not in _CONCEPT_PATTERNS:
        _CONCEPT_PATTERNS[concept_id] = [
            re.compile(r'\b' + re.escape(alias.lower()) + r'\b', re.IGNORECASE)
            for alias in aliases
        ]
    return _CONCEPT_PATTERNS[concept_id]


def _match_concept_in_text(full_text: str, concept_id: str, aliases: list[str]) -> bool:
    """Check if any alias of a concept appears in text with word-boundary matching."""
    for pattern in _get_concept_patterns(concept_id, aliases):
        if pattern.search(full_text):
            return True
    return False
