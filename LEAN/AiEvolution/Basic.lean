/-
  AiEvolution.Basic — Core type definitions for AI evolution formal analysis.

  Defines the research line taxonomy, innovation properties, and paper metadata
  structures used throughout the formal verification system.
-/

namespace AiEvolution

/-- The 16 research lines that organize AI innovation into a taxonomy. -/
inductive ResearchLine where
  | SequenceModeling     -- RNN → LSTM → Transformer → Mamba → ...
  | GenerativeModels     -- GAN → VAE → Diffusion → Flow Matching → ...
  | AlignmentPreference  -- PPO → DPO → Constitutional AI → ...
  | EfficiencyCompression -- Pruning → Quantization → Distillation → LoRA → MoE → ...
  | AgentReasoning       -- ReAct → CoT → Tool Use → Multi-Agent → ...
  | VisionRepresentation -- CNN → ViT → CLIP → DINO → ...
  | SelfSupervised       -- Word2Vec → BERT → GPT → MAE → ...
  | RetrievalAugmented   -- BM25 → DPR → RAG → ...
  | MultimodalFusion     -- CLIP → Flamingo → GPT-4V → ...
  | ReinforcementLearning -- DQN → PPO → SAC → ...
  | MetaLearning         -- MAML → Prototypical → ...
  | GraphNeuralNetworks  -- GCN → GAT → GraphSAGE → ...
  | OptimizationMethods  -- SGD → Adam → LAMB → ...
  | ScalingLaw           -- Kaplan → Chinchilla → ...
  | SafetyRobustness     -- Adversarial → RLHF → Red Teaming → ...
  | SpeechAudio          -- WaveNet → Whisper → ...
  deriving Repr, DecidableEq, Inhabited

/-- Quantitative properties for comparing innovations on three axes. -/
structure Properties where
  scalability : Nat  -- 1-5: how well the method scales with compute/data
  simplicity  : Nat  -- 1-5: how simple the method is (lower = more complex)
  stability   : Nat  -- 1-5: how stable/reliable the method is
  deriving Repr, DecidableEq

/-- An innovation node in the AI evolution graph. -/
structure Innovation where
  id         : String
  line       : ResearchLine
  core       : Bool       -- true if this is a core/foundational innovation
  year       : Nat
  properties : Properties
  deriving Repr, DecidableEq

/-- A paper record linking to the knowledge base. -/
structure Paper where
  id   : String           -- human-readable ID, e.g. "Attention_Is_All_You_Need"
  year : Nat
  deriving Repr, DecidableEq

/-- A citation relation between two papers. -/
structure Citation where
  from : String           -- citing paper id
  to   : String           -- cited paper id
  deriving Repr, DecidableEq

/-- A replacement relation: innovation `from` is superseded by innovation `to`. -/
structure Replacement where
  from : String           -- old innovation id
  to   : String           -- new innovation id
  deriving Repr, DecidableEq

end AiEvolution
