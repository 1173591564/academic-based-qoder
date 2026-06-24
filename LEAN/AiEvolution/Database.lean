/-
  AiEvolution.Database — 125 Innovations + 440 Papers + relations.

  This is the canonical data source parsed by:
  - scholar/year_fix.py  (parse_lean_papers, parse_lean_innovations)
  - scholar/graph_db.py  (LEAN_INNOVATIONS, CONCEPT_ALIASES)
-/
import AiEvolution.Basic

open AiEvolution

namespace AiEvolution.Database

-- ===================================================================
-- 125 Innovation Nodes (grouped by ResearchLine)
-- ===================================================================

-- ── SequenceModeling (9) ──
def RNN : Innovation := { id := "RNN", line := ResearchLine.SequenceModeling, core := true, year := 1986, properties := { scalability := 1, simplicity := 3, stability := 5 } }
def LSTM : Innovation := { id := "LSTM", line := ResearchLine.SequenceModeling, core := true, year := 1997, properties := { scalability := 2, simplicity := 3, stability := 5 } }
def GRU : Innovation := { id := "GRU", line := ResearchLine.SequenceModeling, core := false, year := 2014, properties := { scalability := 2, simplicity := 4, stability := 5 } }
def Seq2Seq : Innovation := { id := "Seq2Seq", line := ResearchLine.SequenceModeling, core := true, year := 2014, properties := { scalability := 3, simplicity := 3, stability := 5 } }
def Bahdanau_Attention : Innovation := { id := "Bahdanau_Attention", line := ResearchLine.SequenceModeling, core := true, year := 2014, properties := { scalability := 3, simplicity := 3, stability := 5 } }
def Transformer : Innovation := { id := "Transformer", line := ResearchLine.SequenceModeling, core := true, year := 2017, properties := { scalability := 5, simplicity := 2, stability := 5 } }
def Decoder_Only : Innovation := { id := "Decoder_Only", line := ResearchLine.SequenceModeling, core := true, year := 2019, properties := { scalability := 5, simplicity := 4, stability := 5 } }
def Mamba : Innovation := { id := "Mamba", line := ResearchLine.SequenceModeling, core := true, year := 2023, properties := { scalability := 4, simplicity := 3, stability := 4 } }

-- ── GenerativeModels (10) ──
def VAE : Innovation := { id := "VAE", line := ResearchLine.GenerativeModels, core := true, year := 2013, properties := { scalability := 3, simplicity := 3, stability := 4 } }
def GAN_Architecture : Innovation := { id := "GAN_Architecture", line := ResearchLine.GenerativeModels, core := true, year := 2014, properties := { scalability := 3, simplicity := 2, stability := 1 } }
def StyleGAN : Innovation := { id := "StyleGAN", line := ResearchLine.GenerativeModels, core := false, year := 2019, properties := { scalability := 3, simplicity := 2, stability := 3 } }
def Diffusion_Architecture : Innovation := { id := "Diffusion_Architecture", line := ResearchLine.GenerativeModels, core := true, year := 2020, properties := { scalability := 4, simplicity := 3, stability := 5 } }
def Score_Matching : Innovation := { id := "Score_Matching", line := ResearchLine.GenerativeModels, core := false, year := 2019, properties := { scalability := 3, simplicity := 2, stability := 4 } }
def Classifier_Free_Guidance : Innovation := { id := "Classifier_Free_Guidance", line := ResearchLine.GenerativeModels, core := true, year := 2022, properties := { scalability := 4, simplicity := 4, stability := 5 } }
def Flow_Matching_Objective : Innovation := { id := "Flow_Matching_Objective", line := ResearchLine.GenerativeModels, core := true, year := 2023, properties := { scalability := 5, simplicity := 4, stability := 5 } }
def Consistency_Model : Innovation := { id := "Consistency_Model", line := ResearchLine.GenerativeModels, core := false, year := 2023, properties := { scalability := 4, simplicity := 3, stability := 3 } }
def Latent_Diffusion : Innovation := { id := "Latent_Diffusion", line := ResearchLine.GenerativeModels, core := true, year := 2022, properties := { scalability := 4, simplicity := 3, stability := 5 } }
def Stable_Diffusion : Innovation := { id := "Stable_Diffusion", line := ResearchLine.GenerativeModels, core := false, year := 2022, properties := { scalability := 4, simplicity := 3, stability := 4 } }

-- ── AlignmentPreference (9) ──
def RLHF : Innovation := { id := "RLHF", line := ResearchLine.AlignmentPreference, core := true, year := 2022, properties := { scalability := 3, simplicity := 2, stability := 3 } }
def PPO_Objective : Innovation := { id := "PPO_Objective", line := ResearchLine.AlignmentPreference, core := true, year := 2017, properties := { scalability := 4, simplicity := 1, stability := 3 } }
def DPO_Loss : Innovation := { id := "DPO_Loss", line := ResearchLine.AlignmentPreference, core := true, year := 2023, properties := { scalability := 5, simplicity := 5, stability := 5 } }
def Constitutional_AI : Innovation := { id := "Constitutional_AI", line := ResearchLine.AlignmentPreference, core := true, year := 2022, properties := { scalability := 4, simplicity := 3, stability := 4 } }
def KTO : Innovation := { id := "KTO", line := ResearchLine.AlignmentPreference, core := false, year := 2023, properties := { scalability := 4, simplicity := 4, stability := 4 } }
def ORPO : Innovation := { id := "ORPO", line := ResearchLine.AlignmentPreference, core := false, year := 2024, properties := { scalability := 4, simplicity := 4, stability := 4 } }
def Rejection_Sampling : Innovation := { id := "Rejection_Sampling", line := ResearchLine.AlignmentPreference, core := false, year := 2023, properties := { scalability := 3, simplicity := 4, stability := 3 } }
def Reward_Modeling : Innovation := { id := "Reward_Modeling", line := ResearchLine.AlignmentPreference, core := false, year := 2020, properties := { scalability := 3, simplicity := 2, stability := 3 } }
def Instruct_Tuning : Innovation := { id := "Instruct_Tuning", line := ResearchLine.AlignmentPreference, core := true, year := 2022, properties := { scalability := 4, simplicity := 4, stability := 4 } }

-- ── EfficiencyCompression (11) ──
def Pruning : Innovation := { id := "Pruning", line := ResearchLine.EfficiencyCompression, core := true, year := 2015, properties := { scalability := 4, simplicity := 4, stability := 4 } }
def Quantization : Innovation := { id := "Quantization", line := ResearchLine.EfficiencyCompression, core := true, year := 2016, properties := { scalability := 4, simplicity := 4, stability := 4 } }
def Knowledge_Distillation : Innovation := { id := "Knowledge_Distillation", line := ResearchLine.EfficiencyCompression, core := true, year := 2015, properties := { scalability := 4, simplicity := 3, stability := 4 } }
def LoRA_Algorithm : Innovation := { id := "LoRA_Algorithm", line := ResearchLine.EfficiencyCompression, core := true, year := 2021, properties := { scalability := 5, simplicity := 5, stability := 5 } }
def QLoRA : Innovation := { id := "QLoRA", line := ResearchLine.EfficiencyCompression, core := false, year := 2023, properties := { scalability := 5, simplicity := 4, stability := 4 } }
def MoE : Innovation := { id := "MoE", line := ResearchLine.EfficiencyCompression, core := true, year := 2021, properties := { scalability := 3, simplicity := 3, stability := 3 } }
def Flash_Attention : Innovation := { id := "Flash_Attention", line := ResearchLine.EfficiencyCompression, core := true, year := 2023, properties := { scalability := 3, simplicity := 3, stability := 3 } }
def Speculative_Decoding : Innovation := { id := "Speculative_Decoding", line := ResearchLine.EfficiencyCompression, core := true, year := 2024, properties := { scalability := 3, simplicity := 3, stability := 3 } }
def INT8_Quantization : Innovation := { id := "INT8_Quantization", line := ResearchLine.EfficiencyCompression, core := false, year := 2020, properties := { scalability := 4, simplicity := 3, stability := 4 } }
def Switch_Transformer : Innovation := { id := "Switch_Transformer", line := ResearchLine.EfficiencyCompression, core := false, year := 2022, properties := { scalability := 4, simplicity := 3, stability := 3 } }
-- ── AgentReasoning (8) ──
def Chain_of_Thought : Innovation := { id := "Chain_of_Thought", line := ResearchLine.AgentReasoning, core := true, year := 2022, properties := { scalability := 3, simplicity := 3, stability := 3 } }
def ReAct : Innovation := { id := "ReAct", line := ResearchLine.AgentReasoning, core := true, year := 2022, properties := { scalability := 3, simplicity := 4, stability := 4 } }
def Tree_of_Thought : Innovation := { id := "Tree_of_Thought", line := ResearchLine.AgentReasoning, core := false, year := 2023, properties := { scalability := 3, simplicity := 3, stability := 3 } }
def Tool_Use : Innovation := { id := "Tool_Use", line := ResearchLine.AgentReasoning, core := true, year := 2023, properties := { scalability := 3, simplicity := 3, stability := 3 } }
def Multi_Agent : Innovation := { id := "Multi_Agent", line := ResearchLine.AgentReasoning, core := false, year := 2023, properties := { scalability := 3, simplicity := 3, stability := 3 } }
def Reflexion : Innovation := { id := "Reflexion", line := ResearchLine.AgentReasoning, core := false, year := 2023, properties := { scalability := 3, simplicity := 4, stability := 3 } }
def Self_Consistency : Innovation := { id := "Self_Consistency", line := ResearchLine.AgentReasoning, core := false, year := 2022, properties := { scalability := 3, simplicity := 4, stability := 3 } }

-- ── VisionRepresentation (8) ──
def CNN : Innovation := { id := "CNN", line := ResearchLine.VisionRepresentation, core := true, year := 1998, properties := { scalability := 3, simplicity := 3, stability := 5 } }
def ResNet : Innovation := { id := "ResNet", line := ResearchLine.VisionRepresentation, core := true, year := 2015, properties := { scalability := 4, simplicity := 4, stability := 5 } }
def ViT : Innovation := { id := "ViT", line := ResearchLine.VisionRepresentation, core := true, year := 2020, properties := { scalability := 5, simplicity := 3, stability := 5 } }
def DINOv2 : Innovation := { id := "DINOv2", line := ResearchLine.VisionRepresentation, core := false, year := 2023, properties := { scalability := 4, simplicity := 3, stability := 4 } }
def SAM : Innovation := { id := "SAM", line := ResearchLine.VisionRepresentation, core := true, year := 2023, properties := { scalability := 4, simplicity := 3, stability := 4 } }
def YOLO : Innovation := { id := "YOLO", line := ResearchLine.VisionRepresentation, core := false, year := 2016, properties := { scalability := 3, simplicity := 3, stability := 5 } }
def ConvNeXt : Innovation := { id := "ConvNeXt", line := ResearchLine.VisionRepresentation, core := false, year := 2022, properties := { scalability := 4, simplicity := 3, stability := 4 } }
def EfficientNet : Innovation := { id := "EfficientNet", line := ResearchLine.VisionRepresentation, core := false, year := 2019, properties := { scalability := 4, simplicity := 3, stability := 4 } }

-- ── SelfSupervised (10) ──
def Word2Vec : Innovation := { id := "Word2Vec", line := ResearchLine.SelfSupervised, core := true, year := 2013, properties := { scalability := 3, simplicity := 4, stability := 5 } }
def BERT : Innovation := { id := "BERT", line := ResearchLine.SelfSupervised, core := true, year := 2018, properties := { scalability := 4, simplicity := 3, stability := 5 } }
def GPT : Innovation := { id := "GPT", line := ResearchLine.SelfSupervised, core := true, year := 2018, properties := { scalability := 5, simplicity := 3, stability := 5 } }
def GPT2 : Innovation := { id := "GPT2", line := ResearchLine.SelfSupervised, core := false, year := 2019, properties := { scalability := 5, simplicity := 3, stability := 5 } }
def GPT3 : Innovation := { id := "GPT3", line := ResearchLine.SelfSupervised, core := true, year := 2020, properties := { scalability := 5, simplicity := 3, stability := 5 } }
def MAE : Innovation := { id := "MAE", line := ResearchLine.SelfSupervised, core := false, year := 2022, properties := { scalability := 4, simplicity := 4, stability := 4 } }
def SimCLR : Innovation := { id := "SimCLR", line := ResearchLine.SelfSupervised, core := false, year := 2020, properties := { scalability := 3, simplicity := 3, stability := 4 } }
def BYOL : Innovation := { id := "BYOL", line := ResearchLine.SelfSupervised, core := false, year := 2020, properties := { scalability := 3, simplicity := 3, stability := 4 } }
def DeBERTa : Innovation := { id := "DeBERTa", line := ResearchLine.SelfSupervised, core := false, year := 2021, properties := { scalability := 4, simplicity := 3, stability := 4 } }
def T5 : Innovation := { id := "T5", line := ResearchLine.SelfSupervised, core := true, year := 2020, properties := { scalability := 4, simplicity := 3, stability := 5 } }

-- ── RetrievalAugmented (8) ──
def BM25 : Innovation := { id := "BM25", line := ResearchLine.RetrievalAugmented, core := true, year := 1994, properties := { scalability := 4, simplicity := 5, stability := 5 } }
def Dense_Passage_Retrieval : Innovation := { id := "Dense_Passage_Retrieval", line := ResearchLine.RetrievalAugmented, core := true, year := 2020, properties := { scalability := 4, simplicity := 3, stability := 4 } }
def ColBERT : Innovation := { id := "ColBERT", line := ResearchLine.RetrievalAugmented, core := false, year := 2020, properties := { scalability := 4, simplicity := 3, stability := 4 } }
def E5_Embedding : Innovation := { id := "E5_Embedding", line := ResearchLine.RetrievalAugmented, core := false, year := 2023, properties := { scalability := 4, simplicity := 4, stability := 4 } }
def BGE_Embedding : Innovation := { id := "BGE_Embedding", line := ResearchLine.RetrievalAugmented, core := false, year := 2023, properties := { scalability := 4, simplicity := 4, stability := 4 } }
def RAG_Framework : Innovation := { id := "RAG_Framework", line := ResearchLine.RetrievalAugmented, core := true, year := 2020, properties := { scalability := 4, simplicity := 4, stability := 4 } }
def Cross_Encoder : Innovation := { id := "Cross_Encoder", line := ResearchLine.RetrievalAugmented, core := false, year := 2020, properties := { scalability := 3, simplicity := 3, stability := 4 } }
def Sentence_Transformers : Innovation := { id := "Sentence_Transformers", line := ResearchLine.RetrievalAugmented, core := false, year := 2019, properties := { scalability := 4, simplicity := 4, stability := 5 } }

-- ── MultimodalFusion (8) ──
def CLIP : Innovation := { id := "CLIP", line := ResearchLine.MultimodalFusion, core := true, year := 2021, properties := { scalability := 5, simplicity := 3, stability := 5 } }
def Flamingo : Innovation := { id := "Flamingo", line := ResearchLine.MultimodalFusion, core := true, year := 2022, properties := { scalability := 4, simplicity := 3, stability := 4 } }
def LLaVA : Innovation := { id := "LLaVA", line := ResearchLine.MultimodalFusion, core := true, year := 2023, properties := { scalability := 4, simplicity := 3, stability := 4 } }
def BLIP2 : Innovation := { id := "BLIP2", line := ResearchLine.MultimodalFusion, core := false, year := 2023, properties := { scalability := 4, simplicity := 3, stability := 4 } }
def GPT4V : Innovation := { id := "GPT4V", line := ResearchLine.MultimodalFusion, core := true, year := 2023, properties := { scalability := 5, simplicity := 2, stability := 4 } }
def Qwen_VL : Innovation := { id := "Qwen_VL", line := ResearchLine.MultimodalFusion, core := false, year := 2023, properties := { scalability := 4, simplicity := 3, stability := 4 } }
def CogVLM : Innovation := { id := "CogVLM", line := ResearchLine.MultimodalFusion, core := false, year := 2023, properties := { scalability := 4, simplicity := 3, stability := 4 } }
-- ── ReinforcementLearning (8) ──
def DQN : Innovation := { id := "DQN", line := ResearchLine.ReinforcementLearning, core := true, year := 2013, properties := { scalability := 3, simplicity := 3, stability := 4 } }
def Policy_Gradient : Innovation := { id := "Policy_Gradient", line := ResearchLine.ReinforcementLearning, core := true, year := 2016, properties := { scalability := 3, simplicity := 3, stability := 3 } }
def A3C : Innovation := { id := "A3C", line := ResearchLine.ReinforcementLearning, core := false, year := 2016, properties := { scalability := 3, simplicity := 2, stability := 3 } }
def SAC : Innovation := { id := "SAC", line := ResearchLine.ReinforcementLearning, core := true, year := 2018, properties := { scalability := 3, simplicity := 2, stability := 4 } }
def TD3 : Innovation := { id := "TD3", line := ResearchLine.ReinforcementLearning, core := false, year := 2018, properties := { scalability := 3, simplicity := 2, stability := 4 } }
def MuZero : Innovation := { id := "MuZero", line := ResearchLine.ReinforcementLearning, core := true, year := 2019, properties := { scalability := 3, simplicity := 1, stability := 3 } }
def Dreamer : Innovation := { id := "Dreamer", line := ResearchLine.ReinforcementLearning, core := false, year := 2020, properties := { scalability := 3, simplicity := 1, stability := 3 } }
def Rainbow_DQN : Innovation := { id := "Rainbow_DQN", line := ResearchLine.ReinforcementLearning, core := false, year := 2018, properties := { scalability := 3, simplicity := 2, stability := 4 } }

-- ── MetaLearning (6) ──
def MAML : Innovation := { id := "MAML", line := ResearchLine.MetaLearning, core := true, year := 2017, properties := { scalability := 2, simplicity := 3, stability := 3 } }
def Prototypical_Networks : Innovation := { id := "Prototypical_Networks", line := ResearchLine.MetaLearning, core := false, year := 2017, properties := { scalability := 3, simplicity := 4, stability := 4 } }
def Matching_Networks : Innovation := { id := "Matching_Networks", line := ResearchLine.MetaLearning, core := false, year := 2016, properties := { scalability := 2, simplicity := 3, stability := 3 } }
def Reptile : Innovation := { id := "Reptile", line := ResearchLine.MetaLearning, core := false, year := 2018, properties := { scalability := 2, simplicity := 4, stability := 3 } }
def Meta_SGD : Innovation := { id := "Meta_SGD", line := ResearchLine.MetaLearning, core := false, year := 2018, properties := { scalability := 2, simplicity := 3, stability := 3 } }
def ANIL : Innovation := { id := "ANIL", line := ResearchLine.MetaLearning, core := false, year := 2020, properties := { scalability := 2, simplicity := 3, stability := 3 } }

-- ── GraphNeuralNetworks (6) ──
def GCN : Innovation := { id := "GCN", line := ResearchLine.GraphNeuralNetworks, core := true, year := 2016, properties := { scalability := 3, simplicity := 4, stability := 5 } }
def GAT : Innovation := { id := "GAT", line := ResearchLine.GraphNeuralNetworks, core := true, year := 2018, properties := { scalability := 3, simplicity := 3, stability := 4 } }
def GraphSAGE : Innovation := { id := "GraphSAGE", line := ResearchLine.GraphNeuralNetworks, core := false, year := 2017, properties := { scalability := 4, simplicity := 3, stability := 4 } }
def GNN_MPNN : Innovation := { id := "GNN_MPNN", line := ResearchLine.GraphNeuralNetworks, core := false, year := 2017, properties := { scalability := 3, simplicity := 3, stability := 4 } }
def GIN : Innovation := { id := "GIN", line := ResearchLine.GraphNeuralNetworks, core := false, year := 2019, properties := { scalability := 3, simplicity := 3, stability := 4 } }
-- ── OptimizationMethods (8) ──
def SGD_Momentum : Innovation := { id := "SGD_Momentum", line := ResearchLine.OptimizationMethods, core := true, year := 1964, properties := { scalability := 4, simplicity := 5, stability := 5 } }
def Adam : Innovation := { id := "Adam", line := ResearchLine.OptimizationMethods, core := true, year := 2014, properties := { scalability := 5, simplicity := 5, stability := 4 } }
def AdamW : Innovation := { id := "AdamW", line := ResearchLine.OptimizationMethods, core := true, year := 2019, properties := { scalability := 5, simplicity := 5, stability := 5 } }
def LAMB : Innovation := { id := "LAMB", line := ResearchLine.OptimizationMethods, core := false, year := 2019, properties := { scalability := 5, simplicity := 4, stability := 4 } }
def Lion : Innovation := { id := "Lion", line := ResearchLine.OptimizationMethods, core := false, year := 2023, properties := { scalability := 4, simplicity := 4, stability := 4 } }
def Cosine_Annealing : Innovation := { id := "Cosine_Annealing", line := ResearchLine.OptimizationMethods, core := false, year := 2016, properties := { scalability := 4, simplicity := 4, stability := 5 } }
def LR_Warmup : Innovation := { id := "LR_Warmup", line := ResearchLine.OptimizationMethods, core := false, year := 2017, properties := { scalability := 4, simplicity := 4, stability := 5 } }
def Adafactor : Innovation := { id := "Adafactor", line := ResearchLine.OptimizationMethods, core := false, year := 2018, properties := { scalability := 4, simplicity := 3, stability := 4 } }

-- ── ScalingLaw (5) ──
def Kaplan_Law : Innovation := { id := "Kaplan_Law", line := ResearchLine.ScalingLaw, core := true, year := 2020, properties := { scalability := 5, simplicity := 5, stability := 5 } }
def Chinchilla : Innovation := { id := "Chinchilla", line := ResearchLine.ScalingLaw, core := true, year := 2022, properties := { scalability := 5, simplicity := 4, stability := 5 } }
def Emergent_Abilities : Innovation := { id := "Emergent_Abilities", line := ResearchLine.ScalingLaw, core := true, year := 2022, properties := { scalability := 5, simplicity := 4, stability := 4 } }
def Grokking : Innovation := { id := "Grokking", line := ResearchLine.ScalingLaw, core := false, year := 2022, properties := { scalability := 3, simplicity := 3, stability := 3 } }
def Double_Descent : Innovation := { id := "Double_Descent", line := ResearchLine.ScalingLaw, core := false, year := 2019, properties := { scalability := 4, simplicity := 3, stability := 3 } }
-- ── SafetyRobustness (8) ──
def Adversarial_Training : Innovation := { id := "Adversarial_Training", line := ResearchLine.SafetyRobustness, core := true, year := 2014, properties := { scalability := 2, simplicity := 2, stability := 3 } }
def RLHF_Safety : Innovation := { id := "RLHF_Safety", line := ResearchLine.SafetyRobustness, core := true, year := 2022, properties := { scalability := 3, simplicity := 2, stability := 3 } }
def Red_Teaming : Innovation := { id := "Red_Teaming", line := ResearchLine.SafetyRobustness, core := true, year := 2022, properties := { scalability := 3, simplicity := 4, stability := 3 } }
def Constitutional_AI_Safety : Innovation := { id := "Constitutional_AI_Safety", line := ResearchLine.SafetyRobustness, core := true, year := 2022, properties := { scalability := 4, simplicity := 3, stability := 4 } }
def DPO_Safety : Innovation := { id := "DPO_Safety", line := ResearchLine.SafetyRobustness, core := false, year := 2023, properties := { scalability := 4, simplicity := 4, stability := 4 } }
def Guardrails : Innovation := { id := "Guardrails", line := ResearchLine.SafetyRobustness, core := false, year := 2023, properties := { scalability := 3, simplicity := 3, stability := 3 } }
def Watermarking : Innovation := { id := "Watermarking", line := ResearchLine.SafetyRobustness, core := false, year := 2023, properties := { scalability := 3, simplicity := 3, stability := 3 } }
def Alignment_Tax : Innovation := { id := "Alignment_Tax", line := ResearchLine.SafetyRobustness, core := false, year := 2023, properties := { scalability := 3, simplicity := 4, stability := 4 } }
-- ── SpeechAudio (5) ──
def WaveNet : Innovation := { id := "WaveNet", line := ResearchLine.SpeechAudio, core := true, year := 2016, properties := { scalability := 2, simplicity := 2, stability := 4 } }
def Wav2Vec2 : Innovation := { id := "Wav2Vec2", line := ResearchLine.SpeechAudio, core := true, year := 2020, properties := { scalability := 3, simplicity := 3, stability := 4 } }
def Whisper : Innovation := { id := "Whisper", line := ResearchLine.SpeechAudio, core := true, year := 2022, properties := { scalability := 4, simplicity := 3, stability := 5 } }
def Tacotron2 : Innovation := { id := "Tacotron2", line := ResearchLine.SpeechAudio, core := false, year := 2018, properties := { scalability := 3, simplicity := 2, stability := 4 } }
def EnCodec : Innovation := { id := "EnCodec", line := ResearchLine.SpeechAudio, core := false, year := 2022, properties := { scalability := 3, simplicity := 2, stability := 4 } }

-- ── CodingLLM (3) ──
def Copilot : Innovation := { id := "Copilot", line := ResearchLine.CodingLLM, core := true, year := 2021, properties := { scalability := 4, simplicity := 3, stability := 4 } }
def CodeLLaMA : Innovation := { id := "CodeLLaMA", line := ResearchLine.CodingLLM, core := false, year := 2023, properties := { scalability := 4, simplicity := 3, stability := 4 } }
def StarCoder : Innovation := { id := "StarCoder", line := ResearchLine.CodingLLM, core := false, year := 2023, properties := { scalability := 4, simplicity := 3, stability := 4 } }

-- ===================================================================
-- 440 Paper Records (generated from output/parsed/*.json)
-- ===================================================================

def p_000 : Paper := { id := "3D_Gaussian_Splatting_for_Real_Time_Radiance_Field_Rendering", year := 2023 }
def p_001 : Paper := { id := "Asynchronous_Methods_for_Deep_Reinforcement_Learning", year := 2016 }
def p_002 : Paper := { id := "Paper_002", year := 2024 }
def p_003 : Paper := { id := "Parameter_Efficient_Transfer_Learning_for_NLP", year := 2019 }
def p_004 : Paper := { id := "AdvPrompter_Fast_Adaptive_Adversarial_Prompting_for_LLMs", year := 2025 }
def p_005 : Paper := { id := "Agent57_Outperforming_the_Atari_Human_Benchmark", year := 2020 }
def p_006 : Paper := { id := "An_Interactive_Agent_Foundation_Model", year := 2024 }
def p_007 : Paper := { id := "Agent_FLAN_Designing_Data_and_Methods_of_Effective_Agent_Tun", year := 2021 }
def p_008 : Paper := { id := "A_Survey_on_the_Optimization_of_Large_Language_Model_based_A", year := 2025 }
def p_009 : Paper := { id := "Question_Decomposition_Improves_the_Faithfulness_of_Model_Ge", year := 2023 }
def p_010 : Paper := { id := "A_Comprehensive_Survey_in_LLM_Agent_Full_Stack_Safety_Data_T", year := 2015 }
def p_011 : Paper := { id := "AgentBench_Evaluating_LLMs_as_Agents", year := 2024 }
def p_012 : Paper := { id := "AgentLite_A_Lightweight_Library_for_Building_and_Advancing_T", year := 2024 }
def p_013 : Paper := { id := "Paper_013", year := 2024 }
def p_014 : Paper := { id := "AgentSims_An_Open_Source_Sandbox_for_Large_Language_Model_Ev", year := 2023 }
def p_015 : Paper := { id := "AgentTuning_Enabling_Generalized_Agent_Abilities_for_LLMs", year := 2024 }
def p_016 : Paper := { id := "AgentVerse_Facilitating_Multi_Agent_Collaboration_and_Explor", year := 2024 }
def p_017 : Paper := { id := "Alpa_Automating_Inter_and_Intra_Operator_Parallelism_for_Dis", year := 2024 }
def p_018 : Paper := { id := "Competition_Level_Code_Generation_with_AlphaCode", year := 2024 }
def p_019 : Paper := { id := "Wus_Method_can_Boost_Symbolic_AI_to_Rival_Silver_Medalists_a", year := 2024 }
def p_020 : Paper := { id := "API_Bank_A_Comprehensive_Benchmark_for_Tool_Augmented_LLMs", year := 2023 }
def p_021 : Paper := { id := "Navigating_the_Risks_A_Survey_of_Security_Privacy_and_Ethics", year := 2018 }
def p_022 : Paper := { id := "Attention_Is_All_You_Need", year := 2017 }
def p_023 : Paper := { id := "AutoDAN_Interpretable_Gradient_Based_Adversarial_Attacks_on_", year := 2024 }
def p_024 : Paper := { id := "Autoformer_Decomposition_Transformers_with_Auto_Correlation_", year := 2021 }
def p_025 : Paper := { id := "AutoGen_Enabling_Next_Gen_LLM_Applications_via_Multi_Agent_C", year := 2023 }
def p_026 : Paper := { id := "Auto_GPT_for_Online_Decision_Making_Benchmarks_and_Additiona", year := 2023 }
def p_027 : Paper := { id := "Paper_027", year := 2024 }
def p_028 : Paper := { id := "Neural_Machine_Translation_by_Jointly_Learning_to_Align_and_", year := 2015 }
def p_029 : Paper := { id := "Batch_Normalization_Accelerating_Deep_Network_Training_by_Re", year := 2015 }
def p_030 : Paper := { id := "BEiT_BERT_Pre_Training_of_Image_Transformers", year := 2022 }
def p_031 : Paper := { id := "BERT_Pre_training_of_Deep_Bidirectional_Transformers_for_Lan", year := 2017 }
def p_032 : Paper := { id := "Big_Bird_Transformers_for_Longer_Sequences", year := 2020 }
def p_033 : Paper := { id := "BioPlanner_Automatic_Evaluation_of_LLMs_on_Protocol_Planning", year := 2023 }
def p_034 : Paper := { id := "BLIP_2_Bootstrapping_Language_Image_Pre_training_with_Frozen", year := 2023 }
def p_035 : Paper := { id := "Block_Recurrent_Transformers", year := 2022 }
def p_036 : Paper := { id := "Paper_036", year := 2022 }
def p_037 : Paper := { id := "Brainformers_Trading_Simplicity_for_Efficiency", year := 2022 }
def p_038 : Paper := { id := "Bootstrap_Your_Own_Latent_A_New_Approach_to_Self_Supervised_", year := 2020 }
def p_039 : Paper := { id := "Neural_Machine_Translation_in_Linear_Time", year := 2017 }
def p_040 : Paper := { id := "CAMEL_Communicative_Agents_for_Mind_Exploration_of_Large_Lan", year := 2023 }
def p_041 : Paper := { id := "Dynamic_Routing_Between_Capsules", year := 2017 }
def p_042 : Paper := { id := "Chain_of_Thought_Prompting_Elicits_Reasoning_in_Large_Langua", year := 2022 }
def p_043 : Paper := { id := "ChatDev_Communicative_Agents_for_Software_Development", year := 2024 }
def p_044 : Paper := { id := "ChatEval_Towards_better_LLM_based_evaluators_through_multi_a", year := 2024 }
def p_045 : Paper := { id := "Training_Compute_Optimal_Large_Language_Models", year := 2021 }
def p_046 : Paper := { id := "Chronos_Learning_the_Language_of_Time_Series", year := 2024 }
def p_047 : Paper := { id := "Paper_047", year := 2023 }
def p_048 : Paper := { id := "Classifier_Free_Diffusion_Guidance", year := 2021 }
def p_049 : Paper := { id := "ARCHITECTURAL_BLUEPRINT_FOR_HETEROGENEITY_RESILIENT_FEDERATE", year := 2024 }
def p_050 : Paper := { id := "ClimaX_A_foundation_model_for_weather_and_climate", year := 2024 }
def p_051 : Paper := { id := "Learning_Transferable_Visual_Models_From_Natural_Language_Su", year := 2020 }
def p_052 : Paper := { id := "CodeRL_Mastering_Code_Generation_through_Pretrained_Models_a", year := 2022 }
def p_053 : Paper := { id := "CodeLlama_Open_Foundation_Models_for_Code", year := 2024 }
def p_054 : Paper := { id := "CogVLM_Visual_Expert_for_Pretrained_Language_Models", year := 2024 }
def p_055 : Paper := { id := "LQER_Low_Rank_Quantization_Error_Reconstruction_for_LLMs", year := 2024 }
def p_056 : Paper := { id := "What_to_align_in_multimodal_contrastive_learning", year := 2024 }
def p_057 : Paper := { id := "Getting_ViT_in_Shape_Scaling_Laws_for_Compute_Optimal_Model_", year := 2023 }
def p_058 : Paper := { id := "Consistency_Models", year := 2023 }
def p_059 : Paper := { id := "Constitutional_AI_Harmlessness_from_AI_Feedback", year := 2018 }
def p_060 : Paper := { id := "A_Comprehensive_Survey_of_Continual_Learning_Theory_Method_a", year := 2015 }
def p_061 : Paper := { id := "Adding_Conditional_Control_to_Text_to_Image_Diffusion_Models", year := 2024 }
def p_062 : Paper := { id := "A_ConvNet_for_the_2020s", year := 2022 }
def p_063 : Paper := { id := "Paper_063", year := 2024 }
def p_064 : Paper := { id := "Unpaired_Image_to_Image_Translation_using_Cycle_Consistent_A", year := 2024 }
def p_065 : Paper := { id := "Hierarchical_Text_Conditional_Image_Generation_with_CLIP_Lat", year := 2021 }
def p_066 : Paper := { id := "DARTS_Differentiable_Architecture_Search", year := 2024 }
def p_067 : Paper := { id := "Generalization_or_Memorization_Data_Contamination_and_Trustw", year := 2024 }
def p_068 : Paper := { id := "Towards_Self_Adaptive_Pseudo_Label_Filtering_for_Semi_Superv", year := 2022 }
def p_069 : Paper := { id := "DataComp_In_search_of_the_next_generation_of_multimodal_data", year := 2024 }
def p_070 : Paper := { id := "Denoising_Diffusion_Probabilistic_Models", year := 2020 }
def p_071 : Paper := { id := "Decision_Transformer_Reinforcement_Learning_via_Sequence_Mod", year := 2021 }
def p_072 : Paper := { id := "Deep_contextualized_word_representations", year := 2024 }
def p_073 : Paper := { id := "DeepSeek_R1_Incentivizing_Reasoning_Capability_in_LLMs_via_R", year := 2024 }
def p_074 : Paper := { id := "DeepSeek_V2_A_Strong_Economical_and_Efficient_Mixture_of_Exp", year := 2024 }
def p_075 : Paper := { id := "DeepSeek_V3_Technical_Report", year := 2024 }
def p_076 : Paper := { id := "DeepSeek_Coder_When_the_Large_Language_Model_Meets_Programmi", year := 2021 }
def p_077 : Paper := { id := "DeepSeek_Coder_V2_Breaking_the_Barrier_of_Closed_Source_Mode", year := 2021 }
def p_078 : Paper := { id := "DeepSeekMath_Pushing_the_Limits_of_Mathematical_Reasoning_in", year := 2021 }
def p_079 : Paper := { id := "DeepSeekMoE_Towards_Ultimate_Expert_Specialization_in_Mixtur", year := 2021 }
def p_080 : Paper := { id := "Kernel_methods_for_long_term_dose_response_curves", year := 2022 }
def p_081 : Paper := { id := "Training_data_efficient_image_transformers_distillation_thro", year := 2012 }
def p_082 : Paper := { id := "Depth_Anything_Unleashing_the_Power_of_Large_Scale_Unlabeled", year := 2024 }
def p_083 : Paper := { id := "End_to_End_Object_Detection_with_Transformers", year := 2024 }
def p_084 : Paper := { id := "Deformable_DETR_Deformable_Transformers_for_End_to_End_Objec", year := 2024 }
def p_085 : Paper := { id := "DiffDock_Diffusion_Steps_Twists_and_Turns_for_Molecular_Dock", year := 2024 }
def p_086 : Paper := { id := "Diffusion_LM_Improves_Controllable_Text_Generation", year := 2022 }
def p_087 : Paper := { id := "Emerging_Properties_in_Self_Supervised_Vision_Transformers", year := 2024 }
def p_088 : Paper := { id := "DINOv2_Learning_Robust_Visual_Features_withoutSupervision", year := 2024 }
def p_089 : Paper := { id := "DistilBERT_a_distilled_version_of_BERT_smaller_faster_cheape", year := 2019 }
def p_090 : Paper := { id := "Scalable_Diffusion_Models_with_Transformers", year := 2023 }
def p_091 : Paper := { id := "Are_Transformers_Effective_for_Time_Series_Forecasting", year := 2019 }
def p_092 : Paper := { id := "Direct_Preference_Optimization_Your_Language_Model_is_Secret", year := 2023 }
def p_093 : Paper := { id := "Negative_Preference_Optimization_From_Catastrophic_Collapse_", year := 2024 }
def p_094 : Paper := { id := "Instructions_for_ACL_Proceedings", year := 2024 }
def p_095 : Paper := { id := "Optimal_Policies_Tend_To_Seek_Power", year := 2021 }
def p_096 : Paper := { id := "Mastering_Atari_with_Discrete_World_Models", year := 2024 }
def p_097 : Paper := { id := "Mastering_Diverse_Domains_through_World_Models", year := 2019 }
def p_098 : Paper := { id := "Improving_neural_networks_by_preventing_co_adaptation_of_fea", year := 2010 }
def p_099 : Paper := { id := "EAGLE_Speculative_Sampling_Requires_Rethinking_Feature_Uncer", year := 2024 }
def p_100 : Paper := { id := "Elucidating_the_Design_Space_of_Diffusion_Based_Generative_M", year := 2022 }
def p_101 : Paper := { id := "Interleaving_Pre_Trained_Language_Models_and_Large_Language_", year := 2020 }
def p_102 : Paper := { id := "Efficient_Estimation_of_Word_Representations_in_Vector_Space", year := 2013 }
def p_103 : Paper := { id := "EfficientNet_Rethinking_Model_Scaling_for_Convolutional_Neur", year := 2019 }
def p_104 : Paper := { id := "EfficientNetV2_Smaller_Models_and_Faster_Training", year := 2021 }
def p_105 : Paper := { id := "Mastering_Atari_Games_with_Limited_Data", year := 2021 }
def p_106 : Paper := { id := "Embodied_Agent_Interface_Benchmarking_LLMs_for_Embodied_Deci", year := 2024 }
def p_107 : Paper := { id := "End_To_End_Memory_Networks", year := 2024 }
def p_108 : Paper := { id := "Disentangling_Learning_Representations_with_Density_Estimati", year := 2024 }
def p_109 : Paper := { id := "Exploring_the_Limits_of_Masked_Visual_Representation_Learnin", year := 2023 }
def p_110 : Paper := { id := "A_Visual_Representation_for_Neon_Genesis", year := 2024 }
def p_111 : Paper := { id := "WizardLM_Empowering_Large_Pre_Trained_Language_Models_to_Fol", year := 2022 }
def p_112 : Paper := { id := "The_Evolved_Transformer", year := 2019 }
def p_113 : Paper := { id := "Overcoming_catastrophic_forgetting_in_neural_networks", year := 2016 }
def p_114 : Paper := { id := "FActScore_Fine_grained_Atomic_Evaluation_of_Factual_Precisio", year := 2023 }
def p_115 : Paper := { id := "The_Falcon_Series_of_Open_Language_Models", year := 2022 }
def p_116 : Paper := { id := "Faster_R_CNN_Towards_Real_Time_Object_Detection_with_Region_", year := 2012 }
def p_117 : Paper := { id := "Submission_and_Formatting_Instructions_for_ICML_2022", year := 2021 }
def p_118 : Paper := { id := "Training_a_Helpful_and_Harmless_Assistant_with_Reinforcement", year := 2018 }
def p_119 : Paper := { id := "Flamingo_a_Visual_Language_Model_for_Few_Shot_Learning", year := 2022 }
def p_120 : Paper := { id := "FlashDecoding_Faster_Large_Language_Model_Inference_on_GPUs", year := 2024 }
def p_121 : Paper := { id := "Flow_Matching_for_Generative_Modeling", year := 2024 }
def p_122 : Paper := { id := "FNet_Mixing_Tokens_with_Fourier_Transforms", year := 2024 }
def p_123 : Paper := { id := "FourCastNet_A_Global_Data_driven_High_resolution_Weather_Mod", year := 1985 }
def p_124 : Paper := { id := "PyTorch_FSDP_Experiences_on_Scaling_Fully_Sharded_Data_Paral", year := 2023 }
def p_125 : Paper := { id := "Global_gravitational_anomaly_cancellation_for_five_branes", year := 2012 }
def p_126 : Paper := { id := "Generative_Adversarial_Nets", year := 2009 }
def p_127 : Paper := { id := "Graph_Attention_Networks", year := 2017 }
def p_128 : Paper := { id := "Universal_and_Transferable_Adversarial_Attacks_on_Aligned_La", year := 2024 }
def p_129 : Paper := { id := "Gemini_A_Family_of_Highly_Capable_Multimodal_Models", year := 2024 }
def p_130 : Paper := { id := "Gemini_15_Unlocking_multimodal_understanding_across_millions", year := 2024 }
def p_131 : Paper := { id := "Gemma_Open_Models_Based_on_Gemini_Research_and_Technology", year := 2024 }
def p_132 : Paper := { id := "Gemma_2_Improving_Open_Language_Models_at_a_Practical_Size", year := 2024 }
def p_133 : Paper := { id := "Generative_Agents_Interactive_Simulacra_of_Human_Behavior", year := 2023 }
def p_134 : Paper := { id := "GLaM_Efficient_Scaling_of_Language_Models_with_Mixture_of_Ex", year := 2021 }
def p_135 : Paper := { id := "Pay_Attention_to_MLPs", year := 2021 }
def p_136 : Paper := { id := "Language_Models_are_Few_Shot_Learners", year := 2019 }
def p_137 : Paper := { id := "GPT_4_Technical_Report", year := 2021 }
def p_138 : Paper := { id := "The_Dawn_of_LMMs_Preliminary_Explorations_with_GPT_4Vision", year := 2023 }
def p_139 : Paper := { id := "GPTQ_Accurate_Post_Training_Quantization_for_Generative_Pre_", year := 2024 }
def p_140 : Paper := { id := "Granite_Code_Models_A_Family_of_Open_Foundation_Models_for_C", year := 2024 }
def p_141 : Paper := { id := "Graph_of_Thoughts_Solving_Elaborate_Problems_with_Large_Lang", year := 2023 }
def p_142 : Paper := { id := "GraphCast_Learning_skillful_medium_range_global_weather_fore", year := 2022 }
def p_143 : Paper := { id := "Inductive_Representation_Learning_on_Large_Graphs", year := 2017 }
def p_144 : Paper := { id := "Griffin_Mixing_Gated_Linear_Recurrences_with_Local_Attention", year := 2024 }
def p_145 : Paper := { id := "Grounding_DINO_Marrying_DINO_with_Grounded_Pre_Training_for_", year := 2024 }
def p_146 : Paper := { id := "GShard_Scaling_Giant_Models_with_Conditional_Computation_and", year := 2020 }
def p_147 : Paper := { id := "Training_Verifiers_to_Solve_Math_Word_Problems", year := 2024 }
def p_148 : Paper := { id := "GTBench_Uncovering_the_Strategic_Reasoning_Limitations_of_LL", year := 2024 }
def p_149 : Paper := { id := "Hash_Layers_For_Large_Sparse_Models", year := 2021 }
def p_150 : Paper := { id := "Holistic_Evaluation_of_Language_Models", year := 2023 }
def p_151 : Paper := { id := "Humanoid_Agents_Platform_for_Simulating_Human_like_Generativ", year := 2023 }
def p_152 : Paper := { id := "Hyena_Hierarchy_Towards_Larger_Convolutional_Language_Models", year := 2024 }
def p_153 : Paper := { id := "Jailbreak_and_Guard_Aligned_Language_Models_with_Only_Few_In", year := 2024 }
def p_154 : Paper := { id := "Paper_154", year := 2023 }
def p_155 : Paper := { id := "ImageBind_One_Embedding_Space_To_Bind_Them_All", year := 2023 }
def p_156 : Paper := { id := "Leave_No_Context_Behind_Efficient_Infinite_Context_Transform", year := 2024 }
def p_157 : Paper := { id := "Informer_Beyond_Efficient_Transformer_for_Long_Sequence_Time", year := 2021 }
def p_158 : Paper := { id := "Instant_Neural_Graphics_Primitives_with_a_Multiresolution_Ha", year := 2022 }
def p_159 : Paper := { id := "InstructBLIP_Towards_General_purpose_Vision_Language_Models_", year := 2023 }
def p_160 : Paper := { id := "Training_language_models_to_follow_instructions_with_human_f", year := 2021 }
def p_161 : Paper := { id := "Language_Instructed_RL_for_Human_AI_Coordination", year := 2023 }
def p_162 : Paper := { id := "InternVL_Scaling_up_Vision_Foundation_Models_and_Aligning_fo", year := 2024 }
def p_163 : Paper := { id := "How_Far_Are_We_to_GPT_4V_Closing_the_Gap_to_Commercial_Multi", year := 2024 }
def p_164 : Paper := { id := "Monte_Carlo_Tree_Search_for_Behavior_Planning_in_Autonomous_", year := 2024 }
def p_165 : Paper := { id := "Implicit_Quantile_Networks_for_Distributional_Reinforcement_", year := 2018 }
def p_166 : Paper := { id := "Transformers_are_Sample_Efficient_World_Models", year := 2024 }
def p_167 : Paper := { id := "iTransformer_Inverted_Transformers_Are_Effective_for_Time_Se", year := 2024 }
def p_168 : Paper := { id := "SelfDefend_LLMs_Can_Defend_Themselves_against_Jailbreaking_i", year := 2024 }
def p_169 : Paper := { id := "Jailbroken_How_Does_LLM_Safety_Training_Fail", year := 2023 }
def p_170 : Paper := { id := "Jamba_A_Hybrid_Transformer_Mamba_Language_Model", year := 2023 }
def p_171 : Paper := { id := "Jamba_15_Hybrid_Transformer_Mamba_Models_at_Scale", year := 2023 }
def p_172 : Paper := { id := "Knowledge_Distillation_A_Survey", year := 2020 }
def p_173 : Paper := { id := "Kosmos_2_Grounding_Multimodal_Large_Language_Models_to_the_W", year := 2022 }
def p_174 : Paper := { id := "Model_Alignment_as_Prospect_Theoretic_Optimization", year := 2024 }
def p_175 : Paper := { id := "Lag_Llama", year := 2024 }
def p_176 : Paper := { id := "High_Resolution_Image_Synthesis_with_Latent_Diffusion_Models", year := 2021 }
def p_177 : Paper := { id := "Least_to_Most_Prompting_Enables_Complex_Reasoning_in_Large_L", year := 2024 }
def p_178 : Paper := { id := "Lets_Verify_Step_by_Step", year := 2024 }
def p_179 : Paper := { id := "LLaMA_MoE_Building_Mixture_of_Experts_from_LLaMA_with_Contin", year := 2023 }
def p_180 : Paper := { id := "LIMA_Less_Is_More_for_Alignment", year := 2023 }
def p_181 : Paper := { id := "Linformer_Self_Attention_with_Linear_Complexity", year := 2019 }
def p_182 : Paper := { id := "Liquid_Time_constant_Networks", year := 2016 }
def p_183 : Paper := { id := "Liquid_Structural_State_Space_Models", year := 2016 }
def p_184 : Paper := { id := "LLaMA_Open_and_Efficient_Foundation_Language_Models", year := 2023 }
def p_185 : Paper := { id := "Llama_2_Open_Foundation_and_Fine_Tuned_Chat_Models", year := 2024 }
def p_186 : Paper := { id := "Visual_Instruction_Tuning", year := 2023 }
def p_187 : Paper := { id := "The_Rise_and_Potential_of_Large_Language_Model_Based_Agents_", year := 2023 }
def p_188 : Paper := { id := "Training_Socially_Aligned_Language_Models_on_Simulated_Socia", year := 2024 }
def p_189 : Paper := { id := "Neural_Machine_Translation_Models_Can_Learn_to_be_Few_shot_L", year := 2023 }
def p_190 : Paper := { id := "LongBench_A_Bilingual_Multitask_Benchmark_for_Long_Context_U", year := 2024 }
def p_191 : Paper := { id := "Longformer_The_Long_Document_Transformer", year := 2020 }
def p_192 : Paper := { id := "LongLoRA_Efficient_Fine_tuning_of_Long_Context_Large_Languag", year := 2023 }
def p_193 : Paper := { id := "LoRA_Low_Rank_Adaptation_of_Large_Language_Models", year := 2024 }
def p_194 : Paper := { id := "LoRA_Meets_Dropout_under_a_Unified_Framework", year := 2024 }
def p_195 : Paper := { id := "Improving_Factuality_and_Reasoning_in_Language_Models_throug", year := 2023 }
def p_196 : Paper := { id := "Masked_Autoencoders_Are_Scalable_Vision_Learners", year := 2024 }
def p_197 : Paper := { id := "Unified_Directly_Denoising_for_Both_Variance_Preserving_and_", year := 2024 }
def p_198 : Paper := { id := "Mamba_Linear_Time_Sequence_Modeling_with_Selective_State_Spa", year := 2024 }
def p_199 : Paper := { id := "Model_Agnostic_Meta_Learning_for_Fast_Adaptation_of_Deep_Net", year := 2016 }
def p_200 : Paper := { id := "MathCoder_Seamless_Code_Integration_in_LLMs_for_Enhanced_Mat", year := 2024 }
def p_201 : Paper := { id := "Fast_Continual_Multi_View_Clustering_with_Incomplete_Views", year := 2021 }
def p_202 : Paper := { id := "Towards_Foundation_Models_for_Materials_Science_The_Open_Mat", year := 2010 }
def p_203 : Paper := { id := "Simple_LLM_Inference_Acceleration_Framework_with_Multiple_De", year := 2024 }
def p_204 : Paper := { id := "Mega_Moving_Average_Equipped_Gated_Attention", year := 2024 }
def p_205 : Paper := { id := "MegaByte_Predicting_Million_byte_Sequences_with_Multiscale_T", year := 2022 }
def p_206 : Paper := { id := "Megatron_LM_Training_Multi_Billion_Parameter_Language_Models", year := 2020 }
def p_207 : Paper := { id := "Systematic_Single_Deletion_Multiple_Substitution_Correcting_", year := 2020 }
def p_208 : Paper := { id := "MetaGPT_Meta_Programming_for_a_Multi_Agent_Collaborative_Fra", year := 2024 }
def p_209 : Paper := { id := "Mind2Web_Towards_a_Generalist_Agent_for_the_Web", year := 2023 }
def p_210 : Paper := { id := "Solving_Quantitative_Reasoning_Problems_with_Language_Models", year := 2020 }
def p_211 : Paper := { id := "MiniCPM_Unveiling_the_Potential_of_Small_Language_Models_wit", year := 2024 }
def p_212 : Paper := { id := "MiniGPT_4_Enhancing_Vision_Language_Understanding_with_Advan", year := 2024 }
def p_213 : Paper := { id := "Mistral7B", year := 2023 }
def p_214 : Paper := { id := "Mixtral_of_Experts", year := 2023 }
def p_215 : Paper := { id := "MLP_Mixer_An_all_MLP_Architecture_for_Vision", year := 2021 }
def p_216 : Paper := { id := "MMBench_Is_Your_Multi_modal_Model_an_All_around_Player", year := 2022 }
def p_217 : Paper := { id := "MME_A_Comprehensive_Evaluation_Benchmark_for_Multimodal_Larg", year := 2025 }
def p_218 : Paper := { id := "Measuring_Massive_Multitask_Language_Understanding", year := 2018 }
def p_219 : Paper := { id := "Momentum_Contrast_for_Unsupervised_Visual_Representation_Lea", year := 2024 }
def p_220 : Paper := { id := "Improved_Baselines_with_Momentum_Contrastive_Learning", year := 2024 }
def p_221 : Paper := { id := "An_Empirical_Study_of_Training_Self_Supervised_Vision_Transf", year := 2024 }
def p_222 : Paper := { id := "Equivariant_Neural_Simulators_for_Stochastic_Spatiotemporal_", year := 2023 }
def p_223 : Paper := { id := "Mixture_of_Experts_with_Expert_Choice_Routing", year := 2024 }
def p_224 : Paper := { id := "A_Survey_on_Mixture_of_Experts_in_Large_Language_Models", year := 2015 }
def p_225 : Paper := { id := "Unified_Training_of_Universal_Time_Series_Forecasting_Transf", year := 2024 }
def p_226 : Paper := { id := "mPLUG_Owl2_Revolutionizing_Multi_modal_Large_Language_Model_", year := 2024 }
def p_227 : Paper := { id := "Redefining_hallucination_in_LLMs", year := 2024 }
def p_228 : Paper := { id := "Large_Language_Model_based_Multi_Agents_A_Survey_of_Progress", year := 2023 }
def p_229 : Paper := { id := "Mastering_Atari_Go_Chess_and_Shogi_by_Planning_with_a_Learne", year := 2024 }
def p_230 : Paper := { id := "MVBench_A_Comprehensive_Multi_modal_Video_Understanding_Benc", year := 2024 }
def p_231 : Paper := { id := "Nash_Learning_from_Human_Feedback", year := 2024 }
def p_232 : Paper := { id := "Small_Language_Models_for_Application_Interactions_A_Case_St", year := 2024 }
def p_233 : Paper := { id := "Learning_Transferable_Architectures_for_Scalable_Image_Recog", year := 2024 }
def p_234 : Paper := { id := "Native_Sparse_Attention_Hardware_Aligned_and_Natively_Traina", year := 2024 }
def p_235 : Paper := { id := "How_Well_Can_LLMs_Negotiate_Platform_and_Analysis", year := 2021 }
def p_236 : Paper := { id := "NeRF_Representing_Scenes_as_Neural_Radiance_Fields_for_View_", year := 2010 }
def p_237 : Paper := { id := "Neural_Ordinary_Differential_Equations", year := 2018 }
def p_238 : Paper := { id := "A_Neural_Algorithm_of_Artistic_Style", year := 2024 }
def p_239 : Paper := { id := "Neural_Turing_Machines", year := 2024 }
def p_240 : Paper := { id := "Neural_General_Circulation_Models_for_Weather_and_Climate", year := 2023 }
def p_241 : Paper := { id := "The_Neuro_Symbolic_Concept_Learner_Interpreting_Scenes_Words", year := 2024 }
def p_242 : Paper := { id := "NExT_GPT_Any_to_Any_Multimodal_LLM", year := 2024 }
def p_243 : Paper := { id := "Non_Autoregressive_Neural_Machine_Translation", year := 2016 }
def p_244 : Paper := { id := "tfShearlab_The_TensorFlow_Digital_Shearlet_Transform_for_Dee", year := 2024 }
def p_245 : Paper := { id := "Offline_Reinforcement_Learning_Tutorial_Review_and_Perspecti", year := 2016 }
def p_246 : Paper := { id := "Accelerating_the_Science_of_Language_Models", year := 2023 }
def p_247 : Paper := { id := "Paper_247", year := 2022 }
def p_248 : Paper := { id := "OpenELM_An_Efficient_Language_Model_Family_with_Open_Trainin", year := 2022 }
def p_249 : Paper := { id := "Orca_Progressive_Learning_from_Complex_Explanation_Traces_of", year := 2023 }
def p_250 : Paper := { id := "ORPO_Monolithic_Preference_Optimization_without_Reference_Mo", year := 2023 }
def p_251 : Paper := { id := "PCArena_Benchmarking_Multimodal_Agents_for_Open_Ended_Tasks_", year := 2023 }
def p_252 : Paper := { id := "Otter_A_Multi_Modal_Model_with_In_Context_Instruction_Tuning", year := 2015 }
def p_253 : Paper := { id := "Jailbreaking_Black_Box_Large_Language_Models_in_Twenty_Queri", year := 2024 }
def p_254 : Paper := { id := "height_4pt_025in_PaLM_Scaling_Language_Modeling_with_Pathway", year := 2022 }
def p_255 : Paper := { id := "PaLM_E_An_Embodied_Multimodal_Language_Model", year := 2022 }
def p_256 : Paper := { id := "PandaGPT_One_Model_To_Instruction_Follow_Them_All", year := 2023 }
def p_257 : Paper := { id := "A_Time_Series_is_Worth_64_Words_Long_term_Forecasting_with_T", year := 2024 }
def p_258 : Paper := { id := "Rethinking_Attention_with_Performers", year := 2020 }
def p_259 : Paper := { id := "Phi_3_Technical_Report_A_Highly_Capable_Language_Model_Local", year := 2024 }
def p_260 : Paper := { id := "Image_to_Image_Translation_with_Conditional_Adversarial_Netw", year := 2024 }
def p_261 : Paper := { id := "Capacity_Credit_Evaluation_of_Generalized_Energy_Storage_Con", year := 2019 }
def p_262 : Paper := { id := "Paper_262", year := 2024 }
def p_263 : Paper := { id := "Reward_Constrained_Policy_Optimization", year := 2018 }
def p_264 : Paper := { id := "PySCIPOpt_ML_Embedding_Trained_Machine_Learning_Models_into_", year := 2024 }
def p_265 : Paper := { id := "Gaussian_Gated_Linear_Networks", year := 2020 }
def p_266 : Paper := { id := "Prefix_Tuning_Optimizing_Continuous_Prompts_for_Generation", year := 2020 }
def p_267 : Paper := { id := "ProAgent_Building_Proactive_Cooperative_Agents_with_Large_La", year := 2024 }
def p_268 : Paper := { id := "The_Power_of_Scale_for_Parameter_Efficient_Prompt_Tuning", year := 2021 }
def p_269 : Paper := { id := "Prototypical_Networks_for_Few_shot_Learning", year := 2017 }
def p_270 : Paper := { id := "Entanglement_entropy_and_Page_curve_from_the_M_theory_dual_o", year := 2020 }
def p_271 : Paper := { id := "QLoRA_Efficient_Finetuning_of_Quantized_LLMs", year := 2023 }
def p_272 : Paper := { id := "Qwen_VL_A_Versatile_Vision_Language_Model_for_Understanding_", year := 2024 }
def p_273 : Paper := { id := "Qwen2_VL_Enhancing_Vision_Language_Models_Perception_of_the_", year := 2024 }
def p_274 : Paper := { id := "Qwen2_Technical_Report", year := 2024 }
def p_275 : Paper := { id := "RAFT_Adapting_Language_Model_to_Domain_Specific_RAG", year := 2024 }
def p_276 : Paper := { id := "Retrieval_Augmented_Generation_for_Knowledge_Intensive_NLP_T", year := 2020 }
def p_277 : Paper := { id := "Rainbow_Combining_Improvements_in_Deep_Reinforcement_Learnin", year := 2018 }
def p_278 : Paper := { id := "ReAct_Synergizing_Reasoning_and_Acting_in_Language_Models", year := 2023 }
def p_279 : Paper := { id := "REALM_Retrieval_Augmented_Language_Model_Pre_Training", year := 2020 }
def p_280 : Paper := { id := "Red_Teaming_Language_Models_to_Reduce_Harms_Methods_Scaling_", year := 2018 }
def p_281 : Paper := { id := "Reflexion_Language_Agents_with_Verbal_Reinforcement_Learning", year := 2023 }
def p_282 : Paper := { id := "Reformer_The_Efficient_Transformer", year := 2019 }
def p_283 : Paper := { id := "ReMax_A_Simple_Effective_and_Efficient_Reinforcement_Learnin", year := 2024 }
def p_284 : Paper := { id := "Deep_Residual_Learning_for_Image_Recognition", year := 2015 }
def p_285 : Paper := { id := "Retentive_Network_A_Successor_to_Transformer_for_Large_Langu", year := 2023 }
def p_286 : Paper := { id := "Evaluating_Reward_Models_for_Language_Modeling", year := 2024 }
def p_287 : Paper := { id := "Ring_Attention_with_Blockwise_Transformers_for_Near_Infinite", year := 2023 }
def p_288 : Paper := { id := "RL4F_Generating_Natural_Language_Feedback_with_Reinforcement", year := 2023 }
def p_289 : Paper := { id := "RLAIF_vs_RLHF", year := 2024 }
def p_290 : Paper := { id := "Improving_Multimodal_Interactive_Agents_with_Reinforcement_L", year := 2019 }
def p_291 : Paper := { id := "Deep_Reinforcement_Learning_from_Human_Preferences", year := 2024 }
def p_292 : Paper := { id := "RLHF_V_Towards_Trustworthy_MLLMs_via_Behavior_Alignment_from", year := 2024 }
def p_293 : Paper := { id := "Back_to_Basics_Revisiting_REINFORCE_Style_Optimization_for_L", year := 2024 }
def p_294 : Paper := { id := "RRHF_Rank_Responses_to_Align_Language_Models_with_Human_Feed", year := 2024 }
def p_295 : Paper := { id := "RT_1_Robotics_Transformer_for_Real_World_Control_at_Scale", year := 2024 }
def p_296 : Paper := { id := "RT_2_Vision_Language_Action_Models_Transfer_Web_Knowledge_to", year := 2024 }
def p_297 : Paper := { id := "RWKV_Reinventing_RNNs_for_the_Transformer_Era", year := 2023 }
def p_298 : Paper := { id := "Efficiently_Modeling_Long_Sequences_with_Structured_State_Sp", year := 2024 }
def p_299 : Paper := { id := "Soft_Actor_Critic", year := 2018 }
def p_300 : Paper := { id := "SAM_2_Segment_Anything_in_Images_and_Videos", year := 2024 }
def p_301 : Paper := { id := "Segment_Anything_in_High_Quality", year := 2023 }
def p_302 : Paper := { id := "Segment_Anything", year := 2024 }
def p_303 : Paper := { id := "Sarathi_Efficient_LLM_Inference_by_Piggybacking_Decodes_with", year := 2024 }
def p_304 : Paper := { id := "Do_As_I_Can_Not_As_I_Say_Grounding_Language_in_Robotic_Affor", year := 2024 }
def p_305 : Paper := { id := "Reason_for_Future_Act_for_Now_A_Principled_Framework_for_Aut", year := 2024 }
def p_306 : Paper := { id := "Scaling_Laws_for_Neural_Language_Models", year := 2018 }
def p_307 : Paper := { id := "Scaling_LLM_Test_Time_Compute_Optimally_can_be_More_Effectiv", year := 2024 }
def p_308 : Paper := { id := "SciAgent_Tool_augmented_Language_Models_for_Scientific_Reaso", year := 2024 }
def p_309 : Paper := { id := "SDEdit_Guided_Image_Synthesis_and_Editing_with_Stochastic_Di", year := 2024 }
def p_310 : Paper := { id := "Self_Consistency_Improves_Chain_of_Thought_Reasoning_in_Lang", year := 2024 }
def p_311 : Paper := { id := "ACL_2023_Self_Instruct_Aligning_Language_Models_with_Self_Ge", year := 2023 }
def p_312 : Paper := { id := "Self_Play_Preference_Optimization_for_Language_Model_Alignme", year := 2024 }
def p_313 : Paper := { id := "Self_Rewarding_Language_Models", year := 2023 }
def p_314 : Paper := { id := "Sequence_to_Sequence_Learning_with_Neural_Networks", year := 2024 }
def p_315 : Paper := { id := "A_Simple_Framework_for_Contrastive_Learning_of_Visual_Repres", year := 2020 }
def p_316 : Paper := { id := "SimPO_Simple_Preference_Optimization_with_a_Reference_Free_R", year := 2024 }
def p_317 : Paper := { id := "Skeleton_of_Thought_Prompting_LLMs_for_Efficient_Parallel_Ge", year := 2024 }
def p_318 : Paper := { id := "SLiC_HF_Sequence_Likelihood_Calibration_with_Human_Feedback", year := 2023 }
def p_319 : Paper := { id := "DESTINE_Dynamic_Goal_Queries_with_Temporal_Transductive_Alig", year := 2024 }
def p_320 : Paper := { id := "Ghost_in_the_Minecraft_Generally_Capable_Agents_for_Open_Wor", year := 2024 }
def p_321 : Paper := { id := "White_Box_Adversarial_Attacks_on_Deep_Learning_Based_Radio_F", year := 2024 }
def p_322 : Paper := { id := "Scaling_and_evaluating_sparse_autoencoders", year := 2024 }
def p_323 : Paper := { id := "Generating_Long_Sequences_with_Sparse_Transformers", year := 2019 }
def p_324 : Paper := { id := "Empowering_Large_Language_Models_with_Intrinsic_Cross_Modal_", year := 2023 }
def p_325 : Paper := { id := "Self_Play_Fine_Tuning_Converts_Weak_Language_Models_to_Stron", year := 2024 }
def p_326 : Paper := { id := "Dishonesty_in_Helpful_and_Harmless_Alignment", year := 2023 }
def p_327 : Paper := { id := "ST_MoE_Designing_Stable_and_Transferable_Sparse_Expert_Model", year := 2024 }
def p_328 : Paper := { id := "Stable_Video_Diffusion_Scaling_Latent_Video_Diffusion_Models", year := 2024 }
def p_329 : Paper := { id := "StarCoder_may_the_source_be_with_you", year := 2023 }
def p_330 : Paper := { id := "GameBench_Evaluating_Strategic_Reasoning_Abilities_of_LLM_Ag", year := 2023 }
def p_331 : Paper := { id := "Efficient_Streaming_Language_Models_with_Attention_Sinks", year := 2024 }
def p_332 : Paper := { id := "A_Style_Based_Generator_Architecture_for_Generative_Adversar", year := 2024 }
def p_333 : Paper := { id := "Analyzing_and_Improving_the_Image_Quality_of_StyleGAN", year := 2024 }
def p_334 : Paper := { id := "Diffusion_Models_A_Comprehensive_Survey_of_Methods_and_Appli", year := 2023 }
def p_335 : Paper := { id := "ShapeShift_Superquadric_based_Object_Pose_Estimation_for_Rob", year := 2023 }
def p_336 : Paper := { id := "Paper_336", year := 2010 }
def p_337 : Paper := { id := "A_Comprehensive_Survey_of_AI_Generated_Content_AIGC_A_Histor", year := 2018 }
def p_338 : Paper := { id := "A_Survey_on_Hallucination_in_Large_Language_Models_Principle", year := 2024 }
def p_339 : Paper := { id := "A_Survey_on_Knowledge_Distillation_of_Large_Language_Models", year := 2024 }
def p_340 : Paper := { id := "A_Survey_of_Large_Language_Models", year := 2026 }
def p_341 : Paper := { id := "Large_Language_Model_Alignment_A_Survey", year := 2024 }
def p_342 : Paper := { id := "Bias_and_Fairness_in_Large_Language_Models_A_Survey", year := 2024 }
def p_343 : Paper := { id := "Commonsense_Reasoning_for_Conversational_AI_A_Survey_of_the_", year := 2023 }
def p_344 : Paper := { id := "A_Comprehensive_Survey_of_Compression_Algorithms_for_Languag", year := 2024 }
def p_345 : Paper := { id := "On_the_Creativity_of_Large_Language_Models", year := 2020 }
def p_346 : Paper := { id := "Large_Language_Models_for_Education_A_Survey_and_Outlook", year := 2018 }
def p_347 : Paper := { id := "Learning_to_Control_under_Uncertainty_with_Data_Based_Iterat", year := 2024 }
def p_348 : Paper := { id := "A_Survey_on_Evaluation_of_Large_Language_Models", year := 2018 }
def p_349 : Paper := { id := "Large_Language_Models_in_Finance_A_Survey", year := 2023 }
def p_350 : Paper := { id := "Instruction_Tuning_for_Large_Language_Models_A_Survey", year := 2025 }
def p_351 : Paper := { id := "Galaxy_Zoo_DESI_Detailed_Morphology_Measurements_for_87M_Gal", year := 2015 }
def p_352 : Paper := { id := "Towards_Reasoning_in_Large_Language_Models_A_Survey", year := 2023 }
def p_353 : Paper := { id := "Large_Language_Models_for_Mathematical_Reasoning_Progresses_", year := 2024 }
def p_354 : Paper := { id := "A_Survey_on_Medical_Large_Language_Models_Technology_Applica", year := 2024 }
def p_355 : Paper := { id := "A_Systematic_Survey_of_Prompt_Engineering_in_Large_Language_", year := 2024 }
def p_356 : Paper := { id := "Multi_Step_Reasoning_with_Large_Language_Models_a_Survey", year := 2021 }
def p_357 : Paper := { id := "A_Survey_of_Safety_and_Trustworthiness_of_Large_Language_Mod", year := 2023 }
def p_358 : Paper := { id := "A_Comprehensive_Survey_of_Scientific_Large_Language_Models_a", year := 2024 }
def p_359 : Paper := { id := "Tool_Learning_with_Large_Language_Models_A_Survey", year := 2016 }
def p_360 : Paper := { id := "Understanding_World_or_Predicting_Future_A_Comprehensive_Sur", year := 2024 }
def p_361 : Paper := { id := "Advancing_Transformer_Architecture_in_Long_Context_Large_Lan", year := 2024 }
def p_362 : Paper := { id := "A_Survey_on_Multimodal_Large_Language_Models", year := 2015 }
def p_363 : Paper := { id := "Parameter_Efficient_Fine_Tuning_for_Large_Models_A_Comprehen", year := 2024 }
def p_364 : Paper := { id := "Paper_364", year := 2019 }
def p_365 : Paper := { id := "Retrieval_Augmented_Generation_for_Large_Language_Models_A_S", year := 2024 }
def p_366 : Paper := { id := "SWE_agent_Agent_Computer_Interfaces_Enable_Automated_Softwar", year := 2024 }
def p_367 : Paper := { id := "Swin_Transformer_Hierarchical_Vision_Transformer_using_Shift", year := 2024 }
def p_368 : Paper := { id := "Switch_Transformers_Scaling_to_Trillion_Parameter_Models_wit", year := 2022 }
def p_369 : Paper := { id := "Synthesizer_Rethinking_Self_Attention_for_Transformer_Models", year := 2020 }
def p_370 : Paper := { id := "Exploring_the_Limits_of_Transfer_Learning_with_a_Unified_Tex", year := 2020 }
def p_371 : Paper := { id := "Scaling_Up_Models_and_Data_with_t5x_and_seqio", year := 2024 }
def p_372 : Paper := { id := "Tree_of_Attacks_Jailbreaking_Black_Box_LLMs_Automatically", year := 2024 }
def p_373 : Paper := { id := "An_Empirical_Evaluation_of_Generic_Convolutional_and_Recurre", year := 2018 }
def p_374 : Paper := { id := "Addressing_Function_Approximation_Error_in_Actor_Critic_Meth", year := 2018 }
def p_375 : Paper := { id := "TD_MPC2_Scalable_Robust_World_Models_for_Continuous_Control", year := 2024 }
def p_376 : Paper := { id := "Textbooks_Are_All_You_Need", year := 2023 }
def p_377 : Paper := { id := "The_Pile_An_800GB_Dataset_of_Diverse_Text_for_Language_Model", year := 2020 }
def p_378 : Paper := { id := "Time_LLM_Time_Series_Forecasting_by_Reprogramming_Large_Lang", year := 2024 }
def p_379 : Paper := { id := "TimesNet_Temporal_2D_Variation_Modeling_for_General_Time_Ser", year := 2024 }
def p_380 : Paper := { id := "TinyBERT_Distilling_BERT_for_Natural_Language_Understanding", year := 2020 }
def p_381 : Paper := { id := "ToolLLM_Facilitating_Large_Language_Models_to_Master_16000_R", year := 2024 }
def p_382 : Paper := { id := "Identifying_the_Risks_of_LM_Agents_with_an_LM_Emulated_Sandb", year := 2024 }
def p_383 : Paper := { id := "Toolformer_Language_Models_Can_Teach_Themselves_to_Use_Tools", year := 2021 }
def p_384 : Paper := { id := "Transformers_in_Reinforcement_Learning_A_Survey", year := 2017 }
def p_385 : Paper := { id := "Tree_of_Thoughts_Deliberate_Problem_Solving_with_Large_Langu", year := 2023 }
def p_386 : Paper := { id := "Trellis_Networks_for_Sequence_Modeling", year := 2024 }
def p_387 : Paper := { id := "Trust_Region_Policy_Optimization", year := 2015 }
def p_388 : Paper := { id := "Uni_Perceiver_MoE_Learning_Sparse_Generalist_Models_with_Con", year := 2022 }
def p_389 : Paper := { id := "Universal_Transformers", year := 2024 }
def p_390 : Paper := { id := "Auto_Encoding_Variational_Bayes", year := 2024 }
def p_391 : Paper := { id := "Very_Deep_Convolutional_Networks_for_Large_Scale_Image_Recog", year := 2015 }
def p_392 : Paper := { id := "Video_LLaVA_Learning_United_Visual_Representation_by_Alignme", year := 2024 }
def p_393 : Paper := { id := "VideoChat_Chat_Centric_Video_Understanding", year := 2022 }
def p_394 : Paper := { id := "An_Image_is_Worth_16x16_Words_Transformers_for_Image_Recogni", year := 2024 }
def p_395 : Paper := { id := "Efficient_Memory_Management_for_Large_Language_Model_Serving", year := 2023 }
def p_396 : Paper := { id := "An_Open_Ended_Embodied_Agent_with_Large_Language_Models", year := 2023 }
def p_397 : Paper := { id := "War_and_Peace_WarAgent_LLM_based_Multi_Agent_Simulation_of_W", year := 2024 }
def p_398 : Paper := { id := "wav2vec_20_A_Framework_for_Self_Supervised_Learning_of_Speec", year := 2020 }
def p_399 : Paper := { id := "WebArena_A_Realistic_Web_Environment_for_Building_Autonomous", year := 2024 }
def p_400 : Paper := { id := "Robust_Speech_Recognition_via_Large_Scale_Weak_Supervision", year := 2022 }
def p_401 : Paper := { id := "World_Models", year := 2018 }
def p_402 : Paper := { id := "Unsupervised_Cross_lingual_Representation_Learning_at_Scale", year := 2020 }
def p_403 : Paper := { id := "XLNet_Generalized_Autoregressive_Pretraining_for_Language_Un", year := 2019 }
def p_404 : Paper := { id := "YaRN_Efficient_Context_Window_Extension_of_Large_Language_Mo", year := 2024 }
def p_405 : Paper := { id := "Yi_Open_Foundation_Models_by_01AI", year := 2023 }
def p_406 : Paper := { id := "You_Only_Look_Once_Unified_Real_Time_Object_Detection", year := 2012 }
def p_407 : Paper := { id := "YOLOv7_Trainable_bag_of_freebies_sets_new_state_of_the_art_f", year := 2020 }
def p_408 : Paper := { id := "Learning_Better_Representations_From_Less_Data_For_Propositi", year := 2024 }
def p_409 : Paper := { id := "ZeRO_Memory_Optimizations_Toward_Training_Trillion_Parameter", year := 2024 }
def p_410 : Paper := { id := "Value_Bonuses_using_Ensemble_Errors_for_Exploration_in_Reinf", year := 2025 }
def p_411 : Paper := { id := "Learning_Universal_Graph_Neural_Network_Embeddings_With_Aid_", year := 2019 }
def p_412 : Paper := { id := "Graph_Neural_Network_Training_Systems_A_Performance_Comparis", year := 2025 }
def p_413 : Paper := { id := "Proficient_Graph_Neural_Network_Design_by_Accumulating_Knowl", year := 2026 }
def p_414 : Paper := { id := "Fast_and_Deep_Graph_Neural_Networks", year := 2020 }
def p_415 : Paper := { id := "Atom_Neural_Traffic_Compression_with_Spatio_Temporal_Graph_N", year := 2023 }
def p_416 : Paper := { id := "Transformers_are_Graph_Neural_Networks", year := 2021 }
def p_417 : Paper := { id := "MECCH_Metapath_Context_Convolution_based_Heterogeneous_Graph", year := 2015 }
def p_418 : Paper := { id := "Graph_neural_network_for_colliding_particles_with_an_applica", year := 2024 }
def p_419 : Paper := { id := "Modern_graph_neural_networks_do_worse_than_classical_greedy_", year := 2021 }
def p_420 : Paper := { id := "Detecting_Contextual_Network_Anomalies_with_Graph_Neural_Net", year := 2023 }
def p_421 : Paper := { id := "A_Tutorial_about_Random_Neural_Networks_in_Supervised_Learni", year := 2015 }
def p_422 : Paper := { id := "Masked_Conditional_Neural_Networks_for_Audio_Classification", year := 2024 }
def p_423 : Paper := { id := "The_Deep_Arbitrary_Polynomial_Chaos_Neural_Network_or_how_De", year := 2019 }
def p_424 : Paper := { id := "Development_of_a_Sensory_Neural_Network_for_Medical_Diagnosi", year := 2024 }
def p_425 : Paper := { id := "A_Review_on_Neural_Network_Models_of_Schizophrenia_and_Autis", year := 2018 }
def p_426 : Paper := { id := "How_transferable_are_features_in_deep_neural_networks", year := 2014 }
def p_427 : Paper := { id := "Parallel_Neural_Networks_in_Golang", year := 2024 }
def p_428 : Paper := { id := "Dual_Accuracy_Quality_Driven_Neural_Network_for_Prediction_I", year := 2023 }
def p_429 : Paper := { id := "Midterm_Status_Report_of_the_ILC_Technology_Network_Activiti", year := 2026 }
def p_430 : Paper := { id := "TradingAgents_Multi_Agents_LLM_Financial_Trading_Framework", year := 2025 }
def p_431 : Paper := { id := "Causal_Explanations_for_Sequential_Decision_Making_in_Multi_", year := 2024 }
def p_432 : Paper := { id := "Context_Engineering_for_Multi_Agent_LLM_Code_Assistants_Usin", year := 2025 }
def p_433 : Paper := { id := "LLM_Constitutional_Multi_Agent_Governance", year := 2024 }
def p_434 : Paper := { id := "Learning_the_Value_Systems_of_Agents_with_Preference_based_a", year := 2023 }
def p_435 : Paper := { id := "AOAD_MAT_Transformer_based_Multi_Agent_Deep_Reinforcement_Le", year := 2022 }
def p_436 : Paper := { id := "GOV_REK_Governed_Reward_Engineering_Kernels_for_Designing_Ro", year := 2022 }
def p_437 : Paper := { id := "Automatic_Verification_of_Parameterised_Interleaved_Multi_Ag", year := 2024 }
def p_438 : Paper := { id := "Towards_Effective_GenAI_Multi_Agent_Collaboration_Design_and", year := 2024 }
def p_439 : Paper := { id := "A_Survey_of_Multi_Agent_Deep_Reinforcement_Learning_with_Com", year := 2024 }

-- ===================================================================
-- Citation Relations (key citations between landmark papers)
-- ===================================================================

def citationsDb : List Citation := [
  { source := "BERT", target := "Attention_Is_All_You_Need" },
  { source := "GPT2", target := "GPT" },
  { source := "GPT3", target := "GPT2" },
  { source := "T5", target := "BERT" },
  { source := "DeBERTa", target := "BERT" },
  { source := "Decoder_Only", target := "Transformer" },
  { source := "Mamba", target := "Transformer" },
  { source := "LoRA_Algorithm", target := "Transformer" },
  { source := "QLoRA", target := "LoRA_Algorithm" },
  { source := "Flash_Attention", target := "Transformer" },
  { source := "Speculative_Decoding", target := "Decoder_Only" },
  { source := "MoE", target := "Transformer" },
  { source := "Switch_Transformer", target := "MoE" },
  { source := "DPO_Loss", target := "PPO_Objective" },
  { source := "DPO_Loss", target := "RLHF" },
  { source := "KTO", target := "DPO_Loss" },
  { source := "ORPO", target := "DPO_Loss" },
  { source := "RLHF", target := "PPO_Objective" },
  { source := "Constitutional_AI", target := "RLHF" },
  { source := "Instruct_Tuning", target := "GPT3" },
  { source := "Diffusion_Architecture", target := "GAN_Architecture" },
  { source := "Diffusion_Architecture", target := "VAE" },
  { source := "Latent_Diffusion", target := "Diffusion_Architecture" },
  { source := "Stable_Diffusion", target := "Latent_Diffusion" },
  { source := "Score_Matching", target := "Diffusion_Architecture" },
  { source := "Classifier_Free_Guidance", target := "Diffusion_Architecture" },
  { source := "Flow_Matching_Objective", target := "Diffusion_Architecture" },
  { source := "Consistency_Model", target := "Diffusion_Architecture" },
  { source := "StyleGAN", target := "GAN_Architecture" },
  { source := "ViT", target := "Transformer" },
  { source := "ViT", target := "ResNet" },
  { source := "DINOv2", target := "ViT" },
  { source := "SAM", target := "ViT" },
  { source := "ConvNeXt", target := "ResNet" },
  { source := "ConvNeXt", target := "ViT" },
  { source := "EfficientNet", target := "CNN" },
  { source := "CLIP", target := "Transformer" },
  { source := "CLIP", target := "ResNet" },
  { source := "Flamingo", target := "CLIP" },
  { source := "Flamingo", target := "GPT3" },
  { source := "LLaVA", target := "CLIP" },
  { source := "LLaVA", target := "LLaMA" },
  { source := "BLIP2", target := "CLIP" },
  { source := "GPT4V", target := "GPT3" },
  { source := "Qwen_VL", target := "CLIP" },
  { source := "CogVLM", target := "CLIP" },
  { source := "Chain_of_Thought", target := "GPT3" },
  { source := "ReAct", target := "Chain_of_Thought" },
  { source := "Tree_of_Thought", target := "Chain_of_Thought" },
  { source := "Reflexion", target := "ReAct" },
  { source := "Self_Consistency", target := "Chain_of_Thought" },
  { source := "Tool_Use", target := "GPT3" },
  { source := "Multi_Agent", target := "ReAct" },
  { source := "LSTM", target := "RNN" },
  { source := "GRU", target := "RNN" },
  { source := "Seq2Seq", target := "RNN" },
  { source := "Bahdanau_Attention", target := "Seq2Seq" },
  { source := "Transformer", target := "Bahdanau_Attention" },
  { source := "Dense_Passage_Retrieval", target := "BERT" },
  { source := "ColBERT", target := "BERT" },
  { source := "RAG_Framework", target := "BERT" },
  { source := "RAG_Framework", target := "Dense_Passage_Retrieval" },
  { source := "E5_Embedding", target := "BERT" },
  { source := "BGE_Embedding", target := "BERT" },
  { source := "Sentence_Transformers", target := "BERT" },
  { source := "GAT", target := "GCN" },
  { source := "GraphSAGE", target := "GCN" },
  { source := "GIN", target := "GCN" },
  { source := "AdamW", target := "Adam" },
  { source := "LAMB", target := "Adam" },
  { source := "Lion", target := "Adam" },
  { source := "Chinchilla", target := "Kaplan_Law" },
  { source := "Emergent_Abilities", target := "Kaplan_Law" },
  { source := "Grokking", target := "Double_Descent" },
  { source := "RLHF_Safety", target := "RLHF" },
  { source := "Red_Teaming", target := "RLHF_Safety" },
  { source := "Constitutional_AI_Safety", target := "Constitutional_AI" },
  { source := "DPO_Safety", target := "DPO_Loss" },
  { source := "Guardrails", target := "RLHF_Safety" },
  { source := "Watermarking", target := "GPT3" },
  { source := "Wav2Vec2", target := "BERT" },
  { source := "Whisper", target := "GPT3" },
  { source := "EnCodec", target := "VAE" },
  { source := "Copilot", target := "GPT3" },
  { source := "CodeLLaMA", target := "LLaMA" },
  { source := "StarCoder", target := "GPT3" },
  { source := "MAML", target := "Adam" },
  { source := "Prototypical_Networks", target := "MAML" },
  { source := "Rainbow_DQN", target := "DQN" },
  { source := "A3C", target := "Policy_Gradient" },
  { source := "SAC", target := "Policy_Gradient" },
  { source := "TD3", target := "SAC" },
  { source := "MuZero", target := "DQN" },
  { source := "Dreamer", target := "MuZero" },
  { source := "QLoRA", target := "Quantization" },
  { source := "INT8_Quantization", target := "Quantization" },
  { source := "Knowledge_Distillation", target := "ResNet" },
  { source := "Pruning", target := "CNN" },
  { source := "MAE", target := "ViT" },
  { source := "SimCLR", target := "ResNet" },
  { source := "BYOL", target := "SimCLR" },
  { source := "Word2Vec", target := "RNN" },
  { source := "BERT", target := "Word2Vec" },
  { source := "GPT", target := "Transformer" },
  { source := "GPT", target := "Word2Vec" }
]

-- ===================================================================
-- Replacement Relations (formal proof targets)
-- ===================================================================

def replacesDb : List Replacement := [
  { source := "RNN", target := "Transformer" },
  { source := "LSTM", target := "Transformer" },
  { source := "GAN_Architecture", target := "Diffusion_Architecture" },
  { source := "PPO_Objective", target := "DPO_Loss" },
  { source := "CNN", target := "ViT" },
  { source := "BM25", target := "Dense_Passage_Retrieval" },
  { source := "VAE", target := "Diffusion_Architecture" },
  { source := "StyleGAN", target := "Latent_Diffusion" },
  { source := "Seq2Seq", target := "Transformer" },
  { source := "SGD_Momentum", target := "Adam" },
  { source := "Adam", target := "AdamW" },
  { source := "MAML", target := "Reptile" },
  { source := "GCN", target := "GAT" },
  { source := "DQN", target := "Rainbow_DQN" },
  { source := "Policy_Gradient", target := "SAC" },
  { source := "WaveNet", target := "Whisper" },
  { source := "Pruning", target := "LoRA_Algorithm" },
  { source := "Quantization", target := "QLoRA" },
  { source := "Knowledge_Distillation", target := "LoRA_Algorithm" }
]

end AiEvolution.Database
